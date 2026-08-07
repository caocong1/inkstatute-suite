"""Auth middleware for the InkStatute Gateway.

Uses ``rbac.identity.resolve_identity()`` for identity resolution — Bearer
token first, session cookie fallback. When ``rbac_enabled=False``, a
static-token fallback is used (v1.6 behavior, returning a default admin
identity).

CRITICAL: The auth middleware NEVER auto-approves any permission. It only
resolves identity — permission decisions are made by the user through
elicitation/approval endpoints, not by the auth layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rbac.identity import Identity, resolve_identity
from rbac.roles import Role
from rbac.session import SESSION_COOKIE_NAME, SessionStore, parse_cookie_header


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Resolved auth context for a Gateway request.

    When ``authenticated`` is ``True``, ``tenant_id`` is always from the
    identity. When ``authenticated`` is ``False``, ``tenant_id`` falls back
    to the ``default_tenant_id`` from config (for self-hosted single-tenant
    mode where auth may be disabled).
    """

    identity: Identity | None
    authenticated: bool
    tenant_id: str
    error: str | None


class GatewayAuthError(Exception):
    """Raised when auth fails or tenant access is denied."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class GatewayAuth:
    """Auth middleware that wraps all Gateway endpoint handlers.

    Calls ``resolve_identity()`` on every request. No endpoint bypasses auth.
    """

    def __init__(
        self,
        *,
        rbac_secret: str | None = None,
        static_token: str | None = None,
        rbac_enabled: bool = False,
        session_store: SessionStore | None = None,
        default_tenant_id: str = "default",
    ) -> None:
        self._rbac_secret = rbac_secret
        self._static_token = static_token
        self._rbac_enabled = rbac_enabled
        self._session_store = session_store
        self._default_tenant_id = default_tenant_id

    def authenticate(self, headers: Mapping[str, str]) -> AuthContext:
        """Resolve identity from headers. Returns an AuthContext (never raises)."""
        auth_header = _get_header(headers, "Authorization")
        cookie_header = _get_header(headers, "Cookie")
        session_cookie = parse_cookie_header(cookie_header, SESSION_COOKIE_NAME)

        identity = resolve_identity(
            auth_header,
            rbac_secret=self._rbac_secret,
            static_token=self._static_token,
            rbac_enabled=self._rbac_enabled,
            session_cookie=session_cookie,
            session_store=self._session_store,
        )

        if identity is not None:
            return AuthContext(
                identity=identity,
                authenticated=True,
                tenant_id=identity.tenant_id,
                error=None,
            )

        return AuthContext(
            identity=None,
            authenticated=False,
            tenant_id=self._default_tenant_id,
            error="Invalid or missing authentication credentials",
        )

    def require_auth(self, headers: Mapping[str, str]) -> AuthContext:
        """Like ``authenticate`` but raises ``GatewayAuthError`` (401) on failure."""
        ctx = self.authenticate(headers)
        if not ctx.authenticated:
            raise GatewayAuthError(
                status=401,
                code="unauthorized",
                message=ctx.error or "Authentication required",
            )
        return ctx

    def require_role(
        self,
        headers: Mapping[str, str],
        allowed_roles: tuple[Role, ...],
    ) -> AuthContext:
        """Like ``require_auth`` but also checks the identity's role."""
        ctx = self.require_auth(headers)
        if ctx.identity is not None and ctx.identity.role not in allowed_roles:
            raise GatewayAuthError(
                status=403,
                code="forbidden",
                message=f"Role '{ctx.identity.role.value}' is not permitted for this endpoint",
            )
        return ctx

    def check_tenant(self, ctx: AuthContext, resource_tenant_id: str | None) -> None:
        """Raise ``GatewayAuthError`` (403) on cross-tenant access.

        When ``resource_tenant_id`` is ``None``, no check is performed
        (resource is not tenant-scoped).
        """
        if resource_tenant_id is None:
            return
        if ctx.tenant_id != resource_tenant_id:
            raise GatewayAuthError(
                status=403,
                code="tenant_mismatch",
                message=f"Cross-tenant access denied: ctx tenant='{ctx.tenant_id}', resource tenant='{resource_tenant_id}'",
            )


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


__all__ = [
    "AuthContext",
    "GatewayAuth",
    "GatewayAuthError",
]
