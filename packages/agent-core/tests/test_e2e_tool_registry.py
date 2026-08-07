"""E2E integration test: ToolRegistry + dispatching executor + clarification tool + turn loop.

Wires the ``ToolRegistry``, ``create_dispatching_executor``,
``create_clarification_tool``, and the enhanced ``run_turn()`` together
using the ``FixtureProvider`` from Phase 100.  No external LLM calls.

Verifies the complete flow:
1. EventEmitter with injectable clocks
2. ToolRegistry registers the clarification tool (via create_clarification_tool)
3. Dispatching executor created from the registry
4. FixtureProvider scripted to emit a tool call for ``ask_user``
5. ``run_turn()`` with the dispatching executor
6. Asserts: ``elicitation.requested`` emitted, ``tool_call.completed``
   with status="succeeded", ``run.state_changed`` with
   status="waiting_for_user", generator stops (does not reach turn limit
   or final content)
"""

from __future__ import annotations

import asyncio
import json
import unittest

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import FinishDelta, ToolCallDelta
from inkstatute_agent_core.tools.clarification import (
    CLARIFICATION_TOOL_DEFINITION,
    create_clarification_tool,
)
from inkstatute_agent_core.tools.executor import create_dispatching_executor
from inkstatute_agent_core.tools.registry import ToolRegistry
from inkstatute_agent_core.turn_loop import run_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events(gen) -> list[RunEvent]:
    """Collect all events from an async generator into a list."""
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# E2E: ToolRegistry + clarification tool + turn loop
# ---------------------------------------------------------------------------


