import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "knowledge" / "global" / "KNOWLEDGE_GLOBAL_MANIFEST.json"

PUBLIC_ALLOW = {"VERIFIED_PRIMARY_SOURCE", "VERIFIED", "HIGH_CONFIDENCE"}
PUBLIC_LABEL = {"ANALYSIS"}


@dataclass
class KnowledgeResult:
    domain: str
    path: str
    score: float
    status: str
    data: Any


def _load(path: Path):
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9àèéìòù_-]+", text.lower()) if len(x) > 2}


def _flatten(value: Any) -> str:
    if isinstance(value, str): return value
    if isinstance(value, dict): return " ".join(f"{k} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, list): return " ".join(_flatten(v) for v in value)
    return str(value)


def _status(data: Any) -> str:
    if isinstance(data, dict):
        raw = data.get("classification") or data.get("status") or data.get("verification_level")
        if isinstance(raw, str): return raw.upper()
    return "VERIFIED"


class GlobalKnowledgeService:
    def __init__(self):
        self.manifest = _load(MANIFEST)
        self.documents = []
        for item in sorted(self.manifest["domains"], key=lambda x: x.get("priority", 0), reverse=True):
            path = ROOT / item["path"]
            if path.exists():
                data = _load(path)
                self.documents.append({"domain": item["id"], "path": item["path"], "priority": item.get("priority", 0), "data": data})

    def health(self) -> dict:
        expected = len(self.manifest["domains"])
        loaded = len(self.documents)
        return {"ok": loaded > 0, "loaded_domains": loaded, "configured_domains": expected, "missing_domains": expected - loaded}

    def domains(self) -> list[dict]:
        return [{"domain": x["domain"], "path": x["path"], "priority": x["priority"]} for x in self.documents]

    def search(self, query: str, public_only: bool = True, limit: int = 5) -> list[KnowledgeResult]:
        q = _tokens(query)
        ranked = []
        for doc in self.documents:
            text = _flatten(doc["data"])
            words = _tokens(text)
            overlap = len(q & words)
            if not overlap: continue
            score = overlap / max(1, len(q)) + (doc["priority"] / 10000)
            status = _status(doc["data"])
            if public_only and status not in PUBLIC_ALLOW | PUBLIC_LABEL:
                continue
            ranked.append(KnowledgeResult(doc["domain"], doc["path"], score, status, doc["data"]))
        return sorted(ranked, key=lambda r: r.score, reverse=True)[:limit]

    def query(self, query: str, public_only: bool = True) -> dict:
        results = self.search(query, public_only=public_only, limit=3)
        if not results:
            return {"found": False, "answer_policy": "ESCALATE_OR_REQUEST_MORE_CONTEXT", "results": []}
        return {
            "found": True,
            "answer_policy": "ANSWER_WITH_EVIDENCE_STATUS",
            "results": [
                {"domain": r.domain, "source_path": r.path, "score": round(r.score, 4), "status": r.status, "data": r.data}
                for r in results
            ]
        }


SERVICE = GlobalKnowledgeService()
