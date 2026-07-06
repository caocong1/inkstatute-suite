"""Tenant-namespaced cache — prefixes cache keys by tenant_id.

When ``multi_tenant_enabled=False``, keys are stored without namespacing
(v1.6 behavior).  When enabled, every key is prefixed with
``tenant:{tenant_id}:`` ensuring no cross-tenant cache leakage.
"""

from __future__ import annotations

from typing import Any

from .feature_flags import RuntimeFeatureFlags
from .tenant_scope import TenantScope, TenantScopeError


class TenantNamespacedCache:
    """In-memory dict cache with tenant key namespacing."""

    def __init__(self, *, feature_flags: RuntimeFeatureFlags) -> None:
        self._feature_flags = feature_flags
        self._cache: dict[str, Any] = {}

    def get(self, scope: TenantScope, key: str) -> Any | None:
        """Get a value by key, namespaced by tenant when enabled.

        Raises ``TenantScopeError`` when enabled but scope is unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return self._cache.get(key)
        if not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for cache get"
            )
        return self._cache.get(self._namespaced_key(scope, key))

    def set(self, scope: TenantScope, key: str, value: Any) -> None:
        """Set a value by key, namespaced by tenant when enabled.

        Raises ``TenantScopeError`` when enabled but scope is unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            self._cache[key] = value
            return
        if not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for cache set"
            )
        self._cache[self._namespaced_key(scope, key)] = value

    def delete(self, scope: TenantScope, key: str) -> bool:
        """Delete a key, namespaced by tenant when enabled.

        Returns ``True`` if the key existed and was deleted, ``False`` otherwise.

        Raises ``TenantScopeError`` when enabled but scope is unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return self._cache.pop(key, None) is not None
        if not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for cache delete"
            )
        return self._cache.pop(self._namespaced_key(scope, key), None) is not None

    def keys(self) -> tuple[str, ...]:
        """Return all cache keys (for inspection/testing)."""
        return tuple(self._cache.keys())

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def _namespaced_key(self, scope: TenantScope, key: str) -> str:
        """Return the tenant-namespaced key."""
        return f"tenant:{scope.tenant_id}:{key}"


__all__ = ["TenantNamespacedCache"]
