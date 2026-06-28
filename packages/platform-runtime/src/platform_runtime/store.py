"""Append-only, reference-first contract log storage for embedded runtimes."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from platform_contract.events import JsonObject


class ContractLogPrivacyError(ValueError):
    """Raised when an event attempts to store forbidden raw payload material."""


@dataclass(frozen=True, slots=True)
class ContractLogEntry:
    event_key: str
    occurred_at: str
    ingested_at: str
    seq: int
    event: JsonObject

    def to_dict(self) -> JsonObject:
        return {
            "event_key": self.event_key,
            "occurred_at": self.occurred_at,
            "ingested_at": self.ingested_at,
            "seq": self.seq,
            "event": _json_clone(self.event),
        }


class InMemoryContractLogStore:
    def __init__(self, *, start_seq: int = 0, clock: Any | None = None) -> None:
        self._next_seq = start_seq
        self._clock = clock
        self._entries: list[ContractLogEntry] = []

    def append(
        self,
        event_key: str,
        event: Mapping[str, Any],
        *,
        occurred_at: str | None = None,
        ingested_at: str | None = None,
    ) -> ContractLogEntry:
        _reject_forbidden_payload_storage(event)
        now = _timestamp(_clock_now(self._clock))
        stored = ContractLogEntry(
            event_key=event_key,
            occurred_at=occurred_at or now,
            ingested_at=ingested_at or now,
            seq=self._next_seq,
            event=_json_clone(event),
        )
        self._entries.append(stored)
        self._next_seq += 1
        return _copy_entry(stored)

    def entries(self) -> tuple[ContractLogEntry, ...]:
        return tuple(_copy_entry(entry) for entry in self._entries)

    def entries_for_run(self, run_id: str) -> tuple[ContractLogEntry, ...]:
        return tuple(
            _copy_entry(entry)
            for entry in self._entries
            if entry.event.get("run_id") == run_id
        )


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.endswith("+00:00"):
        return value[:-6] + "Z"
    return str(value)


def _clock_now(clock: Callable[[], datetime | str] | Any | None) -> datetime | str:
    if clock is None:
        return datetime.now(timezone.utc)
    if callable(clock):
        return clock()
    now = getattr(clock, "now", None)
    if callable(now):
        return now()
    raise TypeError("clock must be callable or provide now()")


def _copy_entry(entry: ContractLogEntry) -> ContractLogEntry:
    return ContractLogEntry(
        event_key=entry.event_key,
        occurred_at=entry.occurred_at,
        ingested_at=entry.ingested_at,
        seq=entry.seq,
        event=_json_clone(entry.event),
    )


def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _reject_forbidden_payload_storage(event: Mapping[str, Any]) -> None:
    for path, key in _walk_keys(event):
        if key == "raw_payload":
            raise ContractLogPrivacyError(f"contract log event contains forbidden raw_payload at {path}")
        if key in _FORBIDDEN_FULL_TEXT_KEYS:
            raise ContractLogPrivacyError(
                f"contract log event contains forbidden full-text payload field at {path}"
            )


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            yield child_path, key_text
            yield from _walk_keys(nested, child_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_keys(nested, f"{path}[{index}]")


_FORBIDDEN_FULL_TEXT_KEYS = {
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
}


__all__ = [
    "ContractLogEntry",
    "ContractLogPrivacyError",
    "InMemoryContractLogStore",
]
