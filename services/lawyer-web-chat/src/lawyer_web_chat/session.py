"""Session management for Lawyer Web Chat.

Provides server-side session storage with RBAC token-based authentication.
Session tokens are HMAC-signed RBAC tokens (lawyer role) set as HttpOnly
cookies. Multi-device sync is achieved via shared session_id — multiple
devices can join the same conversation session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rbac import RbacTokenClaims, Role, issue_token, verify_token

COOKIE_NAME = "lawyer_chat_session"
COOKIE_FLAGS = "HttpOnly; Secure; SameSite=Strict"
DEFAULT_SESSION_TTL = 900  # 15 minutes


@dataclass
class ChatSession:
    """A lawyer chat session."""

    session_id: str
    tenant_id: str
    user_id: str
    conversation_id: str
    created_at: int
    expires_at: int
    devices: list[str] = field(default_factory=list)


class SessionStore:
    """In-memory server-side session store with multi-device sync.

    Multiple devices can share the same session_id to sync chat state.
    Sessions are scoped by tenant_id and conversation_id.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._by_conversation: dict[str, list[str]] = {}

    def create_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        device_id: str | None = None,
        ttl_seconds: int = DEFAULT_SESSION_TTL,
        now: int | None = None,
    ) -> tuple[str, ChatSession]:
        """Create a new chat session and return (token, session).

        The token is an RBAC token (lawyer role) that encodes the session_id
        in the tenant_id claim.
        """
        now_int = int(now if now is not None else time.time())
        session_id = f"session-{tenant_id}-{conversation_id}-{now_int}"
        expires_at = now_int + ttl_seconds

        session = ChatSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            created_at=now_int,
            expires_at=expires_at,
            devices=[device_id] if device_id else [],
        )
        self._sessions[session_id] = session
        self._by_conversation.setdefault(conversation_id, []).append(session_id)
        return session_id, session

    def issue_session_token(
        self,
        secret: str,
        session: ChatSession,
        *,
        ttl_seconds: int = DEFAULT_SESSION_TTL,
        now: int | None = None,
    ) -> str:
        """Issue an RBAC token for the session (lawyer role)."""
        return issue_token(
            secret,
            role=Role.LAWYER,
            tenant_id=session.tenant_id,
            ttl_seconds=ttl_seconds,
            now=now,
        )

    def verify_session_token(
        self,
        token: str,
        secret: str,
        *,
        now: int | None = None,
    ) -> RbacTokenClaims | None:
        """Verify an RBAC session token. Returns claims or None."""
        try:
            claims = verify_token(token, secret, now=now)
        except Exception:
            return None
        if claims.role != Role.LAWYER.value:
            return None
        return claims

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def add_device(self, session_id: str, device_id: str) -> bool:
        """Add a device to an existing session (multi-device sync).

        Returns True if the session exists and the device was added.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if device_id not in session.devices:
            session.devices.append(device_id)
        return True

    def get_sessions_for_conversation(self, conversation_id: str) -> list[ChatSession]:
        """Get all sessions for a conversation (multi-device sync)."""
        session_ids = self._by_conversation.get(conversation_id, [])
        return [
            self._sessions[sid]
            for sid in session_ids
            if sid in self._sessions
        ]

    def cleanup_expired(self, now: int | None = None) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        now_int = int(now if now is not None else time.time())
        expired = [
            sid for sid, session in self._sessions.items()
            if session.expires_at <= now_int
        ]
        for sid in expired:
            session = self._sessions.pop(sid)
            conv_sessions = self._by_conversation.get(session.conversation_id, [])
            if sid in conv_sessions:
                conv_sessions.remove(sid)
        return len(expired)


def build_set_cookie_header(token: str, *, max_age: int = DEFAULT_SESSION_TTL) -> str:
    """Build a Set-Cookie header value for the session token."""
    return f"{COOKIE_NAME}={token}; Max-Age={max_age}; {COOKIE_FLAGS}"


def extract_cookie(headers: dict[str, str]) -> str | None:
    """Extract the session token from Cookie header."""
    cookie_header = None
    for key, value in headers.items():
        if key.lower() == "cookie":
            cookie_header = value
            break
    if cookie_header is None:
        return None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{COOKIE_NAME}="):
            return part[len(COOKIE_NAME) + 1:]
    return None


__all__ = [
    "COOKIE_FLAGS",
    "COOKIE_NAME",
    "ChatSession",
    "DEFAULT_SESSION_TTL",
    "SessionStore",
    "build_set_cookie_header",
    "extract_cookie",
]
