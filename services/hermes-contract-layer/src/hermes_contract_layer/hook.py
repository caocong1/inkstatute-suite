"""Safe Hermes hook entrypoint for shadow contract recording."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Callable, Mapping

from .mapper import map_agent_end_context
from .writer import ContractEventWriter


CONTRACT_LOG_PATH_ENV = "INKSTATUTE_CONTRACT_LOG_PATH"

OUTBOUND_CONTEXT_KEYS = (
    "response",
    "message_id",
    "platform",
    "user_id",
    "chat_id",
    "session_id",
    "message",
)


@dataclass(frozen=True)
class HookRecordingResult:
    status: str
    event_count: int = 0
    error: str | None = None


def handle(event_type: str, context: dict[str, Any]) -> HookRecordingResult:
    """Hermes hook handler that shields outbound context from recorder failures."""

    snapshot = _snapshot_outbound_context(context)
    try:
        return record_contract_result(event_type, context)
    except Exception:
        return HookRecordingResult(status="error", error="recorder_failed")
    finally:
        _restore_outbound_context(context, snapshot)


def record_contract_result(
    event_type: str,
    context: dict[str, Any],
    *,
    writer: Callable[..., Any] | Any | None = None,
    log_path: str | os.PathLike[str] | None = None,
    clock: Callable[[], Any] | None = None,
) -> HookRecordingResult:
    """Record a Hermes contract result when a writer is configured.

    Plan 04-01 establishes the safe hook boundary. Plan 04-02 supplies the
    mapper and JSONL writer used by this entrypoint.
    """

    if event_type != "agent:end":
        return HookRecordingResult(status="ignored")

    resolved_log_path = log_path or os.environ.get(CONTRACT_LOG_PATH_ENV)
    if writer is None and resolved_log_path is None:
        return HookRecordingResult(status="skipped")

    events = map_agent_end_context(dict(context), now=_clock_now(clock))
    if writer is None:
        writer = ContractEventWriter(resolved_log_path, clock=clock)

    event_count = _invoke_writer(writer, events=events, log_path=resolved_log_path, clock=clock)
    return HookRecordingResult(status="recorded", event_count=event_count)


def _invoke_writer(
    writer: Callable[..., Any] | Any,
    *,
    events: Mapping[str, Mapping[str, Any]],
    log_path: str | os.PathLike[str] | None,
    clock: Callable[[], Any] | None,
) -> int:
    if callable(writer):
        result = writer(events, log_path=log_path, clock=clock)
    elif hasattr(writer, "append_many"):
        result = writer.append_many(events)
    elif hasattr(writer, "write_events"):
        result = writer.write_events(events, log_path=log_path, clock=clock)
    else:
        raise TypeError("writer must be callable or expose append_many/write_events")

    if isinstance(result, int):
        return result
    if isinstance(result, HookRecordingResult):
        return result.event_count
    if result is None:
        return 0
    if hasattr(result, "__len__"):
        return len(result)
    return 1


def _clock_now(clock: Callable[[], Any] | None) -> datetime | str:
    return clock() if clock is not None else datetime.now(timezone.utc)


def _snapshot_outbound_context(context: Mapping[str, Any]) -> dict[str, tuple[bool, Any]]:
    return {key: (key in context, context.get(key)) for key in OUTBOUND_CONTEXT_KEYS}


def _restore_outbound_context(
    context: dict[str, Any],
    snapshot: Mapping[str, tuple[bool, Any]],
) -> None:
    for key, (existed, value) in snapshot.items():
        if existed:
            context[key] = value
        else:
            context.pop(key, None)
