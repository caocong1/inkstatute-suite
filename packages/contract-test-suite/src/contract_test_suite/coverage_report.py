"""Coverage summaries for sanitized V2 contract streams and fixture bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .event_stream_replay import load_event_stream, replay_event_streams
from .fixture_replay import replay_fixtures


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


__all__ = [
    "CoverageReport",
    "CoverageSourceReport",
    "assert_coverage_thresholds",
    "format_coverage_summary",
    "summarize_event_stream_coverage",
    "summarize_fixture_bundle_coverage",
]
