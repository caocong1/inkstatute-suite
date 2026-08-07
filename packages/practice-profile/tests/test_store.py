"""Tests for PracticeProfileStore and InMemoryPracticeProfileStore (store.py)."""

from __future__ import annotations

import threading
import unittest

from inkstatute_practice_profile import (
    InMemoryPracticeProfileStore,
    PracticeProfile,
    PracticeProfileStore,
    SecretDetectedError,
)
from typing import Protocol


class PracticeProfileStoreProtocolTests(unittest.TestCase):
    def test_is_protocol(self) -> None:
        self.assertTrue(
            hasattr(PracticeProfileStore, "_is_protocol")
            and PracticeProfileStore._is_protocol
        )

    def test_has_four_methods(self) -> None:
        for method in ("get", "upsert", "delete", "list_plugins"):
            self.assertTrue(hasattr(PracticeProfileStore, method))


class InMemoryPracticeProfileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()

    def test_get_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.store.get("t1", "commercial-legal"))

    def test_upsert_and_get_round_trip(self) -> None:
        profile = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "某律所"},
        )
        self.store.upsert("t1", profile)
        result = self.store.get("t1", "commercial-legal")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tenant_id, "t1")
        self.assertEqual(result.plugin, "commercial-legal")
        self.assertEqual(result.identity["org_name"], "某律所")

    def test_upsert_rejects_secrets(self) -> None:
        bad_profile = PracticeProfile(
            tenant_id="t1",
            plugin="test",
            identity={"api_key": "sk-abc123"},
        )
        with self.assertRaises(SecretDetectedError):
            self.store.upsert("t1", bad_profile)
        # The profile should not have been stored
        self.assertIsNone(self.store.get("t1", "test"))

    def test_upsert_rejects_tenant_id_mismatch(self) -> None:
        profile = PracticeProfile(tenant_id="t2", plugin="test")
        with self.assertRaises(ValueError):
            self.store.upsert("t1", profile)

    def test_delete_removes_profile(self) -> None:
        profile = PracticeProfile(tenant_id="t1", plugin="commercial-legal")
        self.store.upsert("t1", profile)
        self.assertIsNotNone(self.store.get("t1", "commercial-legal"))
        self.store.delete("t1", "commercial-legal")
        self.assertIsNone(self.store.get("t1", "commercial-legal"))

    def test_delete_nonexistent_is_noop(self) -> None:
        # Should not raise
        self.store.delete("t1", "nonexistent")

    def test_list_plugins_returns_plugins_for_tenant(self) -> None:
        self.store.upsert("t1", PracticeProfile(tenant_id="t1", plugin="commercial-legal"))
        self.store.upsert("t1", PracticeProfile(tenant_id="t1", plugin="litigation-legal"))
        plugins = self.store.list_plugins("t1")
        self.assertIn("commercial-legal", plugins)
        self.assertIn("litigation-legal", plugins)
        self.assertEqual(len(plugins), 2)

    def test_list_plugins_tenant_isolation(self) -> None:
        self.store.upsert("t1", PracticeProfile(tenant_id="t1", plugin="commercial-legal"))
        self.assertEqual(self.store.list_plugins("t2"), [])

    def test_upsert_overwrites_previous(self) -> None:
        p1 = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "旧律所"},
        )
        self.store.upsert("t1", p1)
        p2 = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "新律所"},
        )
        self.store.upsert("t1", p2)
        result = self.store.get("t1", "commercial-legal")
        assert result is not None
        self.assertEqual(result.identity["org_name"], "新律所")

    def test_thread_safety_smoke_test(self) -> None:
        """Concurrent upserts from multiple threads should not corrupt state."""
        errors: list[Exception] = []

        def worker(tenant: str, plugin: str) -> None:
            try:
                for i in range(50):
                    self.store.upsert(
                        tenant,
                        PracticeProfile(
                            tenant_id=tenant,
                            plugin=plugin,
                            identity={"iteration": str(i)},
                        ),
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=("t1", "commercial-legal")),
            threading.Thread(target=worker, args=("t1", "litigation-legal")),
            threading.Thread(target=worker, args=("t2", "commercial-legal")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # After all threads, each tenant should have its plugins
        self.assertEqual(len(self.store.list_plugins("t1")), 2)
        self.assertEqual(len(self.store.list_plugins("t2")), 1)


if __name__ == "__main__":
    unittest.main()
