"""Role-based access control for InkStatute admin APIs."""

from .guard import RbacGuard
from .identity import Identity, resolve_identity
from .matrix import PERMISSIONS_MATRIX
from .roles import Role
from .token import (
    DEFAULT_TOKEN_TTL_SECONDS,
    RbacTokenClaims,
    RbacTokenError,
    issue_token,
    verify_token,
)

__all__ = [
    "DEFAULT_TOKEN_TTL_SECONDS",
    "PERMISSIONS_MATRIX",
    "Identity",
    "RbacTokenClaims",
    "RbacTokenError",
    "Role",
    "RbacGuard",
    "issue_token",
    "resolve_identity",
    "verify_token",
]
