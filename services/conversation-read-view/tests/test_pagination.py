from __future__ import annotations

from pathlib import Path
import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.pagination import (
    DEFAULT_MAX_RESULT_LIMIT,
    DEFAULT_PAGE_SIZE,
    MAX_MAX_RESULT_LIMIT,
    MIN_MAX_RESULT_LIMIT,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    resolve_max_result_limit,
    slice_page,
)
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records, normalize_feedback_inputs


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class PaginationTests(unittest.TestCase):
    def test_resolve_max_result_limit_defaults_to_100(self) -> None:
        self.assertEqual(resolve_max_result_limit({}), 100)

    def test_resolve_max_result_limit_env_override(self) -> None:
        self.assertEqual(
            resolve_max_result_limit({"CONVERSATION_READ_VIEW_MAX_LIMIT": "500"}),
            500,
        )

    def test_resolve_max_result_limit_clamps_to_min(self) -> None:
        self.assertEqual(
            resolve_max_result_limit({"CONVERSATION_READ_VIEW_MAX_LIMIT": "5"}),
            MIN_MAX_RESULT_LIMIT,
        )

    def test_resolve_max_result_limit_clamps_to_max(self) -> None:
        self.assertEqual(
            resolve_max_result_limit({"CONVERSATION_READ_VIEW_MAX_LIMIT": "99999"}),
            MAX_MAX_RESULT_LIMIT,
        )

    def test_resolve_max_result_limit_ignores_garbage(self) -> None:
        self.assertEqual(
            resolve_max_result_limit({"CONVERSATION_READ_VIEW_MAX_LIMIT": "abc"}),
            DEFAULT_MAX_RESULT_LIMIT,
        )

    def test_clamp_limit_defaults_when_none(self) -> None:
        self.assertEqual(clamp_limit(None, 100), DEFAULT_PAGE_SIZE)

    def test_clamp_limit_clamps_to_max(self) -> None:
        self.assertEqual(clamp_limit(10000, 100), 100)

    def test_clamp_limit_clamps_to_min_1(self) -> None:
        self.assertEqual(clamp_limit(0, 100), 1)

    def test_encode_decode_cursor_roundtrip(self) -> None:
        cursor = encode_cursor("conv-001", "2026-06-28T05:00:00Z")
        self.assertEqual(
            decode_cursor(cursor),
            ("conv-001", "2026-06-28T05:00:00Z"),
        )

    def test_decode_invalid_cursor_returns_none(self) -> None:
        self.assertIsNone(decode_cursor("!!!not-valid-base64!!!"))
        self.assertIsNone(decode_cursor("not-base64-at-all"))

    def test_slice_page_without_cursor(self) -> None:
        items = [
            ("a", "t1", {"id": "a"}),
            ("b", "t2", {"id": "b"}),
            ("c", "t3", {"id": "c"}),
        ]
        page, next_cursor, has_more = slice_page(items, None, 2)

        self.assertEqual(len(page), 2)
        self.assertEqual(page[0]["id"], "a")
        self.assertTrue(has_more)
        self.assertIsNotNone(next_cursor)

    def test_slice_page_with_cursor(self) -> None:
        items = [
            ("a", "t1", {"id": "a"}),
            ("b", "t2", {"id": "b"}),
            ("c", "t3", {"id": "c"}),
        ]
        cursor = encode_cursor("a", "t1")
        page, next_cursor, has_more = slice_page(items, cursor, 2)

        self.assertEqual(len(page), 2)
        self.assertEqual(page[0]["id"], "b")
        self.assertFalse(has_more)
        self.assertIsNone(next_cursor)

    def test_slice_page_exact_page_no_more(self) -> None:
        items = [
            ("a", "t1", {"id": "a"}),
            ("b", "t2", {"id": "b"}),
        ]
        page, next_cursor, has_more = slice_page(items, None, 2)

        self.assertEqual(len(page), 2)
        self.assertFalse(has_more)
        self.assertIsNone(next_cursor)

    def test_same_cursor_replays_same_boundary(self) -> None:
        items = [
            ("a", "t1", {}),
            ("b", "t2", {}),
            ("c", "t3", {}),
            ("d", "t4", {}),
        ]
        cursor = encode_cursor("b", "t2")
        page1, _, _ = slice_page(items, cursor, 1)
        page2, _, _ = slice_page(items, cursor, 1)

        self.assertEqual(page1, page2)


class ListEndpointsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_list_conversations_returns_all_conversations(self) -> None:
        items = self.model.list_conversations()

        self.assertGreaterEqual(len(items), 1)
        for entry in items:
            self.assertEqual(len(entry), 3)
            sort_key, occurred_at, conversation_dict = entry
            self.assertIsInstance(sort_key, str)
            self.assertIsInstance(occurred_at, str)
            self.assertIn("conversation_id", conversation_dict)

    def test_list_conversations_filters_by_user_id(self) -> None:
        items = self.model.list_conversations(user_id="phase5-lawyer-001")

        self.assertGreaterEqual(len(items), 1)
        for _, _, conversation_dict in items:
            self.assertIn("phase5-lawyer-001", conversation_dict["user_ids"])

    def test_list_conversations_filters_by_channel(self) -> None:
        items = self.model.list_conversations(channel="wecom")

        self.assertGreaterEqual(len(items), 1)
        for _, _, conversation_dict in items:
            channels = {
                turn.get("agent_turn", {}).get("channel")
                for turn in conversation_dict.get("turns", [])
            }
            self.assertIn("wecom", channels)

    def test_list_conversations_time_range_filter(self) -> None:
        items = self.model.list_conversations(
            time_from="2026-06-28T00:00:00Z",
            time_to="2026-06-29T00:00:00Z",
        )

        for _, occurred_at, _ in items:
            self.assertGreaterEqual(occurred_at, "2026-06-28T00:00:00Z")
            self.assertLessEqual(occurred_at, "2026-06-29T00:00:00Z")

    def test_list_conversations_time_from_excludes_earlier(self) -> None:
        items = self.model.list_conversations(time_from="2026-06-29T00:00:00Z")

        for _, occurred_at, _ in items:
            self.assertGreaterEqual(occurred_at, "2026-06-29T00:00:00Z")

    def test_list_tasks_returns_unique_tasks(self) -> None:
        items = self.model.list_tasks()

        task_ids = [item[0] for item in items]
        self.assertEqual(len(task_ids), len(set(task_ids)))

    def test_list_tasks_filters_by_status(self) -> None:
        items = self.model.list_tasks(status="success")

        for _, _, task_dict in items:
            self.assertEqual(task_dict["status"], "success")

    def test_list_tasks_filters_by_user_id(self) -> None:
        items = self.model.list_tasks(user_id="phase5-lawyer-001")

        self.assertGreaterEqual(len(items), 1)
        for _, _, task_dict in items:
            self.assertEqual(task_dict["conversation_id"], "phase5-conv-retrieval-001")

    def test_list_tasks_combined_filters_and_semantics(self) -> None:
        items = self.model.list_tasks(status="success", channel="wecom")

        for _, _, task_dict in items:
            self.assertEqual(task_dict["status"], "success")

    def test_list_conversations_sorted_by_conversation_id(self) -> None:
        items = self.model.list_conversations()

        sort_keys = [item[0] for item in items]
        self.assertEqual(sort_keys, sorted(sort_keys))

    def test_list_tasks_sorted_by_task_id(self) -> None:
        items = self.model.list_tasks()

        sort_keys = [item[0] for item in items]
        self.assertEqual(sort_keys, sorted(sort_keys))


