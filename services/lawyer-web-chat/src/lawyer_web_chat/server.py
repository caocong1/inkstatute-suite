"""Lawyer Web Chat HTTP server — stdlib http.server with SSE + session auth.

Request flow:
  Browser --HTTP--> LawyerWebChatServer
    -> feature flag gate (lawyer_web_chat_enabled)
    -> /login: issue RBAC token (lawyer role) -> Set-Cookie httpOnly
    -> /sessions: server-side session store (multi-device sync)
    -> /history: message history (reference-only)
    -> /stream: SSE via encode_sse_event, output boundary per event
    -> /upload: file upload -> payload_ref/content_ref only
    -> /feedback: normalize feedback -> FeedbackEvent
    -> all responses: CSP header, html.escape rendering
"""

from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler
from typing import Any, Mapping

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from platform_runtime.tenant_scope import (
    TenantGuard,
    TenantScopeRequestContext,
    TenantScopeResolver,
)

from .boundary import ChatBoundary
from .feedback import FeedbackHandler
from .history import MessageHistory
from .session import (
    COOKIE_NAME,
    SessionStore,
    build_set_cookie_header,
    extract_cookie,
)
from .sse import SseStream
from .upload import FileUploadHandler

CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self'"


def _esc(value: Any) -> str:
    return html.escape(str(value))


