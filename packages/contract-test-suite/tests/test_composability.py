from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT, PLATFORM_FIXTURE_ROOT
from contract_test_suite.schema_validation import (
    ContractValidationError,
    FORBIDDEN_TOP_LEVEL_FIELDS,
    load_schemas,
    validate_event_bundle,
)


EXPECTED_NON_LEGAL_DOMAINS = {"finance_tax", "engineering", "education"}
NON_LEGAL_FIXTURE_PATHS = (
    PLATFORM_FIXTURE_ROOT / "non_legal_engineering_task.json",
    LOCAL_FIXTURE_ROOT / "non_legal_finance_tax_task.json",
    LOCAL_FIXTURE_ROOT / "non_legal_education_task.json",
)


class ComposabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixtures = load_non_legal_composability_fixtures()

    def test_non_legal_fixtures_validate_and_preserve_relationships(self) -> None:
        for fixture_path, fixture in self.fixtures:
            with self.subTest(fixture=fixture["fixture_id"]):
                validate_event_bundle(fixture, self.schemas)
                report = assert_relationship_integrity([fixture_path], schemas=self.schemas)

                self.assertEqual(report.broken_relationship_count, 0)
                self.assertEqual(report.breakage_rate, 0.0)

    def test_non_legal_domain_set_covers_finance_tax_engineering_and_education(self) -> None:
        self.assertEqual(non_legal_domains(self.fixtures), EXPECTED_NON_LEGAL_DOMAINS)

    def test_non_legal_event_top_levels_do_not_contain_forbidden_fields(self) -> None:
        for _fixture_path, fixture in self.fixtures:
            with self.subTest(fixture=fixture["fixture_id"]):
                assert_no_forbidden_top_level_fields(fixture)

    def test_platform_required_fields_do_not_introduce_lawfirm_only_requirements(self) -> None:
        for schema_name, schema in self.schemas.items():
            with self.subTest(schema=schema_name):
                assert_schema_required_fields_are_industry_neutral(schema)

    def test_mutated_non_legal_fixture_with_legal_top_level_field_fails(self) -> None:
        _fixture_path, fixture = self.fixtures[0]
        mutated = copy.deepcopy(fixture)
        mutated["events"]["agent_turn"]["jurisdiction"] = "synthetic-lawfirm-only"

        with self.assertRaisesRegex(
            ContractValidationError,
            r"agent_turn\.jurisdiction.*forbidden top-level",
        ):
            validate_event_bundle(mutated, self.schemas)


def load_non_legal_composability_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    fixtures: list[tuple[Path, dict[str, Any]]] = []
    for path in NON_LEGAL_FIXTURE_PATHS:
        fixtures.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return fixtures


def non_legal_domains(fixtures: list[tuple[Path, dict[str, Any]]]) -> set[str]:
    domains: set[str] = set()
    for _path, fixture in fixtures:
        for event in fixture["events"].values():
            industry_context = event.get("industry_context", {})
            if isinstance(industry_context, dict) and isinstance(industry_context.get("domain"), str):
                domains.add(industry_context["domain"])
    return domains


def assert_no_forbidden_top_level_fields(fixture: Mapping[str, Any]) -> None:
    for event_key, event in fixture["events"].items():
        forbidden = sorted(set(event) & FORBIDDEN_TOP_LEVEL_FIELDS)
        if forbidden:
            raise AssertionError(
                f"{fixture['fixture_id']}.{event_key}.{forbidden[0]} is forbidden at event top level"
            )


def assert_schema_required_fields_are_industry_neutral(schema: Mapping[str, Any]) -> None:
    schema_title = schema.get("title", "<unknown-schema>")
    for path, required_fields in iter_required_fields(schema):
        forbidden = sorted(set(required_fields) & FORBIDDEN_TOP_LEVEL_FIELDS)
        if forbidden:
            raise AssertionError(
                f"{schema_title}.{'.'.join(path)} requires lawfirm-only field {forbidden[0]}"
            )

    properties = schema.get("properties", {})
    if isinstance(properties, Mapping):
        forbidden_properties = sorted(set(properties) & FORBIDDEN_TOP_LEVEL_FIELDS)
        if forbidden_properties:
            raise AssertionError(
                f"{schema_title} exposes lawfirm-only top-level property {forbidden_properties[0]}"
            )


def iter_required_fields(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], list[str]]]:
    if isinstance(value, Mapping):
        required = value.get("required")
        if isinstance(required, list):
            yield path, [field for field in required if isinstance(field, str)]
        for key, child in value.items():
            yield from iter_required_fields(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_required_fields(child, path + (str(index),))


if __name__ == "__main__":
    unittest.main()
