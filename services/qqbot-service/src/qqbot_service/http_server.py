"""Thin stdlib HTTP wrapper over the pure QQBot webhook handler.

Reads Content-Length body bytes once from ``rfile`` and delegates to
``handle_qqbot_webhook_request``. No FastAPI; no WeCom imports.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler
from typing import Any

from qqbot_service.webhook import handle_qqbot_webhook_request

__all__ = [
    "DEFAULT_MAX_BODY_BYTES",
    "QQBotWebhookServer",
    "default_post_ack_error_handler",
    "default_post_ack_scheduler",
    "read_request_body_once",
]

DEFAULT_MAX_BODY_BYTES = 1_048_576  # 1 MiB fail-closed ceiling

PostAckErrorHandler = Callable[[BaseException], None]


def read_request_body_once(
    rfile: Any,
    headers: Mapping[str, str],
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> bytes:
    """Read exactly Content-Length bytes once (signature-safe).

    Raises ``ValueError`` for invalid/negative/oversized lengths.
    """
    raw_len = None
    for key, value in headers.items():
        if key.lower() == "content-length":
            raw_len = value
            break
    if raw_len is None or str(raw_len).strip() == "":
        length = 0
    else:
        try:
            length = int(str(raw_len).strip())
        except ValueError as exc:
            raise ValueError("invalid_content_length") from exc
    if length < 0:
        raise ValueError("negative_content_length")
    if length > max_body_bytes:
        raise ValueError("body_too_large")
    if length == 0:
        return b""
    return rfile.read(length)


def default_post_ack_error_handler(exc: BaseException) -> None:
    """Sanitized failure signal — exception type only, never secrets/payloads."""
    sys.stderr.write(f"qqbot-post-ack failed type={type(exc).__name__}\n")


def default_post_ack_scheduler(
    thunk: Callable[[], Any],
    *,
    on_error: PostAckErrorHandler | None = None,
) -> None:
    """Production default: run post-ACK work on a daemon thread.

    Exceptions are swallowed so the HTTP process never crashes after ACK, but
    a sanitized failure signal is always emitted via ``on_error`` (default:
    stderr with exception type only).
    """
    error_handler = on_error or default_post_ack_error_handler

    def _runner() -> None:
        try:
            result = thunk()
            if asyncio.iscoroutine(result):
                asyncio.run(result)
        except Exception as exc:
            # Never crash the HTTP process from background composition.
            try:
                error_handler(exc)
            except Exception:
                # Error handler must not take down the daemon thread either.
                sys.stderr.write(
                    f"qqbot-post-ack failed type={type(exc).__name__}\n"
                )

    thread = threading.Thread(target=_runner, name="qqbot-post-ack", daemon=True)
    thread.start()


class QQBotWebhookServer(BaseHTTPRequestHandler):
    """HTTP handler for POST /qqbot/callback.

    Server attributes (set by the operator / test harness):

    - ``self.server.wired`` — ``QQBotWiredRuntime``
    - ``self.server.env`` — injected env mapping for secret resolve
    - ``self.server.post_ack_scheduler`` — optional; defaults to daemon thread
    - ``self.server.on_post_ack_error`` — optional sanitized failure callback
    - ``self.server.max_body_bytes`` — optional body ceiling
    - ``self.server.reply_text`` — optional fixed reply for smoke / Fake paths
    - ``self.server.reply_resolver`` — optional ``Callable[[], str | None]``
      for Phase 71 smoke before a full get_run/stream resolver lands
    """

    def do_POST(self) -> None:
        max_body = int(getattr(self.server, "max_body_bytes", DEFAULT_MAX_BODY_BYTES))
        try:
            body = read_request_body_once(
                self.rfile,
                dict(self.headers),
                max_body_bytes=max_body,
            )
        except ValueError:
            self._write_response(400, b'{"error":"invalid_body"}', {
                "Content-Type": "application/json; charset=utf-8",
            })
            return

        wired = getattr(self.server, "wired", None)
        if wired is None:
            self._write_response(503, b'{"error":"not_configured"}', {
                "Content-Type": "application/json; charset=utf-8",
            })
            return

        env = getattr(self.server, "env", None) or {}
        scheduler = getattr(self.server, "post_ack_scheduler", None)
        on_error = getattr(self.server, "on_post_ack_error", None)
        if scheduler is None:
            if on_error is not None:

                def _bound_scheduler(thunk: Callable[[], Any]) -> None:
                    default_post_ack_scheduler(thunk, on_error=on_error)

                scheduler = _bound_scheduler
            else:
                scheduler = default_post_ack_scheduler

        reply_text = getattr(self.server, "reply_text", None)
        reply_resolver = getattr(self.server, "reply_resolver", None)
        if reply_text is None and callable(reply_resolver):
            try:
                reply_text = reply_resolver()
            except Exception:
                # Resolver failures must not block ACK; composition records
                # completed_no_reply when no reply source is available.
                reply_text = None

        status, resp_body, resp_headers = asyncio.run(
            handle_qqbot_webhook_request(
                "POST",
                self.path,
                dict(self.headers),
                body,
                wired=wired,
                env=env,
                post_ack_scheduler=scheduler,
                reply_text=reply_text,
            )
        )
        self._write_response(status, resp_body, resp_headers)

    def do_GET(self) -> None:
        self._write_response(405, b'{"error":"method_not_allowed"}', {
            "Content-Type": "application/json; charset=utf-8",
        })

    def _write_response(
        self,
        status: int,
        body: bytes,
        headers: Mapping[str, str],
    ) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default access logs — never log Authorization or secrets.
        return None
