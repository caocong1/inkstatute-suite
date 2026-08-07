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
from .ingress_runtime import WeComRuntimeIngress
from .normalization import normalize_wecom_feedback_callback, normalize_wecom_turn
from .delivery_guard import DeliveryCompletionAssessment, assess_delivery_completion
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
from .session_runtime import (
    WeComSessionRuntime,
    WeComSessionRuntimeAction,
    WeComSessionRuntimeOutcome,
    build_clarification_delivery,
)
from .runtime_audit import append_runtime_audit, parse_bool_env
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
from .channel_wiring import build_wecom_channel_config, load_wecom_channel_config

# Lazy import for wiring to avoid circular import:
# wecom_service.__init__ → wiring → inkstatute_channels_wecom.adapter →
# wecom_service.normalization → wecom_service.__init__
# The wiring module imports the channel adapter, which imports back into
# wecom_service.  Deferring this import breaks the cycle when both
# packages are on PYTHONPATH simultaneously (e.g. wecom-channel gate).
def __getattr__(name: str):  # type: ignore[no-redef]
    if name in ("WeComWiredRuntime", "build_wecom_wired_runtime"):
        from .wiring import WeComWiredRuntime, build_wecom_wired_runtime

        return {"WeComWiredRuntime": WeComWiredRuntime, "build_wecom_wired_runtime": build_wecom_wired_runtime}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ActiveTaskRoute",
    "ActiveTaskRoutingDecision",
    "AgentBackendSelection",
    "AgentBackendSelectionError",
    "AdapterTaskCapabilities",
    "DeliveryCompletionAssessment",
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
    "WeComSessionRuntime",
    "WeComSessionRuntimeAction",
    "WeComSessionRuntimeOutcome",
    "WeComRuntimeIngress",
    "WeComWiredRuntime",
    "ack_response",
    "apply_output_policy",
    "append_runtime_audit",
    "assess_delivery_completion",
    "build_owned_notice",
    "build_file_send_envelope",
    "build_clarification_delivery",
    "build_template_card_envelope",
    "build_text_send_envelope",
    "build_wecom_channel_config",
    "build_wecom_wired_runtime",
    "create_task_flow",
    "deadline_exceeded",
    "load_wecom_channel_config",
    "normalize_wecom_feedback_callback",
    "normalize_wecom_turn",
    "parse_callback_envelope",
    "parse_bool_env",
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
