from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
