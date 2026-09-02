import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from global_knowledge_service import SERVICE


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/knowledge/health":
            return self._json(SERVICE.health())
        if parsed.path == "/knowledge/domains":
            return self._json({"domains": SERVICE.domains()})
        if parsed.path in {"/knowledge/search", "/knowledge/query"}:
            q = (qs.get("q") or [""])[0].strip()
            if not q: return self._json({"error": "missing q"}, 400)
            return self._json(SERVICE.query(q, public_only=True))
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/knowledge/query":
            return self._json({"error": "not found"}, 404)
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 16384)
            payload = json.loads(self.rfile.read(length) or b"{}")
            q = str(payload.get("query", "")).strip()
            if not q: return self._json({"error": "missing query"}, 400)
            return self._json(SERVICE.query(q, public_only=True))
        except (ValueError, json.JSONDecodeError):
            return self._json({"error": "invalid json"}, 400)

    def log_message(self, fmt, *args):
        print("knowledge_api", fmt % args)


def main():
    host = os.getenv("KNOWLEDGE_API_HOST", "127.0.0.1")
    port = int(os.getenv("KNOWLEDGE_API_PORT", "8080"))
    print(f"CryptoAID Knowledge API listening on {host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
