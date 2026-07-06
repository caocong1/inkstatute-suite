"""Tests for Admin Console API data views (sessions, tasks, feedback)."""

from __future__ import annotations

import copy
import json
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
from platform_runtime.tenant_scope import ScopedQueryFilter

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


def _load_raw_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_tenant_tagged_read_model():
    """Build a read model with tenant_id-injected records for two tenants."""
    base_records = _load_raw_records(PHASE5_STREAM)
    records: list[dict[str, object]] = []

    for tenant in ("firm-a", "firm-b"):
        for rec in base_records:
            cloned = copy.deepcopy(rec)
            event = cloned.get("event")
            if isinstance(event, dict):
                event["tenant_id"] = tenant
                if cloned.get("event_key") == "agent_turn":
                    event["conversation_id"] = f"conv-{tenant}"
                    event["turn_id"] = f"turn-{tenant}"
                elif "turn_id" in event:
                    event["turn_id"] = f"turn-{tenant}"
                    event["conversation_id"] = f"conv-{tenant}"
            records.append(cloned)

    return build_read_model(records)


class TenantScopedSessionsViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = _build_tenant_tagged_read_model()

    def test_list_sessions_with_active_tenant_filter(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_sessions("/sessions", {}, self.read_model, tenant_filter=active)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["conversation_id"], "conv-firm-a")

    def test_list_sessions_with_disabled_filter_returns_all(self) -> None:
        disabled = ScopedQueryFilter.disabled()
        status, body = handle_sessions("/sessions", {}, self.read_model, tenant_filter=disabled)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 2)

    def test_list_sessions_with_no_filter_returns_all(self) -> None:
        status, body = handle_sessions("/sessions", {}, self.read_model)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 2)

    def test_get_session_wrong_tenant_returns_404(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_sessions("/sessions/conv-firm-b", {}, self.read_model, tenant_filter=active)
        self.assertEqual(status, 404)

    def test_get_session_matching_tenant_returns_200(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_sessions("/sessions/conv-firm-a", {}, self.read_model, tenant_filter=active)
        self.assertEqual(status, 200)
        self.assertEqual(body["conversation_id"], "conv-firm-a")


class TenantScopedTasksViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = _build_tenant_tagged_read_model()

    def test_list_tasks_with_active_tenant_filter(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_tasks("/tasks", {}, self.read_model, tenant_filter=active)
        self.assertEqual(status, 200)
        for item in body["items"]:
            self.assertEqual(item["conversation_id"], "conv-firm-a")

    def test_list_tasks_with_disabled_filter_returns_all(self) -> None:
        disabled = ScopedQueryFilter.disabled()
        status, body = handle_tasks("/tasks", {}, self.read_model, tenant_filter=disabled)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body["items"]), 1)

    def test_get_task_wrong_tenant_returns_404(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_tasks("/tasks/turn-firm-b", {}, self.read_model, tenant_filter=active)
        self.assertEqual(status, 404)


class TenantScopedFeedbackViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = _build_tenant_tagged_read_model()
        self.feedback_queue = [
            {"feedback_id": "fb-1", "status": "pending", "tenant_id": "firm-a"},
            {"feedback_id": "fb-2", "status": "pending", "tenant_id": "firm-b"},
            {"feedback_id": "fb-3", "status": "pending", "tenant_id": "firm-a"},
            {"feedback_id": "fb-4", "status": "resolved", "tenant_id": "firm-a"},
        ]

    def test_feedback_with_active_tenant_filter(self) -> None:
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_feedback({}, self.read_model, self.feedback_queue, tenant_filter=active)
        self.assertEqual(status, 200)
        ids = [item["feedback_id"] for item in body["items"]]
        self.assertIn("fb-1", ids)
        self.assertIn("fb-3", ids)
        self.assertNotIn("fb-2", ids)
        self.assertNotIn("fb-4", ids)

    def test_feedback_with_disabled_filter_returns_all_pending(self) -> None:
        disabled = ScopedQueryFilter.disabled()
        status, body = handle_feedback({}, self.read_model, self.feedback_queue, tenant_filter=disabled)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 3)

    def test_feedback_with_no_filter_returns_all_pending(self) -> None:
        status, body = handle_feedback({}, self.read_model, self.feedback_queue)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 3)

    def test_feedback_active_filter_excludes_items_without_tenant_id(self) -> None:
        queue = [
            {"feedback_id": "fb-no-tenant", "status": "pending"},
            {"feedback_id": "fb-a", "status": "pending", "tenant_id": "firm-a"},
        ]
        active = ScopedQueryFilter(tenant_id="firm-a", active=True)
        status, body = handle_feedback({}, self.read_model, queue, tenant_filter=active)
        self.assertEqual(status, 200)
        ids = [item["feedback_id"] for item in body["items"]]
        self.assertIn("fb-a", ids)
        self.assertNotIn("fb-no-tenant", ids)


if __name__ == "__main__":
    unittest.main()
