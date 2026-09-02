import json

from twin.mirror_registry import MirrorRegistryIndex
from twin.runtime_search import SEARCH_RUNTIME_CONTRACT_VERSION, SearchReadFacade


def _row(twin_id: str, name: str, *, aliases: str = "", token: str = "", contract: str = "", status: str = "STATUS_UNVERIFIED") -> dict[str, str]:
    return {
        "ID MIRROR81+": twin_id,
        "Nome canonico": name,
        "Alias / versioni": aliases,
        "Stato prudenziale": status,
        "Categoria": "Test",
        "Chain": "Polygon",
        "Chain primaria": "Polygon",
        "Token": token,
        "Contratti / indirizzi": contract,
        "Sito ufficiale": "https://example.invalid",
        "Copertura fonti": "fixture",
        "Attendibilità": "A",
        "Data acquisizione": "2026-08-20 00:00:00",
    }


def _facade() -> SearchReadFacade:
    rows = [
        _row(
            "M81-1",
            "Alpha",
            aliases="Alpha Protocol",
            token="ALP",
            contract="0x1111111111111111111111111111111111111111",
        ),
        _row("M81-2", "Beta", aliases="Common", token="SAME"),
        _row("M81-3", "Gamma", aliases="Common", token="SAME"),
    ]
    return SearchReadFacade(MirrorRegistryIndex.from_rows(rows, source_version="mirror81-test"))


def test_known_and_alias_return_same_minimal_trustworthy_twin():
    facade = _facade()
    canonical = facade.query("Alpha")
    alias = facade.query("Alpha Protocol")
    assert canonical["state"] == alias["state"] == "MATCH"
    assert canonical["result"]["twin_id"] == alias["result"]["twin_id"] == "M81-1"
    card = canonical["result"]
    assert card["status"] == "KNOWN"
    assert card["source"] == "MIRROR81:fixture"
    assert card["source_date"] == "2026-08-20 00:00:00"
    assert card["confidence"] == 0.9
    assert card["cache_state"] == "STALE"
    assert card["truth_label"] == "CACHED"
    assert card["source_status"] == "STATUS_UNVERIFIED"
    assert card["case_available"] is True


def test_unknown_is_to_verify_and_can_continue_without_promotion():
    payload = _facade().query("Unknown Project")
    assert payload["state"] == "TO_VERIFY"
    assert payload["result"] is None
    assert payload["results"] == []
    assert payload["candidate"] == {
        "status": "USER_SUBMITTED_TO_VERIFY",
        "truth_label": "TO_VERIFY",
        "promoted": False,
        "case_available": True,
    }


def test_ambiguous_term_never_first_picks_a_twin():
    payload = _facade().query("Common")
    assert payload["state"] == "AMBIGUOUS"
    assert payload["result"] is None
    assert payload["requires_disambiguation"] is True
    assert {card["twin_id"] for card in payload["results"]} == {"M81-2", "M81-3"}


def test_runtime_envelope_is_json_serializable_and_authority_explicit():
    payload = _facade().query("ALP", chain_id=137)
    assert payload["contract_version"] == SEARCH_RUNTIME_CONTRACT_VERSION
    assert payload["authority"] == "READ_ONLY_MIRROR_DERIVED_TWIN_VIEW"
    assert payload["source_version"] == "mirror81-test"
    assert payload["chain_id"] == 137
    json.dumps(payload)


def test_candidate_source_status_cannot_leak_into_verified_twin_status():
    index = MirrorRegistryIndex.from_rows(
        [_row("M81-X", "Candidate Example", status="CANDIDATE")],
        source_version="mirror81-test",
    )
    payload = SearchReadFacade(index).query("Candidate Example")
    assert payload["state"] == "MATCH"
    assert payload["result"]["status"] == "KNOWN"
    assert payload["result"]["source_status"] == "CANDIDATE"
    assert payload["result"]["truth_label"] == "CACHED"
    assert payload["result"]["status"] != "VERIFIED"


def test_blank_search_query_fails_closed():
    try:
        _facade().query("   ")
    except ValueError as exc:
        assert "search query is required" in str(exc)
    else:
        raise AssertionError("blank query must fail closed")
