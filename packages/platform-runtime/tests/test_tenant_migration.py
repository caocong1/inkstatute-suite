"""Migration test: no null tenant_id in any persisted record when enabled.

When ``multi_tenant_enabled=True``, every persisted record (contract log
entries, cache keys, memory queries) must carry a non-null, non-empty
``tenant_id``.  When ``False``, null ``tenant_id`` is allowed (v1.6 behavior).
"""

from __future__ import annotations

import unittest

from platform_runtime import (
    InMemoryContractLogStore,
    RuntimeFeatureFlags,
    TenantGuard,
    TenantNamespacedCache,
    TenantScope,
    TenantScopeError,
    TenantScopedContractLogStore,
)
from platform_runtime.memory import MemoryQuery


class TenantMigrationEnabledTests(unittest.TestCase):
    """When multi_tenant_enabled=True, no null tenant_id in persisted records."""

    def _flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags(multi_tenant_enabled=True)

    def test_contract_log_no_null_tenant_id_when_enabled(self) -> None:
        store = TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=self._flags(),
        )
        store.append("agent_turn", {"turn_id": "t-1"}, scope=TenantScope(tenant_id="firm-a"))
        store.append("agent_turn", {"turn_id": "t-2"}, scope=TenantScope(tenant_id="firm-b"))

        for scope_tenant in ("firm-a", "firm-b"):
            entries = store.entries(scope=TenantScope(tenant_id=scope_tenant))
            for entry in entries:
                tid = entry.event.get("tenant_id")
                self.assertIsNotNone(tid, f"entry has null tenant_id: {entry.event_key}")
                self.assertNotEqual(tid, "", f"entry has empty tenant_id: {entry.event_key}")
                self.assertEqual(tid, scope_tenant)

    def test_cache_keys_namespaced_when_enabled(self) -> None:
        cache = TenantNamespacedCache(feature_flags=self._flags())
        cache.set(TenantScope(tenant_id="firm-a"), "key-1", "val-a")
        cache.set(TenantScope(tenant_id="firm-b"), "key-2", "val-b")

        for key in cache.keys():
            self.assertTrue(key.startswith("tenant:"), f"key {key!r} lacks tenant: prefix")
            # Key must contain a non-empty tenant_id between "tenant:" and the next ":"
            parts = key.split(":", 2)
            self.assertEqual(len(parts), 3, f"key {key!r} does not have 3 parts")
            self.assertTrue(parts[1], f"key {key!r} has empty tenant_id in namespace")

    def test_memory_query_tenant_id_not_null_when_enabled(self) -> None:
        query = MemoryQuery(
            tenant_id="firm-a",
            workspace_id="ws-1",
            user_id="user-1",
            session_id="s-1",
        )
        self.assertIsNotNone(query.tenant_id)
        self.assertNotEqual(query.tenant_id, "")

    def test_tenant_guard_rejects_null_scope_when_enabled(self) -> None:
        guard = TenantGuard(feature_flags=self._flags())
        with self.assertRaises(TenantScopeError):
            guard.enforce(TenantScope.NONE)

    def test_tenant_guard_returns_active_filter_for_resolved_scope(self) -> None:
        guard = TenantGuard(feature_flags=self._flags())
        f = guard.enforce(TenantScope(tenant_id="firm-a"))
        self.assertTrue(f.is_active)
        self.assertEqual(f.tenant_id, "firm-a")

    def test_all_tenant_scoped_entities_have_tenant_id_when_enabled(self) -> None:
        """Integration: contract log + cache records all carry tenant_id."""
        flags = self._flags()
        log_store = TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=flags,
        )
        cache = TenantNamespacedCache(feature_flags=flags)
        scope = TenantScope(tenant_id="firm-a", workspace_id="ws-1")

        # Write records
        log_store.append("agent_turn", {"turn_id": "t-1"}, scope=scope)
        log_store.append("agent_result", {"turn_id": "t-1"}, scope=scope)
        cache.set(scope, "session-state", {"key": "value"})

        # Verify contract log entries
        entries = log_store.entries(scope=scope)
        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertEqual(entry.event.get("tenant_id"), "firm-a")
            self.assertEqual(entry.event.get("workspace_id"), "ws-1")

        # Verify cache keys
        for key in cache.keys():
            self.assertIn("firm-a", key)
            self.assertTrue(key.startswith("tenant:firm-a:"))

    def test_contract_log_entries_for_run_filtered_by_tenant(self) -> None:
        """entries_for_run returns only entries for the resolved tenant."""
        store = TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=self._flags(),
        )
        store.append(
            "agent_turn",
            {"run_id": "run-1", "turn_id": "t-1"},
            scope=TenantScope(tenant_id="firm-a"),
        )
        store.append(
            "agent_turn",
            {"run_id": "run-1", "turn_id": "t-2"},
            scope=TenantScope(tenant_id="firm-b"),
        )
        firm_a = store.entries_for_run("run-1", scope=TenantScope(tenant_id="firm-a"))
        for entry in firm_a:
            self.assertEqual(entry.event.get("tenant_id"), "firm-a")
        self.assertEqual(len(firm_a), 1)


class TenantMigrationDisabledTests(unittest.TestCase):
    """When multi_tenant_enabled=False, null tenant_id is allowed (v1.6)."""

    def _flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags()

    def test_contract_log_null_tenant_id_allowed_when_disabled(self) -> None:
        store = TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=self._flags(),
        )
        # Append without scope — no tenant_id tagging
        entry = store.append("agent_turn", {"turn_id": "t-1"})
        self.assertIsNone(entry.event.get("tenant_id"))
        # entries() returns all without filtering
        all_entries = store.entries()
        self.assertEqual(len(all_entries), 1)

    def test_cache_keys_not_namespaced_when_disabled(self) -> None:
        cache = TenantNamespacedCache(feature_flags=self._flags())
        cache.set(TenantScope.NONE, "foo", "bar")
        self.assertIn("foo", cache.keys())
        for key in cache.keys():
            self.assertFalse(key.startswith("tenant:"))

    def test_tenant_guard_allows_null_scope_when_disabled(self) -> None:
        guard = TenantGuard(feature_flags=self._flags())
        f = guard.enforce(TenantScope.NONE)
        self.assertFalse(f.is_active)

    def test_tenant_guard_returns_disabled_filter_for_resolved_scope_when_disabled(self) -> None:
        """Even with a resolved scope, disabled mode returns inactive filter."""
        guard = TenantGuard(feature_flags=self._flags())
        f = guard.enforce(TenantScope(tenant_id="firm-a"))
        self.assertFalse(f.is_active)


if __name__ == "__main__":
    unittest.main()
