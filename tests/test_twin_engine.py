import pytest

from twin.contracts import DAPPMAP_CONTRACT, POLYGON_CHAIN_ID, WALLET_MATRIX
from twin.engine import DigitalTwinEngine, TwinRecord, TwinStatus


def test_alias_resolution_and_old_name():
    engine = DigitalTwinEngine([TwinRecord("p1", "New Project", {"Old Project"}, 137, status=TwinStatus.VERIFIED)])
    assert engine.resolve_one("old-project").twin_id == "p1"


def test_same_name_different_chain_requires_disambiguation():
    engine = DigitalTwinEngine([
        TwinRecord("p1", "Alpha", chain_id=137),
        TwinRecord("p2", "Alpha", chain_id=1),
    ])
    with pytest.raises(ValueError):
        engine.resolve_one("Alpha")
    assert engine.resolve_one("Alpha", chain_id=137).twin_id == "p1"


def test_contract_resolution_is_case_insensitive():
    address = "0x" + "aB" * 20
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha", chain_id=137, contracts={address})])
    assert engine.resolve_one(address.upper().replace("0X", "0x")).twin_id == "p1"


def test_search_miss_is_to_verify_not_verified():
    result = DigitalTwinEngine().search_or_candidate("Unknown")
    assert result["state"] == "TO_VERIFY"
    assert result["case_available"] is True
    assert result["promoted"] is False


def test_wallet_contract_is_non_custodial_polygon_user_confirmed():
    assert POLYGON_CHAIN_ID == 137
    assert WALLET_MATRIX["custody"] == "NON_CUSTODIAL"
    assert "private_key" in WALLET_MATRIX["forbidden_storage"]
    assert WALLET_MATRIX["signing_policy"] == "USER_CONFIRMED_ONLY"


def test_dappmap_requires_epistemic_metadata():
    required = set(DAPPMAP_CONTRACT["required_epistemic_fields"])
    assert {"source", "confidence", "freshness", "status", "version"} <= required
