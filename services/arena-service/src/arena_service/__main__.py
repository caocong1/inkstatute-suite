"""Runnable entry point for the local-only Arena Service.

Usage:
    python -m arena_service [--host 127.0.0.1] [--port 8001]

Environment:
    ARENA_SERVICE_TOKEN (default: auto-generated per start)
    ARENA_SERVICE_BIND_HOST (default 127.0.0.1 — NEVER 0.0.0.0)
    ARENA_SERVICE_BIND_PORT (default 8001)
    ARENA_SERVICE_MAX_CONCURRENT_INIT (default 2)
    ARENA_SERVICE_PER_RUN_TIMEOUT (default 300.0)

The service is local-only: it binds to 127.0.0.1 by default and refuses
to bind to 0.0.0.0 (binding guard in :class:`ArenaServiceConfig`). Auth
(localhost + bearer token) is enforced BEFORE routing — no bypass.

Stream routes (``GET /v1/arena/{id}/stream``) are handled via the
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
    _REPO_ROOT / "packages" / "arena-engine" / "src",
    _REPO_ROOT / "packages" / "agent-core" / "src",
    _REPO_ROOT / "packages" / "acp-client" / "src",
    _REPO_ROOT / "packages" / "acp-event-bridge" / "src",
    _REPO_ROOT / "packages" / "platform-contract" / "src",
    _REPO_ROOT / "packages" / "platform-runtime" / "src",
):
    _path = str(_root)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from arena_service.app import ArenaServiceApp, ArenaServiceError
from arena_service.auth import ArenaServiceAuth, ArenaServiceAuthError
from arena_service.config import ArenaServiceConfig
from arena_service.engine_integration import ArenaServiceEngine


def create_app(
    env: Mapping[str, str] | None = None,
    *,
    engine: object | None = None,
) -> tuple[ArenaServiceApp, ArenaServiceConfig]:
    """Build a configured :class:`ArenaServiceApp` + its :class:`ArenaServiceConfig`.

    When ``engine`` is None, a default :class:`ArenaServiceEngine` is
    constructed (no ``adapter_factory`` — arenas can be created and
    status/openapi work, but ``create_arena`` will not auto-start a run
    until an adapter_factory is wired). This is enough for the HTTP
    surface to boot and for the desktop app to hit status/openapi/export.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    config = ArenaServiceConfig.from_env(source)
    if not config.token:
        # Auto-generate a per-start token when none is configured so the
        # service is never accidentally unauthenticated. Print it once.
        import secrets as _secrets

        config = ArenaServiceConfig(
            bind_host=config.bind_host,
            bind_port=config.bind_port,
            base_path=config.base_path,
            token=_secrets.token_urlsafe(32),
            max_concurrent_initializations=config.max_concurrent_initializations,
            per_run_timeout_seconds=config.per_run_timeout_seconds,
            enabled=config.enabled,
        )
        print(
            f"arena-service: no ARENA_SERVICE_TOKEN set — generated token: {config.token}",
            flush=True,
        )
        print(
            "Set ARENA_SERVICE_TOKEN in .env to persist, or pass it to the desktop app "
            "via VITE_ARENA_SERVICE_TOKEN.",
            flush=True,
        )
    auth = ArenaServiceAuth(config)
    if engine is None:
        engine = ArenaServiceEngine(config)
    app = ArenaServiceApp(config=config, auth=auth, engine=engine)
    return app, config


class _ArenaRequestHandler(BaseHTTPRequestHandler):
    """Stdlib HTTP handler that bridges to ``ArenaServiceApp.dispatch``/``stream``.

    The handler holds a reference to the app via the server instance
    (``self.server.app``). Non-stream routes call ``app.dispatch()``;
    stream routes (``GET /v1/arena/{id}/stream``) call ``app.stream()``
    and flush SSE frames incrementally.
    """

    server_version = "ArenaService/0.1"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def _headers_map(self) -> dict[str, str]:
        # Lowercase keys for case-insensitive lookup by auth layer.
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
        # Stream route: /v1/arena/{arena_id}/stream
        base = self.server.base_path  # type: ignore[attr-defined]
        prefix = base.rstrip("/")
        if not path.startswith(prefix + "/arena/"):
            return False
        return path.endswith("/stream")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        headers = self._headers_map()
        body = self._read_body() if method in ("POST", "PUT", "PATCH") else None
        client_ip = self._client_ip()
        app: ArenaServiceApp = self.server.app  # type: ignore[attr-defined]

        if self._is_stream_route(method, path):
            self._dispatch_stream(app, method, path, headers, client_ip)
            return

        try:
            result = asyncio.run(
                app.dispatch(method, path, headers, body, client_address=client_ip)
            )
        except ArenaServiceAuthError as exc:
            self._write_error(exc.status, exc.code, exc.message)
            return
        except ArenaServiceError as exc:
            self._write_error(exc.status, exc.code, str(exc))
            return
        except Exception as exc:  # pragma: no cover — defensive
            self._write_error(500, "internal_error", str(exc))
            return

        status = int(result.get("status", 200))
        response_body = result.get("body", result)
        self._write_json(status, response_body)

    def _dispatch_stream(
        self,
        app: ArenaServiceApp,
        method: str,
        path: str,
        headers: dict[str, str],
        client_ip: str,
    ) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            async def _pump() -> None:
                async for frame in app.stream(method, path, headers, client_address=client_ip):
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()

            asyncio.run(_pump())
        except ArenaServiceAuthError as exc:
            # Headers not sent yet in some paths — try to send an error frame.
            try:
                self._write_error(exc.status, exc.code, exc.message)
            except Exception:
                pass
            return
        except ArenaServiceError as exc:
            try:
                self._write_error(exc.status, exc.code, str(exc))
            except Exception:
                pass
            return
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected mid-stream — normal for SSE.
            return

    # ------------------------------------------------------------------
    # HTTP method handlers
    # ------------------------------------------------------------------

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
        """Handle CORS preflight requests from desktop/web WebView clients."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-Id, X-Session-Id, Last-Event-ID")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Concise access log to stderr.
        sys.stderr.write(
            "%s - %s\n" % (self.address_string(), format % args)
        )


def create_server(
    env: Mapping[str, str] | None = None,
    *,
    engine: object | None = None,
) -> ThreadingHTTPServer:
    """Create a configured :class:`ThreadingHTTPServer` for the Arena Service."""
    app, config = create_app(env, engine=engine)
    host = config.bind_host
    port = config.bind_port
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, port), _ArenaRequestHandler)
    httpd.app = app  # type: ignore[attr-defined]
    httpd.base_path = config.base_path  # type: ignore[attr-defined]
    httpd.config = config  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="InkStatute Arena Service (local-only)")
    parser.add_argument("--host", default=None, help="bind host (default 127.0.0.1, never 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default 8001)")
    args = parser.parse_args(argv)

    if args.host is not None:
        os.environ["ARENA_SERVICE_BIND_HOST"] = args.host
    if args.port is not None:
        os.environ["ARENA_SERVICE_BIND_PORT"] = str(args.port)

    httpd = create_server()

    def _shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    host, port = httpd.server_address[:2]
    token = httpd.config.token  # type: ignore[attr-defined]
    print(f"arena-service listening on {host}:{port}", flush=True)
    print(f"  base_path: {httpd.base_path}", flush=True)  # type: ignore[attr-defined]
    print(f"  token: {token}", flush=True)
    print(f"  OpenAPI: http://{host}:{port}{httpd.base_path}/openapi", flush=True)  # type: ignore[attr-defined]
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
