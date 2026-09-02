"""Load a user-provided .env into memory and start CryptoAID runtime.

Duplicate variable names are preserved as numbered slots (NAME, NAME_01, ...).
Values are never printed and are not copied into the repository.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_KEYS = {
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "CEREBRAS_API_KEY",
}


def parse_env(path: Path) -> dict[str, str]:
    counts: dict[str, int] = defaultdict(int)
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if key in PROVIDER_KEYS:
            index = counts[key]
            target = key if index == 0 else f"{key}_{index:02d}"
            counts[key] += 1
            result[target] = value
        elif key not in result:
            result[key] = value
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python runtime/run_with_env.py <path-to-apikeys.env>")
    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.is_file():
        raise SystemExit("env_file_not_found")
    env = os.environ.copy()
    env.update(parse_env(path))
    env.setdefault("AI_ENABLED", "true")
    env.setdefault("AI_HTTP_ENABLED", "true")
    configured = sum(1 for k in env if k.startswith(tuple(PROVIDER_KEYS)))
    print(f"runtime: loaded provider secret slots={configured}; values hidden")
    proc = subprocess.run([sys.executable, str(ROOT / "bot" / "runtime_supervisor.py")], cwd=str(ROOT), env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
