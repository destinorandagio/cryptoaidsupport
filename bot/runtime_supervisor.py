"""Persistent supervisor for CryptoAID Telegram bot + optional DAPP AI API.

Secrets are inherited from the runtime environment and never printed.
Each child is restarted independently after unexpected exit.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = False


def _stop(*_args):
    global STOP
    STOP = True


def validate_env() -> None:
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        raise RuntimeError("missing_required_runtime_secrets:TELEGRAM_BOT_TOKEN")


def _specs() -> dict[str, Path]:
    specs = {"telegram": ROOT / "bot" / "main.py"}
    if os.getenv("AI_HTTP_ENABLED", "true").lower() == "true":
        specs["ai_api"] = ROOT / "bot" / "api_server.py"
    return specs


def _spawn(name: str, path: Path) -> subprocess.Popen:
    print(f"runtime: starting {name}", flush=True)
    return subprocess.Popen([sys.executable, str(path)], cwd=str(ROOT), env=os.environ.copy())


def main() -> int:
    validate_env()
    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    delay = max(2, int(os.getenv("BOT_RESTART_DELAY_SECONDS", "5")))
    processes = {name: _spawn(name, path) for name, path in _specs().items()}
    failures = {name: 0 for name in processes}

    try:
        while not STOP:
            time.sleep(1)
            for name, proc in list(processes.items()):
                code = proc.poll()
                if code is None:
                    continue
                failures[name] += 1
                backoff = min(60, delay * max(1, failures[name]))
                print(f"runtime: {name} exited code={code}; restart_in={backoff}s", flush=True)
                slept = 0
                while slept < backoff and not STOP:
                    time.sleep(1)
                    slept += 1
                if not STOP:
                    processes[name] = _spawn(name, _specs()[name])
    finally:
        for name, proc in processes.items():
            if proc.poll() is None:
                print(f"runtime: stopping {name}", flush=True)
                proc.terminate()
        deadline = time.monotonic() + 10
        for proc in processes.values():
            if proc.poll() is None:
                try:
                    proc.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    proc.kill()
    print("runtime: stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
