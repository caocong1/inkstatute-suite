"""Tests for the clarification (ask_user) tool.

Covers: valid 2-question elicitation, valid 4-question elicitation,
invalid 1-question (error), invalid 5-question (error), auto-assigned IDs,
auto-filled values, free-text questions (no options), emit event verification,
terminate_turn metadata.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import RunEventType
from platform_contract.unified_events import ElicitationQuestion

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.tools.clarification import (
    CLARIFICATION_TOOL_DEFINITION,
    create_clarification_tool,
)
from inkstatute_agent_core.turn_loop import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_emitter(run_id: str = "run-clarify") -> EventEmitter:
    return EventEmitter(run_id, AgentCoreConfig())


def _run_handler(handler, arguments: dict) -> ToolResult:
    return asyncio.run(handler(arguments))


# ---------------------------------------------------------------------------
# CLARIFICATION_TOOL_DEFINITION tests
# ---------------------------------------------------------------------------


class TestClarificationToolDefinition(unittest.TestCase):
    """CLARIFICATION_TOOL_DEFINITION is a valid OpenAI function-calling format dict."""

    def test_definition_has_type_function(self):
        self.assertEqual(CLARIFICATION_TOOL_DEFINITION["type"], "function")

    def test_definition_has_name_ask_user(self):
        self.assertEqual(CLARIFICATION_TOOL_DEFINITION["function"]["name"], "ask_user")

    def test_definition_has_description(self):
        self.assertIn("description", CLARIFICATION_TOOL_DEFINITION["function"])
        self.assertTrue(len(CLARIFICATION_TOOL_DEFINITION["function"]["description"]) > 0)

    def test_definition_has_parameters(self):
        params = CLARIFICATION_TOOL_DEFINITION["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("intro", params["properties"])
        self.assertIn("questions", params["properties"])
        self.assertIn("intro", params["required"])
        self.assertIn("questions", params["required"])

    def test_definition_questions_min_max_items(self):
        params = CLARIFICATION_TOOL_DEFINITION["function"]["parameters"]
        questions_prop = params["properties"]["questions"]
        self.assertEqual(questions_prop["minItems"], 2)
        self.assertEqual(questions_prop["maxItems"], 4)


# ---------------------------------------------------------------------------
# create_clarification_tool tests
# ---------------------------------------------------------------------------


class TestCreateClarificationTool(unittest.TestCase):
    """create_clarification_tool returns a ToolHandler callable."""

    def test_returns_callable(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)
        self.assertTrue(callable(handler))

    def test_handler_is_async(self):
        import inspect
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)
        self.assertTrue(inspect.iscoroutinefunction(handler))


# ---------------------------------------------------------------------------
# Valid elicitation tests
# ---------------------------------------------------------------------------


class TestValidElicitation(unittest.TestCase):
    """Valid 2-4 question elicitations succeed."""

    def test_valid_2_question_elicitation(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "请回答以下问题",
            "questions": [
                {
                    "id": "q1",
                    "question": "您是甲方还是乙方？",
                    "options": [
                        {"label": "甲方", "value": "party_a"},
                        {"label": "乙方", "value": "party_b"},
                    ],
                },
                {
                    "id": "q2",
                    "question": "合同类型？",
                    "options": [
                        {"label": "租赁合同", "value": "lease"},
                        {"label": "买卖合同", "value": "sale"},
                    ],
                },
            ],
        })

        self.assertIsNone(result.error)
        self.assertTrue(result.metadata.get("terminate_turn"))
        self.assertIn("elicitation_id", result.metadata)
        self.assertIn("interrupt_id", result.content)

    def test_valid_4_question_elicitation(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "请补充以下信息",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
                {"id": "q3", "question": "问题3", "options": [{"label": "C", "value": "c"}]},
                {"id": "q4", "question": "问题4", "options": [{"label": "D", "value": "d"}]},
            ],
        })

        self.assertIsNone(result.error)
        self.assertTrue(result.metadata.get("terminate_turn"))

    def test_valid_elicitation_emits_event(self):
        """The handler emits elicitation.requested via the emitter."""
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "请回答",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        })

        # The emitter should have emitted at least one event (the elicitation.requested)
        self.assertGreater(emitter.seq, 0)

    def test_emitted_event_is_elicitation_requested(self):
        """The emitted event has event_type='elicitation.requested'."""
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        _run_handler(handler, {
            "intro": "请回答",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        })

        # seq should be 1 (one event emitted: elicitation.requested)
        self.assertEqual(emitter.seq, 1)

    def test_terminate_turn_metadata(self):
        """The returned ToolResult has terminate_turn=True and elicitation_id."""
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "q1", "question": "q1"},
                {"id": "q2", "question": "q2"},
            ],
        })

        self.assertTrue(result.metadata["terminate_turn"])
        self.assertIn("elicitation_id", result.metadata)
        interrupt_id = result.metadata["elicitation_id"]
        self.assertEqual(len(interrupt_id), 36)  # UUID format


# ---------------------------------------------------------------------------
# Invalid question count tests
# ---------------------------------------------------------------------------


class TestInvalidQuestionCount(unittest.TestCase):
    """Invalid question counts (1 or 5) produce error results."""

    def test_invalid_1_question_returns_error_result(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "q1", "question": "only one question"},
            ],
        })

        # Should not terminate the turn
        self.assertFalse(result.metadata.get("terminate_turn"))
        self.assertTrue(result.metadata.get("validation_error"))
        self.assertIn("at least 2", result.content)

    def test_invalid_5_question_returns_error_result(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        result = _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": f"q{i}", "question": f"问题{i}"}
                for i in range(1, 6)
            ],
        })

        self.assertFalse(result.metadata.get("terminate_turn"))
        self.assertTrue(result.metadata.get("validation_error"))
        self.assertIn("at most 4", result.content)

    def test_invalid_count_does_not_emit_event(self):
        """When question count is invalid, no elicitation.requested is emitted."""
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "q1", "question": "only one"},
            ],
        })

        # No events should have been emitted
        self.assertEqual(emitter.seq, 0)


# ---------------------------------------------------------------------------
# Auto-assigned IDs and auto-filled values tests
# ---------------------------------------------------------------------------


class TestAutoAssignedIds(unittest.TestCase):
    """Empty id fields are auto-assigned as q1, q2, etc."""

    def test_empty_id_auto_assigned(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        # We need to capture the emitted event to verify the auto-assigned IDs.
        # We'll use a wrapper emitter that records the last emitted event.
        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        })

        # The elicitation.requested event should have auto-assigned IDs
        self.assertEqual(len(emitted_events), 1)
        payload = emitted_events[0].payload
        self.assertEqual(payload["questions"][0]["id"], "q1")
        self.assertEqual(payload["questions"][1]["id"], "q2")

    def test_explicit_id_preserved(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "custom_1", "question": "问题1"},
                {"id": "custom_2", "question": "问题2"},
            ],
        })

        payload = emitted_events[0].payload
        self.assertEqual(payload["questions"][0]["id"], "custom_1")
        self.assertEqual(payload["questions"][1]["id"], "custom_2")


class TestAutoFilledValues(unittest.TestCase):
    """Empty value fields are auto-filled from label."""

    def test_empty_value_auto_filled_from_label(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {
                    "id": "q1",
                    "question": "问题1",
                    "options": [
                        {"label": "甲方", "value": ""},
                        {"label": "乙方"},  # no value key at all
                    ],
                },
                {
                    "id": "q2",
                    "question": "问题2",
                    "options": [
                        {"label": "租赁", "value": "lease"},
                    ],
                },
            ],
        })

        payload = emitted_events[0].payload
        options_q1 = payload["questions"][0]["options"]
        self.assertEqual(options_q1[0]["value"], "甲方")  # auto-filled from label
        self.assertEqual(options_q1[1]["value"], "乙方")  # auto-filled from label
        # Explicit value is preserved
        options_q2 = payload["questions"][1]["options"]
        self.assertEqual(options_q2[0]["value"], "lease")


# ---------------------------------------------------------------------------
# Free-text questions (no options) tests
# ---------------------------------------------------------------------------


class TestFreeTextQuestions(unittest.TestCase):
    """Questions with no options are free-text (empty options list)."""

    def test_free_text_question_has_empty_options(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "请补充信息",
            "questions": [
                {"id": "q1", "question": "请描述您的需求"},
                {"id": "q2", "question": "请补充其他信息"},
            ],
        })

        payload = emitted_events[0].payload
        self.assertEqual(payload["questions"][0]["options"], [])
        self.assertEqual(payload["questions"][1]["options"], [])

    def test_mixed_free_text_and_choice_questions(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {
                    "id": "q1",
                    "question": "您是甲方还是乙方？",
                    "options": [
                        {"label": "甲方", "value": "a"},
                        {"label": "乙方", "value": "b"},
                    ],
                },
                {
                    "id": "q2",
                    "question": "请描述合同标的",
                    # no options → free-text
                },
            ],
        })

        payload = emitted_events[0].payload
        self.assertEqual(len(payload["questions"][0]["options"]), 2)
        self.assertEqual(payload["questions"][1]["options"], [])


# ---------------------------------------------------------------------------
# Emit event verification
# ---------------------------------------------------------------------------


class TestEmitEventVerification(unittest.TestCase):
    """Verify the emitted elicitation.requested event structure."""

    def test_emitted_event_has_correct_type(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "请回答以下问题",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        })

        self.assertEqual(len(emitted_events), 1)
        event = emitted_events[0]
        self.assertEqual(event.event_type, RunEventType.ELICITATION_REQUESTED.value)

    def test_emitted_event_payload_has_intro_and_questions(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "澄清引导语",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        })

        payload = emitted_events[0].payload
        self.assertEqual(payload["intro"], "澄清引导语")
        self.assertEqual(len(payload["questions"]), 2)
        self.assertEqual(payload["questions"][0]["question"], "问题1")
        self.assertEqual(payload["questions"][1]["question"], "问题2")

    def test_emitted_event_has_interrupt_id(self):
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "q1", "question": "q1"},
                {"id": "q2", "question": "q2"},
            ],
        })

        payload = emitted_events[0].payload
        self.assertIn("interrupt_id", payload)
        self.assertEqual(len(payload["interrupt_id"]), 36)  # UUID

    def test_interrupt_id_matches_metadata(self):
        """The interrupt_id in the event payload matches the elicitation_id in ToolResult metadata."""
        emitter = _make_emitter()
        handler = create_clarification_tool(emitter)

        emitted_events = []
        original_emit = emitter._emit

        def recording_emit(event_type, payload, metadata=None):
            event = original_emit(event_type, payload, metadata)
            emitted_events.append(event)
            return event

        emitter._emit = recording_emit

        result = _run_handler(handler, {
            "intro": "intro",
            "questions": [
                {"id": "q1", "question": "q1"},
                {"id": "q2", "question": "q2"},
            ],
        })

        payload = emitted_events[0].payload
        self.assertEqual(payload["interrupt_id"], result.metadata["elicitation_id"])


if __name__ == "__main__":
    unittest.main()
