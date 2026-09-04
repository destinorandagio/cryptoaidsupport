from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import uuid
from typing import Any, Iterable, Mapping
from .contracts import POLYGON_CHAIN_ID
from .engine import normalize_address

@dataclass(frozen=True)
class ProviderCandidate:
    uuid: str; name: str; rdns: str; provider_id: str; source: str="EIP6963"
    def __post_init__(self) -> None:
        try: parsed=uuid.UUID(self.uuid)
        except (ValueError,AttributeError) as exc: raise ValueError("provider uuid must be UUID") from exc
        if parsed.version != 4: raise ValueError("provider uuid must be UUIDv4")
        if not self.name.strip() or not self.provider_id.strip(): raise ValueError("provider name/provider_id required")
        if self.rdns and not re.fullmatch(r"[A-Za-z0-9.-]+",self.rdns): raise ValueError("invalid rdns display metadata")

def select_provider(candidates: Iterable[ProviderCandidate], selected_uuid: str) -> ProviderCandidate:
    if not selected_uuid: raise ValueError("explicit provider selection required")
    seen=set(); selected=None
    for candidate in candidates:
        if candidate.uuid in seen: raise ValueError("duplicate provider uuid")
        seen.add(candidate.uuid)
        if candidate.uuid==selected_uuid: selected=candidate
    if selected is None: raise ValueError("selected provider not available")
    return selected

def parse_chain_id(value: int | str) -> int:
    if isinstance(value,bool): raise ValueError("invalid chain id")
    if isinstance(value,int): chain_id=value
    elif isinstance(value,str):
        raw=value.strip().lower(); base=16 if raw.startswith("0x") else 10
        try: chain_id=int(raw,base)
        except ValueError as exc: raise ValueError("invalid chain id") from exc
    else: raise ValueError("invalid chain id")
    if chain_id<=0: raise ValueError("invalid chain id")
    return chain_id

@dataclass
class WalletSession:
    sic_id: str; provider_uuid: str; provider_id: str; account: str|None=None; chain_id: int|None=None; active: bool=False; needs_revalidation: bool=True; authenticated: bool=False
    def bind(self, account: str, chain_id: int|str) -> None:
        normalized=normalize_address(account); parsed=parse_chain_id(chain_id)
        if parsed!=POLYGON_CHAIN_ID:
            self.account=normalized; self.chain_id=parsed; self.active=False; self.needs_revalidation=True; raise ValueError("wrong chain; Polygon 137 required")
        self.account=normalized; self.chain_id=parsed; self.active=True; self.needs_revalidation=False; self.authenticated=False
    def on_event(self,event: str,payload: Any=None)->None:
        if event=="disconnect": self.active=False; self.needs_revalidation=True; return
        if event=="connect": self.active=False; self.needs_revalidation=True; self.authenticated=False; return
        if event=="accountsChanged":
            accounts=list(payload or [])
            if not accounts: self.account=None; self.active=False; self.needs_revalidation=True; return
            new=normalize_address(str(accounts[0]))
            if self.account!=new: self.account=new; self.active=False; self.needs_revalidation=True
            return
        if event=="chainChanged": self.chain_id=parse_chain_id(payload); self.active=False; self.needs_revalidation=True; return
        raise ValueError("unsupported wallet event")

_REQUIRED_RPC_FIELDS={"provider_id","observed_at","latency_ms","chain_id","result","source"}
def _parse_observed_at(value: str)->datetime:
    try: parsed=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("invalid observed_at") from exc
    if parsed.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)
def validate_rpc_observation(observation: Mapping[str,Any],*,now:datetime|None=None,max_age_seconds:int=60)->dict[str,Any]:
    missing=_REQUIRED_RPC_FIELDS-set(observation)
    if missing: raise ValueError(f"rpc observation missing fields: {sorted(missing)}")
    if not str(observation["provider_id"]).strip() or not str(observation["source"]).strip(): raise ValueError("rpc provider/source required")
    latency=observation["latency_ms"]
    if isinstance(latency,bool) or not isinstance(latency,(int,float)) or latency<0: raise ValueError("invalid latency_ms")
    chain_id=parse_chain_id(observation["chain_id"]); observed=_parse_observed_at(str(observation["observed_at"])); current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc); age=(current-observed).total_seconds()
    if age < -5: raise ValueError("rpc observation timestamp is in the future")
    success=observation["result"]
    if not isinstance(success,bool): raise ValueError("rpc result must be boolean")
    if chain_id!=POLYGON_CHAIN_ID or not success: return {"provider_id":str(observation["provider_id"]),"chain_id":chain_id,"truth_label":"TO_VERIFY","cache_state":"BYPASS","usable":False,"reason":"WRONG_CHAIN" if chain_id!=POLYGON_CHAIN_ID else "RPC_FAILURE"}
    if age>max_age_seconds: return {"provider_id":str(observation["provider_id"]),"chain_id":chain_id,"truth_label":"CACHED","cache_state":"STALE","usable":False,"reason":"STALE_OBSERVATION"}
    return {"provider_id":str(observation["provider_id"]),"chain_id":chain_id,"truth_label":"LIVE","cache_state":"FRESH","usable":True,"reason":"REQUEST_TIME_POLYGON_HEALTH_VERIFIED"}
