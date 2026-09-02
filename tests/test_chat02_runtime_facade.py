from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from evidence_payment import (
    EvidencePaymentEngine,
    EvidencePaymentError,
    TrustedEvidencePaymentRuntimeFacade,
    TrustedPolygonRPCAdapter,
)


PAYER_A = "0x1111111111111111111111111111111111111111"
PAYER_B = "0x2222222222222222222222222222222222222222"
TX_ACT = "0x" + "a" * 64
TX_CASE1 = "0x" + "b" * 64
TX_CASE2 = "0x" + "c" * 64
TX_PENDING = "0x" + "d" * 64
TX_BAD = "0x" + "e" * 64


class FakeRPC:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def set_tx(
        self,
        tx_hash: str,
        *,
        sender: str,
        recipient: str,
        pol: str,
        block: int = 100,
        finalized: int = 101,
        status: int = 1,
        provider_overrides: dict[str, dict] | None = None,
    ):
        wei = int(Decimal(pol) * Decimal(10**18))
        block_hash = "0x" + f"{block:064x}"
        for provider in ("rpc_a", "rpc_b"):
            row = {
                "chain_id": 137,
                "sender": sender.lower(),
                "recipient": recipient.lower(),
                "wei": wei,
                "block": block,
                "block_hash": block_hash,
                "finalized": finalized,
                "status": status,
            }
            row.update((provider_overrides or {}).get(provider, {}))
            self.rows[(provider, tx_hash.lower())] = row

    def __call__(self, provider_id: str, method: str, params: list):
        tx_hash = params[0].lower() if params and isinstance(params[0], str) and params[0].startswith("0x") else None
        if method == "eth_chainId":
            row = next(value for (provider, _), value in self.rows.items() if provider == provider_id)
            return hex(row["chain_id"])
        if method == "eth_getBlockByNumber":
            row = max(
                (value for (provider, _), value in self.rows.items() if provider == provider_id),
                key=lambda value: value["finalized"],
            )
            return {"number": hex(row["finalized"])}
        row = self.rows[(provider_id, tx_hash)]
        if method == "eth_getTransactionByHash":
            return {
                "hash": tx_hash,
                "from": row["sender"],
                "to": row["recipient"],
                "value": hex(row["wei"]),
                "blockNumber": hex(row["block"]),
                "blockHash": row["block_hash"],
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": tx_hash,
                "status": hex(row["status"]),
                "blockNumber": hex(row["block"]),
                "blockHash": row["block_hash"],
            }
        raise AssertionError(method)


@pytest.fixture()
def stack(tmp_path: Path):
    private_root = tmp_path / "private-evidence"
    engine = EvidencePaymentEngine(tmp_path / "authority.sqlite", private_root)
    rpc = FakeRPC()
    adapter = TrustedPolygonRPCAdapter(engine, rpc)
    sessions = {
        "ses_a": {"principal_id": "SIC-A", "sic_id": "SIC-A"},
        "ses_b": {"principal_id": "SIC-B", "sic_id": "SIC-B"},
    }
    owned = {("SIC-A", "case_a"), ("SIC-A", "case_b"), ("SIC-B", "case_other")}

    def resolve_principal(session_id: str):
        if session_id not in sessions:
            raise RuntimeError("missing session")
        return sessions[session_id]

    def authorize_case(principal: dict, case_id: str):
        return (principal["principal_id"], case_id) in owned

    def evidence_grant(principal: dict, case_id: str):
        return {
            "uploader": principal["principal_id"],
            "consent_id": f"server-consent:{principal['principal_id']}:{case_id}",
            "authorization": "OWNER",
        }

    facade = TrustedEvidencePaymentRuntimeFacade(
        engine=engine,
        rpc_adapter=adapter,
        resolve_principal=resolve_principal,
        authorize_case=authorize_case,
        resolve_evidence_grant=evidence_grant,
        provider_ids=("rpc_a", "rpc_b"),
    )
    return facade, engine, rpc, private_root


def settle_activation(facade, engine, rpc, tx_hash=TX_ACT):
    intent = facade.create_activation_intent(
        session_id="ses_a",
        payer=PAYER_A,
        request_id="req_activation",
        idempotency_key="idem_activation",
    )
    rpc.set_tx(
        tx_hash,
        sender=PAYER_A,
        recipient=intent["treasury_address"],
        pol="50",
    )
    result = facade.settle_tx_hash(session_id="ses_a", intent_id=intent["intent_id"], tx_hash=tx_hash)
    assert result["payment_state"] == "SETTLED"
    assert result["entitlement_granted"] is True
    assert result["case_active"] is False
    assert result["core_activation_ready"] is False
    assert result["credit_effect"] == {"amount": "50", "state": "AVAILABLE"}
    return intent


