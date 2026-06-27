"""Fixture replay helpers for Phase 1 platform contract examples."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import PLATFORM_FIXTURE_ROOT
from .schema_validation import ContractValidationError, load_schemas, validate_event_bundle


class FixtureReplayError(AssertionError):
    """Raised when a fixture cannot be loaded or schema-validated for replay."""


@dataclass(frozen=True)
class LoadedFixture:
    path: Path
    fixture: dict[str, Any]


@dataclass(frozen=True)
class RelationshipIssue:
    fixture_id: str
    fixture_path: Path | None
    relationship: str
    field_path: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ReplayReport:
    fixture_count: int
    relationship_check_count: int
    broken_relationship_count: int
    breakage_rate: float
    issues: list[RelationshipIssue]


def load_fixture_paths(fixture_root: Path = PLATFORM_FIXTURE_ROOT) -> list[Path]:
    return sorted(fixture_root.glob("*.json"))


def load_fixtures_from_paths(paths: list[Path] | tuple[Path, ...]) -> list[LoadedFixture]:
    loaded: list[LoadedFixture] = []
    for path in paths:
        loaded.append(LoadedFixture(path=path, fixture=json.loads(path.read_text(encoding="utf-8"))))
    return loaded


def replay_fixtures(
    fixture_paths: list[Path] | tuple[Path, ...] | None = None,
    *,
    schemas: dict[str, dict[str, Any]] | None = None,
) -> ReplayReport:
    paths = load_fixture_paths() if fixture_paths is None else list(fixture_paths)
    loaded_schemas = schemas if schemas is not None else load_schemas()
    loaded_fixtures = load_fixtures_from_paths(paths)

    total_checks = 0
    issues: list[RelationshipIssue] = []
    for item in loaded_fixtures:
        fixture_id = _fixture_id(item.fixture)
        try:
            validate_event_bundle(item.fixture, loaded_schemas)
        except ContractValidationError as exc:
            raise FixtureReplayError(f"{item.path}: {fixture_id}: {exc}") from exc

        check_count, fixture_issues = _check_fixture_relationships(item.fixture, item.path)
        total_checks += check_count
        issues.extend(fixture_issues)

    broken_checks = len(issues)
    breakage_rate = broken_checks / total_checks if total_checks else 0.0
    return ReplayReport(
        fixture_count=len(loaded_fixtures),
        relationship_check_count=total_checks,
        broken_relationship_count=broken_checks,
        breakage_rate=breakage_rate,
        issues=issues,
    )


def assert_relationship_integrity(
    fixture_paths: list[Path] | tuple[Path, ...] | None = None,
    *,
    max_breakage_rate: float = 0.05,
    schemas: dict[str, dict[str, Any]] | None = None,
) -> ReplayReport:
    report = replay_fixtures(fixture_paths, schemas=schemas)
    if report.breakage_rate > max_breakage_rate:
        details = "; ".join(_format_issue(issue) for issue in report.issues)
        raise AssertionError(
            f"relationship breakage rate {report.breakage_rate:.2%} exceeds "
            f"{max_breakage_rate:.2%}: {details}"
        )
    return report


def _check_fixture_relationships(
    fixture: dict[str, Any],
    fixture_path: Path | None,
) -> tuple[int, list[RelationshipIssue]]:
    fixture_id = _fixture_id(fixture)
    events = fixture["events"]
    agent_turn = events["agent_turn"]
    route_decision = events["route_decision"]
    execution_trace = events["execution_trace"]
    agent_result = events["agent_result"]
    feedback_event = events["feedback_event"]

    checks: list[tuple[str, str, Any, Any]] = []
    turn_id = agent_turn["turn_id"]
    for event_key in ("route_decision", "execution_trace", "agent_result", "feedback_event"):
        checks.append(("turn_id", f"{event_key}.turn_id", turn_id, events[event_key]["turn_id"]))

    checks.extend(
        [
            (
                "feedback_conversation_id",
                "feedback_event.conversation_id",
                agent_turn["conversation_id"],
                feedback_event["conversation_id"],
            ),
            (
                "feedback_user_id",
                "feedback_event.user_id",
                agent_turn["user_id"],
                feedback_event["user_id"],
            ),
            (
                "feedback_result_id",
                "feedback_event.result_id",
                agent_result["result_id"],
                feedback_event["result_id"],
            ),
            (
                "feedback_target",
                "feedback_event.feedback_target",
                agent_result["feedback_target"],
                feedback_event["feedback_target"],
            ),
        ]
    )

    route_decision_id = route_decision["route_decision_id"]
    if "related_route_decision" in feedback_event:
        checks.append(
            (
                "route_decision",
                "feedback_event.related_route_decision",
                route_decision_id,
                feedback_event["related_route_decision"],
            )
        )
    result_metadata = agent_result.get("metadata", {})
    if isinstance(result_metadata, dict) and "route_decision_id" in result_metadata:
        checks.append(
            (
                "route_decision",
                "agent_result.metadata.route_decision_id",
                route_decision_id,
                result_metadata["route_decision_id"],
            )
        )
    trace_route_decision = execution_trace.get("route_decision", {})
    if isinstance(trace_route_decision, dict) and "route_decision_id" in trace_route_decision:
        checks.append(
            (
                "route_decision",
                "execution_trace.route_decision.route_decision_id",
                route_decision_id,
                trace_route_decision["route_decision_id"],
            )
        )

    if isinstance(result_metadata, dict) and "trace_id" in result_metadata:
        checks.append(
            (
                "trace_id",
                "agent_result.metadata.trace_id",
                execution_trace["trace_id"],
                result_metadata["trace_id"],
            )
        )

    artifacts_written = set(execution_trace.get("artifacts_written", []))
    result_artifact_ids: set[Any] = set()
    for index, artifact in enumerate(agent_result.get("artifacts", [])):
        artifact_id = artifact.get("artifact_id")
        result_artifact_ids.add(artifact_id)
        checks.append(
            (
                "artifact_id",
                f"agent_result.artifacts[{index}].artifact_id",
                artifact_id,
                artifacts_written,
            )
        )
    for artifact_id in artifacts_written:
        checks.append(
            (
                "artifact_written",
                "execution_trace.artifacts_written",
                artifact_id,
                result_artifact_ids,
            )
        )

    issues: list[RelationshipIssue] = []
    for relationship, field_path, expected, actual in checks:
        matches = expected in actual if relationship in {"artifact_id", "artifact_written"} else expected == actual
        if not matches:
            issues.append(
                RelationshipIssue(
                    fixture_id=fixture_id,
                    fixture_path=fixture_path,
                    relationship=relationship,
                    field_path=field_path,
                    expected=expected,
                    actual=actual,
                )
            )

    return len(checks), issues


def _format_issue(issue: RelationshipIssue) -> str:
    return (
        f"{issue.fixture_id} {issue.relationship} {issue.field_path} "
        f"expected={issue.expected!r} actual={issue.actual!r}"
    )


def _fixture_id(fixture: dict[str, Any]) -> str:
    value = fixture.get("fixture_id", "<unknown-fixture>")
    return value if isinstance(value, str) else "<unknown-fixture>"
