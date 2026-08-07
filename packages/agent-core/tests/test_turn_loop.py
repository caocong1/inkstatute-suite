"""Tests for the async turn loop — streaming, tool calls, error recovery, turn limit.

Uses ``FixtureProvider`` from 100-02 to test without external LLM calls.
Covers: single-turn (no tools), multi-turn tool orchestration, tool failure
recovery, turn limit exceeded, provider error, heartbeat, usage accumulation.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import ErrorCategory, RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ReasoningDelta,
    ToolCallDelta,
    UsageDelta,
)
from inkstatute_agent_core.turn_loop import ToolResult, run_turn

from platform_contract.events import ErrorInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeMonotonicClock:
    """Returns controlled monotonic values for silence threshold testing."""

    def __init__(self, start: float = 0.0):
        self._current = start

    def __call__(self) -> float:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current += seconds


async def _collect_events(gen) -> list[RunEvent]:
    """Collect all events from an async generator into a list."""
    events = []
    async for event in gen:
        events.append(event)
    return events


def _make_emitter(
    run_id: str = "run-test",
    config: AgentCoreConfig | None = None,
    monotonic_clock=None,
) -> EventEmitter:
    """Create an EventEmitter with optional injectable clocks."""
    kwargs = {}
    if monotonic_clock is not None:
        kwargs["monotonic_clock"] = monotonic_clock
    return EventEmitter(run_id, config or AgentCoreConfig(), **kwargs)


# ---------------------------------------------------------------------------
# Single-turn (no tools)
# ---------------------------------------------------------------------------


class TestSingleTurnNoTools(unittest.TestCase):
    """Single-turn: LLM produces content, no tool calls."""

    def test_single_turn_streams_content_and_completes(self):
        """A single content round emits message.delta + message.completed + run.state_changed."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="Hello"),
                ContentDelta(content=" world"),
                UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        # Should have phase.changed, thought.delta, message.delta x2,
        # message.completed, run.state_changed
        event_types = [e.event_type for e in events]
        self.assertIn(RunEventType.PHASE_CHANGED.value, event_types)
        self.assertIn(RunEventType.MESSAGE_DELTA_V3.value, event_types)
        self.assertIn(RunEventType.MESSAGE_COMPLETED.value, event_types)
        self.assertIn(RunEventType.RUN_STATE_CHANGED.value, event_types)

        # message.completed should have the full content
        completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["content"], "Hello world")

        # run.state_changed should be "succeeded"
        state_changed = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_changed), 1)
        self.assertEqual(state_changed[0].payload["status"], "succeeded")

    def test_provider_usage_in_metadata(self):
        """message.completed and run.state_changed include provider_usage."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="answer"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}),
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
                run_id="run-test",
            )
        ))

        completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value][0]
        self.assertIn("provider_usage", completed.metadata)
        self.assertEqual(completed.metadata["provider_usage"]["prompt_tokens"], 100)
        self.assertEqual(completed.metadata["provider_usage"]["completion_tokens"], 50)

        state_changed = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value][0]
        self.assertIn("provider_usage", state_changed.metadata)

    def test_reasoning_delta_emits_thought_delta(self):
        """ReasoningDelta from provider → thought.delta events."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ReasoningDelta(reasoning="Let me think..."),
                ContentDelta(content="Answer"),
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
                run_id="run-test",
            )
        ))

        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        # At least the pre-LLM thought + the reasoning delta
        self.assertGreaterEqual(len(thought_deltas), 2)
        # Check that the reasoning content appears
        thought_contents = [e.payload["delta"] for e in thought_deltas]
        self.assertIn("Let me think...", thought_contents)


# ---------------------------------------------------------------------------
# Multi-turn tool orchestration
# ---------------------------------------------------------------------------


