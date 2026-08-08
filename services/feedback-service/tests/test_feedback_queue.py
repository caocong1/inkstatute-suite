from __future__ import annotations

import copy
from pathlib import Path
import unittest

from contract_test_suite.schema_validation import validate_event
from feedback_service.classification import FEEDBACK_CATEGORIES, classify_feedback_event
from feedback_service.queue import (
    build_pending_feedback_queue,
    dedupe_feedback_events,
    load_jsonl_records,
    normalize_feedback_inputs,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"


class FeedbackClassificationTests(unittest.TestCase):
    def test_classification_covers_all_prd_categories(self) -> None:
        cases = {
            "rating": {"event_type": "rating", "action": "up"},
            "correction": {"event_type": "correction", "action": "down"},
            "fact_missing": {"event_type": "correction", "labels": ["fact_missing"]},
            "citation_error": {"event_type": "correction", "message": "Citation is wrong."},
            "route_mismatch": {"event_type": "route_mismatch", "route_mismatch": True},
            "format_issue": {"event_type": "correction", "labels": ["format_issue"]},
            "compliance_issue": {"event_type": "correction", "message": "Compliance issue."},
            "skill_candidate": {
                "event_type": "skill_candidate",
                "skill_candidate": {"detected": True, "requires_human_review": True},
            },
        }

        self.assertEqual(set(cases), FEEDBACK_CATEGORIES)
        for expected, event in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify_feedback_event(event).category, expected)

    def test_route_mismatch_requires_human_review_and_no_auto_modify(self) -> None:
        classification = classify_feedback_event({"event_type": "correction", "route_mismatch": True})

        self.assertEqual(classification.category, "route_mismatch")
        self.assertTrue(classification.requires_human_review)
        self.assertTrue(classification.no_auto_modify)

    def test_event_type_fallback_to_known_category(self) -> None:
        classification = classify_feedback_event({"event_type": "format_issue"})

        self.assertEqual(classification.category, "format_issue")
        self.assertEqual(classification.reason, "event_type")

    def test_default_fallback_when_no_signals_match(self) -> None:
        classification = classify_feedback_event({"event_type": "unknown_type"})

        self.assertEqual(classification.category, "correction")
        self.assertEqual(classification.reason, "default fallback")

    def test_label_aliases_for_fact_missing(self) -> None:
        for label in ("missing_fact", "missing_facts", "fact_gap"):
            with self.subTest(label=label):
                classification = classify_feedback_event({"labels": [label]})
                self.assertEqual(classification.category, "fact_missing")

    def test_label_aliases_for_citation_error(self) -> None:
        for label in ("bad_citation", "citation_missing", "wrong_citation"):
            with self.subTest(label=label):
                classification = classify_feedback_event({"labels": [label]})
                self.assertEqual(classification.category, "citation_error")

    def test_label_aliases_for_format_issue(self) -> None:
        for label in ("format", "formatting"):
            with self.subTest(label=label):
                classification = classify_feedback_event({"labels": [label]})
                self.assertEqual(classification.category, "format_issue")

    def test_label_aliases_for_compliance_issue(self) -> None:
        for label in ("compliance", "policy"):
            with self.subTest(label=label):
                classification = classify_feedback_event({"labels": [label]})
                self.assertEqual(classification.category, "compliance_issue")

    def test_message_hint_fact_missing(self) -> None:
        classification = classify_feedback_event({"message": "Missing a key fact"})

        self.assertEqual(classification.category, "fact_missing")
        self.assertEqual(classification.reason, "message hint")

    def test_message_hint_format_issue(self) -> None:
        classification = classify_feedback_event({"message": "Bad format"})

        self.assertEqual(classification.category, "format_issue")

    def test_message_hint_compliance_issue(self) -> None:
        classification = classify_feedback_event({"message": "Compliance problem"})

        self.assertEqual(classification.category, "compliance_issue")

    def test_message_hint_returns_none_for_unmatched_text(self) -> None:
        classification = classify_feedback_event({"message": "general feedback"})

        self.assertEqual(classification.category, "correction")
        self.assertEqual(classification.reason, "default fallback")

    def test_to_dict_serializes_classification(self) -> None:
        classification = classify_feedback_event({"event_type": "rating", "action": "up"})
        d = classification.to_dict()

        self.assertEqual(d["category"], "rating")
        self.assertIsInstance(d["labels"], list)
        self.assertIn("requires_human_review", d)
        self.assertIn("no_auto_modify", d)


