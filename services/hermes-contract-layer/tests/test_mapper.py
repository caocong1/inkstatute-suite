from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from contract_test_suite.schema_validation import validate_event
from hermes_contract_layer.mapper import ASYNC_TASK_STATES, EVENT_KEYS, map_agent_end_context


FIXED_NOW = "2026-06-28T02:00:00Z"


def normal_context() -> dict[str, Any]:
    return {
        "platform": "wecom",
        "user_id": "lawyer-001",
        "chat_id": "chat-001",
        "session_id": "session-001",
        "message": "Review this synthetic contract clause.",
        "response": "Synthetic reviewed answer.",
        "message_id": "msg-001",
        "active_skill_name": "lawfirm.contract_review",
        "route_confidence": 0.91,
        "reply_type": "text",
    }


class MapperTests(unittest.TestCase):
    def test_maps_normal_post_filter_context_to_schema_valid_events(self) -> None:
        events = map_agent_end_context(normal_context(), now=FIXED_NOW)

        self.assertEqual(tuple(events), EVENT_KEYS)
        for event_key, event in events.items():
            validate_event(event_key, event, fixture_id="phase4-mapper-normal")

        turn = events["agent_turn"]
        route = events["route_decision"]
        trace = events["execution_trace"]
        result = events["agent_result"]

        self.assertEqual(route["turn_id"], turn["turn_id"])
        self.assertEqual(trace["turn_id"], turn["turn_id"])
        self.assertEqual(result["turn_id"], turn["turn_id"])
        self.assertEqual(trace["route_decision"]["route_decision_id"], route["route_decision_id"])
        self.assertEqual(result["metadata"]["trace_id"], trace["trace_id"])
        self.assertEqual(result["metadata"]["route_decision_id"], route["route_decision_id"])
        self.assertEqual(result["feedback_target"], "msg-001")
        self.assertEqual(route["mode"], "matched")
        self.assertTrue(trace["matched_registered_skill"])

    def test_missing_message_id_records_unavailable_feedback_target(self) -> None:
        context = normal_context()
        context.pop("message_id")
        context.pop("active_skill_name")

        events = map_agent_end_context(context, now=FIXED_NOW)
        result = events["agent_result"]
        route = events["route_decision"]
        trace = events["execution_trace"]

        for event_key, event in events.items():
            validate_event(event_key, event, fixture_id="phase4-mapper-missing-message")

        self.assertNotIn("feedback_target", result)
        self.assertEqual(result["metadata"]["feedback_target_source"], "unavailable")
        self.assertEqual(route["mode"], "simple_qa")
        self.assertIsNone(route["primary_skill"])
        self.assertFalse(trace["matched_registered_skill"])

    def test_zero_match_route_adds_human_review_skill_candidate(self) -> None:
        context = normal_context()
        context.pop("active_skill_name")
        context["route_mismatch"] = True
        context["skill_candidate_name"] = "lawfirm.unknown_task"

        events = map_agent_end_context(context, now=FIXED_NOW)
        route = events["route_decision"]
        result = events["agent_result"]

        for event_key, event in events.items():
            validate_event(event_key, event, fixture_id="phase4-mapper-zero-match")

        self.assertEqual(route["mode"], "zero_match")
        self.assertTrue(route["route_mismatch"])
        self.assertTrue(result["route_mismatch"])
        self.assertEqual(result["skill_candidate"]["source"], "route_mismatch")
        self.assertTrue(result["skill_candidate"]["requires_human_review"])
        self.assertTrue(result["skill_candidate"]["metadata"]["no_auto_modify"])

    def test_failed_status_preserves_exact_async_states_and_runtime_error(self) -> None:
        context = normal_context()
        context.update(
            {
                "status": "failed",
                "response": "Synthetic long task failed during artifact generation.",
                "error": {
                    "category": "runtime_error",
                    "code": "DOCUMENT_RENDERER_TIMEOUT",
                    "message": "Synthetic renderer timeout.",
                    "stage": "artifact_generation",
                    "retryable": True,
                },
                "async_states": [
                    "queued",
                    {"name": "skill_execution_started", "state": "running"},
                    {"name": "document_renderer_failed", "state": "failed"},
                    {"name": "ignored_vendor_state", "state": "timed_out"},
                ],
            }
        )

        events = map_agent_end_context(context, now=FIXED_NOW)
        trace = events["execution_trace"]
        result = events["agent_result"]

        for event_key, event in events.items():
            validate_event(event_key, event, fixture_id="phase4-mapper-failed")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reply_type"], "status_update")
        self.assertEqual(result["error"]["category"], "runtime_error")
        self.assertEqual(result["error"]["code"], "DOCUMENT_RENDERER_TIMEOUT")
        state_values = [step["state"] for step in trace["steps"] if "state" in step]
        self.assertEqual(state_values, ["queued", "running", "failed"])
        self.assertTrue(set(state_values).issubset(ASYNC_TASK_STATES))
        self.assertEqual(trace["steps"][-1]["skipped_unrecognized_states"], ["timed_out"])

    def test_events_use_reference_first_payload_metadata(self) -> None:
        events = map_agent_end_context(normal_context(), now=FIXED_NOW)

        for event in events.values():
            self.assert_no_raw_payload_key(event)
        self.assertTrue(events["agent_turn"]["metadata"]["raw_payload_ref"].startswith("hermes://"))
        self.assertTrue(events["agent_result"]["metadata"]["raw_payload_ref"].startswith("hermes://"))

    def assert_no_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, Mapping):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_raw_payload_key(child)


if __name__ == "__main__":
    unittest.main()
