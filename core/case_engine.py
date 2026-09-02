"""CHAT01 canonical Core/User/SIC-ID/Case authority.

Uses the runtime canonical BLOCKCHAINPLUS-MASTER.sqlite path. This module owns
Case workflow state but never payment/evidence/entitlement truth.
"""
from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION="1.0"; SCHEMA_VERSION="chat01-core-1"; API_CONTRACT_VERSION="v1"; CASE_STATE_VERSION="1.0"
PRODUCT_KINDS={"FREE","ACTIVATION","ONE_SHOT","CASE","MEMBERSHIP","RECURRING","UPGRADE","DOWNGRADE","RENEWAL","CANCELLATION"}
STATES=("DRAFT","TRIAGE","PRODUCT_SELECTED","EVIDENCE_REQUIRED","CONSENT_REQUIRED","PAYMENT_REQUIRED","PAYMENT_VERIFYING","ACTIVE","ANALYSIS","ACTION_REQUIRED","RESULT_READY","FOLLOW_UP","CLOSED")
TRANSITIONS={
"DRAFT":{"TRIAGE"},"TRIAGE":{"PRODUCT_SELECTED"},"PRODUCT_SELECTED":{"EVIDENCE_REQUIRED","CONSENT_REQUIRED","PAYMENT_REQUIRED","ACTIVE"},
"EVIDENCE_REQUIRED":{"CONSENT_REQUIRED"},"CONSENT_REQUIRED":{"PAYMENT_REQUIRED","ACTIVE"},"PAYMENT_REQUIRED":{"PAYMENT_VERIFYING"},
"PAYMENT_VERIFYING":{"ACTIVE"},"ACTIVE":{"ANALYSIS","ACTION_REQUIRED"},"ANALYSIS":{"ACTION_REQUIRED","RESULT_READY"},
"ACTION_REQUIRED":{"ANALYSIS","RESULT_READY"},"RESULT_READY":{"FOLLOW_UP","CLOSED"},"FOLLOW_UP":{"ACTION_REQUIRED","CLOSED"},"CLOSED":set()}

def now(): return datetime.now(timezone.utc).isoformat()
def ident(p): return f"{p}_{uuid.uuid4().hex}"
class CoreError(RuntimeError):
    def __init__(self,code,message,status=400): super().__init__(message); self.code=code; self.status=status

