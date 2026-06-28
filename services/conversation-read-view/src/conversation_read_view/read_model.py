"""Contract log loading primitives for read-only conversation views."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_records_from_jsonl(path: str | Path) -> list[Any]:
    """Load schema-validated contract event records from a JSONL file."""

    from contract_test_suite.event_stream_replay import load_event_stream

    return load_event_stream(Path(path))


__all__ = [
    "load_records_from_jsonl",
]

