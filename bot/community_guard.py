"""CHAT07 community safety guard adapted from established Telegram moderation patterns.
Detection only; irreversible moderation remains human/admin controlled unless explicitly authorized.
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
import re

OFFICIAL_HOSTS={"cryptoaid.support","t.me"}
SHORTENERS={"bit.ly","tinyurl.com","cutt.ly","rb.gy","is.gd","tiny.cc"}
SUSPICIOUS_TERMS=(
    "seed phrase","private key","wallet validation","wallet rectification",
    "guaranteed recovery","guaranteed return","double your","risk-free profit",
)
URL_RE=re.compile(r"https?://[^\s<>]+",re.I)

@dataclass(frozen=True)
class GuardDecision:
    level:int
    action:str
    reasons:tuple[str,...]
    urls:tuple[str,...]


def classify_url(url:str)->str:
    try:
        host=(urlparse(url).hostname or "").lower()
    except Exception:
        return "INVALID"
    if not host: return "INVALID"
    if host in SHORTENERS: return "SHORTENER"
    if host=="cryptoaid.support" or host.endswith(".cryptoaid.support"): return "OFFICIAL"
    if host=="t.me": return "TELEGRAM"
    return "EXTERNAL"


def inspect(text:str, *, is_admin:bool=False)->GuardDecision:
    value=(text or "").strip()
    lower=value.lower()
    urls=tuple(URL_RE.findall(value))
    reasons=[]
    for term in SUSPICIOUS_TERMS:
        if term in lower: reasons.append(f"term:{term}")
    for url in urls:
        cls=classify_url(url)
        if cls=="SHORTENER": reasons.append("shortened_url")
        elif cls=="INVALID": reasons.append("invalid_url")
    dm_pitch=bool(re.search(r"\b(dm me|message me privately|scrivimi in privato|contattami in privato)\b",lower))
    money_pitch=bool(re.search(r"\b(recovery|recupero|profit|guadagno|investment|investimento)\b",lower))
    if dm_pitch and money_pitch: reasons.append("unsolicited_private_pitch")
    if is_admin and not any(r.startswith("term:seed phrase") or r.startswith("term:private key") for r in reasons):
        return GuardDecision(0,"ALLOW",tuple(sorted(set(reasons))),urls)
    high=any(r.startswith("term:") for r in reasons) or "unsolicited_private_pitch" in reasons
    medium="shortened_url" in reasons or "invalid_url" in reasons
    if high: return GuardDecision(4,"WARN_AND_REVIEW",tuple(sorted(set(reasons))),urls)
    if medium: return GuardDecision(2,"WARN",tuple(sorted(set(reasons))),urls)
    return GuardDecision(0,"ALLOW",(),urls)
