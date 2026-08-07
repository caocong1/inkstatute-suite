"""End-to-end tracer tests for the WeCom event consumer + degradation + delivery mapping.

All tests are network-free, using ``FakeGatewayClient`` and
``FakeWeComAdapter`` from ``fakes.py``. Fixture events are loaded from
``fixtures/bot_events.json``.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import unittest
from pathlib import Path

from platform_contract.bot_degradation import aggregate_events
from platform_runtime.protocols import ChannelDelivery

from wecom_service.event_consumer import (
    WeComEventConsumer,
    is_terminal_event,
    solution_to_dict,
)

from fakes import FakeGatewayClient, FakeWeComAdapter, load_fixture_events


def _run_async(coro):
    """Helper to run an async coroutine in tests."""
    return asyncio.run(coro)


def _make_events(*overrides: dict) -> list[dict]:
    """Build a minimal event list from overrides.

    Each override is a dict with at least ``event_type`` and ``seq``.
    """
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


class TestWeComEventConsumer(unittest.TestCase):
    """Integration tests for ``WeComEventConsumer`` — full consumption path."""

    def _make_consumer(
        self,
        *,
        events: list[dict] | None = None,
        media_uploader=None,
        progress_interval_seconds: float = 180.0,
    ) -> tuple[WeComEventConsumer, FakeGatewayClient, FakeWeComAdapter]:
        """Create a consumer with fake deps for testing."""
        client = FakeGatewayClient(events=events)
        adapter = FakeWeComAdapter()
        consumer = WeComEventConsumer(
            gateway_client=client,
            adapter=adapter,
            media_uploader=media_uploader,
            progress_interval_seconds=progress_interval_seconds,
        )
        return consumer, client, adapter

    # ------------------------------------------------------------------
    # 1. Final message delivery
    # ------------------------------------------------------------------

    def test_consume_and_deliver_final_message(self) -> None:
        """Final message from message.completed is delivered as text."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "合同审查完成"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        result = _run_async(consumer.consume_and_deliver(
            turn={"content": "审查合同"},
            to_user="user-1",
        ))
        text_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "text"]
        contents = [d.content for d in text_deliveries]
        self.assertTrue(any("合同审查完成" in c for c in contents),
                        f"Expected '合同审查完成' in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 2. Intermediate tool prompt
    # ------------------------------------------------------------------

    def test_consume_and_deliver_intermediate_tool_prompt(self) -> None:
        """Tool call events produce '正在检索法规…' intermediate prompt."""
        events = _make_events(
            {"event_type": "tool_call.started", "payload": {"tool_name": "search"}},
            {"event_type": "message.completed", "payload": {"content": "done"}, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries]
        self.assertIn("正在检索法规…", contents,
                      f"Expected '正在检索法规…' in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 3. Intermediate plan prompt
    # ------------------------------------------------------------------

    def test_consume_and_deliver_intermediate_plan_prompt(self) -> None:
        """Plan.updated events produce '仍在处理' intermediate prompt."""
        events = _make_events(
            {"event_type": "plan.updated", "payload": {"plan": []}},
            {"event_type": "message.completed", "payload": {"content": "done"}, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries]
        self.assertIn("仍在处理", contents,
                      f"Expected '仍在处理' in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 4. Card delivery
    # ------------------------------------------------------------------

    def test_consume_and_deliver_card(self) -> None:
        """Elicitation.requested maps to WeCom template card delivery."""
        events = _make_events(
            {"event_type": "elicitation.requested", "payload": {
                "interrupt_id": "int-1",
                "questions": [{"id": "q1", "question": "What?"}],
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        card_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "card"]
        self.assertTrue(len(card_deliveries) >= 1, f"Expected at least 1 card delivery, got {len(card_deliveries)}")
        card = card_deliveries[0]
        self.assertEqual(card.metadata.get("card_id"), "int-1")
        self.assertEqual(card.metadata.get("feedback_target"), "int-1")

    # ------------------------------------------------------------------
    # 5. File delivery with media_uploader
    # ------------------------------------------------------------------

    def test_consume_and_deliver_file_with_media_uploader(self) -> None:
        """Artifact.created with media_uploader delivers a file."""
        events = _make_events(
            {"event_type": "artifact.created", "payload": {
                "artifact_id": "art-1", "name": "doc.docx",
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-123",
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        file_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "file"]
        self.assertTrue(len(file_deliveries) >= 1, f"Expected file delivery, got {len(file_deliveries)}")
        self.assertEqual(file_deliveries[0].metadata.get("media_id"), "media-123")

    # ------------------------------------------------------------------
    # 6. File delivery without media_uploader (skip)
    # ------------------------------------------------------------------

    def test_consume_and_deliver_file_without_media_uploader(self) -> None:
        """Artifact.created without media_uploader skips file delivery."""
        events = _make_events(
            {"event_type": "artifact.created", "payload": {
                "artifact_id": "art-1", "name": "doc.docx",
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events, media_uploader=None)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        file_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "file"]
        self.assertEqual(len(file_deliveries), 0, f"Expected no file deliveries, got {len(file_deliveries)}")

    # ------------------------------------------------------------------
    # 7. Error prompt on failure
    # ------------------------------------------------------------------

    def test_consume_and_deliver_error_prompt(self) -> None:
        """run.state_changed with status=failed delivers error message."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "failed"}},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries]
        self.assertIn("处理失败，请稍后重试或联系管理员", contents,
                      f"Expected failure prompt in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 8. Citations appended to final message
    # ------------------------------------------------------------------

    def test_consume_and_deliver_citations_appended(self) -> None:
        """Citation.recorded events append a reference section to final message."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "审查结果"}},
            {"event_type": "citation.recorded", "payload": {
                "citations": [{"source": "合同法第107条", "status": "verified"}],
            }, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        text_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "text"]
        final_contents = [d.content for d in text_deliveries]
        found = any("引用：" in c for c in final_contents)
        self.assertTrue(found, f"Expected '引用：' section in final message: {final_contents}")

    # ------------------------------------------------------------------
    # 9. Session reuse
    # ------------------------------------------------------------------

    def test_consume_and_deliver_session_reuse(self) -> None:
        """When session_id is provided, create_session is NOT called."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1", session_id="existing-sess",
        ))
        self.assertFalse(client.create_session_called, "create_session should NOT be called when session_id provided")

    def test_consume_and_deliver_session_creation_when_none(self) -> None:
        """When session_id is None, create_session IS called."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1", conversation_id="conv-1",
        ))
        self.assertTrue(client.create_session_called, "create_session should be called when session_id is None")

    # ------------------------------------------------------------------
    # 10. Evidence dict
    # ------------------------------------------------------------------

    def test_consume_and_deliver_evidence_dict(self) -> None:
        """Returned evidence dict has correct structure."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        result = _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["run_id"], "run_id should be non-empty")
        self.assertEqual(result["delivery_count"], len(adapter.deliveries))
        self.assertTrue(result["delivered"])

    # ------------------------------------------------------------------
    # 11. Thought.delta discarded
    # ------------------------------------------------------------------

    def test_consume_and_deliver_thought_delta_discarded(self) -> None:
        """thought.delta events are discarded by the degradation layer."""
        events = _make_events(
            {"event_type": "thought.delta", "payload": {"delta": "internal reasoning"}},
            {"event_type": "message.completed", "payload": {"content": "visible reply"}, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries]
        self.assertFalse(any("internal reasoning" in c for c in contents),
                         f"Thought content should not appear in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 12. session.started silent
    # ------------------------------------------------------------------

    def test_consume_and_deliver_session_started_silent(self) -> None:
        """session.started events are silent — no delivery produced for them."""
        events = _make_events(
            {"event_type": "session.started", "payload": {"session_id": "s1"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        # No deliveries should mention session_id from the event
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertFalse(any("s1" == c for c in contents),
                         f"Session.started payload should not appear in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 13. Output boundary double enforced
    # ------------------------------------------------------------------

    def test_consume_and_deliver_output_boundary_double_enforced(self) -> None:
        """Backend noise in message.completed is blocked by output policy."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "gateway: restarted"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        contents = [d.content for d in adapter.deliveries if d.content]
        self.assertFalse(any("gateway: restarted" in c for c in contents),
                         f"Backend noise should be blocked: {contents}")

    # ------------------------------------------------------------------
    # 14. Full lifecycle end-to-end
    # ------------------------------------------------------------------

    def test_consume_and_deliver_full_lifecycle(self) -> None:
        """End-to-end tracer: load fixture, consume, verify all delivery types."""
        events = load_fixture_events()
        consumer, client, adapter = self._make_consumer(
            events=events,
            media_uploader=lambda name, data: "media-fake",
        )
        result = _run_async(consumer.consume_and_deliver(
            turn={"content": "审查合同"},
            to_user="user-1",
        ))

        # (a) at least one intermediate prompt was sent
        contents = [d.content for d in adapter.deliveries]
        has_intermediate = any("正在检索法规…" in c or "仍在处理" in c for c in contents)
        self.assertTrue(has_intermediate, f"Expected intermediate prompt: {contents}")

        # (b) a final message was delivered
        has_final = any("合同审查完成" in c for c in contents)
        self.assertTrue(has_final, f"Expected final message: {contents}")

        # (c) a card was delivered (from elicitation)
        card_deliveries = [d for d in adapter.deliveries if d.metadata.get("delivery_type") == "card"]
        self.assertTrue(len(card_deliveries) >= 1, f"Expected card delivery: {adapter.deliveries}")

        # (d) evidence status is "completed"
        self.assertEqual(result["status"], "completed")

    # ------------------------------------------------------------------
    # 15. No direct agent calls (BOT-02 compliance)
    # ------------------------------------------------------------------

    def test_consume_and_deliver_no_direct_agent_calls(self) -> None:
        """event_consumer.py does not import or call direct agent/backend APIs."""
        from wecom_service import event_consumer as ec_mod
        source = inspect.getsource(ec_mod)
        self.assertNotIn("from platform_runtime.runtime", source)
        self.assertNotIn("runtime.create_run", source)
        self.assertNotIn("backend.get_run", source)
        self.assertNotIn("DefaultRunRuntime", source)
        self.assertNotIn("BackendAdapter", source)

    # ------------------------------------------------------------------
    # 16. aggregate_events integration
    # ------------------------------------------------------------------

    def test_aggregate_events_integration(self) -> None:
        """aggregate_events() with fixture events produces correct BotDelivery."""
        events = load_fixture_events()
        delivery = aggregate_events(events)
        self.assertIsNotNone(delivery.final_message)
        self.assertIn("正在检索法规…", delivery.intermediate_prompts)
        self.assertIn("仍在处理", delivery.intermediate_prompts)
        self.assertTrue(len(delivery.cards) >= 1, f"Expected cards: {delivery.cards}")
        self.assertTrue(len(delivery.files) >= 1, f"Expected files: {delivery.files}")
        self.assertTrue(delivery.delivered)

    # ------------------------------------------------------------------
    # 17. Progress interval
    # ------------------------------------------------------------------

    def test_consume_and_deliver_progress_interval(self) -> None:
        """Additional '仍在处理' prompts sent at progress_interval_seconds intervals."""
        # Create events with many plan.updated events to trigger progress
        events = _make_events(
            {"event_type": "plan.updated", "payload": {"plan": []}},
            {"event_type": "message.completed", "payload": {"content": "done"}, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        consumer, client, adapter = self._make_consumer(
            events=events,
            progress_interval_seconds=0.1,
        )
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        # At least one "仍在处理" should be sent (from the first plan.updated)
        contents = [d.content for d in adapter.deliveries]
        self.assertIn("仍在处理", contents, f"Expected progress prompt: {contents}")

    # ------------------------------------------------------------------
    # 18. Idempotent delivery IDs
    # ------------------------------------------------------------------

    def test_consume_and_deliver_idempotent_delivery_ids(self) -> None:
        """Delivery IDs follow the pattern wecom-deliv-{run_id}-{index}."""
        events = _make_events(
            {"event_type": "plan.updated", "payload": {"plan": []}},
            {"event_type": "tool_call.started", "payload": {"tool_name": "search"}, "seq": 2},
            {"event_type": "message.completed", "payload": {"content": "done"}, "seq": 3},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 4},
        )
        consumer, client, adapter = self._make_consumer(events=events)
        _run_async(consumer.consume_and_deliver(
            turn={"content": "hi"}, to_user="user-1",
        ))
        for i, delivery in enumerate(adapter.deliveries):
            expected_id = f"wecom-deliv-run-fake-1-{i}"
            self.assertEqual(
                delivery.delivery_id, expected_id,
                f"Delivery {i} ID should be {expected_id}, got {delivery.delivery_id}",
            )


if __name__ == "__main__":
    unittest.main()
