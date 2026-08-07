"""Integration tests for ACPBackendAdapter — BackendAdapter 9-method Protocol.

All tests use the in-repo echo agent fixture — no network, no external agents.
"""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from platform_contract.agent_adapter import AdapterCapabilitySet, BackendProcessMode
from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime.protocols import (
    Approval,
    BootstrapStatus,
    RunHandle,
    RunRequest,
    SolutionBinding,
)

from inkstatute_acp_client.adapter import (
    ACPBackendAdapter,
    ACPBackendConfig,
    HERMES_COMPATIBILITY_MATRIX,
    check_hermes_compatibility,
    create_hermes_adapter,
)
from inkstatute_acp_client.capability_negotiation import RequiredCapabilities

ECHO_AGENT = str(Path(__file__).resolve().parent / "fixtures" / "echo_agent.py")


def _make_request(content: str = "hello world") -> RunRequest:
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


def _make_echo_config(
    backend_id: str = "echo",
    required: RequiredCapabilities | None = None,
) -> ACPBackendConfig:
    """Construct an ACPBackendConfig pointing at the echo agent fixture."""
    return ACPBackendConfig(
        backend_id=backend_id,
        command=("python", ECHO_AGENT),
        required_capabilities=required or RequiredCapabilities(streaming=True),
    )


