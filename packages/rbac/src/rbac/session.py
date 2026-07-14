"""HMAC-signed session cookies with server-side session store (Phase 85).

Session cookies are ``base64url(payload_json).base64url(hmac_sha256(secret,
payload_b64))`` — the same signing scheme as ``rbac.token`` but with an
added ``sid`` claim.  The server-side ``SessionStore`` maps the session ID
to a ``SessionRecord`` so that logout can invalidate the session by
deleting the entry.  Verification requires both a valid signature AND a
live store entry — a self-contained cookie alone is never sufficient.

The ``SessionStore`` Protocol is extensible: ``InMemorySessionStore`` is
the MVP implementation; future implementations (Redis, DB) can be
swapped without changing call sites.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any, Protocol

from .roles import Role

DEFAULT_SESSION_TTL_SECONDS = 28800  # 8 hours
SESSION_COOKIE_NAME = "inkstatute_session"


class SessionStore(Protocol):
    """Extensible session store interface.

    MVP: ``InMemorySessionStore`` (dict + lock).  Future: Redis, DB.
    """

    def create(
        self, *, role: Role, tenant_id: str, ttl_seconds: int, now: int
    ) -> str:
        """Create a new session with a fresh random sid; return the sid."""
        ...

    def get(self, sid: str, *, now: int | None = None) -> "SessionRecord | None":
        """Return the session record for *sid*, or None if not found / expired."""
        ...

    def delete(self, sid: str) -> None:
        """Delete the session for *sid* (logout invalidation)."""
        ...


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Server-side session record stored in the SessionStore."""

    sid: str
    role: str
    tenant_id: str
    created_at: int
    expires_at: int


class InMemorySessionStore:
    """In-memory dict-backed session store (MVP).

    Thread-safe via a ``threading.Lock`` — safe for ``ThreadingHTTPServer``.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def create(
        self, *, role: Role, tenant_id: str, ttl_seconds: int, now: int
    ) -> str:
        sid = secrets.token_urlsafe(32)
        record = SessionRecord(
            sid=sid,
            role=role.value if isinstance(role, Role) else str(role),
            tenant_id=tenant_id,
            created_at=int(now),
            expires_at=int(now) + int(ttl_seconds),
        )
        with self._lock:
            self._sessions[sid] = record
        return sid

    def get(self, sid: str, *, now: int | None = None) -> SessionRecord | None:
        now_int = int(now if now is not None else time.time())
        with self._lock:
            record = self._sessions.get(sid)
            if record is None:
                return None
            if record.expires_at <= now_int:
                del self._sessions[sid]
                return None
            return record

    def delete(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_session_cookie(
    secret: str,
    sid: str,
    *,
    role: Role | str,
    tenant_id: str,
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    now: int | None = None,
) -> str:
    """Issue an HMAC-SHA256 signed session cookie value.

    Returns ``base64url(payload).base64url(signature)`` where payload
    contains ``sid``, ``role``, ``tenant_id``, ``iat``, ``exp``.
    """
    iat = int(now if now is not None else time.time())
    exp = iat + int(ttl_seconds)
    role_value = role.value if isinstance(role, Role) else str(role)
    payload = {
        "sid": sid,
        "role": role_value,
        "tenant_id": tenant_id,
        "iat": iat,
        "exp": exp,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


def verify_session_cookie(
    cookie_value: str,
    secret: str,
    session_store: SessionStore | None,
    now: int | None = None,
) -> SessionRecord | None:
    """Verify a session cookie's signature and store presence.

    Returns a ``SessionRecord`` only when: the format is valid, the
    signature matches (``hmac.compare_digest``), the ``sid`` exists in
    ``session_store``, and ``exp > now``.  Returns ``None`` on any
    failure — never raises.
    """
    now_int = int(now if now is not None else time.time())
    if not isinstance(cookie_value, str) or cookie_value.count(".") != 1:
        return None
    payload_b64, sig_b64 = cookie_value.split(".")
    try:
        payload_json = _b64url_decode(payload_b64).decode("utf-8")
        provided_sig = _b64url_decode(sig_b64)
    except Exception:
        return None
    expected_sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    try:
        payload = json.loads(payload_json)
    except Exception:
        return None
    try:
        sid = str(payload["sid"])
        role = str(payload["role"])
        tenant_id = str(payload["tenant_id"])
        iat = int(payload["iat"])
        exp = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return None
    if exp <= now_int:
        return None
    if session_store is None:
        return None
    record = session_store.get(sid, now=now_int)
    if record is None:
        return None
    return record


def parse_cookie_header(cookie_header: str | None, name: str) -> str | None:
    """Extract the value of cookie *name* from a Cookie header string.

    Returns ``None`` when the header is missing or the cookie is absent.
    """
    if cookie_header is None:
        return None
    c = SimpleCookie()
    try:
        c.load(cookie_header)
    except Exception:
        return None
    morsel = c.get(name)
    if morsel is None:
        return None
    return morsel.value


__all__ = [
    "DEFAULT_SESSION_TTL_SECONDS",
    "SESSION_COOKIE_NAME",
    "SessionStore",
    "SessionRecord",
    "InMemorySessionStore",
    "issue_session_cookie",
    "verify_session_cookie",
    "parse_cookie_header",
]
