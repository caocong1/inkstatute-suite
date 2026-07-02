"""Retry wrapper around the Memory interface with failure classification and events."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .long_term_memory import (
    Memory,
    MemoryRecallInput,
    MemoryRecallResult,
    MemoryReflectInput,
    MemoryReflectResult,
    MemoryRetainInput,
    MemoryRetainResult,
)
from .memory_errors import MemoryFailureCategory, MemoryOperationError, classify_exception
from .memory_events import MemoryObserver, MemoryOperationEvent


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy for memory operations."""

    max_retries: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    retryable_categories: tuple[MemoryFailureCategory, ...] = (
        MemoryFailureCategory.TRANSIENT,
        MemoryFailureCategory.TIMEOUT,
    )


class RetryableMemory:
    """Wrap a Memory implementation with retry and observability.

    Retries only on transient and timeout failures. Auth and permanent failures
    are raised immediately. Events are emitted for every attempt.
    """

    def __init__(
        self,
        memory: Memory,
        *,
        retry_policy: RetryPolicy | None = None,
        observer: MemoryObserver | None = None,
    ) -> None:
        self._memory = memory
        self._retry_policy = retry_policy or RetryPolicy()
        self._observer = observer

    async def _call_with_retry(
        self,
        operation: str,
        bank_id: str,
        coro_factory: Any,
    ) -> Any:
        policy = self._retry_policy
        last_error: BaseException | None = None
        for attempt in range(policy.max_retries + 1):
            start = time.perf_counter()
            try:
                result = await coro_factory()
                latency_ms = (time.perf_counter() - start) * 1000
                self._emit(
                    MemoryOperationEvent(
                        operation=operation,
                        bank_id=bank_id,
                        status="success",
                        latency_ms=latency_ms,
                        retry_count=attempt,
                        metadata={"attempt": attempt + 1},
                    )
                )
                return result
            except Exception as e:
                last_error = e
                latency_ms = (time.perf_counter() - start) * 1000
                classified = classify_exception(e, bank_id=bank_id)
                classified.operation = operation
                classified.attempts = attempt + 1
                self._emit(
                    MemoryOperationEvent(
                        operation=operation,
                        bank_id=bank_id,
                        status="error",
                        category=classified.category.value,
                        latency_ms=latency_ms,
                        retry_count=attempt,
                        error_code=classified.category.value,
                        metadata={"attempt": attempt + 1},
                    )
                )
                if classified.category not in policy.retryable_categories:
                    break
                if attempt < policy.max_retries:
                    delay = min(policy.base_delay_seconds * (2 ** attempt), policy.max_delay_seconds)
                    await asyncio.sleep(delay)
        raise MemoryOperationError(
            f"{operation} failed after {policy.max_retries + 1} attempts: {last_error}",
            category=classify_exception(last_error or RuntimeError("unknown"), bank_id=bank_id).category,
            operation=operation,
            bank_id=bank_id,
            attempts=policy.max_retries + 1,
            cause=last_error,
        )

    def _emit(self, event: MemoryOperationEvent) -> None:
        if self._observer is not None:
            self._observer.on_memory_event(event)

    async def aretain(self, input: MemoryRetainInput) -> MemoryRetainResult:
        bank_id = f"{input.tenant_id}:{input.workspace_id}:{input.user_id}"
        return await self._call_with_retry("retain", bank_id, lambda: self._memory.aretain(input))

    async def arecall(self, input: MemoryRecallInput) -> MemoryRecallResult:
        bank_id = f"{input.tenant_id}:{input.workspace_id}:{input.user_id}"
        return await self._call_with_retry("recall", bank_id, lambda: self._memory.arecall(input))

    async def areflect(self, input: MemoryReflectInput) -> MemoryReflectResult:
        bank_id = f"{input.tenant_id}:{input.workspace_id}:{input.user_id}"
        return await self._call_with_retry("reflect", bank_id, lambda: self._memory.areflect(input))

    def capability_manifest(self) -> Any:
        return self._memory.capability_manifest()
