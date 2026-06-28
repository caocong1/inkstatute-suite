"""InkStatute-owned WeCom service primitives."""

from .agent_backend import (
    AgentBackendSelection,
    AgentBackendSelectionError,
    select_agent_backend,
)
from .active_task_router import (
    ActiveTaskRoute,
    ActiveTaskRoutingDecision,
    AdapterTaskCapabilities,
    route_active_task_turn,
)
from .idempotency import wecom_idempotency_key
from .normalization import normalize_wecom_feedback_callback, normalize_wecom_turn
from .output_policy import OutputPolicyDecision, apply_output_policy
from .owned_notices import OWNED_NOTICE_TEMPLATES, build_owned_notice
from .protocol import (
    RawPayloadForbiddenError,
    ack_response,
    parse_callback_envelope,
    verify_callback_signature,
)
from .sender import (
    build_file_send_envelope,
    build_template_card_envelope,
    build_text_send_envelope,
)
from .task_flow import (
    TASK_STAGE_TO_ASYNC_STATE,
    TERMINAL_TASK_STAGES,
    TaskFlow,
    TaskFlowConfig,
    TaskInputSummary,
    TaskStageRecord,
    WeComTaskStage,
    create_task_flow,
    deadline_exceeded,
    progress_notice_due,
    record_stage,
    summarize_task_input,
    task_snapshot,
    task_stage_idempotency_key,
)

__all__ = [
    "ActiveTaskRoute",
    "ActiveTaskRoutingDecision",
    "AgentBackendSelection",
    "AgentBackendSelectionError",
    "AdapterTaskCapabilities",
    "OutputPolicyDecision",
    "OWNED_NOTICE_TEMPLATES",
    "RawPayloadForbiddenError",
    "TASK_STAGE_TO_ASYNC_STATE",
    "TERMINAL_TASK_STAGES",
    "TaskFlow",
    "TaskFlowConfig",
    "TaskInputSummary",
    "TaskStageRecord",
    "WeComTaskStage",
    "ack_response",
    "apply_output_policy",
    "build_owned_notice",
    "build_file_send_envelope",
    "build_template_card_envelope",
    "build_text_send_envelope",
    "create_task_flow",
    "deadline_exceeded",
    "normalize_wecom_feedback_callback",
    "normalize_wecom_turn",
    "parse_callback_envelope",
    "progress_notice_due",
    "record_stage",
    "route_active_task_turn",
    "select_agent_backend",
    "summarize_task_input",
    "task_snapshot",
    "task_stage_idempotency_key",
    "verify_callback_signature",
    "wecom_idempotency_key",
]
