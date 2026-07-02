"""Contract events for memory operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from platform_contract.events import JsonObject

from .memory_errors import MemoryFailureCategory


@dataclass(frozen=True, slots=True)
class MemoryOperationEvent:
    """Observable event for a memory operation attempt."""

    operation: str
    bank_id: str
    status: str
    category: str | None = None
    latency_ms: float | None = None
    retry_count: int = 0
    error_code: str | None = None
    metadata: JsonObject = field(default_factory=dict)

    def as_json(self) -> JsonObject:
        return {
            "event": "memory_operation",
            "operation": self.operation,
            "bank_id": self.bank_id,
            "status": self.status,
            "category": self.category,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "error_code": self.error_code,
            "metadata": self.metadata,
        }


@runtime_checkable
class MemoryObserver(Protocol):
    """Port for recording memory operation events."""

    def on_memory_event(self, event: MemoryOperationEvent) -> None:
        """Record a memory operation event."""
        ...


class InMemoryMemoryObserver:
    """Simple observer that stores events in memory for tests."""

    def __init__(self) -> None:
        self.events: list[MemoryOperationEvent] = []

    def on_memory_event(self, event: MemoryOperationEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()
