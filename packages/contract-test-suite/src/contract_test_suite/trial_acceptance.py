"""Phase 8 lawyer trial acceptance helpers.

The helpers in this module consume minimized evidence rows only. Runtime logs,
callback bodies, customer documents, and legal payload text stay outside the repo
behind reference fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


_FORBIDDEN_PAYLOAD_KEY = "raw" + "_payload"
LIVE_EVIDENCE_KINDS = frozenset({"sanitized_runtime", "operator_annotation", "live_external_ref"})
LONG_TASK_SECONDS = 60.0
NEGATIVE_FEEDBACK_RESPONSE_WINDOW = timedelta(hours=48)


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

    @property
    def long_task_success_rate(self) -> float:
        return _rate(self.long_task_success_count, self.long_task_count)

    @property
    def ordinary_task_success_rate(self) -> float:
        return _rate(self.ordinary_task_success_count, self.ordinary_task_count)

    @property
    def feedback_capture_rate(self) -> float:
        return _rate(self.feedback_captured_count, self.live_task_count)

    @property
    def positive_feedback_share(self) -> float:
        return _rate(self.positive_feedback_count, self.feedback_captured_count)

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
            "rates": {
                "long_task_success_rate": self.long_task_success_rate,
                "ordinary_task_success_rate": self.ordinary_task_success_rate,
                "feedback_capture_rate": self.feedback_capture_rate,
                "positive_feedback_share": self.positive_feedback_share,
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


def evaluate_trial_acceptance(
    rows: Iterable[TrialTaskEvidence | Mapping[str, Any]],
    *,
    readiness_gates_passed: bool = False,
    repair_plan_ref: str | None = None,
    now: datetime | str | None = None,
) -> TrialAcceptanceReport:
    if now is not None:
        _parse_datetime(now)

    normalized_rows = tuple(_coerce_row(row) for row in rows)
    evidence_kind_counts = _count_evidence_kinds(normalized_rows)
    live_rows = tuple(row for row in normalized_rows if row.evidence_kind in LIVE_EVIDENCE_KINDS)

    live_task_count = len(live_rows)
    workday_count = len({row.workday for row in live_rows})
    participant_count = len({row.participant_alias for row in live_rows})
    category_count = len({row.category for row in live_rows})
    clear_business_output_count = sum(1 for row in live_rows if row.clear_business_output)
    long_rows = tuple(row for row in live_rows if row.duration_seconds > LONG_TASK_SECONDS)
    ordinary_rows = tuple(row for row in live_rows if row.duration_seconds <= LONG_TASK_SECONDS)
    long_task_success_count = sum(1 for row in long_rows if row.success)
    ordinary_task_success_count = sum(1 for row in ordinary_rows if row.success)
    feedback_captured_count = sum(1 for row in live_rows if row.feedback_captured)
    positive_feedback_count = sum(1 for row in live_rows if row.feedback_captured and row.positive_feedback)
    negative_feedback_count = sum(1 for row in live_rows if row.negative_feedback)
    route_mismatch_count = sum(1 for row in live_rows if row.route_mismatch)
    output_boundary_checked_count = sum(1 for row in live_rows if row.output_boundary_checked)
    hermes_meta_leak_count = sum(1 for row in live_rows if row.hermes_meta_leak_detected)

    issues: list[TrialAcceptanceIssue] = []
    if not normalized_rows:
        issues.append(_issue("trial_evidence_pending", "pending", "No trial task evidence has been supplied."))
    elif not live_rows:
        issues.append(
            _issue(
                "no_live_trial_evidence",
                "blocked",
                "Fixture or synthetic rows cannot count toward live lawyer trial acceptance.",
            )
        )
    elif not readiness_gates_passed:
        issues.append(
            _issue(
                "readiness_gates_missing",
                "blocked",
                "Live InkStatute WeCom, no-channel-io, and output-boundary gates must pass before counting trial rows.",
            )
        )

    if live_rows and readiness_gates_passed:
        if workday_count < 5:
            issues.append(_issue("workdays_below_threshold", "failed", "Trial must span at least 5 workdays."))
        if participant_count < 1:
            issues.append(_issue("participant_missing", "failed", "Trial requires at least 1 participant alias."))
        if live_task_count < 15:
            issues.append(_issue("task_count_below_threshold", "failed", "Trial requires at least 15 live tasks."))
        if clear_business_output_count < 12:
            issues.append(
                _issue("clear_business_output_below_threshold", "failed", "At least 12 tasks need clear business output.")
            )
        if category_count < 3:
            issues.append(_issue("category_coverage_below_threshold", "failed", "Trial must cover at least 3 categories."))
        if _rate(long_task_success_count, len(long_rows)) < 0.80:
            issues.append(_issue("long_task_success_below_threshold", "failed", "Long-task success rate must be at least 80%."))
        if _rate(ordinary_task_success_count, len(ordinary_rows)) < 0.85:
            issues.append(
                _issue("ordinary_task_success_below_threshold", "failed", "Ordinary-task success rate must be at least 85%.")
            )
        if _rate(feedback_captured_count, live_task_count) < 0.60:
            issues.append(_issue("feedback_capture_below_threshold", "failed", "Feedback capture rate must be at least 60%."))
        if _rate(positive_feedback_count, feedback_captured_count) < 0.60:
            if repair_plan_ref:
                issues.append(
                    _issue(
                        "positive_feedback_repair_plan",
                        "repair_plan",
                        "Positive feedback share is below 60%, but a repair plan is linked.",
                    )
                )
            else:
                issues.append(
                    _issue(
                        "positive_feedback_below_threshold",
                        "failed",
                        "Positive feedback share must be at least 60% or link a categorized repair plan.",
                    )
                )
        if route_mismatch_count > 3:
            issues.append(_issue("route_mismatch_above_threshold", "failed", "Route mismatch count must be no more than 3."))

        for row in live_rows:
            if row.route_mismatch and not (row.skill_candidate_ref or row.routing_rule_candidate_ref):
                issues.append(
                    _issue(
                        "route_mismatch_missing_candidate",
                        "failed",
                        "Every route mismatch needs skill or routing-rule candidate evidence.",
                        row.task_ref,
                    )
                )
            if row.negative_feedback:
                response_issue = _negative_feedback_response_issue(row)
                if response_issue is not None:
                    issues.append(response_issue)
            if not row.output_boundary_checked:
                issues.append(
                    _issue(
                        "output_boundary_check_missing",
                        "failed",
                        "Every live row must have output-boundary evidence.",
                        row.task_ref,
                    )
                )
            if row.hermes_meta_leak_detected:
                issues.append(
                    _issue(
                        "hermes_meta_leak_detected",
                        "failed",
                        "Hermes meta or gateway notices block acceptance until repaired and re-tested.",
                        row.task_ref,
                    )
                )

    return TrialAcceptanceReport(
        status=_status_from_issues(issues),
        readiness_gates_passed=readiness_gates_passed,
        evidence_kind_counts=evidence_kind_counts,
        live_task_count=live_task_count,
        workday_count=workday_count,
        participant_count=participant_count,
        category_count=category_count,
        clear_business_output_count=clear_business_output_count,
        long_task_count=len(long_rows),
        long_task_success_count=long_task_success_count,
        ordinary_task_count=len(ordinary_rows),
        ordinary_task_success_count=ordinary_task_success_count,
        feedback_captured_count=feedback_captured_count,
        positive_feedback_count=positive_feedback_count,
        negative_feedback_count=negative_feedback_count,
        route_mismatch_count=route_mismatch_count,
        output_boundary_checked_count=output_boundary_checked_count,
        hermes_meta_leak_count=hermes_meta_leak_count,
        repair_plan_ref=repair_plan_ref,
        issues=tuple(issues),
    )


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


def _coerce_row(row: TrialTaskEvidence | Mapping[str, Any]) -> TrialTaskEvidence:
    if isinstance(row, TrialTaskEvidence):
        _reject_forbidden_payload_key(row.to_dict())
        return row
    return TrialTaskEvidence.from_mapping(row)


def _count_evidence_kinds(rows: tuple[TrialTaskEvidence, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.evidence_kind] = counts.get(row.evidence_kind, 0) + 1
    return counts


def _issue(code: str, severity: str, message: str, *refs: str) -> TrialAcceptanceIssue:
    return TrialAcceptanceIssue(code=code, severity=severity, message=message, refs=tuple(refs))


def _negative_feedback_response_issue(row: TrialTaskEvidence) -> TrialAcceptanceIssue | None:
    if not row.response_action_ref or not row.response_action_at:
        return _issue(
            "negative_feedback_response_missing",
            "failed",
            "Negative feedback requires a response action record within 48 hours.",
            row.task_ref,
        )

    completed_at = _parse_datetime(row.completed_at)
    response_at = _parse_datetime(row.response_action_at)
    if completed_at is None or response_at is None:
        return _issue(
            "negative_feedback_response_time_invalid",
            "failed",
            "Negative feedback response timestamps must be parseable.",
            row.task_ref,
        )
    if response_at < completed_at or response_at - completed_at > NEGATIVE_FEEDBACK_RESPONSE_WINDOW:
        return _issue(
            "negative_feedback_response_late",
            "failed",
            "Negative feedback response action must be recorded within 48 hours.",
            row.task_ref,
        )
    return None


def _parse_datetime(value: datetime | str) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _status_from_issues(issues: list[TrialAcceptanceIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if "pending" in severities:
        return "pending"
    if "blocked" in severities:
        return "blocked"
    if "failed" in severities:
        return "failed"
    if "repair_plan" in severities:
        return "passed_with_repair_plan"
    return "passed"


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


__all__ = [
    "LIVE_EVIDENCE_KINDS",
    "TrialAcceptanceIssue",
    "TrialAcceptanceReport",
    "TrialTaskEvidence",
    "evaluate_trial_acceptance",
]
