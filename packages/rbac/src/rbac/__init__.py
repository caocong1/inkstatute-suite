"""Role-based access control for InkStatute admin APIs."""

from .guard import RbacGuard
from .identity import Identity, resolve_identity
from .matrix import PERMISSIONS_MATRIX
from .roles import Role
from .session import (
    DEFAULT_SESSION_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    InMemorySessionStore,
    SessionRecord,
    SessionStore,
    issue_session_cookie,
    parse_cookie_header,
    verify_session_cookie,
)
from .token import (
    DEFAULT_TOKEN_TTL_SECONDS,
    RbacTokenClaims,
    RbacTokenError,
    issue_token,
    verify_token,
)

__all__ = [
    "DEFAULT_SESSION_TTL_SECONDS",
    "DEFAULT_TOKEN_TTL_SECONDS",
    "PERMISSIONS_MATRIX",
    "Identity",
    "InMemorySessionStore",
    "RbacTokenClaims",
    "RbacTokenError",
    "Role",
    "RbacGuard",
    "SESSION_COOKIE_NAME",
    "SessionRecord",
    "SessionStore",
    "issue_session_cookie",
    "issue_token",
    "parse_cookie_header",
    "resolve_identity",
    "verify_session_cookie",
    "verify_token",
]
