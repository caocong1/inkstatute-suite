"""Typed payload dataclasses for V3 unified event types.

Each dataclass corresponds to a JSON Schema in ``schemas/`` and is the
Python binding for one of the 13 unified event categories defined in
V3-PRD §3.2.  The event vocabulary is isomorphic to ACP v1
``session/update`` — the platform stays a thin relay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

from .enums import RunEventType
from .events import Artifact, ErrorInfo, JsonObject


# ---------------------------------------------------------------------------
# Payload dataclasses (frozen, slotted — same pattern as events.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionStartedPayload:
    backend_id: str
    capabilities: list[str] = field(default_factory=list)
    session_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MessageDeltaPayload:
    delta: str
    message_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MessageCompletedPayload:
    content: str
    message_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ThoughtDeltaPayload:
    delta: str
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallStartedPayload:
    tool_call_id: str
    tool_name: str
    kind: str | None = None
    title: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallDeltaPayload:
    tool_call_id: str
    content: str | None = None
    status: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallCompletedPayload:
    tool_call_id: str
    status: str
    content: str | None = None
    file_locations: list[str] = field(default_factory=list)
    raw_input_ref: str | None = None
    raw_output_ref: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanUpdatedPayload:
    plan: list[JsonObject] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PhaseChangedPayload:
    phase: str
    previous_phase: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ElicitationOption:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ElicitationQuestion:
    id: str
    question: str
    allow_multiple: bool = False
    options: list[ElicitationOption] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ElicitationRequestedPayload:
    interrupt_id: str
    intro: str
    questions: list[ElicitationQuestion]
    resume_state_ref: str | None = None
    expires_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PermissionRequestedPayload:
    permission_id: str
    tool_call_id: str
    description: str
    kind: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactCreatedPayload:
    artifact: Artifact
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CitationRecord:
    source: str
    status: str


@dataclass(frozen=True, slots=True)
class CitationRecordedPayload:
    citations: list[CitationRecord] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunStateChangedPayload:
    status: str
    previous_status: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ErrorEventPayload:
    error: ErrorInfo
    metadata: JsonObject = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event-type → payload-class mapping
# ---------------------------------------------------------------------------

EVENT_TYPE_TO_PAYLOAD_CLASS: dict[str, type] = {
    RunEventType.SESSION_STARTED.value: SessionStartedPayload,
    RunEventType.MESSAGE_DELTA_V3.value: MessageDeltaPayload,
    RunEventType.MESSAGE_COMPLETED.value: MessageCompletedPayload,
    RunEventType.THOUGHT_DELTA.value: ThoughtDeltaPayload,
    RunEventType.TOOL_CALL_STARTED_V3.value: ToolCallStartedPayload,
    RunEventType.TOOL_CALL_DELTA.value: ToolCallDeltaPayload,
    RunEventType.TOOL_CALL_COMPLETED_V3.value: ToolCallCompletedPayload,
    RunEventType.PLAN_UPDATED.value: PlanUpdatedPayload,
    RunEventType.PHASE_CHANGED.value: PhaseChangedPayload,
    RunEventType.ELICITATION_REQUESTED.value: ElicitationRequestedPayload,
    RunEventType.PERMISSION_REQUESTED.value: PermissionRequestedPayload,
    RunEventType.ARTIFACT_CREATED_V3.value: ArtifactCreatedPayload,
    RunEventType.CITATION_RECORDED.value: CitationRecordedPayload,
    RunEventType.RUN_STATE_CHANGED.value: RunStateChangedPayload,
}


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def serialize_payload(payload: Any) -> JsonObject:
    """Convert a payload dataclass to a plain dict."""
    return asdict(payload)


def _dict_to_dataclass(cls: type, data: JsonObject) -> Any:
    """Instantiate *cls* from *data*, ignoring unknown keys and recursing
    into nested dataclass fields (e.g. ``ErrorInfo``, ``Artifact``,
    ``ElicitationQuestion``, ``ElicitationOption``, ``CitationRecord``).
    """
    known = {f.name for f in fields(cls)}
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        if key not in known:
            continue
        f = next(f for f in fields(cls) if f.name == key)
        kwargs[key] = _coerce_field(f.type, value)
    return cls(**kwargs)


def _coerce_field(annotation: Any, value: Any) -> Any:
    """Best-effort coercion of a plain value into the annotated type.

    Handles nested dataclasses (``ErrorInfo``, ``Artifact``,
    ``ElicitationQuestion``, ``ElicitationOption``, ``CitationRecord``)
    and lists thereof.  Primitives are passed through unchanged.
    """
    if value is None:
        return None

    # Resolve string annotations (from __future__ annotations)
    if isinstance(annotation, str):
        annotation = _resolve_annotation(annotation)

    # Nested dataclass singletons
    _nested_singletons = {
        ErrorInfo, Artifact, ElicitationQuestion, ElicitationOption, CitationRecord,
    }
    if annotation in _nested_singletons and isinstance(value, dict):
        return _dict_to_dataclass(annotation, value)

    # list[SomeDataclass]
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        args = getattr(annotation, "__args__", ())
        item_type = args[0] if args else None
        if item_type in _nested_singletons and isinstance(value, list):
            return [
                _dict_to_dataclass(item_type, item) if isinstance(item, dict) else item
                for item in value
            ]

    return value


def _resolve_annotation(name: str) -> Any:
    """Resolve a forward-reference string to the actual type object."""
    mapping = {
        "ErrorInfo": ErrorInfo,
        "Artifact": Artifact,
        "ElicitationQuestion": ElicitationQuestion,
        "ElicitationOption": ElicitationOption,
        "CitationRecord": CitationRecord,
    }
    return mapping.get(name, str)


def deserialize_payload(event_type: str, data: JsonObject) -> Any:
    """Return the correct payload dataclass for *event_type* from *data*."""
    cls = EVENT_TYPE_TO_PAYLOAD_CLASS.get(event_type)
    if cls is None:
        raise KeyError(f"Unknown V3 event type: {event_type!r}")
    return _dict_to_dataclass(cls, data)
