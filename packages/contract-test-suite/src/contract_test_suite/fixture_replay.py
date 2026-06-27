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

        total_checks += 1

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
        raise AssertionError(
            f"relationship breakage rate {report.breakage_rate:.2%} exceeds "
            f"{max_breakage_rate:.2%}"
        )
    return report


def _fixture_id(fixture: dict[str, Any]) -> str:
    value = fixture.get("fixture_id", "<unknown-fixture>")
    return value if isinstance(value, str) else "<unknown-fixture>"
