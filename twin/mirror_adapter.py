from __future__ import annotations

import re
from typing import Any, Mapping

from .contracts import POLYGON_CHAIN_ID
from .engine import DigitalTwinEngine, TwinRecord, TwinStatus

_MIRROR_SOURCE_KEY = "mirror81"
_CONFIDENCE_BY_GRADE = {"A": 0.90, "B": 0.75, "C": 0.55}

def _text(row: Mapping[str, Any], key: str) -> str:
    value=row.get(key); return "" if value is None else str(value).strip()
def _aliases(value: str) -> set[str]: return {part.strip() for part in value.split("|") if part.strip()}
def _contracts(value: str) -> set[str]: return {m.lower() for m in re.findall(r"0x[a-fA-F0-9]{40}", value)}
def _polygon_chain_id(primary: str, chains: str) -> int | None:
    p=primary.casefold().strip(); cs={x.casefold().strip() for x in chains.split("|") if x.strip()}
    return POLYGON_CHAIN_ID if p=="polygon" or (not p and cs=={"polygon"}) else None

def adapt_mirror_row(row: Mapping[str, Any], *, source_version: str) -> TwinRecord:
    twin_id=_text(row,"ID MIRROR81+"); name=_text(row,"Nome canonico")
    if not twin_id or not name or not source_version.strip(): raise ValueError("MIRROR row requires canonical id, name and source version")
    source_date=_text(row,"Data acquisizione") or _text(row,"Ultimo aggiornamento fonte")
    if not source_date: raise ValueError("MIRROR row requires a source/acquisition date")
    grade=_text(row,"Attendibilità").upper(); confidence=_CONFIDENCE_BY_GRADE.get(grade,0.50); coverage=_text(row,"Copertura fonti") or "MIRROR81 registry"
    provenance=DigitalTwinEngine.provenance(source=f"MIRROR81:{coverage}",confidence=confidence,version=source_version,source_date=source_date,freshness="HISTORICAL_SNAPSHOT",cache_state="STALE",truth_label="CACHED")
    record=TwinRecord(twin_id=twin_id,name=name,aliases=_aliases(_text(row,"Alias / versioni")),chain_id=_polygon_chain_id(_text(row,"Chain primaria"),_text(row,"Chain")),contracts=_contracts(_text(row,"Contratti / indirizzi")),status=TwinStatus.KNOWN,provenance=[provenance],ticker=_text(row,"Token") or None)
    record.context[_MIRROR_SOURCE_KEY]={"source_status":_text(row,"Stato prudenziale") or "STATUS_UNVERIFIED","category":_text(row,"Categoria") or None,"chains":_text(row,"Chain") or None,"primary_chain":_text(row,"Chain primaria") or None,"website":_text(row,"Sito ufficiale") or None,"source_coverage":coverage,"reliability_grade":grade or None,"read_only_source":True}
    return record

def minimal_twin_card(record: TwinRecord) -> dict[str, Any]:
    if not record.provenance: raise ValueError("minimal Twin card requires provenance")
    p=record.provenance[0]; mirror=record.context.get(_MIRROR_SOURCE_KEY,{})
    return {"twin_id":record.twin_id,"name":record.name,"status":record.status.value,"chain_id":record.chain_id,"source_status":mirror.get("source_status"),"source":p.source,"source_date":p.source_date,"confidence":p.confidence,"cache_state":p.cache_state,"truth_label":p.truth_label,"version":p.version,"case_available":True}
