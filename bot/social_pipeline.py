"""Generate channel-specific drafts from one CryptoAID acquisition topic.
No LinkedIn scraping/posting: LinkedIn output is an artifact/draft for manual or official-API delivery.
"""
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "social"

PILLARS = ["social_proof", "web3_intelligence", "educational", "founder"]
TOPICS = {
 "social_proof": "How evidence turns a confusing Web3 incident into a structured investigation",
 "web3_intelligence": "Dead dApps and dead tokens: what users should verify before acting",
 "educational": "The first public evidence to preserve after a suspected crypto scam",
 "founder": "Why CryptoAID is building an investigation-first support ecosystem",
}

def render(pillar, lang):
    topic = TOPICS[pillar]
    if lang == "it":
        linkedin = f"{topic}\n\nCryptoAID parte da un principio semplice: prima si raccolgono fatti verificabili, poi si decide il percorso. Nessuna promessa di recovery. Mai condividere seed phrase o chiavi private.\n\n→ Scopri CryptoAID: cryptoaid.support"
        telegram = f"🛡 {topic}\n\nPrima i fatti. Poi il percorso. Conserva solo evidenze pubbliche: transaction hash, address, contract e URL. Non condividere mai seed phrase o chiavi private.\n\n🌐 cryptoaid.support"
    else:
        linkedin = f"{topic}\n\nCryptoAID starts with a simple principle: collect verifiable facts first, then decide the path. No recovery guarantees. Never share seed phrases or private keys.\n\n→ Explore CryptoAID: cryptoaid.support"
        telegram = f"🛡 {topic}\n\nFacts first. Path second. Preserve public evidence such as transaction hashes, addresses, contracts and URLs. Never share seed phrases or private keys.\n\n🌐 cryptoaid.support"
    return {"pillar":pillar,"topic":topic,"linkedin":linkedin,"telegram":telegram,"language":lang}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pillar",choices=PILLARS); p.add_argument("--lang",choices=["en","it"],default="en"); a=p.parse_args()
    pillar=a.pillar or PILLARS[datetime.now(timezone.utc).weekday()%len(PILLARS)]
    payload=render(pillar,a.lang); OUT.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path=OUT/f"social-{stamp}-{a.lang}.json"; path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(path); print(json.dumps(payload,ensure_ascii=False))
if __name__ == "__main__": main()
