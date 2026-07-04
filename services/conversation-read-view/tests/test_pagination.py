from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
