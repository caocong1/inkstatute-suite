"""Map Hermes lawfirm hook context into InkStatute V2 contract events."""

from __future__ import annotations

import dataclasses
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping

from .ids import stable_hash_id

if TYPE_CHECKING:
    from inkstatute_router_service import RouterPort


EVENT_KEYS = ("agent_turn", "route_decision", "execution_trace", "agent_result")

ASYNC_TASK_STATES = {
    "queued",
    "running",
    "waiting_for_user",
    "succeeded",
    "failed",
    "cancelled",
}
CHANNELS = {"wecom", "qqbot", "web", "desktop"}
MESSAGE_TYPES = {"text", "file", "image", "voice", "button_callback"}
RESULT_STATUSES = {"success", "partial", "failed", "blocked", "needs_clarification"}
REPLY_TYPES = {"text", "markdown", "file", "card", "status_update"}
ROUTE_MODES = {"matched", "simple_qa", "skipped", "zero_match"}


def map_agent_end_context(
    context: Mapping[str, Any],
    *,
    now: datetime | str,
    seq_start: int = 0,
    router: "RouterPort | None" = None,
) -> OrderedDict[str, dict[str, Any]]:
    """Return AgentTurn, RouteDecision, ExecutionTrace, and AgentResult payloads."""

    timestamp = _timestamp(now)
    session_id = _string(context.get("session_id"), "unknown-session")
    user_id = _string(context.get("user_id"), "unknown-user")
    chat_id = _string(context.get("chat_id"), "unknown-chat")
    message = _string_or_none(context.get("message"))
    response = _string_or_none(context.get("response"))
    message_id = _string_or_none(context.get("message_id"))
    raw_payload_ref = _raw_payload_ref(context, session_id=session_id)

    turn_id = stable_hash_id("turn", session_id, user_id, message_id or message, timestamp)
    route_decision_id = stable_hash_id("route", turn_id, session_id, user_id, timestamp)
    trace_id = stable_hash_id("trace", turn_id, route_decision_id, timestamp)
    result_id = stable_hash_id("result", turn_id, message_id or response, timestamp)

    channel, channel_metadata = _normalize_channel(context.get("platform"))
    message_type, message_type_metadata = _normalize_message_type(context.get("message_type"))
    primary_skill = _string_or_none(context.get("active_skill_name") or context.get("skill_name"))
    route_mode = _route_mode(context, primary_skill)
    matched_registered_skill = route_mode == "matched" and primary_skill is not None
    route_mismatch = bool(context.get("route_mismatch")) or route_mode == "zero_match"
    route_confidence = _confidence(context.get("route_confidence"), matched_registered_skill, route_mode)
    status = _result_status(context, route_mismatch=route_mismatch)
    reply_type = _reply_type(context, status=status)
    errors = _errors(context, status=status, raw_payload_ref=raw_payload_ref)

    industry_context = _industry_context(context)
    agent_turn = {
        "turn_id": turn_id,
        "conversation_id": session_id,
        "channel": channel,
        "user_id": user_id,
        "message_type": message_type,
        "received_at": _received_at(context, timestamp),
        "industry_context": industry_context,
        "metadata": {
            "profile": "lawfirm",
            "chat_id": chat_id,
            "message_id": message_id,
            "raw_payload_ref": raw_payload_ref,
            "source_event": "agent:end",
            "source_status": "agent_end_reverse_inference",
            "content_source": "agent:end.message",
            "content_source_status": "source_confirmed_partial" if message else "unavailable",
            "content_truncated": _is_truncated(message, context.get("message_truncated")),
            "attachments_source_status": "unavailable",
            "output_constraints_source_status": "unavailable",
            **channel_metadata,
            **message_type_metadata,
        },
    }
    if message is not None:
        agent_turn["content"] = message
    if "received_at" not in context:
        agent_turn["metadata"]["received_at_source_status"] = "unavailable_substituted_with_mapper_time"

    if router is not None:
        try:
            decision = router.decide(context)
            route_decision = _route_decision_to_dict(
                decision, route_decision_id, turn_id, timestamp, raw_payload_ref, industry_context,
            )
        except Exception:
            route_decision = _inline_route_decision(
                context, route_decision_id, turn_id, primary_skill, route_mode,
                matched_registered_skill, route_mismatch, route_confidence,
                raw_payload_ref, industry_context, timestamp,
            )
    else:
        route_decision = _inline_route_decision(
            context, route_decision_id, turn_id, primary_skill, route_mode,
            matched_registered_skill, route_mismatch, route_confidence,
            raw_payload_ref, industry_context, timestamp,
        )

    execution_trace = {
        "trace_id": trace_id,
        "turn_id": turn_id,
        "started_at": _timestamp(context.get("started_at") or timestamp),
        "ended_at": _timestamp(context.get("ended_at") or timestamp),
        "active_skill_name": primary_skill,
        "matched_registered_skill": matched_registered_skill,
        "occurred_at": timestamp,
        "ingested_at": timestamp,
        "seq": seq_start + 2,
        "steps": _steps(context, status=status),
        "tool_calls": _metadata_list(context.get("tool_calls")),
        "artifacts_written": _string_list(context.get("artifacts_written")),
        "route_decision": _route_reference(route_decision),
        "gates": _metadata_list(context.get("gates")),
        "errors": errors,
        "industry_context": industry_context,
        "metadata": {
            "raw_payload_ref": raw_payload_ref,
            "source_event": "agent:end",
            "async_state_source_status": "source_confirmed_if_present_else_unavailable",
        },
    }

    agent_result = {
        "result_id": result_id,
        "turn_id": turn_id,
        "status": status,
        "reply_type": reply_type,
        "artifacts": _artifacts(context.get("artifacts")),
        "clarifying_questions": _string_list(context.get("clarifying_questions")),
        "route_mismatch": route_mismatch,
        "industry_context": industry_context,
        "metadata": {
            "trace_id": trace_id,
            "route_decision_id": route_decision_id,
            "raw_payload_ref": raw_payload_ref,
            "source_event": "agent:end",
            "response_source": "agent:end.response",
            "response_source_status": "source_confirmed_partial" if response else "unavailable",
            "response_truncated": _is_truncated(response, context.get("response_truncated")),
            "feedback_target_source": "message_id" if message_id else "unavailable",
        },
    }
    if response is not None:
        agent_result["content"] = response
    if message_id is not None:
        agent_result["feedback_target"] = message_id
    if errors:
        agent_result["error"] = errors[0]
    if route_mismatch:
        agent_result["skill_candidate"] = _skill_candidate(context)

    return OrderedDict(
        (
            ("agent_turn", agent_turn),
            ("route_decision", route_decision),
            ("execution_trace", execution_trace),
            ("agent_result", agent_result),
        )
    )


