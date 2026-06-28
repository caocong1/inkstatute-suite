"""Phase 8 lawyer trial acceptance helpers.

The helpers in this module consume minimized evidence rows only. Runtime logs,
callback bodies, customer documents, and legal payload text stay outside the repo
behind reference fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_FORBIDDEN_PAYLOAD_KEY = "raw" + "_payload"


@dataclass(frozen=True)
class TrialTaskEvidence:
    task_ref: str
    evidence_kind: str
    workday: str
    participant_alias: str
    category: str
    started_at: str
    completed_at: str
    duration_seconds: float
    success: bool
    clear_business_output: bool
    feedback_captured: bool
    positive_feedback: bool
    negative_feedback: bool
    route_mismatch: bool
    response_action_ref: str | None
    response_action_at: str | None
    skill_candidate_ref: str | None
    routing_rule_candidate_ref: str | None
    output_boundary_checked: bool
    hermes_meta_leak_detected: bool
    turn_id: str | None = None
    conversation_id: str | None = None
    trace_id: str | None = None
    result_id: str | None = None
    feedback_id: str | None = None
    raw_payload_ref: str | None = None

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "TrialTaskEvidence":
        _reject_forbidden_payload_key(mapping)
        return cls(
            task_ref=_required_string(mapping, "task_ref"),
            evidence_kind=_required_string(mapping, "evidence_kind"),
            workday=_required_string(mapping, "workday"),
            participant_alias=_required_string(mapping, "participant_alias"),
            category=_required_string(mapping, "category"),
            started_at=_required_string(mapping, "started_at"),
            completed_at=_required_string(mapping, "completed_at"),
            duration_seconds=_required_float(mapping, "duration_seconds"),
            success=_required_bool(mapping, "success"),
            clear_business_output=_required_bool(mapping, "clear_business_output"),
            feedback_captured=_required_bool(mapping, "feedback_captured"),
            positive_feedback=_required_bool(mapping, "positive_feedback"),
            negative_feedback=_required_bool(mapping, "negative_feedback"),
            route_mismatch=_required_bool(mapping, "route_mismatch"),
            response_action_ref=_optional_string(mapping, "response_action_ref"),
            response_action_at=_optional_string(mapping, "response_action_at"),
            skill_candidate_ref=_optional_string(mapping, "skill_candidate_ref"),
            routing_rule_candidate_ref=_optional_string(mapping, "routing_rule_candidate_ref"),
            output_boundary_checked=_required_bool(mapping, "output_boundary_checked"),
            hermes_meta_leak_detected=_required_bool(mapping, "hermes_meta_leak_detected"),
            turn_id=_optional_string(mapping, "turn_id"),
            conversation_id=_optional_string(mapping, "conversation_id"),
            trace_id=_optional_string(mapping, "trace_id"),
            result_id=_optional_string(mapping, "result_id"),
            feedback_id=_optional_string(mapping, "feedback_id"),
            raw_payload_ref=_optional_string(mapping, "raw_payload_ref"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_ref": self.task_ref,
            "evidence_kind": self.evidence_kind,
            "workday": self.workday,
            "participant_alias": self.participant_alias,
            "category": self.category,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "clear_business_output": self.clear_business_output,
            "feedback_captured": self.feedback_captured,
            "positive_feedback": self.positive_feedback,
            "negative_feedback": self.negative_feedback,
            "route_mismatch": self.route_mismatch,
            "response_action_ref": self.response_action_ref,
            "response_action_at": self.response_action_at,
            "skill_candidate_ref": self.skill_candidate_ref,
            "routing_rule_candidate_ref": self.routing_rule_candidate_ref,
            "output_boundary_checked": self.output_boundary_checked,
            "hermes_meta_leak_detected": self.hermes_meta_leak_detected,
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "trace_id": self.trace_id,
            "result_id": self.result_id,
            "feedback_id": self.feedback_id,
            "raw_payload_ref": self.raw_payload_ref,
        }


@dataclass(frozen=True)
class TrialAcceptanceIssue:
    code: str
    severity: str
    message: str
    refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "refs": list(self.refs),
        }


@dataclass(frozen=True)
class TrialAcceptanceReport:
    status: str
    readiness_gates_passed: bool
    evidence_kind_counts: dict[str, int]
    live_task_count: int
    workday_count: int
    participant_count: int
    category_count: int
    clear_business_output_count: int
    long_task_count: int
    long_task_success_count: int
    ordinary_task_count: int
    ordinary_task_success_count: int
    feedback_captured_count: int
    positive_feedback_count: int
    negative_feedback_count: int
    route_mismatch_count: int
    output_boundary_checked_count: int
    hermes_meta_leak_count: int
    repair_plan_ref: str | None
    issues: tuple[TrialAcceptanceIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness_gates_passed": self.readiness_gates_passed,
            "evidence_kind_counts": dict(sorted(self.evidence_kind_counts.items())),
            "live_task_count": self.live_task_count,
            "workday_count": self.workday_count,
            "participant_count": self.participant_count,
            "category_count": self.category_count,
            "clear_business_output_count": self.clear_business_output_count,
            "long_task_count": self.long_task_count,
            "long_task_success_count": self.long_task_success_count,
            "ordinary_task_count": self.ordinary_task_count,
            "ordinary_task_success_count": self.ordinary_task_success_count,
            "feedback_captured_count": self.feedback_captured_count,
            "positive_feedback_count": self.positive_feedback_count,
            "negative_feedback_count": self.negative_feedback_count,
            "route_mismatch_count": self.route_mismatch_count,
            "output_boundary_checked_count": self.output_boundary_checked_count,
            "hermes_meta_leak_count": self.hermes_meta_leak_count,
            "repair_plan_ref": self.repair_plan_ref,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _reject_forbidden_payload_key(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) == _FORBIDDEN_PAYLOAD_KEY:
                raise ValueError("trial evidence must use references, not raw payload content")
            _reject_forbidden_payload_key(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_forbidden_payload_key(nested)


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if value is None:
        raise ValueError(f"missing required field: {key}")
    text = str(value)
    if not text:
        raise ValueError(f"empty required field: {key}")
    return text


def _optional_string(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    text = str(value)
    return text or None


def _required_float(mapping: Mapping[str, Any], key: str) -> float:
    value = mapping.get(key)
    if value is None:
        raise ValueError(f"missing required field: {key}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field: {key}") from exc


def _required_bool(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ValueError(f"invalid boolean field: {key}")


__all__ = [
    "TrialAcceptanceIssue",
    "TrialAcceptanceReport",
    "TrialTaskEvidence",
]
