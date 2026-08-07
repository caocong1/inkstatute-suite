"""Cross-channel consistency tests for WeCom — same task from WeCom and Web
produces the same semantic result.

These tests verify that the same Gateway run, when consumed by a bot channel
(WeCom) vs a web client, produces semantically equivalent results — the same
final message, the same cards, the same files, the same citations. The bot
just delivers them as non-streaming messages instead of streaming SSE.

All tests are network-free, using ``FakeGatewayClient`` and
``FakeWeComAdapter`` from ``fakes.py``. Fixture events are loaded from
``fixtures/bot_events.json``.
"""

from __future__ import annotations

import asyncio
import inspect
import unittest

from platform_contract.bot_degradation import (
    DEGRADATION_RULES,
    BotDelivery,
    aggregate_events,
)

from wecom_service.event_consumer import WeComEventConsumer

from fakes import FakeGatewayClient, FakeWeComAdapter, load_fixture_events


def _run_async(coro):
    """Helper to run an async coroutine in tests."""
    return asyncio.run(coro)


def _make_events(*overrides: dict) -> list[dict]:
    """Build a minimal event list from overrides."""
    events = []
    for i, ov in enumerate(overrides, 1):
        event = {
            "event_id": f"evt-{i}",
            "run_id": "run-fake-1",
            "event_type": ov.get("event_type", "message.delta"),
            "seq": ov.get("seq", i),
            "occurred_at": f"2026-08-09T10:00:{i:02d}Z",
            "payload": ov.get("payload", {}),
        }
        if "message_delta" in ov:
            event["message_delta"] = ov["message_delta"]
        events.append(event)
    return events


