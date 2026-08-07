"""Silence threshold verification — no event gaps > 5s during tool rounds.

This is the KEY test for Phase 100 success criterion 2: the "整轮静默"
(whole-round silence) fix.  It verifies that:

1. Heartbeat ``thought.delta`` events with ``metadata={"heartbeat": true}``
   are emitted when silence exceeds the threshold.
2. No heartbeat events when all operations are fast (within threshold).
3. At least one ``thought.delta`` or ``tool_call.*`` event during each
   tool round (no silent rounds).
4. The maximum gap between consecutive events (as measured by the
   monotonic clock) does not exceed ``silence_threshold_seconds +
   tolerance``.

The test uses an injectable monotonic clock (``ScriptedClock``) and a
``RecordingEmitter`` to deterministically control and measure time
progression without real time delays.

Success criterion 2: **工具轮流式** — tool calls期间持续产出
``thought.delta`` 与 ``tool_call.started|delta|completed``，测试断言
从提交到最终回复之间不存在超过阈值的事件静默期。
"""

from __future__ import annotations

import unittest
from typing import Any

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ToolCallDelta,
    UsageDelta,
)
from inkstatute_agent_core.turn_loop import run_turn

from fixtures.turn_scripts import LEGAL_RESEARCH_2_ROUND


# ---------------------------------------------------------------------------
# Test infrastructure: ScriptedClock + RecordingEmitter
# ---------------------------------------------------------------------------


class ScriptedClock:
    """Monotonic clock that returns pre-computed values from a list.

    Returns values in order from ``values``.  If exhausted, returns the
    last value indefinitely.  This allows deterministic control of time
    progression without real ``asyncio.sleep`` delays.
    """

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._index = 0

    def __call__(self) -> float:
        if self._index < len(self._values):
            val = self._values[self._index]
            self._index += 1
            return val
        return self._values[-1] if self._values else 0.0


