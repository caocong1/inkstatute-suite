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
        self.assertEqual(
            set(self.schemas),
            {
                "agent_result",
                "agent_turn",
                "common",
                "execution_trace",
                "feedback_event",
                "route_decision",
            },
        )
        self.assertEqual(
            {fixture["fixture_id"] for fixture in self.fixtures},
            {
                "legal-wecom-contract-review-001",
                "non-legal-engineering-task-001",
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

    def test_fixture_relationships(self):
        self_check.assert_fixture_relationships(self.fixtures)

    def test_python_binding_schema_parity(self):
        self_check.assert_python_binding_schema_parity(self.schemas)

    def test_main_returns_zero(self):
        self.assertEqual(self_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
