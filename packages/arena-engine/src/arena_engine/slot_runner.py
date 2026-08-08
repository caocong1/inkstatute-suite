"""SlotRunner — asyncio exception-isolated slot execution with retry.

Provides :func:`run_agent_slot` and :func:`_run_with_retry` for driving
a single agent slot through any :class:`BackendAdapter`.  The key
invariant is that ``run_agent_slot`` **never raises** — all exceptions
are caught and converted to a :class:`SlotResult` with status
``"timeout"`` or ``"failed"``.  This ensures that when multiple slots
run concurrently inside an ``asyncio.TaskGroup``, a failure in one slot
does not cancel sibling slots.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or ``resume_session``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from platform_contract.enums import RunEventType
from platform_runtime.protocols import BackendAdapter, RunEvent, RunRequest


@dataclass(frozen=True, slots=True)
class SlotResult:
    """Frozen slotted result of a single agent slot execution.

    Attributes
    ----------
    slot_id
        Identifier of the slot that was run.
    status
        One of ``"success"``, ``"timeout"``, ``"failed"``.
    content
        Extracted content from the ``MESSAGE_COMPLETED`` event, or
        ``None`` if no content was available.
    events
        All ``RunEvent`` objects collected during streaming.
    metadata
        Additional metadata (error messages, partial flags, etc.).
    run_id
        The run ID assigned by the adapter, or ``None`` if submission
        failed before a handle was returned.
    """

    slot_id: str
    status: str
    content: str | None = None
    events: list[RunEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None


async def run_agent_slot(
    slot_id: str,
    adapter: BackendAdapter,
    run_request: RunRequest,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> SlotResult:
    """Execute a single agent slot with exception isolation.

    Wraps ``submit_run`` + ``stream_events`` in ``asyncio.wait_for``
    with the given ``timeout``.  **Never raises** — all exceptions are
    caught and converted to a :class:`SlotResult`.

    Returns
    -------
    SlotResult
        ``status="success"`` on completion, ``"timeout"`` on
        ``TimeoutError``, ``"failed"`` on any other exception.
    """
    return await _run_with_retry(slot_id, adapter, run_request, timeout, max_retries)


async def _run_with_retry(
    slot_id: str,
    adapter: BackendAdapter,
    run_request: RunRequest,
    timeout: float,
    max_retries: int,
) -> SlotResult:
    """Retry loop: up to ``max_retries + 1`` total attempts with backoff.

    Only retries on ``"failed"`` and ``"timeout"`` statuses.  On the
    final attempt, returns the last ``SlotResult`` without raising.
    """
    last_result: SlotResult | None = None
    total_attempts = max_retries + 1

    for attempt in range(total_attempts):
        result = await _attempt_once(slot_id, adapter, run_request, timeout)
        if result.status == "success":
            return result
        last_result = result
        if attempt < total_attempts - 1:
            await asyncio.sleep(0.01 * (attempt + 1))

    return last_result  # type: ignore[return-value]


async def _attempt_once(
    slot_id: str,
    adapter: BackendAdapter,
    run_request: RunRequest,
    timeout: float,
) -> SlotResult:
    """Single attempt: submit + stream, wrapped in timeout, never raises."""
    run_id: str | None = None
    try:
        handle = await asyncio.wait_for(
            adapter.submit_run(run_request),
            timeout=timeout,
        )
        run_id = handle.run_id

        events = await asyncio.wait_for(
            _collect_all_events(adapter, handle.run_id),
            timeout=timeout,
        )

        content = _extract_content(events)
        return SlotResult(
            slot_id=slot_id,
            status="success",
            content=content,
            events=events,
            run_id=run_id,
            metadata={"backend_id": adapter.backend_id()},
        )
    except asyncio.TimeoutError:
        return SlotResult(
            slot_id=slot_id,
            status="timeout",
            metadata={"error": "timeout", "partial": True},
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001
        return SlotResult(
            slot_id=slot_id,
            status="failed",
            metadata={"error": str(exc), "partial": True},
            run_id=run_id,
        )


async def _collect_all_events(
    adapter: BackendAdapter, run_id: str
) -> list[RunEvent]:
    """Collect all events from ``stream_events`` into a list.

    This is a regular coroutine (not an async generator) so it can be
    wrapped in ``asyncio.wait_for`` for timeout enforcement.
    """
    events: list[RunEvent] = []
    async for event in adapter.stream_events(run_id):
        events.append(event)
    return events


def _extract_content(events: list[RunEvent]) -> str | None:
    """Extract content from the first MESSAGE_COMPLETED event payload."""
    completed_type = str(RunEventType.MESSAGE_COMPLETED)
    for event in events:
        if event.event_type == completed_type:
            content = event.payload.get("content")
            if isinstance(content, str):
                return content
    return None


__all__ = [
    "SlotResult",
    "run_agent_slot",
    "_run_with_retry",
]