class RecordingEmitter(EventEmitter):
    """EventEmitter that records monotonic clock values at each _emit() call.

    The ``emit_times`` list stores the ``_last_event_time`` after each
    ``_emit()`` call, allowing gap calculation between consecutive events.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.emit_times: list[float] = []

    def _emit(self, event_type, payload, metadata=None) -> RunEvent:
        event = super()._emit(event_type, payload, metadata)
        self.emit_times.append(self._last_event_time)
        return event


async def _collect_events(gen) -> list[RunEvent]:
    """Collect all events from an async generator into a list."""
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


def _max_gap(times: list[float]) -> float:
    """Calculate the maximum gap between consecutive time values."""
    if len(times) < 2:
        return 0.0
    return max(times[i + 1] - times[i] for i in range(len(times) - 1))


# ---------------------------------------------------------------------------
# Scenario 1: Long LLM call — heartbeat fires before LLM stream
# ---------------------------------------------------------------------------


class TestSilenceThresholdLongLLMCall(unittest.TestCase):
    """Long LLM call: heartbeat fires when silence exceeds threshold."""

    def test_heartbeat_present_before_long_llm_call(self):
        """When the clock advances > threshold before the LLM call, a heartbeat fires.

        Clock script: time stays at 0 for initial events, then jumps to 5.1
        at the maybe_heartbeat() check (exceeding the 5s threshold), triggering
        a heartbeat.  All subsequent calls return 5.1 (no further advancement).
        """
        # ScriptedClock values for single-turn scenario:
        # v0=0 (init), v1=0 (phase.changed), v2=0 (thought.delta),
        # v3=5.1 (maybe_heartbeat → elapsed=5.1 > 5 → heartbeat!),
        # v4=5.1 (heartbeat _emit), v5=5.1 (message.delta),
        # v6=5.1 (message.completed), v7=5.1 (run.state_changed)
        clock = ScriptedClock([0, 0, 0, 5.1, 5.1, 5.1, 5.1, 5.1, 5.1, 5.1])
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="answer"),
                UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
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
                run_id="run-silence",
            )
        ))

        # 1. Heartbeat thought.delta events present
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat") is True]
        self.assertGreater(len(heartbeats), 0,
            "Expected at least one heartbeat thought.delta when silence > threshold")

    def test_max_gap_within_threshold_plus_tolerance(self):
        """Max gap between consecutive events <= threshold + tolerance (5.5s)."""
        clock = ScriptedClock([0, 0, 0, 5.1, 5.1, 5.1, 5.1, 5.1, 5.1, 5.1])
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="answer"),
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
                run_id="run-silence",
            )
        ))

        # Calculate gaps from recorded emit times
        gaps = _max_gap(emitter.emit_times)
        self.assertLessEqual(
            gaps, 5.5,
            f"Max gap {gaps}s exceeds threshold + tolerance (5.5s). "
            f"emit_times={emitter.emit_times}",
        )


# ---------------------------------------------------------------------------
# Scenario 2: Long tool execution — heartbeat fires during tool round
# ---------------------------------------------------------------------------


class TestSilenceThresholdLongToolExecution(unittest.TestCase):
    """Long tool execution: heartbeat fires during tool round."""

    def test_heartbeat_during_tool_execution(self):
        """Heartbeat fires during tool execution when silence exceeds threshold.

        Clock script for 2-round scenario (tool call → final content):
        - Round 1: phase.changed(0), thought(0), heartbeat_check(5.1→heartbeat),
          tool_call.started(5.1), heartbeat_check(10.2→heartbeat),
          tool_call.delta(10.2), tool_call.completed(10.2), thought(10.2)
        - Round 2: phase.changed(10.2), thought(10.2), heartbeat_check(15.3→heartbeat),
          message.delta(15.3), message.completed(15.3), run.state_changed(15.3)
        """
        clock_values = [
            0,      # init
            0,      # phase.changed R1
            0,      # thought.delta R1
            5.1,    # maybe_heartbeat R1 → heartbeat (5.1 > 5)
            5.1,    # heartbeat _emit
            5.1,    # tool_call.started
            10.2,   # maybe_heartbeat during tool → heartbeat (10.2-5.1=5.1 > 5)
            10.2,   # heartbeat _emit
            10.2,   # tool_call.delta
            10.2,   # tool_call.completed
            10.2,   # thought.delta (transition)
            10.2,   # phase.changed R2
            10.2,   # thought.delta R2
            15.3,   # maybe_heartbeat R2 → heartbeat (15.3-10.2=5.1 > 5)
            15.3,   # heartbeat _emit
            15.3,   # message.delta
            15.3,   # message.completed
            15.3,   # run.state_changed
            15.3,   # extra (safety)
        ]
        clock = ScriptedClock(clock_values)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        # 1. Heartbeat events present
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat") is True]
        self.assertGreater(len(heartbeats), 0,
            "Expected heartbeat events during long tool execution")

    def test_max_gap_during_tool_round_within_tolerance(self):
        """Max gap between events during tool round <= 5.5s."""
        clock_values = [
            0, 0, 0, 5.1, 5.1, 5.1, 10.2, 10.2, 10.2, 10.2, 10.2,
            10.2, 10.2, 15.3, 15.3, 15.3, 15.3, 15.3, 15.3,
        ]
        clock = ScriptedClock(clock_values)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        gaps = _max_gap(emitter.emit_times)
        self.assertLessEqual(
            gaps, 5.5,
            f"Max gap {gaps}s exceeds threshold + tolerance (5.5s). "
            f"emit_times={emitter.emit_times}",
        )

    def test_at_least_one_event_per_tool_round(self):
        """Each tool round has at least one thought.delta or tool_call.* event."""
        clock_values = [
            0, 0, 0, 5.1, 5.1, 5.1, 10.2, 10.2, 10.2, 10.2, 10.2,
            10.2, 10.2, 15.3, 15.3, 15.3, 15.3, 15.3, 15.3,
        ]
        clock = ScriptedClock(clock_values)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        # Split events by round (phase.changed marks round boundaries)
        phase_indices = [
            i for i, e in enumerate(events)
            if e.event_type == RunEventType.PHASE_CHANGED.value
        ]
        self.assertEqual(len(phase_indices), 2, "Expected 2 rounds")

        # Round 1 events (from first phase.changed to second phase.changed)
        round1_events = events[phase_indices[0]:phase_indices[1]]
        round1_has_event = any(
            e.event_type in (
                RunEventType.THOUGHT_DELTA.value,
                RunEventType.TOOL_CALL_STARTED_V3.value,
                RunEventType.TOOL_CALL_DELTA.value,
                RunEventType.TOOL_CALL_COMPLETED_V3.value,
            )
            for e in round1_events
        )
        self.assertTrue(round1_has_event,
            "Round 1 (tool round) must have at least one thought.delta or tool_call.* event")

        # Round 2 events (from second phase.changed to end)
        round2_events = events[phase_indices[1]:]
        round2_has_event = any(
            e.event_type in (
                RunEventType.THOUGHT_DELTA.value,
                RunEventType.MESSAGE_DELTA_V3.value,
                RunEventType.MESSAGE_COMPLETED.value,
            )
            for e in round2_events
        )
        self.assertTrue(round2_has_event,
            "Round 2 must have at least one thought.delta or message.* event")


# ---------------------------------------------------------------------------
# Scenario 3: Multi-round with delays — heartbeats in each round
# ---------------------------------------------------------------------------


class TestSilenceThresholdMultiRoundWithDelays(unittest.TestCase):
    """3 rounds, each with > threshold delay → heartbeats in each round."""

    def test_heartbeats_in_each_round(self):
        """Heartbeats are present in each of 3 rounds when delays exceed threshold."""
        from fixtures.turn_scripts import LEGAL_RESEARCH_3_ROUND

        # Clock values for 3-round scenario:
        # Each round has a heartbeat before the LLM call (clock advances by 5.1)
        # Round 1: 0 → 5.1 (heartbeat)
        # Round 2: 5.1 → 10.2 (heartbeat)
        # Round 3: 10.2 → 15.3 (heartbeat)
        clock_values = []
        t = 0.0
        for _round in range(3):
            # init/phase.changed/thought.delta at current time
            clock_values.extend([t, t, t])
            # maybe_heartbeat advances to t + 5.1 → heartbeat fires
            t += 5.1
            clock_values.extend([t, t])  # heartbeat check + heartbeat _emit
            # Tool call events (rounds 1-2) or content events (round 3) at t
            if _round < 2:
                # tool_call.started, maybe_heartbeat (no advance), tool_call.delta, tool_call.completed, thought
                clock_values.extend([t, t, t, t, t, t])
            else:
                # message.delta, message.completed, run.state_changed
                clock_values.extend([t, t, t])
        # Extra safety values
        clock_values.extend([t] * 10)

        clock = ScriptedClock(clock_values)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_3_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        # Heartbeats present
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat") is True]
        self.assertGreater(len(heartbeats), 0,
            "Expected heartbeat events in multi-round scenario")

        # Max gap within tolerance
        gaps = _max_gap(emitter.emit_times)
        self.assertLessEqual(
            gaps, 5.5,
            f"Max gap {gaps}s exceeds threshold + tolerance (5.5s). "
            f"emit_times={emitter.emit_times}",
        )


# ---------------------------------------------------------------------------
# Scenario 4: No delay (fast) — no heartbeats needed, no gaps > threshold
# ---------------------------------------------------------------------------


class TestSilenceThresholdFastNoHeartbeat(unittest.TestCase):
    """Fast operations: no heartbeats needed, no gaps > threshold."""

    def test_no_heartbeat_when_fast(self):
        """When all operations are fast (clock doesn't advance), no heartbeats."""
        # Clock stays at 0 — no time passes
        clock = ScriptedClock([0.0] * 20)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="fast answer"),
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
                run_id="run-silence",
            )
        ))

        # No heartbeat events
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat") is True]
        self.assertEqual(len(heartbeats), 0,
            "No heartbeat events expected when all operations are fast")

    def test_max_gap_zero_when_fast(self):
        """Max gap is 0 when clock doesn't advance."""
        clock = ScriptedClock([0.0] * 20)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="fast"),
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
                run_id="run-silence",
            )
        ))

        gaps = _max_gap(emitter.emit_times)
        self.assertEqual(gaps, 0.0,
            f"Max gap should be 0 when clock doesn't advance. "
            f"emit_times={emitter.emit_times}")

    def test_fast_multi_turn_no_heartbeat(self):
        """Fast multi-turn (tool round + content round) — no heartbeats."""
        clock = ScriptedClock([0.0] * 30)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        # No heartbeat events
        thought_deltas = [
            e for e in events
            if e.event_type == RunEventType.THOUGHT_DELTA.value
        ]
        heartbeats = [e for e in thought_deltas if e.metadata.get("heartbeat") is True]
        self.assertEqual(len(heartbeats), 0,
            "No heartbeat events expected in fast multi-turn scenario")

        # Tool call events still present (no silent rounds)
        started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3.value]
        self.assertGreater(len(started), 0, "Tool call events should be present")