class ListRouteTests(unittest.TestCase):
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

    def test_list_conversations_returns_200_with_items(self) -> None:
        status, body = handle_get("/conversations", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)
        self.assertIn("next_cursor", body)
        self.assertIn("has_more", body)
        self.assertIn("metadata", body)
        self.assertTrue(body["metadata"]["derived_from_contract_log"])
        self.assertEqual(body["metadata"]["max_result_limit"], 100)

    def test_list_conversations_with_limit(self) -> None:
        status, body = handle_get("/conversations?limit=1", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertLessEqual(body["count"], 1)
        self.assertEqual(body["metadata"]["limit"], 1)

    def test_list_conversations_limit_clamped_to_max(self) -> None:
        status, body = handle_get("/conversations?limit=99999", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertLessEqual(body["metadata"]["limit"], body["metadata"]["max_result_limit"])

    def test_list_conversations_pagination_roundtrip(self) -> None:
        status1, body1 = handle_get("/conversations?limit=1", "", self.read_model)

        if body1["has_more"]:
            cursor = body1["next_cursor"]
            status2, body2 = handle_get(
                f"/conversations?limit=1&cursor={cursor}", "", self.read_model
            )
            self.assertEqual(status2, 200)
            self.assertNotEqual(
                body2["items"][0]["conversation_id"],
                body1["items"][0]["conversation_id"],
            )

    def test_list_conversations_filter_by_channel(self) -> None:
        status, body = handle_get("/conversations?channel=wecom", "", self.read_model)

        self.assertEqual(status, 200)
        for item in body["items"]:
            channels = {
                turn.get("agent_turn", {}).get("channel")
                for turn in item.get("turns", [])
            }
            self.assertIn("wecom", channels)

    def test_list_conversations_filter_by_user_id(self) -> None:
        status, body = handle_get(
            "/conversations?user_id=phase5-lawyer-001", "", self.read_model
        )

        self.assertEqual(status, 200)

    def test_list_conversations_time_range(self) -> None:
        status, body = handle_get(
            "/conversations?from=2026-06-28T00:00:00Z&to=2026-06-29T00:00:00Z",
            "",
            self.read_model,
        )

        self.assertEqual(status, 200)

    def test_list_conversations_unknown_filter_returns_400(self) -> None:
        status, body = handle_get("/conversations?foo=bar", "", self.read_model)

        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unsupported_filter")

    def test_list_conversations_invalid_time_returns_400(self) -> None:
        status, body = handle_get("/conversations?from=not-a-date", "", self.read_model)

        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_time_filter")

    def test_list_tasks_returns_200_with_items(self) -> None:
        status, body = handle_get("/tasks", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)

    def test_list_tasks_filter_by_status(self) -> None:
        status, body = handle_get("/tasks?status=success", "", self.read_model)

        self.assertEqual(status, 200)
        for item in body["items"]:
            self.assertEqual(item["status"], "success")

    def test_list_tasks_unknown_filter_returns_400(self) -> None:
        status, body = handle_get("/tasks?foo=bar", "", self.read_model)

        self.assertEqual(status, 400)

    def test_list_tasks_pagination_next_cursor_null_when_no_more(self) -> None:
        status, body = handle_get("/tasks?limit=1000", "", self.read_model)

        self.assertEqual(status, 200)
        self.assertFalse(body["has_more"])
        self.assertIsNone(body["next_cursor"])

    def test_existing_single_conversation_still_works(self) -> None:
        status, body = handle_get(
            "/conversations/phase5-conv-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        self.assertIn("conversation_id", body)
        self.assertNotIn("items", body)

    def test_existing_single_task_still_works(self) -> None:
        status, body = handle_get(
            "/tasks/turn-phase5-retrieval-001", "", self.read_model
        )

        self.assertEqual(status, 200)
        self.assertIn("task_id", body)
        self.assertNotIn("items", body)

    def test_existing_feedback_still_works(self) -> None:
        status, body = handle_get(
            "/feedback?status=pending", "", self.read_model, self.feedback_queue
        )

        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)


if __name__ == "__main__":
    unittest.main()
