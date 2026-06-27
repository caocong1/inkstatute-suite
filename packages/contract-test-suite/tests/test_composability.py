from __future__ import annotations

import copy
import unittest

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.schema_validation import (
    ContractValidationError,
    FORBIDDEN_TOP_LEVEL_FIELDS,
    load_schemas,
    validate_event_bundle,
)


EXPECTED_NON_LEGAL_DOMAINS = {"finance_tax", "engineering", "education"}


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


if __name__ == "__main__":
    unittest.main()
