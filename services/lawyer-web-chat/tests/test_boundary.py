"""Tests for ChatBoundary — output boundary + HTML escaping."""

from __future__ import annotations

import unittest

from lawyer_web_chat.boundary import ChatBoundary
from platform_runtime.output_boundary import BoundaryAction


class ChatBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = ChatBoundary()

    def test_allows_business_text_and_escapes_html(self) -> None:
        decision = self.boundary.apply("Your case analysis is ready <b>bold</b>")
        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertIsNotNone(decision.visible_text)
        assert decision.visible_text is not None
        self.assertIn("&lt;b&gt;", decision.visible_text)
        self.assertNotIn("<b>", decision.visible_text)

    def test_blocks_model_name_leak(self) -> None:
        decision = self.boundary.apply("model: gpt-4 is processing your request")
        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertIsNone(decision.visible_text)

    def test_blocks_api_error_traces(self) -> None:
        decision = self.boundary.apply("api key invalid: quota exceeded")
        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertIsNone(decision.visible_text)

    def test_blocks_function_call_internals(self) -> None:
        decision = self.boundary.apply("function call result: tool output")
        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertIsNone(decision.visible_text)

    def test_blocks_secret_like_patterns(self) -> None:
        decision = self.boundary.apply("access_token=abc123 for authentication")
        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertIsNone(decision.visible_text)

    def test_rewrites_backend_lifecycle_notice(self) -> None:
        decision = self.boundary.apply("self-update in progress, restarting")
        self.assertEqual(decision.action, BoundaryAction.REWRITE)
        self.assertIsNotNone(decision.visible_text)
        assert decision.visible_text is not None
        self.assertIn("InkStatute", decision.visible_text)
        self.assertNotIn("restarting", decision.visible_text)

    def test_rewrites_debug_trace(self) -> None:
        decision = self.boundary.apply("debug: checking internal state")
        self.assertEqual(decision.action, BoundaryAction.REWRITE)
        self.assertIsNotNone(decision.visible_text)

    def test_rewrites_rate_limit_notice(self) -> None:
        decision = self.boundary.apply("rate limited: too many requests, retrying after 30s")
        self.assertEqual(decision.action, BoundaryAction.REWRITE)
        self.assertIsNotNone(decision.visible_text)

    def test_escape_value_escapes_arbitrary_string(self) -> None:
        result = self.boundary.escape_value('<img src="x" onerror="alert(1)">')
        self.assertIn("&lt;img", result)
        self.assertNotIn("<img", result)

    def test_escape_value_handles_non_string(self) -> None:
        result = self.boundary.escape_value(42)
        self.assertEqual(result, "42")

    def test_allows_none_text(self) -> None:
        decision = self.boundary.apply(None)
        self.assertEqual(decision.action, BoundaryAction.ALLOW)


if __name__ == "__main__":
    unittest.main()
