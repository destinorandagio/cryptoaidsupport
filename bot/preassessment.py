"""Structured, privacy-minimal CryptoAID Case pre-assessment.
Only public/non-secret evidence fields are represented.
"""
from dataclasses import dataclass, asdict

FORBIDDEN = ("seed phrase", "private key", "password", "2fa", "recovery phrase", "mnemonic")

@dataclass(frozen=True)
class PreAssessment:
    project: str = ""
    incident: str = ""
    approximate_date: str = ""
    chain: str = ""
    public_tx_hash: str = ""
    public_address: str = ""
    public_contract: str = ""
    public_url: str = ""

    def public_dict(self) -> dict:
        return {k: v.strip() for k, v in asdict(self).items() if v and v.strip()}


def contains_secret(text: str) -> bool:
    lower = (text or "").lower()
    return any(term in lower for term in FORBIDDEN)


def completeness(data: PreAssessment) -> dict:
    values = data.public_dict()
    core = ["project", "incident", "chain"]
    evidence = ["public_tx_hash", "public_address", "public_contract", "public_url"]
    core_count = sum(bool(values.get(k)) for k in core)
    evidence_count = sum(bool(values.get(k)) for k in evidence)
    score = min(100, core_count * 20 + min(evidence_count, 2) * 20)
    return {
        "score": score,
        "qualified": core_count == len(core) and evidence_count >= 1,
        "missing_core": [k for k in core if not values.get(k)],
        "has_public_evidence": evidence_count > 0,
    }
