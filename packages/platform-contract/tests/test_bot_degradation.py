"""Tests for the bot degradation aggregator — deterministic golden fixtures.

Covers all 8 degradation categories, determinism, out-of-order handling,
and full lifecycle scenarios per V3-PRD §3.2 and Plan 88-05.
"""

import unittest

from platform_contract import (
    BotDelivery,
    DEGRADATION_RULES,
    DegradationCategory,
    aggregate_events,
    get_degradation_category,
)
from platform_contract.enums import RunEventType


class BotDegradationTests(unittest.TestCase):

    # 1. Empty events produce empty delivery
    def test_empty_events_produce_empty_delivery(self):
        result = aggregate_events([])
        self.assertEqual(
            result,
            BotDelivery(
                final_message=None,
                intermediate_prompts=[],
                cards=[],
                files=[],
                citations=[],
                error_prompt=None,
                delivered=False,
            ),
        )

    # 2. Silent events (session.started) are dropped
    def test_silent_events_dropped(self):
        events = [
            {"seq": 0, "event_type": "session.started", "payload": {"backend_id": "hermes"}},
        ]
        result = aggregate_events(events)
        self.assertFalse(result.delivered)
        self.assertIsNone(result.final_message)
        self.assertEqual(result.intermediate_prompts, [])

    # 3. Buffer then deliver (message.delta → message.completed)
    def test_buffer_then_deliver(self):
        events = [
            {"seq": 0, "event_type": "message.delta", "message_delta": "Hello "},
            {"seq": 1, "event_type": "message.delta", "message_delta": "World"},
            {"seq": 2, "event_type": "message.completed", "payload": {"content": "Hello World"}},
        ]
        result = aggregate_events(events)
        self.assertTrue(result.delivered)
        self.assertEqual(result.final_message, "Hello World")

    # 3b. Buffer accumulates and delivers buffered content when no explicit content
    def test_buffer_delivers_buffered_deltas_when_no_content(self):
        events = [
            {"seq": 0, "event_type": "message.delta", "message_delta": "A"},
            {"seq": 1, "event_type": "message.delta", "message_delta": "B"},
            {"seq": 2, "event_type": "message.completed", "payload": {}},
        ]
        result = aggregate_events(events)
        self.assertTrue(result.delivered)
        self.assertEqual(result.final_message, "AB")

    # 4. thought.delta events are discarded
    def test_thought_delta_discarded(self):
        events = [
            {"seq": 0, "event_type": "thought.delta", "payload": {"delta": "thinking..."}},
            {"seq": 1, "event_type": "message.completed", "payload": {"content": "Done"}},
        ]
        result = aggregate_events(events)
        self.assertEqual(result.final_message, "Done")
        self.assertEqual(result.intermediate_prompts, [])
        self.assertEqual(result.cards, [])
        self.assertEqual(result.files, [])
        self.assertEqual(result.citations, [])

    # 5. tool_call events are folded to a single business prompt
    def test_tool_call_folded_to_business_prompt(self):
        events = [
            {"seq": 0, "event_type": "tool_call.started", "payload": {"tool_call_id": "t1", "tool_name": "search"}},
            {"seq": 1, "event_type": "tool_call.delta", "payload": {"tool_call_id": "t1"}},
            {"seq": 2, "event_type": "tool_call.completed", "payload": {"tool_call_id": "t1", "status": "completed"}},
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.intermediate_prompts), 1)
        self.assertIn("正在检索", result.intermediate_prompts[0])

    # 6. plan.updated: first occurrence delivered, subsequent silent
    def test_plan_updated_first_then_silent(self):
        events = [
            {"seq": 0, "event_type": "plan.updated", "payload": {"plan": []}},
            {"seq": 1, "event_type": "plan.updated", "payload": {"plan": [{"step": 2}]}},
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.intermediate_prompts), 1)

    # 7. phase.changed: first occurrence delivered, subsequent silent
    def test_phase_changed_first_then_silent(self):
        events = [
            {"seq": 0, "event_type": "phase.changed", "payload": {"phase": "retrieval"}},
            {"seq": 1, "event_type": "phase.changed", "payload": {"phase": "draft"}},
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.intermediate_prompts), 1)

    # 8. elicitation.requested delivered as card
    def test_elicitation_delivered_as_card(self):
        events = [
            {
                "seq": 0,
                "event_type": "elicitation.requested",
                "payload": {
                    "interrupt_id": "i1",
                    "intro": "请确认",
                    "questions": [{"id": "q1", "question": "test"}],
                },
            },
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.cards), 1)
        self.assertEqual(result.cards[0]["interrupt_id"], "i1")
        self.assertTrue(result.delivered)

    # 9. permission.requested delivered as card
    def test_permission_delivered_as_card(self):
        events = [
            {
                "seq": 0,
                "event_type": "permission.requested",
                "payload": {
                    "permission_id": "p1",
                    "tool_call_id": "t1",
                    "description": "approve search",
                },
            },
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.cards), 1)
        self.assertTrue(result.delivered)

    # 10. artifact.created delivered as file
    def test_artifact_delivered_as_file(self):
        events = [
            {
                "seq": 0,
                "event_type": "artifact.created",
                "payload": {
                    "artifact": {
                        "artifact_id": "a1",
                        "kind": "docx",
                        "name": "review.docx",
                        "uri": "file://a1",
                    }
                },
            },
        ]
        result = aggregate_events(events)
        self.assertEqual(len(result.files), 1)
        self.assertTrue(result.delivered)

    # 11. citation.recorded attached to final message
    def test_citation_attached_to_final_message(self):
        events = [
            {"seq": 0, "event_type": "message.completed", "payload": {"content": "Answer"}},
            {
                "seq": 1,
                "event_type": "citation.recorded",
                "payload": {"citations": [{"source": "民法典第1条", "status": "verified"}]},
            },
        ]
        result = aggregate_events(events)
        self.assertIsNotNone(result.final_message)
        self.assertTrue(len(result.citations) > 0)
        self.assertIn("引用", result.final_message)
        self.assertIn("民法典第1条", result.final_message)

    # 12. run.state_changed with failed status delivers error prompt
    def test_run_state_changed_failure_delivers_error_prompt(self):
        events = [
            {"seq": 0, "event_type": "run.state_changed", "payload": {"status": "failed"}},
        ]
        result = aggregate_events(events)
        self.assertIsNotNone(result.error_prompt)
        self.assertTrue(result.delivered)

    # 13. error event delivers error prompt
    def test_error_event_delivers_error_prompt(self):
        events = [
            {"seq": 0, "event_type": "error", "error": {"category": "runtime_error", "message": "timeout"}},
        ]
        result = aggregate_events(events)
        self.assertIsNotNone(result.error_prompt)
        self.assertTrue(result.delivered)

    # 14. run.state_changed with succeeded status does NOT deliver
    def test_run_state_changed_success_no_delivery(self):
        events = [
            {"seq": 0, "event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        ]
        result = aggregate_events(events)
        self.assertIsNone(result.error_prompt)
        self.assertFalse(result.delivered)

    # 15. Deterministic output: same input → same output
    def test_deterministic_output_same_input_same_output(self):
        events = [
            {"seq": 0, "event_type": "session.started", "payload": {"backend_id": "hermes"}},
            {"seq": 1, "event_type": "thought.delta", "payload": {"delta": "thinking"}},
            {"seq": 2, "event_type": "tool_call.started", "payload": {"tool_call_id": "t1", "tool_name": "search"}},
            {"seq": 3, "event_type": "tool_call.delta", "payload": {"tool_call_id": "t1"}},
            {"seq": 4, "event_type": "tool_call.completed", "payload": {"tool_call_id": "t1", "status": "completed"}},
            {"seq": 5, "event_type": "plan.updated", "payload": {"plan": []}},
            {"seq": 6, "event_type": "phase.changed", "payload": {"phase": "retrieval"}},
            {"seq": 7, "event_type": "message.delta", "message_delta": "Hello "},
            {"seq": 8, "event_type": "message.delta", "message_delta": "World"},
            {"seq": 9, "event_type": "message.completed", "payload": {"content": "Hello World"}},
            {
                "seq": 10,
                "event_type": "citation.recorded",
                "payload": {"citations": [{"source": "民法典", "status": "verified"}]},
            },
            {"seq": 11, "event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        ]
        result1 = aggregate_events(events)
        result2 = aggregate_events(events)
        self.assertEqual(result1, result2)
        # Verify the result has expected content
        self.assertTrue(result1.delivered)
        self.assertEqual(result1.final_message.split("\n")[0], "Hello World")
        self.assertEqual(len(result1.intermediate_prompts), 2)  # tool_call fold + plan/phase first
        self.assertIsNone(result1.error_prompt)

    # 16. Out-of-order events sorted by seq
    def test_out_of_order_events_sorted_by_seq(self):
        events = [
            {"seq": 2, "event_type": "message.completed", "payload": {"content": "AB"}},
            {"seq": 0, "event_type": "message.delta", "message_delta": "A"},
            {"seq": 1, "event_type": "message.delta", "message_delta": "B"},
        ]
        result = aggregate_events(events)
        self.assertEqual(result.final_message, "AB")

    # 17. Full lifecycle scenario
    def test_full_lifecycle_scenario(self):
        events = [
            {"seq": 0, "event_type": "session.started", "payload": {"backend_id": "hermes"}},
            {"seq": 1, "event_type": "thought.delta", "payload": {"delta": "analyzing"}},
            {"seq": 2, "event_type": "tool_call.started", "payload": {"tool_call_id": "t1", "tool_name": "search"}},
            {"seq": 3, "event_type": "tool_call.completed", "payload": {"tool_call_id": "t1", "status": "completed"}},
            {"seq": 4, "event_type": "message.delta", "message_delta": "The "},
            {"seq": 5, "event_type": "message.delta", "message_delta": "answer "},
            {"seq": 6, "event_type": "message.delta", "message_delta": "is 42"},
            {"seq": 7, "event_type": "message.completed", "payload": {"content": "The answer is 42"}},
            {
                "seq": 8,
                "event_type": "citation.recorded",
                "payload": {"citations": [{"source": "民法典第2条", "status": "retrieved"}]},
            },
            {"seq": 9, "event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        ]
        result = aggregate_events(events)
        self.assertIsNotNone(result.final_message)
        self.assertEqual(len(result.intermediate_prompts), 1)  # from tool_call fold
        self.assertTrue(len(result.citations) > 0)
        self.assertIsNone(result.error_prompt)  # success
        self.assertTrue(result.delivered)

    # 18. get_degradation_category returns None for V2 types
    def test_get_degradation_category_returns_none_for_v2_types(self):
        self.assertIsNone(get_degradation_category("state_changed"))
        self.assertIsNone(get_degradation_category("step_started"))

    # 19. All 15 V3 event type values have degradation rules
    def test_all_13_categories_have_degradation_rules(self):
        v3_values = [
            RunEventType.SESSION_STARTED.value,
            RunEventType.MESSAGE_DELTA_V3.value,
            RunEventType.MESSAGE_COMPLETED.value,
            RunEventType.THOUGHT_DELTA.value,
            RunEventType.TOOL_CALL_STARTED_V3.value,
            RunEventType.TOOL_CALL_DELTA.value,
            RunEventType.TOOL_CALL_COMPLETED_V3.value,
            RunEventType.PLAN_UPDATED.value,
            RunEventType.PHASE_CHANGED.value,
            RunEventType.ELICITATION_REQUESTED.value,
            RunEventType.PERMISSION_REQUESTED.value,
            RunEventType.ARTIFACT_CREATED_V3.value,
            RunEventType.CITATION_RECORDED.value,
            RunEventType.RUN_STATE_CHANGED.value,
            RunEventType.ERROR.value,
        ]
        for value in v3_values:
            self.assertIn(
                value,
                DEGRADATION_RULES,
                f"V3 event type {value!r} missing from DEGRADATION_RULES",
            )


if __name__ == "__main__":
    unittest.main()
