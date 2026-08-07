"""E2E test: error recovery — tool failure + provider error + turn limit.

Verifies error recovery patterns in the turn loop:

1. Tool failure recovery: tool executor raises exception →
   tool_call.completed with status="error" → error appended as tool
   result → loop continues → round 2 LLM produces final content →
   run.state_changed to "succeeded"
2. Provider error: FixtureProvider with TurnScript(error=ConnectionError)
   → error event emitted → run.state_changed to "failed"
3. Turn limit exceeded: 15 rounds of tool calls, max_turns=10 → error
   with turn_limit_exceeded → run.state_changed to "failed"
4. Multiple tool failures then recovery: rounds 1-2 tool failures, round
   3 LLM produces final content → run.state_changed to "succeeded"

All tests use FixtureProvider (no external LLM).
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import ErrorCategory, RunEventType
from platform_contract.events import ErrorInfo, RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ToolCallDelta,
)
from inkstatute_agent_core.turn_loop import ToolResult, run_turn

from fixtures.turn_scripts import (
    MULTIPLE_FAILURES_THEN_RECOVERY,
    PROVIDER_ERROR_SCRIPT,
    TOOL_FAILURE_THEN_RECOVERY,
    make_turn_limit_scripts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events(gen) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


def _make_emitter(
    run_id: str = "run-err",
    config: AgentCoreConfig | None = None,
) -> EventEmitter:
    return EventEmitter(run_id, config or AgentCoreConfig())


# ---------------------------------------------------------------------------
# 1. Tool failure recovery
# ---------------------------------------------------------------------------


class TestE2EToolFailureRecovery(unittest.TestCase):
    """Tool failure → error event → loop continues → final content."""

    def test_tool_executor_returns_error_result(self):
        """ToolExecutor returns ToolResult with error → tool_call.completed status=error."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="connection timeout",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                    message="connection timeout",
                ),
            )

        provider = FixtureProvider(TOOL_FAILURE_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # tool_call.completed with status="error"
        completed = [
            e for e in events
            if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "error")
        self.assertIsNotNone(completed[0].payload["error"])

        # Loop continues — message.completed from round 2
        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ]
        self.assertEqual(len(msg_completed), 1)

        # Final state is "succeeded" (recovered)
        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(state_events[0].payload["status"], "succeeded")

    def test_tool_executor_raises_exception(self):
        """ToolExecutor raises exception → caught, error event, loop continues."""
        async def crashing_executor(tool_call_id, tool_name, arguments):
            raise RuntimeError("Tool crashed!")

        provider = FixtureProvider(TOOL_FAILURE_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # tool_call.completed with status="error"
        completed = [
            e for e in events
            if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["status"], "error")

        # Loop continues — message.completed from round 2
        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ]
        self.assertEqual(len(msg_completed), 1)

    def test_error_tool_result_appended_to_messages(self):
        """Error tool result is appended and provider is called again (loop continues)."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="connection refused",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                ),
            )

        provider = FixtureProvider(TOOL_FAILURE_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # Provider called twice (round 1: tool call, round 2: final content)
        self.assertEqual(provider.call_count, 2)

    def test_tool_failure_does_not_crash(self):
        """Tool failure does not crash the generator — it terminates cleanly."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            raise ValueError("bad arguments")

        provider = FixtureProvider(TOOL_FAILURE_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # Generator terminated cleanly (events collected without hanging)
        self.assertGreater(len(events), 0)


# ---------------------------------------------------------------------------
# 2. Provider error
# ---------------------------------------------------------------------------


class TestE2EProviderError(unittest.TestCase):
    """Provider exception → error event + run.state_changed to failed."""

    def test_provider_error_emits_error_event(self):
        """Provider raises ConnectionError → error event with provider_error code."""
        provider = FixtureProvider(PROVIDER_ERROR_SCRIPT)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        error_events = [
            e for e in events
            if e.event_type == RunEventType.ERROR.value
        ]
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].payload["error"]["code"], "provider_error")

    def test_provider_error_run_state_failed(self):
        """Provider error → run.state_changed to 'failed'."""
        provider = FixtureProvider(PROVIDER_ERROR_SCRIPT)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "failed")

    def test_provider_error_generator_stops(self):
        """Generator stops cleanly after provider error (no hang)."""
        provider = FixtureProvider([TurnScript(error=RuntimeError("model unavailable"))])
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        # Generator terminated cleanly
        self.assertGreater(len(events), 0)

    def test_provider_error_includes_usage_metadata(self):
        """Provider error event includes provider_usage in run.state_changed."""
        provider = FixtureProvider(PROVIDER_ERROR_SCRIPT)
        config = AgentCoreConfig()
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertIn("provider_usage", state_events[0].metadata)


# ---------------------------------------------------------------------------
# 3. Turn limit exceeded
# ---------------------------------------------------------------------------


