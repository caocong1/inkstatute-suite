"""InkStatute-owned WeCom service primitives."""

from .idempotency import wecom_idempotency_key
from .normalization import normalize_wecom_feedback_callback, normalize_wecom_turn
from .output_policy import OutputPolicyDecision, apply_output_policy
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

__all__ = [
    "OutputPolicyDecision",
    "RawPayloadForbiddenError",
    "ack_response",
    "apply_output_policy",
    "build_file_send_envelope",
    "build_template_card_envelope",
    "build_text_send_envelope",
    "normalize_wecom_feedback_callback",
    "normalize_wecom_turn",
    "parse_callback_envelope",
    "verify_callback_signature",
    "wecom_idempotency_key",
]
