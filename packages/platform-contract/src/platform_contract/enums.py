"""Enum domains for InkStatute V2 platform contract events."""

from enum import StrEnum


class AsyncTaskState(StrEnum):
    """Locked async task states for platform-visible task progress."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorCategory(StrEnum):
    """Top-level contract error categories."""

    CONTRACT_ERROR = "contract_error"
    RUNTIME_ERROR = "runtime_error"
    CHANNEL_ERROR = "channel_error"


class ApprovalStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Channel(StrEnum):
    WECOM = "wecom"
    QQBOT = "qqbot"
    WEB = "web"
    DESKTOP = "desktop"


class ChannelDeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class MessageType(StrEnum):
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    VOICE = "voice"
    BUTTON_CALLBACK = "button_callback"


class OutputFormat(StrEnum):
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"
    CARD = "card"
    OTHER = "other"


class LanguageRegister(StrEnum):
    FORMAL = "formal"
    COLLOQUIAL = "colloquial"


class AgentResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"


class ReplyType(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    FILE = "file"
    CARD = "card"
    STATUS_UPDATE = "status_update"


class ArtifactKind(StrEnum):
    DOCX = "docx"
    PPTX = "pptx"
    TRACKCHANGES_DOCX = "trackchanges_docx"
    XLSX = "xlsx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    OTHER = "other"


class RunEventType(StrEnum):
    STATE_CHANGED = "state_changed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    MESSAGE_DELTA = "message_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    APPROVAL_REQUESTED = "approval_requested"
    ARTIFACT_CREATED = "artifact_created"
    ERROR = "error"
    # V3 unified event types (ACP-isomorphic). V2 values retained for backward compatibility.
    SESSION_STARTED = "session.started"
    MESSAGE_DELTA_V3 = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    THOUGHT_DELTA = "thought.delta"
    TOOL_CALL_STARTED_V3 = "tool_call.started"
    TOOL_CALL_DELTA = "tool_call.delta"
    TOOL_CALL_COMPLETED_V3 = "tool_call.completed"
    PLAN_UPDATED = "plan.updated"
    PHASE_CHANGED = "phase.changed"
    ELICITATION_REQUESTED = "elicitation.requested"
    PERMISSION_REQUESTED = "permission.requested"
    ARTIFACT_CREATED_V3 = "artifact.created"
    CITATION_RECORDED = "citation.recorded"
    RUN_STATE_CHANGED = "run.state_changed"


class RunStepKind(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    APPROVAL = "approval"
    DELIVERY = "delivery"
    SYSTEM = "system"


class SkillCandidateSource(StrEnum):
    ROUTE_MISMATCH = "route_mismatch"
    REPEATED_FEEDBACK = "repeated_feedback"
    UNKNOWN_TASK = "unknown_task"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeedbackSource(StrEnum):
    CARD_BUTTON = "card_button"
    TEXT_COMMAND = "text_command"
    WEB_FORM = "web_form"
    ADMIN_ANNOTATION = "admin_annotation"


class FeedbackEventType(StrEnum):
    RATING = "rating"
    CORRECTION = "correction"
    FACT_MISSING = "fact_missing"
    CITATION_ERROR = "citation_error"
    ROUTE_MISMATCH = "route_mismatch"
    FORMAT_ISSUE = "format_issue"
    COMPLIANCE_ISSUE = "compliance_issue"
    SKILL_CANDIDATE = "skill_candidate"


class FeedbackAction(StrEnum):
    UP = "up"
    DOWN = "down"
    NEEDS_FIX = "needs_fix"
    ROUTE_WRONG = "route_wrong"


class FeedbackStatus(StrEnum):
    PENDING = "pending"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RouteMode(StrEnum):
    MATCHED = "matched"
    SIMPLE_QA = "simple_qa"
    SKIPPED = "skipped"
    ZERO_MATCH = "zero_match"


class MemoryScope(StrEnum):
    SESSION = "session"
    USER = "user"
    WORKSPACE = "workspace"
    TENANT = "tenant"


class MemorySensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPPRESSED = "suppressed"
    DELETED = "deleted"


class MemoryCandidateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPPRESSED = "suppressed"


class InterruptStatus(StrEnum):
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


__all__ = [
    "AgentResultStatus",
    "ApprovalStatus",
    "ArtifactKind",
    "AsyncTaskState",
    "Channel",
    "ChannelDeliveryStatus",
    "ErrorCategory",
    "FeedbackAction",
    "FeedbackEventType",
    "FeedbackSource",
    "FeedbackStatus",
    "LanguageRegister",
    "InterruptStatus",
    "MemoryCandidateStatus",
    "MemoryScope",
    "MemorySensitivity",
    "MemoryStatus",
    "MessageType",
    "OutputFormat",
    "ReplyType",
    "RiskLevel",
    "RouteMode",
    "RunEventType",
    "RunStepKind",
    "SkillCandidateSource",
]
