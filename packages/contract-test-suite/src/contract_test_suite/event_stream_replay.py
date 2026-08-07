"""Replay helpers for Phase 4 JSONL contract event streams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema_validation import ContractValidationError, EVENT_SCHEMA_BY_KEY, load_schemas, validate_event


class EventStreamReplayError(AssertionError):
    """Raised when an event stream cannot be parsed or schema-validated."""


@dataclass(frozen=True)
class EventStreamRecord:
    path: Path
    line_number: int
    event_key: str
    occurred_at: str
    ingested_at: str
    seq: int
    event: dict[str, Any]


@dataclass(frozen=True)
class EventStreamIssue:
    stream_path: Path
    event_key: str | None
    relationship: str
    field_path: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class EventStreamReport:
    stream_count: int
    record_count: int
    relationship_check_count: int
    broken_relationship_count: int
    breakage_rate: float
    issues: list[EventStreamIssue]


ENVELOPE_FIELDS = {"event_key", "occurred_at", "ingested_at", "seq", "event"}
CORE_PHASE4_EVENT_KEYS = ("agent_turn", "route_decision", "execution_trace", "agent_result")


def load_event_stream(
    path: str | Path,
    *,
    schemas: dict[str, dict[str, Any]] | None = None,
) -> list[EventStreamRecord]:
    stream_path = Path(path)
    loaded_schemas = schemas if schemas is not None else load_schemas()
    records: list[EventStreamRecord] = []

    for line_number, line in enumerate(stream_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw_record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EventStreamReplayError(f"{stream_path}:{line_number}: invalid JSONL record") from exc

        record = _coerce_record(stream_path, line_number, raw_record)
        try:
            validate_event(record.event_key, record.event, loaded_schemas, fixture_id=str(stream_path))
        except ContractValidationError as exc:
            raise EventStreamReplayError(f"{stream_path}:{line_number}: {exc}") from exc
        records.append(record)

    if not records:
        raise EventStreamReplayError(f"{stream_path}: event stream is empty")
    return records


def replay_event_streams(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    schemas: dict[str, dict[str, Any]] | None = None,
) -> EventStreamReport:
    loaded_schemas = schemas if schemas is not None else load_schemas()
    total_records = 0
    total_checks = 0
    issues: list[EventStreamIssue] = []

    for path in paths:
        records = load_event_stream(path, schemas=loaded_schemas)
        total_records += len(records)
        check_count, stream_issues = _check_stream_relationships(records)
        total_checks += check_count
        issues.extend(stream_issues)

    broken_checks = len(issues)
    breakage_rate = broken_checks / total_checks if total_checks else 0.0
    return EventStreamReport(
        stream_count=len(paths),
        record_count=total_records,
        relationship_check_count=total_checks,
        broken_relationship_count=broken_checks,
        breakage_rate=breakage_rate,
        issues=issues,
    )


def assert_event_stream_integrity(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    max_breakage_rate: float = 0.05,
    schemas: dict[str, dict[str, Any]] | None = None,
) -> EventStreamReport:
    report = replay_event_streams(paths, schemas=schemas)
    if report.breakage_rate > max_breakage_rate:
        details = "; ".join(_format_issue(issue) for issue in report.issues)
        raise AssertionError(
            f"event stream relationship breakage rate {report.breakage_rate:.2%} exceeds "
            f"{max_breakage_rate:.2%}: {details}"
        )
    return report


def _coerce_record(path: Path, line_number: int, raw_record: Any) -> EventStreamRecord:
    if not isinstance(raw_record, dict):
        raise EventStreamReplayError(f"{path}:{line_number}: envelope must be object")

    fields = set(raw_record)
    missing = sorted(ENVELOPE_FIELDS - fields)
    if missing:
        raise EventStreamReplayError(f"{path}:{line_number}: envelope missing {missing[0]}")
    extra = sorted(fields - ENVELOPE_FIELDS)
    if extra:
        raise EventStreamReplayError(f"{path}:{line_number}: envelope rejected extra field {extra[0]}")

    event_key = raw_record["event_key"]
    if not isinstance(event_key, str) or event_key not in EVENT_SCHEMA_BY_KEY:
        raise EventStreamReplayError(f"{path}:{line_number}: unknown event_key {event_key!r}")
    if not isinstance(raw_record["occurred_at"], str):
        raise EventStreamReplayError(f"{path}:{line_number}: occurred_at must be string")
    if not isinstance(raw_record["ingested_at"], str):
        raise EventStreamReplayError(f"{path}:{line_number}: ingested_at must be string")
    if not isinstance(raw_record["seq"], int) or isinstance(raw_record["seq"], bool):
        raise EventStreamReplayError(f"{path}:{line_number}: seq must be integer")
    if raw_record["seq"] < 0:
        raise EventStreamReplayError(f"{path}:{line_number}: seq must be non-negative")
    if not isinstance(raw_record["event"], dict):
        raise EventStreamReplayError(f"{path}:{line_number}: event must be object")

    return EventStreamRecord(
        path=path,
        line_number=line_number,
        event_key=event_key,
        occurred_at=raw_record["occurred_at"],
        ingested_at=raw_record["ingested_at"],
        seq=raw_record["seq"],
        event=raw_record["event"],
    )


def _check_stream_relationships(records: list[EventStreamRecord]) -> tuple[int, list[EventStreamIssue]]:
    stream_path = records[0].path
    checks: list[tuple[str | None, str, str, Any, Any]] = []
    issues: list[EventStreamIssue] = []
    event_by_key: dict[str, EventStreamRecord] = {}

    seqs = [record.seq for record in records]
    checks.append((None, "seq_monotonic", "envelope.seq", sorted(seqs), seqs))
    checks.append((None, "seq_unique", "envelope.seq", len(set(seqs)), len(seqs)))

    for record in records:
        if record.event_key in event_by_key:
            issues.append(
                EventStreamIssue(
                    stream_path=stream_path,
                    event_key=record.event_key,
                    relationship="duplicate_event_key",
                    field_path="event_key",
                    expected="unique",
                    actual=record.event_key,
                )
            )
        event_by_key[record.event_key] = record

    for event_key in CORE_PHASE4_EVENT_KEYS:
        checks.append((event_key, "core_event_present", event_key, "present", "present" if event_key in event_by_key else "missing"))

    agent_turn = event_by_key.get("agent_turn")
    route_decision = event_by_key.get("route_decision")
    execution_trace = event_by_key.get("execution_trace")
    agent_result = event_by_key.get("agent_result")
    if not all((agent_turn, route_decision, execution_trace, agent_result)):
        return _finalize_checks(stream_path, checks, issues)

    assert agent_turn is not None and route_decision is not None and execution_trace is not None and agent_result is not None
    turn_id = agent_turn.event["turn_id"]
    checks.extend(
        [
            ("route_decision", "turn_id", "route_decision.turn_id", turn_id, route_decision.event.get("turn_id")),
            ("execution_trace", "turn_id", "execution_trace.turn_id", turn_id, execution_trace.event.get("turn_id")),
            ("agent_result", "turn_id", "agent_result.turn_id", turn_id, agent_result.event.get("turn_id")),
        ]
    )

    route_decision_id = route_decision.event["route_decision_id"]
    trace_id = execution_trace.event["trace_id"]
    result_metadata = agent_result.event.get("metadata", {})
    checks.extend(
        [
            (
                "agent_result",
                "trace_id",
                "agent_result.metadata.trace_id",
                trace_id,
                result_metadata.get("trace_id") if isinstance(result_metadata, dict) else None,
            ),
            (
                "agent_result",
                "route_decision",
                "agent_result.metadata.route_decision_id",
                route_decision_id,
                result_metadata.get("route_decision_id") if isinstance(result_metadata, dict) else None,
            ),
        ]
    )

    trace_route = execution_trace.event.get("route_decision", {})
    checks.append(
        (
            "execution_trace",
            "route_decision",
            "execution_trace.route_decision.route_decision_id",
            route_decision_id,
            trace_route.get("route_decision_id") if isinstance(trace_route, dict) else None,
        )
    )

    artifacts_written = set(execution_trace.event.get("artifacts_written", []))
    result_artifact_ids = {
        artifact.get("artifact_id")
        for artifact in agent_result.event.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    for artifact_id in sorted(result_artifact_ids):
        checks.append(
            (
                "agent_result",
                "artifact_id",
                "agent_result.artifacts.artifact_id",
                artifact_id,
                artifacts_written,
            )
        )
    for artifact_id in sorted(artifacts_written):
        checks.append(
            (
                "execution_trace",
                "artifact_written",
                "execution_trace.artifacts_written",
                artifact_id,
                result_artifact_ids,
            )
        )

    return _finalize_checks(stream_path, checks, issues)


def _finalize_checks(
    stream_path: Path,
    checks: list[tuple[str | None, str, str, Any, Any]],
    issues: list[EventStreamIssue],
) -> tuple[int, list[EventStreamIssue]]:
    for event_key, relationship, field_path, expected, actual in checks:
        if not _matches(relationship, expected, actual):
            issues.append(
                EventStreamIssue(
                    stream_path=stream_path,
                    event_key=event_key,
                    relationship=relationship,
                    field_path=field_path,
                    expected=expected,
                    actual=actual,
                )
            )
    return len(checks), issues


def _matches(relationship: str, expected: Any, actual: Any) -> bool:
    if relationship in {"artifact_id", "artifact_written"}:
        return expected in actual
    return expected == actual


def _format_issue(issue: EventStreamIssue) -> str:
    event_key = issue.event_key or "<envelope>"
    return (
        f"{issue.stream_path} {event_key} {issue.relationship} {issue.field_path} "
        f"expected={issue.expected!r} actual={issue.actual!r}"
    )


def sort_events_by_seq(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort RunEvent dicts by ``seq`` ascending for out-of-order replay.

    Events may arrive non-monotonically by ``seq`` (e.g. due to network
    reordering or multi-source fan-in). This pure function returns a new list
    sorted by ``seq`` ascending so that replay produces the correct temporal
    order. The input list is not mutated.

    Each event dict is expected to carry an integer ``seq`` field (as defined
    by the ``RunEvent`` contract). No other fields are inspected or modified.
    """
    return sorted(events, key=lambda event: event["seq"])


def resume_from_seq(events: list[dict[str, Any]], last_seen_seq: int) -> list[dict[str, Any]]:
    """Return events with ``seq`` strictly greater than ``last_seen_seq``.

    This enables seq-based resume: from any ``last_seen_seq`` breakpoint, the
    client receives exactly the events it has not yet seen — no duplicates, no
    loss. The input list order is preserved in the output.

    Semantics:
    - ``last_seen_seq = -1`` returns all events (the client has seen nothing).
    - ``last_seen_seq >= max(seq)`` returns an empty list (everything seen).
    - For any breakpoint ``b``, the result contains exactly the events with
      ``seq > b``, in their original relative order.

    The input list is not mutated.
    """
    return [event for event in events if event["seq"] > last_seen_seq]
