"""Tests for ContractLogMemoryObserver (MEM-16 closure)."""

from __future__ import annotations

import unittest

from platform_runtime.memory_events import (
    ContractLogMemoryObserver,
    MemoryOperationEvent,
)


class FakeContractLogStore:
    """Minimal ContractLogStore double for tests."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, object]]] = []

    def append(self, event_key: str, event: dict[str, object]) -> None:
        self.entries.append((event_key, event))


class ContractLogMemoryObserverTests(unittest.TestCase):
    def test_writes_event_to_contract_log(self) -> None:
        store = FakeContractLogStore()
        observer = ContractLogMemoryObserver(store)

        event = MemoryOperationEvent(
            operation="retain",
            bank_id="tenant:ws:user",
            status="success",
            latency_ms=12.5,
        )
        observer.on_memory_event(event)

        self.assertEqual(len(store.entries), 1)
        key, payload = store.entries[0]
        self.assertEqual(key, "memory_operation")
        self.assertEqual(payload["operation"], "retain")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["bank_id"], "tenant:ws:user")
        self.assertEqual(payload["latency_ms"], 12.5)

    def test_custom_event_key(self) -> None:
        store = FakeContractLogStore()
        observer = ContractLogMemoryObserver(store, event_key="memory_op")

        observer.on_memory_event(
            MemoryOperationEvent(operation="recall", bank_id="b", status="success")
        )

        self.assertEqual(store.entries[0][0], "memory_op")

    def test_failure_event_recorded(self) -> None:
        store = FakeContractLogStore()
        observer = ContractLogMemoryObserver(store)

        observer.on_memory_event(
            MemoryOperationEvent(
                operation="retain",
                bank_id="b",
                status="error",
                category="transient",
                error_code="transient",
                retry_count=2,
            )
        )

        payload = store.entries[0][1]
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["category"], "transient")
        self.assertEqual(payload["retry_count"], 2)

    def test_multiple_events_accumulate(self) -> None:
        store = FakeContractLogStore()
        observer = ContractLogMemoryObserver(store)

        for i in range(5):
            observer.on_memory_event(
                MemoryOperationEvent(operation="retain", bank_id=f"b{i}", status="success")
            )

        self.assertEqual(len(store.entries), 5)


if __name__ == "__main__":
    unittest.main()
