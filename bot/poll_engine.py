"""Telegram poll factory for CryptoAID community engagement."""
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class Poll:
    id: str
    question: str
    options: tuple[str, ...]
    language: str
    category: str

POLLS = (
    Poll("risk-01", "What worries you most in Web3?", ("Scams", "Wallet security", "Dead dApps/tokens", "Smart contracts"), "en", "security"),
    Poll("risk-it-01", "Cosa ti preoccupa di più nel Web3?", ("Scam", "Sicurezza wallet", "dApp/token morti", "Smart contract"), "it", "security"),
    Poll("case-01", "If a project disappeared today, would you know which public evidence to preserve first?", ("Yes", "Not sure", "No"), "en", "education"),
    Poll("case-it-01", "Se un progetto sparisse oggi, sapresti quali evidenze pubbliche conservare per prime?", ("Sì", "Non sono sicuro", "No"), "it", "education"),
)


def choose(language: str = "en", seed: int | None = None) -> Poll:
    eligible = [p for p in POLLS if p.language == language]
    if not eligible:
        eligible = [p for p in POLLS if p.language == "en"]
    index = seed if seed is not None else datetime.now(timezone.utc).timetuple().tm_yday
    return eligible[index % len(eligible)]
