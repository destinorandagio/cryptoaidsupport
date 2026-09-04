from __future__ import annotations

from typing import Any

from .mirror_adapter import minimal_twin_card
from .mirror_registry import MirrorRegistryIndex

SEARCH_RUNTIME_CONTRACT_VERSION = "1.0.0"


class SearchReadFacade:
    """Serializable, fail-closed Search/Twin view for runtime consumers.

    The facade does not create identity, mutate MIRROR, persist a second registry, or
    promote upstream classification. It exposes only the minimum contract required by
    the MVP Search -> Twin/TO_VERIFY -> Case path.
    """

    def __init__(self, index: MirrorRegistryIndex) -> None:
        self.index = index

    def query(self, query: str, *, chain_id: int | None = None) -> dict[str, Any]:
        raw = query.strip()
        if not raw:
            raise ValueError("search query is required")

        matches = self.index.resolve(raw, chain_id=chain_id)
        envelope = {
            "contract_version": SEARCH_RUNTIME_CONTRACT_VERSION,
            "query": raw,
            "chain_id": chain_id,
            "source_version": self.index.source_version,
            "source_sha256": self.index.source_sha256,
            "authority": "READ_ONLY_MIRROR_DERIVED_TWIN_VIEW",
        }

        if not matches:
            return {
                **envelope,
                "state": "TO_VERIFY",
                "result": None,
                "results": [],
                "requires_disambiguation": False,
                "candidate": {
                    "status": "USER_SUBMITTED_TO_VERIFY",
                    "truth_label": "TO_VERIFY",
                    "promoted": False,
                    "case_available": True,
                },
            }

        cards = [minimal_twin_card(record) for record in matches]
        if len(cards) > 1:
            return {
                **envelope,
                "state": "AMBIGUOUS",
                "result": None,
                "results": cards,
                "requires_disambiguation": True,
                "candidate": None,
            }

        return {
            **envelope,
            "state": "MATCH",
            "result": cards[0],
            "results": cards,
            "requires_disambiguation": False,
            "candidate": None,
        }


__all__ = ["SEARCH_RUNTIME_CONTRACT_VERSION", "SearchReadFacade"]
