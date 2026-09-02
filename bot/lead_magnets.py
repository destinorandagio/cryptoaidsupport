"""Lead magnet routing for CryptoAID Social Acquisition OS.
No secret wallet material is ever requested or stored here.
"""

MAGNETS = {
    "scam": {
        "id": "crypto-scam-emergency-checklist",
        "en": "Crypto Scam Emergency Checklist",
        "it": "Checklist Emergenza Crypto Scam",
    },
    "rug": {
        "id": "rug-pull-evidence-checklist",
        "en": "Rug Pull Evidence Checklist",
        "it": "Checklist Evidenze Rug Pull",
    },
    "dead_token": {
        "id": "dead-token-survival-guide",
        "en": "Dead Token Survival Guide",
        "it": "Guida di Sopravvivenza Dead Token",
    },
    "dead_dapp": {
        "id": "dead-dapp-atlas",
        "en": "Dead DApp Atlas",
        "it": "Dead DApp Atlas",
    },
    "wallet": {
        "id": "wallet-exposure-checklist",
        "en": "Wallet Exposure Checklist",
        "it": "Checklist Esposizione Wallet",
    },
    "default": {
        "id": "cryptoaid-case-pre-assessment",
        "en": "CryptoAID Case Pre-Assessment",
        "it": "Pre-Assessment Case CryptoAID",
    },
}


def route(text: str, language: str = "en") -> dict:
    t = (text or "").lower()
    if "rug" in t:
        key = "rug"
    elif "dead token" in t:
        key = "dead_token"
    elif "dead dapp" in t or "abandoned dapp" in t:
        key = "dead_dapp"
    elif "wallet" in t or "drainer" in t:
        key = "wallet"
    elif any(x in t for x in ("scam", "fraud", "hacked", "stolen")):
        key = "scam"
    else:
        key = "default"
    item = MAGNETS[key]
    return {"key": key, "id": item["id"], "title": item["it" if language == "it" else "en"]}
