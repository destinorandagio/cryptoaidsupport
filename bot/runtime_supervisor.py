"""Persistent supervisor for CryptoAID Telegram bot.

Runs bot/main.py as a child process and restarts on unexpected exit.
Secrets are inherited from the runtime environment and never printed.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "bot" / "main.py"
STOP = False


def _stop(*_args):
    global STOP
    STOP = True


def validate_env() -> None:
    required = ["TELEGRAM_BOT_TOKEN"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("missing_required_runtime_secrets:" + ",".join(missing))


def main() -> int:
    validate_env()
    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    delay = max(2, int(os.getenv("BOT_RESTART_DELAY_SECONDS", "5")))
    failures = 0
    while not STOP:
        started = time.monotonic()
        print("runtime: starting CryptoAID Telegram bot", flush=True)
        proc = subprocess.Popen([sys.executable, str(BOT)], cwd=str(ROOT), env=os.environ.copy())
        try:
            while proc.poll() is None and not STOP:
                time.sleep(1)
        finally:
            if STOP and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if STOP:
            break
        uptime = time.monotonic() - started
        failures = 0 if uptime >= 300 else failures + 1
        backoff = min(60, delay * max(1, failures))
        print(f"runtime: bot exited code={proc.returncode}; restart_in={backoff}s", flush=True)
        time.sleep(backoff)
    print("runtime: stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
