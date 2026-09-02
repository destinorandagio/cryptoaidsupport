"""CHAT07 nurturing selector. Presentation/growth only; no Case or payment authority."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "nurturing_flows.json"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def touch_for_day(flow: str, day: int) -> dict | None:
    cfg = load_config()
    items = cfg["flows"].get(flow, [])
    for item in items:
        if item.get("day") == day:
            return item
    return None


def cta_url(cta: str) -> str | None:
    return load_config().get("cta_registry", {}).get(cta)


def can_nurture(*, touches_today: int, hours_since_last: float) -> bool:
    guard = load_config()["anti_spam"]
    return touches_today < guard["max_nurture_touches_per_day"] and hours_since_last >= guard["min_hours_between_touches"]


def invite_copy(language: str = "en") -> str:
    if language == "it":
        return "Conosci una persona che ha perso fondi o non sa come muoversi nel Web3? Invitala nella community CryptoAID: informazione verificata, sicurezza ed evidence-first. Nessuna promessa di recupero."
    return "Know someone who lost funds or does not know what to do next in Web3? Invite them to the CryptoAID community for verified information, security and evidence-first guidance. No recovery guarantees."
