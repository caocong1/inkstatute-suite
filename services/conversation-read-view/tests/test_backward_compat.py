"""Backward compatibility regression guard for existing endpoint response shapes.

Snapshots the exact top-level keys of existing endpoint responses
(``/conversations/{id}``, ``/tasks/{id}``, ``/feedback?status=pending``) and
asserts they are unchanged after the Phase 41 read-view extension.  If any
future change alters an existing response shape, this test fails.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from feedback_service.queue import (
    build_pending_feedback_queue,
    load_jsonl_records,
    normalize_feedback_inputs,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class BackwardCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))
        feedback_events = normalize_feedback_inputs(
            compatibility_feedback_records=load_jsonl_records(
                FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"
            ),
            compatibility_preview_records=load_jsonl_records(
                FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"
            ),
        )
        self.feedback_queue = build_pending_feedback_queue(feedback_events) + [
            {
                "feedback_id": "resolved-feedback",
                "status": "resolved",
            }
        ]

    def test_conversation_response_top_level_keys_unchanged(self) -> None:
        status, body = handle_get(
            "/conversations/phase5-conv-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        expected_keys = {
            "conversation_id",
            "turn_count",
            "user_ids",
            "turns",
            "metadata",
            "issues",
        }
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertTrue(body["metadata"]["derived_from_contract_log"])
        self.assertEqual(body["metadata"]["source_status"], "contract_log_derived")
        self.assertNotIn("items", body)
        self.assertNotIn("next_cursor", body)
        self.assertNotIn("has_more", body)

    def test_task_response_top_level_keys_unchanged(self) -> None:
        status, body = handle_get(
            "/tasks/turn-phase5-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        expected_keys = {
            "task_id",
            "turn_id",
            "conversation_id",
            "trace_id",
            "status",
            "route_decision",
            "execution_trace",
            "agent_result",
            "feedback_events",
            "artifacts",
            "errors",
            "lookup_aliases",
            "source_status",
            "derived_from_contract_log",
            "fallback_source",
            "missing_associations",
            "metadata",
        }
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertNotIn("items", body)
        self.assertNotIn("next_cursor", body)
        self.assertNotIn("has_more", body)

    def test_feedback_response_top_level_keys_unchanged(self) -> None:
        status, body = handle_get(
            "/feedback?status=pending", "", self.read_model, self.feedback_queue
        )

        self.assertEqual(status, 200)
        expected_keys = {"items", "count", "metadata"}
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertTrue(body["metadata"]["derived_from_contract_log"])
        self.assertEqual(body["metadata"]["source_status"], "derived_pending_queue")
        self.assertNotIn("next_cursor", body)
        self.assertNotIn("has_more", body)

    def test_conversation_turn_keys_unchanged(self) -> None:
        status, body = handle_get(
            "/conversations/phase5-conv-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        turn = body["turns"][0]
        expected_turn_keys = {
            "turn_id",
            "conversation_id",
            "task_id",
            "agent_turn",
            "route_decision",
            "execution_trace",
            "agent_result",
            "feedback_events",
            "event_refs",
            "missing_associations",
            "source_status",
            "derived_from_contract_log",
        }
        self.assertGreaterEqual(set(turn.keys()), expected_turn_keys)

    def test_task_lookup_aliases_unchanged(self) -> None:
        status, body = handle_get(
            "/tasks/turn-phase5-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            body["lookup_aliases"],
            {
                "task_id": body["task_id"],
                "turn_id": body["turn_id"],
                "trace_id": body["trace_id"],
            },
        )

    def test_404_response_shape_unchanged(self) -> None:
        status, body = handle_get("/conversations/nonexistent", "", self.read_model)

        self.assertEqual(status, 404)
        self.assertEqual(set(body.keys()), {"error", "metadata"})
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["metadata"]["source_status"], "not_found")

    def test_handle_get_signature_unchanged(self) -> None:
        sig = inspect.signature(handle_get)
        self.assertEqual(
            list(sig.parameters.keys()),
            ["path", "query", "read_model", "feedback_queue"],
        )
        self.assertIsNone(sig.parameters["feedback_queue"].default)


if __name__ == "__main__":
    unittest.main()
