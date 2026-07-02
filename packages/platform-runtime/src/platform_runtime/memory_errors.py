"""Failure classification for long-term memory operations."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class MemoryFailureCategory(StrEnum):
    """Classified failure category for a memory operation."""

    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    PERMANENT = "permanent"
    AUTH = "auth"
    UNKNOWN = "unknown"


class MemoryOperationError(RuntimeError):
    """Raised when a memory operation fails after retry exhaustion."""

    def __init__(
        self,
        message: str,
        *,
        category: MemoryFailureCategory,
        operation: str,
        bank_id: str,
        attempts: int,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.operation = operation
        self.bank_id = bank_id
        self.attempts = attempts
        self.cause = cause


def classify_exception(exc: BaseException, *, bank_id: str = "") -> MemoryOperationError:
    """Classify an exception into a MemoryOperationError."""
    text = str(exc).lower()
    category = MemoryFailureCategory.UNKNOWN
    if "timeout" in text or "timed out" in text:
        category = MemoryFailureCategory.TIMEOUT
    elif "unauthorized" in text or "invalid api key" in text or "authentication" in text:
        category = MemoryFailureCategory.AUTH
    elif "connection" in text or "network" in text or "connect" in text or "temporary" in text or "transient" in text or "503" in text:
        category = MemoryFailureCategory.TRANSIENT
    elif "bad request" in text or "invalid" in text or "not found" in text or "404" in text or "422" in text:
        category = MemoryFailureCategory.PERMANENT
    return MemoryOperationError(
        f"{category.value} memory operation failure: {exc}",
        category=category,
        operation="unknown",
        bank_id=bank_id,
        attempts=1,
        cause=exc,
    )
