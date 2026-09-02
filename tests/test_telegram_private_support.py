from pathlib import Path

import pytest

from bot.telegram_private_support import (
    TelegramPrivateSupportRejected,
    TelegramPrivateSupportRuntime,
)
from core import CaseEngine


def _fixture(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    binding_db = tmp_path / "private" / "support-binding.sqlite"
    core = CaseEngine(core_db)
    owner = core.register_user("SIC-TG-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-TG-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(
        owner["user_id"], owner["sic_id"], "req-s-owner", "idem-s-owner", 3600
    )
    other_session = core.create_session(
        other["user_id"], other["sic_id"], "req-s-other", "idem-s-other", 3600
    )
    case = core.open_case(
        owner["user_id"], owner["sic_id"], None, "project:unknown", False,
        "USER", "req-case", "idem-case",
    )
    runtime = TelegramPrivateSupportRuntime(binding_db, core_db)
    return core, runtime, owner, other, owner_session, other_session, case


def _bind(runtime, session, sic_id, principal):
    code = runtime.store.issue_link_code(
        core_session_id=session["session_id"], sic_id=sic_id
    )
    return runtime.bind(telegram_principal=principal, link_code=code)


def test_bound_owner_gets_only_minimal_core_case_projection(tmp_path: Path):
    _, runtime, owner, _, owner_session, _, case = _fixture(tmp_path)
    token = _bind(runtime, owner_session, owner["sic_id"], "telegram:1001")
    verdict = runtime.case_status(
        telegram_principal="telegram:1001",
        support_session_id=token,
        case_id=case["case_id"],
    )
    assert verdict["requester_is_case_owner"] is True
    assert verdict["case_id"] == case["case_id"]
    assert set(verdict) == {
        "case_id", "requester_is_case_owner", "case_state", "case_version"
    }
    serialized = repr(verdict).lower()
    assert "sic-" not in serialized
    assert "wallet" not in serialized
    assert "evidence" not in serialized
    assert "payment" not in serialized


def test_stolen_support_token_fails_for_other_telegram_principal(tmp_path: Path):
    _, runtime, owner, _, owner_session, _, case = _fixture(tmp_path)
    token = _bind(runtime, owner_session, owner["sic_id"], "telegram:1001")
    with pytest.raises(TelegramPrivateSupportRejected) as exc:
        runtime.case_status(
            telegram_principal="telegram:attacker",
            support_session_id=token,
            case_id=case["case_id"],
        )
    assert str(exc.value) == "private_support_failed"


def test_cross_user_case_and_core_revocation_fail_closed(tmp_path: Path):
    core, runtime, owner, other, owner_session, other_session, case = _fixture(tmp_path)
    other_token = _bind(runtime, other_session, other["sic_id"], "telegram:other")
    with pytest.raises(TelegramPrivateSupportRejected):
        runtime.case_status(
            telegram_principal="telegram:other",
            support_session_id=other_token,
            case_id=case["case_id"],
        )

    owner_token = _bind(runtime, owner_session, owner["sic_id"], "telegram:owner")
    core.revoke_session(owner_session["session_id"], owner["user_id"])
    with pytest.raises(TelegramPrivateSupportRejected):
        runtime.case_status(
            telegram_principal="telegram:owner",
            support_session_id=owner_token,
            case_id=case["case_id"],
        )


def test_env_runtime_is_explicit_opt_in_and_public_webroot_remains_forbidden(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CRYPTOAID_SUPPORT_BINDING_DB", raising=False)
    monkeypatch.delenv("CRYPTOAID_CORE_DB", raising=False)
    with pytest.raises(TelegramPrivateSupportRejected) as missing:
        TelegramPrivateSupportRuntime.from_env()
    assert str(missing.value) == "private_support_unavailable"

    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    CaseEngine(core_db)
    monkeypatch.setenv("CRYPTOAID_CORE_DB", str(core_db))
    monkeypatch.setenv(
        "CRYPTOAID_SUPPORT_BINDING_DB",
        str(tmp_path / "public_html" / "support.sqlite"),
    )
    with pytest.raises(TelegramPrivateSupportRejected) as public:
        TelegramPrivateSupportRuntime.from_env()
    assert str(public.value) == "private_support_unavailable"


def test_main_declares_private_link_and_mycase_handlers_without_persisting_token_to_text():
    source = (Path(__file__).parents[1] / "bot" / "main.py").read_text()
    assert '"link":link_support' in source
    assert '"mycase":mycase' in source
    assert 'context.user_data["support_session_id"]' in source
    assert "support_session_id}" not in source
