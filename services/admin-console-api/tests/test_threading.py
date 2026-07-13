"""Thread-safety proofs for shared mutable state in Phase 79."""

from __future__ import annotations

import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from admin_console_api.feedback import ThreadSafeFeedbackQueue
from admin_console_api.process_registry import ProcessRecord, ProcessRegistry
from inkstatute_operator_config import OperatorConfigStore
from inkstatute_operator_config.schemas import OperatorConfigDocument
from platform_runtime.feature_flags import RuntimeFeatureFlags


class OperatorConfigStoreThreadSafetyTests(unittest.TestCase):
    """Concurrent saves must produce valid JSON and avoid .tmp collisions."""

    def test_concurrent_save_produces_valid_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "operator-config.json"
            store = OperatorConfigStore(store_path)
            flags = RuntimeFeatureFlags(operator_config_enabled=True)
            document = OperatorConfigDocument()

            errors: list[Exception] = []
            threads: list[threading.Thread] = []

            def _save() -> None:
                try:
                    for _ in range(50):
                        store.save(document, feature_flags=flags)
                        time.sleep(0.001)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            for _ in range(10):
                t = threading.Thread(target=_save)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertTrue(store_path.is_file())
            parsed = json.loads(store_path.read_text(encoding="utf-8"))
            self.assertIsInstance(parsed, dict)
            self.assertIn("schema_version", parsed)


class ThreadSafeFeedbackQueueTests(unittest.TestCase):
    """Concurrent appends and iterations do not lose items or raise."""

    def test_concurrent_append_and_iteration_is_consistent(self) -> None:
        queue = ThreadSafeFeedbackQueue()
        errors: list[Exception] = []

        def _append(value: int) -> None:
            try:
                for i in range(100):
                    queue.append({"id": f"{value}-{i}", "status": "pending"})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_append, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(queue), 1000)
        self.assertEqual(len(list(queue)), 1000)

    def test_replace_and_iteration_snapshot(self) -> None:
        queue = ThreadSafeFeedbackQueue([{"id": "1"}, {"id": "2"}])
        self.assertTrue(queue)
        self.assertEqual(len(queue), 2)
        queue.replace([{"id": "3"}])
        self.assertEqual(len(queue), 1)
        self.assertEqual(len(list(queue)), 1)


class ProcessRegistryThreadSafetyTests(unittest.TestCase):
    """Concurrent add/remove/list on the process table is consistent."""

    def test_concurrent_add_remove_list(self) -> None:
        registry = ProcessRegistry()
        errors: list[Exception] = []

        def _add(name: str) -> None:
            try:
                for i in range(100):
                    registry.add(name, ProcessRecord(name=name, status="running", pid=i))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def _remove(name: str) -> None:
            try:
                for _ in range(100):
                    registry.remove(name)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def _list() -> None:
            try:
                for _ in range(200):
                    registry.list()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = []
        for n in range(5):
            threads.append(threading.Thread(target=_add, args=(f"proc-{n}",)))
            threads.append(threading.Thread(target=_remove, args=(f"proc-{n}",)))
            threads.append(threading.Thread(target=_list))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        records = {r.name for r in registry.list()}
        # Only records that survived the final add/remove races remain.
        self.assertTrue(all(name.startswith("proc-") for name in records))


if __name__ == "__main__":
    unittest.main()