def handle_lawyer_chat_request(
    method: str,
    path: str,
    headers: Mapping[str, str] | None,
    body: bytes | None,
    *,
    feature_flags: RuntimeFeatureFlags,
    session_store: SessionStore,
    message_history: MessageHistory,
    upload_handler: FileUploadHandler,
    feedback_handler: FeedbackHandler,
    sse_stream: SseStream,
    rbac_secret: str,
    env: Mapping[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Handle a single lawyer web chat request.

    Returns ``(status_code, response_body_bytes, response_headers)``.

    This function is the testable core — it does not depend on the
    BaseHTTPRequestHandler class and can be called directly from tests.
    """
    response_headers: dict[str, str] = {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Security-Policy": CSP_HEADER,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    # Step 1 — feature flag gate
    try:
        feature_flags.require_enabled("lawyer_web_chat_enabled")
    except RuntimeFeatureDisabledError:
        body_html = _render_error_page("lawyer_web_chat_disabled", "lawyer_web_chat_enabled flag is False")
        return 503, body_html.encode("utf-8"), response_headers

    route_path = path.split("?")[0]

    # Step 2 — route dispatch
    if method == "GET" and route_path == "/":
        return _handle_index(headers, session_store, rbac_secret, response_headers)

    if method == "POST" and route_path == "/login":
        return _handle_login(body, session_store, rbac_secret, response_headers)

    # All remaining routes require authentication
    claims = _authenticate(headers, session_store, rbac_secret)
    if claims is None:
        body_html = _render_error_page("unauthorized", "Invalid or missing session token")
        return 401, body_html.encode("utf-8"), response_headers

    tenant_id = claims.tenant_id

    # Tenant scope resolution + guard enforcement
    resolver = TenantScopeResolver(feature_flags=feature_flags)
    tenant_guard = TenantGuard(feature_flags=feature_flags)
    scope = resolver.resolve(TenantScopeRequestContext(identity=claims, headers=headers))
    tenant_filter = tenant_guard.enforce(scope)

    if method == "GET" and route_path == "/sessions":
        return _handle_sessions(tenant_id, session_store, response_headers)

    if method == "GET" and route_path == "/history":
        return _handle_history(path, tenant_id, message_history, response_headers, tenant_filter=tenant_filter)

    if method == "GET" and route_path == "/stream":
        return _handle_stream(tenant_id, sse_stream, message_history, response_headers, tenant_filter=tenant_filter)

    if method == "POST" and route_path == "/upload":
        return _handle_upload(body, tenant_id, upload_handler, response_headers, tenant_filter=tenant_filter)

    if method == "POST" and route_path == "/feedback":
        return _handle_feedback(body, tenant_id, feedback_handler, response_headers, tenant_filter=tenant_filter)

    body_html = _render_error_page("not_found", f"Unknown route: {route_path}")
    return 404, body_html.encode("utf-8"), response_headers


def _authenticate(
    headers: Mapping[str, str] | None,
    session_store: SessionStore,
    rbac_secret: str,
) -> Any:
    """Extract and verify the session token from cookies."""
    if headers is None:
        return None
    token = extract_cookie(dict(headers))
    if token is None:
        return None
    return session_store.verify_session_token(token, rbac_secret)


def _handle_index(
    headers: Mapping[str, str] | None,
    session_store: SessionStore,
    rbac_secret: str,
    response_headers: dict[str, str],
) -> tuple[int, bytes, dict[str, str]]:
    """Render the chat index page."""
    claims = _authenticate(headers, session_store, rbac_secret)
    if claims is not None:
        html_doc = _render_chat_page(tenant_id=claims.tenant_id)
    else:
        html_doc = _render_login_page()
    return 200, html_doc.encode("utf-8"), response_headers


def _handle_login(
    body: bytes | None,
    session_store: SessionStore,
    rbac_secret: str,
    response_headers: dict[str, str],
) -> tuple[int, bytes, dict[str, str]]:
    """Handle login — issue RBAC token and set cookie."""
    if body is None:
        body = b""
    try:
        data = json.loads(body.decode("utf-8")) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {}

    tenant_id = data.get("tenant_id", "default")
    user_id = data.get("user_id", "lawyer")
    conversation_id = data.get("conversation_id", f"conv-{tenant_id}")
    device_id = data.get("device_id")

    session_id, session = session_store.create_session(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        device_id=device_id,
    )
    token = session_store.issue_session_token(rbac_secret, session)

    response_headers["Set-Cookie"] = build_set_cookie_header(token)
    response_headers["Content-Type"] = "application/json"
    response_body = json.dumps({
        "status": "ok",
        "session_id": _esc(session_id),
        "tenant_id": _esc(tenant_id),
        "conversation_id": _esc(conversation_id),
    })
    return 200, response_body.encode("utf-8"), response_headers


def _handle_sessions(
    tenant_id: str,
    session_store: SessionStore,
    response_headers: dict[str, str],
) -> tuple[int, bytes, dict[str, str]]:
    """List sessions for the tenant (multi-device sync)."""
    response_headers["Content-Type"] = "application/json"
    sessions = [
        {
            "session_id": _esc(s.session_id),
            "conversation_id": _esc(s.conversation_id),
            "user_id": _esc(s.user_id),
            "devices": [_esc(d) for d in s.devices],
            "created_at": s.created_at,
        }
        for s in session_store._sessions.values()
        if s.tenant_id == tenant_id
    ]
    response_body = json.dumps({"sessions": sessions, "count": len(sessions)})
    return 200, response_body.encode("utf-8"), response_headers


def _handle_history(
    path: str,
    tenant_id: str,
    message_history: MessageHistory,
    response_headers: dict[str, str],
    *,
    tenant_filter: Any = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Get message history for a conversation."""
    response_headers["Content-Type"] = "application/json"
    # Parse conversation_id from query string
    query = path.split("?", 1)[1] if "?" in path else ""
    conversation_id = "default"
    for part in query.split("&"):
        if part.startswith("conversation_id="):
            conversation_id = part.split("=", 1)[1]
    result = message_history.get_history(conversation_id, tenant_filter=tenant_filter)
    response_body = json.dumps(result)
    return 200, response_body.encode("utf-8"), response_headers


def _handle_stream(
    tenant_id: str,
    sse_stream: SseStream,
    message_history: MessageHistory,
    response_headers: dict[str, str],
    *,
    tenant_filter: Any = None,
) -> tuple[int, bytes, dict[str, str]]:
    """SSE streaming endpoint."""
    response_headers["Content-Type"] = "text/event-stream"
    response_headers["Cache-Control"] = "no-cache"
    response_headers["Connection"] = "keep-alive"
    # In a real implementation, this would stream from the runtime.
    # For now, we encode any existing history as SSE events.
    history = message_history.get_history(tenant_id, tenant_filter=tenant_filter)
    events = []
    for item in history["items"]:
        events.append({
            "event_id": item["message_id"],
            "run_id": tenant_id,
            "event_type": "message_delta",
            "occurred_at": str(item["timestamp"]),
            "seq": 0,
            "payload": {"message_delta": item["content"]},
            "metadata": {"sender": item["sender"]},
        })
    stream_body = sse_stream.encode_stream_response(events)
    return 200, stream_body.encode("utf-8"), response_headers


def _handle_upload(
    body: bytes | None,
    tenant_id: str,
    upload_handler: FileUploadHandler,
    response_headers: dict[str, str],
    *,
    tenant_filter: Any = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Handle file upload — stores references only."""
    if body is None:
        body = b""
    try:
        data = json.loads(body.decode("utf-8")) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {}

    filename = data.get("filename", "unnamed")
    content_b64 = data.get("content", "")
    mime_type = data.get("mime_type", "application/octet-stream")
    conversation_id = data.get("conversation_id", "default")

    import base64
    try:
        content_bytes = base64.b64decode(content_b64) if content_b64 else b""
    except Exception:
        content_bytes = b""

    result = upload_handler.handle_upload(
        filename=filename,
        content_bytes=content_bytes,
        mime_type=mime_type,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )

    response_headers["Content-Type"] = "application/json"
    response_body = json.dumps({
        "upload_id": _esc(result.upload_id),
        "payload_ref": _esc(result.payload_ref),
        "content_ref": _esc(result.content_ref),
        "content_hash": _esc(result.content_hash),
        "filename": _esc(result.filename),
        "size_bytes": result.size_bytes,
        "mime_type": _esc(result.mime_type),
        "reference_only": True,
    })
    return 200, response_body.encode("utf-8"), response_headers


def _handle_feedback(
    body: bytes | None,
    tenant_id: str,
    feedback_handler: FeedbackHandler,
    response_headers: dict[str, str],
    *,
    tenant_filter: Any = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Handle feedback submission."""
    if body is None:
        body = b""
    try:
        data = json.loads(body.decode("utf-8")) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {}

    try:
        result = feedback_handler.submit_feedback(
            conversation_id=data.get("conversation_id", "default"),
            user_id=data.get("user_id", "lawyer"),
            action=data.get("action", "needs_fix"),
            feedback_target=data.get("feedback_target", ""),
            message=data.get("message"),
            turn_id=data.get("turn_id"),
            tenant_id=tenant_id,
        )
    except ValueError as e:
        response_headers["Content-Type"] = "application/json"
        response_body = json.dumps({"error": {"code": "invalid_action", "message": str(e)}})
        return 400, response_body.encode("utf-8"), response_headers

    response_headers["Content-Type"] = "application/json"
    response_body = json.dumps({
        "feedback_id": _esc(result.feedback_id),
        "action": _esc(result.action),
        "event_type": _esc(result.event_type),
        "status": "pending",
    })
    return 200, response_body.encode("utf-8"), response_headers


def _render_error_page(code: str, message: str) -> str:
    """Render an error page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Error - InkStatute Chat</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #333; }}
    .error {{ color: #c0392b; }}
  </style>
</head>
<body>
  <h1>InkStatute Lawyer Chat</h1>
  <p class="error">Error [{_esc(code)}]: {_esc(message)}</p>
</body>
</html>"""


def _render_login_page() -> str:
    """Render the login page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login - InkStatute Chat</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; color: #333; }
    .form { max-width: 400px; margin: 2rem auto; }
    input { display: block; width: 100%; padding: 0.5rem; margin: 0.5rem 0; box-sizing: border-box; }
    button { padding: 0.5rem 2rem; background: #1a1a2e; color: #fff; border: none; cursor: pointer; }
  </style>
</head>
<body>
  <h1>InkStatute Lawyer Chat</h1>
  <div class="form">
    <h2>Login</h2>
    <form action="/login" method="post">
      <input type="text" name="tenant_id" placeholder="Tenant ID" required>
      <input type="text" name="user_id" placeholder="User ID" required>
      <input type="text" name="conversation_id" placeholder="Conversation ID">
      <button type="submit">Login</button>
    </form>
  </div>
</body>
</html>"""


def _render_chat_page(tenant_id: str) -> str:
    """Render the chat page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InkStatute Chat</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
    .header {{ background: #1a1a2e; color: #fff; padding: 1rem 2rem; }}
    .chat {{ max-width: 800px; margin: 2rem auto; background: #fff; border-radius: 8px; padding: 1.5rem; }}
    .messages {{ min-height: 300px; margin-bottom: 1rem; }}
    .input {{ display: flex; gap: 0.5rem; }}
    input {{ flex: 1; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }}
    button {{ padding: 0.5rem 1rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }}
  </style>
</head>
<body>
  <div class="header"><h1>InkStatute Lawyer Chat</h1></div>
  <div class="chat">
    <p>Tenant: <strong>{_esc(tenant_id)}</strong></p>
    <div class="messages" id="messages"></div>
    <div class="input">
      <input type="text" id="message" placeholder="Type a message...">
      <button onclick="sendMessage()">Send</button>
    </div>
  </div>
</body>
</html>"""


class LawyerWebChatServer(BaseHTTPRequestHandler):
    """HTTP server handler for the Lawyer Web Chat.

    Configuration is passed via server-level attributes:

    - ``self.server.feature_flags`` — RuntimeFeatureFlags
    - ``self.server.session_store`` — SessionStore
    - ``self.server.message_history`` — MessageHistory
    - ``self.server.upload_handler`` — FileUploadHandler
    - ``self.server.feedback_handler`` — FeedbackHandler
    - ``self.server.sse_stream`` — SseStream
    - ``self.server.rbac_secret`` — str
    - ``self.server.env`` — Mapping[str, str] or None
    """

    def do_GET(self) -> None:
        status, body, headers = handle_lawyer_chat_request(
            "GET",
            self.path,
            dict(self.headers),
            None,
            feature_flags=self.server.feature_flags,  # type: ignore[attr-defined]
            session_store=self.server.session_store,  # type: ignore[attr-defined]
            message_history=self.server.message_history,  # type: ignore[attr-defined]
            upload_handler=self.server.upload_handler,  # type: ignore[attr-defined]
            feedback_handler=self.server.feedback_handler,  # type: ignore[attr-defined]
            sse_stream=self.server.sse_stream,  # type: ignore[attr-defined]
            rbac_secret=self.server.rbac_secret,  # type: ignore[attr-defined]
            env=getattr(self.server, "env", None),  # type: ignore[attr-defined]
        )
        self._send_response(status, body, headers)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        status, response_body, headers = handle_lawyer_chat_request(
            "POST",
            self.path,
            dict(self.headers),
            body,
            feature_flags=self.server.feature_flags,  # type: ignore[attr-defined]
            session_store=self.server.session_store,  # type: ignore[attr-defined]
            message_history=self.server.message_history,  # type: ignore[attr-defined]
            upload_handler=self.server.upload_handler,  # type: ignore[attr-defined]
            feedback_handler=self.server.feedback_handler,  # type: ignore[attr-defined]
            sse_stream=self.server.sse_stream,  # type: ignore[attr-defined]
            rbac_secret=self.server.rbac_secret,  # type: ignore[attr-defined]
            env=getattr(self.server, "env", None),  # type: ignore[attr-defined]
        )
        self._send_response(status, response_body, headers)

    def _send_response(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


__all__ = [
    "CSP_HEADER",
    "LawyerWebChatServer",
    "handle_lawyer_chat_request",
]
