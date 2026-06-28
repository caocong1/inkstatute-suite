from __future__ import annotations

from pathlib import Path
import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records, normalize_feedback_inputs


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class ReadViewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))
        feedback_events = normalize_feedback_inputs(
            compatibility_feedback_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"),
            compatibility_preview_records=load_jsonl_records(FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"),
        )
        self.feedback_queue = build_pending_feedback_queue(feedback_events) + [
            {
                "feedback_id": "resolved-feedback",
                "status": "resolved",
            }
        ]

    def test_get_conversation_returns_200(self) -> None:
        status, body = handle_get("/conversations/phase5-conv-retrieval-001", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertEqual(body["conversation_id"], "phase5-conv-retrieval-001")
        self.assertTrue(body["metadata"]["derived_from_contract_log"])

    def test_get_task_by_turn_id_returns_200(self) -> None:
        status, body = handle_get("/tasks/turn-phase5-retrieval-001", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertEqual(body["turn_id"], "turn-phase5-retrieval-001")

    def test_get_task_by_trace_id_returns_200(self) -> None:
        status, body = handle_get("/tasks/trace-phase5-retrieval-001", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertEqual(body["trace_id"], "trace-phase5-retrieval-001")

    def test_get_feedback_pending_returns_only_pending_items(self) -> None:
        status, body = handle_get("/feedback?status=pending", "", self.read_model, self.feedback_queue)

        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)
        self.assertTrue(all(item["status"] == "pending" for item in body["items"]))

    def test_unsupported_path_returns_404(self) -> None:
        status, body = handle_get("/unknown", "", self.read_model)

        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_unsupported_feedback_status_returns_400(self) -> None:
        status, body = handle_get("/feedback", "status=closed", self.read_model, self.feedback_queue)

        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unsupported_status")


if __name__ == "__main__":
    unittest.main()

