"""Tests for InProcessAgentCoreAdapter — BackendAdapter 9-method Protocol.

All tests use FixtureProvider — no external LLM calls.  Covers all 9
BackendAdapter methods: backend_id, capabilities, bootstrap_check,
submit_run, get_run, stream_events, cancel_run, submit_approval,
collect_artifacts.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn, Artifact
from platform_contract.enums import ArtifactKind
from platform_runtime.protocols import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    RunHandle,
    RunRequest,
    SolutionBinding,
)

from inkstatute_agent_core.backend_adapter import InProcessAgentCoreAdapter
from inkstatute_agent_core.backend_config import AgentCoreBackendConfig
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(content: str = "请帮我分析这份合同的风险") -> RunRequest:
    """Construct a minimal RunRequest for testing."""
    return RunRequest(
        turn=AgentTurn(
            turn_id="t1",
            conversation_id="c1",
            channel=Channel.WEB,
            user_id="u1",
            message_type=MessageType.TEXT,
            received_at="2026-01-01T00:00:00Z",
            content=content,
        ),
        solution=SolutionBinding(solution_id="s1"),
    )


def _make_simple_provider() -> FixtureProvider:
    """A FixtureProvider that produces a single content turn (no tools)."""
    return FixtureProvider([
        TurnScript(deltas=[
            ContentDelta(content="根据分析，"),
            ContentDelta(content="该合同存在以下风险..."),
            UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
            FinishDelta(finish_reason="stop"),
        ]),
    ])


def _make_thought_provider() -> FixtureProvider:
    """A FixtureProvider that produces reasoning + content."""
    return FixtureProvider([
        TurnScript(deltas=[
            ReasoningDelta(reasoning="正在思考合同条款..."),
            ContentDelta(content="分析完成。"),
            FinishDelta(finish_reason="stop"),
        ]),
    ])


def _make_tool_call_provider() -> FixtureProvider:
    """A FixtureProvider that produces a tool call then a content turn."""
    return FixtureProvider([
        TurnScript(deltas=[
            ToolCallDelta(
                tool_call_id="tc-001",
                tool_name="regulation_search",
                arguments='{"query": "合同法"}',
            ),
            FinishDelta(finish_reason="tool_calls"),
        ]),
        TurnScript(deltas=[
            ContentDelta(content="根据检索结果，"),
            ContentDelta(content="合同风险如下..."),
            FinishDelta(finish_reason="stop"),
        ]),
    ])


def _make_config(
    provider: FixtureProvider | None = None,
    **kwargs,
) -> AgentCoreBackendConfig:
    """Construct an AgentCoreBackendConfig with a FixtureProvider."""
    p = provider or _make_simple_provider()
    return AgentCoreBackendConfig(
        config=AgentCoreConfig(max_turns=5, silence_threshold_seconds=999),
        provider_factory=lambda: p,
        **kwargs,
    )


async def _collect_events(adapter: InProcessAgentCoreAdapter, run_id: str, timeout: float = 10.0) -> list:
    """Collect all events from stream_events with a timeout."""
    events: list = []
    try:
        async with asyncio.timeout(timeout):
            async for event in adapter.stream_events(run_id):
                events.append(event)
    except (asyncio.TimeoutError, TimeoutError):
        pass
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInProcessAgentCoreAdapter(unittest.IsolatedAsyncioTestCase):
    """Tests for all 9 BackendAdapter methods."""

    adapter: InProcessAgentCoreAdapter | None = None

    async def asyncTearDown(self) -> None:
        if self.adapter is not None:
            try:
                await self.adapter.shutdown()
            except Exception:
                pass
            self.adapter = None

    # (1) test_backend_id_returns_inkstatute
    def test_backend_id_returns_inkstatute(self) -> None:
        """backend_id() returns 'inkstatute'."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        self.assertEqual(self.adapter.backend_id(), "inkstatute")

    # (2) test_capabilities_declares_streaming_cancel_approval
    def test_capabilities_declares_streaming_cancel_approval(self) -> None:
        """capabilities() declares stream_event_support, cancel_support, approval_support."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        caps = self.adapter.capabilities()
        self.assertIsInstance(caps, AdapterCapabilitySet)
        self.assertTrue(caps.stream_event_support)
        self.assertTrue(caps.cancel_support)
        self.assertTrue(caps.approval_support)
        self.assertTrue(caps.session_memory_support)

    # (3) test_capabilities_does_not_declare_fs_or_terminal
    def test_capabilities_does_not_declare_fs_or_terminal(self) -> None:
        """capabilities() does NOT declare fs/* or terminal/* capabilities."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        caps = self.adapter.capabilities()
        # hook_event_support should not contain fs/* or terminal/*
        for hook in caps.hook_event_support:
            self.assertFalse(hook.startswith("fs/"), f"unexpected fs/ capability: {hook}")
            self.assertFalse(hook.startswith("terminal/"), f"unexpected terminal/ capability: {hook}")
        # run_invocation_modes should not contain terminal or execute_code
        for mode in caps.run_invocation_modes:
            self.assertNotIn("terminal", mode)
            self.assertNotIn("execute_code", mode)

    # (4) test_bootstrap_check_success
    async def test_bootstrap_check_success(self) -> None:
        """bootstrap_check returns BootstrapStatus with ok=True when provider is available."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        status = await self.adapter.bootstrap_check()
        self.assertIsInstance(status, BootstrapStatus)
        self.assertTrue(status.ok)
        self.assertEqual(status.backend_id, "inkstatute")
        self.assertEqual(len(status.issues), 0)
        self.assertEqual(status.metadata.get("entry_point"), "in_process")
        self.assertIn("model_name", status.metadata)

    # (5) test_bootstrap_check_failure_when_provider_unavailable
    async def test_bootstrap_check_failure_when_provider_unavailable(self) -> None:
        """bootstrap_check returns ok=False when provider_factory raises."""
        def _bad_factory():
            raise RuntimeError("no API key configured")

        config = AgentCoreBackendConfig(
            config=AgentCoreConfig(),
            provider_factory=_bad_factory,
        )
        self.adapter = InProcessAgentCoreAdapter(config)
        status = await self.adapter.bootstrap_check()
        self.assertFalse(status.ok)
        self.assertEqual(status.backend_id, "inkstatute")
        self.assertGreater(len(status.issues), 0)
        self.assertIn("provider_unavailable", status.issues[0])

    # (6) test_submit_run_returns_handle_with_running_status
    async def test_submit_run_returns_handle_with_running_status(self) -> None:
        """submit_run returns RunHandle with non-empty run_id and RUNNING status."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        self.assertIsInstance(handle, RunHandle)
        self.assertTrue(handle.run_id)
        self.assertEqual(handle.status, AsyncTaskState.RUNNING)
        self.assertEqual(handle.metadata.get("backend_id"), "inkstatute")
        self.assertEqual(handle.metadata.get("entry_point"), "in_process")

    # (7) test_get_run_after_submit
    async def test_get_run_after_submit(self) -> None:
        """get_run returns Run with correct run_id and RUNNING status."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        run = await self.adapter.get_run(handle.run_id)
        self.assertEqual(run.run_id, handle.run_id)
        self.assertEqual(run.status, AsyncTaskState.RUNNING)
        self.assertEqual(run.turn_id, "t1")
        self.assertEqual(run.solution_id, "s1")

    # (8) test_get_run_unknown_raises_keyerror
    async def test_get_run_unknown_raises_keyerror(self) -> None:
        """get_run with unknown run_id raises KeyError."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        with self.assertRaises(KeyError):
            await self.adapter.get_run("nonexistent-run")

    # (9) test_stream_events_yields_message_delta
    async def test_stream_events_yields_message_delta(self) -> None:
        """stream_events yields at least one message.delta event."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("message.delta", event_types)

    # (10) test_stream_events_yields_message_completed
    async def test_stream_events_yields_message_completed(self) -> None:
        """stream_events yields at least one message.completed event."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("message.completed", event_types)

    # (11) test_stream_events_yields_thought_delta
    async def test_stream_events_yields_thought_delta(self) -> None:
        """stream_events yields at least one thought.delta event."""
        self.adapter = InProcessAgentCoreAdapter(_make_config(_make_thought_provider()))
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("thought.delta", event_types)

    # (12) test_stream_events_yields_tool_call_events
    async def test_stream_events_yields_tool_call_events(self) -> None:
        """stream_events yields tool_call.started and tool_call.completed events."""
        self.adapter = InProcessAgentCoreAdapter(_make_config(_make_tool_call_provider()))
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("tool_call.started", event_types)
        self.assertIn("tool_call.completed", event_types)

    # (13) test_stream_events_completes_with_terminal_state
    async def test_stream_events_completes_with_terminal_state(self) -> None:
        """stream_events completes and the run reaches SUCCEEDED status."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        # Should have run.state_changed to succeeded
        state_events = [e for e in events if e.event_type == "run.state_changed"]
        self.assertTrue(any(e.payload.get("status") == "succeeded" for e in state_events))
        # Run status should be SUCCEEDED
        run = await self.adapter.get_run(handle.run_id)
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)

    # (14) test_cancel_run_emits_state_changed
    async def test_cancel_run_emits_state_changed(self) -> None:
        """cancel_run cancels the background task and emits run.state_changed to cancelled."""
        # Use a provider with delay so we can cancel before completion
        provider = FixtureProvider([
            TurnScript(
                deltas=[ContentDelta(content="正在分析...")],
                delay_seconds=2.0,
            ),
        ])
        self.adapter = InProcessAgentCoreAdapter(_make_config(provider))
        handle = await self.adapter.submit_run(_make_request())
        # Cancel immediately
        cancelled = await self.adapter.cancel_run(handle.run_id)
        self.assertEqual(cancelled.status, AsyncTaskState.CANCELLED)
        # Collect remaining events — should include run.state_changed to cancelled
        events = await _collect_events(self.adapter, handle.run_id)
        state_events = [e for e in events if e.event_type == "run.state_changed"]
        self.assertTrue(any(e.payload.get("status") == "cancelled" for e in state_events))

    # (15) test_cancel_run_unknown_raises_keyerror
    async def test_cancel_run_unknown_raises_keyerror(self) -> None:
        """cancel_run with unknown run_id raises KeyError."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        with self.assertRaises(KeyError):
            await self.adapter.cancel_run("nonexistent-run")

    # (16) test_submit_approval_rejects_terminal
    async def test_submit_approval_rejects_terminal(self) -> None:
        """submit_approval with terminal permission and decision='approved' is rejected."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        approval = Approval(
            approval_id="a1",
            decision="approved",
            metadata={"kind": "terminal"},
        )
        result = await self.adapter.submit_approval(handle.run_id, approval)
        self.assertEqual(result.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertFalse(result.metadata.get("approval_decision_recorded", True))
        self.assertIn("approval_rejected", result.metadata)

    # (17) test_submit_approval_rejects_execute_code
    async def test_submit_approval_rejects_execute_code(self) -> None:
        """submit_approval with execute_code permission and decision='approved' is rejected."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        approval = Approval(
            approval_id="a2",
            decision="approved",
            metadata={"kind": "execute_code"},
        )
        result = await self.adapter.submit_approval(handle.run_id, approval)
        self.assertEqual(result.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertFalse(result.metadata.get("approval_decision_recorded", True))

    # (18) test_submit_approval_accepts_safe_permission
    async def test_submit_approval_accepts_safe_permission(self) -> None:
        """submit_approval with a safe permission kind is accepted."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        approval = Approval(
            approval_id="a3",
            decision="approved",
            metadata={"kind": "read_file"},
        )
        result = await self.adapter.submit_approval(handle.run_id, approval)
        self.assertNotEqual(result.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertTrue(result.metadata.get("approval_decision_recorded", False))
        self.assertEqual(result.metadata.get("approval_decision"), "approved")

    # (19) test_collect_artifacts_empty_when_no_artifacts
    async def test_collect_artifacts_empty_when_no_artifacts(self) -> None:
        """collect_artifacts returns an empty list when no artifacts were produced."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        # Wait for completion
        await _collect_events(self.adapter, handle.run_id)
        artifacts = await self.adapter.collect_artifacts(handle.run_id)
        self.assertIsInstance(artifacts, list)
        self.assertEqual(len(artifacts), 0)

    # (20) test_collect_artifacts_returns_artifact_records
    async def test_collect_artifacts_returns_artifact_records(self) -> None:
        """collect_artifacts returns ArtifactRecord list when artifacts were produced."""
        # Use a tool executor that emits an artifact via the emitter side channel
        from inkstatute_agent_core.turn_loop import ToolResult

        def _make_tool_executor():
            async def _executor(tool_call_id: str, tool_name: str, args: dict) -> ToolResult:
                return ToolResult(content="document generated", metadata={})
            return _executor

        # We need a provider that does a tool call, then the tool emits an artifact.
        # But our tool executor doesn't have access to the emitter.
        # Instead, let's manually inject an artifact event after the run.
        self.adapter = InProcessAgentCoreAdapter(_make_config(_make_tool_call_provider()))
        handle = await self.adapter.submit_run(_make_request())
        # Wait for completion
        await _collect_events(self.adapter, handle.run_id)
        # Manually add an artifact record to verify collect_artifacts returns it
        # (This tests the collect_artifacts method itself; the _collect_artifact
        #  internal method is tested via the artifact.created event path.)
        self.adapter._artifacts[handle.run_id].append(
            ArtifactRecord(
                artifact_id="art-001",
                kind="docx",
                uri_ref="file:///tmp/report.docx",
                name="合同审查报告.docx",
            )
        )
        artifacts = await self.adapter.collect_artifacts(handle.run_id)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].artifact_id, "art-001")
        self.assertEqual(artifacts[0].kind, "docx")
        self.assertEqual(artifacts[0].uri_ref, "file:///tmp/report.docx")

    # (21) test_submit_run_with_fixture_provider_no_external_calls
    async def test_submit_run_with_fixture_provider_no_external_calls(self) -> None:
        """submit_run with FixtureProvider completes without external LLM calls."""
        provider = _make_simple_provider()
        self.adapter = InProcessAgentCoreAdapter(_make_config(provider))
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        # Should have completed successfully
        self.assertGreater(len(events), 0)
        self.assertEqual(provider.call_count, 1)
        # Verify no external calls — the fixture provider tracks call_count
        # and would raise if script exhausted
        self.assertEqual(provider.remaining_scripts, 0)

    # (22) test_event_seq_is_monotonic
    async def test_event_seq_is_monotonic(self) -> None:
        """Event seq numbers are strictly monotonically increasing."""
        self.adapter = InProcessAgentCoreAdapter(_make_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await _collect_events(self.adapter, handle.run_id)
        seqs = [e.seq for e in events]
        # Check strictly increasing
        for i in range(1, len(seqs)):
            self.assertGreater(seqs[i], seqs[i - 1],
                               f"seq not monotonic at index {i}: {seqs}")
        # First seq should be 0
        self.assertEqual(seqs[0], 0)

    # (23) test_concurrent_runs_have_independent_event_streams
    async def test_concurrent_runs_have_independent_event_streams(self) -> None:
        """Two concurrent runs have independent event streams with distinct run_ids."""
        # Each provider_factory call must return a fresh provider so
        # concurrent runs don't share script state.
        def _factory():
            return _make_simple_provider()

        config = AgentCoreBackendConfig(
            config=AgentCoreConfig(max_turns=5, silence_threshold_seconds=999),
            provider_factory=_factory,
        )
        self.adapter = InProcessAgentCoreAdapter(config)

        handle1 = await self.adapter.submit_run(_make_request("问题一"))
        handle2 = await self.adapter.submit_run(_make_request("问题二"))

        self.assertNotEqual(handle1.run_id, handle2.run_id)

        # Collect events from both runs concurrently
        events1_task = asyncio.create_task(_collect_events(self.adapter, handle1.run_id))
        events2_task = asyncio.create_task(_collect_events(self.adapter, handle2.run_id))
        events1 = await events1_task
        events2 = await events2_task

        # Both should have events
        self.assertGreater(len(events1), 0)
        self.assertGreater(len(events2), 0)

        # Events from run1 should all have run_id == handle1.run_id
        for e in events1:
            self.assertEqual(e.run_id, handle1.run_id)
        # Events from run2 should all have run_id == handle2.run_id
        for e in events2:
            self.assertEqual(e.run_id, handle2.run_id)

        # Both should reach succeeded
        run1 = await self.adapter.get_run(handle1.run_id)
        run2 = await self.adapter.get_run(handle2.run_id)
        self.assertEqual(run1.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run2.status, AsyncTaskState.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
