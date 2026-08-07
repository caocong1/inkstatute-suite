"""E2E test: multi-turn tool orchestration via the full turn loop.

This test exercises the complete ``run_turn()`` async generator with
``FixtureProvider`` (no external LLM).  It verifies:

1. Correct event sequence: ``phase.changed`` → ``thought.delta`` →
   ``tool_call.started`` → ``tool_call.delta`` → ``tool_call.completed`` →
   ``thought.delta`` → ``message.delta`` → ``message.completed`` →
   ``run.state_changed``
2. ``tool_call.started`` comes before ``tool_call.completed``
3. ``message.delta`` events come before ``message.completed``
4. ``seq`` values are strictly increasing
5. ``run.state_changed`` final status is ``"succeeded"``
6. ``provider_usage`` is present in terminal event metadata
7. Tool result message is appended to message history (verified via
   provider call count and message inspection)

Success criterion 1: ``packages/agent-core`` exists, implements async
streaming turn loop, produces Phase 88 unified events, has multi-turn
tool orchestration with turn limit.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider
from inkstatute_agent_core.model.provider import ContentDelta, ToolCallDelta
from inkstatute_agent_core.turn_loop import ToolResult, run_turn

from fixtures.turn_scripts import (
    LEGAL_RESEARCH_2_ROUND,
    LEGAL_RESEARCH_3_ROUND,
    SINGLE_TURN_CONTENT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events(gen) -> list[RunEvent]:
    """Collect all events from an async generator into a list."""
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


def _make_emitter(
    run_id: str = "run-e2e",
    config: AgentCoreConfig | None = None,
) -> EventEmitter:
    return EventEmitter(run_id, config or AgentCoreConfig())


def _event_type_seq_pairs(events: list[RunEvent]) -> list[tuple[str, int]]:
    """Return list of (event_type, seq) for ordering analysis."""
    return [(e.event_type, e.seq) for e in events]


# ---------------------------------------------------------------------------
# E2E: 2-round tool orchestration
# ---------------------------------------------------------------------------


class TestE2EMultiTurnToolOrchestration(unittest.TestCase):
    """Full turn loop with FixtureProvider: 2-round legal research scenario."""

    def test_2_round_legal_research_event_sequence(self):
        """Verify the complete event sequence for a 2-round tool orchestration."""
        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "搜索合同法第三条"}],
                tools=[{"type": "function", "function": {"name": "legal_search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        event_types = [e.event_type for e in events]

        # 1. Event sequence: phase.changed should be first
        self.assertEqual(event_types[0], RunEventType.PHASE_CHANGED.value)

        # 2. phase.changed appears twice (one per round)
        phase_events = [e for e in events if e.event_type == RunEventType.PHASE_CHANGED.value]
        self.assertEqual(len(phase_events), 2)

        # 3. tool_call.started before tool_call.completed
        started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3.value]
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(started), 1)
        self.assertEqual(len(completed), 1)
        self.assertLess(started[0].seq, completed[0].seq)

        # 4. tool_call.delta exists between started and completed
        deltas = [e for e in events if e.event_type == RunEventType.TOOL_CALL_DELTA.value]
        self.assertGreaterEqual(len(deltas), 1)
        for d in deltas:
            self.assertGreater(d.seq, started[0].seq)
            self.assertLess(d.seq, completed[0].seq)

        # 5. message.delta events come before message.completed
        msg_deltas = [e for e in events if e.event_type == RunEventType.MESSAGE_DELTA_V3.value]
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertGreater(len(msg_deltas), 0)
        self.assertEqual(len(msg_completed), 1)
        for md in msg_deltas:
            self.assertLess(md.seq, msg_completed[0].seq)

        # 6. run.state_changed is the last event with status "succeeded"
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "succeeded")
        self.assertEqual(state_events[0].seq, events[-1].seq)

    def test_2_round_seq_strictly_increasing(self):
        """seq values are strictly increasing across all events."""
        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        seqs = [e.seq for e in events]
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1],
                f"seq not strictly increasing at index {i}: {seqs[i-1]} -> {seqs[i]}")

    def test_2_round_provider_usage_in_terminal_events(self):
        """provider_usage is present in message.completed and run.state_changed metadata."""
        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value][0]
        self.assertIn("provider_usage", msg_completed.metadata)
        self.assertGreater(msg_completed.metadata["provider_usage"]["total_tokens"], 0)

        state_changed = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value][0]
        self.assertIn("provider_usage", state_changed.metadata)

    def test_2_round_tool_result_appended_to_history(self):
        """Tool result message is appended — provider is called twice (2 rounds)."""
        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        # Provider should have been called twice (round 1: tool call, round 2: final content)
        self.assertEqual(provider.call_count, 2)

        # The final message.completed should have non-empty content
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value][0]
        self.assertIn("合同法", msg_completed.payload["content"])

    def test_2_round_thought_delta_present_in_each_round(self):
        """thought.delta events are present in both rounds (pre-LLM thoughts)."""
        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        thought_deltas = [e for e in events if e.event_type == RunEventType.THOUGHT_DELTA.value]
        # At least: pre-LLM thought in round 1, reasoning delta in round 1,
        # transition thought after tools, pre-LLM thought in round 2, reasoning in round 2
        self.assertGreaterEqual(len(thought_deltas), 3)

    def test_2_round_tool_executor_invoked_with_correct_args(self):
        """Custom tool_executor receives the correct tool_call_id, name, and arguments."""
        received_calls: list[tuple[str, str, dict]] = []

        async def recording_executor(tool_call_id, tool_name, arguments):
            received_calls.append((tool_call_id, tool_name, arguments))
            return ToolResult(content="搜索结果: 合同法第三条 — 自愿原则")

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "legal_search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=recording_executor,
                run_id="run-e2e",
            )
        ))

        # Tool executor should have been called once
        self.assertEqual(len(received_calls), 1)
        tc_id, tc_name, tc_args = received_calls[0]
        self.assertEqual(tc_id, "call_1")
        self.assertEqual(tc_name, "legal_search")
        self.assertEqual(tc_args.get("query"), "合同法 第三条")

        # tool_call.completed should have status "succeeded" and the content
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "succeeded")
        self.assertIn("自愿原则", completed[0].payload["content"])


# ---------------------------------------------------------------------------
# E2E: 3-round tool orchestration (two tools then final content)
# ---------------------------------------------------------------------------


class TestE2EThreeRoundOrchestration(unittest.TestCase):
    """3-round scenario: search → read_file → final content."""

    def test_3_round_two_tools_then_content(self):
        """Three rounds: two tool calls in sequence, then final content."""
        provider = FixtureProvider(LEGAL_RESEARCH_3_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        # Provider called 3 times
        self.assertEqual(provider.call_count, 3)

        # 3 phase.changed events (one per round)
        phase_events = [e for e in events if e.event_type == RunEventType.PHASE_CHANGED.value]
        self.assertEqual(len(phase_events), 3)

        # 2 tool_call.started, 2 tool_call.completed
        started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3.value]
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(started), 2)
        self.assertEqual(len(completed), 2)

        # Each started comes before its corresponding completed
        for i in range(2):
            self.assertLess(started[i].seq, completed[i].seq)

        # Final state is succeeded
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(state_events[0].payload["status"], "succeeded")

        # message.completed has content
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(msg_completed), 1)
        self.assertIn("劳动合同法", msg_completed[0].payload["content"])

    def test_3_round_seq_monotonicity(self):
        """seq values are strictly increasing across 3 rounds."""
        provider = FixtureProvider(LEGAL_RESEARCH_3_ROUND)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        seqs = [e.seq for e in events]
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1])


# ---------------------------------------------------------------------------
# E2E: Single-turn (no tools) — immediate final content
# ---------------------------------------------------------------------------


class TestE2ESingleTurnNoTools(unittest.TestCase):
    """Single-turn: LLM produces content immediately, no tool calls."""

    def test_single_turn_completes_immediately(self):
        """A single content round emits message.delta + message.completed + run.state_changed."""
        provider = FixtureProvider(SINGLE_TURN_CONTENT)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "你好"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        # Only one round — provider called once
        self.assertEqual(provider.call_count, 1)

        # No tool call events
        started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3.value]
        self.assertEqual(len(started), 0)

        # message.completed present with full content
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(msg_completed), 1)
        self.assertIn("法律助手", msg_completed[0].payload["content"])

        # run.state_changed to succeeded
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "succeeded")

    def test_single_turn_usage_in_metadata(self):
        """provider_usage is present in terminal events for single-turn."""
        provider = FixtureProvider(SINGLE_TURN_CONTENT)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value][0]
        self.assertIn("provider_usage", msg_completed.metadata)
        self.assertEqual(msg_completed.metadata["provider_usage"]["total_tokens"], 30)


# ---------------------------------------------------------------------------
# E2E: Always-streaming verification — content streamed during tool rounds
# ---------------------------------------------------------------------------


class TestE2EAlwaysStreaming(unittest.TestCase):
    """Verify the 'always stream' fix — content is streamed even during tool rounds."""

    def test_content_streamed_during_tool_round(self):
        """During a tool round, content deltas are still emitted as message.delta."""
        from inkstatute_agent_core.fixtures import TurnScript
        from inkstatute_agent_core.model.provider import FinishDelta

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="让我先搜索相关法规。"),
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="根据搜索结果，答案是..."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e",
            )
        ))

        # message.delta from round 1 (tool round) should be present
        msg_deltas = [e for e in events if e.event_type == RunEventType.MESSAGE_DELTA_V3.value]
        delta_contents = [e.payload["delta"] for e in msg_deltas]
        self.assertIn("让我先搜索相关法规。", delta_contents)
        self.assertIn("根据搜索结果，答案是...", delta_contents)


if __name__ == "__main__":
    unittest.main()
