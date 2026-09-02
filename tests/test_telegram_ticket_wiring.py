from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "bot" / "main.py").read_text()


def test_ticket_and_escalate_are_registered_only_through_authorized_facade():
    assert '"ticket":ticket' in MAIN
    assert '"escalate":escalate' in MAIN
    assert "create_case_ticket_command(" in MAIN
    assert "TelegramDurableSupportRuntime" in MAIN
    assert 'os.getenv("CRYPTOAID_SUPPORT_TRANSPORT_DB", "").strip()' in MAIN


def test_ticket_handler_is_dm_only_case_id_only_and_uses_existing_linked_session():
    section = MAIN.split("async def _ticket_command", 1)[1].split("async def ask_text", 1)[0]
    assert 'update.effective_chat.type != "private"' in section
    assert "len(context.args) != 1" in section
    assert 'context.user_data.get("support_session_id")' in section
    assert "telegram_principal(update)" in section
    assert "args=context.args" in section
    assert "summary=" not in section
    assert "private Evidence" in section


def test_help_surface_exposes_minimum_private_ticket_commands_without_free_text_contract():
    assert "/ticket <Case ID>" in MAIN
    assert "/escalate <Case ID>" in MAIN
    assert "No free text is accepted" in MAIN
    assert "Non è accettato testo libero" in MAIN
