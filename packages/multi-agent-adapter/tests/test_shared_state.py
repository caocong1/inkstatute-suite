"""Tests for SharedStateStore copy-on-write isolation."""

from __future__ import annotations

import unittest

from inkstatute_multi_agent_adapter import SharedStateStore


class TestSharedStateStore(unittest.TestCase):
    def test_init_stores_deep_copy(self) -> None:
        store = SharedStateStore()
        initial = {"key": "value", "nested": {"a": 1}}
        store.init("run-001", initial)
        # Mutating the original does not affect stored state.
        initial["key"] = "changed"
        initial["nested"]["a"] = 999
        snap = store.snapshot("run-001")
        self.assertEqual(snap["key"], "value")
        self.assertEqual(snap["nested"]["a"], 1)

    def test_snapshot_returns_copy_not_reference(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"x": 1})
        snap1 = store.snapshot("run-001")
        snap1["x"] = 999
        snap2 = store.snapshot("run-001")
        self.assertEqual(snap2["x"], 1)

    def test_write_creates_cow_copy(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        store.write("run-001", "agent-a", "local", 42)
        # Agent has a COW copy.
        self.assertTrue(store.has_cow_copy("run-001", "agent-a"))
        # Shared state is NOT mutated.
        self.assertNotIn("local", store.snapshot("run-001"))
        # Agent state reflects the write.
        agent_state = store.agent_state("run-001", "agent-a")
        self.assertEqual(agent_state["local"], 42)
        self.assertEqual(agent_state["shared"], 1)

    def test_write_all_batch(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"base": 0})
        store.write_all("run-001", "agent-a", {"a": 1, "b": 2})
        state = store.agent_state("run-001", "agent-a")
        self.assertEqual(state["a"], 1)
        self.assertEqual(state["b"], 2)
        self.assertEqual(state["base"], 0)

    def test_commit_merges_into_shared(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        store.write_all("run-001", "agent-a", {"new": 99})
        store.commit("run-001", "agent-a")
        snap = store.snapshot("run-001")
        self.assertEqual(snap["shared"], 1)
        self.assertEqual(snap["new"], 99)

    def test_cross_agent_writes_do_not_mutate_shared(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        store.write_all("run-001", "agent-a", {"a_key": "a_val"})
        store.write_all("run-001", "agent-b", {"b_key": "b_val"})
        # Shared state unchanged.
        shared = store.snapshot("run-001")
        self.assertNotIn("a_key", shared)
        self.assertNotIn("b_key", shared)
        # Agent A does not see Agent B's writes.
        state_a = store.agent_state("run-001", "agent-a")
        self.assertNotIn("b_key", state_a)
        # Agent B does not see Agent A's writes.
        state_b = store.agent_state("run-001", "agent-b")
        self.assertNotIn("a_key", state_b)

    def test_agent_state_returns_snapshot_when_no_writes(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        state = store.agent_state("run-001", "agent-a")
        self.assertEqual(state["shared"], 1)
        self.assertFalse(store.has_cow_copy("run-001", "agent-a"))

    def test_commit_without_cow_raises(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        with self.assertRaises(KeyError):
            store.commit("run-001", "agent-a")

    def test_dispose_cleans_up(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"shared": 1})
        store.write("run-001", "agent-a", "x", 1)
        store.dispose("run-001")
        with self.assertRaises(KeyError):
            store.snapshot("run-001")

    def test_deep_copy_isolation_on_cow_creation(self) -> None:
        store = SharedStateStore()
        store.init("run-001", {"nested": {"a": 1}})
        store.write("run-001", "agent-a", "new", 2)
        # Mutating the COW copy's nested dict should not affect shared.
        state = store.agent_state("run-001", "agent-a")
        state["nested"]["a"] = 999
        shared = store.snapshot("run-001")
        self.assertEqual(shared["nested"]["a"], 1)


if __name__ == "__main__":
    unittest.main()
