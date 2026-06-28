from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from contract_test_suite.fixture_replay import assert_platform_foundation_relationships
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import (
    ContractValidationError,
    FORBIDDEN_TOP_LEVEL_FIELDS,
    load_schemas,
    validate_event_bundle,
)


PLATFORM_FIXTURE_PATH = LOCAL_FIXTURE_ROOT / "platform_foundation_non_legal_run.json"
LEGAL_ONLY_TOP_LEVEL_FIELDS = {
    "jurisdiction",
    "statute",
    "cause_of_action",
    "liability",
}


class PlatformFoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PLATFORM_FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_platform_foundation_fixture_validates(self) -> None:
        validate_event_bundle(self.fixture, self.schemas)
        assert_platform_foundation_relationships(self.fixture, PLATFORM_FIXTURE_PATH)

        run_states = set(self.schemas["run"]["properties"]["status"]["enum"])
        async_states = set(self.schemas["common"]["$defs"]["async_task_state"]["enum"])
        self.assertEqual(run_states, async_states)
        self.assertIn(self.fixture["events"]["run"]["status"], async_states)

        invalid = copy.deepcopy(self.fixture)
        invalid["events"]["run"]["status"] = "completed"
        with self.assertRaisesRegex(ContractValidationError, r"run\.status.*enum"):
            validate_event_bundle(invalid, self.schemas)

    def test_platform_relationship_chain_detects_broken_ids(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["events"]["channel_delivery"]["result_id"] = "result-broken"

        with self.assertRaisesRegex(
            AssertionError,
            r"delivery_result_id.*channel_delivery\.result_id.*result-platform-education-001.*result-broken",
        ):
            assert_platform_foundation_relationships(mutated, PLATFORM_FIXTURE_PATH)

    def test_non_legal_fixture_has_no_legal_top_level_fields(self) -> None:
        self.assertEqual(self.fixture["events"]["agent_turn"]["industry_context"]["domain"], "education")

        for object_path, value in iter_event_objects(self.fixture):
            with self.subTest(path=object_path):
                forbidden = sorted((FORBIDDEN_TOP_LEVEL_FIELDS | LEGAL_ONLY_TOP_LEVEL_FIELDS) & set(value))
                self.assertEqual(forbidden, [], f"{object_path} has forbidden top-level fields")
                self.assertNotIn("raw_payload", value)

    def test_artifact_record_and_nested_agent_result_artifacts_are_both_present(self) -> None:
        events = self.fixture["events"]
        artifact_records = events["artifact_records"]
        nested_artifacts = events["agent_result"]["artifacts"]

        self.assertGreaterEqual(len(artifact_records), 1)
        self.assertGreaterEqual(len(nested_artifacts), 1)
        self.assertEqual(
            {artifact["artifact_id"] for artifact in artifact_records},
            {artifact["artifact_id"] for artifact in nested_artifacts},
        )


def iter_event_objects(fixture: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for event_key, value in fixture["events"].items():
        if isinstance(value, Mapping):
            yield event_key, value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    yield f"{event_key}[{index}]", item


if __name__ == "__main__":
    unittest.main()
