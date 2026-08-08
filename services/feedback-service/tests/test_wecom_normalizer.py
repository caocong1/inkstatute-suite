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

    def test_unsupported_action_returns_issue(self) -> None:
        previews = _load_jsonl(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl")
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-bad-action",
                    "feedback_target": "phase5-msg-retrieval-001",
                    "action": "invalid_action",
                    "user_id": "phase5-lawyer-001",
                    "created_at": "2026-06-28T03:24:00Z",
                    "raw_payload_ref": "fixture://raw/bad-action",
                }
            ],
            previews,
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "unsupported_action")

    def test_preview_raw_payload_returns_issue(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-preview-raw",
                    "feedback_target": "preview-with-raw",
                    "action": "up",
                    "user_id": "lawyer-1",
                    "created_at": "2026-06-28T03:24:00Z",
                    "raw_payload_ref": "fixture://raw/preview-raw",
                }
            ],
            [
                {
                    "feedback_target": "preview-with-raw",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "user_id": "lawyer-1",
                    "raw_payload": {"secret": "forbidden"},
                }
            ],
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "raw_payload_forbidden")
        self.assertTrue(batch.issues[0].path.startswith("preview."))

    def test_missing_created_at_returns_issue(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-no-time",
                    "feedback_target": "target-no-time",
                    "action": "down",
                    "user_id": "lawyer-1",
                    "raw_payload_ref": "fixture://raw/no-time",
                }
            ],
            [
                {
                    "feedback_target": "target-no-time",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "user_id": "lawyer-1",
                }
            ],
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "missing_created_at")

    def test_missing_required_reference_returns_issue(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-no-refs",
                    "preview_id": "shared-preview-id",
                    "action": "up",
                    "created_at": "2026-06-28T03:24:00Z",
                    "raw_payload_ref": "fixture://raw/no-refs",
                }
            ],
            [
                {
                    "preview_id": "shared-preview-id",
                }
            ],
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "missing_required_reference")

    def test_labels_are_included_when_present(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-labels",
                    "feedback_target": "target-labels",
                    "action": "down",
                    "user_id": "lawyer-1",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "created_at": "2026-06-28T03:24:00Z",
                    "labels": ["citation_error", "format"],
                    "raw_payload_ref": "fixture://raw/labels",
                }
            ],
            [
                {
                    "feedback_target": "target-labels",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "user_id": "lawyer-1",
                }
            ],
        )

        self.assertEqual(batch.issues, [])
        self.assertEqual(len(batch.events), 1)
        self.assertEqual(batch.events[0]["labels"], ["citation_error", "format"])

    def test_event_type_mapping(self) -> None:
        actions_types = [("up", "rating"), ("down", "correction"), ("needs_fix", "correction"), ("route_wrong", "route_mismatch")]
        previews = [
            {
                "feedback_target": "target-type",
                "turn_id": "turn-1",
                "conversation_id": "conv-1",
                "user_id": "lawyer-1",
            }
        ]

        for action, expected_type in actions_types:
            with self.subTest(action=action):
                batch = normalize_wecom_feedback_records(
                    [
                        {
                            "feedback_id": f"feedback-{action}",
                            "feedback_target": "target-type",
                            "action": action,
                            "user_id": "lawyer-1",
                            "created_at": "2026-06-28T03:24:00Z",
                            "raw_payload_ref": f"fixture://raw/{action}",
                        }
                    ],
                    previews,
                )

                self.assertEqual(batch.issues, [])
                self.assertEqual(batch.events[0]["event_type"], expected_type)

    def test_find_exact_key_in_nested_list(self) -> None:
        batch = normalize_wecom_feedback_records(
            [
                {
                    "feedback_id": "feedback-nested-list",
                    "feedback_target": "target-nested",
                    "action": "up",
                    "user_id": "lawyer-1",
                    "created_at": "2026-06-28T03:24:00Z",
                    "items": [{"raw_payload": "forbidden"}],
                    "raw_payload_ref": "fixture://raw/nested-list",
                }
            ],
            [
                {
                    "feedback_target": "target-nested",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "user_id": "lawyer-1",
                }
            ],
        )

        self.assertEqual(batch.events, [])
        self.assertEqual(batch.issues[0].code, "raw_payload_forbidden")

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
