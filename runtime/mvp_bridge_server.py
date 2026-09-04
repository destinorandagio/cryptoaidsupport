"""Fail-closed same-origin runtime bridge for the CryptoAID 48H MVP.

This is staging/local plumbing, not a second domain authority. Core remains the
SIC-ID/Case authority and Twin remains a read-only MIRROR projection. The
browser never supplies user_id, sic_id, payment economics, Evidence truth or
privileged authorization. Production exposure remains a HUMAN_GATE.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import uuid

from core import CaseEngine, CoreError
from core.api import CORE_API_FACADE_VERSION, CoreAPI
from twin.mirror_registry import MirrorRegistryIndex
from twin.runtime_search import SearchReadFacade

BRIDGE_VERSION = "1.0.0"
COOKIE_SESSION = "caid_session"
COOKIE_CASE = "caid_case"
MAX_BODY = 16_384


class BridgeRejected(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _token(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _cookie_value(header: str | None, name: str) -> str | None:
    if not header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(header)
    except Exception:
        return None
    item = jar.get(name)
    return item.value.strip() if item and item.value.strip() else None


def _safe_static_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if root.name.lower() != "public_html" or not (root / "index.html").is_file():
        raise BridgeRejected("invalid_static_root", 503)
    return root


@dataclass(frozen=True)
class BridgeConfig:
    master_db: Path
    static_root: Path
    sandbox_sic_id: str | None
    cookie_secure: bool = False
    mirror_xlsx: Path | None = None
    mirror_version: str = "MVP-LOCAL"
    mirror_sha256: str | None = None


class MVPBridgeRuntime:
    """Server-trusted adapter used by the packaged public bridge."""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.static_root = _safe_static_root(config.static_root)
        self.core = CoreAPI(config.master_db)
        self.engine: CaseEngine = self.core.engine
        self.search_facade: SearchReadFacade | None = None
        if config.mirror_xlsx:
            path = Path(config.mirror_xlsx).expanduser().resolve()
            if not path.is_file():
                raise BridgeRejected("mirror_source_missing", 503)
            index = MirrorRegistryIndex.from_xlsx(
                path,
                source_version=config.mirror_version,
                expected_sha256=config.mirror_sha256,
            )
            self.search_facade = SearchReadFacade(index)

    def _principal(self, session_id: str | None) -> dict:
        if not session_id:
            raise BridgeRejected("session_required", 401)
        with self.engine.conn() as connection:
            row = connection.execute(
                "SELECT u.sic_id FROM core_sessions s JOIN core_users u ON u.user_id=s.user_id WHERE s.session_id=?",
                (session_id,),
            ).fetchone()
        if not row:
            raise BridgeRejected("session_required", 401)
        try:
            return self.core.resume_session(session_id=session_id, sic_id=row["sic_id"])
        except CoreError as exc:
            raise BridgeRejected("session_required", getattr(exc, "status", 401) or 401) from exc

    def login_sandbox(self, payload: dict) -> dict:
        if any(key in payload for key in ("sic_id", "sicId", "user_id", "userId", "session_id", "wallet")):
            raise BridgeRejected("caller_identity_forbidden", 400)
        if payload.get("action") != "LOGIN_OR_RESUME":
            raise BridgeRejected("invalid_login_action", 400)
        sic_id = (self.config.sandbox_sic_id or "").strip()
        if not sic_id:
            raise BridgeRejected("sandbox_identity_not_configured", 503)
        user = self.engine.register_user(sic_id, {"source": "MVP_SANDBOX_SERVER"}, _token("regidem"), _token("regreq"))
        session = self.engine.create_session(user["user_id"], sic_id, _token("sesreq"), _token("sesidem"), 3600)
        return session

    def session_projection(self, session_id: str | None, case_id: str | None = None) -> dict:
        principal = self._principal(session_id)
        state = {
            "bridgeVersion": BRIDGE_VERSION,
            "coreApiVersion": CORE_API_FACADE_VERSION,
            "sicId": principal["sic_id"],
            "identityDataState": "LIVE",
            "dataState": "LIVE",
        }
        if case_id:
            try:
                case = self.core.resume_case(session_id=principal["session_id"], sic_id=principal["sic_id"], case_id=case_id)
                state.update({
                    "caseId": case["case_id"],
                    "caseDataState": "LIVE",
                    "timeline": [
                        {"label": item.get("reason") or item.get("new_state") or "Case update", "dataState": "LIVE"}
                        for item in self.core.timeline(session_id=principal["session_id"], sic_id=principal["sic_id"], case_id=case_id)[-8:]
                    ],
                    "nextAction": self._next_action(principal, case_id),
                })
            except (CoreError, BridgeRejected):
                pass
        return state

    def _next_action(self, principal: dict, case_id: str) -> dict | None:
        raw = self.core.next_action(session_id=principal["session_id"], sic_id=principal["sic_id"], case_id=case_id)
        if not raw:
            return None
        return {
            "title": raw.get("title") or "Next recovery action",
            "description": "Open the Case to continue with the next authorized recovery step.",
            "cta": raw.get("next_action") or "REVIEW ACTION",
            "route": "recovery",
        }

    def search(self, session_id: str | None, query: str) -> dict:
        self._principal(session_id)
        raw = query.strip()
        if not raw:
            raise BridgeRejected("search_query_required", 400)
        if self.search_facade is None:
            return {
                "contract_version": "1.0.0",
                "query": raw,
                "chain_id": 137,
                "authority": "READ_ONLY_MIRROR_DERIVED_TWIN_VIEW",
                "state": "TO_VERIFY",
                "result": None,
                "results": [],
                "requires_disambiguation": False,
                "candidate": {"status": "USER_SUBMITTED_TO_VERIFY", "truth_label": "TO_VERIFY", "promoted": False, "case_available": True},
            }
        return self.search_facade.query(raw, chain_id=137)

    def create_case(self, session_id: str | None, payload: dict) -> dict:
        if any(key in payload for key in ("sic_id", "sicId", "user_id", "userId", "authorization", "payment", "entitlement")):
            raise BridgeRejected("caller_authority_forbidden", 400)
        principal = self._principal(session_id)
        project_query = str(payload.get("projectQuery", "")).strip()[:500]
        request_id = str(payload.get("requestId", "")).strip()
        idempotency_key = str(payload.get("idempotencyKey", "")).strip()
        if not request_id or not idempotency_key:
            raise BridgeRejected("mutation_metadata_required", 400)
        search_result = self.search(principal["session_id"], project_query) if project_query else {"state": "TO_VERIFY"}
        search_hit = search_result.get("state") == "MATCH" and isinstance(search_result.get("result"), dict)
        project_ref = None
        if search_hit:
            result = search_result["result"]
            project_ref = str(result.get("twin_id") or result.get("sic_id") or project_query)[:500]
        elif project_query:
            project_ref = project_query
        case = self.core.create_case(
            session_id=principal["session_id"],
            sic_id=principal["sic_id"],
            wallet=None,
            project_ref=project_ref,
            search_hit=bool(search_hit),
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        return {**self.session_projection(principal["session_id"], case["case_id"]), "caseId": case["case_id"], "caseDataState": "LIVE"}


class Handler(SimpleHTTPRequestHandler):
    server_version = "CryptoAID-MVP-Bridge/1.0"
    runtime: MVPBridgeRuntime

    def __init__(self, *args, runtime: MVPBridgeRuntime, **kwargs):
        self.runtime = runtime
        super().__init__(*args, directory=str(runtime.static_root), **kwargs)

    def log_message(self, fmt, *args):
        print("mvp-bridge:", fmt % args)

    def _session(self) -> str | None:
        return _cookie_value(self.headers.get("Cookie"), COOKIE_SESSION)

    def _case(self) -> str | None:
        return _cookie_value(self.headers.get("Cookie"), COOKIE_CASE)

    def _json(self, status: int, payload: dict, cookies: list[str] | None = None):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cookie(self, name: str, value: str, max_age: int = 3600) -> str:
        secure = "; Secure" if self.runtime.config.cookie_secure else ""
        return f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict{secure}"

    def _payload(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                raise BridgeRejected("invalid_body_size", 400)
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BridgeRejected("invalid_json", 400) from exc
        if not isinstance(value, dict):
            raise BridgeRejected("invalid_json", 400)
        return value

    def _failure(self, exc: Exception):
        if isinstance(exc, BridgeRejected):
            self._json(exc.status, {"error": exc.code})
        elif isinstance(exc, CoreError):
            self._json(getattr(exc, "status", 400) or 400, {"error": getattr(exc, "code", "core_rejected")})
        else:
            self._json(503, {"error": "runtime_unavailable"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/mvp/"):
            return super().do_GET()
        try:
            if parsed.path == "/api/mvp/health":
                self._json(200, {"status": "ok", "bridgeVersion": BRIDGE_VERSION, "coreApiVersion": CORE_API_FACADE_VERSION, "productionDeployPerformed": False})
                return
            if parsed.path == "/api/mvp/session":
                self._json(200, self.runtime.session_projection(self._session(), self._case()))
                return
            if parsed.path == "/api/mvp/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                self._json(200, self.runtime.search(self._session(), query))
                return
            raise BridgeRejected("not_found", 404)
        except Exception as exc:
            self._failure(exc)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/mvp/session":
                session = self.runtime.login_sandbox(self._payload())
                projection = self.runtime.session_projection(session["session_id"])
                self._json(200, projection, [self._cookie(COOKIE_SESSION, session["session_id"])])
                return
            if parsed.path == "/api/mvp/cases":
                result = self.runtime.create_case(self._session(), self._payload())
                self._json(201, result, [self._cookie(COOKIE_CASE, result["caseId"], 86400)])
                return
            raise BridgeRejected("not_found", 404)
        except Exception as exc:
            self._failure(exc)


def config_from_env() -> BridgeConfig:
    repo = Path(__file__).resolve().parents[1]
    static_root = Path(os.getenv("CAID_STATIC_ROOT", repo / "frontend" / "public_html"))
    db_value = os.getenv("CAID_MASTER_DB", "").strip()
    if not db_value:
        raise BridgeRejected("CAID_MASTER_DB_required", 503)
    if os.getenv("CAID_MVP_MODE", "").strip().lower() != "sandbox":
        raise BridgeRejected("sandbox_mode_required", 503)
    mirror = os.getenv("CAID_MIRROR_XLSX", "").strip()
    return BridgeConfig(
        master_db=Path(db_value),
        static_root=static_root,
        sandbox_sic_id=os.getenv("CAID_MVP_SANDBOX_SIC_ID"),
        cookie_secure=os.getenv("CAID_MVP_COOKIE_SECURE", "0") == "1",
        mirror_xlsx=Path(mirror) if mirror else None,
        mirror_version=os.getenv("CAID_MIRROR_VERSION", "MVP-LOCAL"),
        mirror_sha256=os.getenv("CAID_MIRROR_SHA256") or None,
    )


def main():
    runtime = MVPBridgeRuntime(config_from_env())
    host = os.getenv("CAID_MVP_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"} and os.getenv("CAID_MVP_ALLOW_NONLOOPBACK") != "1":
        raise SystemExit("non-loopback bind requires explicit human-gated CAID_MVP_ALLOW_NONLOOPBACK=1")
    port = int(os.getenv("CAID_MVP_PORT", "8788"))
    server = ThreadingHTTPServer((host, port), partial(Handler, runtime=runtime))
    print(f"mvp-bridge: listening on {host}:{port}; sandbox only; no deploy/sign/tx performed")
    server.serve_forever()


if __name__ == "__main__":
    main()
