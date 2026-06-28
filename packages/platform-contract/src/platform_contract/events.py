"""Dataclass bindings for InkStatute V2 platform contract events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import (
    AgentResultStatus,
    ApprovalStatus,
    ArtifactKind,
    AsyncTaskState,
    Channel,
    ChannelDeliveryStatus,
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
    RunEventType,
    RunStepKind,
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
    code: str | None = None
    message: str | None = None
    stage: str | None = None
    retryable: bool | None = None
    details: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SolutionBinding:
    solution_id: str
    backend_id: str
    manifest_ref: str | None = None
    materialization_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class McpServerDescriptor:
    server_id: str
    name: str
    transport: str
    capability_refs: list[str] = field(default_factory=list)
    secret_refs: list[str] = field(default_factory=list)
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
    feedback_target: str | None = None
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


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    message_id: str
    tenant_id: str
    workspace_id: str
    channel: Channel | str
    channel_conversation_id: str
    sender_id: str
    message_type: MessageType | str
    received_at: str
    content: str | None = None
    attachments: list[AttachmentRef] = field(default_factory=list)
    raw_payload_ref: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChannelDelivery:
    delivery_id: str
    tenant_id: str
    workspace_id: str
    channel: Channel | str
    channel_conversation_id: str
    status: ChannelDeliveryStatus | str
    created_at: str
    message_id: str | None = None
    run_id: str | None = None
    result_id: str | None = None
    content: str | None = None
    reply_type: ReplyType | str | None = None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    card_ref: str | None = None
    delivered_at: str | None = None
    error: ErrorInfo | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Run:
    run_id: str
    tenant_id: str
    workspace_id: str
    solution_id: str
    backend_id: str
    status: AsyncTaskState | str
    created_at: str
    updated_at: str
    session_id: str | None = None
    channel_message_id: str | None = None
    turn_id: str | None = None
    objective: str | None = None
    requested_output: OutputConstraints | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: ErrorInfo | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: str
    run_id: str
    event_type: RunEventType | str
    occurred_at: str
    seq: int
    status: AsyncTaskState | str | None = None
    step_id: str | None = None
    tool_call_id: str | None = None
    approval_id: str | None = None
    artifact_id: str | None = None
    message_delta: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunStep:
    step_id: str
    run_id: str
    kind: RunStepKind | str
    status: AsyncTaskState | str
    started_at: str
    title: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    tool_call_id: str | None = None
    approval_id: str | None = None
    ended_at: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCall:
    tool_call_id: str
    run_id: str
    tool_name: str
    status: AsyncTaskState | str
    created_at: str
    step_id: str | None = None
    server_id: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    approval_id: str | None = None
    completed_at: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    run_id: str
    status: ApprovalStatus | str
    requested_at: str
    prompt: str
    step_id: str | None = None
    tool_call_id: str | None = None
    requested_by: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    decision_reason: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    run_id: str
    kind: ArtifactKind | str
    name: str
    uri: str
    created_at: str
    result_id: str | None = None
    step_id: str | None = None
    tenant_id: str | None = None
    workspace_id: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    source_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    tenant_id: str
    workspace_id: str
    created_at: str
    updated_at: str
    user_id: str | None = None
    channel: Channel | str | None = None
    channel_conversation_id: str | None = None
    status: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Tenant:
    tenant_id: str
    name: str
    created_at: str
    status: str | None = None
    default_workspace_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Workspace:
    workspace_id: str
    tenant_id: str
    name: str
    created_at: str
    status: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SolutionPackageManifest:
    solution_id: str
    version: str
    name: str
    skills: list[NeutralSkillDescriptor]
    mcp_servers: list[McpServerDescriptor]
    description: str | None = None
    persona_ref: str | None = None
    backend_bindings: list[SolutionBinding] = field(default_factory=list)
    output_policy_ref: str | None = None
    secret_templates: list[str] = field(default_factory=list)
    evaluation_fixture_refs: list[str] = field(default_factory=list)
    industry_context_defaults: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BotInstance:
    bot_instance_id: str
    tenant_id: str
    workspace_id: str
    solution_id: str
    backend_id: str
    channel_binding_id: str
    status: str
    created_at: str
    name: str | None = None
    default_session_policy: JsonObject = field(default_factory=dict)
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChannelBinding:
    channel_binding_id: str
    tenant_id: str
    workspace_id: str
    channel: Channel | str
    bot_instance_id: str
    secret_ref: str
    created_at: str
    config_ref: str | None = None
    webhook_url_ref: str | None = None
    status: str | None = None
    metadata: JsonObject = field(default_factory=dict)


__all__ = [
    "AgentResult",
    "AgentTurn",
    "Approval",
    "Artifact",
    "ArtifactRecord",
    "AttachmentRef",
    "BotInstance",
    "ChannelBinding",
    "ChannelDelivery",
    "ChannelMessage",
    "ErrorInfo",
    "ExecutionTrace",
    "FeedbackEvent",
    "McpServerDescriptor",
    "NeutralSkillDescriptor",
    "OutputConstraints",
    "RouteDecision",
    "Run",
    "RunEvent",
    "RunStep",
    "Session",
    "SkillCandidate",
    "SolutionBinding",
    "SolutionPackageManifest",
    "Tenant",
    "ToolCall",
    "Workspace",
]
