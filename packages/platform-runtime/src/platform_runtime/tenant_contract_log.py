"""Tenant-scoped contract log store — partitions entries by tenant_id/workspace_id path.

Wraps a ``ContractLogStore`` delegate (e.g. ``InMemoryContractLogStore``) and
injects ``tenant_id``/``workspace_id`` into event metadata on append, then
filters retrieval by tenant on read.  When ``multi_tenant_enabled=False``,
delegates directly with no tenant tagging — preserving v1.6 behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

from .feature_flags import RuntimeFeatureFlags
from .store import ContractLogEntry
from .tenant_scope import TenantScope, TenantScopeError


class TenantScopedContractLogStore:
    """ContractLogStore wrapper that partitions entries by tenant scope."""

    def __init__(
        self,
        delegate: Any,
        *,
        feature_flags: RuntimeFeatureFlags,
    ) -> None:
        self._delegate = delegate
        self._feature_flags = feature_flags

    def append(
        self,
        event_key: str,
        event: Mapping[str, Any],
        *,
        scope: TenantScope | None = None,
        occurred_at: str | None = None,
        ingested_at: str | None = None,
    ) -> ContractLogEntry:
        """Append an event, tagging it with tenant_id when enabled.

        When ``multi_tenant_enabled=False``, delegates directly with no
        tenant tagging (v1.6 behavior).

        Raises ``TenantScopeError`` when enabled but scope is None or
        unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return self._delegate.append(
                event_key,
                event,
                occurred_at=occurred_at,
                ingested_at=ingested_at,
            )

        if scope is None or not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for contract log append"
            )

        enriched = dict(event)
        enriched["tenant_id"] = scope.tenant_id
        if scope.workspace_id is not None and scope.workspace_id != "":
            enriched["workspace_id"] = scope.workspace_id
        enriched["_tenant_partition"] = self.partition_path(scope)

        return self._delegate.append(
            event_key,
            enriched,
            occurred_at=occurred_at,
            ingested_at=ingested_at,
        )

    def entries(self, *, scope: TenantScope | None = None) -> tuple[ContractLogEntry, ...]:
        """Return entries, filtered by tenant when enabled.

        When disabled, returns all entries (v1.6 behavior).

        Raises ``TenantScopeError`` when enabled but scope is None or
        unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return self._delegate.entries()

        if scope is None or not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for contract log entries"
            )

        all_entries = self._delegate.entries()
        return tuple(
            entry for entry in all_entries
            if entry.event.get("tenant_id") == scope.tenant_id
        )

    def entries_for_run(
        self,
        run_id: str,
        *,
        scope: TenantScope | None = None,
    ) -> tuple[ContractLogEntry, ...]:
        """Return entries for a run, filtered by tenant when enabled.

        When disabled, returns all entries for the run (v1.6 behavior).

        Raises ``TenantScopeError`` when enabled but scope is None or
        unresolved.
        """
        if not self._feature_flags.multi_tenant_enabled:
            return self._delegate.entries_for_run(run_id)

        if scope is None or not scope.is_resolved:
            raise TenantScopeError(
                "multi_tenant_enabled requires resolved tenant scope for contract log entries_for_run"
            )

        all_entries = self._delegate.entries_for_run(run_id)
        return tuple(
            entry for entry in all_entries
            if entry.event.get("tenant_id") == scope.tenant_id
        )

    @staticmethod
    def partition_path(scope: TenantScope) -> str:
        """Return the tenant partition path for the given scope."""
        return scope.partition_path


__all__ = ["TenantScopedContractLogStore"]
