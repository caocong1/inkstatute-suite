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


class Channel(StrEnum):
    WECOM = "wecom"
    QQBOT = "qqbot"
    WEB = "web"
    DESKTOP = "desktop"


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


__all__ = [
    "AgentResultStatus",
    "ArtifactKind",
    "AsyncTaskState",
    "Channel",
    "ErrorCategory",
    "FeedbackAction",
    "FeedbackEventType",
    "FeedbackSource",
    "FeedbackStatus",
    "LanguageRegister",
    "MessageType",
    "OutputFormat",
    "ReplyType",
    "RiskLevel",
    "RouteMode",
    "SkillCandidateSource",
]
