"""Dataclass bindings for InkStatute V2 platform contract events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import (
    AgentResultStatus,
    ArtifactKind,
    Channel,
    ErrorCategory,
    FeedbackAction,
    FeedbackEventType,
    FeedbackSource,
    FeedbackStatus,
    LanguageRegister,
    MessageType,
    OutputFormat,
    ReplyType,
    RiskLevel,
    RouteMode,
    SkillCandidateSource,
)

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    attachment_id: str
    kind: str
    uri: str
    name: str | None = None
    mime_type: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutputConstraints:
    format: OutputFormat | str | None = None
    features: list[str] = field(default_factory=list)
    template_ref: str | None = None
    citation_style: str | None = None
    language_register: LanguageRegister | str | None = None
    must_cite: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    kind: ArtifactKind | str
    name: str
    uri: str
    mime_type: str | None = None
    template_ref: str | None = None
    features: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SkillCandidate:
    detected: bool
    source: SkillCandidateSource | str
    proposed_name: str | None = None
    risk_level: RiskLevel | str | None = None
    requires_human_review: bool = True
    evidence: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    category: ErrorCategory | str
    code: str
    message: str
    retryable: bool | None = None
    details: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentTurn:
    turn_id: str
    conversation_id: str
    channel: Channel | str
    user_id: str
    message_type: MessageType | str
    received_at: str
    content: str | None = None
    attachments: list[AttachmentRef] = field(default_factory=list)
    output_constraints: OutputConstraints | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResult:
    result_id: str
    turn_id: str
    status: AgentResultStatus | str
    reply_type: ReplyType | str
    content: str | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    execution_trace: ExecutionTrace | None = None
    feedback_target: str | None = None
    route_mismatch: bool | None = None
    skill_candidate: SkillCandidate | None = None
    error: ErrorInfo | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    feedback_id: str
    turn_id: str
    conversation_id: str
    user_id: str
    source: FeedbackSource | str
    event_type: FeedbackEventType | str
    status: FeedbackStatus | str
    created_at: str
    result_id: str | None = None
    rating: float | None = None
    action: FeedbackAction | str | None = None
    message: str | None = None
    route_mismatch: bool | None = None
    skill_candidate: SkillCandidate | None = None
    labels: list[str] = field(default_factory=list)
    related_skill: str | None = None
    related_route_decision: str | None = None
    raw_payload_ref: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    trace_id: str
    turn_id: str
    started_at: str
    ended_at: str
    active_skill_name: str | None
    matched_registered_skill: bool
    occurred_at: str
    ingested_at: str
    seq: int
    steps: list[JsonObject] = field(default_factory=list)
    tool_calls: list[JsonObject] = field(default_factory=list)
    artifacts_written: list[str] = field(default_factory=list)
    route_decision: JsonObject | None = None
    gates: list[JsonObject] = field(default_factory=list)
    errors: list[JsonObject] = field(default_factory=list)
    model_usage: JsonObject | None = None
    debug_payload: JsonObject | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route_decision_id: str
    turn_id: str
    primary_skill: str | None
    confidence: float
    mode: RouteMode | str
    created_at: str
    supporting_skills: list[str] = field(default_factory=list)
    gates_before: list[str] = field(default_factory=list)
    gates_after: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    matched_rule: str | None = None
    reason: str | None = None
    route_mismatch: bool | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


__all__ = [
    "AgentResult",
    "AgentTurn",
    "Artifact",
    "AttachmentRef",
    "ErrorInfo",
    "ExecutionTrace",
    "FeedbackEvent",
    "OutputConstraints",
    "RouteDecision",
    "SkillCandidate",
]
