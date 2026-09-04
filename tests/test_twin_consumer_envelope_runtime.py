import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public_html"
BRIDGE = (PUBLIC / "assets" / "runtime-bridge.js").read_text()
APP = (PUBLIC / "assets" / "app.js").read_text()


def consume(payload: dict) -> dict:
    node = shutil.which("node")
    assert node, "Node.js is required for executable Twin consumer contract coverage"
    adapt = next(line for line in BRIDGE.splitlines() if line.startswith("const adaptTwinEnvelope="))
    normalize = next(line for line in APP.splitlines() if line.startswith("function normalizeTwinResult("))
    script = (
        f"{adapt}\n{normalize}\n"
        "const raw=JSON.parse(process.argv[1]);"
        "process.stdout.write(JSON.stringify(normalizeTwinResult(adaptTwinEnvelope(raw))));"
    )
    completed = subprocess.run(
        [node, "-e", script, json.dumps(payload, separators=(",", ":"))],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_actual_match_envelope_reaches_app_with_flat_provenance_preserved():
    consumed = consume(
        {
            "state": "MATCH",
            "result": {
                "name": "Example Twin",
                "summary": "Canonical match",
                "source": "registry-A",
                "source_date": "2026-09-02",
                "confidence": 0.91,
                "cache_state": "LIVE",
                "truth_label": "LIVE",
                "version": "1.0.0",
            },
        }
    )
    assert consumed["match"] is True
    assert consumed["name"] == "Example Twin"
    assert consumed["dataState"] == "LIVE"
    assert consumed["provenance"] == [
        {
            "source": "registry-A",
            "source_date": "2026-09-02",
            "confidence": 0.91,
            "cache_state": "LIVE",
            "truth_label": "LIVE",
            "version": "1.0.0",
        }
    ]


def test_actual_ambiguous_envelope_reaches_app_as_explicit_disambiguation():
    consumed = consume(
        {
            "state": "AMBIGUOUS",
            "result": None,
            "results": [{"name": "A"}, {"name": "B"}],
            "requires_disambiguation": True,
        }
    )
    assert consumed["ambiguous"] is True
    assert consumed["state"] == "AMBIGUOUS"
    assert consumed["requires_disambiguation"] is True
    assert consumed.get("match") is not True