def test_private_evidence_uses_server_grant_and_never_client_authority(stack):
    facade, engine, _, private_root = stack
    payload = b"%PDF-1.4\ntrusted-evidence\n"
    result = facade.store_private_evidence(
        session_id="ses_a",
        case_id="case_a",
        content=payload,
        original_name="proof.pdf",
        mime_declared="application/pdf",
        mime_detected="application/pdf",
    )
    assert result["private_storage"] is True
    assert result["status"] == "AVAILABLE"
    with engine._connect() as connection:
        row = connection.execute(
            "SELECT * FROM evidence_records WHERE evidence_id=?", (result["evidence_id"],)
        ).fetchone()
    assert row["uploader"] == "SIC-A"
    assert row["authorization"] == "OWNER"
    assert row["consent_id"].startswith("server-consent:SIC-A:case_a")
    final = (private_root / row["storage_relpath"]).resolve(strict=True)
    final.relative_to(private_root.resolve(strict=True))
    assert final.read_bytes() == payload

    with pytest.raises(TypeError):
        facade.store_private_evidence(
            session_id="ses_a",
            case_id="case_a",
            content=payload,
            original_name="forged.pdf",
            mime_declared="application/pdf",
            mime_detected="application/pdf",
            authorization="OWNER",  # type: ignore[call-arg]
        )


def test_case_ownership_rejects_before_any_evidence_bytes(stack):
    facade, engine, _, private_root = stack
    before = list(private_root.rglob("*"))
    with pytest.raises(EvidencePaymentError) as rejected:
        facade.store_private_evidence(
            session_id="ses_a",
            case_id="case_other",
            content=b"%PDF-1.4\nforbidden\n",
            original_name="forbidden.pdf",
            mime_declared="application/pdf",
            mime_detected="application/pdf",
        )
    assert rejected.value.code == "CASE_FORBIDDEN"
    assert list(private_root.rglob("*")) == before
    with engine._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0] == 0


def test_server_grant_failure_is_fail_closed_before_bytes(tmp_path: Path):
    private_root = tmp_path / "private"
    engine = EvidencePaymentEngine(tmp_path / "authority.sqlite", private_root)
    rpc = FakeRPC()
    facade = TrustedEvidencePaymentRuntimeFacade(
        engine=engine,
        rpc_adapter=TrustedPolygonRPCAdapter(engine, rpc),
        resolve_principal=lambda _: {"principal_id": "SIC-A"},
        authorize_case=lambda _principal, _case: True,
        resolve_evidence_grant=lambda _principal, _case: {
            "uploader": "SIC-A",
            "consent_id": "consent",
            "authorization": "REVOKED",
        },
        provider_ids=("rpc_a", "rpc_b"),
    )
    with pytest.raises(EvidencePaymentError) as rejected:
        facade.store_private_evidence(
            session_id="ses_a",
            case_id="case_a",
            content=b"%PDF-1.4\nrejected\n",
            original_name="rejected.pdf",
            mime_declared="application/pdf",
            mime_detected="application/pdf",
        )
    assert rejected.value.code == "UNAUTHORIZED"
    assert not list(private_root.rglob("*.bin"))
    assert not list(private_root.rglob("*.quarantine"))


def test_frozen_activation_first_case_and_later_case_golden_boundary(stack):
    facade, engine, rpc, _ = stack
    assert facade.quote(session_id="ses_a") == {
        "contract_version": "1.0",
        "chain_id": 137,
        "asset": "POL",
        "stage": "ACTIVATION_REQUIRED",
        "activation_payable": "50",
    }
    settle_activation(facade, engine, rpc)

    first = facade.create_case_intent(
        session_id="ses_a",
        case_id="case_a",
        payer=PAYER_A,
        request_id="req_case_a",
        idempotency_key="idem_case_a",
    )
    assert first["expected_value"] == "450"
    assert first["chain_id"] == 137
    assert first["asset"] == "POL"
    rpc.set_tx(TX_CASE1, sender=PAYER_A, recipient=first["treasury_address"], pol="450", block=110, finalized=111)
    settled = facade.settle_tx_hash(session_id="ses_a", intent_id=first["intent_id"], tx_hash=TX_CASE1)
    assert settled["payment_state"] == "SETTLED"
    assert settled["entitlement_granted"] is True
    assert settled["case_active"] is False
    assert settled["core_activation_ready"] is True
    claim = settled["core_activation_claim"]
    assert claim["case_id"] == "case_a"
    assert claim["payment_state"] == "SETTLED"
    assert claim["case_state_authority"] == "CORE"
    assert len(claim["sha256"]) == 64
    assert engine.get_activation_credit("SIC-A")["state"] == "CONSUMED"

    later = facade.create_case_intent(
        session_id="ses_a",
        case_id="case_b",
        payer=PAYER_A,
        request_id="req_case_b",
        idempotency_key="idem_case_b",
    )
    assert later["expected_value"] == "500"
    rpc.set_tx(TX_CASE2, sender=PAYER_A, recipient=later["treasury_address"], pol="500", block=120, finalized=121)
    later_result = facade.settle_tx_hash(session_id="ses_a", intent_id=later["intent_id"], tx_hash=TX_CASE2)
    assert later_result["payment_state"] == "SETTLED"
    assert later_result["core_activation_ready"] is True


