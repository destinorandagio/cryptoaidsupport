"""Minimal server-side HTTP API for CryptoAID AI assistant.

Endpoints:
- GET /health
- POST /api/ai/assistant {message, language?}

No provider key is ever returned to clients.
"""
from __future__ import annotations

import asyncio
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from bot.ai_gateway import provider_inventory
from bot.ai_service import answer_user

HOST = os.getenv("AI_HTTP_HOST", "127.0.0.1")
PORT = int(os.getenv("AI_HTTP_PORT", "8787"))
MAX_BODY = int(os.getenv("AI_HTTP_MAX_BODY", "16384"))
ALLOWED_ORIGIN = os.getenv("AI_CORS_ORIGIN", "")


def validate_payload(payload: dict) -> tuple[str, str | None]:
    message = str(payload.get("message", "")).strip()
    language = payload.get("language")
    if not message or len(message) > 6000:
        raise ValueError("invalid_message")
    if language not in (None, "it", "en"):
        raise ValueError("invalid_language")
    return message, language


class Handler(BaseHTTPRequestHandler):
    server_version = "CryptoAID-AI/1.0"

    def log_message(self, fmt, *args):
        # Do not log request bodies or secrets.
        print("api:", fmt % args)

    def _headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Vary", "Origin")
        self.end_headers()

    def _json(self, status: int, payload: dict):
        self._headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if urlparse(self.path).path != "/health":
            self._json(404, {"error": "not_found"})
            return
        self._json(200, {
            "status": "ok",
            "service": "cryptoaid-ai",
            "providers": provider_inventory(),
        })

    def do_OPTIONS(self):
        self.send_response(204)
        if ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/api/ai/assistant":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                raise ValueError("invalid_body_size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            message, language = validate_payload(payload)
            result = asyncio.run(answer_user(message, language))
            self._json(200, result.to_dict())
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc) or "bad_request"})
        except Exception:
            self._json(503, {"error": "assistant_temporarily_unavailable"})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"api: listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
