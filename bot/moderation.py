import re

HIGH_RISK = [
 r"\b(seed phrase|recovery phrase|private key|secret phrase)\b",
 r"\b(send|give|share|enter|verify)\b.{0,35}\b(seed|private key|recovery phrase)\b",
 r"\bguaranteed\s+(profit|return|recovery)\b",
 r"\bwallet\s*(drainer|validation|rectification)\b",
]
MEDIUM_RISK = [
 r"\b(double your|risk[- ]?free profit|100% return)\b",
 r"\b(dm me|message me privately)\b.{0,50}\b(support|recovery|investment)\b",
 r"\b(airdrop|giveaway|presale)\b.{0,80}\b(connect wallet|claim now|urgent)\b",
]
SHORTENERS=("bit.ly/","tinyurl.com/","t.co/","cutt.ly/","rb.gy/")


def classify_message(text: str):
    value=(text or "").lower()
    reasons=[]
    for p in HIGH_RISK:
        if re.search(p,value,re.I): reasons.append("high_risk_pattern")
    for p in MEDIUM_RISK:
        if re.search(p,value,re.I): reasons.append("medium_risk_pattern")
    if any(x in value for x in SHORTENERS): reasons.append("shortened_url")
    high=reasons.count("high_risk_pattern")
    medium=reasons.count("medium_risk_pattern")
    level=4 if high else 2 if medium or "shortened_url" in reasons else 0
    return {"level":level,"reasons":sorted(set(reasons))}
