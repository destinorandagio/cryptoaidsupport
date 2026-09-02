"""CHAT02 trusted Polygon RPC provenance adapter for the 48H MVP.

This module never signs or submits a transaction. It accepts only a transaction
hash plus server-configured provider identities, derives the economic
observation from EVM JSON-RPC, and delegates settlement truth to the canonical
CHAT02 EvidencePaymentEngine.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Iterable

from .engine import CHAIN_ID, PAYMENT_TRANSITIONS, EvidencePaymentError, _block_number

RPC_PROVENANCE_VERSION = "1.0"
WEI_PER_POL = 10**18
RpcCall = Callable[[str, str, list[Any]], Any]


def _rpc_result(value: Any) -> Any:
    """Accept a raw result or a JSON-RPC envelope, rejecting provider errors."""
    if isinstance(value, dict) and ("result" in value or "error" in value):
        if value.get("error") is not None:
            raise EvidencePaymentError("RPC_PROVIDER_ERROR", "RPC provider returned an error")
        return value.get("result")
    return value


def _hex_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidencePaymentError("RPC_MALFORMED", f"Missing {field}")
    return value.strip().lower()


def _address(value: Any, field: str) -> str:
    return _hex_identity(value, field)


def _status(value: Any) -> int:
    try:
        return _block_number(value)
    except (TypeError, ValueError) as exc:
        raise EvidencePaymentError("RPC_MALFORMED", "Invalid receipt status") from exc


def _wei_to_pol(value: Any) -> str:
    try:
        wei = _block_number(value)
    except (TypeError, ValueError) as exc:
        raise EvidencePaymentError("RPC_MALFORMED", "Invalid native transaction value") from exc
    amount = Decimal(wei) / Decimal(WEI_PER_POL)
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class TrustedPolygonRPCAdapter:
    """Build server-trusted payment evidence from at least two RPC authorities."""

    def __init__(self, engine: Any, rpc_call: RpcCall):
        self.engine = engine
        self.rpc_call = rpc_call

    def _provider_snapshot(self, provider_id: str, tx_hash: str) -> dict[str, Any]:
        try:
            chain_raw = _rpc_result(self.rpc_call(provider_id, "eth_chainId", []))
            tx = _rpc_result(self.rpc_call(provider_id, "eth_getTransactionByHash", [tx_hash]))
            receipt = _rpc_result(self.rpc_call(provider_id, "eth_getTransactionReceipt", [tx_hash]))
            finalized = _rpc_result(self.rpc_call(provider_id, "eth_getBlockByNumber", ["finalized", False]))
        except EvidencePaymentError:
            raise
        except Exception as exc:
            raise EvidencePaymentError("RPC_UNAVAILABLE", "RPC provider call failed") from exc

        if not isinstance(tx, dict) or not isinstance(receipt, dict) or not isinstance(finalized, dict):
            raise EvidencePaymentError("RPC_MISSING_DATA", "RPC transaction, receipt and finalized block are required")

        try:
            chain_id = _block_number(chain_raw)
            tx_block = _block_number(tx.get("blockNumber"))
            receipt_block = _block_number(receipt.get("blockNumber"))
            finalized_block = _block_number(finalized.get("number"))
        except (TypeError, ValueError) as exc:
            raise EvidencePaymentError("RPC_MALFORMED", "Invalid RPC quantity") from exc

        observed_tx = _hex_identity(tx.get("hash"), "transaction hash")
        receipt_tx = _hex_identity(receipt.get("transactionHash"), "receipt transaction hash")
        requested_tx = _hex_identity(tx_hash, "requested transaction hash")
        tx_block_hash = _hex_identity(tx.get("blockHash"), "transaction block hash")
        receipt_block_hash = _hex_identity(receipt.get("blockHash"), "receipt block hash")
        if observed_tx != requested_tx or receipt_tx != requested_tx:
            raise EvidencePaymentError("RPC_TX_MISMATCH", "RPC transaction hash mismatch")
        if tx_block != receipt_block or tx_block_hash != receipt_block_hash:
            raise EvidencePaymentError("RPC_BLOCK_MISMATCH", "Transaction and receipt block mismatch")

        return {
            "provider_id": provider_id,
            "chain_id": chain_id,
            "from": _address(tx.get("from"), "sender"),
            "to": _address(tx.get("to"), "recipient"),
            "value": _wei_to_pol(tx.get("value")),
            "receipt_status": _status(receipt.get("status")),
            "tx_hash": observed_tx,
            "block_hash": tx_block_hash,
            "tx_block_number": tx_block,
            "finalized_block_number": finalized_block,
        }

    def build_trusted_observation(
        self, *, intent_id: str, tx_hash: str, provider_ids: Iterable[str]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        intent = self.engine.get_intent(intent_id)
        if intent["asset"] != "POL":
            raise EvidencePaymentError("RPC_ASSET_UNSUPPORTED", "MVP RPC adapter supports native POL only")

        ids = [str(provider_id).strip() for provider_id in provider_ids]
        if len(ids) < 2 or any(not provider_id for provider_id in ids) or len(set(ids)) != len(ids):
            raise EvidencePaymentError("RPC_PROVIDER_QUORUM", "At least two distinct RPC provider identities are required")

        snapshots = [self._provider_snapshot(provider_id, tx_hash) for provider_id in ids]
        economic_keys = (
            "chain_id", "from", "to", "value", "receipt_status",
            "tx_hash", "block_hash", "tx_block_number",
        )
        agreed = {tuple(snapshot[key] for key in economic_keys) for snapshot in snapshots}
        if len(agreed) != 1:
            raise EvidencePaymentError("RPC_PROVIDER_DISAGREEMENT", "RPC providers disagree on payment evidence")

        first = snapshots[0]
        if first["chain_id"] != CHAIN_ID or first["chain_id"] != intent["chain_id"]:
            raise EvidencePaymentError("RPC_CHAIN_MISMATCH", "Wrong chain")
        if first["from"] != str(intent["payer"]).lower():
            raise EvidencePaymentError("RPC_SENDER_MISMATCH", "Wrong sender")
        if first["to"] != str(intent["treasury_address"]).lower():
            raise EvidencePaymentError("RPC_TREASURY_MISMATCH", "Wrong treasury")
        if first["value"] != str(intent["expected_value"]):
            raise EvidencePaymentError("RPC_VALUE_MISMATCH", "Wrong payment value")
        if first["receipt_status"] != 1:
            raise EvidencePaymentError("RPC_RECEIPT_FAILED", "Transaction receipt is not successful")

        provider_observations = [
            {
                "provider_id": snapshot["provider_id"],
                "tx_hash": snapshot["tx_hash"],
                "block_hash": snapshot["block_hash"],
                "receipt_status": snapshot["receipt_status"],
                "tx_block_number": snapshot["tx_block_number"],
                "finalized_block_number": snapshot["finalized_block_number"],
                "chain_id": snapshot["chain_id"],
                "from": snapshot["from"],
                "to": snapshot["to"],
                "value": snapshot["value"],
                "asset": "POL",
            }
            for snapshot in snapshots
        ]
        observation = {
            "chain_id": first["chain_id"],
            "from": first["from"],
            "to": first["to"],
            "value": first["value"],
            "asset": intent["asset"],
            "receipt_status": first["receipt_status"],
            "case_id": intent["case_id"],
            "entitlement_ref": intent["entitlement_ref"],
            "tx_hash": first["tx_hash"],
            "block_hash": first["block_hash"],
            "block_number": first["tx_block_number"],
            "rpc_provenance": {
                "version": RPC_PROVENANCE_VERSION,
                "provider_ids": sorted(ids),
                "methods": [
                    "eth_chainId",
                    "eth_getTransactionByHash",
                    "eth_getTransactionReceipt",
                    "eth_getBlockByNumber(finalized)",
                ],
            },
        }
        return observation, provider_observations

    def _mark_manual_review(self, intent_id: str, reason: str) -> dict[str, Any]:
        current = self.engine.get_intent(intent_id)
        state = current["state"]
        if state in {"INTENT_CREATED", "USER_ACTION_REQUIRED"}:
            if state == "INTENT_CREATED":
                self.engine.transition_payment(intent_id, "USER_ACTION_REQUIRED", "payment action observed")
            self.engine.transition_payment(intent_id, "TX_OBSERVED", "transaction hash submitted to server verifier")
            state = "TX_OBSERVED"
        if "MANUAL_REVIEW" in PAYMENT_TRANSITIONS.get(state, set()):
            self.engine.transition_payment(intent_id, "MANUAL_REVIEW", reason)
        return {"intent_id": intent_id, "verdict": "MANUAL_REVIEW", "entitlement_granted": False}

    def settle_from_tx_hash(self, *, intent_id: str, tx_hash: str, provider_ids: Iterable[str]) -> dict[str, Any]:
        """Verify and settle using only server-derived RPC evidence; never client economics."""
        current = self.engine.get_intent(intent_id)
        if current["state"] == "SETTLED":
            certificate = self.engine.get_settlement_certificate(intent_id)
            return {
                "intent_id": intent_id,
                "verdict": "SETTLED",
                "entitlement_granted": True,
                "settlement_certificate_id": certificate["certificate_id"],
                "idempotent": True,
            }
        if current["state"] in {"EXPIRED", "REJECTED", "MANUAL_REVIEW"}:
            return {"intent_id": intent_id, "verdict": "MANUAL_REVIEW", "entitlement_granted": False}

        if current["state"] == "INTENT_CREATED":
            current = self.engine.transition_payment(intent_id, "USER_ACTION_REQUIRED", "payment action observed")
        if current["state"] == "USER_ACTION_REQUIRED":
            current = self.engine.transition_payment(intent_id, "TX_OBSERVED", "transaction hash submitted to server verifier")
        if current["state"] == "TX_OBSERVED":
            current = self.engine.transition_payment(intent_id, "VERIFYING", "server-side RPC provenance verification")

        try:
            observation, providers = self.build_trusted_observation(
                intent_id=intent_id, tx_hash=tx_hash, provider_ids=provider_ids
            )
        except EvidencePaymentError as exc:
            return self._mark_manual_review(intent_id, exc.code)

        if current["state"] == "VERIFYING":
            self.engine.transition_payment(intent_id, "FINALITY_PENDING", "trusted RPC evidence bound")
        return self.engine.settle(intent_id, observation, providers)


__all__ = ["TrustedPolygonRPCAdapter", "RPC_PROVENANCE_VERSION"]
