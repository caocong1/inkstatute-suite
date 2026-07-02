"""Tests for RetryableMemory wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unittest

from platform_runtime import (
    FakeMemory,
    InMemoryMemoryObserver,
    Memory,
    MemoryFailureCategory,
    MemoryOperationError,
    MemoryRecallInput,
    MemoryRetainInput,
    RetryPolicy,
    RetryableMemory,
)


class FailingMemory:
    """Configurable test double that fails a set number of times."""

    def __init__(self, fail_count: int = 0, error_message: str = "transient error") -> None:
        self.fail_count = fail_count
        self.error_message = error_message
        self.calls = 0

    async def aretain(self, input: MemoryRetainInput) -> Any:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError(self.error_message)
        return await FakeMemory().aretain(input)

    async def arecall(self, input: MemoryRecallInput) -> Any:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError(self.error_message)
        return await FakeMemory().arecall(input)

    async def areflect(self, input: Any) -> Any:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError(self.error_message)
        return await FakeMemory().areflect(input)

    def capability_manifest(self) -> dict[str, Any]:
        return {"provider": "failing"}


class RetryableMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.observer = InMemoryMemoryObserver()
        self.policy = RetryPolicy(max_retries=2, base_delay_seconds=0.0)

    async def test_retry_succeeds_after_transient_failure(self) -> None:
        inner = FailingMemory(fail_count=1)
        memory = RetryableMemory(inner, retry_policy=self.policy, observer=self.observer)
        result = await memory.aretain(
            MemoryRetainInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                content="User prefers concise answers.",
            )
        )
        self.assertEqual(result.retained_count, 1)
        self.assertEqual(inner.calls, 2)
        self.assertEqual(len(self.observer.events), 2)
        self.assertEqual(self.observer.events[0].status, "error")
        self.assertEqual(self.observer.events[1].status, "success")

    async def test_permanent_failure_does_not_retry(self) -> None:
        inner = FailingMemory(fail_count=10, error_message="invalid request 422")
        memory = RetryableMemory(inner, retry_policy=self.policy, observer=self.observer)
        with self.assertRaises(MemoryOperationError) as ctx:
            await memory.aretain(
                MemoryRetainInput(
                    tenant_id="t1",
                    workspace_id="w1",
                    user_id="u1",
                    bank_id="default",
                    content="User prefers concise answers.",
                )
            )
        self.assertEqual(ctx.exception.category, MemoryFailureCategory.PERMANENT)
        self.assertEqual(inner.calls, 1)
        self.assertEqual(len(self.observer.events), 1)

    async def test_timeout_failure_is_retried(self) -> None:
        inner = FailingMemory(fail_count=2, error_message="connection timed out")
        policy = RetryPolicy(max_retries=3, base_delay_seconds=0.0)
        memory = RetryableMemory(inner, retry_policy=policy, observer=self.observer)
        result = await memory.arecall(
            MemoryRecallInput(
                tenant_id="t1",
                workspace_id="w1",
                user_id="u1",
                bank_id="default",
                query="concise",
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(inner.calls, 3)

    async def test_auth_failure_fails_immediately(self) -> None:
        inner = FailingMemory(fail_count=10, error_message="invalid api key")
        memory = RetryableMemory(inner, retry_policy=self.policy, observer=self.observer)
        with self.assertRaises(MemoryOperationError) as ctx:
            await memory.aretain(
                MemoryRetainInput(
                    tenant_id="t1",
                    workspace_id="w1",
                    user_id="u1",
                    bank_id="default",
                    content="User prefers concise answers.",
                )
            )
        self.assertEqual(ctx.exception.category, MemoryFailureCategory.AUTH)
        self.assertEqual(inner.calls, 1)


if __name__ == "__main__":
    unittest.main()
