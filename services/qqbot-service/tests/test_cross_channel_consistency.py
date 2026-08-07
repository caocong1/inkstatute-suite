"""Cross-channel consistency tests for QQ bot — same task from QQ and Web
produces the same semantic result.

These tests verify that the same Gateway run, when consumed by a bot channel
(QQ) vs a web client, produces semantically equivalent results — the same
final message, the same cards, the same files, the same citations. The bot
just delivers them as non-streaming messages instead of streaming SSE.

All tests are network-free, using ``FakeGatewayClient`` and
``FakeQQBotAdapter`` from ``fakes.py``. Fixture events are loaded from
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

from qqbot_service.event_consumer import QQBotEventConsumer

from fakes import FakeGatewayClient, FakeQQBotAdapter, load_fixture_events


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


class TestQQCrossChannelConsistency(unittest.TestCase):
    """Verify that the same Gateway run produces semantically equivalent
    results for QQ (bot) and Web (streaming) channels."""

    def _make_consumer(
        self,
        *,
        events: list[dict] | None = None,
        media_uploader=None,
    ) -> tuple[QQBotEventConsumer, FakeGatewayClient, FakeQQBotAdapter]:
        client = FakeGatewayClient(events=events)
        adapter = FakeQQBotAdapter()
        consumer = QQBotEventConsumer(
            gateway_client=client,
            adapter=adapter,
            media_uploader=media_uploader,
        )
        return consumer, client, adapter

    def _consume(self, consumer, **kwargs):
        """Run consume_and_deliver with sensible defaults for QQ scene metadata."""
        defaults = {
            "turn": {"content": "审查合同"},
            "scene": "c2c",
            "user_openid": "user-1",
            "group_openid": None,
            "msg_id": "msg-001",
            "msg_seq": 1,
            "received_at": "2026-08-09T10:00:00Z",
        }
        defaults.update(kwargs)
        return _run_async(consumer.consume_and_deliver(**defaults))

    # ------------------------------------------------------------------
    # 1. Same final message
    # ------------------------------------------------------------------

    def test_same_events_same_final_message(self) -> None:
        """Given the same fixture events, aggregate_events() final_message
        matches the content of the text delivery from the QQ consumer."""
        events = load_fixture_events()
        web_delivery = aggregate_events(events)
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: {"file_info": "fake"},
        )
        self._consume(consumer)
        text_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "text"
        ]
        final_deliveries = [
            d for d in text_deliveries
            if d.content and "正在检索法规…" not in d.content and "仍在处理" not in d.content
        ]
        self.assertTrue(len(final_deliveries) >= 1,
                        f"Expected at least one final text delivery: {[d.content for d in text_deliveries]}")
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
        and the QQ consumer's card deliveries contain the same card payload."""
        events = _make_events(
            {"event_type": "elicitation.requested", "payload": {
                "interrupt_id": "int-001",
                "questions": [{"id": "q1", "question": "该合同是否涉及涉外因素？"}],
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.cards) >= 1)
        web_card = web_delivery.cards[0]
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer)
        card_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "card"
        ]
        self.assertTrue(len(card_deliveries) >= 1,
                        f"Expected card deliveries: {adapter.deliveries}")
        bot_card = card_deliveries[0]
        self.assertEqual(bot_card.metadata.get("card_id"),
                         web_card.get("interrupt_id"))
        self.assertEqual(bot_card.metadata.get("card_id"), "int-001")

    # ------------------------------------------------------------------
    # 3. Same files
    # ------------------------------------------------------------------

    def test_same_events_same_files(self) -> None:
        """Given events with artifact.created, both aggregate_events().files
        and the QQ consumer's file deliveries reference the same artifact_id."""
        events = _make_events(
            {"event_type": "artifact.created", "payload": {
                "artifact_id": "art-001", "name": "合同审查报告.docx",
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.files) >= 1)
        web_file = web_delivery.files[0]
        self.assertEqual(web_file.get("artifact_id"), "art-001")
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: {"file_info": "fake-123"},
        )
        self._consume(consumer)
        file_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "file"
        ]
        self.assertTrue(len(file_deliveries) >= 1,
                        f"Expected file deliveries: {adapter.deliveries}")
        bot_file_content = file_deliveries[0].content
        self.assertIn("合同审查报告", bot_file_content)

    # ------------------------------------------------------------------
    # 4. Same citations
    # ------------------------------------------------------------------

    def test_same_events_same_citations(self) -> None:
        """Given events with citation.recorded, the citations from
        aggregate_events() appear in the QQ consumer's final message
        (appended as a reference section)."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "审查结果"}},
            {"event_type": "citation.recorded", "payload": {
                "citations": [{"source": "合同法第107条", "status": "verified"}],
            }, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        web_delivery = aggregate_events(events)
        self.assertTrue(len(web_delivery.citations) >= 1)
        web_citation = web_delivery.citations[0]
        self.assertEqual(web_citation.get("source"), "合同法第107条")
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer)
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
        aggregate_events().error_prompt and the QQ consumer's error
        delivery contain the failure message."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "failed"}},
        )
        web_delivery = aggregate_events(events)
        self.assertIsNotNone(web_delivery.error_prompt)
        self.assertIn("处理失败", web_delivery.error_prompt)
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer)
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertTrue(any("处理失败" in c for c in contents),
                        f"Expected failure prompt in bot deliveries: {contents}")

    # ------------------------------------------------------------------
    # 6. Bot receives intermediate prompts, web sees raw events
    # ------------------------------------------------------------------

    def test_bot_receives_intermediate_prompts_web_does_not(self) -> None:
        """The bot receives '正在检索法规…' and '仍在处理' as intermediate
        prompts during the stream. The web client sees the raw events and
        renders them as progress indicators."""
        events = load_fixture_events()
        web_delivery = aggregate_events(events)
        self.assertIn("正在检索法规…", web_delivery.intermediate_prompts)
        self.assertIn("仍在处理", web_delivery.intermediate_prompts)
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: {"file_info": "fake"},
        )
        self._consume(consumer)
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
        ('gateway: restarted'), assert the output policy blocks the noise
        and no delivery contains the noise text."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "gateway: restarted"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        web_delivery = aggregate_events(events)
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer)
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertFalse(any("gateway: restarted" in c for c in contents),
                         f"Backend noise should be blocked by output policy: {contents}")
        self.assertIn("gateway", web_delivery.final_message or "",
                      "Web delivery should have the raw content (web client "
                      "applies its own boundary at the SSE layer)")

    # ------------------------------------------------------------------
    # 8. Backend meta invisible in bot channel
    # ------------------------------------------------------------------

    def test_backend_meta_invisible_in_bot_channel(self) -> None:
        """Given events with session.started (SILENT), thought.delta (DISCARD),
        and tool_call.* (FOLD), assert none of these event contents appear in
        any QQ delivery. The bot user only sees '正在检索法规…' (folded)."""
        events = _make_events(
            {"event_type": "session.started", "payload": {"session_id": "secret-sess"}},
            {"event_type": "thought.delta", "payload": {"delta": "internal reasoning about contract"}},
            {"event_type": "tool_call.started", "payload": {"tool_name": "search_statutes", "tool_call_id": "tc-1"}},
            {"event_type": "message.completed", "payload": {"content": "审查完成"}, "seq": 4},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 5},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer)
        contents = [d.content for d in adapter.deliveries if d.content]
        all_text = " ".join(contents)
        self.assertNotIn("secret-sess", all_text,
                         f"Session metadata should not appear in deliveries: {all_text}")
        self.assertNotIn("internal reasoning", all_text,
                         f"Thought content should not appear in deliveries: {all_text}")
        self.assertNotIn("search_statutes", all_text,
                         f"Tool name should not appear in deliveries: {all_text}")
        self.assertNotIn("tc-1", all_text,
                         f"Tool call ID should not appear in deliveries: {all_text}")
        self.assertIn("正在检索法规…", all_text,
                      f"Expected folded tool prompt: {all_text}")

    # ------------------------------------------------------------------
    # 9. Gateway/system noise invisible
    # ------------------------------------------------------------------

    def test_gateway_system_noise_invisible(self) -> None:
        """Given events with text content containing backend noise keywords,
        assert the output boundary blocks them from all deliveries. SC#6 verified.

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
                self._consume(consumer)
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
        from qqbot_service import event_consumer as ec_mod
        source = inspect.getsource(ec_mod)
        self.assertIn("from platform_contract.bot_degradation import", source)
        self.assertIn("aggregate_events", source)
        expected_types = {
            "session.started", "message.delta", "message.completed",
            "thought.delta", "tool_call.started", "tool_call.delta",
            "tool_call.completed", "plan.updated", "phase.changed",
            "elicitation.requested", "permission.requested",
            "artifact.created", "citation.recorded", "run.state_changed",
            "error",
        }
        self.assertEqual(set(DEGRADATION_RULES.keys()), expected_types)
        events = load_fixture_events()
        result1 = aggregate_events(events)
        result2 = aggregate_events(events)
        self.assertEqual(result1, result2)

    # ------------------------------------------------------------------
    # 11. Full lifecycle QQ tracer
    # ------------------------------------------------------------------

    def test_full_lifecycle_qq_tracer(self) -> None:
        """End-to-end: load bot_events.json, create QQBotEventConsumer with
        FakeGatewayClient and FakeQQBotAdapter, call consume_and_deliver().
        Assert: (a) intermediate prompts sent, (b) final message delivered,
        (c) card delivered, (d) evidence status 'completed'."""
        events = load_fixture_events()
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: {"file_info": "fake"},
        )
        result = self._consume(consumer)
        contents = [d.content for d in adapter.deliveries]
        has_intermediate = any(
            "正在检索法规…" in c or "仍在处理" in c for c in contents
        )
        self.assertTrue(has_intermediate,
                        f"Expected intermediate prompts: {contents}")
        has_final = any("合同审查完成" in c for c in contents)
        self.assertTrue(has_final,
                        f"Expected final message: {contents}")
        card_deliveries = [
            d for d in adapter.deliveries
            if d.metadata.get("delivery_type") == "card"
        ]
        self.assertTrue(len(card_deliveries) >= 1,
                        f"Expected card delivery: {adapter.deliveries}")
        self.assertEqual(result["status"], "completed")

    # ------------------------------------------------------------------
    # 12. QQ scene metadata in deliveries
    # ------------------------------------------------------------------

    def test_qq_scene_metadata_in_deliveries(self) -> None:
        """QQ deliveries include scene (c2c/group), user_openid, msg_id."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        self._consume(consumer, scene="c2c", user_openid="qq-user-123",
                      msg_id="msg-999", msg_seq=5)
        for delivery in adapter.deliveries:
            meta = delivery.metadata
            self.assertEqual(meta.get("scene"), "c2c",
                             f"Delivery metadata should have scene=c2c: {meta}")
            self.assertEqual(meta.get("user_openid"), "qq-user-123",
                             f"Delivery metadata should have user_openid: {meta}")
            self.assertEqual(meta.get("msg_id"), "msg-999",
                             f"Delivery metadata should have msg_id: {meta}")

    # ------------------------------------------------------------------
    # 13. No WeCom import in consistency tests
    # ------------------------------------------------------------------

    def test_no_wecom_import_in_consistency_tests(self) -> None:
        """Verify no WeCom imports in the QQ event consumer module."""
        # Check the event consumer module — no WeCom cross-contamination
        from qqbot_service import event_consumer as ec_mod
        ec_source = inspect.getsource(ec_mod)
        self.assertNotIn("wecom_service", ec_source.lower())
        self.assertNotIn("WeComEventConsumer", ec_source)
        self.assertNotIn("from wecom", ec_source.lower())
        self.assertNotIn("import wecom", ec_source.lower())


if __name__ == "__main__":
    unittest.main()
