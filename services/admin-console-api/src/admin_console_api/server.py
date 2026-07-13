"""Stdlib HTTP adapter for the Admin Console API.

Binds ``AdminConsoleApiServer`` to a ``ThreadingHTTPServer`` and delegates
GET/PUT to the existing ``handle_admin_get`` / ``handle_admin_put`` handlers.
"""

from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from inkstatute_operator_config import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags

from .api import handle_admin_get, handle_admin_put
from .feedback import ThreadSafeFeedbackQueue

MAX_BODY_BYTES = 1_048_576  # 1 MiB fail-closed ceiling


def _query_map(query_string: str) -> dict[str, str]:
    """Return the last value for each query key."""
    parsed = parse_qs(query_string, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


class AdminConsoleApiServer(BaseHTTPRequestHandler):
    """HTTP handler for the Admin Console API.

    Server-level attributes are set by ``create_server``:

    - ``self.server.feature_flags`` — RuntimeFeatureFlags
    - ``self.server.env`` — Mapping[str, str] | None
    - ``self.server.rbac_secret`` — str | None
    - ``self.server.read_model`` — ContractLogReadModel or compatible
    - ``self.server.feedback_queue`` — ThreadSafeFeedbackQueue or list | None
    - ``self.server.config_store`` — OperatorConfigStore
    """

    def do_GET(self) -> None:
        self._dispatch("GET", b"")

    def do_PUT(self) -> None:
        try:
            body = self._read_body()
        except ValueError:
            self._send_json(
                400,
                {"error": {"code": "invalid_request", "message": "invalid or oversized Content-Length"}},
            )
            return
        self._dispatch("PUT", body)

    def do_POST(self) -> None:
        self._method_not_allowed()

    def do_HEAD(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def _read_body(self) -> bytes:
        raw = self.headers.get("Content-Length", "0")
        try:
            length = int(raw)
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("body too large")
        if length == 0:
            return b""
        return self.rfile.read(length)

    def _dispatch(self, method: str, body: bytes) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if method == "GET":
                status, response = self.server.handle_admin_get(
                    path,
                    _query_map(parsed.query),
                    dict(self.headers),
                    self.server.read_model,
                    self.server.feedback_queue,
                    self.server.feature_flags,
                    self.server.env,
                    self.server.rbac_secret,
                    config_store=self.server.config_store,
                )
            else:  # PUT
                try:
                    payload = json.loads(body.decode("utf-8")) if body else None
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    self._send_json(
                        400,
                        {"error": {"code": "invalid_json", "message": "request body is not valid JSON"}},
                    )
                    return
                status, response = self.server.handle_admin_put(
                    path,
                    payload,
                    dict(self.headers),
                    self.server.feature_flags,
                    self.server.env,
                    config_store=self.server.config_store,
                    rbac_secret=self.server.rbac_secret,
                )
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            status, response = 500, {
                "error": {
                    "code": "internal_error",
                    "message": "internal server error",
                    "type": type(exc).__name__,
                }
            }

        self._send_json(status, response)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _method_not_allowed(self) -> None:
        self._send_json(
            405,
            {"error": {"code": "method_not_allowed", "message": "only GET and PUT are supported"}},
        )

    def log_message(self, format: str, *args: Any) -> None:
        pass


def create_server(
    env: dict[str, str] | None = None,
) -> ThreadingHTTPServer:
    """Create a configured ``ThreadingHTTPServer`` for the admin console API.

    ``env`` defaults to ``os.environ``.  The caller is responsible for calling
    ``serve_forever`` and ``shutdown``.
    """
    import os

    from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
    from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records

    source = env if env is not None else os.environ
    feature_flags = RuntimeFeatureFlags.from_env(source)
    feature_flags.require_enabled("admin_api_enabled")

    host = source.get("ADMIN_CONSOLE_API_HOST", "127.0.0.1")
    try:
        port = int(source.get("ADMIN_CONSOLE_API_PORT", "8081"))
    except ValueError:
        port = 8081

    rbac_secret = source.get("RBAC_TOKEN_SECRET") or None
    config_path = source.get("INKSTATUTE_OPERATOR_CONFIG_PATH") or None
    config_store = OperatorConfigStore(config_path)

    contract_log_path = source.get("INKSTATUTE_CONTRACT_LOG_PATH") or None
    read_model = _build_read_model(contract_log_path)

    feedback_path = source.get("INKSTATUTE_FEEDBACK_QUEUE_PATH") or None
    feedback_queue = _build_feedback_queue(feedback_path)

    httpd = ThreadingHTTPServer((host, port), AdminConsoleApiServer)
    httpd.feature_flags = feature_flags
    httpd.env = dict(source)
    httpd.rbac_secret = rbac_secret
    httpd.read_model = read_model
    httpd.feedback_queue = feedback_queue
    httpd.config_store = config_store
    httpd.handle_admin_get = handle_admin_get
    httpd.handle_admin_put = handle_admin_put
    return httpd


def _build_read_model(contract_log_path: str | None) -> Any:
    from conversation_read_view.read_model import build_read_model, load_records_from_jsonl

    if not contract_log_path:
        return build_read_model([])
    path = contract_log_path
    if not __import__("pathlib").Path(path).is_file():
        return build_read_model([])
    records = load_records_from_jsonl(path)
    return build_read_model(records)


def _build_feedback_queue(feedback_path: str | None) -> Any:
    from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records

    if not feedback_path:
        return ThreadSafeFeedbackQueue()
    path = feedback_path
    if not __import__("pathlib").Path(path).is_file():
        return ThreadSafeFeedbackQueue()
    records = load_jsonl_records(path)
    return ThreadSafeFeedbackQueue(build_pending_feedback_queue(records))


__all__ = ["AdminConsoleApiServer", "create_server", "MAX_BODY_BYTES"]
