"""Threading proof for shared-state wrappers used by the Admin Web UI."""

from __future__ import annotations

import threading
import unittest

from admin_console_api.feedback import ThreadSafeFeedbackQueue


class ThreadSafeFeedbackQueueCompatibilityTests(unittest.TestCase):
    """The feedback queue behaves like an iterable, truthy list for the UI."""

    def test_iterable_and_truthy(self) -> None:
        queue = ThreadSafeFeedbackQueue()
        self.assertFalse(queue)
        queue.append({"id": "fb-1", "status": "pending"})
        self.assertTrue(queue)
        self.assertEqual(len(queue), 1)
        self.assertEqual([item["id"] for item in queue], ["fb-1"])

    def test_snapshot_iteration(self) -> None:
        queue = ThreadSafeFeedbackQueue([{"id": "1"}, {"id": "2"}])
        # Iteration returns a snapshot, so concurrent appends do not affect it.
        items = list(queue)
        queue.append({"id": "3"})
        self.assertEqual(len(items), 2)
        self.assertEqual(len(queue), 3)

    def test_concurrent_append(self) -> None:
        queue = ThreadSafeFeedbackQueue()
        threads = [
            threading.Thread(target=lambda: queue.append({"id": "x", "status": "pending"}))
            for _ in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(queue), 50)


if __name__ == "__main__":
    unittest.main()
