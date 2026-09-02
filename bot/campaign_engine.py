"""CHAT07 campaign/growth engine.
Presentation/orchestration only: no Case, Payment, Evidence, SIC-ID or Knowledge authority.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

ALLOWED_STATES={"DRAFT","READY","ACTIVE","PAUSED","COMPLETED"}
ALLOWED_DESTINATIONS={"channel","group"}

@dataclass(frozen=True)
class Campaign:
    campaign_id:str
    name:str
    goal:str
    audience:str
    language:str
    destination:str
    cta:str
    status:str="DRAFT"
    start:str=""
    end:str=""
    frequency:str="daily"

    def to_dict(self): return asdict(self)

def validate_campaign(c:Campaign)->Campaign:
    if c.status not in ALLOWED_STATES: raise ValueError("invalid_campaign_state")
    if c.language not in {"it","en"}: raise ValueError("invalid_language")
    if c.destination not in ALLOWED_DESTINATIONS: raise ValueError("invalid_destination")
    if not all(x.strip() for x in (c.campaign_id,c.name,c.goal,c.audience,c.cta)): raise ValueError("missing_campaign_field")
    forbidden=("guaranteed recovery","recupero garantito","guaranteed return","rendimento garantito")
    if any(x in f"{c.name} {c.goal} {c.cta}".lower() for x in forbidden): raise ValueError("prohibited_claim")
    return c

def next_funnel_step(stage:str)->str:
    order=["DISCOVERY","CHANNEL","GROUP","ENGAGEMENT","TRUST","SERVICE_DISCOVERY","CTA","CONVERSION","RETENTION","ADVOCACY"]
    try: i=order.index(stage.upper())
    except ValueError: return "DISCOVERY"
    return order[min(i+1,len(order)-1)]

def growth_cta(stage:str, language:str)->tuple[str,str]:
    it=language=="it"
    mapping={
      "DISCOVERY":(("Segui il canale CryptoAID" if it else "Follow the CryptoAID channel"),"https://t.me/cryptoaidsup"),
      "CHANNEL":(("Entra nella community" if it else "Join the community"),"https://t.me/cryptoAIDsupporter"),
      "GROUP":(("Partecipa alla conversazione" if it else "Join the conversation"),"https://t.me/cryptoAIDsupporter"),
      "ENGAGEMENT":(("Scopri CryptoAID" if it else "Discover CryptoAID"),"https://cryptoaid.support"),
      "TRUST":(("Chiedi a CryptoAID" if it else "Ask CryptoAID"),"https://t.me/CryptoAIDsupportBOT"),
      "SERVICE_DISCOVERY":(("Scopri il percorso adatto" if it else "Explore the right path"),"https://cryptoaid.support"),
      "CTA":(("Inizia da qui" if it else "Start here"),"https://cryptoaid.support"),
      "CONVERSION":(("Resta aggiornato" if it else "Stay updated"),"https://t.me/cryptoaidsup"),
      "RETENTION":(("Condividi con la tua community" if it else "Share with your community"),"https://t.me/cryptoaidsup"),
      "ADVOCACY":(("Invita il tuo team" if it else "Invite your team"),"https://t.me/cryptoAIDsupporter"),
    }
    return mapping.get(stage.upper(),mapping["DISCOVERY"])

def weekly_report(metrics:dict)->dict:
    allowed={"posts_published","polls_published","support_requests","moderation_events","new_members","command_usage","campaign_activity","publisher_errors","bot_errors"}
    clean={k:int(v) for k,v in metrics.items() if k in allowed and isinstance(v,(int,float))}
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"metrics":clean,"note":"Only connector/runtime-observed metrics; no inferred vanity metrics."}
