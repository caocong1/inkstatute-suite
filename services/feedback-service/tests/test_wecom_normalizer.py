from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import unittest

from contract_test_suite.schema_validation import validate_event
from feedback_service.wecom_normalizer import (
    FeedbackNormalizationIssue,
    NormalizedFeedbackBatch,
    normalize_wecom_feedback_records,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"


class FeedbackServiceScaffoldTests(unittest.TestCase):
    def test_normalizer_is_importable_and_returns_batch(self) -> None:
        batch = normalize_wecom_feedback_records([], [], now="2026-06-28T03:20:00Z")

        self.assertIsInstance(batch, NormalizedFeedbackBatch)
        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues, [])

    def test_issue_dataclass_is_exported(self) -> None:
        issue = FeedbackNormalizationIssue(code="sample", message="sample issue")

        self.assertEqual(issue.code, "sample")
        self.assertIsNone(issue.feedback_ref)

    def test_pyproject_declares_no_runtime_dependencies(self) -> None:
        text = (SERVICE_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("dependencies = []", text)

    def test_readme_defers_phase6_scope_and_legal_skill_modification(self) -> None:
        text = (SERVICE_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Phase 6 owns APIs", text)
        self.assertIn("does not automatically modify legal skills", text)


class WeComFeedbackNormalizerTests(unittest.TestCase):
    def test_sanitized_fixture_records_normalize_to_schema_valid_events(self) -> None:
        batch = normalize_wecom_feedback_records(
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )

        self.assertEqual(batch.issues, [])
        self.assertEqual(len(batch.events), 2)
        for event in batch.events:
            validate_event("feedback_event", event, fixture_id="phase5-wecom-feedback-normalizer")
            self.assert_no_exact_raw_payload_key(event)

    def test_repeated_callbacks_collapse_to_one_canonical_feedback_event(self) -> None:
        batch = normalize_wecom_feedback_records(
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )

        rating_event = next(event for event in batch.events if event["event_type"] == "rating")
        self.assertEqual(rating_event["feedback_target"], "phase5-msg-retrieval-001")
        self.assertEqual(rating_event["rating"], 1.0)
        self.assertEqual(rating_event["metadata"]["duplicate_count"], 2)
        self.assertEqual(
            rating_event["metadata"]["duplicate_callback_refs"],
            [
                "fixture://raw/phase5-feedback-retrieval-up-001",
                "fixture://raw/phase5-feedback-retrieval-up-002",
            ],
        )
        self.assertEqual(
            rating_event["metadata"]["idempotency_key"],
            "phase5-msg-retrieval-001:up:phase5-lawyer-001:2026-06-28T03:21Z",
        )

    def test_route_wrong_feedback_requires_human_review_and_no_auto_modify(self) -> None:
        batch = normalize_wecom_feedback_records(
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            _load_jsonl(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )

        route_event = next(event for event in batch.events if event["event_type"] == "route_mismatch")
        self.assertTrue(route_event["route_mismatch"])
        self.assertTrue(route_event["metadata"]["no_auto_modify"])
        self.assertEqual(route_event["skill_candidate"]["source"], "route_mismatch")
        self.assertTrue(route_event["skill_candidate"]["requires_human_review"])
        self.assertTrue(route_event["skill_candidate"]["metadata"]["no_auto_modify"])

    def test_missing_preview_returns_issue_without_event(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-missing-preview-001",
                    "feedback_target": "missing-target",
                    "action": "up",
                    "user_id": "phase5-lawyer-001",
                    "created_at": "2026-06-28T03:24:00Z",
                    "raw_payload_ref": "fixture://raw/missing-preview-001",
                }
            ],
            [],
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "missing_preview")

    def test_raw_payload_key_returns_privacy_issue_without_event(self) -> None:
        previews = _load_jsonl(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl")
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-raw-payload-001",
                    "feedback_target": "phase5-msg-retrieval-001",
                    "action": "up",
                    "user_id": "phase5-lawyer-001",
                    "created_at": "2026-06-28T03:24:00Z",
                    "raw_payload": {"button": "up"},
                    "raw_payload_ref": "fixture://raw/raw-payload-001",
                }
            ],
            previews,
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "raw_payload_forbidden")
        self.assertEqual(batch.issues[0].path, "raw_payload")

    def assert_no_exact_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, dict):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
