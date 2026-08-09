"""Identity resolution from RBAC tokens with static-token fallback.

``resolve_identity()`` extracts role+tenant claims from a Bearer token when
``rbac_enabled=True``.  When ``rbac_enabled=False``, it falls back to the v1.6
``check_auth_header`` static-token validation, returning a default admin
identity on success — preserving the existing static-token behavior with no
regression.

When ``rbac_enabled=True`` and a Bearer header is absent or invalid, the
function falls back to a session cookie (``session_cookie`` +
``session_store``) via ``rbac.session.verify_session_cookie``.  The Bearer
header always takes priority — the API path is unchanged when a valid
Bearer token is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .roles import Role
from .token import RbacTokenError, verify_token

_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True, slots=True)
class Identity:
    """Resolved caller identity with role and tenant scope."""

    role: Role
    tenant_id: str


def _strip_bearer(header_value: str | None) -> str | None:
    if header_value is None or not header_value.startswith(_BEARER_PREFIX):
        return None
    return header_value[len(_BEARER_PREFIX):]


def resolve_identity(
    auth_header: str | None,
    *,
    rbac_secret: str | None = None,
    static_token: str | None = None,
    rbac_enabled: bool = False,
    now: int | None = None,
    session_cookie: str | None = None,
    session_store: Any = None,
) -> Identity | None:
    """Resolve caller identity from a Bearer token or session cookie.

    When ``rbac_enabled`` is ``True``, the Bearer token is verified first as
    an RBAC HMAC-SHA256 token with role+tenant claims.  When the Bearer token
    is absent or invalid, the function falls back to the ``session_cookie``
    via ``rbac.session.verify_session_cookie`` (browser sessions) — the
    Bearer header always takes priority so the API path is unchanged.

    When ``rbac_enabled`` is ``False``, the function falls back to
    ``check_auth_header`` static-token validation (v1.6 behavior), returning
    a default admin identity on success.

    Returns ``None`` when the token/cookie is invalid, expired, or the role
    is unknown.
    """
    if rbac_enabled:
        # Bearer header takes priority (API path unchanged).
        token = _strip_bearer(auth_header)
        if token is not None and rbac_secret is not None:
            try:
                claims = verify_token(token, rbac_secret, now=now)
            except RbacTokenError:
                claims = None
            if claims is not None:
                try:
                    role = Role(claims.role)
                except ValueError:
                    role = None
                if role is not None:
                    return Identity(role=role, tenant_id=claims.tenant_id)
        # Bearer absent or invalid — try session cookie fallback (browser sessions).
        if session_cookie is not None and rbac_secret is not None and session_store is not None:
            from .session import verify_session_cookie

            record = verify_session_cookie(session_cookie, rbac_secret, session_store, now=now)
            if record is not None:
                try:
                    role = Role(record.role)
                except ValueError:
                    role = None
                if role is not None:
                    return Identity(role=role, tenant_id=record.tenant_id)
        return None

    # Static-token fallback (v1.6 behavior).  The ``admin_console_api.auth``
    # module is imported lazily so the rbac package remains stdlib-only at
    # module top level and testable standalone.  When ``admin_console_api`` is
    # not on the import path (e.g. rbac-only test runs), a local stdlib
    # implementation of the same constant-time Bearer-token comparison is
    # used — preserving identical v1.6 semantics with no external dependency.
    try:
        from admin_console_api.auth import check_auth_header
    except ImportError:
        check_auth_header = _static_token_check

    if check_auth_header(auth_header, static_token):
        return Identity(role=Role.ADMIN, tenant_id="default")

    # Dev-mode cookie fallback: when rbac is off but a session cookie is
    # present (e.g. desktop app logged in via POST /v1/auth/login), verify
    # the cookie with the dev secret so cookie-based auth works in dev mode.
    if session_cookie is not None and rbac_secret is not None and session_store is not None:
        from .session import verify_session_cookie

        record = verify_session_cookie(session_cookie, rbac_secret, session_store, now=now)
        if record is not None:
            try:
                role = Role(record.role)
            except ValueError:
                role = None
            if role is not None:
                return Identity(role=role, tenant_id=record.tenant_id)

    return None


def _static_token_check(header_value: str | None, expected_token: str | None) -> bool:
    """Local fallback for ``check_auth_header`` (v1.6 static-token semantics).

    Returns ``False`` when the token is not configured, the header is missing,
    or the header does not start with ``"Bearer "``.  Uses
    ``hmac.compare_digest`` for constant-time comparison — identical to
    ``admin_console_api.auth.check_auth_header``.
    """
    import hmac

    if expected_token is None:
        return False
    if header_value is None or not header_value.startswith(_BEARER_PREFIX):
        return False
    provided = header_value[len(_BEARER_PREFIX):]
    return hmac.compare_digest(provided, expected_token)


__all__ = ["Identity", "resolve_identity"]
