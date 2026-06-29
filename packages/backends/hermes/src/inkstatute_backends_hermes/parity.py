"""Deterministic parity report evaluation for Hermes one-shot vs /v1/runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

JsonObject = dict[str, Any]

DIMENSION_FIELDS: dict[str, tuple[str, ...]] = {
    "route": ("route_id",),
    "skills_gates": ("skill_refs", "gate_refs"),
    "mcp_tool_trace": ("tool_trace_refs",),
    "artifacts": ("artifact_refs",),
    "visible_output": ("visible_text_hash",),
    "output_policy": ("output_policy_action",),
    "state_transitions": ("state_sequence",),
    "feedback_target": ("feedback_target_ref",),
}


@dataclass(frozen=True, slots=True)
class ParityDimensionResult:
    case_id: str
    dimension: str
    passed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ParityCase:
    case_id: str
    input_ref: str
    one_shot_observation: JsonObject
    api_runs_observation: JsonObject
    required_dimensions: list[str]
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParityReport:
    cases_total: int
    cases_passed: int
    dimension_results: list[ParityDimensionResult]
    promote_api_runs: bool
    default_lane: str = "oneshot"
    metadata: JsonObject = field(default_factory=dict)


def load_parity_cases(path: str | Path) -> list[ParityCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    return [
        ParityCase(
            case_id=str(case["case_id"]),
            input_ref=str(case["input_ref"]),
            one_shot_observation=dict(case["one_shot_observation"]),
            api_runs_observation=dict(case["api_runs_observation"]),
            required_dimensions=[str(item) for item in case["required_dimensions"]],
            metadata=dict(case.get("metadata", {})),
        )
        for case in cases
    ]


def evaluate_parity_cases(cases: list[ParityCase]) -> ParityReport:
    results: list[ParityDimensionResult] = []
    passed_cases = 0
    for case in cases:
        case_results = [_evaluate_dimension(case, dimension) for dimension in case.required_dimensions]
        results.extend(case_results)
        if case_results and all(result.passed for result in case_results):
            passed_cases += 1
    promote = bool(cases) and passed_cases == len(cases) and all(result.passed for result in results)
    return ParityReport(
        cases_total=len(cases),
        cases_passed=passed_cases,
        dimension_results=results,
        promote_api_runs=promote,
        default_lane="oneshot",
        metadata={
            "not_live_acceptance": True,
            "promotion_policy": "requires_full_parity_and_later_human_gate",
        },
    )


def _evaluate_dimension(case: ParityCase, dimension: str) -> ParityDimensionResult:
    fields = DIMENSION_FIELDS.get(dimension)
    if fields is None:
        return ParityDimensionResult(case.case_id, dimension, False, "unknown_dimension")
    for observation in (case.one_shot_observation, case.api_runs_observation):
        if any("visible_text" == key for key in observation):
            return ParityDimensionResult(case.case_id, dimension, False, "raw_visible_text_field")
        for field_name in fields:
            if field_name not in observation:
                return ParityDimensionResult(case.case_id, dimension, False, "missing_observation_field")
    passed = all(case.one_shot_observation[field] == case.api_runs_observation[field] for field in fields)
    return ParityDimensionResult(case.case_id, dimension, passed, None if passed else "dimension_mismatch")


def iter_case_observations(cases: list[ParityCase]) -> list[Mapping[str, Any]]:
    observations: list[Mapping[str, Any]] = []
    for case in cases:
        observations.append(case.one_shot_observation)
        observations.append(case.api_runs_observation)
    return observations


__all__ = [
    "DIMENSION_FIELDS",
    "ParityCase",
    "ParityDimensionResult",
    "ParityReport",
    "evaluate_parity_cases",
    "iter_case_observations",
    "load_parity_cases",
]
