"""Thin stdlib HTTP client for the Gateway API.

This module provides a minimal HTTP client for bot services to consume the
Gateway API using **only** the Python standard library (``urllib.request``,
``http.client``, ``json``). No external dependencies, no imports from the
``gateway`` package — this is an HTTP client, not an in-process caller.

All methods include ``Authorization: Bearer {token}`` — no auth bypass.
The ``stream_events`` method parses SSE frames (``id:``, ``event:``,
``data:`` lines) and yields parsed event dicts as they arrive.
"""

from __future__ import annotations

import http.client
import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GatewayClientConfig:
    """Configuration for :class:`GatewayClient`.

    Attributes
    ----------
    base_url:
        Gateway base URL (e.g. ``http://127.0.0.1:8081``).
    bearer_token:
        Pre-resolved Bearer token for auth.
    tenant_id:
        Tenant ID for run creation.
    timeout_seconds:
        HTTP request timeout in seconds.
    """

    base_url: str
    bearer_token: str
    tenant_id: str = "default-tenant"
    timeout_seconds: float = 30.0


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GatewayClientError(Exception):
    """Raised on non-2xx HTTP responses from the Gateway."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"[{status}] {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_headers(
    config: GatewayClientConfig,
    *,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the standard headers dict with Bearer auth and JSON content type."""
    headers: dict[str, str] = {
        "Authorization": f"Bearer {config.bearer_token}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _parse_sse_frame(lines: list[str]) -> dict[str, Any] | None:
    """Parse a group of SSE lines (separated by blank line) into an event dict.

    Extracts ``id`` (event_id), ``event`` (event_type), and ``data``
    (JSON-parsed payload). Multi-line ``data:`` fields are concatenated
    before JSON parsing. Returns ``None`` for incomplete frames (no lines).
    """
    if not lines:
        return None

    event_id: str | None = None
    event_type: str | None = None
    data_parts: list[str] = []

    for line in lines:
        if line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_parts.append(line[5:].strip())

    if event_id is None and event_type is None and not data_parts:
        return None

    payload: Any = {}
    if data_parts:
        raw_data = "\n".join(data_parts)
        try:
            payload = json.loads(raw_data)
        except (json.JSONDecodeError, ValueError):
            payload = {"_raw": raw_data}

    return {
        "event_id": event_id,
        "event_type": event_type,
        "payload": payload,
    }


def _parse_base_url(base_url: str) -> tuple[str, str, int]:
    """Parse a base URL into (scheme, host, port)."""
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, host, port


def _check_response(status: int, body: str) -> dict[str, Any]:
    """Check HTTP status and return parsed JSON body, or raise."""
    if 200 <= status < 300:
        try:
            return json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            return {"_raw": body}
    # Non-2xx — raise GatewayClientError
    try:
        error_body = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        error_body = {}
    raise GatewayClientError(
        status=status,
        code=str(error_body.get("code", "http_error")),
        message=str(error_body.get("message", error_body.get("error", body or "HTTP error"))),
    )


# ---------------------------------------------------------------------------
# GatewayClient
# ---------------------------------------------------------------------------


class GatewayClient:
    """Thin stdlib HTTP client for the Gateway API.

    No network connection at construction time. All methods include
    ``Authorization: Bearer {token}`` header.
    """

    def __init__(self, config: GatewayClientConfig) -> None:
        self._config = config
        self._scheme, self._host, self._port = _parse_base_url(config.base_url)

    @property
    def config(self) -> GatewayClientConfig:
        return self._config

    # -- Session management --------------------------------------------------

    def create_session(self, *, conversation_id: str) -> dict[str, Any]:
        """POST ``/v1/sessions`` to create a session for a conversation."""
        body = json.dumps({
            "conversation_id": conversation_id,
            "tenant_id": self._config.tenant_id,
        }).encode("utf-8")
        headers = _build_headers(self._config)
        response_body = self._do_request("POST", "/v1/sessions", headers, body)
        return response_body

    # -- Run management ------------------------------------------------------

    def create_run(
        self,
        *,
        turn: dict[str, Any],
        solution: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """POST ``/v1/runs`` to create a new run."""
        payload: dict[str, Any] = {
            "turn": turn,
            "solution": solution,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        body = json.dumps(payload).encode("utf-8")
        headers = _build_headers(self._config)
        return self._do_request("POST", "/v1/runs", headers, body)

    def stream_events(
        self,
        run_id: str,
        *,
        last_event_id: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """GET ``/v1/runs/{run_id}/events`` as an SSE stream.

        Reads the HTTP response line-by-line, parses SSE frames, and yields
        each event as a parsed dict. The iterator ends when the HTTP
        connection closes (terminal state).

        If ``last_event_id`` is provided, sends ``Last-Event-ID`` header
        for reconnection replay.
        """
        path = f"/v1/runs/{run_id}/events"
        extra: dict[str, str] = {"Accept": "text/event-stream"}
        if last_event_id is not None:
            extra["Last-Event-ID"] = str(last_event_id)
        headers = _build_headers(self._config, extra=extra)

        conn_cls = http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(self._host, self._port, timeout=self._config.timeout_seconds)
        try:
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            if not (200 <= response.status < 300):
                body = response.read().decode("utf-8", errors="replace")
                _check_response(response.status, body)

            # Read SSE stream line-by-line
            frame_lines: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    # Blank line — frame boundary
                    if frame_lines:
                        event = _parse_sse_frame(frame_lines)
                        if event is not None:
                            yield event
                        frame_lines = []
                else:
                    frame_lines.append(line)

            # Flush any remaining frame
            if frame_lines:
                event = _parse_sse_frame(frame_lines)
                if event is not None:
                    yield event
        finally:
            conn.close()

    # -- Elicitation / Approval ---------------------------------------------

    def submit_elicitation(
        self,
        run_id: str,
        *,
        interrupt_id: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        """POST ``/v1/runs/{run_id}/elicitation`` to submit an elicitation answer."""
        path = f"/v1/runs/{run_id}/elicitation"
        body = json.dumps({
            "interrupt_id": interrupt_id,
            "answers": answers,
        }).encode("utf-8")
        headers = _build_headers(self._config)
        return self._do_request("POST", path, headers, body)

    def submit_approval(
        self,
        run_id: str,
        *,
        permission_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """POST ``/v1/runs/{run_id}/approvals`` to submit an approval decision."""
        path = f"/v1/runs/{run_id}/approvals"
        body = json.dumps({
            "permission_id": permission_id,
            "decision": decision,
        }).encode("utf-8")
        headers = _build_headers(self._config)
        return self._do_request("POST", path, headers, body)

    # -- Artifacts -----------------------------------------------------------

    def download_artifact(self, artifact_id: str) -> bytes:
        """GET ``/v1/artifacts/{artifact_id}`` — returns raw artifact bytes."""
        path = f"/v1/artifacts/{artifact_id}"
        headers = _build_headers(self._config)
        conn_cls = http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(self._host, self._port, timeout=self._config.timeout_seconds)
        try:
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            data = response.read()
            if not (200 <= response.status < 300):
                body = data.decode("utf-8", errors="replace")
                _check_response(response.status, body)
            return data
        finally:
            conn.close()

    # -- Feedback ------------------------------------------------------------

    def submit_feedback(
        self,
        *,
        run_id: str,
        feedback_data: dict[str, Any],
    ) -> dict[str, Any]:
        """POST ``/v1/feedback`` to submit user feedback."""
        payload = {"run_id": run_id, **feedback_data}
        body = json.dumps(payload).encode("utf-8")
        headers = _build_headers(self._config)
        return self._do_request("POST", "/v1/feedback", headers, body)

    # -- Internal HTTP helper ------------------------------------------------

    def _do_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> dict[str, Any]:
        """Execute a non-streaming HTTP request and return parsed JSON."""
        import urllib.request

        url = f"{self._config.base_url}{path}"
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                status = resp.status
                resp_body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return _check_response(status, resp_body)


__all__ = [
    "GatewayClient",
    "GatewayClientConfig",
    "GatewayClientError",
    "_build_headers",
    "_parse_sse_frame",
]
