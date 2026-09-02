"""CryptoAID Social Acquisition OS.
Shared, privacy-minimal intent scoring and conversation routing for Telegram
and manually/officially sourced LinkedIn interactions.
"""
from dataclasses import dataclass
from typing import Iterable

SIGNAL_POINTS = {
    # Cross-channel / legacy
    "profile_view": 2,
    "reaction": 2,
    "comment": 5,
    "connection": 4,
    "lead_magnet": 10,
    "dm_reply": 12,
    "site_visit": 8,
    "case_start": 30,
    "case_paid": 50,
    # Telegram-native
    "bot_start": 3,
    "group_join": 2,
    "question": 4,
    "security_question": 6,
    "scam_question": 8,
    "recovery_question": 8,
    "checklist_request": 10,
    "case_command": 15,
    "evidence_supplied": 18,
    "case_started": 30,
    "case_completed": 40,
    "paid_case": 50,
    "referral": 20,
    "poll_vote": 3,
}

RISK_TERMS = (
    "seed phrase", "private key", "password", "2fa", "recovery phrase", "mnemonic"
)
CASE_TERMS = (
    "scam", "rug pull", "rugpull", "hacked", "hack", "stolen", "lost funds",
    "dead token", "dead dapp", "recovery", "abandoned dapp", "wallet drainer"
)
EVIDENCE_TERMS = (
    "tx hash", "transaction hash", "wallet address", "contract address", "public url",
    "etherscan", "polygonscan", "screenshot"
)

@dataclass(frozen=True)
class Intent:
    score: int
    stage: str
    case_intent: bool
    evidence_signal: bool
    safety_risk: bool


def stage_for(score: int) -> str:
    if score >= 60: return "customer"
    if score >= 35: return "case_ready"
    if score >= 20: return "problem_aware"
    if score >= 10: return "engaged"
    if score >= 3: return "aware"
    return "cold"


def assess(text: str = "", signals: Iterable[str] = ()) -> Intent:
    lower = (text or "").lower()
    score = sum(SIGNAL_POINTS.get(s, 0) for s in signals)
    case_intent = any(t in lower for t in CASE_TERMS)
    evidence = any(t in lower for t in EVIDENCE_TERMS)
    risk = any(t in lower for t in RISK_TERMS)
    if case_intent: score += 12
    if evidence: score += 8
    return Intent(score, stage_for(score), case_intent, evidence, risk)


def next_step(intent: Intent, language: str = "en") -> str:
    it = language == "it"
    if intent.safety_risk:
        return ("Non inviare seed phrase, chiavi private, password, mnemonic o codici 2FA. "
                "Condividi solo prove pubbliche e non segrete." if it else
                "Never send seed phrases, private keys, passwords, mnemonics or 2FA codes. Share only public, non-secret evidence.")
    if intent.case_intent and intent.evidence_signal:
        return ("Sembra esserci un caso concreto. Posso aiutarti a strutturare le informazioni pubbliche necessarie per avviare un Case CryptoAID." if it else
                "This looks like a concrete case. I can help structure the public information needed to start a CryptoAID Case.")
    if intent.case_intent:
        return ("Capito. Quale progetto, token o dApp è coinvolto? Non pubblicare segreti del wallet." if it else
                "Understood. Which project, token or dApp is involved? Do not post wallet secrets.")
    return ("Posso aiutarti con sicurezza Web3, scam, dApp/token e percorso CryptoAID." if it else
            "I can help with Web3 safety, scams, dApps/tokens and the CryptoAID path.")