class FeedbackNormalizationQueueTests(unittest.TestCase):
    def test_duplicate_wecom_callback_events_collapse_to_one_canonical_event(self) -> None:
        event = _normalized_wecom_feedback_event("callback-queue-1")

        events = normalize_feedback_inputs(wecom_callback_events=[event, copy.deepcopy(event)])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metadata"]["duplicate_count"], 2)
        self.assertIn("idempotency_key", events[0]["metadata"])

    def test_phase5_compatibility_inputs_normalize_to_schema_valid_events(self) -> None:
        events = normalize_feedback_inputs(
            compatibility_feedback_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            compatibility_preview_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )

        self.assertEqual(len(events), 2)
        for event in events:
            validate_event("feedback_event", event, fixture_id="phase6-feedback-queue")

    def test_contract_feedback_events_are_deduped_without_shape_changes(self) -> None:
        event = normalize_feedback_inputs(
            compatibility_feedback_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            compatibility_preview_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )[0]

        events = normalize_feedback_inputs(contract_feedback_events=[event, copy.deepcopy(event)])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["feedback_id"], event["feedback_id"])
        validate_event("feedback_event", events[0], fixture_id="phase6-contract-feedback")

    def test_normalization_does_not_mutate_input_events(self) -> None:
        event = _normalized_wecom_feedback_event("callback-queue-immutability", action="up")
        original = copy.deepcopy(event)

        dedupe_feedback_events([event, copy.deepcopy(event)])

        self.assertEqual(event, original)

    def test_pending_queue_excludes_non_pending_feedback(self) -> None:
        pending = _normalized_wecom_feedback_event("callback-pending")
        resolved = _normalized_wecom_feedback_event("callback-resolved")
        resolved["status"] = "resolved"

        queue = build_pending_feedback_queue([resolved, pending], status="pending")

        self.assertEqual([item["feedback_id"] for item in queue], [pending["feedback_id"]])

    def test_route_mismatch_queue_item_is_human_review_only(self) -> None:
        event = _normalized_wecom_feedback_event("callback-route", action="route_wrong")
        event.update(
            {
                "event_type": "route_mismatch",
                "route_mismatch": True,
                "skill_candidate": {
                    "detected": True,
                    "source": "route_mismatch",
                    "requires_human_review": True,
                    "evidence": ["feedback-callback-route"],
                    "metadata": {"no_auto_modify": True},
                },
            }
        )
        event["metadata"]["no_auto_modify"] = True

        item = build_pending_feedback_queue([event])[0]

        self.assertEqual(item["classification"]["category"], "route_mismatch")
        self.assertTrue(item["requires_human_review"])
        self.assertTrue(item["no_auto_modify"])
        self.assertIsNotNone(item["skill_candidate"])

    def test_queue_output_is_reference_first(self) -> None:
        item = build_pending_feedback_queue([_normalized_wecom_feedback_event("callback-privacy")])[0]

        self.assertEqual(item["raw_payload_ref"], "fixture://wecom/callback/callback-privacy")
        self.assert_no_exact_raw_payload_key(item)

    def test_pending_queue_sorts_by_created_at_then_input_order(self) -> None:
        first = _normalized_wecom_feedback_event("callback-sort-first")
        second = _normalized_wecom_feedback_event("callback-sort-second")
        first["created_at"] = "2026-06-28T05:02:00Z"
        second["created_at"] = "2026-06-28T05:02:00Z"

        queue = build_pending_feedback_queue([first, second])

        self.assertEqual(
            [item["feedback_id"] for item in queue],
            [first["feedback_id"], second["feedback_id"]],
        )

    def assert_no_exact_raw_payload_key(self, value: object) -> None:
        if isinstance(value, dict):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


