import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "knowledge" / "cryptoaid_master.json"
CANONICAL_MASTER = ROOT / "knowledge" / "canonical" / "cryptoaid_master.json"
LEGACY_FAQ = ROOT / "knowledge" / "faq.json"
CANONICAL_FAQ = ROOT / "knowledge" / "faq" / "faq_core.json"
SERVICES = ROOT / "knowledge" / "canonical" / "services.json"
LINKS = ROOT / "knowledge" / "canonical" / "official_links.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def detect_language(text: str) -> str:
    t = text.lower()
    italian = (" cos'è ", " cosa ", " come ", " aiuto", "truff", "sicurezza", "recuper", "portafoglio", "servizi", "funziona", "quali")
    padded = f" {t} "
    return "it" if any(x in padded for x in italian) else "en"


def normalize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9àèéìòù]+", text.lower()) if len(w) > 2}


def score(query: str, candidate: str) -> float:
    q = normalize(query)
    c = normalize(candidate)
    return len(q & c) / max(1, len(q)) if q and c else 0.0


def canonical_candidates(lang: str):
    out = []
    if CANONICAL_MASTER.exists():
        m = load_json(CANONICAL_MASTER)
        out.append(("cos'è cryptoaid cosa fa missione" if lang == "it" else "what is cryptoaid mission what does cryptoaid do", m["mission"][lang], "canonical-master"))
    if SERVICES.exists():
        s = load_json(SERVICES)
        rendered = "\n".join(f"• {x['name']}: {x['description']}" for x in s[lang])
        out.append(("servizi cosa fate supporto sicurezza recovery web3 scam" if lang == "it" else "services what do you do support security recovery web3 scam", rendered, "canonical-services"))
    if LINKS.exists():
        l = load_json(LINKS)
        rendered = f"🌐 {l['website']}\n💬 {l['telegram']['group']}\n📢 {l['telegram']['channel']}"
        out.append(("link ufficiali sito gruppo canale telegram" if lang == "it" else "official links website group channel telegram", rendered, "canonical-links"))
    if CANONICAL_FAQ.exists():
        for item in load_json(CANONICAL_FAQ):
            if item.get("lang") == lang:
                out.append((item["q"], item["a"], "canonical-faq"))
    return out


def legacy_candidates(lang: str):
    if not MASTER.exists():
        return []
    master = load_json(MASTER)
    identity, recovery, links = master["identity"], master["recovery"], master["official_links"]
    if lang == "it":
        out = [
            ("cos'è cryptoaid chi siete", identity["description_it"], "legacy-master"),
            ("recovery recupero fondi truffa scam investigazione", recovery["positioning_it"] + " Non condividere mai seed phrase, chiavi private, password o codici 2FA.", "legacy-master"),
        ]
    else:
        out = [
            ("what is cryptoaid who are you", identity["description_en"], "legacy-master"),
            ("recovery recover funds scam investigation", recovery["positioning_en"] + " Never share a seed phrase, private key, password or 2FA code.", "legacy-master"),
        ]
    if LEGACY_FAQ.exists():
        data = load_json(LEGACY_FAQ)
        for item in data if isinstance(data, list) else data.get("items", []):
            item_lang = item.get("language") or item.get("lang")
            if item_lang and item_lang != lang:
                continue
            q, a = item.get("question") or item.get("q"), item.get("answer") or item.get("a")
            if q and a:
                out.append((q, a, "legacy-faq"))
    return out


def answer(query: str, language: str | None = None) -> tuple[str, float, str]:
    lang = language or detect_language(query)
    candidates = canonical_candidates(lang) + legacy_candidates(lang)
    ranked = sorted(((score(query, key), text, source) for key, text, source in candidates), reverse=True)
    if ranked and ranked[0][0] >= 0.28:
        confidence, text, source = ranked[0]
        return text, confidence, source
    fallback = (
        "Non ho ancora una risposta CryptoAID verificata abbastanza precisa per questa domanda. Usa /support: la richiesta può essere indirizzata a un amministratore senza inventare informazioni."
        if lang == "it" else
        "I don't yet have a sufficiently verified CryptoAID answer for that question. Use /support so the request can be routed to a human admin rather than inventing information."
    )
    return fallback, 0.0, "escalation"
