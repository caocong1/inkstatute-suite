"""Coverage summaries for sanitized V2 contract streams and fixture bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .event_stream_replay import load_event_stream, replay_event_streams
from .fixture_replay import replay_fixtures
from .paths import REPO_ROOT


@dataclass(frozen=True)
class CoverageSourceReport:
    source_type: str
    evidence_kind: str
    paths: tuple[str, ...]
    record_count: int
    turn_count: int
    paired_turn_result_count: int
    paired_turn_result_coverage: float
    relationship_check_count: int
    broken_relationship_count: int
    breakage_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "evidence_kind": self.evidence_kind,
            "paths": list(self.paths),
            "record_count": self.record_count,
            "turn_count": self.turn_count,
            "paired_turn_result_count": self.paired_turn_result_count,
            "paired_turn_result_coverage": self.paired_turn_result_coverage,
            "relationship_check_count": self.relationship_check_count,
            "broken_relationship_count": self.broken_relationship_count,
            "breakage_rate": self.breakage_rate,
        }


@dataclass(frozen=True)
class CoverageReport:
    sources: tuple[CoverageSourceReport, ...]
    runtime_input_status: str
    turn_count: int
    paired_turn_result_count: int
    paired_turn_result_coverage: float
    relationship_check_count: int
    broken_relationship_count: int
    breakage_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_input_status": self.runtime_input_status,
            "turn_count": self.turn_count,
            "paired_turn_result_count": self.paired_turn_result_count,
            "paired_turn_result_coverage": self.paired_turn_result_coverage,
            "relationship_check_count": self.relationship_check_count,
            "broken_relationship_count": self.broken_relationship_count,
            "breakage_rate": self.breakage_rate,
            "sources": [source.to_dict() for source in self.sources],
        }


RUNTIME_EVIDENCE_KINDS = {"runtime", "sanitized_runtime"}


def summarize_event_stream_coverage(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    evidence_kind: str = "fixture",
    max_breakage_rate: float = 0.05,
) -> CoverageReport:
    stream_paths = tuple(Path(path) for path in paths)
    replay = replay_event_streams(stream_paths)
    turn_ids: set[str] = set()
    result_turn_ids: set[str] = set()
    record_count = 0

    for path in stream_paths:
        records = load_event_stream(path)
        record_count += len(records)
        for record in records:
            turn_id = _string(record.event.get("turn_id"))
            if record.event_key == "agent_turn" and turn_id is not None:
                turn_ids.add(turn_id)
            elif record.event_key == "agent_result" and turn_id is not None:
                result_turn_ids.add(turn_id)

    paired_count = len(turn_ids & result_turn_ids)
    source = CoverageSourceReport(
        source_type="event_stream",
        evidence_kind=evidence_kind,
        paths=tuple(str(path) for path in stream_paths),
        record_count=record_count,
        turn_count=len(turn_ids),
        paired_turn_result_count=paired_count,
        paired_turn_result_coverage=_rate(paired_count, len(turn_ids)),
        relationship_check_count=replay.relationship_check_count,
        broken_relationship_count=replay.broken_relationship_count,
        breakage_rate=replay.breakage_rate,
    )
    return _aggregate((source,), evidence_kind=evidence_kind)


def summarize_fixture_bundle_coverage(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    evidence_kind: str = "fixture",
    max_breakage_rate: float = 0.05,
) -> CoverageReport:
    fixture_paths = tuple(Path(path) for path in paths)
    replay = replay_fixtures(fixture_paths)
    turn_ids: set[str] = set()
    result_turn_ids: set[str] = set()
    record_count = 0

    for path in fixture_paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        events = fixture.get("events", {})
        if not isinstance(events, dict):
            continue
        record_count += len(events)
        agent_turn = events.get("agent_turn")
        if isinstance(agent_turn, dict):
            turn_id = _string(agent_turn.get("turn_id"))
            if turn_id is not None:
                turn_ids.add(turn_id)
        agent_result = events.get("agent_result")
        if isinstance(agent_result, dict):
            turn_id = _string(agent_result.get("turn_id"))
            if turn_id is not None:
                result_turn_ids.add(turn_id)

    paired_count = len(turn_ids & result_turn_ids)
    source = CoverageSourceReport(
        source_type="fixture_bundle",
        evidence_kind=evidence_kind,
        paths=tuple(str(path) for path in fixture_paths),
        record_count=record_count,
        turn_count=len(turn_ids),
        paired_turn_result_count=paired_count,
        paired_turn_result_coverage=_rate(paired_count, len(turn_ids)),
        relationship_check_count=replay.relationship_check_count,
        broken_relationship_count=replay.broken_relationship_count,
        breakage_rate=replay.breakage_rate,
    )
    return _aggregate((source,), evidence_kind=evidence_kind)


def assert_coverage_thresholds(
    report: CoverageReport,
    *,
    min_pair_coverage: float = 0.95,
    max_breakage_rate: float = 0.05,
    require_runtime_input: bool = False,
) -> CoverageReport:
    failures: list[str] = []
    if report.paired_turn_result_coverage < min_pair_coverage:
        failures.append(
            "paired AgentTurn/AgentResult coverage "
            f"{report.paired_turn_result_coverage:.2%} below {min_pair_coverage:.2%}"
        )
    if report.breakage_rate > max_breakage_rate:
        failures.append(
            f"relationship breakage {report.breakage_rate:.2%} exceeds {max_breakage_rate:.2%}"
        )
    if require_runtime_input and report.runtime_input_status != "provided":
        failures.append("sanitized runtime coverage input not provided")
    if failures:
        raise AssertionError("; ".join(failures) + "; " + format_coverage_summary(report))
    return report


def format_coverage_summary(report: CoverageReport, *, as_json: bool = False) -> str:
    summary = report.to_dict()
    if as_json:
        return json.dumps(summary, indent=2, sort_keys=True)
    return (
        "coverage="
        f"{report.paired_turn_result_coverage:.2%} "
        f"turns={report.turn_count} paired={report.paired_turn_result_count} "
        f"breakage={report.breakage_rate:.2%} "
        f"runtime_input={report.runtime_input_status}"
    )


def _aggregate(
    sources: tuple[CoverageSourceReport, ...],
    *,
    evidence_kind: str,
) -> CoverageReport:
    turns = sum(source.turn_count for source in sources)
    paired = sum(source.paired_turn_result_count for source in sources)
    relationship_checks = sum(source.relationship_check_count for source in sources)
    broken_relationships = sum(source.broken_relationship_count for source in sources)
    runtime_input_status = "provided" if evidence_kind in RUNTIME_EVIDENCE_KINDS else "not_provided"
    return CoverageReport(
        sources=sources,
        runtime_input_status=runtime_input_status,
        turn_count=turns,
        paired_turn_result_count=paired,
        paired_turn_result_coverage=_rate(paired, turns),
        relationship_check_count=relationship_checks,
        broken_relationship_count=broken_relationships,
        breakage_rate=_rate(broken_relationships, relationship_checks),
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


# ---------------------------------------------------------------------------
# Composability fixture coverage report (GAP-08)
# ---------------------------------------------------------------------------

#: Static registry mapping V2-PRD §10.3 synthetic task types to fixture paths.
#: Each entry is (task_type, prd_label, fixture_paths, evidence_description).
SYNTHETIC_TASK_TYPES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "simple_legal_qa",
        "简单法律问答（短任务）",
        (
            "packages/contract-test-suite/fixtures/phase4_simple_qa_event_stream.jsonl",
            "packages/contract-test-suite/fixtures/phase3_non_legal_wild_task_contract_fixture.json",
        ),
        "route_decision.mode=simple_qa; short-task event stream with AgentTurn/AgentResult pair",
    ),
    (
        "contract_review",
        "合同审查（长任务 + skill + gate + Artifact）",
        (
            "packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl",
            "packages/platform-contract/fixtures/legal_wecom_contract_review.json",
        ),
        "primary_skill=lawfirm.contract_review; artifacts_written; long-task success event stream",
    ),
    (
        "legal_retrieval",
        "法律检索（MCP tool trace）",
        (
            "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
        ),
        "primary_skill=lawfirm.legal_retrieval; tool_calls=[law-database]; MCP tool trace evidence",
    ),
    (
        "route_error",
        "路由错误模拟（route_mismatch）",
        (
            "packages/contract-test-suite/fixtures/phase3_route_error_contract_fixture.json",
            "packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl",
            "packages/contract-test-suite/fixtures/phase6_read_feedback_bundle.json",
        ),
        "route_mismatch=true; action=route_wrong; feedback event with human-review safety",
    ),
    (
        "wecom_feedback",
        "WeCom 反馈（模板卡片 → FeedbackEvent）",
        (
            "packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json",
            "packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json",
        ),
        "feedback_event with feedback_target linking; template-card → FeedbackEvent normalization",
    ),
    (
        "long_task_failure",
        "长任务失败（AsyncTask.status=failed）",
        (
            "packages/contract-test-suite/fixtures/phase3_long_task_failure_contract_fixture.json",
            "packages/contract-test-suite/fixtures/phase4_failed_long_task_event_stream.jsonl",
        ),
        "state=failed; errors=[runtime_error]; long-task failure event stream",
    ),
    (
        "non_legal_synthetic",
        "非法律合成任务（财税、工程、教育）",
        (
            "packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json",
            "packages/contract-test-suite/fixtures/non_legal_education_task.json",
            "packages/platform-contract/fixtures/non_legal_engineering_task.json",
            "packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json",
        ),
        "industry_context.domain in {finance_tax, engineering, education}; non-legal synthetic tasks",
    ),
)


@dataclass(frozen=True)
class ComposabilityCoverageEntry:
    """Coverage status for a single §10.3 synthetic task type."""

    task_type: str
    prd_label: str
    covered: bool
    fixtures: tuple[str, ...]
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "prd_label": self.prd_label,
            "covered": self.covered,
            "fixtures": list(self.fixtures),
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ComposabilityCoverageReport:
    """Aggregate composability fixture coverage across all §10.3 task types."""

    entries: tuple[ComposabilityCoverageEntry, ...]
    covered_count: int
    missing_count: int
    all_covered: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "covered_count": self.covered_count,
            "missing_count": self.missing_count,
            "all_covered": self.all_covered,
        }


def build_composability_coverage_report(
    repo_root: str | Path = REPO_ROOT,
) -> ComposabilityCoverageReport:
    """Map §10.3 synthetic task types to fixtures and report coverage.

    A task type is ``covered=True`` when at least one listed fixture file
    exists on disk and is non-empty.
    """
    root = Path(repo_root)
    entries: list[ComposabilityCoverageEntry] = []
    covered_count = 0

    for task_type, prd_label, fixture_paths, evidence in SYNTHETIC_TASK_TYPES:
        existing: list[str] = []
        for rel_path in fixture_paths:
            abs_path = root / rel_path
            if abs_path.exists() and abs_path.stat().st_size > 0:
                existing.append(rel_path)
        covered = len(existing) > 0
        if covered:
            covered_count += 1
        entries.append(
            ComposabilityCoverageEntry(
                task_type=task_type,
                prd_label=prd_label,
                covered=covered,
                fixtures=tuple(existing),
                evidence=evidence,
            )
        )

    total = len(entries)
    missing_count = total - covered_count
    return ComposabilityCoverageReport(
        entries=tuple(entries),
        covered_count=covered_count,
        missing_count=missing_count,
        all_covered=missing_count == 0,
    )


__all__ = [
    "ComposabilityCoverageEntry",
    "ComposabilityCoverageReport",
    "CoverageReport",
    "CoverageSourceReport",
    "SYNTHETIC_TASK_TYPES",
    "assert_coverage_thresholds",
    "build_composability_coverage_report",
    "format_coverage_summary",
    "summarize_event_stream_coverage",
    "summarize_fixture_bundle_coverage",
]
