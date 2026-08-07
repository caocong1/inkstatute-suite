"""Gateway login handler — unauthenticated session creation endpoint.

This is the ONLY endpoint that bypasses ``require_auth``. It creates a
session and issues a cookie so that subsequent requests are authenticated.

When ``config.rbac_enabled == False`` (dev mode): accepts any credentials
(or no credentials), uses ``tenant_id`` from body or ``config.default_tenant_id``,
uses ``user_id`` from body or ``"web-user"``.

When ``config.rbac_enabled == True``: validates ``token`` against the
static token configured in ``GatewayAuth``. If the token matches, a session
is created. Otherwise, a 401 is returned.

The dev-mode cookie omits the ``Secure`` flag and uses ``SameSite=Lax``
so that HTTP localhost works. The production cookie uses ``Secure;
SameSite=Strict`` (from ``build_set_cookie_header``).
"""

from __future__ import annotations

from typing import Any, Mapping

from rbac.roles import Role
from rbac.session import DEFAULT_SESSION_TTL_SECONDS, SESSION_COOKIE_NAME

from .auth import GatewayAuth
from .config import GatewayConfig
from .sessions import GatewaySessionManager

JsonObject = dict[str, Any]


def build_dev_set_cookie_header(cookie_value: str, *, max_age: int = DEFAULT_SESSION_TTL_SECONDS) -> str:
    """Build a ``Set-Cookie`` header for dev mode (HTTP localhost).

    Omits the ``Secure`` flag (so the browser stores the cookie over HTTP)
    and uses ``SameSite=Lax`` (so dev navigation works).
    """
    return f"{SESSION_COOKIE_NAME}={cookie_value}; Max-Age={max_age}; HttpOnly; SameSite=Lax"


class GatewayLoginHandler:
    """Handle POST /v1/auth/login — the only unauthenticated endpoint.

    This handler is called BEFORE ``require_auth`` in ``GatewayApp.dispatch()``.
    It validates credentials (if RBAC is enabled) and creates a session.
    """

    def __init__(
        self,
        session_manager: GatewaySessionManager,
        auth: GatewayAuth,
        config: GatewayConfig,
    ) -> None:
        self._session_manager = session_manager
        self._auth = auth
        self._config = config

    def handle_login(self, body: Mapping[str, object]) -> JsonObject:
        """Process a login request and return a session response.

        Raises ``GatewayError`` with ``code="invalid_credentials"`` and
        ``status=401`` when credentials are invalid.
        """
        tenant_id = str(body.get("tenant_id") or self._config.default_tenant_id)
        user_id = str(body.get("user_id") or "web-user")
        token = body.get("token")
        conversation_id = str(body.get("conversation_id") or f"conv-{tenant_id}")

        if self._config.rbac_enabled:
            # RBAC mode: validate token against the static token.
            static_token = self._auth._static_token  # type: ignore[attr-defined]
            if not token or token != static_token:
                from .app import GatewayError
                raise GatewayError(
                    "Invalid credentials",
                    code="invalid_credentials",
                    status=401,
                )

        session_id, cookie_value, session = self._session_manager.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role=Role.LAWYER,
        )

        # In dev mode (rbac_enabled=False), use the dev cookie (no Secure flag).
        if self._config.rbac_enabled:
            from .sessions import build_set_cookie_header
            set_cookie = build_set_cookie_header(cookie_value)
        else:
            set_cookie = build_dev_set_cookie_header(cookie_value)

        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "set_cookie": set_cookie,
            "status": "ok",
        }


__all__ = [
    "GatewayLoginHandler",
    "build_dev_set_cookie_header",
]
