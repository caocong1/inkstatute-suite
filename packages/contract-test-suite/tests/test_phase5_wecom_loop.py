from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
import re
import sys
from typing import Any
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
for source_path in (
    REPO_ROOT / "services" / "feedback-service" / "src",
):
    sys.path.insert(0, str(source_path))

from contract_test_suite.event_stream_replay import assert_event_stream_integrity, load_event_stream
from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle
from contract_test_suite.wecom_validation import validate_wecom_shadow_evidence
from feedback_service.wecom_normalizer import normalize_wecom_feedback_records


PHASE5_STREAM = LOCAL_FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"
PHASE5_BUNDLE = LOCAL_FIXTURE_ROOT / "phase5_wecom_feedback_loop_fixture.json"
PHASE5_FEEDBACK = LOCAL_FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"
PHASE5_PREVIEWS = LOCAL_FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"
SECRET_LIKE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


class Phase5WeComLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def test_phase5_contract_stream_replays_and_passes_wecom_evidence_validation(self) -> None:
        replay_report = assert_event_stream_integrity([PHASE5_STREAM], max_breakage_rate=0.0, schemas=self.schemas)
        validation_report = validate_wecom_shadow_evidence(
            PHASE5_STREAM,
            ack_started_at="2026-06-28T03:20:00Z",
            ack_completed_at="2026-06-28T03:20:04Z",
        )

        self.assertEqual(replay_report.broken_relationship_count, 0)
        self.assertEqual(replay_report.breakage_rate, 0.0)
        self.assertTrue(validation_report.passed)
        self.assertEqual(validation_report.feedback_target, "phase5-msg-retrieval-001")

    def test_phase5_full_fixture_validates_result_to_feedback_relationships(self) -> None:
        fixture = _load_json(PHASE5_BUNDLE)

        validate_event_bundle(fixture, self.schemas)
        report = assert_relationship_integrity([PHASE5_BUNDLE], max_breakage_rate=0.0, schemas=self.schemas)

        events = fixture["events"]
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertEqual(events["agent_result"]["feedback_target"], events["feedback_event"]["feedback_target"])
        self.assertEqual(events["agent_result"]["result_id"], events["feedback_event"]["result_id"])

    def test_normalizer_output_matches_fixture_feedback_event_shape(self) -> None:
        fixture_feedback = _load_json(PHASE5_BUNDLE)["events"]["feedback_event"]
        batch = normalize_wecom_feedback_records(_load_jsonl(PHASE5_FEEDBACK), _load_jsonl(PHASE5_PREVIEWS))
        normalized_feedback = next(event for event in batch.events if event["event_type"] == "rating")

        self.assertEqual(batch.issues, [])
        self.assertEqual(normalized_feedback, fixture_feedback)

    def test_route_mismatch_normalizer_output_remains_human_review_only(self) -> None:
        batch = normalize_wecom_feedback_records(_load_jsonl(PHASE5_FEEDBACK), _load_jsonl(PHASE5_PREVIEWS))
        route_event = next(event for event in batch.events if event["event_type"] == "route_mismatch")

        self.assertTrue(route_event["route_mismatch"])
        self.assertTrue(route_event["skill_candidate"]["requires_human_review"])
        self.assertTrue(route_event["skill_candidate"]["metadata"]["no_auto_modify"])
        self.assertTrue(route_event["metadata"]["no_auto_modify"])

    def test_phase5_fixtures_are_reference_first_and_secret_free(self) -> None:
        for path in (PHASE5_STREAM, PHASE5_BUNDLE, PHASE5_FEEDBACK, PHASE5_PREVIEWS):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(SECRET_LIKE.search(text))
                for record in _load_any_records(path):
                    self.assert_no_exact_raw_payload_key(record)

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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_any_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        if path == PHASE5_STREAM:
            return [record.event for record in load_event_stream(path)]
        return _load_jsonl(path)
    return [_load_json(path)]


if __name__ == "__main__":
    unittest.main()