class TestMultiTurnToolOrchestration(unittest.TestCase):
    """Multi-turn: round 1 has tool calls, round 2 has final content."""

    def test_tool_calls_then_final_content(self):
        """Round 1: tool call → execute → round 2: final content."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="legal_search",
                    arguments='{"query": "合同法"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="根据检索结果..."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "搜索合同法"}],
                tools=[{"type": "function", "function": {"name": "legal_search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        event_types = [e.event_type for e in events]

        # Should have tool_call.started, tool_call.delta, tool_call.completed
        self.assertIn(RunEventType.TOOL_CALL_STARTED_V3.value, event_types)
        self.assertIn(RunEventType.TOOL_CALL_DELTA.value, event_types)
        self.assertIn(RunEventType.TOOL_CALL_COMPLETED_V3.value, event_types)

        # Should have message.completed (from round 2)
        self.assertIn(RunEventType.MESSAGE_COMPLETED.value, event_types)

        # Should have two phase.changed events (one per round)
        phase_events = [e for e in events if e.event_type == RunEventType.PHASE_CHANGED.value]
        self.assertEqual(len(phase_events), 2)

        # Provider should have been called twice
        self.assertEqual(provider.call_count, 2)

    def test_tool_call_started_before_completed(self):
        """tool_call.started comes before tool_call.completed."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="done"),
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
                run_id="run-test",
            )
        ))

        started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3.value]
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(started), 1)
        self.assertEqual(len(completed), 1)
        self.assertLess(started[0].seq, completed[0].seq)

    def test_fixture_tool_result_when_no_executor(self):
        """When tool_executor is None, a fixture result is produced."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="final"),
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
                run_id="run-test",
            )
        ))

        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "succeeded")
        self.assertEqual(completed[0].payload["content"], "[fixture tool result]")


# ---------------------------------------------------------------------------
# Tool failure recovery
# ---------------------------------------------------------------------------


class TestToolFailureRecovery(unittest.TestCase):
    """Tool failures produce error events, don't crash, loop continues."""

    def test_tool_executor_returns_error_result(self):
        """ToolExecutor returns ToolResult with error → tool_call.completed with status=error."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="Tool failed: connection timeout",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                    message="connection timeout",
                ),
            )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="Sorry, the search failed. Let me try another approach."),
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
                tool_executor=failing_executor,
                run_id="run-test",
            )
        ))

        # Should have tool_call.completed with status=error
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "error")
        self.assertIsNotNone(completed[0].payload["error"])

        # Loop should continue — message.completed from round 2
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(msg_completed), 1)

    def test_tool_executor_raises_exception(self):
        """ToolExecutor raises exception → caught, error event, loop continues."""
        async def crashing_executor(tool_call_id, tool_name, arguments):
            raise RuntimeError("Tool crashed!")

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="Recovering from error..."),
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
                tool_executor=crashing_executor,
                run_id="run-test",
            )
        ))

        # Should have tool_call.completed with status=error
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "error")

        # Loop continues — message.completed from round 2
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(msg_completed), 1)

    def test_error_tool_result_appended_to_messages(self):
        """Error tool result is appended as {'role': 'tool', 'content': 'Error: ...'}."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="connection refused",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                ),
            )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="recovered"),
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
                tool_executor=failing_executor,
                run_id="run-test",
            )
        ))

        # The provider should have been called twice, meaning the loop continued
        self.assertEqual(provider.call_count, 2)


# ---------------------------------------------------------------------------
# Turn limit exceeded
# ---------------------------------------------------------------------------


class TestTurnLimitExceeded(unittest.TestCase):
    """Turn limit enforcement: emits error + run.state_changed to failed."""

    def test_turn_limit_emits_error_and_failed_state(self):
        """When max_turns is reached, emit error with turn_limit_exceeded + run.state_changed to failed."""
        # Script that always returns tool calls — never produces final content
        script = [
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id=f"tc_{i}", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ])
            for i in range(15)  # more than max_turns
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig(max_turns=3)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        # Should have error event with turn_limit_exceeded
        error_events = [e for e in events if e.event_type == RunEventType.ERROR.value]
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].payload["error"]["code"], "turn_limit_exceeded")

        # Should have run.state_changed to "failed"
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "failed")

        # Provider should have been called exactly max_turns times
        self.assertEqual(provider.call_count, 3)

    def test_turn_limit_with_default_max_turns(self):
        """Default max_turns=10 is enforced."""
        script = [
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id=f"tc_{i}", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ])
            for i in range(20)
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()  # default max_turns=10
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        self.assertEqual(provider.call_count, 10)
        error_events = [e for e in events if e.event_type == RunEventType.ERROR.value]
        self.assertEqual(len(error_events), 1)


