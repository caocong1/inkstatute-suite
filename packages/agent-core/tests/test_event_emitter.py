"""Tests for EventEmitter — seq monotonicity, convenience methods, heartbeat."""

from __future__ import annotations

import unittest

from platform_contract.enums import ErrorCategory, RunEventType
from platform_contract.events import ErrorInfo, RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter


# ---------------------------------------------------------------------------
# Helpers for deterministic testing
# ---------------------------------------------------------------------------

class FakeClock:
    """Returns incrementing ISO timestamps for deterministic testing."""

    def __init__(self, start: str = "2026-01-01T00:00:00+00:00"):
        self._tick = 0
        self._start = start

    def __call__(self) -> str:
        # Return a deterministic timestamp that increments
        result = f"2026-01-01T00:00:{self._tick:02d}+00:00"
        self._tick += 1
        return result


class FakeMonotonicClock:
    """Returns controlled monotonic values for silence threshold testing."""

    def __init__(self, start: float = 0.0):
        self._current = start

    def __call__(self) -> float:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current += seconds


# ---------------------------------------------------------------------------
# Seq monotonicity tests
# ---------------------------------------------------------------------------

class TestSeqMonotonicity(unittest.TestCase):
    """EventEmitter assigns strictly monotonic seq starting from 0."""

    def test_first_event_has_seq_0(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("thinking")
        self.assertEqual(event.seq, 0)

    def test_seq_strictly_increasing(self):
        emitter = EventEmitter("run-1")
        seqs = []
        for i in range(5):
            event = emitter.emit_thought_delta(f"thought {i}")
            seqs.append(event.seq)
        self.assertEqual(seqs, [0, 1, 2, 3, 4])

    def test_seq_increments_across_different_event_types(self):
        emitter = EventEmitter("run-1")
        e0 = emitter.emit_thought_delta("thinking")
        e1 = emitter.emit_message_delta("hello", "msg-1")
        e2 = emitter.emit_tool_call_started("tc-1", "search")
        e3 = emitter.emit_message_completed("done", "msg-1")
        self.assertEqual(e0.seq, 0)
        self.assertEqual(e1.seq, 1)
        self.assertEqual(e2.seq, 2)
        self.assertEqual(e3.seq, 3)

    def test_seq_property_reflects_next_seq(self):
        emitter = EventEmitter("run-1")
        emitter.emit_thought_delta("a")
        emitter.emit_thought_delta("b")
        self.assertEqual(emitter.seq, 2)


# ---------------------------------------------------------------------------
# RunEvent construction tests
# ---------------------------------------------------------------------------

class TestRunEventConstruction(unittest.TestCase):
    """Each convenience method produces a RunEvent with correct event_type and payload."""

    def test_all_events_are_run_event_instances(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("test")
        self.assertIsInstance(event, RunEvent)

    def test_event_has_uuid_event_id(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("test")
        self.assertIsNotNone(event.event_id)
        self.assertIsInstance(event.event_id, str)
        # UUID strings have 36 chars with hyphens
        self.assertEqual(len(event.event_id), 36)

    def test_event_has_run_id(self):
        emitter = EventEmitter("run-abc")
        event = emitter.emit_thought_delta("test")
        self.assertEqual(event.run_id, "run-abc")

    def test_event_has_occurred_at(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("test")
        self.assertIsNotNone(event.occurred_at)
        self.assertIsInstance(event.occurred_at, str)

    def test_event_has_payload_dict(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("thinking hard")
        self.assertIsNotNone(event.payload)
        self.assertIsInstance(event.payload, dict)
        self.assertEqual(event.payload["delta"], "thinking hard")


# ---------------------------------------------------------------------------
# Convenience method tests
# ---------------------------------------------------------------------------

class TestEmitMessageDelta(unittest.TestCase):
    def test_event_type_is_message_delta(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_message_delta("hello", "msg-1")
        self.assertEqual(event.event_type, RunEventType.MESSAGE_DELTA_V3.value)

    def test_payload_has_delta_and_message_id(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_message_delta("hello world", "msg-1")
        self.assertEqual(event.payload["delta"], "hello world")
        self.assertEqual(event.payload["message_id"], "msg-1")

    def test_optional_message_id(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_message_delta("text")
        self.assertEqual(event.payload["delta"], "text")
        self.assertIsNone(event.payload["message_id"])


class TestEmitMessageCompleted(unittest.TestCase):
    def test_event_type_is_message_completed(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_message_completed("final text", "msg-1")
        self.assertEqual(event.event_type, RunEventType.MESSAGE_COMPLETED.value)

    def test_payload_has_content(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_message_completed("final text", "msg-1")
        self.assertEqual(event.payload["content"], "final text")
        self.assertEqual(event.payload["message_id"], "msg-1")


class TestEmitThoughtDelta(unittest.TestCase):
    def test_event_type_is_thought_delta(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("reasoning...")
        self.assertEqual(event.event_type, RunEventType.THOUGHT_DELTA.value)

    def test_payload_has_delta(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("reasoning...")
        self.assertEqual(event.payload["delta"], "reasoning...")


class TestEmitToolCallStarted(unittest.TestCase):
    def test_event_type_is_tool_call_started(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_started("tc-1", "legal_search")
        self.assertEqual(event.event_type, RunEventType.TOOL_CALL_STARTED_V3.value)

    def test_payload_has_tool_call_id_and_name(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_started(
            "tc-1", "legal_search", kind="retrieval", title="法规检索"
        )
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["tool_name"], "legal_search")
        self.assertEqual(event.payload["kind"], "retrieval")
        self.assertEqual(event.payload["title"], "法规检索")


class TestEmitToolCallDelta(unittest.TestCase):
    def test_event_type_is_tool_call_delta(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_delta("tc-1", content="searching...")
        self.assertEqual(event.event_type, RunEventType.TOOL_CALL_DELTA.value)

    def test_payload_has_content_and_status(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_delta(
            "tc-1", content="found 3 results", status="running"
        )
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["content"], "found 3 results")
        self.assertEqual(event.payload["status"], "running")


class TestEmitToolCallCompleted(unittest.TestCase):
    def test_event_type_is_tool_call_completed(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_completed("tc-1", "succeeded", content="result")
        self.assertEqual(event.event_type, RunEventType.TOOL_CALL_COMPLETED_V3.value)

    def test_payload_has_status_and_content(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_tool_call_completed(
            "tc-1", "succeeded", content="result text",
            file_locations=["/path/to/file"],
        )
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["status"], "succeeded")
        self.assertEqual(event.payload["content"], "result text")
        self.assertEqual(event.payload["file_locations"], ["/path/to/file"])

    def test_payload_with_error(self):
        emitter = EventEmitter("run-1")
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="tool_failed",
            message="Tool execution failed",
        )
        event = emitter.emit_tool_call_completed(
            "tc-1", "failed", error=error
        )
        self.assertEqual(event.payload["status"], "failed")
        self.assertIsNotNone(event.payload["error"])
        self.assertEqual(event.payload["error"]["code"], "tool_failed")


class TestEmitPhaseChanged(unittest.TestCase):
    def test_event_type_is_phase_changed(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_phase_changed("research", "intake")
        self.assertEqual(event.event_type, RunEventType.PHASE_CHANGED.value)

    def test_payload_has_phase_and_previous(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_phase_changed("draft", "research")
        self.assertEqual(event.payload["phase"], "draft")
        self.assertEqual(event.payload["previous_phase"], "research")

    def test_payload_without_previous(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_phase_changed("research")
        self.assertEqual(event.payload["phase"], "research")
        self.assertIsNone(event.payload["previous_phase"])


class TestEmitRunStateChanged(unittest.TestCase):
    def test_event_type_is_run_state_changed(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_run_state_changed("succeeded", "running")
        self.assertEqual(event.event_type, RunEventType.RUN_STATE_CHANGED.value)

    def test_payload_has_status_and_previous(self):
        emitter = EventEmitter("run-1")
        event = emitter.emit_run_state_changed("succeeded", "running")
        self.assertEqual(event.payload["status"], "succeeded")
        self.assertEqual(event.payload["previous_status"], "running")

    def test_provider_usage_in_metadata(self):
        """emit_run_state_changed includes provider_usage in metadata when provided."""
        emitter = EventEmitter("run-1")
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        event = emitter.emit_run_state_changed(
            "succeeded", "running", metadata={"provider_usage": usage}
        )
        self.assertIn("provider_usage", event.metadata)
        self.assertEqual(event.metadata["provider_usage"], usage)

    def test_payload_with_error(self):
        emitter = EventEmitter("run-1")
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="turn_limit_exceeded",
            message="达到最大轮次上限",
        )
        event = emitter.emit_run_state_changed("failed", "running", error=error)
        self.assertEqual(event.payload["status"], "failed")
        self.assertIsNotNone(event.payload["error"])
        self.assertEqual(event.payload["error"]["code"], "turn_limit_exceeded")


class TestEmitError(unittest.TestCase):
    def test_event_type_is_error(self):
        emitter = EventEmitter("run-1")
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="something_went_wrong",
            message="An error occurred",
        )
        event = emitter.emit_error(error)
        self.assertEqual(event.event_type, RunEventType.ERROR.value)

    def test_payload_has_error_info(self):
        """emit_error produces an ErrorEventPayload with the ErrorInfo."""
        emitter = EventEmitter("run-1")
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="something_went_wrong",
            message="An error occurred",
        )
        event = emitter.emit_error(error)
        self.assertIsNotNone(event.payload)
        self.assertIn("error", event.payload)
        self.assertEqual(event.payload["error"]["code"], "something_went_wrong")
        self.assertEqual(event.payload["error"]["message"], "An error occurred")


# ---------------------------------------------------------------------------
# Heartbeat tests
# ---------------------------------------------------------------------------

class TestHeartbeat(unittest.TestCase):
    """maybe_heartbeat() emits heartbeat thought.delta when silence > threshold."""

    def test_heartbeat_emitted_when_threshold_exceeded(self):
        """emit_thought_delta with metadata={"heartbeat": true} is produced by maybe_heartbeat()."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        # Emit an event at t=0
        emitter.emit_thought_delta("initial thought")
        self.assertEqual(clock(), 0.0)  # last_event_time is 0

        # Advance past threshold
        clock.advance(6.0)
        heartbeat = emitter.maybe_heartbeat("正在检索...")
        self.assertIsNotNone(heartbeat)
        self.assertEqual(heartbeat.event_type, RunEventType.THOUGHT_DELTA.value)
        self.assertEqual(heartbeat.payload["delta"], "正在检索...")
        self.assertTrue(heartbeat.metadata.get("heartbeat"))

    def test_heartbeat_returns_none_within_threshold(self):
        """maybe_heartbeat() returns None when within threshold."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        emitter.emit_thought_delta("initial thought")
        clock.advance(3.0)  # within threshold
        heartbeat = emitter.maybe_heartbeat()
        self.assertIsNone(heartbeat)

    def test_heartbeat_at_exact_threshold_returns_none(self):
        """At exactly the threshold, no heartbeat (elapsed <= threshold)."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        emitter.emit_thought_delta("initial")
        clock.advance(5.0)  # exactly at threshold
        heartbeat = emitter.maybe_heartbeat()
        self.assertIsNone(heartbeat)

    def test_heartbeat_uses_custom_heartbeat_metadata_key(self):
        """Heartbeat metadata key is configurable via AgentCoreConfig."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(
            silence_threshold_seconds=5.0,
            heartbeat_metadata_key="hb",
        )
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        emitter.emit_thought_delta("initial")
        clock.advance(6.0)
        heartbeat = emitter.maybe_heartbeat("still working")
        self.assertIsNotNone(heartbeat)
        self.assertTrue(heartbeat.metadata.get("hb"))
        self.assertNotIn("heartbeat", heartbeat.metadata)

    def test_heartbeat_increments_seq(self):
        """Heartbeat events also get monotonic seq numbers."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        e0 = emitter.emit_thought_delta("first")  # seq=0
        clock.advance(6.0)
        hb = emitter.maybe_heartbeat("heartbeat")  # seq=1
        self.assertIsNotNone(hb)
        self.assertEqual(e0.seq, 0)
        self.assertEqual(hb.seq, 1)

    def test_heartbeat_updates_last_event_time(self):
        """After a heartbeat, last_event_time is updated."""
        clock = FakeMonotonicClock(start=0.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=clock)

        emitter.emit_thought_delta("initial")
        clock.advance(6.0)
        emitter.maybe_heartbeat("heartbeat")
        # Now within threshold again
        clock.advance(2.0)
        hb2 = emitter.maybe_heartbeat()
        self.assertIsNone(hb2)


# ---------------------------------------------------------------------------
# Injectable clock tests
# ---------------------------------------------------------------------------

class TestInjectableClocks(unittest.TestCase):
    """Injectable clocks work for deterministic testing."""

    def test_fixed_timestamp_clock(self):
        fixed_clock = FakeClock()
        emitter = EventEmitter("run-1", clock=fixed_clock)

        e0 = emitter.emit_thought_delta("first")
        e1 = emitter.emit_thought_delta("second")

        self.assertEqual(e0.occurred_at, "2026-01-01T00:00:00+00:00")
        self.assertEqual(e1.occurred_at, "2026-01-01T00:00:01+00:00")

    def test_fixed_monotonic_clock(self):
        mono = FakeMonotonicClock(start=100.0)
        config = AgentCoreConfig(silence_threshold_seconds=5.0)
        emitter = EventEmitter("run-1", config, monotonic_clock=mono)

        emitter.emit_thought_delta("initial")
        self.assertEqual(emitter.last_event_time, 100.0)

        mono.advance(3.0)
        self.assertIsNone(emitter.maybe_heartbeat())

        mono.advance(3.0)  # total 6.0 > 5.0
        hb = emitter.maybe_heartbeat()
        self.assertIsNotNone(hb)

    def test_default_clocks_work_without_injection(self):
        """Without injection, real clocks are used."""
        emitter = EventEmitter("run-1")
        event = emitter.emit_thought_delta("test")
        self.assertIsNotNone(event.occurred_at)
        self.assertGreaterEqual(emitter.last_event_time, 0.0)


# ---------------------------------------------------------------------------
# Event ordering tests
# ---------------------------------------------------------------------------

class TestEventOrdering(unittest.TestCase):
    """Events maintain correct ordering (tool_call.started before completed, etc.)."""

    def test_tool_call_started_before_completed(self):
        emitter = EventEmitter("run-1")
        started = emitter.emit_tool_call_started("tc-1", "search")
        delta = emitter.emit_tool_call_delta("tc-1", content="running")
        completed = emitter.emit_tool_call_completed("tc-1", "succeeded", content="done")
        self.assertLess(started.seq, delta.seq)
        self.assertLess(delta.seq, completed.seq)

    def test_message_delta_before_completed(self):
        emitter = EventEmitter("run-1")
        d1 = emitter.emit_message_delta("hello", "msg-1")
        d2 = emitter.emit_message_delta(" world", "msg-1")
        final = emitter.emit_message_completed("hello world", "msg-1")
        self.assertLess(d1.seq, d2.seq)
        self.assertLess(d2.seq, final.seq)


if __name__ == "__main__":
    unittest.main()
