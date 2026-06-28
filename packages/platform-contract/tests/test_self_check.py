import sys
import unittest
from copy import deepcopy
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PACKAGE_ROOT / "scripts"

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import self_check


class SelfCheckTests(unittest.TestCase):
    def setUp(self):
        self.schemas = self_check.load_schemas()
        self.fixtures = self_check.load_fixtures()

    def test_loads_all_schemas_and_fixtures(self):
        self.assertTrue(
            {
                "agent_result",
                "agent_turn",
                "artifact_record",
                "channel_delivery",
                "channel_message",
                "common",
                "execution_trace",
                "feedback_event",
                "route_decision",
                "run",
                "solution_package_manifest",
            }
            <= set(self.schemas)
        )
        self.assertIn("agent_adapter_manifest", self.schemas)
        self.assertEqual(
            {fixture["fixture_id"] for fixture in self.fixtures},
            {
                "legal-wecom-contract-review-001",
                "non-legal-engineering-task-001",
                "platform-foundation-non-legal-run-001",
            },
        )

    def test_schema_shape_and_privacy_boundary(self):
        self_check.assert_schema_shape(self.schemas)
        self_check.assert_no_legal_top_level_required(self.schemas)

    def test_fixture_required_fields_and_enums(self):
        self_check.assert_fixture_required_fields(self.schemas, self.fixtures)

    def test_fixture_rejects_unknown_top_level_fields(self):
        fixtures = deepcopy(self.fixtures)
        fixtures[0]["events"]["feedback_event"]["unsupported_field"] = "not allowed"

        with self.assertRaisesRegex(AssertionError, "unsupported fields"):
            self_check.assert_fixture_required_fields(self.schemas, fixtures)

    def test_fixture_rejects_sensitive_top_level_fields(self):
        fixtures = deepcopy(self.fixtures)
        fixtures[0]["events"]["agent_turn"]["raw_payload"] = "sensitive content"

        with self.assertRaisesRegex(AssertionError, "forbidden top-level fields"):
            self_check.assert_fixture_required_fields(self.schemas, fixtures)

    def test_fixture_allows_legal_fields_inside_industry_context(self):
        fixtures = deepcopy(self.fixtures)
        fixtures[0]["events"]["agent_turn"].setdefault("industry_context", {})["jurisdiction"] = "CN"

        self_check.assert_fixture_required_fields(self.schemas, fixtures)

    def test_fixture_relationships(self):
        self_check.assert_fixture_relationships(self.fixtures)

    def test_python_binding_schema_parity(self):
        self_check.assert_python_binding_schema_parity(self.schemas)

    def test_new_schema_binding_parity_rejects_field_drift(self):
        schemas = deepcopy(self.schemas)
        del schemas["run"]["properties"]["metadata"]

        with self.assertRaisesRegex(AssertionError, "run schema/binding mismatch"):
            self_check.assert_python_binding_schema_parity(schemas)

    def test_new_schema_rejects_forbidden_required_fields(self):
        schemas = deepcopy(self.schemas)
        schemas["run"]["required"].append("case_type")

        with self.assertRaisesRegex(AssertionError, "forbidden top-level required fields"):
            self_check.assert_no_legal_top_level_required(schemas)

    def test_five_event_fixtures_do_not_need_new_resource_objects(self):
        legacy_fixture_ids = {
            "legal-wecom-contract-review-001",
            "non-legal-engineering-task-001",
        }
        for fixture in self.fixtures:
            if fixture["fixture_id"] not in legacy_fixture_ids:
                continue
            self.assertEqual(
                set(fixture["events"]),
                {
                    "agent_turn",
                    "route_decision",
                    "execution_trace",
                    "agent_result",
                    "feedback_event",
                },
            )

        self_check.assert_fixture_required_fields(self.schemas, self.fixtures)

    def test_main_returns_zero(self):
        self.assertEqual(self_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
