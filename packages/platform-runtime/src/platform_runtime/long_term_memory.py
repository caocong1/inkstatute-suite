"""Backend-agnostic long-term memory interface for v1.4 productized memory."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from platform_contract.events import JsonObject

from .memory import MemoryPrivacyError


@dataclass(frozen=True, slots=True)
class MemoryRetainInput:
    """Input for retaining a durable memory."""

    tenant_id: str
    workspace_id: str
    user_id: str
    bank_id: str
    content: str
    source_refs: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)
    now: str | datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryRecallInput:
    """Input for recalling relevant memories."""

    tenant_id: str
    workspace_id: str
    user_id: str
    bank_id: str
    query: str
    max_results: int = 8
    metadata: JsonObject = field(default_factory=dict)
    now: str | datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryReflectInput:
    """Input for generating a memory-grounded answer."""

    tenant_id: str
    workspace_id: str
    user_id: str
    bank_id: str
    query: str
    metadata: JsonObject = field(default_factory=dict)
    now: str | datetime | None = None


@dataclass(frozen=True, slots=True)
class RecalledMemory:
    """A single memory recalled from the backend."""

    memory_id: str
    text: str
    type: str = "world"
    relevance_score: float | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRecallResult:
    """Result of a memory recall operation."""

    bank_id: str
    query: str
    memories: tuple[RecalledMemory, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryReflectResult:
    """Result of a memory-grounded reflection."""

    bank_id: str
    query: str
    text: str
    based_on: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRetainResult:
    """Result of a memory retain operation."""

    bank_id: str
    retained_count: int = 0
    metadata: JsonObject = field(default_factory=dict)


@runtime_checkable
class Memory(Protocol):
    """Backend-agnostic long-term memory interface.

    Implementations are async-first because external memory backends (Hindsight,
    cloud providers) are network-bound. Sync wrappers are intentionally omitted to
    keep the contract honest and avoid blocking the event loop.
    """

    async def aretain(self, input: MemoryRetainInput) -> MemoryRetainResult:
        """Persist a durable memory."""
        ...

    async def arecall(self, input: MemoryRecallInput) -> MemoryRecallResult:
        """Recall memories relevant to the query."""
        ...

    async def areflect(self, input: MemoryReflectInput) -> MemoryReflectResult:
        """Generate a memory-grounded answer."""
        ...

    def capability_manifest(self) -> JsonObject:
        """Return a capability manifest for adapter evaluation."""
        ...


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_metadata(value: object, path: str = "$") -> JsonObject:
    if not isinstance(value, Mapping):
        raise MemoryPrivacyError(f"memory metadata must be an object at {path}")
    output: JsonObject = {}
    for key, child in value.items():
        key_text = str(key)
        child_path = f"{path}.{key_text}"
        if key_text in ("secret", "token", "password", "api_key", "key"):
            raise MemoryPrivacyError(f"memory metadata contains forbidden field at {child_path}")
        output[key_text] = _safe_value(child, child_path)
    return output


def _safe_value(value: object, path: str) -> object:
    if isinstance(value, Mapping):
        return _safe_metadata(value, path)
    if isinstance(value, list | tuple):
        return [_safe_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _validate_input_text(text: str, *, field: str, max_chars: int = 100_000) -> None:
    if not isinstance(text, str):
        raise MemoryPrivacyError(f"{field} must be a string")
    if not text.strip():
        raise MemoryPrivacyError(f"{field} must be non-empty")
    if len(text) > max_chars:
        raise MemoryPrivacyError(f"{field} exceeds {max_chars} characters")


def _validate_scope(tenant_id: str, workspace_id: str, user_id: str, bank_id: str) -> None:
    for field, value in (
        ("tenant_id", tenant_id),
        ("workspace_id", workspace_id),
        ("user_id", user_id),
        ("bank_id", bank_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise MemoryPrivacyError(f"{field} must be a non-empty string")


def _validate_retain_input(input: MemoryRetainInput) -> None:
    _validate_scope(input.tenant_id, input.workspace_id, input.user_id, input.bank_id)
    _validate_input_text(input.content, field="content")
    _safe_metadata(input.metadata)


def _validate_recall_input(input: MemoryRecallInput) -> None:
    _validate_scope(input.tenant_id, input.workspace_id, input.user_id, input.bank_id)
    _validate_input_text(input.query, field="query")
    _safe_metadata(input.metadata)


def _validate_reflect_input(input: MemoryReflectInput) -> None:
    _validate_scope(input.tenant_id, input.workspace_id, input.user_id, input.bank_id)
    _validate_input_text(input.query, field="query")
    _safe_metadata(input.metadata)
