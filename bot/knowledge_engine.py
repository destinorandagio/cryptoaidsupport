import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "knowledge" / "cryptoaid_master.json"
FAQ = ROOT / "knowledge" / "faq.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def detect_language(text: str) -> str:
    t = text.lower()
    italian = (" cos'è ", " cosa ", " come ", " aiuto", "truff", "sicurezza", "recuper", "portafoglio", "servizi", "funziona")
    padded = f" {t} "
    return "it" if any(x in padded for x in italian) else "en"


def normalize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9àèéìòù]+", text.lower()) if len(w) > 2}


def score(query: str, candidate: str) -> float:
    q = normalize(query)
    c = normalize(candidate)
    if not q or not c:
        return 0.0
    return len(q & c) / max(1, len(q))


def built_in_answers(master: dict, lang: str):
    identity = master["identity"]
    recovery = master["recovery"]
    links = master["official_links"]
    if lang == "it":
        return [
            ("cos'è cryptoaid cosa è cryptoaid chi siete", identity["description_it"]),
            ("sito link ufficiali telegram gruppo canale", f"Link ufficiali CryptoAID:\n🌐 {links['website']}\n💬 {links['group']}\n📢 {links['channel']}"),
            ("recovery recupero fondi truffa scam investigazione", recovery["positioning_it"] + " Non condividere mai seed phrase, chiavi private, password o codici 2FA."),
            ("sicurezza seed phrase chiave privata password 2fa", "CryptoAID mette la sicurezza al primo posto: non condividere mai seed phrase, chiave privata, password o codici 2FA. Un supporto legittimo CryptoAID non te li chiederà."),
            ("servizi cosa fate aiuto supporto", "CryptoAID offre orientamento e supporto su ecosistema CryptoAID, sicurezza crypto, scam, wallet, blockchain, Web3, token, dApp, recovery education, segnalazioni e triage tecnico."),
        ]
    return [
        ("what is cryptoaid who are you", identity["description_en"]),
        ("official links website telegram group channel", f"Official CryptoAID links:\n🌐 {links['website']}\n💬 {links['group']}\n📢 {links['channel']}"),
        ("recovery recover funds scam investigation", recovery["positioning_en"] + " Never share a seed phrase, private key, password or 2FA code."),
        ("security seed phrase private key password 2fa", "CryptoAID puts security first: never share your seed phrase, private key, password or 2FA codes. Legitimate CryptoAID support will never ask for them."),
        ("services help support what do you do", "CryptoAID provides orientation and support around the CryptoAID ecosystem, crypto security, scams, wallets, blockchain, Web3, tokens, dApps, recovery education, reports and technical triage."),
    ]


def answer(query: str, language: str | None = None) -> tuple[str, float, str]:
    master = load_json(MASTER)
    lang = language or detect_language(query)
    candidates = [(k, v, "master") for k, v in built_in_answers(master, lang)]

    if FAQ.exists():
        data = load_json(FAQ)
        items = data if isinstance(data, list) else data.get("items", [])
        for item in items:
            if item.get("language", lang) != lang:
                continue
            q = item.get("question") or item.get("q") or ""
            a = item.get("answer") or item.get("a") or ""
            if q and a:
                candidates.append((q, a, "faq"))

    ranked = sorted(((score(query, key), text, source) for key, text, source in candidates), reverse=True)
    if ranked and ranked[0][0] >= 0.28:
        confidence, text, source = ranked[0]
        return text, confidence, source

    fallback = (
        "Non ho ancora una risposta CryptoAID verificata abbastanza precisa per questa domanda. Usa /support: posso indirizzare la richiesta a un amministratore senza inventare informazioni."
        if lang == "it" else
        "I don't yet have a sufficiently verified CryptoAID answer for that question. Use /support and I can route the request to a human admin rather than invent information."
    )
    return fallback, 0.0, "escalation"
