from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from bot.support_binding import SupportBindingRejected, SupportBindingStore
from core import CaseEngine, CoreError, TrustedSupportAPI


def _fixture(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    support_db = tmp_path / "private" / "support-binding.sqlite"
    core = CaseEngine(core_db)
    owner = core.register_user("SIC-BIND-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-BIND-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(
        owner["user_id"], owner["sic_id"], "req-s-owner", "idem-s-owner", 3600
    )
    other_session = core.create_session(
        other["user_id"], other["sic_id"], "req-s-other", "idem-s-other", 3600
    )
    case = core.open_case(
        owner["user_id"],
        owner["sic_id"],
        None,
        "project:unknown",
        False,
        "USER",
        "req-case",
        "idem-case",
    )
    store = SupportBindingStore(
        support_db,
        core_db,
        link_ttl_seconds=300,
        binding_ttl_seconds=3600,
    )
    return core_db, support_db, core, store, owner, other, owner_session, other_session, case


def _issue(store: SupportBindingStore, session: dict, sic_id: str, *, now: int = 1000) -> str:
    return store.issue_link_code(
        core_session_id=session["session_id"],
        sic_id=sic_id,
        now=now,
    )


def test_live_core_session_can_bind_once_and_raw_transport_secrets_are_not_stored(tmp_path: Path):
    _, support_db, _, store, owner, _, owner_session, _, _ = _fixture(tmp_path)
    telegram_principal = "telegram-user-123456789"
    link_code = _issue(store, owner_session, owner["sic_id"])
    support_session = store.consume_link_code(
        telegram_principal=telegram_principal,
        link_code=link_code,
        now=1001,
    )

    raw = support_db.read_bytes()
    assert link_code.encode() not in raw
    assert support_session.encode() not in raw
    assert telegram_principal.encode() not in raw
    assert owner["sic_id"].encode() in raw  # private resolver reference; never public-package data

    resolver = store.resolver_for_principal(telegram_principal, now=lambda: 1002)
    resolved = resolver(support_session)
    assert resolved == {
        "session_id": owner_session["session_id"],
        "sic_id": owner["sic_id"],
    }

    with pytest.raises(SupportBindingRejected) as replay:
        store.consume_link_code(
            telegram_principal=telegram_principal,
            link_code=link_code,
            now=1002,
        )
    assert str(replay.value) == "support_binding_failed"


def test_link_code_expiry_and_core_revocation_fail_before_binding(tmp_path: Path):
    _, _, core, store, owner, _, owner_session, _, _ = _fixture(tmp_path)
    expired = _issue(store, owner_session, owner["sic_id"], now=1000)
    with pytest.raises(SupportBindingRejected):
        store.consume_link_code(
            telegram_principal="tg-expired",
            link_code=expired,
            now=1301,
        )

    revoked = _issue(store, owner_session, owner["sic_id"], now=2000)
    core.revoke_session(owner_session["session_id"], owner["user_id"])
    with pytest.raises(SupportBindingRejected) as exc:
        store.consume_link_code(
            telegram_principal="tg-revoked",
            link_code=revoked,
            now=2001,
        )
    assert str(exc.value) == "support_binding_failed"


def test_eight_concurrent_consumers_of_one_code_have_exactly_one_winner(tmp_path: Path):
    _, _, _, store, owner, _, owner_session, _, _ = _fixture(tmp_path)
    code = _issue(store, owner_session, owner["sic_id"])

    def consume(index: int):
        try:
            token = store.consume_link_code(
                telegram_principal=f"tg-race-{index}",
                link_code=code,
                now=1001,
            )
            return ("PASS", token)
        except SupportBindingRejected as exc:
            return ("REJECT", str(exc))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(consume, range(8)))

    winners = [value for status, value in results if status == "PASS"]
    rejects = [value for status, value in results if status == "REJECT"]
    assert len(winners) == 1
    assert len(rejects) == 7
    assert set(rejects) == {"support_binding_failed"}

    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM support_link_codes WHERE consumed_at IS NOT NULL"
        ).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM support_principal_bindings").fetchone()[0] == 1


def test_support_session_is_principal_scoped_revocable_and_expiring(tmp_path: Path):
    _, _, _, store, owner, _, owner_session, _, _ = _fixture(tmp_path)
    code = _issue(store, owner_session, owner["sic_id"])
    token = store.consume_link_code(
        telegram_principal="tg-owner",
        link_code=code,
        now=1001,
    )

    assert store.resolver_for_principal("tg-owner", now=lambda: 1002)(token) is not None
    assert store.resolver_for_principal("tg-attacker", now=lambda: 1002)(token) is None

    store.revoke_principal("tg-owner", now=1003)
    assert store.resolver_for_principal("tg-owner", now=lambda: 1004)(token) is None

    code2 = _issue(store, owner_session, owner["sic_id"], now=2000)
    token2 = store.consume_link_code(
        telegram_principal="tg-owner-2",
        link_code=code2,
        now=2001,
    )
    assert store.resolver_for_principal("tg-owner-2", now=lambda: 5602)(token2) is None


def test_trusted_support_api_revalidates_core_and_case_owner_end_to_end(tmp_path: Path):
    core_db, _, core, store, owner, other, owner_session, other_session, case = _fixture(tmp_path)

    owner_code = _issue(store, owner_session, owner["sic_id"])
    owner_token = store.consume_link_code(
        telegram_principal="tg-owner",
        link_code=owner_code,
        now=1001,
    )
    owner_api = TrustedSupportAPI(
        core_db,
        store.resolver_for_principal("tg-owner", now=lambda: 1002),
    )
    verdict = owner_api.case_authorization(
        support_session_id=owner_token,
        case_id=case["case_id"],
    )
    assert set(verdict) == {
        "case_id",
        "requester_is_case_owner",
        "case_state",
        "case_version",
    }
    assert verdict["requester_is_case_owner"] is True

    other_code = _issue(store, other_session, other["sic_id"], now=1100)
    other_token = store.consume_link_code(
        telegram_principal="tg-other",
        link_code=other_code,
        now=1101,
    )
    other_api = TrustedSupportAPI(
        core_db,
        store.resolver_for_principal("tg-other", now=lambda: 1102),
    )
    with pytest.raises(CoreError) as cross_user:
        other_api.case_authorization(
            support_session_id=other_token,
            case_id=case["case_id"],
        )
    assert cross_user.value.code == "SUPPORT_AUTHORIZATION_FAILED"

    core.revoke_session(owner_session["session_id"], owner["user_id"])
    with pytest.raises(CoreError) as revoked:
        owner_api.case_authorization(
            support_session_id=owner_token,
            case_id=case["case_id"],
        )
    assert revoked.value.code == "SUPPORT_AUTHORIZATION_FAILED"


def test_support_binding_database_is_rejected_inside_public_html(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    CaseEngine(core_db)
    with pytest.raises(ValueError) as exc:
        SupportBindingStore(tmp_path / "public_html" / "support.sqlite", core_db)
    assert str(exc.value) == "support_binding_db_must_be_private"
