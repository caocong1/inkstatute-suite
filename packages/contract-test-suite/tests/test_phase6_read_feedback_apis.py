from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import unittest

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE6_BUNDLE = LOCAL_FIXTURE_ROOT / "phase6_read_feedback_bundle.json"


class Phase6ReadFeedbackApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def test_phase6_fixture_validates_contract_relationships(self) -> None:
        fixture = _load_json(PHASE6_BUNDLE)

        validate_event_bundle(fixture, self.schemas)
        report = assert_relationship_integrity([PHASE6_BUNDLE], max_breakage_rate=0.0, schemas=self.schemas)

        self.assertEqual(fixture["fixture_id"], "phase6-read-feedback-apis-001")
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertEqual(fixture["events"]["agent_turn"]["metadata"]["task_id"], "task-phase6-read-feedback-001")
        self.assertEqual(fixture["events"]["feedback_event"]["event_type"], "route_mismatch")
        self.assertTrue(fixture["events"]["feedback_event"]["skill_candidate"]["requires_human_review"])

    def test_phase6_fixture_is_reference_first(self) -> None:
        fixture = _load_json(PHASE6_BUNDLE)

        self.assert_no_exact_raw_payload_key(fixture)
        self.assertIn("raw_payload_ref", PHASE6_BUNDLE.read_text(encoding="utf-8"))

    def assert_no_exact_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, Mapping):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