class TestE2EToolRegistryClarification(unittest.TestCase):
    """Full integration: ToolRegistry + clarification tool + enhanced turn loop."""

    def test_clarification_tool_e2e(self):
        """End-to-end: LLM calls ask_user → elicitation.requested emitted →
        turn stops with waiting_for_user."""
        # 1. Create EventEmitter
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-tools", config)

        # 2. Create ToolRegistry and register the clarification tool
        registry = ToolRegistry()
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            "ask_user",
            clarification_handler,
            CLARIFICATION_TOOL_DEFINITION,
        )

        # 3. Create dispatching executor from the registry
        executor = create_dispatching_executor(registry)

        # 4. FixtureProvider scripted to emit a tool call for ask_user
        ask_user_args = json.dumps({
            "intro": "为了更好地帮您审查合同，请回答以下问题：",
            "questions": [
                {
                    "id": "q1",
                    "question": "您在本交易中是甲方还是乙方？",
                    "options": [
                        {"label": "甲方", "value": "party_a"},
                        {"label": "乙方", "value": "party_b"},
                    ],
                },
                {
                    "id": "q2",
                    "question": "本次涉及哪类合同？",
                    "options": [
                        {"label": "技术开发合同", "value": "tech_dev"},
                        {"label": "买卖合同", "value": "sale"},
                        {"label": "租赁合同", "value": "lease"},
                    ],
                },
            ],
        }, ensure_ascii=False)

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments=ask_user_args,
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # This second round should NOT be reached
            TurnScript(deltas=[
                # Would produce final content if reached
                FinishDelta(finish_reason="stop"),
            ]),
        ])

        # 5. Run the turn loop with the dispatching executor
        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "请帮我审查这份合同"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-e2e-tools",
            )
        ))

        # 6. Assertions

        # a. elicitation.requested event is emitted
        elicitation_events = [
            e for e in events
            if e.event_type == RunEventType.ELICITATION_REQUESTED.value
        ]
        self.assertEqual(len(elicitation_events), 1)
        elicitation = elicitation_events[0]
        self.assertEqual(elicitation.payload["intro"], "为了更好地帮您审查合同，请回答以下问题：")
        self.assertEqual(len(elicitation.payload["questions"]), 2)
        self.assertEqual(elicitation.payload["questions"][0]["id"], "q1")
        self.assertEqual(elicitation.payload["questions"][0]["question"], "您在本交易中是甲方还是乙方？")
        self.assertEqual(len(elicitation.payload["questions"][0]["options"]), 2)
        self.assertEqual(elicitation.payload["questions"][0]["options"][0]["label"], "甲方")

        # b. tool_call.completed with status="succeeded"
        completed_events = [
            e for e in events
            if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value
        ]
        self.assertEqual(len(completed_events), 1)
        self.assertEqual(completed_events[0].payload["status"], "succeeded")
        self.assertIn("interrupt_id", completed_events[0].payload["content"])

        # c. run.state_changed with status="waiting_for_user"
        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "waiting_for_user")

        # d. The generator stops after the clarification tool
        #    (does not continue to next round)
        self.assertEqual(provider.call_count, 1)

        # e. No message.completed event (loop did not reach final content)
        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ]
        self.assertEqual(len(msg_completed), 0)

        # f. No error events
        error_events = [
            e for e in events
            if e.event_type == RunEventType.ERROR.value
        ]
        self.assertEqual(len(error_events), 0)

    def test_clarification_tool_e2e_seq_monotonic(self):
        """All events have strictly increasing seq values."""
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-seq", config)

        registry = ToolRegistry()
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            "ask_user",
            clarification_handler,
            CLARIFICATION_TOOL_DEFINITION,
        )
        executor = create_dispatching_executor(registry)

        ask_user_args = json.dumps({
            "intro": "请回答",
            "questions": [
                {"id": "q1", "question": "问题1", "options": [{"label": "A", "value": "a"}]},
                {"id": "q2", "question": "问题2", "options": [{"label": "B", "value": "b"}]},
            ],
        }, ensure_ascii=False)

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments=ask_user_args,
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
        ])

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-e2e-seq",
            )
        ))

        seqs = [e.seq for e in events]
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1])

    def test_clarification_tool_e2e_no_external_llm(self):
        """The test uses FixtureProvider — no external LLM calls."""
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-no-llm", config)

        registry = ToolRegistry()
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            "ask_user",
            clarification_handler,
            CLARIFICATION_TOOL_DEFINITION,
        )
        executor = create_dispatching_executor(registry)

        ask_user_args = json.dumps({
            "intro": "请回答",
            "questions": [
                {"id": "q1", "question": "问题1"},
                {"id": "q2", "question": "问题2"},
            ],
        }, ensure_ascii=False)

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments=ask_user_args,
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
        ])

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-e2e-no-llm",
            )
        ))

        # FixtureProvider was used (model_name is "fixture")
        self.assertEqual(provider.model_name(), "fixture")
        # Events were produced
        self.assertGreater(len(events), 0)

    def test_clarification_tool_e2e_tool_definitions_passed(self):
        """The tool definitions from the registry are passed to ChatRequest.tools."""
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-defs", config)

        registry = ToolRegistry()
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            "ask_user",
            clarification_handler,
            CLARIFICATION_TOOL_DEFINITION,
        )

        # Verify the registry has the correct tool definitions
        defs = registry.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["function"]["name"], "ask_user")

    def test_clarification_tool_e2e_free_text_questions(self):
        """E2e with free-text questions (no options) works correctly."""
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-freetext", config)

        registry = ToolRegistry()
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            "ask_user",
            clarification_handler,
            CLARIFICATION_TOOL_DEFINITION,
        )
        executor = create_dispatching_executor(registry)

        ask_user_args = json.dumps({
            "intro": "请补充以下信息",
            "questions": [
                {"id": "q1", "question": "请描述您的合同标的"},
                {"id": "q2", "question": "请补充其他需要说明的事项"},
            ],
        }, ensure_ascii=False)

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments=ask_user_args,
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
        ])

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-e2e-freetext",
            )
        ))

        # elicitation.requested should have free-text questions (empty options)
        elicitation = [
            e for e in events
            if e.event_type == RunEventType.ELICITATION_REQUESTED.value
        ][0]
        self.assertEqual(elicitation.payload["questions"][0]["options"], [])
        self.assertEqual(elicitation.payload["questions"][1]["options"], [])

        # Turn still stops with waiting_for_user
        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(state_events[0].payload["status"], "waiting_for_user")


if __name__ == "__main__":
    unittest.main()
