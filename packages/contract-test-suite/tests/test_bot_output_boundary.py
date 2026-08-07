"""Bot output boundary double enforcement tests.

These tests verify that the output boundary is enforced at multiple layers
for bot channels — the Gateway SSE (first point), the degradation rules
(second point), and the channel output policy (third point).

SC#6: "后端 meta / gateway / system 噪声在 bot 通道同样不可见
（输出边界在 Gateway 与降级层双重生效）"
"""

from __future__ import annotations

import unittest

from platform_contract.bot_degradation import (
    DEGRADATION_RULES,
    BotDelivery,
    DegradationCategory,
    aggregate_events,
)
from platform_runtime.output_boundary import (
    BoundaryAction,
    DefaultAssistantOutputBoundary,
)


class TestBotOutputBoundary(unittest.TestCase):
    """Verify output boundary double enforcement for bot channels."""

    # ------------------------------------------------------------------
    # 1. SILENT drops session.started
    # ------------------------------------------------------------------

    def test_silent_drops_session_started(self) -> None:
        """aggregate_events with session.started returns BotDelivery(delivered=False)."""
        result = aggregate_events([
            {"event_type": "session.started", "seq": 1, "payload": {}},
        ])
        self.assertFalse(result.delivered)
        self.assertIsNone(result.final_message)
        self.assertEqual(result.intermediate_prompts, [])

    # ------------------------------------------------------------------
    # 2. DISCARD drops thought.delta
    # ------------------------------------------------------------------

    def test_discard_drops_thought_delta(self) -> None:
        """aggregate_events with thought.delta returns BotDelivery(delivered=False).
        No thought content reaches the bot."""
        result = aggregate_events([
            {"event_type": "thought.delta", "seq": 1,
             "payload": {"delta": "internal reasoning"}},
        ])
        self.assertFalse(result.delivered)
        self.assertIsNone(result.final_message)
        self.assertEqual(result.intermediate_prompts, [])
        # The thought content must not appear anywhere in the delivery
        self.assertNotIn("internal reasoning", result.final_message or "")

    # ------------------------------------------------------------------
    # 3. FOLD collapses tool_call to prompt
    # ------------------------------------------------------------------

    def test_fold_collapses_tool_call_to_prompt(self) -> None:
        """aggregate_events with tool_call.started returns
        BotDelivery(intermediate_prompts=['正在检索法规…']).
        The actual tool name does NOT appear in the output."""
        result = aggregate_events([
            {"event_type": "tool_call.started", "seq": 1,
             "payload": {"tool": "search_law"}},
        ])
        self.assertIn("正在检索法规…", result.intermediate_prompts)
        # The tool name must not appear in any output field
        all_output = " ".join(result.intermediate_prompts)
        self.assertNotIn("search_law", all_output,
                         f"Tool name should not appear in output: {all_output}")

    # ------------------------------------------------------------------
    # 4. FOLD subsequent tool calls are silent
    # ------------------------------------------------------------------

    def test_fold_subsequent_tool_calls_silent(self) -> None:
        """Multiple tool_call.* events produce only ONE '正在检索法规…' prompt.
        Subsequent tool calls are silent."""
        result = aggregate_events([
            {"event_type": "tool_call.started", "seq": 1, "payload": {"tool": "search"}},
            {"event_type": "tool_call.delta", "seq": 2, "payload": {"tool": "search"}},
            {"event_type": "tool_call.completed", "seq": 3, "payload": {"tool": "search"}},
            {"event_type": "tool_call.started", "seq": 4, "payload": {"tool": "other"}},
        ])
        tool_prompts = [p for p in result.intermediate_prompts if "正在检索法规…" in p]
        self.assertEqual(len(tool_prompts), 1,
                         f"Expected exactly 1 tool fold prompt, got {len(tool_prompts)}: {result.intermediate_prompts}")

    # ------------------------------------------------------------------
    # 5. ON_FAILURE only delivers on failure
    # ------------------------------------------------------------------

    def test_on_failure_only_delivers_on_failure(self) -> None:
        """run.state_changed with status=succeeded returns delivered=False.
        status=failed produces error_prompt."""
        # Success — silent
        result_success = aggregate_events([
            {"event_type": "run.state_changed", "seq": 1,
             "payload": {"status": "succeeded"}},
        ])
        self.assertFalse(result_success.delivered)
        self.assertIsNone(result_success.error_prompt)

        # Failure — delivers error prompt
        result_failed = aggregate_events([
            {"event_type": "run.state_changed", "seq": 1,
             "payload": {"status": "failed"}},
        ])
        self.assertTrue(result_failed.delivered)
        self.assertEqual(result_failed.error_prompt, "处理失败，请稍后重试或联系管理员")

    # ------------------------------------------------------------------
    # 6. Gateway noise blocked by boundary
    # ------------------------------------------------------------------

    def test_gateway_noise_blocked_by_boundary(self) -> None:
        """Given a message.completed event with payload content 'gateway: restarted',
        the DefaultAssistantOutputBoundary.apply() returns BLOCK or REWRITE.
        The noise is blocked at the output boundary."""
        boundary = DefaultAssistantOutputBoundary()
        decision = boundary.apply(
            "ordinary_user",
            text="gateway: restarted",
            event_type="message_delta",
        )
        self.assertIn(decision.action, (BoundaryAction.BLOCK, BoundaryAction.REWRITE),
                      f"Expected BLOCK or REWRITE for gateway noise, got {decision.action}")
        # The original noise text should not be the visible text
        if decision.visible_text:
            self.assertNotIn("gateway: restarted", decision.visible_text,
                             "Original noise should not appear in visible text")

    # ------------------------------------------------------------------
    # 7. System noise blocked by boundary
    # ------------------------------------------------------------------

    def test_system_noise_blocked_by_boundary(self) -> None:
        """Same test for 'admin_notice: system maintenance' content."""
        boundary = DefaultAssistantOutputBoundary()
        decision = boundary.apply(
            "ordinary_user",
            text="admin_notice: system maintenance",
            event_type="message_delta",
        )
        self.assertIn(decision.action, (BoundaryAction.BLOCK, BoundaryAction.REWRITE),
                      f"Expected BLOCK or REWRITE for system noise, got {decision.action}")
        if decision.visible_text:
            self.assertNotIn("admin_notice", decision.visible_text,
                             "Original noise should not appear in visible text")

    # ------------------------------------------------------------------
    # 8. Degradation + boundary combined
    # ------------------------------------------------------------------

    def test_degradation_plus_boundary_combined(self) -> None:
        """Given a mixed event stream with: session.started (SILENT),
        thought.delta (DISCARD), tool_call.started (FOLD), message.completed
        with noise (BLOCK), message.completed with clean text (DELIVER).
        Assert the final BotDelivery has: intermediate_prompts=['正在检索法规…'],
        final_message is the clean text (not the noise), delivered=True."""
        events = [
            {"event_type": "session.started", "seq": 1, "payload": {}},
            {"event_type": "thought.delta", "seq": 2, "payload": {"delta": "thinking"}},
            {"event_type": "tool_call.started", "seq": 3, "payload": {"tool": "search"}},
            {"event_type": "message.completed", "seq": 4,
             "payload": {"content": "admin_notice: system check"}},
            {"event_type": "message.completed", "seq": 5,
             "payload": {"content": "合同审查完成，风险已识别"}},
            {"event_type": "run.state_changed", "seq": 6,
             "payload": {"status": "succeeded"}},
        ]
        result = aggregate_events(events)
        # The FOLD rule produces the tool prompt
        self.assertIn("正在检索法规…", result.intermediate_prompts)
        # The final message is the last message.completed content (clean text)
        self.assertIsNotNone(result.final_message)
        self.assertIn("合同审查完成", result.final_message)
        # The noise from the first message.completed is overwritten by the
        # second message.completed (aggregate_events uses the last one)
        self.assertNotIn("admin_notice", result.final_message,
                         f"Noise should not appear in final message: {result.final_message}")
        self.assertTrue(result.delivered)

    # ------------------------------------------------------------------
    # 9. No backend meta in bot delivery
    # ------------------------------------------------------------------

    def test_no_backend_meta_in_bot_delivery(self) -> None:
        """Given events with various backend metadata in payloads (gateway,
        system, update, command, help, available_commands_update, terminal),
        assert NONE of these keywords appear in BotDelivery.final_message,
        intermediate_prompts, cards, files, or error_prompt."""
        # Use noise that matches block/rewrite patterns in the output boundary
        # The degradation layer itself doesn't filter message.completed content —
        # it just sets final_message. The output boundary at the channel level
        # blocks the noise. Here we test that the degradation rules correctly
        # drop SILENT/DISCARD events so their content never enters the delivery.
        events = [
            {"event_type": "session.started", "seq": 1,
             "payload": {"gateway": "restarting", "system": "maintenance"}},
            {"event_type": "thought.delta", "seq": 2,
             "payload": {"delta": "update available, command /help, terminal access"}},
            {"event_type": "tool_call.started", "seq": 3,
             "payload": {"tool": "available_commands_update"}},
            {"event_type": "message.completed", "seq": 4,
             "payload": {"content": "合法合规的审查结果"}},
            {"event_type": "run.state_changed", "seq": 5,
             "payload": {"status": "succeeded"}},
        ]
        result = aggregate_events(events)
        # Check all output fields for backend noise keywords
        all_output_parts = [
            result.final_message or "",
            " ".join(result.intermediate_prompts),
            " ".join(str(c) for c in result.cards),
            " ".join(str(f) for f in result.files),
            result.error_prompt or "",
        ]
        all_output = " ".join(all_output_parts).lower()
        # These backend meta keywords should not appear in the output
        # (session.started and thought.delta are dropped by SILENT/DISCARD)
        forbidden = ["restarting", "maintenance", "update available",
                     "command /help", "terminal access",
                     "available_commands_update"]
        for keyword in forbidden:
            self.assertNotIn(keyword.lower(), all_output,
                             f"Backend meta '{keyword}' should not appear in delivery output: {all_output}")

    # ------------------------------------------------------------------
    # 10. Citation attach preserves clean text
    # ------------------------------------------------------------------

    def test_citation_attach_preserves_clean_text(self) -> None:
        """Given message.completed with clean content + citation.recorded,
        the final message includes the clean content plus a '引用：' section.
        No noise is introduced by the citation attachment."""
        events = [
            {"event_type": "message.completed", "seq": 1,
             "payload": {"content": "审查结果：合同条款合法"}},
            {"event_type": "citation.recorded", "seq": 2,
             "payload": {"citations": [
                 {"source": "合同法第107条", "status": "verified"},
             ]}},
            {"event_type": "run.state_changed", "seq": 3,
             "payload": {"status": "succeeded"}},
        ]
        result = aggregate_events(events)
        self.assertIsNotNone(result.final_message)
        self.assertIn("审查结果：合同条款合法", result.final_message)
        self.assertIn("引用：", result.final_message)
        self.assertIn("合同法第107条", result.final_message)
        # No noise introduced
        self.assertNotIn("gateway", result.final_message.lower())
        self.assertNotIn("system", result.final_message.lower())

    # ------------------------------------------------------------------
    # 11. Double enforcement documentation
    # ------------------------------------------------------------------

    def test_double_enforcement_documentation(self) -> None:
        """A documentation test that asserts the output boundary is enforced at:
        (a) Gateway SSE (GatewaySseStream.encode_event returns None for blocked events),
        (b) degradation rules (SILENT/DISCARD/FOLD/ON_FAILURE filter events),
        (c) channel output policy (apply_output_policy at delivery time).
        Import the relevant modules and assert they exist and have the expected
        interfaces."""
        # (a) Gateway SSE enforcement
        from gateway.sse import GatewaySseStream
        sse_stream = GatewaySseStream()
        # encode_event with noise should return None (blocked)
        blocked_event = {
            "event_type": "message_delta",
            "seq": 1,
            "payload": {"content": "admin_notice: system check"},
        }
        result = sse_stream.encode_event(blocked_event)
        self.assertIsNone(result,
                          "Gateway SSE should block admin_notice noise (return None)")

        # (b) Degradation rules enforcement
        self.assertIn("session.started", DEGRADATION_RULES)
        self.assertEqual(DEGRADATION_RULES["session.started"],
                         DegradationCategory.SILENT)
        self.assertEqual(DEGRADATION_RULES["thought.delta"],
                         DegradationCategory.DISCARD)
        self.assertEqual(DEGRADATION_RULES["tool_call.started"],
                         DegradationCategory.FOLD)
        self.assertEqual(DEGRADATION_RULES["run.state_changed"],
                         DegradationCategory.ON_FAILURE)

        # (c) Channel output policy enforcement
        from channel_core.output_policy import apply_output_policy
        decision = apply_output_policy("admin_notice: system check")
        self.assertEqual(decision.action, "block",
                         f"Channel output policy should block admin_notice: {decision.action}")

    # ------------------------------------------------------------------
    # 12. aggregate_events pure function
    # ------------------------------------------------------------------

    def test_aggregate_events_pure_function(self) -> None:
        """Call aggregate_events() twice with the same input and assert the
        results are identical (deterministic). Call with out-of-order events
        and assert the result is the same as in-order (seq sorting works)."""
        events_in_order = [
            {"event_type": "session.started", "seq": 1, "payload": {}},
            {"event_type": "tool_call.started", "seq": 2, "payload": {"tool": "search"}},
            {"event_type": "message.completed", "seq": 3, "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "seq": 4, "payload": {"status": "succeeded"}},
        ]
        events_out_of_order = [
            {"event_type": "run.state_changed", "seq": 4, "payload": {"status": "succeeded"}},
            {"event_type": "message.completed", "seq": 3, "payload": {"content": "done"}},
            {"event_type": "tool_call.started", "seq": 2, "payload": {"tool": "search"}},
            {"event_type": "session.started", "seq": 1, "payload": {}},
        ]
        # Deterministic: same input → same output
        result1 = aggregate_events(events_in_order)
        result2 = aggregate_events(events_in_order)
        self.assertEqual(result1, result2)
        # Order-independent: out-of-order → same result as in-order
        result3 = aggregate_events(events_out_of_order)
        self.assertEqual(result1, result3,
                         "aggregate_events should be order-independent (seq sorting)")


if __name__ == "__main__":
    unittest.main()