# ---------------------------------------------------------------------------
# Provider error
# ---------------------------------------------------------------------------


class TestProviderError(unittest.TestCase):
    """Provider exception → error event + run.state_changed to failed."""

    def test_provider_raises_exception(self):
        """If provider.chat_stream() raises, emit error + run.state_changed to failed."""
        provider = FixtureProvider([
            TurnScript(error=ConnectionError("API connection refused")),
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
                run_id="run-test",
            )
        ))

        # Should have error event
        error_events = [e for e in events if e.event_type == RunEventType.ERROR.value]
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].payload["error"]["code"], "provider_error")

        # Should have run.state_changed to "failed"
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "failed")

    def test_provider_error_does_not_crash_generator(self):
        """The generator should terminate cleanly after a provider error."""
        provider = FixtureProvider([
            TurnScript(error=RuntimeError("model unavailable")),
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
                run_id="run-test",
            )
        ))

        # Generator should have terminated (events collected without hanging)
        self.assertGreater(len(events), 0)


# ---------------------------------------------------------------------------
# Heartbeat during long operations
# ---------------------------------------------------------------------------


class TestHeartbeat(unittest.TestCase):
    """thought.delta heartbeat events are emitted when silence > threshold."""

    def test_heartbeat_emitted_during_long_silence(self):
        """When silence > threshold, maybe_heartbeat emits a heartbeat thought.delta."""
        # Use an auto-advancing clock: each call advances by 6 seconds
        # (exceeding the 5s threshold), so maybe_heartbeat will detect silence
        class AutoAdvancingClock:
            def __init__(self):
                self._current = 0.0

            def __call__(self) -> float:
                result = self._current
                self._current += 6.0
                return result

        clock = AutoAdvancingClock()
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = _make_emitter(config=config, monotonic_clock=clock)

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="thinking..."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        # Should have at least one heartbeat thought.delta
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat")]
        self.assertGreater(len(heartbeats), 0)


# ---------------------------------------------------------------------------
# Usage accumulation
# ---------------------------------------------------------------------------


class TestUsageAccumulation(unittest.TestCase):
    """Usage data is accumulated across rounds and attached to final events."""

    def test_usage_accumulated_across_rounds(self):
        """Usage from multiple rounds is summed in the final events."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                UsageDelta(usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="final answer"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}),
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
                run_id="run-test",
            )
        ))

        completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value][0]
        usage = completed.metadata["provider_usage"]
        # Usage from round 2 (the final content round) should be in the metadata
        self.assertEqual(usage["prompt_tokens"], 100)
        self.assertEqual(usage["completion_tokens"], 20)


# ---------------------------------------------------------------------------
# Seq monotonicity
# ---------------------------------------------------------------------------


class TestSeqMonotonicity(unittest.TestCase):
    """seq values are strictly monotonic (assigned by EventEmitter)."""

    def test_seq_strictly_increasing(self):
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="a"),
                ContentDelta(content="b"),
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
                run_id="run-test",
            )
        ))

        seqs = [e.seq for e in events]
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1])


# ---------------------------------------------------------------------------
# Always streaming
# ---------------------------------------------------------------------------


class TestAlwaysStreaming(unittest.TestCase):
    """LLM response is ALWAYS streamed — even during tool rounds."""

    def test_tool_round_streams_content(self):
        """During a tool round, content deltas are still streamed as message.delta."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="Let me search for that."),
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="Here is the result."),
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
                run_id="run-test",
            )
        ))

        # Should have message.delta from round 1 (tool round)
        message_deltas = [e for e in events if e.event_type == RunEventType.MESSAGE_DELTA_V3.value]
        delta_contents = [e.payload["delta"] for e in message_deltas]
        self.assertIn("Let me search for that.", delta_contents)
        self.assertIn("Here is the result.", delta_contents)


