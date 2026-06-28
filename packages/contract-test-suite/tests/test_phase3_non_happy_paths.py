from __future__ import annotations

import json
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import (
    FORBIDDEN_TOP_LEVEL_FIELDS,
    load_schemas,
    validate_event_bundle,
)


PHASE3_FIXTURE_PATHS = (
    LOCAL_FIXTURE_ROOT / "phase3_route_error_contract_fixture.json",
    LOCAL_FIXTURE_ROOT / "phase3_long_task_failure_contract_fixture.json",
    LOCAL_FIXTURE_ROOT / "phase3_repeated_feedback_clicks_contract_fixture.json",
    LOCAL_FIXTURE_ROOT / "phase3_non_legal_wild_task_contract_fixture.json",
)

EXPECTED_PHASE3_FIXTURE_IDS = {
    "phase3-route-error-contract-001",
    "phase3-long-task-failure-contract-001",
    "phase3-repeated-feedback-clicks-contract-001",
    "phase3-non-legal-wild-task-contract-001",
}


def load_phase3_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in PHASE3_FIXTURE_PATHS
    ]


class Phase3NonHappyPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixtures = load_phase3_fixtures()
        cls.fixture_by_id = {
            fixture["fixture_id"]: fixture for _path, fixture in cls.fixtures
        }

    def test_phase3_fixtures_validate_and_preserve_relationships(self) -> None:
        for fixture_path, fixture in self.fixtures:
            with self.subTest(fixture=fixture["fixture_id"]):
                validate_event_bundle(fixture, self.schemas)
                report = assert_relationship_integrity([fixture_path], schemas=self.schemas)

                self.assertEqual(report.broken_relationship_count, 0)
                self.assertEqual(report.breakage_rate, 0.0)

    def test_all_required_phase3_fixture_ids_are_present(self) -> None:
        self.assertEqual(set(self.fixture_by_id), EXPECTED_PHASE3_FIXTURE_IDS)

    def test_route_error_records_human_review_only_skill_candidate(self) -> None:
        fixture = self.fixture_by_id["phase3-route-error-contract-001"]
        events = fixture["events"]
        agent_result = events["agent_result"]
        feedback_event = events["feedback_event"]

        self.assertTrue(events["route_decision"]["route_mismatch"])
        self.assertEqual(events["route_decision"]["mode"], "zero_match")
        self.assertTrue(agent_result["route_mismatch"])
        self.assertTrue(feedback_event["route_mismatch"])

        for candidate in (agent_result["skill_candidate"], feedback_event["skill_candidate"]):
            with self.subTest(candidate=candidate["source"]):
                self.assertTrue(candidate["detected"])
                self.assertEqual(candidate["source"], "route_mismatch")
                self.assertTrue(candidate["requires_human_review"])
                self.assertFalse(candidate["metadata"]["auto_modify_skill"])

    def test_long_task_failure_uses_exact_async_states_and_error_category(self) -> None:
        fixture = self.fixture_by_id["phase3-long-task-failure-contract-001"]
        events = fixture["events"]
        states = {step["state"] for step in events["execution_trace"]["steps"]}

        self.assertGreaterEqual(states, {"queued", "running", "failed"})
        self.assertEqual(events["agent_result"]["status"], "failed")
        self.assertEqual(events["agent_result"]["reply_type"], "status_update")
        self.assertEqual(events["agent_result"]["error"]["category"], "runtime_error")
        self.assertEqual(events["execution_trace"]["errors"][0]["category"], "runtime_error")

    def test_repeated_feedback_clicks_have_one_canonical_event_and_idempotency_metadata(self) -> None:
        fixture = self.fixture_by_id["phase3-repeated-feedback-clicks-contract-001"]
        events = fixture["events"]
        feedback_event = events["feedback_event"]
        metadata = feedback_event["metadata"]

        self.assertEqual(
            events["agent_result"]["feedback_target"],
            feedback_event["feedback_target"],
        )
        self.assertTrue(metadata["canonical_event"])
        self.assertIn("idempotency_key", metadata)
        self.assertEqual(
            metadata["dedupe_strategy"],
            "feedback_target + action + user_id + created_at_bucket",
        )
        self.assertEqual(metadata["duplicate_count"], len(metadata["duplicate_callback_refs"]))
        self.assertGreater(metadata["duplicate_count"], 1)
        self.assertTrue(all(ref.startswith("fixture://raw/") for ref in metadata["duplicate_callback_refs"]))

    def test_non_legal_wild_task_has_non_lawfirm_domain_and_no_forbidden_top_level_fields(self) -> None:
        fixture = self.fixture_by_id["phase3-non-legal-wild-task-contract-001"]
        events = fixture["events"]

        self.assertEqual(events["agent_turn"]["industry_context"]["domain"], "product_ops")
        self.assertNotEqual(events["agent_turn"]["industry_context"]["domain"], "lawfirm")
        self.assertEqual(events["route_decision"]["mode"], "simple_qa")
        self.assertFalse(events["execution_trace"]["matched_registered_skill"])
        assert_no_forbidden_top_level_fields(fixture)

    def test_raw_payloads_are_references_not_inline_payload_fields(self) -> None:
        for _fixture_path, fixture in self.fixtures:
            with self.subTest(fixture=fixture["fixture_id"]):
                assert_no_forbidden_top_level_fields(fixture)
                self.assertEqual(collect_values_by_key(fixture, "raw_payload"), [])
                raw_refs = collect_values_by_key(fixture, "raw_payload_ref")
                self.assertTrue(raw_refs)
                self.assertTrue(all(isinstance(ref, str) for ref in raw_refs))
                self.assertTrue(all(ref.startswith("fixture://raw/") for ref in raw_refs))


def assert_no_forbidden_top_level_fields(fixture: Mapping[str, Any]) -> None:
    for event_key, event in fixture["events"].items():
        forbidden = sorted(set(event) & FORBIDDEN_TOP_LEVEL_FIELDS)
        if forbidden:
            raise AssertionError(
                f"{fixture['fixture_id']}.{event_key}.{forbidden[0]} is forbidden at event top level"
            )


def collect_values_by_key(value: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if child_key == key:
                found.append(child_value)
            found.extend(collect_values_by_key(child_value, key))
    elif isinstance(value, list):
        for item in value:
            found.extend(collect_values_by_key(item, key))
    return found


if __name__ == "__main__":
    unittest.main()
