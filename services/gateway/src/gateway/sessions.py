"""Session management for the InkStatute Gateway.

Uses the RBAC ``SessionStore`` Protocol with multi-device sync support
(absorbed from ``lawyer-web-chat``'s ``SessionStore``). The RBAC
``SessionStore`` handles auth-side session records (sid, role, tenant_id,
created_at, expires_at), while the ``GatewaySession`` adds conversation_id
and device tracking that the RBAC ``SessionRecord`` does not have.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rbac.roles import Role
from rbac.session import (
    DEFAULT_SESSION_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    SessionStore,
    issue_session_cookie,
)


@dataclass
class GatewaySession:
    """A Gateway session with conversation and device tracking."""

    session_id: str
    tenant_id: str
    user_id: str
    conversation_id: str
    created_at: int
    expires_at: int
    devices: list[str] = field(default_factory=list)


class GatewaySessionManager:
    """Session manager using the RBAC ``SessionStore`` Protocol.

    The RBAC ``SessionStore`` is Protocol-based and extensible —
    ``InMemorySessionStore`` is the MVP implementation; future
    implementations (Redis, DB) can be swapped without changing call sites.
    """

    def __init__(
        self,
        *,
        session_store: SessionStore,
        rbac_secret: str,
        default_ttl: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> None:
        self._session_store = session_store
        self._rbac_secret = rbac_secret
        self._default_ttl = default_ttl
        self._gateway_sessions: dict[str, GatewaySession] = {}

    def create_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        device_id: str | None = None,
        role: Role = Role.LAWYER,
        ttl_seconds: int | None = None,
    ) -> tuple[str, str, GatewaySession]:
        """Create a session and return ``(session_id, cookie_value, GatewaySession)``.

        Creates a session via the RBAC ``SessionStore.create()``, issues a
        session cookie via ``issue_session_cookie()``, and stores a
        ``GatewaySession`` record internally for conversation_id and device
        tracking.
        """
        now = int(time.time())
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl

        sid = self._session_store.create(
            role=role,
            tenant_id=tenant_id,
            ttl_seconds=ttl,
            now=now,
        )

        cookie_value = issue_session_cookie(
            self._rbac_secret,
            sid,
            role=role,
            tenant_id=tenant_id,
            ttl_seconds=ttl,
            now=now,
        )

        session = GatewaySession(
            session_id=sid,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            created_at=now,
            expires_at=now + ttl,
            devices=[device_id] if device_id else [],
        )
        self._gateway_sessions[sid] = session

        return sid, cookie_value, session

    def get_session(self, session_id: str) -> GatewaySession | None:
        """Retrieve a ``GatewaySession`` by session_id."""
        return self._gateway_sessions.get(session_id)

    def list_sessions(self, tenant_id: str) -> list[GatewaySession]:
        """List all sessions for a tenant (multi-device sync)."""
        return [
            session
            for session in self._gateway_sessions.values()
            if session.tenant_id == tenant_id
        ]

    def add_device(self, session_id: str, device_id: str) -> bool:
        """Add a device to an existing session (multi-device sync).

        Returns ``True`` if the session exists and the device was added.
        """
        session = self._gateway_sessions.get(session_id)
        if session is None:
            return False
        if device_id not in session.devices:
            session.devices.append(device_id)
        return True

    def delete_session(self, session_id: str) -> None:
        """Delete a session from both the RBAC ``SessionStore`` and the internal store."""
        self._session_store.delete(session_id)
        self._gateway_sessions.pop(session_id, None)


def build_set_cookie_header(cookie_value: str, *, max_age: int = DEFAULT_SESSION_TTL_SECONDS) -> str:
    """Build a ``Set-Cookie`` header value with security flags.

    Uses ``HttpOnly; Secure; SameSite=Strict`` flags (same as
    ``lawyer-web-chat``).
    """
    return f"{SESSION_COOKIE_NAME}={cookie_value}; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict"


def serialize_session(session: GatewaySession) -> dict:
    """Serialize a ``GatewaySession`` to a JSON-compatible dict.

    Returns ``{ session_id, tenant_id, user_id, conversation_id,
    created_at, expires_at, devices }``.
    """
    return {
        "session_id": session.session_id,
        "tenant_id": session.tenant_id,
        "user_id": session.user_id,
        "conversation_id": session.conversation_id,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "devices": list(session.devices),
    }


def serialize_session_list(sessions: list[GatewaySession]) -> dict:
    """Serialize a list of ``GatewaySession`` objects to a JSON-compatible dict.

    Returns ``{ sessions: [...], count: N }``.
    """
    return {
        "sessions": [serialize_session(s) for s in sessions],
        "count": len(sessions),
    }


__all__ = [
    "GatewaySession",
    "GatewaySessionManager",
    "build_set_cookie_header",
    "serialize_session",
    "serialize_session_list",
]