class FeedbackQueueEdgeCaseTests(unittest.TestCase):
    def test_idempotency_key_from_target_action_user_created_at(self) -> None:
        event = {
            "feedback_target": "target-1",
            "action": "down",
            "user_id": "user-1",
            "created_at": "2026-06-28T05:00:00Z",
            "status": "pending",
        }

        events = dedupe_feedback_events([event])

        key = events[0]["metadata"]["idempotency_key"]
        self.assertIn("target-1", key)
        self.assertIn("down", key)
        self.assertIn("user-1", key)

    def test_idempotency_key_fallback_to_feedback_id(self) -> None:
        event = {
            "feedback_id": "fb-unique-123",
            "status": "pending",
        }

        events = dedupe_feedback_events([event])

        self.assertEqual(events[0]["metadata"]["idempotency_key"], "fb-unique-123")

    def test_idempotency_key_fallback_to_hash(self) -> None:
        event = {"status": "pending", "some_field": "value"}

        events = dedupe_feedback_events([event])

        key = events[0]["metadata"]["idempotency_key"]
        self.assertTrue(key.startswith("feedback-event:"))

    def test_timestamp_bucket_invalid_date_returns_prefix(self) -> None:
        event = {
            "feedback_target": "target-1",
            "action": "up",
            "user_id": "user-1",
            "created_at": "not-a-date-at-all",
            "status": "pending",
        }

        events = dedupe_feedback_events([event])

        self.assertEqual(len(events), 1)

    def test_privacy_checked_clone_rejects_raw_payload_key(self) -> None:
        event = {
            "feedback_id": "fb-1",
            "raw_payload": {"secret": "data"},
            "status": "pending",
        }

        with self.assertRaises(ValueError) as ctx:
            dedupe_feedback_events([event])

        self.assertIn("raw_payload_ref", str(ctx.exception))

    def test_privacy_checked_clone_rejects_nested_raw_payload(self) -> None:
        event = {
            "feedback_id": "fb-2",
            "metadata": {"raw_payload": {"data": "secret"}},
            "status": "pending",
        }

        with self.assertRaises(ValueError):
            dedupe_feedback_events([event])

    def test_privacy_checked_clone_rejects_raw_payload_in_list(self) -> None:
        event = {
            "feedback_id": "fb-3",
            "items": [{"raw_payload": "forbidden"}],
            "status": "pending",
        }

        with self.assertRaises(ValueError):
            dedupe_feedback_events([event])

    def test_normalize_inputs_raises_on_compatibility_issues(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_feedback_inputs(
                compatibility_feedback_records=[
                    {
                        "feedback_id": "fb-bad",
                        "action": "invalid_action",
                        "feedback_target": "target",
                        "user_id": "u1",
                        "created_at": "2026-06-28T05:00:00Z",
                    }
                ],
                compatibility_preview_records=[],
            )

        self.assertIn("could not normalize", str(ctx.exception))

    def test_duplicate_count_from_metadata(self) -> None:
        event1 = _normalized_wecom_feedback_event("dc-1")
        event1["metadata"]["duplicate_count"] = 3
        event2 = _normalized_wecom_feedback_event("dc-1")
        event2["metadata"]["duplicate_count"] = 2

        events = dedupe_feedback_events([event1, event2])

        self.assertEqual(events[0]["metadata"]["duplicate_count"], 5)

    def test_string_helper_returns_none_for_empty_string(self) -> None:
        event = {
            "feedback_id": "",
            "feedback_target": "t",
            "action": "up",
            "user_id": "u",
            "created_at": "2026-06-28T05:00:00Z",
            "status": "pending",
        }

        events = dedupe_feedback_events([event])
        self.assertEqual(len(events), 1)


def _normalized_wecom_feedback_event(callback_id: str, *, action: str = "down") -> dict[str, object]:
    return {
        "feedback_id": f"feedback-{callback_id}",
        "turn_id": f"turn-{callback_id}",
        "conversation_id": f"conv-{callback_id}",
        "user_id": f"lawyer-{callback_id}",
        "source": "card_button",
        "event_type": "rating" if action == "up" else "correction",
        "status": "pending",
        "created_at": "2026-06-28T05:00:00Z",
        "feedback_target": f"target-{callback_id}",
        "action": action,
        "raw_payload_ref": f"fixture://wecom/callback/{callback_id}",
        "metadata": {
            "idempotency_key": f"wecom:feedback:{callback_id}",
            "source_event": "wecom_button_callback",
            "source_status": "sanitized_callback",
        },
    }


if __name__ == "__main__":
    unittest.main()
