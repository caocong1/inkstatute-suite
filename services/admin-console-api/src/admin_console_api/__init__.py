"""Read-only Admin Console API for InkStatute V2 operator views."""

from .auth import check_auth_header, resolve_admin_token

__all__ = ["resolve_admin_token", "check_auth_header"]
