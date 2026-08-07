"""EventEmitter — core event infrastructure for the agent turn loop.

The ``EventEmitter`` is the single point through which the turn loop
produces Phase 88 unified events.  It:

1. **Monotonic seq** — assigns strictly increasing ``seq`` integers
   starting from 0 to each emitted event.  Used for SSE replay
   (Phase 91 Last-Event-ID support).

2. **Silence threshold** — tracks ``last_event_time`` (using an
   injectable monotonic clock).  If no event has been emitted for
   more than ``silence_threshold_seconds``, ``maybe_heartbeat()``
   emits a heartbeat ``thought.delta`` event with
   ``metadata={"heartbeat": true}`` and a contextual progress message.

3. **RunEvent construction** — builds ``RunEvent`` objects with
   ``event_id`` (UUID), ``run_id``, ``event_type`` (from
   ``RunEventType`` V3 values), ``occurred_at`` (ISO-8601), ``seq``,
   ``payload`` (serialized via ``serialize_payload()``), and
   ``metadata``.

4. **Convenience methods** — ``emit_message_delta()``,
   ``emit_message_completed()``, ``emit_thought_delta()``,
   ``emit_tool_call_started()``, ``emit_tool_call_delta()``,
   ``emit_tool_call_completed()``, ``emit_phase_changed()``,
   ``emit_run_state_changed()``, ``emit_error()``.

5. **Heartbeat** — ``maybe_heartbeat()`` checks elapsed time since
   last event and emits a heartbeat ``thought.delta`` if threshold
   exceeded.  The turn loop calls this before/after long operations.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from platform_contract.enums import RunEventType
from platform_contract.events import Artifact, ErrorInfo, RunEvent
from platform_contract.unified_events import (
    ArtifactCreatedPayload,
    ElicitationQuestion,
    ElicitationRequestedPayload,
    ErrorEventPayload,
    MessageCompletedPayload,
    MessageDeltaPayload,
    PhaseChangedPayload,
    RunStateChangedPayload,
    ThoughtDeltaPayload,
    ToolCallCompletedPayload,
    ToolCallDeltaPayload,
    ToolCallStartedPayload,
    serialize_payload,
)

from .config import AgentCoreConfig

JsonObject = dict[str, Any]

# Default clock functions
def _default_clock() -> str:
    """Default ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _default_monotonic_clock() -> float:
    """Default monotonic clock for silence threshold tracking."""
    return time.monotonic()