class TestACPBackendAdapter(unittest.IsolatedAsyncioTestCase):
    """Integration tests using the in-repo echo agent fixture."""

    adapter: ACPBackendAdapter | None = None

    async def asyncTearDown(self) -> None:
        if self.adapter is not None:
            try:
                await self.adapter.shutdown()
            except Exception:
                pass
            self.adapter = None

    # (1) test_backend_id
    def test_backend_id(self) -> None:
        """adapter.backend_id() returns the configured backend_id string."""
        self.adapter = ACPBackendAdapter(_make_echo_config(backend_id="echo"))
        self.assertEqual(self.adapter.backend_id(), "echo")

    # (2) test_capabilities_default
    def test_capabilities_default(self) -> None:
        """adapter.capabilities() returns AdapterCapabilitySet with stream_event_support=True."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        caps = self.adapter.capabilities()
        self.assertIsInstance(caps, AdapterCapabilitySet)
        self.assertTrue(caps.stream_event_support)

    # (3) test_bootstrap_check_success
    async def test_bootstrap_check_success(self) -> None:
        """bootstrap_check returns BootstrapStatus with ok=True and correct metadata."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        status = await self.adapter.bootstrap_check()
        self.assertIsInstance(status, BootstrapStatus)
        self.assertTrue(status.ok)
        self.assertEqual(status.backend_id, "echo")
        self.assertEqual(status.metadata.get("protocol_version"), 1)
        self.assertEqual(status.metadata.get("agent_name"), "echo")
        self.assertIn("process_mode", status.metadata)

    # (4) test_bootstrap_check_capability_mismatch
    async def test_bootstrap_check_capability_mismatch(self) -> None:
        """bootstrap_check with required elicitation returns ok=False."""
        config = _make_echo_config(
            required=RequiredCapabilities(streaming=True, elicitation=True),
        )
        self.adapter = ACPBackendAdapter(config)
        status = await self.adapter.bootstrap_check()
        self.assertFalse(status.ok)
        self.assertGreater(len(status.issues), 0)

    # (5) test_submit_run_returns_handle
    async def test_submit_run_returns_handle(self) -> None:
        """submit_run returns RunHandle with non-empty run_id and RUNNING status."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        self.assertIsInstance(handle, RunHandle)
        self.assertTrue(handle.run_id)
        self.assertEqual(handle.status, AsyncTaskState.RUNNING)

    # (6) test_get_run_after_submit
    async def test_get_run_after_submit(self) -> None:
        """get_run returns Run with correct run_id and RUNNING status."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        run = await self.adapter.get_run(handle.run_id)
        self.assertEqual(run.run_id, handle.run_id)
        self.assertEqual(run.status, AsyncTaskState.RUNNING)

    # (7) test_stream_events_yields_message_delta
    async def test_stream_events_yields_message_delta(self) -> None:
        """stream_events yields at least one message.delta event."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await self._collect_events(handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("message.delta", event_types)

    # (8) test_stream_events_yields_message_completed
    async def test_stream_events_yields_message_completed(self) -> None:
        """stream_events yields at least one message.completed event."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        events = await self._collect_events(handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("message.completed", event_types)

    # (9) test_cancel_run
    async def test_cancel_run(self) -> None:
        """cancel_run returns Run with CANCELLED status."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        cancelled = await self.adapter.cancel_run(handle.run_id)
        self.assertEqual(cancelled.status, AsyncTaskState.CANCELLED)

    # (10) test_collect_artifacts_empty
    async def test_collect_artifacts_empty(self) -> None:
        """collect_artifacts returns a list (may be empty)."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        artifacts = await self.adapter.collect_artifacts(handle.run_id)
        self.assertIsInstance(artifacts, list)

    # (11) test_submit_approval_no_auto_approve_terminal
    async def test_submit_approval_no_auto_approve_terminal(self) -> None:
        """submit_approval with terminal permission and decision='approved' does NOT auto-approve."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        approval = Approval(
            approval_id="a1",
            decision="approved",
            metadata={"kind": "terminal"},
        )
        result = await self.adapter.submit_approval(handle.run_id, approval)
        self.assertEqual(result.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertFalse(result.metadata.get("approval_decision_recorded", True))

    # (12) test_process_mode_pooled_rejected
    def test_process_mode_pooled_rejected(self) -> None:
        """Constructing ACPBackendAdapter with POOLED mode raises NotImplementedError."""
        config = ACPBackendConfig(
            backend_id="x",
            command=("python", "echo"),
            process_mode=BackendProcessMode.POOLED,
        )
        with self.assertRaises(NotImplementedError):
            ACPBackendAdapter(config)

    # (13) test_hermes_compatibility_matrix
    def test_hermes_compatibility_matrix(self) -> None:
        """check_hermes_compatibility with known versions."""
        # 0.19.0 — compatible, no issues
        ok, issues = check_hermes_compatibility("0.19.0")
        self.assertTrue(ok)
        self.assertEqual(issues, [])

        # 0.16.0 — incompatible (below minimum)
        ok, issues = check_hermes_compatibility("0.16.0")
        self.assertFalse(ok)
        self.assertTrue(any("below_minimum" in i for i in issues))

        # 0.20.0 — untested but compatible
        ok, issues = check_hermes_compatibility("0.20.0")
        self.assertTrue(ok)
        self.assertTrue(any("untested" in i for i in issues))

    # (14) test_create_hermes_adapter
    def test_create_hermes_adapter(self) -> None:
        """create_hermes_adapter returns adapter with backend_id='hermes' and HERMES_HOME env."""
        adapter = create_hermes_adapter("/fake/hermes/home")
        self.assertEqual(adapter.backend_id(), "hermes")
        self.assertIn("HERMES_HOME", adapter.config.env)
        self.assertEqual(adapter.config.env["HERMES_HOME"], "/fake/hermes/home")
        self.adapter = adapter  # for cleanup

    # (15) test_hermes_compatibility_matrix_contents
    def test_hermes_compatibility_matrix_contents(self) -> None:
        """HERMES_COMPATIBILITY_MATRIX covers v0.17.0–0.19.0 with capability lists."""
        self.assertIn("0.19.0", HERMES_COMPATIBILITY_MATRIX)
        self.assertIn("0.18.0", HERMES_COMPATIBILITY_MATRIX)
        self.assertIn("0.17.0", HERMES_COMPATIBILITY_MATRIX)
        caps_019 = HERMES_COMPATIBILITY_MATRIX["0.19.0"]
        self.assertIn("streaming", caps_019)
        self.assertIn("session_update", caps_019)

    # (16) test_submit_approval_execute_code_rejected
    async def test_submit_approval_execute_code_rejected(self) -> None:
        """submit_approval with execute_code permission and decision='approved' is rejected."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        handle = await self.adapter.submit_run(_make_request())
        approval = Approval(
            approval_id="a2",
            decision="approved",
            metadata={"kind": "execute_code"},
        )
        result = await self.adapter.submit_approval(handle.run_id, approval)
        self.assertEqual(result.status, AsyncTaskState.WAITING_FOR_USER)

    # (17) test_get_run_unknown_raises_keyerror
    async def test_get_run_unknown_raises_keyerror(self) -> None:
        """get_run with unknown run_id raises KeyError."""
        self.adapter = ACPBackendAdapter(_make_echo_config())
        with self.assertRaises(KeyError):
            await self.adapter.get_run("nonexistent-run")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _collect_events(self, run_id: str, timeout: float = 10.0) -> list:
        """Collect all events from stream_events with a timeout."""
        events: list = []
        try:
            async for event in self.adapter.stream_events(run_id):  # type: ignore[union-attr]
                events.append(event)
        except asyncio.TimeoutError:
            pass
        return events


if __name__ == "__main__":
    unittest.main()
