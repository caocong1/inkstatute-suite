"""Tests for AdminUiBoundary — output boundary + HTML escaping."""

from __future__ import annotations

import unittest

from admin_web_ui.boundary import AdminUiBoundary
from platform_runtime.output_boundary import BoundaryAction


class AdminUiBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = AdminUiBoundary()

    def test_allows_business_text_and_escapes_html(self) -> None:
        decision = self.boundary.apply("Hello <script>alert(1)</script>")
        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertIsNotNone(decision.visible_text)
        assert decision.visible_text is not None
        self.assertIn("&lt;script&gt;", decision.visible_text)
        self.assertNotIn("<script>", decision.visible_text)

    def test_blocks_model_name_leak(self) -> None:
        decision = self.boundary.apply("model: gpt-4 processing your request")
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

    def test_rewrites_backend_lifecycle_notice(self) -> None:
        decision = self.boundary.apply("self-update in progress, restarting")
        self.assertEqual(decision.action, BoundaryAction.REWRITE)
        self.assertIsNotNone(decision.visible_text)
        assert decision.visible_text is not None
        self.assertIn("InkStatute", decision.visible_text)

    def test_rewrites_debug_trace(self) -> None:
        decision = self.boundary.apply("debug: checking internal state")
        self.assertEqual(decision.action, BoundaryAction.REWRITE)
        self.assertIsNotNone(decision.visible_text)

    def test_escape_value_escapes_arbitrary_string(self) -> None:
        result = self.boundary.escape_value('<img src="x" onerror="alert(1)">')
        self.assertIn("&lt;img", result)
        self.assertIn("&quot;", result)
        self.assertNotIn("<img", result)

    def test_escape_value_handles_non_string(self) -> None:
        result = self.boundary.escape_value(42)
        self.assertEqual(result, "42")

    def test_allows_none_text(self) -> None:
        decision = self.boundary.apply(None)
        # None text is treated as empty string, which is allowed
        self.assertEqual(decision.action, BoundaryAction.ALLOW)


if __name__ == "__main__":
    unittest.main()
