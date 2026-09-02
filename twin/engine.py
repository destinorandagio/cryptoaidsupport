from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Iterable


class TwinStatus(str, Enum):
    KNOWN = "KNOWN"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    TO_VERIFY = "TO_VERIFY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Provenance:
    source: str
    source_date: str | None
    observed_at: str
    confidence: float
    freshness: str
    version: str


@dataclass
class TwinRecord:
    twin_id: str
    name: str
    aliases: set[str] = field(default_factory=set)
    chain_id: int | None = None
    contracts: set[str] = field(default_factory=set)
    status: TwinStatus = TwinStatus.KNOWN
    provenance: list[Provenance] = field(default_factory=list)
    successor_twin_id: str | None = None

    def searchable_names(self) -> set[str]:
        return {normalize_name(self.name), *(normalize_name(x) for x in self.aliases)}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def normalize_address(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"0x[a-f0-9]{40}", value):
        raise ValueError("invalid EVM address")
    return value


class DigitalTwinEngine:
    """Deterministic read model. It never promotes candidates to VERIFIED itself."""

    def __init__(self, records: Iterable[TwinRecord] = ()) -> None:
        self._records: dict[str, TwinRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: TwinRecord) -> None:
        if record.twin_id in self._records:
            raise ValueError("duplicate twin_id")
        record.contracts = {normalize_address(x) for x in record.contracts}
        self._records[record.twin_id] = record

    def resolve(self, query: str, *, chain_id: int | None = None) -> list[TwinRecord]:
        q = query.strip()
        address = None
        try:
            address = normalize_address(q)
        except ValueError:
            pass
        nq = normalize_name(q)
        matches: list[TwinRecord] = []
        for record in self._records.values():
            if chain_id is not None and record.chain_id not in (None, chain_id):
                continue
            hit = address in record.contracts if address else nq in record.searchable_names()
            if hit:
                matches.append(record)
        return sorted(matches, key=lambda x: (x.status != TwinStatus.VERIFIED, x.name.casefold(), x.twin_id))

    def resolve_one(self, query: str, *, chain_id: int | None = None) -> TwinRecord | None:
        matches = self.resolve(query, chain_id=chain_id)
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError("ambiguous entity; chain/contract disambiguation required")
        return matches[0]

    def search_or_candidate(self, query: str, *, chain_id: int | None = None) -> dict:
        matches = self.resolve(query, chain_id=chain_id)
        if matches:
            return {"state": "MATCH", "results": matches}
        return {
            "state": TwinStatus.TO_VERIFY.value,
            "query": query,
            "chain_id": chain_id,
            "case_available": True,
            "promoted": False,
        }

    @staticmethod
    def provenance(source: str, confidence: float, version: str, *, source_date: str | None = None, freshness: str = "CURRENT") -> Provenance:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return Provenance(
            source=source,
            source_date=source_date,
            observed_at=datetime.now(timezone.utc).isoformat(),
            confidence=confidence,
            freshness=freshness,
            version=version,
        )
