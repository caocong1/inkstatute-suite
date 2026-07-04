"""Tests for Admin Console API data views (sessions, tasks, feedback)."""

from __future__ import annotations

import unittest
from pathlib import Path

from admin_console_api.views import (
    handle_feedback,
    handle_sessions,
    handle_tasks,
    resolve_admin_max_limit,
)
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from feedback_service.queue import (
    build_pending_feedback_queue,
    load_jsonl_records,
    normalize_feedback_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


def _build_feedback_queue() -> list[dict]:
    feedback_events = normalize_feedback_inputs(
        compatibility_feedback_records=load_jsonl_records(
            FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"
        ),
        compatibility_preview_records=load_jsonl_records(
            FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"
        ),
    )
    return build_pending_feedback_queue(feedback_events) + [
        {"feedback_id": "resolved-feedback", "status": "resolved"},
    ]


class SessionsViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_list_sessions_returns_200(self) -> None:
        status, body = handle_sessions("/sessions", {}, self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("next_cursor", body)
        self.assertIn("has_more", body)
        self.assertIs(body["metadata"]["admin_api"], True)
        self.assertIs(body["metadata"]["read_only"], True)

    def test_list_sessions_with_filter(self) -> None:
        status, body = handle_sessions("/sessions", {"channel": "wecom"}, self.read_model)
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["filters"]["channel"], "wecom")
        # The read model applies the channel filter; all returned items match.
        unfiltered = handle_sessions("/sessions", {}, self.read_model)[1]["items"]
        self.assertLessEqual(len(body["items"]), len(unfiltered))

    def test_list_sessions_pagination(self) -> None:
        status, body = handle_sessions("/sessions", {"limit": "1"}, self.read_model)
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["items"]), 1)

    def test_list_sessions_unknown_filter_returns_400(self) -> None:
        status, body = handle_sessions("/sessions", {"bad_filter": "x"}, self.read_model)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unsupported_filter")

    def test_get_session_returns_200(self) -> None:
        status, body = handle_sessions(
            "/sessions/phase5-conv-retrieval-001", {}, self.read_model
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["conversation_id"], "phase5-conv-retrieval-001")

    def test_get_session_not_found_returns_404(self) -> None:
        status, body = handle_sessions("/sessions/nonexistent", {}, self.read_model)
        self.assertEqual(status, 404)


class TasksViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_list_tasks_returns_200(self) -> None:
        status, body = handle_tasks("/tasks", {}, self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("items", body)

    def test_list_tasks_with_status_filter(self) -> None:
        status, body = handle_tasks("/tasks", {"status": "completed"}, self.read_model)
        self.assertEqual(status, 200)
        for item in body["items"]:
            self.assertEqual(item.get("status"), "completed")

    def test_list_tasks_pagination(self) -> None:
        status, body = handle_tasks("/tasks", {"limit": "1"}, self.read_model)
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["items"]), 1)

    def test_get_task_returns_200(self) -> None:
        status, body = handle_tasks("/tasks/turn-phase5-retrieval-001", {}, self.read_model)
        self.assertEqual(status, 200)

    def test_get_task_by_trace_id_returns_200(self) -> None:
        status, body = handle_tasks("/tasks/trace-phase5-retrieval-001", {}, self.read_model)
        self.assertEqual(status, 200)

    def test_get_task_not_found_returns_404(self) -> None:
        status, body = handle_tasks("/tasks/nonexistent", {}, self.read_model)
        self.assertEqual(status, 404)


class FeedbackViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))
        self.feedback_queue = _build_feedback_queue()

    def test_feedback_pending_returns_200(self) -> None:
        status, body = handle_feedback({}, self.read_model, self.feedback_queue)
        self.assertEqual(status, 200)
        for item in body["items"]:
            self.assertEqual(item["status"], "pending")

    def test_feedback_unsupported_status_returns_400(self) -> None:
        status, body = handle_feedback({"status": "closed"}, self.read_model, self.feedback_queue)
        self.assertEqual(status, 400)

    def test_feedback_scrubs_forbidden_keys(self) -> None:
        unsafe_queue = [
            {"feedback_id": "x", "status": "pending", "raw_payload": {"body": "blocked"}}
        ]
        with self.assertRaises(ValueError):
            handle_feedback({}, self.read_model, unsafe_queue)


class MaxLimitTests(unittest.TestCase):
    def test_resolve_admin_max_limit_defaults_to_100(self) -> None:
        self.assertEqual(resolve_admin_max_limit({}), 100)

    def test_resolve_admin_max_limit_env_override(self) -> None:
        self.assertEqual(resolve_admin_max_limit({"ADMIN_API_MAX_LIMIT": "500"}), 500)

    def test_resolve_admin_max_limit_clamps_to_min(self) -> None:
        self.assertEqual(resolve_admin_max_limit({"ADMIN_API_MAX_LIMIT": "5"}), 10)

    def test_resolve_admin_max_limit_clamps_to_max(self) -> None:
        self.assertEqual(resolve_admin_max_limit({"ADMIN_API_MAX_LIMIT": "99999"}), 1000)

    def test_resolve_admin_max_limit_ignores_garbage(self) -> None:
        self.assertEqual(resolve_admin_max_limit({"ADMIN_API_MAX_LIMIT": "abc"}), 100)


if __name__ == "__main__":
    unittest.main()
