"""RbacGuard — default-deny role enforcement middleware.

``RbacGuard.check(role, endpoint)`` resolves the endpoint to its matrix entry
by longest-prefix match and returns ``True`` only if the caller's role is in
the allowed set.  Endpoints with no matching prefix are denied by default.
"""

from __future__ import annotations

from .matrix import PERMISSIONS_MATRIX
from .roles import Role


class RbacGuard:
    """Default-deny RBAC guard backed by a permissions matrix."""

    def __init__(self, matrix: dict[str, frozenset[Role]] | None = None) -> None:
        self._matrix: dict[str, frozenset[Role]] = (
            dict(matrix) if matrix is not None else dict(PERMISSIONS_MATRIX)
        )

    def check(self, role: Role, endpoint: str) -> bool:
        """Return ``True`` if *role* may access *endpoint*, else ``False``.

        Unannotated endpoints (no matching matrix prefix) are denied.
        """
        allowed = self._resolve(endpoint)
        if allowed is None:
            return False
        return role in allowed

    def _resolve(self, endpoint: str) -> frozenset[Role] | None:
        """Return the allowed-role set for *endpoint* via longest-prefix match.

        A prefix matches when the endpoint equals it, starts with ``prefix + "/"``,
        or starts with ``prefix + "?"``.
        """
        best: frozenset[Role] | None = None
        best_len = -1
        for prefix, roles in self._matrix.items():
            if (
                endpoint == prefix
                or endpoint.startswith(prefix + "/")
                or endpoint.startswith(prefix + "?")
            ):
                if len(prefix) > best_len:
                    best = roles
                    best_len = len(prefix)
        return best


__all__ = ["RbacGuard"]
