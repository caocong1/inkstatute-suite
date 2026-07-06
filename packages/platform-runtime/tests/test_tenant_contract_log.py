from __future__ import annotations

import unittest

from platform_runtime import (
    InMemoryContractLogStore,
    RuntimeFeatureFlags,
    TenantScope,
    TenantScopeError,
    TenantScopedContractLogStore,
)


class TenantScopedContractLogStoreDisabledTests(unittest.TestCase):
    def _store(self) -> TenantScopedContractLogStore:
        return TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=RuntimeFeatureFlags(),
        )

    def test_disabled_append_delegates_without_tenant_tagging(self) -> None:
        store = self._store()
        entry = store.append("agent_turn", {"turn_id": "t-1", "content_ref": "ref-1"})
        self.assertIsNone(entry.event.get("tenant_id"))

    def test_disabled_entries_returns_all(self) -> None:
        store = self._store()
        store.append("agent_turn", {"turn_id": "t-1"}, scope=TenantScope(tenant_id="firm-a"))
        store.append("agent_turn", {"turn_id": "t-2"}, scope=TenantScope(tenant_id="firm-b"))
        all_entries = store.entries()
        self.assertEqual(len(all_entries), 2)

    def test_disabled_entries_for_run_returns_all(self) -> None:
        store = self._store()
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
        run_entries = store.entries_for_run("run-1")
        self.assertEqual(len(run_entries), 2)


class TenantScopedContractLogStoreEnabledTests(unittest.TestCase):
    def _store(self) -> TenantScopedContractLogStore:
        return TenantScopedContractLogStore(
            delegate=InMemoryContractLogStore(),
            feature_flags=RuntimeFeatureFlags(multi_tenant_enabled=True),
        )

    def test_enabled_append_tags_event_with_tenant_id(self) -> None:
        store = self._store()
        entry = store.append(
            "agent_turn",
            {"turn_id": "t-1"},
            scope=TenantScope(tenant_id="firm-a"),
        )
        self.assertEqual(entry.event.get("tenant_id"), "firm-a")

    def test_enabled_append_tags_event_with_workspace_id(self) -> None:
        store = self._store()
        entry = store.append(
            "agent_turn",
            {"turn_id": "t-1"},
            scope=TenantScope(tenant_id="firm-a", workspace_id="ws-1"),
        )
        self.assertEqual(entry.event.get("tenant_id"), "firm-a")
        self.assertEqual(entry.event.get("workspace_id"), "ws-1")

    def test_enabled_append_tags_partition_path(self) -> None:
        store = self._store()
        entry = store.append(
            "agent_turn",
            {"turn_id": "t-1"},
            scope=TenantScope(tenant_id="firm-a", workspace_id="ws-1"),
        )
        self.assertEqual(entry.event.get("_tenant_partition"), "tenants/firm-a/workspaces/ws-1/")

    def test_enabled_append_without_scope_raises(self) -> None:
        store = self._store()
        with self.assertRaises(TenantScopeError):
            store.append("agent_turn", {"turn_id": "t-1"})

    def test_enabled_append_with_unresolved_scope_raises(self) -> None:
        store = self._store()
        with self.assertRaises(TenantScopeError):
            store.append("agent_turn", {"turn_id": "t-1"}, scope=TenantScope.NONE)

    def test_enabled_entries_filters_by_tenant(self) -> None:
        store = self._store()
        store.append("agent_turn", {"turn_id": "t-1"}, scope=TenantScope(tenant_id="firm-a"))
        store.append("agent_turn", {"turn_id": "t-2"}, scope=TenantScope(tenant_id="firm-b"))
        firm_a_entries = store.entries(scope=TenantScope(tenant_id="firm-a"))
        self.assertEqual(len(firm_a_entries), 1)
        self.assertEqual(firm_a_entries[0].event.get("tenant_id"), "firm-a")
        self.assertEqual(firm_a_entries[0].event.get("turn_id"), "t-1")

    def test_enabled_entries_without_scope_raises(self) -> None:
        store = self._store()
        with self.assertRaises(TenantScopeError):
            store.entries()

    def test_enabled_entries_with_unresolved_scope_raises(self) -> None:
        store = self._store()
        with self.assertRaises(TenantScopeError):
            store.entries(scope=TenantScope.NONE)

    def test_enabled_entries_for_run_filters_by_tenant(self) -> None:
        store = self._store()
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
        firm_a_entries = store.entries_for_run("run-1", scope=TenantScope(tenant_id="firm-a"))
        self.assertEqual(len(firm_a_entries), 1)
        self.assertEqual(firm_a_entries[0].event.get("tenant_id"), "firm-a")

    def test_enabled_entries_for_run_without_scope_raises(self) -> None:
        store = self._store()
        with self.assertRaises(TenantScopeError):
            store.entries_for_run("run-1")

    def test_partition_path_with_workspace(self) -> None:
        path = TenantScopedContractLogStore.partition_path(
            TenantScope(tenant_id="firm-a", workspace_id="ws-1"),
        )
        self.assertEqual(path, "tenants/firm-a/workspaces/ws-1/")

    def test_partition_path_without_workspace(self) -> None:
        path = TenantScopedContractLogStore.partition_path(
            TenantScope(tenant_id="firm-a"),
        )
        self.assertEqual(path, "tenants/firm-a/")

    def test_partition_path_unresolved(self) -> None:
        path = TenantScopedContractLogStore.partition_path(TenantScope.NONE)
        self.assertEqual(path, "")

    def test_enabled_no_cross_tenant_leakage(self) -> None:
        """Firm-a entries are not visible to firm-b and vice versa."""
        store = self._store()
        store.append("agent_turn", {"turn_id": "t-a"}, scope=TenantScope(tenant_id="firm-a"))
        store.append("agent_turn", {"turn_id": "t-b"}, scope=TenantScope(tenant_id="firm-b"))

        firm_a = store.entries(scope=TenantScope(tenant_id="firm-a"))
        firm_b = store.entries(scope=TenantScope(tenant_id="firm-b"))

        self.assertEqual(len(firm_a), 1)
        self.assertEqual(firm_a[0].event.get("turn_id"), "t-a")
        self.assertEqual(len(firm_b), 1)
        self.assertEqual(firm_b[0].event.get("turn_id"), "t-b")


if __name__ == "__main__":
    unittest.main()
