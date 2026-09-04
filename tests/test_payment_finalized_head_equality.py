from evidence_payment import EvidencePaymentEngine


def provider(provider_id: str, *, tx_block: int = 100, finalized: int) -> dict:
    return {
        "provider_id": provider_id,
        "tx_block_number": tx_block,
        "finalized_block_number": finalized,
    }


def test_tx_in_latest_finalized_block_is_finalized_not_pending():
    observation = {"block_number": 100}
    verdict, records = EvidencePaymentEngine._provider_finality(
        observation,
        [
            provider("rpc_a", finalized=100),
            provider("rpc_b", finalized=100),
        ],
    )
    assert verdict == "SETTLED"
    assert all(record["finalized"] is True for record in records)


def test_below_finalized_head_remains_pending_and_mixed_is_manual_review():
    observation = {"block_number": 100}
    pending, _ = EvidencePaymentEngine._provider_finality(
        observation,
        [provider("rpc_a", finalized=99), provider("rpc_b", finalized=99)],
    )
    mixed, _ = EvidencePaymentEngine._provider_finality(
        observation,
        [provider("rpc_a", finalized=100), provider("rpc_b", finalized=99)],
    )
    assert pending == "FINALITY_PENDING"
    assert mixed == "MANUAL_REVIEW"
