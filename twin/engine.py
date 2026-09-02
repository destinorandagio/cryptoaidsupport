from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Iterable, Mapping

from .contracts import CACHE_STATES, KNOWLEDGE_CONTEXT_CONTRACT, TRUTH_LABELS


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
    cache_state: str = "NOT_APPLICABLE"
    truth_label: str = "DERIVED"

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source is required")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.cache_state not in CACHE_STATES:
            raise ValueError("invalid cache_state")
        if self.truth_label not in TRUTH_LABELS:
            raise ValueError("invalid truth_label")
        if self.truth_label == "LIVE" and self.cache_state != "FRESH":
            raise ValueError("LIVE requires FRESH cache_state/request-time evidence")


@dataclass(frozen=True)
class NumericFact:
    value: int | float
    source: str
    source_date: str
    confidence: float
    cache_state: str
    truth_label: str
    version: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("NumericFact value must be numeric")
        if not self.source.strip() or not self.source_date.strip():
            raise ValueError("numeric facts require source and source_date")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.cache_state not in CACHE_STATES:
            raise ValueError("invalid cache_state")
        if self.truth_label not in TRUTH_LABELS:
            raise ValueError("invalid truth_label")
        if self.truth_label == "LIVE" and self.cache_state != "FRESH":
            raise ValueError("LIVE numeric facts require FRESH evidence")


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
    family_id: str | None = None
    ticker: str | None = None
    facts: dict[str, NumericFact] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def searchable_names(self) -> set[str]:
        values = {self.name, *self.aliases}
        if self.ticker:
            values.add(self.ticker)
        if self.family_id:
            values.add(self.family_id)
        return {normalize_name(x) for x in values if x}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def normalize_address(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"0x[a-f0-9]{40}", value):
        raise ValueError("invalid EVM address")
    return value


def _status(value: str) -> TwinStatus:
    try:
        return TwinStatus(value)
    except ValueError as exc:
        raise ValueError(f"unsupported Twin status: {value}") from exc


class DigitalTwinEngine:
    """Deterministic CHAT03 read model.

    It consumes upstream canon and derived context. It never writes Core truth,
    never creates a competing identity registry, and never promotes an
    unverified context pack to VERIFIED.
    """

    def __init__(self, records: Iterable[TwinRecord] = ()) -> None:
        self._records: dict[str, TwinRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: TwinRecord) -> None:
        if record.twin_id in self._records:
            raise ValueError("duplicate twin_id")
        if record.status == TwinStatus.VERIFIED and not record.provenance:
            raise ValueError("VERIFIED records require provenance")
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
        order = {
            TwinStatus.VERIFIED: 0,
            TwinStatus.SUPPORTED: 1,
            TwinStatus.KNOWN: 2,
            TwinStatus.TO_VERIFY: 3,
            TwinStatus.UNKNOWN: 4,
        }
        return sorted(matches, key=lambda x: (order[x.status], x.name.casefold(), x.twin_id))

    def resolve_one(self, query: str, *, chain_id: int | None = None) -> TwinRecord | None:
        matches = self.resolve(query, chain_id=chain_id)
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError("ambiguous entity; chain/contract disambiguation required")
        return matches[0]

    def search_or_candidate(self, query: str, *, chain_id: int | None = None) -> dict[str, Any]:
        matches = self.resolve(query, chain_id=chain_id)
        if matches:
            return {"state": "MATCH", "results": matches}
        return {
            "state": TwinStatus.TO_VERIFY.value,
            "candidate_status": "USER_SUBMITTED_TO_VERIFY",
            "query": query,
            "chain_id": chain_id,
            "case_available": True,
            "promoted": False,
            "truth_label": "TO_VERIFY",
        }

    def consume_context_pack(self, twin_id: str, pack: Mapping[str, Any]) -> dict[str, Any]:
        """Attach CHAT06 derived context after version/provenance/status checks.

        Context packs may enrich presentation/research context, but cannot
        promote Twin or Core truth. CANDIDATE/UNVERIFIED is always TO_VERIFY.
        """
        if twin_id not in self._records:
            raise KeyError("unknown twin_id")
        required = set(KNOWLEDGE_CONTEXT_CONTRACT["required"])
        missing = required - set(pack)
        if missing:
            raise ValueError(f"context pack missing fields: {sorted(missing)}")
        if pack["status"] not in KNOWLEDGE_CONTEXT_CONTRACT["allowed_status"]:
            raise ValueError("unsupported context pack status")
        if not str(pack["version"]).strip() or not str(pack["pack_id"]).strip():
            raise ValueError("context pack id/version required")
        if not isinstance(pack["provenance"], Mapping) or not pack["provenance"].get("source"):
            raise ValueError("context pack provenance source required")

        record = self._records[twin_id]
        incoming_status = str(pack["status"])
        safe_status = incoming_status
        if incoming_status in {"CANDIDATE", "UNVERIFIED"}:
            safe_status = "TO_VERIFY"
        # VERIFIED context may be shown as verified context only; it does not
        # promote a non-VERIFIED Twin record.
        record.context[str(pack["pack_id"])] = {
            "version": str(pack["version"]),
            "status": safe_status,
            "truth_label": "DERIVED" if safe_status not in {"TO_VERIFY"} else "TO_VERIFY",
            "generated_at": str(pack["generated_at"]),
            "provenance": dict(pack["provenance"]),
            "payload": pack.get("payload", {}),
        }
        return record.context[str(pack["pack_id"])]

    @staticmethod
    def provenance(
        source: str,
        confidence: float,
        version: str,
        *,
        source_date: str | None = None,
        freshness: str = "CURRENT",
        cache_state: str = "NOT_APPLICABLE",
        truth_label: str = "DERIVED",
    ) -> Provenance:
        return Provenance(
            source=source,
            source_date=source_date,
            observed_at=datetime.now(timezone.utc).isoformat(),
            confidence=confidence,
            freshness=freshness,
            version=version,
            cache_state=cache_state,
            truth_label=truth_label,
        )