def _inline_route_decision(
    context: Mapping[str, Any],
    route_decision_id: str,
    turn_id: str,
    primary_skill: str | None,
    route_mode: str,
    matched_registered_skill: bool,
    route_mismatch: bool,
    route_confidence: float,
    raw_payload_ref: str | None,
    industry_context: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    """Construct the inline route_decision dict (preserves existing JSONL shape)."""
    route_decision = {
        "route_decision_id": route_decision_id,
        "turn_id": turn_id,
        "primary_skill": primary_skill,
        "supporting_skills": _string_list(context.get("supporting_skills")),
        "gates_before": _string_list(context.get("gates_before")),
        "gates_after": _string_list(context.get("gates_after")),
        "required_tools": _string_list(context.get("required_tools")),
        "confidence": route_confidence,
        "reason": _route_reason(route_mode, matched_registered_skill),
        "mode": route_mode,
        "route_mismatch": route_mismatch,
        "created_at": timestamp,
        "industry_context": industry_context,
        "metadata": {
            "route_source": "hermes_hook_context",
            "router_output_source_status": "unavailable",
            "matched_registered_skill": matched_registered_skill,
            "raw_payload_ref": raw_payload_ref,
        },
    }
    if matched_registered_skill:
        route_decision["matched_rule"] = _string(
            context.get("matched_rule"),
            f"hermes_active_skill:{primary_skill}",
        )
    return route_decision


def _route_decision_to_dict(
    decision: Any,
    route_decision_id: str,
    turn_id: str,
    timestamp: str,
    raw_payload_ref: str | None,
    industry_context: dict[str, Any],
) -> dict[str, Any]:
    """Convert a frozen ``RouteDecision`` dataclass to a dict matching the inline JSONL shape.

    Overrides ``route_decision_id``, ``turn_id``, ``created_at`` with
    mapper-computed values for event chain consistency.  Preserves the
    dataclass ``metadata`` dict (includes ``router_strategy``,
    ``router_service_version``).
    """
    route_dict = dataclasses.asdict(decision)
    route_dict["route_decision_id"] = route_decision_id
    route_dict["turn_id"] = turn_id
    route_dict["created_at"] = timestamp
    route_dict["industry_context"] = industry_context
    route_dict["route_mismatch"] = bool(route_dict.get("route_mismatch"))
    # Ensure required string fields are never None (schema expects strings)
    if route_dict.get("reason") is None:
        route_dict["reason"] = "Route decision produced by injected router."
    route_dict["metadata"]["raw_payload_ref"] = raw_payload_ref
    if route_dict.get("matched_rule") is None:
        route_dict.pop("matched_rule", None)
    return route_dict


def _timestamp(value: datetime | str | Any) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        if value.endswith("+00:00"):
            return value[:-6] + "Z"
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _normalize_channel(value: Any) -> tuple[str, dict[str, Any]]:
    raw = _string_or_none(value)
    normalized = (raw or "").lower().replace("-", "_")
    aliases = {
        "wechat_work": "wecom",
        "wework": "wecom",
        "enterprise_wechat": "wecom",
        "qq_bot": "qqbot",
    }
    channel = aliases.get(normalized, normalized)
    if channel in CHANNELS:
        return channel, {"channel_source_status": "source_confirmed", "raw_platform": raw}
    return "web", {"channel_source_status": "unavailable_defaulted", "raw_platform": raw}


def _normalize_message_type(value: Any) -> tuple[str, dict[str, Any]]:
    raw = _string_or_none(value)
    normalized = (raw or "").lower()
    if normalized in MESSAGE_TYPES:
        return normalized, {"message_type_source_status": "source_confirmed"}
    return "text", {"message_type_source_status": "unavailable_defaulted"}


def _route_mode(context: Mapping[str, Any], primary_skill: str | None) -> str:
    explicit = _string_or_none(context.get("route_mode"))
    if explicit in ROUTE_MODES:
        return explicit
    if context.get("route_mismatch") or context.get("route_error") or context.get("zero_match"):
        return "zero_match"
    if primary_skill:
        return "matched"
    return "simple_qa"


def _confidence(value: Any, matched_registered_skill: bool, route_mode: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return min(1.0, max(0.0, float(value)))
    if matched_registered_skill:
        return 1.0
    if route_mode == "simple_qa":
        return 0.5
    return 0.0


def _route_reason(route_mode: str, matched_registered_skill: bool) -> str:
    if matched_registered_skill:
        return "Mapped from Hermes active skill metadata in post-filter hook context."
    if route_mode == "zero_match":
        return "Hermes route output was unavailable or unmatched in hook context."
    if route_mode == "simple_qa":
        return "No registered skill was exposed; recorded as simple question-answer path."
    return "Route decision was unavailable in Hermes hook context."


def _result_status(context: Mapping[str, Any], *, route_mismatch: bool) -> str:
    raw = _string_or_none(context.get("status") or context.get("result_status"))
    if raw in RESULT_STATUSES:
        return raw
    if context.get("error") or context.get("errors"):
        return "failed"
    if route_mismatch and context.get("route_error"):
        return "failed"
    return "success"


def _reply_type(context: Mapping[str, Any], *, status: str) -> str:
    raw = _string_or_none(context.get("reply_type"))
    if status == "failed":
        return "status_update"
    if raw in REPLY_TYPES:
        return raw
    return "text"


def _received_at(context: Mapping[str, Any], fallback: str) -> str:
    if "received_at" in context:
        return _timestamp(context.get("received_at"))
    return fallback


def _raw_payload_ref(context: Mapping[str, Any], *, session_id: str) -> str:
    raw_ref = _string_or_none(context.get("raw_payload_ref"))
    if raw_ref:
        return raw_ref
    turn_ref = _string_or_none(context.get("message_id") or context.get("message_ref") or context.get("trace_id"))
    if turn_ref:
        return f"hermes://session/{session_id}/turn/{turn_ref}"
    return f"hermes://session/{session_id}/turn/unavailable"


def _industry_context(context: Mapping[str, Any]) -> dict[str, Any]:
    supplied = context.get("industry_context")
    if isinstance(supplied, dict):
        clean = _metadata_dict(supplied)
        return {**clean, "domain": clean.get("domain", "lawfirm"), "profile": clean.get("profile", "lawfirm")}
    return {"domain": "lawfirm", "profile": "lawfirm"}


def _is_truncated(value: str | None, explicit: Any) -> bool:
    if isinstance(explicit, bool):
        return explicit
    return bool(value and len(value) >= 500)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _metadata_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_metadata_dict(item) for item in value if isinstance(item, dict)]


def _steps(context: Mapping[str, Any], *, status: str) -> list[dict[str, Any]]:
    raw_states = context.get("async_states")
    steps: list[dict[str, Any]] = []
    skipped_states: list[str] = []

    if isinstance(raw_states, list):
        for index, item in enumerate(raw_states):
            if isinstance(item, dict):
                state = _string_or_none(item.get("state"))
                name = _string(item.get("name"), f"async_state_{index}")
            else:
                state = _string_or_none(item)
                name = f"async_state_{index}"
            if state in ASYNC_TASK_STATES:
                steps.append({"name": name, "state": state})
            elif state:
                skipped_states.append(state)

    if not steps and status == "failed":
        steps.append({"name": "agent_end_observed_failure", "state": "failed"})
    if not steps:
        steps.append({"name": "agent_end_observed", "async_state_source_status": "unavailable"})
    if skipped_states:
        steps.append({"name": "async_state_filter", "skipped_unrecognized_states": skipped_states})
    return steps


def _errors(context: Mapping[str, Any], *, status: str, raw_payload_ref: str) -> list[dict[str, Any]]:
    raw_errors = context.get("errors")
    if isinstance(raw_errors, list) and raw_errors:
        return [_error_info(item, raw_payload_ref=raw_payload_ref) for item in raw_errors if isinstance(item, dict)]

    raw_error = context.get("error")
    if isinstance(raw_error, dict):
        return [_error_info(raw_error, raw_payload_ref=raw_payload_ref)]

    if status == "failed":
        return [
            {
                "category": "runtime_error",
                "message": "Hermes task failed; source error detail unavailable.",
                "stage": _string(context.get("error_stage"), "agent_execution"),
                "retryable": bool(context.get("retryable", False)),
                "details": {"raw_payload_ref": raw_payload_ref, "source_status": "unavailable"},
            }
        ]
    return []


def _error_info(error: Mapping[str, Any], *, raw_payload_ref: str) -> dict[str, Any]:
    info = {
        "category": _string(error.get("category"), "runtime_error")
        if error.get("category") in {"runtime_error", "contract_error", "channel_error"}
        else "runtime_error",
        "details": {"raw_payload_ref": raw_payload_ref},
    }
    for key in ("code", "message", "stage"):
        value = _string_or_none(error.get(key))
        if value:
            info[key] = value[:240]
    if isinstance(error.get("retryable"), bool):
        info["retryable"] = error["retryable"]
    details = error.get("details")
    if isinstance(details, dict):
        info["details"].update(_metadata_dict(details))
    return info


def _route_reference(route_decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "route_decision_id": route_decision["route_decision_id"],
        "turn_id": route_decision["turn_id"],
        "primary_skill": route_decision["primary_skill"],
        "confidence": route_decision["confidence"],
        "mode": route_decision["mode"],
        "created_at": route_decision["created_at"],
    }


def _artifacts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        artifact_id = _string(item.get("artifact_id"), f"artifact-{index}")
        kind = _string(item.get("kind"), "other")
        if kind not in {"docx", "pptx", "trackchanges_docx", "xlsx", "pdf", "markdown", "json", "other"}:
            kind = "other"
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "kind": kind,
                "name": _string(item.get("name"), artifact_id),
                "uri": _string(item.get("uri"), f"hermes://artifact/{artifact_id}"),
                "metadata": _metadata_dict(item.get("metadata")) if isinstance(item.get("metadata"), dict) else {},
            }
        )
    return artifacts


def _skill_candidate(context: Mapping[str, Any]) -> dict[str, Any]:
    proposed_name = _string(context.get("skill_candidate_name"), "unmatched_lawfirm_task")
    return {
        "detected": True,
        "source": "route_mismatch",
        "proposed_name": proposed_name,
        "risk_level": "medium",
        "requires_human_review": True,
        "evidence": ["Hermes hook context did not expose a matched registered skill."],
        "metadata": {"no_auto_modify": True},
    }


def _metadata_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _metadata_value(child)
        for key, child in value.items()
        if str(key) != "raw_payload"
    }


def _metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _metadata_dict(value)
    if isinstance(value, list):
        return [_metadata_value(item) for item in value]
    return value