# ---------------------------------------------------------------------------
# terminate_turn metadata tests
# ---------------------------------------------------------------------------


class TestTerminateTurn(unittest.TestCase):
    """Tools with terminate_turn=True stop the turn loop."""

    def test_tool_with_terminate_turn_stops_loop(self):
        """A tool returning terminate_turn=True causes the loop to emit
        run.state_changed(waiting_for_user) and return."""
        async def terminating_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="turn terminated by tool",
                metadata={"terminate_turn": True},
            )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments='{"intro":"请回答","questions":[...]}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # This second round should NOT be reached
            TurnScript(deltas=[
                ContentDelta(content="This should not be reached."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "ask_user"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=terminating_executor,
                run_id="run-test",
            )
        ))

        # Provider should have been called only once (loop stopped after round 1)
        self.assertEqual(provider.call_count, 1)

        # run.state_changed with status "waiting_for_user" should be present
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "waiting_for_user")

        # tool_call.completed with status "succeeded" should be present
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "succeeded")

        # No message.completed event (loop did not reach final content round)
        msg_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED.value]
        self.assertEqual(len(msg_completed), 0)

    def test_tool_with_terminate_turn_false_continues(self):
        """A tool returning terminate_turn=False (or not set) continues the loop."""
        async def normal_executor(tool_call_id, tool_name, arguments):
            return ToolResult(content="normal result")

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="search",
                    arguments='{"query":"test"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="Final answer."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=normal_executor,
                run_id="run-test",
            )
        ))

        # Provider should have been called twice (round 1: tool, round 2: content)
        self.assertEqual(provider.call_count, 2)

        # run.state_changed with status "succeeded" (not "waiting_for_user")
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "succeeded")

    def test_multiple_tools_one_terminate_stops_loop(self):
        """When multiple tools are called and one has terminate_turn=True,
        the loop stops after processing all tools in the batch."""
        async def multi_executor(tool_call_id, tool_name, arguments):
            if tool_name == "ask_user":
                return ToolResult(
                    content="terminating",
                    metadata={"terminate_turn": True},
                )
            return ToolResult(content="normal result")

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="search",
                    arguments='{"query":"test"}',
                ),
                ToolCallDelta(
                    tool_call_id="call_2",
                    tool_name="ask_user",
                    arguments='{"intro":"请回答","questions":[...]}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # This should NOT be reached
            TurnScript(deltas=[
                ContentDelta(content="Should not be reached."),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "search"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=multi_executor,
                run_id="run-test",
            )
        ))

        # Provider called only once (loop stopped after round 1)
        self.assertEqual(provider.call_count, 1)

        # Both tool calls should have completed events
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 2)

        # run.state_changed with status "waiting_for_user"
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "waiting_for_user")

    def test_no_tools_normal_final_content_unchanged(self):
        """No tools (normal final content round) — behavior unchanged."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="Hello"),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-test",
            )
        ))

        # Should complete normally with "succeeded"
        state_events = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED.value]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "succeeded")

    def test_terminate_tool_result_appended_to_messages(self):
        """The tool result message is still appended to current_messages before terminating."""
        async def terminating_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="turn terminated by tool",
                metadata={"terminate_turn": True},
            )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments='{}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "ask_user"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=terminating_executor,
                run_id="run-test",
            )
        ))

        # tool_call.completed should have status "succeeded" and the content
        completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "succeeded")
        self.assertIn("turn terminated", completed[0].payload["content"])

    def test_terminate_emits_waiting_for_user_as_last_event(self):
        """run.state_changed(waiting_for_user) is the last event when terminating."""
        async def terminating_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="terminating",
                metadata={"terminate_turn": True},
            )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="ask_user",
                    arguments='{}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=[{"type": "function", "function": {"name": "ask_user"}}],
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=terminating_executor,
                run_id="run-test",
            )
        ))

        # The last event should be run.state_changed
        self.assertEqual(events[-1].event_type, RunEventType.RUN_STATE_CHANGED.value)
        self.assertEqual(events[-1].payload["status"], "waiting_for_user")


if __name__ == "__main__":
    unittest.main()