class CaseEngine:
    def __init__(self,db_path:str|Path):
        self.db_path=Path(db_path)
        if "public_html" in {p.lower() for p in self.db_path.resolve().parts}: raise CoreError("DB_PUBLIC_FORBIDDEN","Canonical DB must not be under public_html",500)
        self._schema()
    def conn(self):
        c=sqlite3.connect(self.db_path,timeout=30,isolation_level=None); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL"); return c
    def _schema(self):
        with self.conn() as c: c.executescript("""
        CREATE TABLE IF NOT EXISTS core_users(user_id TEXT PRIMARY KEY,sic_id TEXT NOT NULL UNIQUE,profile_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_wallet_bindings(binding_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,wallet TEXT NOT NULL UNIQUE,chain_id INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_sessions(session_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT);
        CREATE TABLE IF NOT EXISTS core_cases(case_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,sic_id TEXT NOT NULL,wallet TEXT,project_ref TEXT,project_truth TEXT NOT NULL,state TEXT NOT NULL,product_code TEXT,product_kind TEXT,version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,closed_at TEXT);
        CREATE TABLE IF NOT EXISTS core_case_events(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,actor TEXT NOT NULL,previous_state TEXT,new_state TEXT NOT NULL,reason TEXT NOT NULL,timestamp TEXT NOT NULL,request_id TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,authorization TEXT NOT NULL,audit_event TEXT NOT NULL,case_version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS core_case_tasks(task_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,next_action TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_products(product_code TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,eligibility_json TEXT NOT NULL,config_json TEXT NOT NULL,version INTEGER NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_requests(idempotency_key TEXT PRIMARY KEY,request_id TEXT NOT NULL,operation TEXT NOT NULL,response_json TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
    def register_user(self,sic_id:str,profile:dict[str,Any],idempotency_key:str,request_id:str)->dict:
        if not sic_id: raise CoreError("INVALID_SIC_ID","sic_id required")
        with self.conn() as c:
            old=c.execute("SELECT response_json FROM core_requests WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if old:return json.loads(old[0])
            c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT * FROM core_users WHERE sic_id=?",(sic_id,)).fetchone()
            if row: result={"user_id":row["user_id"],"sic_id":sic_id,"returning":True}
            else:
                uid=ident("usr"); t=now(); c.execute("INSERT INTO core_users VALUES(?,?,?,?,?)",(uid,sic_id,json.dumps(profile,sort_keys=True),t,t)); result={"user_id":uid,"sic_id":sic_id,"returning":False}
            c.execute("INSERT INTO core_requests VALUES(?,?,?,?,?)",(idempotency_key,request_id,"register_user",json.dumps(result,sort_keys=True),now())); c.execute("COMMIT"); return result
    def bind_wallet(self,user_id:str,sic_id:str,wallet:str,request_id:str,idempotency_key:str)->dict:
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE"); u=c.execute("SELECT * FROM core_users WHERE user_id=?",(user_id,)).fetchone()
            if not u: raise CoreError("USER_NOT_FOUND","user not found",404)
            if u["sic_id"]!=sic_id: raise CoreError("SIC_ID_MISMATCH","SIC-ID mismatch",403)
            existing=c.execute("SELECT * FROM core_wallet_bindings WHERE wallet=?",(wallet.lower(),)).fetchone()
            if existing and existing["user_id"]!=user_id: raise CoreError("WALLET_MISMATCH","wallet belongs to another user",409)
            if not existing:c.execute("INSERT INTO core_wallet_bindings VALUES(?,?,?,?,?,?)",(ident("wb"),user_id,wallet.lower(),137,"ACTIVE",now()))
            c.execute("COMMIT"); return {"user_id":user_id,"wallet":wallet.lower(),"chain_id":137,"status":"ACTIVE"}
    def open_case(self,user_id:str,sic_id:str,wallet:str|None,project_ref:str|None,search_hit:bool,actor:str,request_id:str,idempotency_key:str)->dict:
        with self.conn() as c:
            old=c.execute("SELECT response_json FROM core_requests WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if old:return json.loads(old[0])
            c.execute("BEGIN IMMEDIATE"); u=c.execute("SELECT * FROM core_users WHERE user_id=?",(user_id,)).fetchone()
            if not u or u["sic_id"]!=sic_id: raise CoreError("UNAUTHORIZED_USER","user/SIC-ID mismatch",403)
            if wallet:
                b=c.execute("SELECT * FROM core_wallet_bindings WHERE wallet=? AND user_id=? AND status='ACTIVE'",(wallet.lower(),user_id)).fetchone()
                if not b: raise CoreError("WALLET_MISMATCH","wallet is not bound to user",403)
            cid=ident("case"); truth="VERIFIED_REFERENCE" if search_hit else "TO_VERIFY"; t=now()
            c.execute("INSERT INTO core_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,user_id,sic_id,wallet.lower() if wallet else None,project_ref,truth,"DRAFT",None,None,1,t,t,None))
            ev={"event_id":ident("ce"),"case_id":cid,"actor":actor,"previous_state":None,"new_state":"DRAFT","reason":"case opened","timestamp":t,"request_id":request_id,"idempotency_key":idempotency_key,"authorization":"OWNER","audit_event":"CASE_CREATED","case_version":1}
            c.execute("INSERT INTO core_case_events VALUES(:event_id,:case_id,:actor,:previous_state,:new_state,:reason,:timestamp,:request_id,:idempotency_key,:authorization,:audit_event,:case_version)",ev)
            result={"case_id":cid,"state":"DRAFT","project_truth":truth,"version":1}; c.execute("INSERT INTO core_requests VALUES(?,?,?,?,?)",(idempotency_key,request_id,"open_case",json.dumps(result,sort_keys=True),t)); c.execute("COMMIT"); return result
    def get_case(self,case_id:str,user_id:str)->dict:
        with self.conn() as c: r=c.execute("SELECT * FROM core_cases WHERE case_id=? AND user_id=?",(case_id,user_id)).fetchone()
        if not r: raise CoreError("CASE_NOT_FOUND","case not found or unauthorized",404)
        return dict(r)
    def transition(self,case_id:str,user_id:str,new_state:str,actor:str,reason:str,request_id:str,idempotency_key:str,authorization:str,expected_version:int)->dict:
        if new_state not in STATES: raise CoreError("INVALID_STATE","unknown state")
        with self.conn() as c:
            oldreq=c.execute("SELECT response_json FROM core_requests WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if oldreq:return json.loads(oldreq[0])
            c.execute("BEGIN IMMEDIATE"); r=c.execute("SELECT * FROM core_cases WHERE case_id=? AND user_id=?",(case_id,user_id)).fetchone()
            if not r: raise CoreError("CASE_NOT_FOUND","case not found or unauthorized",404)
            if r["version"]!=expected_version: raise CoreError("STALE_STATE","case version is stale",409)
            if new_state not in TRANSITIONS[r["state"]]: raise CoreError("INVALID_TRANSITION",f"{r['state']} -> {new_state}",409)
            # ACTIVE may only be asserted after an external entitlement/payment authority grants the contract.
            if new_state=="ACTIVE" and authorization not in {"ENTITLEMENT_GRANTED","FREE_PRODUCT_AUTHORIZED"}: raise CoreError("MISSING_ENTITLEMENT","activation requires external entitlement authorization",403)
            ver=r["version"]+1; t=now(); c.execute("UPDATE core_cases SET state=?,version=?,updated_at=?,closed_at=? WHERE case_id=?",(new_state,ver,t,t if new_state=="CLOSED" else None,case_id))
            ev=(ident("ce"),case_id,actor,r["state"],new_state,reason,t,request_id,idempotency_key,authorization,"CASE_STATE_TRANSITION",ver); c.execute("INSERT INTO core_case_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",ev)
            result={"case_id":case_id,"previous_state":r["state"],"state":new_state,"version":ver}; c.execute("INSERT INTO core_requests VALUES(?,?,?,?,?)",(idempotency_key,request_id,"transition",json.dumps(result,sort_keys=True),t)); c.execute("COMMIT"); return result
    def upsert_product(self,product_code:str,kind:str,status:str,eligibility:dict,config:dict,version:int)->dict:
        if kind not in PRODUCT_KINDS: raise CoreError("INVALID_PRODUCT_KIND","unsupported product kind")
        with self.conn() as c:c.execute("INSERT INTO core_products VALUES(?,?,?,?,?,?,?) ON CONFLICT(product_code) DO UPDATE SET kind=excluded.kind,status=excluded.status,eligibility_json=excluded.eligibility_json,config_json=excluded.config_json,version=excluded.version,updated_at=excluded.updated_at",(product_code,kind,status,json.dumps(eligibility,sort_keys=True),json.dumps(config,sort_keys=True),version,now()))
        return {"product_code":product_code,"kind":kind,"status":status,"version":version}
    def select_product(self,case_id:str,user_id:str,product_code:str)->dict:
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE"); case=c.execute("SELECT * FROM core_cases WHERE case_id=? AND user_id=?",(case_id,user_id)).fetchone(); product=c.execute("SELECT * FROM core_products WHERE product_code=? AND status='ACTIVE'",(product_code,)).fetchone()
            if not case: raise CoreError("CASE_NOT_FOUND","case not found",404)
            if not product: raise CoreError("PRODUCT_NOT_ELIGIBLE","product unavailable",403)
            c.execute("UPDATE core_cases SET product_code=?,product_kind=?,updated_at=? WHERE case_id=?",(product_code,product["kind"],now(),case_id)); c.execute("COMMIT"); return {"case_id":case_id,"product_code":product_code,"kind":product["kind"]}
    def add_task(self,case_id:str,user_id:str,title:str,next_action:str|None=None)->dict:
        self.get_case(case_id,user_id); tid=ident("task"); t=now()
        with self.conn() as c:c.execute("INSERT INTO core_case_tasks VALUES(?,?,?,?,?,?,?)",(tid,case_id,title,"OPEN",next_action,t,t))
        return {"task_id":tid,"case_id":case_id,"status":"OPEN","next_action":next_action}
    def timeline(self,case_id:str,user_id:str)->list[dict]:
        self.get_case(case_id,user_id)
        with self.conn() as c:return [dict(x) for x in c.execute("SELECT * FROM core_case_events WHERE case_id=? ORDER BY timestamp,event_id",(case_id,)).fetchall()]
