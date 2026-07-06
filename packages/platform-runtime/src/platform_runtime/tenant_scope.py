"""Multi-tenant isolation primitives: TenantScopeResolver, TenantGuard, ScopedQueryFilter.

All components are opt-in via the ``multi_tenant_enabled`` feature flag (defaults
to ``False``).  When disabled, ``TenantScopeResolver.resolve()`` returns
``TenantScope.NONE`` and ``TenantGuard.enforce()`` returns a disabled
``ScopedQueryFilter`` — preserving v1.6 behavior with zero regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

from .feature_flags import RuntimeFeatureFlags
from .session_resolver import SessionScope


class TenantScopeError(RuntimeError):
    """Raised when multi_tenant_enabled=True but tenant_id is unresolved."""


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Resolved tenant scope carrying tenant_id and optional workspace_id."""

    tenant_id: str | None = None
    workspace_id: str | None = None

    @property
    def is_resolved(self) -> bool:
        """Return True when tenant_id is not None and not empty."""
        return self.tenant_id is not None and self.tenant_id != ""

    @property
    def partition_path(self) -> str:
        """Return the tenant partition path for filesystem-style storage.

        Path pattern: ``tenants/{tenant_id}/workspaces/{workspace_id}/`` when both
        are present, ``tenants/{tenant_id}/`` when only tenant_id, or ``""``
        when unresolved.
        """
        if not self.is_resolved:
            return ""
        base = f"tenants/{self.tenant_id}/"
        if self.workspace_id is not None and self.workspace_id != "":
            return f"{base}workspaces/{self.workspace_id}/"
        return base


def _none_scope() -> TenantScope:
    """Return the sentinel None-scope for disabled mode."""
    return TenantScope(tenant_id=None, workspace_id=None)


_NONE_SCOPE = TenantScope(tenant_id=None, workspace_id=None)
TenantScope.NONE = _NONE_SCOPE  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ScopedQueryFilter:
    """Tenant filter injected into read-model queries by TenantGuard.

    When ``active=False`` (disabled mode), stores ignore the filter and return
    all records — preserving v1.6 behavior.
    """

    tenant_id: str | None = None
    workspace_id: str | None = None
    active: bool = False

    @classmethod
    def disabled(cls) -> "ScopedQueryFilter":
        """Return an inactive filter (no tenant scoping)."""
        return cls(tenant_id=None, workspace_id=None, active=False)

    @property
    def is_active(self) -> bool:
        """Return True when this filter is active (tenant scoping enforced)."""
        return self.active


@dataclass(frozen=True, slots=True)
class TenantScopeRequestContext:
    """Carries optional resolution inputs for TenantScopeResolver.

    The resolver checks fields in priority order: identity > scope > request >
    headers.  Any field may be None; the resolver uses the first non-None
    source that provides a truthy tenant_id.
    """

    identity: Any = None
    request: Any = None
    scope: SessionScope | None = None
    headers: Mapping[str, str] | None = None


class TenantScopeResolver:
    """Resolve tenant_id from request context using a priority chain.

    Priority: auth token claims (identity) > channel metadata (scope) >
    request metadata (request) > explicit header (X-Tenant-Id).

    When ``multi_tenant_enabled=False``, always returns ``TenantScope.NONE``.
    """

    _TENANT_HEADER = "X-Tenant-Id"

    def __init__(self, *, feature_flags: RuntimeFeatureFlags) -> None:
        self._feature_flags = feature_flags

    def resolve(self, context: TenantScopeRequestContext) -> TenantScope:
        """Resolve TenantScope from the given context.

        Returns ``TenantScope.NONE`` when ``multi_tenant_enabled=False`` or
        when no source provides a truthy tenant_id.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return _NONE_SCOPE

        # Priority 1: auth token claims (identity)
        tenant_id, workspace_id = _extract_from_identity(context.identity)
        if tenant_id:
            return TenantScope(tenant_id=tenant_id, workspace_id=workspace_id)

        # Priority 2: channel metadata (scope)
        tenant_id, workspace_id = _extract_from_scope(context.scope)
        if tenant_id:
            return TenantScope(tenant_id=tenant_id, workspace_id=workspace_id)

        # Priority 3: request metadata (request)
        tenant_id, workspace_id = _extract_from_request(context.request)
        if tenant_id:
            return TenantScope(tenant_id=tenant_id, workspace_id=workspace_id)

        # Priority 4: explicit header
        tenant_id = _extract_from_headers(context.headers)
        if tenant_id:
            return TenantScope(tenant_id=tenant_id, workspace_id=None)

        return _NONE_SCOPE


class TenantGuard:
    """Enforce tenant_id filter on every read-model query.

    When ``multi_tenant_enabled=False``, ``enforce()`` returns a disabled
    ``ScopedQueryFilter`` (no filtering).  When ``True`` and the scope is
    resolved, returns an active filter.  When ``True`` and the scope is
    unresolved, raises ``TenantScopeError`` — no query can bypass scoping.
    """

    def __init__(self, *, feature_flags: RuntimeFeatureFlags) -> None:
        self._feature_flags = feature_flags

    def enforce(self, scope: TenantScope) -> ScopedQueryFilter:
        """Return a ScopedQueryFilter for the given scope.

        Raises ``TenantScopeError`` when ``multi_tenant_enabled=True`` but
        the scope is unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return ScopedQueryFilter.disabled()
        if not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant_id, got None"
            )
        return ScopedQueryFilter(
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            active=True,
        )


# ---------------------------------------------------------------------------
# Internal helpers — extract tenant_id from each priority source
# ---------------------------------------------------------------------------


def _extract_from_identity(identity: Any) -> tuple[str | None, str | None]:
    """Extract tenant_id from an RBAC Identity-like object."""
    if identity is None:
        return None, None
    tenant_id = getattr(identity, "tenant_id", None)
    if tenant_id and isinstance(tenant_id, str) and tenant_id:
        return tenant_id, None
    return None, None


def _extract_from_scope(scope: SessionScope | None) -> tuple[str | None, str | None]:
    """Extract tenant_id and workspace_id from a SessionScope."""
    if scope is None:
        return None, None
    tenant_id = scope.tenant_id
    if tenant_id and isinstance(tenant_id, str) and tenant_id:
        workspace_id = scope.workspace_id
        if workspace_id == "":
            workspace_id = None
        return tenant_id, workspace_id
    return None, None


def _extract_from_request(request: Any) -> tuple[str | None, str | None]:
    """Extract tenant_id and workspace_id from a RunRequest-like object."""
    if request is None:
        return None, None
    tenant_id = getattr(request, "tenant_id", None)
    if tenant_id and isinstance(tenant_id, str) and tenant_id:
        workspace_id = getattr(request, "workspace_id", None)
        if workspace_id == "":
            workspace_id = None
        return tenant_id, workspace_id
    return None, None


def _extract_from_headers(headers: Mapping[str, str] | None) -> str | None:
    """Extract tenant_id from the X-Tenant-Id header."""
    if headers is None:
        return None
    # Case-insensitive header lookup
    for key, value in headers.items():
        if key.lower() == "x-tenant-id" and value:
            return str(value)
    return None


__all__ = [
    "ScopedQueryFilter",
    "TenantGuard",
    "TenantScope",
    "TenantScopeError",
    "TenantScopeRequestContext",
    "TenantScopeResolver",
]
