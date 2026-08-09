"""Runnable entry point for the unified InkStatute Gateway.

Usage:
    python -m gateway [--host 127.0.0.1] [--port 8000]

Environment:
    INKSTATUTE_GATEWAY_ENABLED (required — must be "true"/"1"/"yes")
    GATEWAY_BIND_HOST (default 127.0.0.1)
    GATEWAY_BIND_PORT (default 8000)
    GATEWAY_STATIC_TOKEN (default: auto-generated per start when rbac off)
    GATEWAY_RBAC_ENABLED (default false)
    GATEWAY_RBAC_SECRET (required when rbac enabled)
    GATEWAY_DEFAULT_TENANT_ID (default "default")
    GATEWAY_BACKEND (default "fake" — one of "fake" | "acp" | "hermes")
        "fake" — in-memory FakeRunRuntime (no real agent; sessions/runs
                 endpoints work but create_run returns fixture events)
        "acp"  — ACPBackendAdapter spawning ``inkstatute-agent acp``
                 (requires inkstatute-agent on PATH; uses agent-core)
        "hermes" — ACPBackendAdapter spawning ``hermes acp``
                 (requires hermes on PATH + HERMES_HOME)
    INKSTATUTE_GATEWAY_HERMES_HOME (for backend=hermes)

The Gateway is the single client-facing HTTP+SSE entry point. Auth
(static token or RBAC session) is enforced BEFORE routing — no bypass.
The login endpoint is the only route that bypasses require_auth.

Stream routes (``GET /v1/runs/{run_id}/events``) are handled via the
``app.stream()`` async generator; all other routes go through
``app.dispatch()``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

# Add repo source roots so the service can run before package installation.
# parents[4] is the repository root for services/<service>/src/<module>/__main__.py.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SERVICE_ROOT = Path(__file__).resolve().parents[2] / "src"
for _root in (
    _SERVICE_ROOT,
    _REPO_ROOT / "packages" / "platform-contract" / "src",
    _REPO_ROOT / "packages" / "platform-runtime" / "src",
    _REPO_ROOT / "packages" / "acp-client" / "src",
    _REPO_ROOT / "packages" / "agent-core" / "src",
    _REPO_ROOT / "packages" / "rbac" / "src",
    _REPO_ROOT / "packages" / "channel-core" / "src",
    _REPO_ROOT / "packages" / "operator-config" / "src",
    _REPO_ROOT / "packages" / "practice-profile" / "src",
):
    _path = str(_root)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from gateway.app import GatewayApp, GatewayError
from gateway.artifacts import GatewayArtifactStore
from gateway.auth import GatewayAuth, GatewayAuthError
from gateway.config import GatewayConfig
from gateway.event_buffer import RunEventBuffer
from gateway.login import GatewayLoginHandler
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from platform_runtime.feature_flags import RuntimeFeatureFlags

from rbac.session import InMemorySessionStore


# ---------------------------------------------------------------------------
# Backend factories
# ---------------------------------------------------------------------------


def _build_fake_runtime() -> Any:
    """Build an in-memory FakeRunRuntime (no real agent backend).

    This is the default when no backend is configured. It lets the Gateway
    boot and respond to session/run/list endpoints, but ``create_run``
    returns fixture events (no real LLM calls). Useful for local dev,
    smoke-testing the desktop app's chat flow, and verifying wiring.
    """
    # Lazy import to avoid pulling test-only deps into production path.
    # The FakeRunRuntime pattern mirrors services/gateway/tests/test_integration.py.
    from platform_contract.enums import AsyncTaskState
    from platform_runtime.protocols import Run, RunEvent, RunRequest
    from typing import AsyncIterator

    class _FakeRunRuntime:
        def __init__(self) -> None:
            self.runs: dict[str, Run] = {}
            self.events: dict[str, list[RunEvent]] = {}
            self._next_id = 1
            self._streamed: set[str] = set()

        async def create_run(self, req: RunRequest) -> Run:
            run_id = f"run-{self._next_id:03d}"
            self._next_id += 1
            run = Run(
                run_id=run_id,
                status=AsyncTaskState.QUEUED,
                turn_id=req.turn.turn_id,
                solution_id=req.solution.solution_id,
                metadata=dict(req.metadata),
            )
            self.runs[run_id] = run
            self.events[run_id] = [
                RunEvent(
                    event_id=f"evt-{run_id}-1",
                    run_id=run_id,
                    event_type="message.delta",
                    occurred_at="2026-01-01T00:00:00Z",
                    seq=1,
                    payload={"message_delta": "[fake backend] Gateway is running with backend=fake. Set GATEWAY_BACKEND=acp or hermes for real agent runs."},
                    metadata={},
                ),
                RunEvent(
                    event_id=f"evt-{run_id}-2",
                    run_id=run_id,
                    event_type="message.completed",
                    occurred_at="2026-01-01T00:00:01Z",
                    seq=2,
                    payload={"message_completed": {"text": "[fake backend] done"}},
                    metadata={},
                ),
            ]
            return run

        async def poll(self, run_id: str) -> Run:
            return self.runs.get(run_id, Run(
                run_id=run_id, status=AsyncTaskState.FAILED,
                turn_id="", solution_id="",
            ))

        async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
            if run_id in self._streamed:
                return
            self._streamed.add(run_id)
            for event in self.events.get(run_id, []):
                yield event

        async def cancel(self, run_id: str) -> Run:
            run = self.runs.get(run_id)
            if run is not None:
                run = Run(
                    run_id=run.run_id, status=AsyncTaskState.CANCELLED,
                    turn_id=run.turn_id, solution_id=run.solution_id,
                    metadata=run.metadata,
                )
                self.runs[run_id] = run
            return run  # type: ignore[return-value]

        async def approve(self, run_id: str, approval: object) -> Run:
            return self.runs.get(run_id, Run(
                run_id=run_id, status=AsyncTaskState.FAILED,
                turn_id="", solution_id="",
            ))

    return _FakeRunRuntime()


def _build_acp_runtime() -> Any:
    """Build a DefaultRunRuntime backed by ACPBackendAdapter (inkstatute-agent).

    Spawns ``inkstatute-agent acp`` as a per-session subprocess. Requires
    the ``inkstatute-agent`` CLI on PATH (install agent-core: ``pip install
    -e packages/agent-core``).
    """
    from platform_runtime.runtime import DefaultRunRuntime
    from inkstatute_acp_client.adapter import ACPBackendAdapter, ACPBackendConfig
    from inkstatute_acp_client.process_mode import BackendProcessMode

    config = ACPBackendConfig(
        backend_id="inkstatute",
        command=("inkstatute-agent", "acp"),
        process_mode=BackendProcessMode.PER_SESSION,
        timeout_seconds=300.0,
    )
    backend = ACPBackendAdapter(config)
    flags = RuntimeFeatureFlags.from_env(os.environ)
    return DefaultRunRuntime(backend=backend, feature_flags=flags)


def _build_hermes_runtime(hermes_home: str) -> Any:
    """Build a DefaultRunRuntime backed by ACPBackendAdapter (hermes acp)."""
    from platform_runtime.runtime import DefaultRunRuntime
    from inkstatute_acp_client.adapter import create_hermes_adapter

    backend = create_hermes_adapter(hermes_home=hermes_home)
    flags = RuntimeFeatureFlags.from_env(os.environ)
    return DefaultRunRuntime(backend=backend, feature_flags=flags)


def _build_runtime(env: Mapping[str, str]) -> Any:
    backend = env.get("GATEWAY_BACKEND", "fake").strip().lower()
    if backend == "acp":
        print("gateway: backend=acp (inkstatute-agent acp subprocess)", flush=True)
        return _build_acp_runtime()
    if backend == "hermes":
        hermes_home = env.get("INKSTATUTE_GATEWAY_HERMES_HOME", "")
        if not hermes_home:
            raise SystemExit(
                "GATEWAY_BACKEND=hermes requires INKSTATUTE_GATEWAY_HERMES_HOME "
                "(path to Hermes home directory)"
            )
        print(f"gateway: backend=hermes (hermes acp, HERMES_HOME={hermes_home})", flush=True)
        return _build_hermes_runtime(hermes_home)
    print("gateway: backend=fake (in-memory, no real agent — set GATEWAY_BACKEND=acp or hermes for real runs)", flush=True)
    return _build_fake_runtime()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    env: Mapping[str, str] | None = None,
    *,
    runtime: Any | None = None,
) -> tuple[GatewayApp, GatewayConfig, str]:
    """Build a configured :class:`GatewayApp` + its config + the static token.

    Returns ``(app, config, static_token)``. When no static token is
    configured and RBAC is off, a per-start token is auto-generated and
    printed so the desktop app can use it.
    """
    import secrets as _secrets

    source: Mapping[str, str] = env if env is not None else os.environ
    config = GatewayConfig.from_env(source)
    if not config.enabled:
        raise SystemExit(
            "Gateway is disabled. Set INKSTATUTE_GATEWAY_ENABLED=true to start."
        )

    rbac_enabled = source.get("GATEWAY_RBAC_ENABLED", "").lower() in {"1", "true", "yes"}
    rbac_secret = source.get("GATEWAY_RBAC_SECRET") or None
    static_token = source.get("GATEWAY_STATIC_TOKEN") or None

    if not rbac_enabled and not static_token:
        static_token = _secrets.token_urlsafe(32)
        print(f"gateway: no GATEWAY_STATIC_TOKEN set — generated token: {static_token}", flush=True)
        print(
            "Set GATEWAY_STATIC_TOKEN in .env to persist, or pass it to the desktop app.",
            flush=True,
        )

    if rbac_enabled and not rbac_secret:
        raise SystemExit("GATEWAY_RBAC_ENABLED=true requires GATEWAY_RBAC_SECRET")

    shared_store = InMemorySessionStore()
    # In dev mode (rbac off), use a dev secret for cookie signing/verification
    # so that session cookies from POST /v1/auth/login work for cookie-based auth.
    cookie_secret = rbac_secret or "dev-secret"
    auth = GatewayAuth(
        rbac_enabled=rbac_enabled,
        static_token=static_token if not rbac_enabled else None,
        rbac_secret=cookie_secret,
        session_store=shared_store,
        default_tenant_id=config.default_tenant_id,
    )
    session_mgr = GatewaySessionManager(
        session_store=shared_store,
        rbac_secret=cookie_secret,
        default_ttl=int(source.get("SESSION_TTL_SECONDS", "3600") or "3600"),
    )
    sse = GatewaySseStream()
    event_buffer = RunEventBuffer()
    artifact_store = GatewayArtifactStore()

    if runtime is None:
        runtime = _build_runtime(source)

    login_handler = GatewayLoginHandler(
        session_manager=session_mgr,
        auth=auth,
        config=config,
    )

    app = GatewayApp(
        config,
        runtime=runtime,
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        event_buffer=event_buffer,
        artifact_store=artifact_store,
        login_handler=login_handler,
    )
    token_out = static_token or "(rbac session — login via POST /v1/login)"
    return app, config, token_out


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class _GatewayRequestHandler(BaseHTTPRequestHandler):
    """Stdlib HTTP handler bridging to ``GatewayApp.dispatch``/``stream``."""

    server_version = "Gateway/0.1"

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def _headers_map(self) -> dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}

    def _read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        if not raw:
            return None
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _write_json(self, status: int, body: Any) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _write_error(self, status: int, code: str, message: str) -> None:
        self._write_json(status, {"error": {"code": code, "message": message}})

    def _is_stream_route(self, method: str, path: str) -> bool:
        if method != "GET":
            return False
        base = self.server.base_path  # type: ignore[attr-defined]
        prefix = base.rstrip("/")
        # Stream route: /v1/runs/{run_id}/events
        if not path.startswith(prefix + "/runs/"):
            return False
        return path.endswith("/events")

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        headers = self._headers_map()
        body = self._read_body() if method in ("POST", "PUT", "PATCH") else None
        app: GatewayApp = self.server.app  # type: ignore[attr-defined]

        if self._is_stream_route(method, path):
            self._dispatch_stream(app, method, path, headers)
            return

        try:
            result = asyncio.run(app.dispatch(method, path, headers, body))
        except GatewayAuthError as exc:
            self._write_error(exc.status, exc.code, exc.message)
            return
        except GatewayError as exc:
            self._write_error(exc.status, exc.code, str(exc))
            return
        except Exception as exc:  # pragma: no cover — defensive
            self._write_error(500, "internal_error", str(exc))
            return

        # Gateway handlers return either:
        #   success: {"session_id": ..., "status": "ok", "set_cookie": ...}  (body dict, HTTP 200)
        #   error:   {"error": {"code": ..., "message": ...}, "status": 400}  (status is int HTTP code)
        raw_status = result.get("status")
        if isinstance(raw_status, int):
            status = raw_status
        else:
            status = 200  # success — "ok" string or absent

        # Extract Set-Cookie header if present (session creation).
        set_cookie = result.pop("set_cookie", None) if isinstance(result, dict) else None

        payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch_stream(
        self,
        app: GatewayApp,
        method: str,
        path: str,
        headers: dict[str, str],
    ) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            async def _pump() -> None:
                async for frame in app.stream(method, path, headers):
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()

            asyncio.run(_pump())
        except GatewayAuthError as exc:
            try:
                self._write_error(exc.status, exc.code, exc.message)
            except Exception:
                pass
            return
        except GatewayError as exc:
            try:
                self._write_error(exc.status, exc.code, str(exc))
            except Exception:
                pass
            return
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests from desktop/web WebView clients.

        The Tauri WebView2 / browser webview treats ``tauri://localhost`` →
        ``http://127.0.0.1:8000`` as cross-origin, so it sends an OPTIONS
        preflight before POST/PUT. We respond with permissive CORS headers
        since all clients are first-party.
        """
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-Id, X-Session-Id, Last-Event-ID")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def create_server(
    env: Mapping[str, str] | None = None,
    *,
    runtime: Any | None = None,
) -> ThreadingHTTPServer:
    """Create a configured :class:`ThreadingHTTPServer` for the Gateway."""
    app, config, token = create_app(env, runtime=runtime)
    source = env if env is not None else os.environ
    host = source.get("GATEWAY_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(source.get("GATEWAY_BIND_PORT", "8000") or "8000")
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, port), _GatewayRequestHandler)
    httpd.app = app  # type: ignore[attr-defined]
    httpd.base_path = config.base_path  # type: ignore[attr-defined]
    httpd.config = config  # type: ignore[attr-defined]
    httpd.token = token  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="InkStatute Gateway (unified HTTP+SSE entry point)")
    parser.add_argument("--host", default=None, help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default 8000)")
    args = parser.parse_args(argv)

    if args.host is not None:
        os.environ["GATEWAY_BIND_HOST"] = args.host
    if args.port is not None:
        os.environ["GATEWAY_BIND_PORT"] = str(args.port)

    httpd = create_server()

    def _shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    host, port = httpd.server_address[:2]
    print(f"gateway listening on {host}:{port}", flush=True)
    print(f"  base_path: {httpd.base_path}", flush=True)  # type: ignore[attr-defined]
    print(f"  token: {httpd.token}", flush=True)  # type: ignore[attr-defined]
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
