"""CryptoAID CHAT02 canonical Evidence + Payment + Entitlement Engine.

Metadata and ledgers live in the canonical SQLite authority supplied at runtime.
Evidence bytes are stored under a private root outside public webroot. No real
transaction is initiated by this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EVIDENCE_VERSION = "1.0"
PAYMENT_VERSION = "1.0"
ENTITLEMENT_VERSION = "1.0"
TREASURY_CONFIG_VERSION = "1.0"
CHAIN_ID = 137
DEFAULT_TREASURY = "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C"

PAYMENT_TRANSITIONS = {
    "INTENT_CREATED": {"USER_ACTION_REQUIRED", "EXPIRED"},
    "USER_ACTION_REQUIRED": {"TX_OBSERVED", "EXPIRED"},
    "TX_OBSERVED": {"VERIFYING", "MANUAL_REVIEW", "REJECTED"},
    "VERIFYING": {"FINALITY_PENDING", "MANUAL_REVIEW", "REJECTED"},
    "FINALITY_PENDING": {"SETTLED", "MANUAL_REVIEW", "REJECTED"},
    "SETTLED": set(), "MANUAL_REVIEW": set(), "REJECTED": set(), "EXPIRED": set(),
}

class EvidencePaymentError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code = code

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

class EvidencePaymentEngine:
    def __init__(self, db_path: str | Path, private_root: str | Path):
        self.db_path = Path(db_path)
        self.private_root = Path(private_root).resolve()
        if "public_html" in {p.lower() for p in self.private_root.parts}:
            raise EvidencePaymentError("PUBLIC_STORAGE_FORBIDDEN", "Evidence root must be outside public_html")
        self.private_root.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init_schema(self) -> None:
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS evidence_records(
              evidence_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL,
              parent_evidence_id TEXT, status TEXT NOT NULL, original_name TEXT NOT NULL,
              mime_declared TEXT NOT NULL, mime_detected TEXT NOT NULL, size_bytes INTEGER NOT NULL,
              sha256 TEXT NOT NULL, storage_relpath TEXT NOT NULL, uploader TEXT NOT NULL,
              consent_id TEXT NOT NULL, authorization TEXT NOT NULL, reason TEXT,
              created_at TEXT NOT NULL, superseded_at TEXT, UNIQUE(case_id, sha256, version));
            CREATE TABLE IF NOT EXISTS payment_intents(
              intent_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entitlement_ref TEXT NOT NULL,
              payer TEXT NOT NULL, chain_id INTEGER NOT NULL, asset TEXT NOT NULL,
              expected_value TEXT NOT NULL, treasury_id TEXT NOT NULL, treasury_address TEXT NOT NULL,
              state TEXT NOT NULL, tx_hash TEXT UNIQUE, request_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS payment_events(
              event_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, previous_state TEXT, new_state TEXT NOT NULL,
              reason TEXT NOT NULL, provider_data TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entitlement_ledger(
              entry_id TEXT PRIMARY KEY, entitlement_ref TEXT NOT NULL, case_id TEXT NOT NULL,
              intent_id TEXT NOT NULL UNIQUE, delta INTEGER NOT NULL, reason TEXT NOT NULL,
              lineage TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS treasury_config(
              treasury_id TEXT NOT NULL, version INTEGER NOT NULL, address TEXT NOT NULL, chain_id INTEGER NOT NULL,
              asset TEXT NOT NULL, status TEXT NOT NULL, priority INTEGER NOT NULL, routing_rule TEXT NOT NULL,
              valid_from TEXT NOT NULL, valid_to TEXT, created_by TEXT NOT NULL, approved_by TEXT NOT NULL,
              created_at TEXT NOT NULL, PRIMARY KEY(treasury_id, version));
            """)
            if not c.execute("SELECT 1 FROM treasury_config LIMIT 1").fetchone():
                c.execute("INSERT INTO treasury_config VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("treasury_primary",1,DEFAULT_TREASURY,CHAIN_ID,"POL","ACTIVE",1,"DEFAULT",_now(),None,"SYSTEM","SYSTEM",_now()))

    def store_evidence(self, *, case_id: str, content: bytes, original_name: str, mime_declared: str,
                       mime_detected: str, uploader: str, consent_id: str, authorization: str,
                       max_bytes: int = 25_000_000, allowed_mimes: Iterable[str] = ("application/pdf","image/png","image/jpeg"),
                       parent_evidence_id: str | None = None, reason: str = "UPLOAD") -> dict[str, Any]:
        if not authorization or authorization == "DENIED": raise EvidencePaymentError("UNAUTHORIZED", "Evidence authorization required")
        if not consent_id: raise EvidencePaymentError("CONSENT_REQUIRED", "Consent binding required")
        if len(content) > max_bytes: raise EvidencePaymentError("OVERSIZED", "Evidence exceeds size limit")
        allowed = set(allowed_mimes)
        if mime_declared not in allowed or mime_detected not in allowed or mime_declared != mime_detected:
            raise EvidencePaymentError("MIME_REJECTED", "MIME validation failed")
        digest = hashlib.sha256(content).hexdigest(); evidence_id = _id("ev")
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            version = 1
            if parent_evidence_id:
                parent = c.execute("SELECT * FROM evidence_records WHERE evidence_id=?", (parent_evidence_id,)).fetchone()
                if not parent or parent["case_id"] != case_id: raise EvidencePaymentError("BAD_LINEAGE", "Invalid evidence parent")
                version = int(parent["version"]) + 1
            rel = Path(case_id) / evidence_id / f"v{version}.bin"; dest = self.private_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".quarantine"); tmp.write_bytes(content); os.replace(tmp, dest)
            c.execute("INSERT INTO evidence_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (evidence_id,case_id,version,parent_evidence_id,"AVAILABLE",original_name,mime_declared,mime_detected,len(content),digest,str(rel),uploader,consent_id,authorization,reason,_now(),None))
            if parent_evidence_id:
                c.execute("UPDATE evidence_records SET status='SUPERSEDED', superseded_at=? WHERE evidence_id=?", (_now(),parent_evidence_id))
            c.execute("COMMIT")
        return {"evidence_id":evidence_id,"case_id":case_id,"version":version,"sha256":digest,"status":"AVAILABLE"}

    def configure_treasury(self, *, treasury_id: str, address: str, asset: str, status: str, priority: int,
                           routing_rule: str, valid_from: str, valid_to: str | None, created_by: str, approved_by: str) -> dict[str, Any]:
        if status not in {"ACTIVE","INACTIVE","RETIRED"}: raise EvidencePaymentError("BAD_STATUS", "Invalid treasury status")
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            count = c.execute("SELECT COUNT(DISTINCT treasury_id) FROM treasury_config").fetchone()[0]
            exists = c.execute("SELECT 1 FROM treasury_config WHERE treasury_id=? LIMIT 1",(treasury_id,)).fetchone()
            if not exists and count >= 100: raise EvidencePaymentError("TREASURY_LIMIT", "Maximum 100 treasury entries")
            version = c.execute("SELECT COALESCE(MAX(version),0)+1 FROM treasury_config WHERE treasury_id=?",(treasury_id,)).fetchone()[0]
            c.execute("INSERT INTO treasury_config VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (treasury_id,version,address,CHAIN_ID,asset,status,priority,routing_rule,valid_from,valid_to,created_by,approved_by,_now()))
            c.execute("COMMIT")
        return {"treasury_id":treasury_id,"version":version,"status":status}

    def _route_treasury(self, asset: str) -> sqlite3.Row:
        with self._connect() as c:
            row=c.execute("SELECT * FROM treasury_config WHERE status='ACTIVE' AND chain_id=? AND asset=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) ORDER BY priority,version DESC LIMIT 1",(CHAIN_ID,asset,_now(),_now())).fetchone()
        if not row: raise EvidencePaymentError("NO_TREASURY", "No active treasury route")
        return row

    def create_payment_intent(self, *, case_id: str, entitlement_ref: str, payer: str, asset: str,
                              expected_value: str, request_id: str, idempotency_key: str) -> dict[str, Any]:
        with self._connect() as c:
            existing=c.execute("SELECT * FROM payment_intents WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if existing: return dict(existing)
        t=self._route_treasury(asset); intent_id=_id("pi"); now=_now()
        with self._connect() as c:
            c.execute("INSERT INTO payment_intents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (intent_id,case_id,entitlement_ref,payer,CHAIN_ID,asset,expected_value,t["treasury_id"],t["address"],"INTENT_CREATED",None,request_id,idempotency_key,now,now))
            c.execute("INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",(_id("pe"),intent_id,None,"INTENT_CREATED","intent created",None,now))
        return self.get_intent(intent_id)

    def get_intent(self, intent_id: str) -> dict[str, Any]:
        with self._connect() as c: row=c.execute("SELECT * FROM payment_intents WHERE intent_id=?",(intent_id,)).fetchone()
        if not row: raise EvidencePaymentError("NOT_FOUND", "Payment intent not found")
        return dict(row)

    def transition_payment(self, intent_id: str, new_state: str, reason: str, provider_data: dict | None = None) -> dict[str, Any]:
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT * FROM payment_intents WHERE intent_id=?",(intent_id,)).fetchone()
            if not row: raise EvidencePaymentError("NOT_FOUND", "Payment intent not found")
            old=row["state"]
            if new_state not in PAYMENT_TRANSITIONS.get(old,set()): raise EvidencePaymentError("INVALID_TRANSITION", f"{old}->{new_state}")
            c.execute("UPDATE payment_intents SET state=?,updated_at=? WHERE intent_id=?",(new_state,_now(),intent_id))
            c.execute("INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",(_id("pe"),intent_id,old,new_state,reason,json.dumps(provider_data or {},sort_keys=True),_now())); c.execute("COMMIT")
        return self.get_intent(intent_id)

    def verify_observation(self, intent_id: str, observation: dict[str, Any], provider_observations: list[dict[str, Any]]) -> str:
        intent=self.get_intent(intent_id)
        checks = [
            observation.get("chain_id") == intent["chain_id"],
            str(observation.get("from","")).lower() == intent["payer"].lower(),
            str(observation.get("to","")).lower() == intent["treasury_address"].lower(),
            str(observation.get("value")) == str(intent["expected_value"]),
            observation.get("asset") == intent["asset"], observation.get("receipt_status") == 1,
            observation.get("case_id") == intent["case_id"], observation.get("entitlement_ref") == intent["entitlement_ref"],
        ]
        tx=observation.get("tx_hash")
        if not tx or not all(checks): return "MANUAL_REVIEW"
        normalized={(p.get("tx_hash"),p.get("block_hash"),p.get("receipt_status")) for p in provider_observations}
        if len(normalized) != 1 or len(provider_observations) < 2: return "MANUAL_REVIEW"
        with self._connect() as c:
            other=c.execute("SELECT intent_id FROM payment_intents WHERE tx_hash=? AND intent_id<>?",(tx,intent_id)).fetchone()
            if other: return "MANUAL_REVIEW"
            c.execute("UPDATE payment_intents SET tx_hash=?,updated_at=? WHERE intent_id=?",(tx,_now(),intent_id))
        return "FINALITY_PENDING" if int(observation.get("confirmations",0)) < int(observation.get("required_confirmations",1)) else "SETTLED"

    def settle(self, intent_id: str, observation: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
        verdict=self.verify_observation(intent_id,observation,providers)
        if verdict != "SETTLED":
            target="MANUAL_REVIEW" if verdict=="MANUAL_REVIEW" else "FINALITY_PENDING"
            current=self.get_intent(intent_id)["state"]
            if target in PAYMENT_TRANSITIONS.get(current,set()): self.transition_payment(intent_id,target,"verification verdict",{"verdict":verdict})
            return {"intent_id":intent_id,"verdict":verdict,"entitlement_granted":False}
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT * FROM payment_intents WHERE intent_id=?",(intent_id,)).fetchone()
            if row["state"] == "SETTLED":
                granted=bool(c.execute("SELECT 1 FROM entitlement_ledger WHERE intent_id=?",(intent_id,)).fetchone()); c.execute("COMMIT")
                return {"intent_id":intent_id,"verdict":"SETTLED","entitlement_granted":granted,"idempotent":True}
            if row["state"] != "FINALITY_PENDING": raise EvidencePaymentError("BAD_SETTLEMENT_STATE", row["state"])
            c.execute("UPDATE payment_intents SET state='SETTLED',updated_at=? WHERE intent_id=?",(_now(),intent_id))
            c.execute("INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",(_id("pe"),intent_id,"FINALITY_PENDING","SETTLED","finality verified",json.dumps(observation,sort_keys=True),_now()))
            c.execute("INSERT INTO entitlement_ledger VALUES(?,?,?,?,?,?,?)",(_id("el"),row["entitlement_ref"],row["case_id"],intent_id,1,"payment settled",json.dumps({"tx_hash":row["tx_hash"],"intent_id":intent_id},sort_keys=True),_now())); c.execute("COMMIT")
        return {"intent_id":intent_id,"verdict":"SETTLED","entitlement_granted":True}
