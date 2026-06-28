"""Append-only JSONL writer for Hermes contract event envelopes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContractLogRecord:
    event_key: str
    occurred_at: str
    ingested_at: str
    seq: int
    event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "occurred_at": self.occurred_at,
            "ingested_at": self.ingested_at,
            "seq": self.seq,
            "event": self.event,
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ContractEventWriter:
    def __init__(self, path: str | Path, *, start_seq: int = 0, clock: Any | None = None) -> None:
        self.path = Path(path)
        self._next_seq = start_seq
        self._clock = clock

    def append(
        self,
        event_key: str,
        event: Mapping[str, Any],
        *,
        occurred_at: str | None = None,
        ingested_at: str | None = None,
    ) -> ContractLogRecord:
        now = _timestamp(self._clock() if self._clock else datetime.now(timezone.utc))
        record = ContractLogRecord(
            event_key=event_key,
            occurred_at=occurred_at or now,
            ingested_at=ingested_at or now,
            seq=self._next_seq,
            event=_json_clone(event),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json_line())
            handle.write("\n")
        self._next_seq += 1
        return record

    def append_many(
        self,
        events: Mapping[str, Mapping[str, Any]] | Iterable[tuple[str, Mapping[str, Any]]],
    ) -> list[ContractLogRecord]:
        items = events.items() if isinstance(events, Mapping) else events
        return [self.append(event_key, event) for event_key, event in items]


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.endswith("+00:00"):
        return value[:-6] + "Z"
    return str(value)


def _json_clone(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
