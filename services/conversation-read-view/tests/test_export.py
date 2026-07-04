from __future__ import annotations

from pathlib import Path
import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class _FakeReadModel:
    """Minimal fake read model for scrub-verification tests."""

    def __init__(self, conversations: list, tasks: list | None = None) -> None:
        self._conversations = conversations
        self._tasks = tasks or []

    def list_conversations(self, **kwargs):
        return self._conversations

    def list_tasks(self, **kwargs):
        return self._tasks


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_export_conversations_json(self) -> None:
        status, body = handle_get("/export?resource=conversations&format=json", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)
        self.assertEqual(body["metadata"]["format"], "json")
        self.assertTrue(body["metadata"]["derived_from_contract_log"])

    def test_export_tasks_json(self) -> None:
        status, body = handle_get("/export?resource=tasks&format=json", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertTrue(all("task_id" in item for item in body["items"]))

    def test_export_conversations_csv(self) -> None:
        status, body = handle_get("/export?resource=conversations&format=csv", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("data", body)
        self.assertIsInstance(body["data"], str)
        self.assertIn("conversation_id,turn_count,user_ids,occurred_at", body["data"])
        self.assertEqual(body["metadata"]["format"], "csv")
        self.assertIsInstance(body["metadata"]["csv_projection"], list)

    def test_export_tasks_csv(self) -> None:
        status, body = handle_get("/export?resource=tasks&format=csv", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("data", body)
        self.assertIn("task_id,turn_id,conversation_id,trace_id,status,occurred_at", body["data"])

    def test_export_unknown_resource_returns_400(self) -> None:
        status, body = handle_get("/export?resource=unknown&format=json", "", self.read_model)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unsupported_resource")

    def test_export_unknown_format_returns_400(self) -> None:
        status, body = handle_get("/export?resource=conversations&format=xml", "", self.read_model)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unsupported_format")

    def test_export_default_format_is_json(self) -> None:
        status, body = handle_get("/export?resource=conversations", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["format"], "json")

    def test_export_limit_clamped(self) -> None:
        status, body = handle_get("/export?resource=conversations&format=json&limit=99999", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertLessEqual(body["metadata"]["limit"], body["metadata"]["max_result_limit"])

    def test_export_with_filters(self) -> None:
        status, body = handle_get("/export?resource=tasks&format=json&status=success", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertTrue(all(item.get("status") == "success" for item in body["items"]))

    def test_export_csv_omits_nested_fields(self) -> None:
        status, body = handle_get("/export?resource=conversations&format=csv", "", self.read_model)
        self.assertEqual(status, 200)
        csv_data = body["data"]
        first_line = csv_data.split("\n", 1)[0]
        self.assertNotIn("agent_result", first_line)
        self.assertNotIn("route_decision", first_line)
        self.assertNotIn("execution_trace", first_line)

    def test_export_json_items_are_scrubbed(self) -> None:
        fake = _FakeReadModel(
            conversations=[("conv-x", "2026-01-01T00:00:00Z", {"conversation_id": "conv-x", "case_facts": "blocked"})]
        )
        with self.assertRaises(ValueError):
            handle_get("/export?resource=conversations&format=json", "", fake)

    def test_export_csv_items_are_scrubbed(self) -> None:
        fake = _FakeReadModel(
            conversations=[("conv-x", "2026-01-01T00:00:00Z", {"conversation_id": "conv-x", "case_facts": "blocked"})]
        )
        with self.assertRaises(ValueError):
            handle_get("/export?resource=conversations&format=csv", "", fake)


if __name__ == "__main__":
    unittest.main()