class EventEmitter:
    """Emits Phase 88 unified events with monotonic seq and silence threshold.

    Args:
        run_id: The run identifier for all emitted events.
        config: AgentCoreConfig providing ``silence_threshold_seconds``
            and ``heartbeat_metadata_key``.
        clock: Injectable callable returning an ISO-8601 timestamp
            string.  Default: ``datetime.now(timezone.utc).isoformat()``.
        monotonic_clock: Injectable callable returning a float for
            silence-threshold tracking.  Default: ``time.monotonic()``.
    """

    def __init__(
        self,
        run_id: str,
        config: AgentCoreConfig | None = None,
        *,
        clock: Callable[[], str] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._run_id = run_id
        self._config = config or AgentCoreConfig()
        self._clock = clock or _default_clock
        self._monotonic_clock = monotonic_clock or _default_monotonic_clock
        self._seq = 0
        self._last_event_time: float = self._monotonic_clock()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def seq(self) -> int:
        """Current seq counter (next event will have this seq)."""
        return self._seq

    @property
    def last_event_time(self) -> float:
        """Monotonic timestamp of the last emitted event."""
        return self._last_event_time

    @property
    def config(self) -> AgentCoreConfig:
        return self._config

    # ------------------------------------------------------------------
    # Core emit method
    # ------------------------------------------------------------------

    def _emit(
        self,
        event_type: RunEventType | str,
        payload: Any,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Build a RunEvent, assign seq, update last_event_time, return it.

        Args:
            event_type: One of the ``RunEventType`` V3 values.
            payload: A payload dataclass (from ``unified_events.py``)
                — will be serialized via ``serialize_payload()``.
            metadata: Optional metadata dict merged into the event.

        Returns:
            The constructed ``RunEvent``.
        """
        event = RunEvent(
            event_id=str(uuid.uuid4()),
            run_id=self._run_id,
            event_type=event_type.value if isinstance(event_type, RunEventType) else event_type,
            occurred_at=self._clock(),
            seq=self._seq,
            payload=serialize_payload(payload),
            metadata=metadata or {},
        )
        self._seq += 1
        self._last_event_time = self._monotonic_clock()
        return event

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def maybe_heartbeat(
        self,
        message: str = "正在处理...",
    ) -> RunEvent | None:
        """Emit a heartbeat thought.delta if silence threshold exceeded.

        Args:
            message: Contextual progress message for the heartbeat.

        Returns:
            A ``RunEvent`` with ``event_type=thought.delta`` and
            ``metadata={"heartbeat": true}`` if the threshold was
            exceeded, otherwise ``None``.
        """
        elapsed = self._monotonic_clock() - self._last_event_time
        if elapsed <= self._config.silence_threshold_seconds:
            return None

        heartbeat_metadata: JsonObject = {self._config.heartbeat_metadata_key: True}
        payload = ThoughtDeltaPayload(delta=message, metadata=heartbeat_metadata)
        return self._emit(RunEventType.THOUGHT_DELTA, payload, metadata=heartbeat_metadata)

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def emit_message_delta(
        self,
        delta: str,
        message_id: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``message.delta`` event for content streaming."""
        payload = MessageDeltaPayload(
            delta=delta,
            message_id=message_id,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.MESSAGE_DELTA_V3, payload, metadata=metadata)

    def emit_message_completed(
        self,
        content: str,
        message_id: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``message.completed`` event for final content."""
        payload = MessageCompletedPayload(
            content=content,
            message_id=message_id,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.MESSAGE_COMPLETED, payload, metadata=metadata)

    def emit_thought_delta(
        self,
        delta: str,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``thought.delta`` event for reasoning/thinking streaming."""
        payload = ThoughtDeltaPayload(
            delta=delta,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.THOUGHT_DELTA, payload, metadata=metadata)

    def emit_tool_call_started(
        self,
        tool_call_id: str,
        tool_name: str,
        kind: str | None = None,
        title: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``tool_call.started`` event before tool execution."""
        payload = ToolCallStartedPayload(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            kind=kind,
            title=title,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.TOOL_CALL_STARTED_V3, payload, metadata=metadata)

    def emit_tool_call_delta(
        self,
        tool_call_id: str,
        content: str | None = None,
        status: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``tool_call.delta`` event during tool execution."""
        payload = ToolCallDeltaPayload(
            tool_call_id=tool_call_id,
            content=content,
            status=status,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.TOOL_CALL_DELTA, payload, metadata=metadata)

    def emit_tool_call_completed(
        self,
        tool_call_id: str,
        status: str,
        content: str | None = None,
        file_locations: list[str] | None = None,
        raw_input_ref: str | None = None,
        raw_output_ref: str | None = None,
        error: ErrorInfo | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``tool_call.completed`` event after tool execution."""
        payload = ToolCallCompletedPayload(
            tool_call_id=tool_call_id,
            status=status,
            content=content,
            file_locations=file_locations or [],
            raw_input_ref=raw_input_ref,
            raw_output_ref=raw_output_ref,
            error=error,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.TOOL_CALL_COMPLETED_V3, payload, metadata=metadata)

    def emit_phase_changed(
        self,
        phase: str,
        previous_phase: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``phase.changed`` event."""
        payload = PhaseChangedPayload(
            phase=phase,
            previous_phase=previous_phase,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.PHASE_CHANGED, payload, metadata=metadata)

    def emit_run_state_changed(
        self,
        status: str,
        previous_status: str | None = None,
        error: ErrorInfo | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``run.state_changed`` event.

        If ``metadata`` contains a ``provider_usage`` key, it is
        preserved in the event metadata.
        """
        payload = RunStateChangedPayload(
            status=status,
            previous_status=previous_status,
            error=error,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.RUN_STATE_CHANGED, payload, metadata=metadata)

    def emit_error(
        self,
        error: ErrorInfo,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit an ``error`` event with an ``ErrorInfo`` payload."""
        payload = ErrorEventPayload(
            error=error,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.ERROR, payload, metadata=metadata)

    def emit_artifact_created(
        self,
        artifact: Artifact,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit an ``artifact.created`` event.

        Args:
            artifact: The ``Artifact`` dataclass describing the produced
                artifact (docx, trackchanges_docx, etc.).
            metadata: Optional metadata dict.

        Returns:
            A ``RunEvent`` with ``event_type="artifact.created"`` and
            a serialized ``ArtifactCreatedPayload`` containing the
            ``Artifact`` dataclass.
        """
        payload = ArtifactCreatedPayload(
            artifact=artifact,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.ARTIFACT_CREATED_V3, payload, metadata=metadata)

    def emit_elicitation_requested(
        self,
        interrupt_id: str,
        intro: str,
        questions: list[ElicitationQuestion],
        resume_state_ref: str | None = None,
        expires_at: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit an ``elicitation.requested`` event.

        Args:
            interrupt_id: Unique identifier for this elicitation interrupt.
            intro: Introductory text shown to the user.
            questions: List of 2-4 ``ElicitationQuestion`` objects.
            resume_state_ref: Optional reference to resume state.
            expires_at: Optional ISO-8601 expiry timestamp.
            metadata: Optional metadata dict.

        Returns:
            A ``RunEvent`` with ``event_type="elicitation.requested"`` and
            a serialized ``ElicitationRequestedPayload``.
        """
        payload = ElicitationRequestedPayload(
            interrupt_id=interrupt_id,
            intro=intro,
            questions=questions,
            resume_state_ref=resume_state_ref,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        return self._emit(RunEventType.ELICITATION_REQUESTED, payload, metadata=metadata)


__all__ = ["EventEmitter"]