def test_browser_cannot_supply_economics_or_provider_authority(stack):
    facade, engine, rpc, _ = stack
    settle_activation(facade, engine, rpc)
    with pytest.raises(TypeError):
        facade.create_case_intent(
            session_id="ses_a",
            case_id="case_a",
            payer=PAYER_A,
            request_id="req_forge",
            idempotency_key="idem_forge",
            expected_value="1",  # type: ignore[call-arg]
        )
    intent = facade.create_case_intent(
        session_id="ses_a",
        case_id="case_a",
        payer=PAYER_A,
        request_id="req_real",
        idempotency_key="idem_real",
    )
    rpc.set_tx(TX_CASE1, sender=PAYER_A, recipient=intent["treasury_address"], pol="450", block=130, finalized=131)
    with pytest.raises(TypeError):
        facade.settle_tx_hash(
            session_id="ses_a",
            intent_id=intent["intent_id"],
            tx_hash=TX_CASE1,
            provider_ids=("evil", "evil2"),  # type: ignore[call-arg]
        )


def test_cross_principal_intent_is_rejected(stack):
    facade, engine, rpc, _ = stack
    intent = settle_activation(facade, engine, rpc)
    with pytest.raises(EvidencePaymentError) as rejected:
        facade.payment_status(session_id="ses_b", intent_id=intent["intent_id"])
    assert rejected.value.code == "INTENT_FORBIDDEN"


def test_finality_pending_never_grants_entitlement_or_core_activation(stack):
    facade, engine, rpc, _ = stack
    settle_activation(facade, engine, rpc)
    intent = facade.create_case_intent(
        session_id="ses_a",
        case_id="case_a",
        payer=PAYER_A,
        request_id="req_pending",
        idempotency_key="idem_pending",
    )
    rpc.set_tx(TX_PENDING, sender=PAYER_A, recipient=intent["treasury_address"], pol="450", block=150, finalized=150)
    result = facade.settle_tx_hash(session_id="ses_a", intent_id=intent["intent_id"], tx_hash=TX_PENDING)
    assert result["payment_state"] == "FINALITY_PENDING"
    assert result["entitlement_granted"] is False
    assert result["core_activation_ready"] is False
    assert result["case_active"] is False
    with engine._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM entitlement_ledger WHERE intent_id=?", (intent["intent_id"],)
        ).fetchone()[0] == 0


def test_provider_disagreement_goes_manual_review(stack):
    facade, engine, rpc, _ = stack
    settle_activation(facade, engine, rpc)
    intent = facade.create_case_intent(
        session_id="ses_a",
        case_id="case_a",
        payer=PAYER_A,
        request_id="req_bad",
        idempotency_key="idem_bad",
    )
    rpc.set_tx(
        TX_BAD,
        sender=PAYER_A,
        recipient=intent["treasury_address"],
        pol="450",
        block=160,
        finalized=161,
        provider_overrides={"rpc_b": {"sender": PAYER_B.lower()}},
    )
    result = facade.settle_tx_hash(session_id="ses_a", intent_id=intent["intent_id"], tx_hash=TX_BAD)
    assert result["payment_state"] == "MANUAL_REVIEW"
    assert result["entitlement_granted"] is False
    assert result["core_activation_ready"] is False
    with engine._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM entitlement_ledger WHERE intent_id=?", (intent["intent_id"],)
        ).fetchone()[0] == 0


def test_provider_config_must_be_distinct_and_adapter_must_share_engine(tmp_path: Path):
    engine = EvidencePaymentEngine(tmp_path / "one.sqlite", tmp_path / "one-private")
    other = EvidencePaymentEngine(tmp_path / "two.sqlite", tmp_path / "two-private")
    rpc = FakeRPC()
    with pytest.raises(EvidencePaymentError) as quorum:
        TrustedEvidencePaymentRuntimeFacade(
            engine=engine,
            rpc_adapter=TrustedPolygonRPCAdapter(engine, rpc),
            resolve_principal=lambda _: {"principal_id": "SIC-A"},
            authorize_case=lambda *_: True,
            resolve_evidence_grant=lambda *_: {"uploader": "SIC-A", "consent_id": "c", "authorization": "OWNER"},
            provider_ids=("rpc_a", "rpc_a"),
        )
    assert quorum.value.code == "RUNTIME_PROVIDER_QUORUM"

    with pytest.raises(EvidencePaymentError) as mismatch:
        TrustedEvidencePaymentRuntimeFacade(
            engine=engine,
            rpc_adapter=TrustedPolygonRPCAdapter(other, rpc),
            resolve_principal=lambda _: {"principal_id": "SIC-A"},
            authorize_case=lambda *_: True,
            resolve_evidence_grant=lambda *_: {"uploader": "SIC-A", "consent_id": "c", "authorization": "OWNER"},
            provider_ids=("rpc_a", "rpc_b"),
        )
    assert mismatch.value.code == "RUNTIME_ENGINE_MISMATCH"