# ---------------------------------------------------------------------------
# Scenario 5: Tool round has events (no silent rounds)
# ---------------------------------------------------------------------------


class TestNoSilentRounds(unittest.TestCase):
    """Every tool round has at least one thought.delta or tool_call.* event."""

    def test_tool_round_has_thought_and_tool_events(self):
        """Tool round emits thought.delta + tool_call.started|delta|completed."""
        clock = ScriptedClock([0.0] * 30)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = RecordingEmitter(
            "run-silence", config, monotonic_clock=clock,
        )

        provider = FixtureProvider(LEGAL_RESEARCH_2_ROUND)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-silence",
            )
        ))

        # Round 1 (tool round) must have thought.delta and tool_call.* events
        phase_indices = [
            i for i, e in enumerate(events)
            if e.event_type == RunEventType.PHASE_CHANGED.value
        ]
        self.assertEqual(len(phase_indices), 2)

        round1_events = events[phase_indices[0]:phase_indices[1]]
        round1_types = {e.event_type for e in round1_events}

        self.assertIn(RunEventType.THOUGHT_DELTA.value, round1_types,
            "Tool round must have thought.delta events")
        self.assertIn(RunEventType.TOOL_CALL_STARTED_V3.value, round1_types,
            "Tool round must have tool_call.started events")
        self.assertIn(RunEventType.TOOL_CALL_COMPLETED_V3.value, round1_types,
            "Tool round must have tool_call.completed events")


# ---------------------------------------------------------------------------
# Import asyncio at module level (needed for asyncio.run)
# ---------------------------------------------------------------------------

import asyncio


if __name__ == "__main__":
    unittest.main()
