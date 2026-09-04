from pathlib import Path
import subprocess
import sys

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


def test_support_class_identity_is_stable_in_direct_bot_entrypoint_mode():
    script = f"""
import sys
sys.path.insert(0, {str(ROOT / 'bot')!r})
import telegram_private_support as private
import telegram_support_transport as durable
import telegram_ticket_commands as commands
assert durable.TelegramPrivateSupportRuntime is private.TelegramPrivateSupportRuntime
assert commands.TelegramDurableSupportRuntime is durable.TelegramDurableSupportRuntime
"""
    subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True)


def test_support_class_identity_is_stable_in_package_mode():
    from bot import telegram_private_support as private
    from bot import telegram_support_transport as durable
    from bot import telegram_ticket_commands as commands

    assert durable.TelegramPrivateSupportRuntime is private.TelegramPrivateSupportRuntime
    assert commands.TelegramDurableSupportRuntime is durable.TelegramDurableSupportRuntime