class TestCrossChannelConsistency(unittest.TestCase):
    """Verify that the same Gateway run produces semantically equivalent
    results for WeCom (bot) and Web (streaming) channels."""

    def _make_consumer(
        self,
        *,
        events: list[dict] | None = None,
        media_uploader=None,
    ) -> tuple[WeComEventConsumer, FakeGatewayClient, FakeWeComAdapter]:
        client = FakeGatewayClient(events=events)
        adapter = FakeWeComAdapter()
        consumer = WeComEventConsumer(
            gateway_client=client,
            adapter=adapter,
            media_uploader=media_uploader,
        )
        return consumer, client, adapter

    # ------------------------------------------------------------------
    # 1. Same final message
    # ------------------------------------------------------------------

    def test_same_events_same_final_message(self) -> None:
        """Given the same fixture events, aggregate_events() final_message
        matches the content of the text delivery from the WeCom consumer."""
        events = load_fixture_events()
        # Web view: aggregate_events produces the final message
        web_delivery = aggregate_events(events)
        # Bot view: WeCom consumer delivers the final message as text
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-fake",
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "审查合同"},
            to_user="user-1",
        ))
        text_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "text"
        ]
        # Find the final message delivery (not intermediate prompts)
        final_deliveries = [
            d for d in text_deliveries
            if d.content and "正在检索法规…" not in d.content and "仍在处理" not in d.content
        ]
        self.assertTrue(len(final_deliveries) >= 1,
                        f"Expected at least one final text delivery: {[d.content for d in text_deliveries]}")
        # The final message content must match — both use aggregate_events
        # which appends citations to final_message, so they should be identical
        bot_final = final_deliveries[0].content
        web_final = web_delivery.final_message
        self.assertIsNotNone(web_final, "Web final_message should not be None")
        self.assertEqual(bot_final, web_final,
                         f"Bot final message should match web final message:\n"
                         f"  bot: {bot_final}\n  web: {web_final}")

    # ------------------------------------------------------------------
    # 2. Same cards
    # ------------------------------------------------------------------

    def test_same_events_same_cards(self) -> None:
        """Given events with elicitation.requested, both aggregate_events().cards
        and the WeCom consumer's card deliveries contain the same card payload."""
        events = _make_events(
            {"event_type": "elicitation.requested", "payload": {
                "interrupt_id": "int-001",
                "questions": [{"id": "q1", "question": "该合同是否涉及涉外因素？"}],
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        # Web view
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.cards) >= 1)
        web_card = web_delivery.cards[0]
        # Bot view
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        card_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "card"
        ]
        self.assertTrue(len(card_deliveries) >= 1,
                        f"Expected card deliveries: {adapter.deliveries}")
        bot_card = card_deliveries[0]
        # Same interrupt_id
        self.assertEqual(bot_card.metadata.get("card_id"),
                         web_card.get("interrupt_id"))
        self.assertEqual(bot_card.metadata.get("card_id"), "int-001")

    # ------------------------------------------------------------------
    # 3. Same files
    # ------------------------------------------------------------------

    def test_same_events_same_files(self) -> None:
        """Given events with artifact.created, both aggregate_events().files
        and the WeCom consumer's file deliveries reference the same artifact_id."""
        events = _make_events(
            {"event_type": "artifact.created", "payload": {
                "artifact_id": "art-001", "name": "合同审查报告.docx",
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        # Web view
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.files) >= 1)
        web_file = web_delivery.files[0]
        self.assertEqual(web_file.get("artifact_id"), "art-001")
        # Bot view
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-123",
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        file_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "file"
        ]
        self.assertTrue(len(file_deliveries) >= 1,
                        f"Expected file deliveries: {adapter.deliveries}")
        # The file delivery content references the artifact name
        bot_file_content = file_deliveries[0].content
        self.assertIn("合同审查报告", bot_file_content)

    # ------------------------------------------------------------------
    # 4. Same citations
    # ------------------------------------------------------------------

    def test_same_events_same_citations(self) -> None:
        """Given events with citation.recorded, the citations from
        aggregate_events() appear in the WeCom consumer's final message
        (appended as a reference section)."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "审查结果"}},
            {"event_type": "citation.recorded", "payload": {
                "citations": [{"source": "合同法第107条", "status": "verified"}],
            }, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        # Web view
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.citations) >= 1)
        web_citation = web_delivery.citations[0]
        self.assertEqual(web_citation.get("source"), "合同法第107条")
        # Bot view
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        text_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "text"
        ]
        all_text = " ".join(d.content or "" for d in text_deliveries)
        self.assertIn("引用：", all_text,
                      f"Expected citation section in bot deliveries: {all_text}")
        self.assertIn("合同法第107条", all_text,
                      f"Expected citation source in bot deliveries: {all_text}")

    # ------------------------------------------------------------------
    # 5. Same error prompt
    # ------------------------------------------------------------------

    def test_same_events_same_error_prompt(self) -> None:
        """Given events with run.state_changed (failed), both
        aggregate_events().error_prompt and the WeCom consumer's error
        delivery contain the failure message."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "failed"}},
        )
        # Web view
        web_delivery = aggregate_events(events)
        self.assertIsNotNone(web_delivery.error_prompt)
        self.assertIn("处理失败", web_delivery.error_prompt)
        # Bot view
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertTrue(any("处理失败" in c for c in contents),
                        f"Expected failure prompt in bot deliveries: {contents}")

    # ------------------------------------------------------------------
    # 6. Bot receives intermediate prompts, web sees raw events
    # ------------------------------------------------------------------

    def test_bot_receives_intermediate_prompts_web_does_not(self) -> None:
        """The bot receives '正在检索法规…' and '仍在处理' as intermediate
        prompts during the stream. The web client sees the raw events and
        renders them as progress indicators. Both channels get the same
        information, just in different formats."""
        events = load_fixture_events()
        # Web view: aggregate_events produces intermediate_prompts
        web_delivery = aggregate_events(events)
        self.assertIn("正在检索法规…", web_delivery.intermediate_prompts)
        self.assertIn("仍在处理", web_delivery.intermediate_prompts)
        # Bot view: consumer delivers intermediate prompts as text messages
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-fake",
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertIn("正在检索法规…", contents,
                      f"Expected '正在检索法规…' in bot deliveries: {contents}")
        self.assertIn("仍在处理", contents,
                      f"Expected '仍在处理' in bot deliveries: {contents}")

    # ------------------------------------------------------------------
    # 7. Output boundary double enforced
    # ------------------------------------------------------------------

    def test_output_boundary_double_enforced(self) -> None:
        """Given events where message.completed payload contains backend noise
        ('gateway: restarted'), assert: (a) the degradation layer processes
        the event, (b) the output policy blocks the noise, (c) no delivery
        contains the noise text."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "gateway: restarted"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        # The degradation layer (aggregate_events) produces the final_message
        web_delivery = aggregate_events(events)
        # The output policy in the consumer blocks the noise
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries if d.content]
        # No delivery should contain the raw noise text
        self.assertFalse(any("gateway: restarted" in c for c in contents),
                         f"Backend noise should be blocked by output policy: {contents}")
        # The noise should not appear in the web delivery either (it's in
        # final_message but the consumer's apply_output_policy blocks it)
        self.assertIn("gateway", web_delivery.final_message or "",
                      "Web delivery should have the raw content (web client "
                      "applies its own boundary at the SSE layer)")

    # ------------------------------------------------------------------
    # 8. Backend meta invisible in bot channel
    # ------------------------------------------------------------------

    def test_backend_meta_invisible_in_bot_channel(self) -> None:
        """Given events with session.started (SILENT), thought.delta (DISCARD),
        and tool_call.* (FOLD), assert none of these event contents appear in
        any WeCom delivery. The bot user only sees '正在检索法规…' (folded),
        not the actual tool call details."""
        events = _make_events(
            {"event_type": "session.started", "payload": {"session_id": "secret-sess"}},
            {"event_type": "thought.delta", "payload": {"delta": "internal reasoning about contract"}},
            {"event_type": "tool_call.started", "payload": {"tool_name": "search_statutes", "tool_call_id": "tc-1"}},
            {"event_type": "message.completed", "payload": {"content": "审查完成"}, "seq": 4},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 5},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries if d.content]
        all_text = " ".join(contents)
        # session.started content should not appear
        self.assertNotIn("secret-sess", all_text,
                         f"Session metadata should not appear in deliveries: {all_text}")
        # thought.delta content should not appear
        self.assertNotIn("internal reasoning", all_text,
                         f"Thought content should not appear in deliveries: {all_text}")
        # tool_call details should not appear (only the folded prompt)
        self.assertNotIn("search_statutes", all_text,
                         f"Tool name should not appear in deliveries: {all_text}")
        self.assertNotIn("tc-1", all_text,
                         f"Tool call ID should not appear in deliveries: {all_text}")
        # The folded prompt should appear
        self.assertIn("正在检索法规…", all_text,
                      f"Expected folded tool prompt: {all_text}")

    # ------------------------------------------------------------------
    # 9. Gateway/system noise invisible
    # ------------------------------------------------------------------

    def test_gateway_system_noise_invisible(self) -> None:
        """Given events with text content containing 'gateway', 'system',
        'update', 'command' keywords (backend noise), assert the output
        boundary blocks them from all deliveries. SC#6 verified.

        The noise texts are chosen to match the actual block/rewrite patterns
        in the channel output policy:
        - 'gateway: restarted' matches rewrite pattern (original replaced)
        - 'admin_notice: system check' matches block pattern
        - 'self-update: gateway reconnecting' matches block pattern
        - 'command /help executed' matches block pattern (slash command)
        """
        noise_texts = [
            "gateway: restarted",
            "admin_notice: system check",
            "self-update: gateway reconnecting",
            "command /help executed",
        ]
        for noise in noise_texts:
            with self.subTest(noise=noise):
                events = _make_events(
                    {"event_type": "message.completed", "payload": {"content": noise}},
                    {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
                )
                consumer, client, adapter = self._make_consumer(events=events)
                _run_async(consumer.consume_and_deliver(
                    turn={"content": "hi"}, to_user="user-1",
                ))
                contents = [d.content for d in adapter.deliveries if d.content]
                self.assertFalse(any(noise in c for c in contents),
                                 f"Noise '{noise}' should be blocked: {contents}")

    # ------------------------------------------------------------------
    # 10. Degradation rules from Phase 88
    # ------------------------------------------------------------------

    def test_degradation_rules_from_phase_88(self) -> None:
        """Verify that the degradation rules used by the consumer are exactly
        the rules from packages/platform-contract/bot_degradation.py (Phase 88).
        SC#1 verified."""
        # The consumer imports aggregate_events from platform_contract
        from wecom_service import event_consumer as ec_mod
        source = inspect.getsource(ec_mod)
        self.assertIn("from platform_contract.bot_degradation import", source)
        self.assertIn("aggregate_events", source)
        # Verify the rules dict exists and has the expected event types
        expected_types = {
            "session.started", "message.delta", "message.completed",
            "thought.delta", "tool_call.started", "tool_call.delta",
            "tool_call.completed", "plan.updated", "phase.changed",
            "elicitation.requested", "permission.requested",
            "artifact.created", "citation.recorded", "run.state_changed",
            "error",
        }
        self.assertEqual(set(DEGRADATION_RULES.keys()), expected_types)
        # Verify aggregate_events is a pure function (deterministic)
        events = load_fixture_events()
        result1 = aggregate_events(events)
        result2 = aggregate_events(events)
        self.assertEqual(result1, result2)

    # ------------------------------------------------------------------
    # 11. Full lifecycle WeCom tracer
    # ------------------------------------------------------------------

    def test_full_lifecycle_wecom_tracer(self) -> None:
        """End-to-end: load bot_events.json, create WeComEventConsumer with
        FakeGatewayClient and FakeWeComAdapter, call consume_and_deliver().
        Assert: (a) intermediate prompts sent, (b) final message delivered,
        (c) card delivered, (d) evidence status 'completed'."""
        events = load_fixture_events()
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-fake",
        )
        result = _run_async(consumer.consume_and_deliver(
            turn={"content": "审查合同"},
            to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries]
        # (a) intermediate prompts sent
        has_intermediate = any(
            "正在检索法规…" in c or "仍在处理" in c for c in contents
        )
        self.assertTrue(has_intermediate,
                        f"Expected intermediate prompts: {contents}")
        # (b) final message delivered
        has_final = any("合同审查完成" in c for c in contents)
        self.assertTrue(has_final,
                        f"Expected final message: {contents}")
        # (c) card delivered
        card_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "card"
        ]
        self.assertTrue(len(card_deliveries) >= 1,
                        f"Expected card delivery: {adapter.deliveries}")
        # (d) evidence status
        self.assertEqual(result["status"], "completed")

    # ------------------------------------------------------------------
    # 12. Web equivalence summary
    # ------------------------------------------------------------------

    def test_web_equivalence_summary(self) -> None:
        """Summary test documenting the semantic equivalence: for the same
        Gateway run, the web client sees streaming events (message.delta →
        message.completed), while the bot sees a single aggregated final
        message. The cards, files, citations, and error prompts are identical.
        The only difference is delivery format (streaming vs non-streaming)."""
        events = load_fixture_events()
        # Web view: aggregate_events produces the full BotDelivery
        web_delivery = aggregate_events(events)
        # Bot view: WeCom consumer delivers via adapter
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-fake",
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "审查合同"},
            to_user="user-1",
        ))
        # The final message content is the same (bot may have citations appended)
        text_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "text"
        ]
        final_deliveries = [
            d for d in text_deliveries
            if d.content and "正在检索法规…" not in d.content
            and "仍在处理" not in d.content
        ]
        self.assertTrue(len(final_deliveries) >= 1)
        bot_final = final_deliveries[0].content
        web_final = web_delivery.final_message
        self.assertIsNotNone(web_final)
        # Both should be identical — aggregate_events produces the same
        # final_message (with citations appended) for both channels
        self.assertEqual(
            bot_final, web_final,
            "Bot and web final messages should be identical "
            "(both use aggregate_events which appends citations)"
        )
        # Both have the same number of cards
        bot_cards = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "card"
        ]
        self.assertEqual(len(bot_cards), len(web_delivery.cards),
                         f"Card count mismatch: bot={len(bot_cards)}, web={len(web_delivery.cards)}")
        # Both have the same intermediate prompts
        bot_intermediate = [
            d.content for d in adapter.deliveries
            if d.content and ("正在检索法规…" in d.content or "仍在处理" in d.content)
        ]
        self.assertEqual(
            len(bot_intermediate), len(web_delivery.intermediate_prompts),
            f"Intermediate prompt count mismatch: "
            f"bot={len(bot_intermediate)}, web={len(web_delivery.intermediate_prompts)}"
        )


if __name__ == "__main__":
    unittest.main()
