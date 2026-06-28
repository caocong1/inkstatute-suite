"""Validate WeCom shadow-loop evidence without touching Hermes runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

from contract_test_suite.event_stream_replay import CORE_PHASE4_EVENT_KEYS, load_event_stream


ACK_TIMEOUT_SECONDS = 5.0
SECRET_LIKE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)

__all__ = [
    "WeComValidationIssue",
    "WeComValidationReport",
    "validate_wecom_shadow_evidence",
]


@dataclass(frozen=True)
class WeComValidationIssue:
    code: str
    message: str
    path: str | None = None
    event_key: str | None = None


@dataclass(frozen=True)
class WeComValidationReport:
    passed: bool
    issues: list[WeComValidationIssue]
    event_count: int
    feedback_target: str | None = None
    live_status: str = "fixture"


def validate_wecom_shadow_evidence(
    stream_path: str | Path,
    *,
    channel: str = "wecom",
    ack_started_at: str | datetime | None = None,
    ack_completed_at: str | datetime | None = None,
    feedback_expected: bool = True,
    live_status: str = "fixture",
) -> WeComValidationReport:
    """Validate a sanitized contract event stream for Phase 5 WeCom evidence."""

    issues: list[WeComValidationIssue] = []
    try:
        records = load_event_stream(stream_path)
    except Exception as exc:
        return WeComValidationReport(
            passed=False,
            issues=[
                WeComValidationIssue(
                    code="stream_invalid",
                    message=str(exc),
                    path=str(stream_path),
                )
            ],
            event_count=0,
            live_status=live_status,
        )

    events = {record.event_key: record.event for record in records}
    for event_key in CORE_PHASE4_EVENT_KEYS:
        if event_key not in events:
            issues.append(
                WeComValidationIssue(
                    code="missing_core_event",
                    message=f"event stream is missing required event {event_key}",
                    path=event_key,
                    event_key=event_key,
                )
            )

    agent_turn = events.get("agent_turn")
    if isinstance(agent_turn, dict):
        actual_channel = agent_turn.get("channel")
        if actual_channel != channel:
            issues.append(
                WeComValidationIssue(
                    code="non_wecom_channel",
                    message=f"expected agent_turn.channel to be {channel!r}, got {actual_channel!r}",
                    path="agent_turn.channel",
                    event_key="agent_turn",
                )
            )

    agent_result = events.get("agent_result")
    feedback_target = agent_result.get("feedback_target") if isinstance(agent_result, dict) else None
    if feedback_expected and not feedback_target:
        issues.append(
            WeComValidationIssue(
                code="missing_feedback_target",
                message="agent_result.feedback_target is required for WeCom callback validation",
                path="agent_result.feedback_target",
                event_key="agent_result",
            )
        )

    issues.extend(_ack_issues(ack_started_at, ack_completed_at))
    for record in records:
        issues.extend(_privacy_issues(record.event, path=record.event_key, event_key=record.event_key))

    return WeComValidationReport(
        passed=not issues,
        issues=issues,
        event_count=len(records),
        feedback_target=feedback_target if isinstance(feedback_target, str) else None,
        live_status=live_status,
    )


def _ack_issues(
    ack_started_at: str | datetime | None,
    ack_completed_at: str | datetime | None,
) -> list[WeComValidationIssue]:
    if ack_started_at is None and ack_completed_at is None:
        return []
    if ack_started_at is None or ack_completed_at is None:
        return [
            WeComValidationIssue(
                code="ack_evidence_incomplete",
                message="both ack_started_at and ack_completed_at are required when ACK timing is supplied",
                path="ack",
            )
        ]

    started = _parse_timestamp(ack_started_at)
    completed = _parse_timestamp(ack_completed_at)
    if started is None or completed is None:
        return [
            WeComValidationIssue(
                code="ack_time_invalid",
                message="ACK timestamps must be ISO-8601 strings or datetime objects",
                path="ack",
            )
        ]

    elapsed = (completed - started).total_seconds()
    if elapsed < 0:
        return [
            WeComValidationIssue(
                code="ack_time_invalid",
                message="ack_completed_at cannot be earlier than ack_started_at",
                path="ack",
            )
        ]
    if elapsed > ACK_TIMEOUT_SECONDS:
        return [
            WeComValidationIssue(
                code="ack_timeout",
                message=f"ACK exceeded {ACK_TIMEOUT_SECONDS:.0f}s timeout",
                path="ack",
            )
        ]
    return []


def _parse_timestamp(value: str | datetime) -> datetime | None:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    normalized = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc)


def _privacy_issues(value: Any, *, path: str, event_key: str) -> list[WeComValidationIssue]:
    issues: list[WeComValidationIssue] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "raw_payload":
                issues.append(
                    WeComValidationIssue(
                        code="raw_payload_forbidden",
                        message="exact raw_payload keys are not allowed in validation evidence",
                        path=child_path,
                        event_key=event_key,
                    )
                )
            issues.extend(_privacy_issues(child, path=child_path, event_key=event_key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_privacy_issues(child, path=f"{path}[{index}]", event_key=event_key))
    elif isinstance(value, str) and SECRET_LIKE.search(value):
        issues.append(
            WeComValidationIssue(
                code="secret_like_value",
                message="secret-like text is not allowed in validation evidence",
                path=path,
                event_key=event_key,
            )
        )
    return issues