class TestE2ETurnLimitExceeded(unittest.TestCase):
    """Turn limit enforcement: error with turn_limit_exceeded after max_turns."""

    def test_turn_limit_emits_error(self):
        """After max_turns rounds of tool calls, error with turn_limit_exceeded."""
        provider = FixtureProvider(make_turn_limit_scripts(15))
        config = AgentCoreConfig(max_turns=3)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        error_events = [
            e for e in events
            if e.event_type == RunEventType.ERROR.value
        ]
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].payload["error"]["code"], "turn_limit_exceeded")

    def test_turn_limit_run_state_failed(self):
        """Turn limit → run.state_changed to 'failed'."""
        provider = FixtureProvider(make_turn_limit_scripts(15))
        config = AgentCoreConfig(max_turns=3)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(len(state_events), 1)
        self.assertEqual(state_events[0].payload["status"], "failed")

    def test_turn_limit_provider_called_max_turns_times(self):
        """Provider is called exactly max_turns times before turn limit error."""
        provider = FixtureProvider(make_turn_limit_scripts(20))
        config = AgentCoreConfig(max_turns=5)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        self.assertEqual(provider.call_count, 5)

    def test_turn_limit_default_max_turns_10(self):
        """Default max_turns=10 is enforced."""
        provider = FixtureProvider(make_turn_limit_scripts(20))
        config = AgentCoreConfig()  # default max_turns=10
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        self.assertEqual(provider.call_count, 10)
        error_events = [
            e for e in events
            if e.event_type == RunEventType.ERROR.value
        ]
        self.assertEqual(len(error_events), 1)

    def test_turn_limit_error_message(self):
        """Turn limit error has the correct message."""
        provider = FixtureProvider(make_turn_limit_scripts(15))
        config = AgentCoreConfig(max_turns=2)
        emitter = _make_emitter(config=config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-err",
            )
        ))

        error_events = [
            e for e in events
            if e.event_type == RunEventType.ERROR.value
        ]
        self.assertIn("最大轮次", error_events[0].payload["error"]["message"])


# ---------------------------------------------------------------------------
# 4. Multiple tool failures then recovery
# ---------------------------------------------------------------------------


class TestE2EMultipleFailuresThenRecovery(unittest.TestCase):
    """Rounds 1-2 tool failures, round 3 LLM produces final content."""

    def test_multiple_failures_then_recovery_succeeds(self):
        """Two tool failures then LLM produces content → run.state_changed to succeeded."""
        call_count = [0]

        async def failing_executor(tool_call_id, tool_name, arguments):
            call_count[0] += 1
            return ToolResult(
                content=f"Tool {tool_name} failed (attempt {call_count[0]})",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                    message=f"{tool_name} unavailable",
                ),
            )

        provider = FixtureProvider(MULTIPLE_FAILURES_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # Two tool_call.completed with status="error"
        completed = [
            e for e in events
            if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3.value
        ]
        self.assertEqual(len(completed), 2)
        for c in completed:
            self.assertEqual(c.payload["status"], "error")

        # Final state is "succeeded" (LLM recovered)
        state_events = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ]
        self.assertEqual(state_events[0].payload["status"], "succeeded")

        # Provider called 3 times (3 rounds)
        self.assertEqual(provider.call_count, 3)

    def test_multiple_failures_message_completed_has_content(self):
        """After multiple failures, final message.completed has content."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="failed",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                ),
            )

        provider = FixtureProvider(MULTIPLE_FAILURES_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ]
        self.assertEqual(len(msg_completed), 1)
        self.assertIn("合同法", msg_completed[0].payload["content"])

    def test_multiple_failures_seq_monotonicity(self):
        """seq values are strictly increasing even with multiple failures."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="failed",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                ),
            )

        provider = FixtureProvider(MULTIPLE_FAILURES_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        seqs = [e.seq for e in events]
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1])


# ---------------------------------------------------------------------------
# 5. Error recovery with reasoning (LLM sees error and adapts)
# ---------------------------------------------------------------------------


class TestE2EErrorRecoveryWithReasoning(unittest.TestCase):
    """LLM sees error results and adapts its response."""

    def test_llm_sees_error_and_produces_alternative(self):
        """LLM produces content mentioning the error and an alternative approach."""
        async def failing_executor(tool_call_id, tool_name, arguments):
            return ToolResult(
                content="search service unavailable",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="tool_failed",
                    message="service unavailable",
                ),
            )

        provider = FixtureProvider(TOOL_FAILURE_THEN_RECOVERY)
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
                run_id="run-err",
            )
        ))

        # The final content should mention the tool was unavailable
        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ][0]
        content = msg_completed.payload["content"]
        self.assertIn("不可用", content)


if __name__ == "__main__":
    unittest.main()
