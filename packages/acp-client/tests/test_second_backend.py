"""Backend replaceability tests — prove backend_id swap needs zero caller code changes.

The SAME test logic runs against two different ACP backends (the base echo
agent and a configurable echo agent simulating ``codex-acp``) with different
``backend_id`` values.  The only difference is the ``ACPBackendConfig``
passed to the adapter — the caller code is identical.

All tests use in-repo fixture agents — no network, no external agent binaries.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime.protocols import (
    Approval,
    BootstrapStatus,
    RunHandle,
    RunRequest,
    SolutionBinding,
)

from inkstatute_acp_client.adapter import ACPBackendAdapter, ACPBackendConfig
from inkstatute_acp_client.capability_negotiation import RequiredCapabilities

ECHO_AGENT = str(Path(__file__).resolve().parent / "fixtures" / "echo_agent.py")
CONFIGURABLE_ECHO_AGENT = str(
    Path(__file__).resolve().parent / "fixtures" / "configurable_echo_agent.py"
)

CODEX_CAPS = '{"streaming": true, "elicitation": true, "permissions": true}'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Config pointing at the base echo agent fixture."""
    return ACPBackendConfig(
        backend_id=backend_id,
        command=("python", ECHO_AGENT),
        required_capabilities=required or RequiredCapabilities(streaming=True),
    )


def _make_codex_config(
    backend_id: str = "codex-acp",
    required: RequiredCapabilities | None = None,
) -> ACPBackendConfig:
    """Config pointing at the configurable echo agent simulating codex-acp."""
    return ACPBackendConfig(
        backend_id=backend_id,
        command=(
            "python",
            CONFIGURABLE_ECHO_AGENT,
            "--backend-name",
            "codex-acp",
            "--capabilities",
            CODEX_CAPS,
        ),
        required_capabilities=required
        or RequiredCapabilities(streaming=True, elicitation=True, permissions=True),
    )


async def run_full_cycle(adapter: ACPBackendAdapter, prompt_content: str) -> dict:
    """Execute the full BackendAdapter cycle and return a summary dict.

    This function is the PROOF of replaceability — it is called with both
    the echo adapter and the codex-acp adapter without any code changes.
    Only the ``ACPBackendConfig`` differs between the two adapters.
    """
    status = await adapter.bootstrap_check()
    handle = await adapter.submit_run(_make_request(prompt_content))

    event_types: list[str] = []
    async for event in adapter.stream_events(handle.run_id):
        event_types.append(event.event_type)

    cancelled = await adapter.cancel_run(handle.run_id)
    artifacts = await adapter.collect_artifacts(handle.run_id)

    return {
        "backend_id": adapter.backend_id(),
        "event_types": event_types,
        "run_status": cancelled.status.value,
        "bootstrap_ok": status.ok,
        "artifacts": artifacts,
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestSecondBackendReplaceability(unittest.IsolatedAsyncioTestCase):
    """Prove that swapping backend_id requires only a config change."""

    adapters: list[ACPBackendAdapter]

    def setUp(self) -> None:
        self.adapters = []

    async def asyncTearDown(self) -> None:
        for adapter in self.adapters:
            try:
                await adapter.shutdown()
            except Exception:
                pass
        self.adapters.clear()

    def _track(self, adapter: ACPBackendAdapter) -> ACPBackendAdapter:
        self.adapters.append(adapter)
        return adapter

    # (1) test_echo_backend_full_cycle
    async def test_echo_backend_full_cycle(self) -> None:
        """Full cycle with the echo backend: bootstrap → submit → stream → cancel → artifacts."""
        adapter = self._track(ACPBackendAdapter(_make_echo_config()))
        result = await asyncio.wait_for(
            run_full_cycle(adapter, "hello world"), timeout=15.0
        )
        self.assertTrue(result["bootstrap_ok"])
        self.assertIn("message.delta", result["event_types"])
        self.assertIn("message.completed", result["event_types"])

    # (2) test_codex_acp_backend_full_cycle
    async def test_codex_acp_backend_full_cycle(self) -> None:
        """Full cycle with the codex-acp backend: same cycle, different backend_id."""
        adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        result = await asyncio.wait_for(
            run_full_cycle(adapter, "hello world"), timeout=15.0
        )
        self.assertTrue(result["bootstrap_ok"])
        self.assertEqual(result["backend_id"], "codex-acp")
        self.assertIn("message.delta", result["event_types"])
        self.assertIn("message.completed", result["event_types"])

    # (3) test_same_caller_code_different_backends
    async def test_same_caller_code_different_backends(self) -> None:
        """The same run_full_cycle function works with both backends — zero caller code changes."""
        echo_adapter = self._track(ACPBackendAdapter(_make_echo_config()))
        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))

        echo_result = await asyncio.wait_for(
            run_full_cycle(echo_adapter, "test prompt"), timeout=15.0
        )
        codex_result = await asyncio.wait_for(
            run_full_cycle(codex_adapter, "test prompt"), timeout=15.0
        )

        # Both succeed
        self.assertTrue(echo_result["bootstrap_ok"])
        self.assertTrue(codex_result["bootstrap_ok"])

        # Both produce the same core event types
        self.assertIn("message.delta", echo_result["event_types"])
        self.assertIn("message.delta", codex_result["event_types"])
        self.assertIn("message.completed", echo_result["event_types"])
        self.assertIn("message.completed", codex_result["event_types"])

        # Backend IDs are different — config-driven, not code-driven
        self.assertEqual(echo_result["backend_id"], "echo")
        self.assertEqual(codex_result["backend_id"], "codex-acp")

    # (4) test_different_capabilities_negotiated
    async def test_different_capabilities_negotiated(self) -> None:
        """Echo backend has no elicitation; codex-acp backend does — adapter adapts."""
        echo_adapter = self._track(ACPBackendAdapter(_make_echo_config()))
        echo_status = await echo_adapter.bootstrap_check()
        self.assertTrue(echo_status.ok)
        echo_caps = echo_adapter.capabilities()
        self.assertFalse(echo_caps.approval_support)
        self.assertFalse(echo_caps.live_update_support)

        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        codex_status = await codex_adapter.bootstrap_check()
        self.assertTrue(codex_status.ok)
        codex_caps = codex_adapter.capabilities()
        self.assertTrue(codex_caps.approval_support)
        self.assertTrue(codex_caps.live_update_support)

    # (5) test_thought_chunks_from_second_backend
    async def test_thought_chunks_from_second_backend(self) -> None:
        """Codex-acp yields thought.delta events; echo does not."""
        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        handle = await codex_adapter.submit_run(_make_request("hello thought test"))
        events = await self._collect_events(codex_adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("thought.delta", event_types)

    # (6) test_elicitation_from_second_backend
    async def test_elicitation_from_second_backend(self) -> None:
        """Codex-acp yields elicitation.requested events when prompt contains 'ask:'."""
        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        handle = await codex_adapter.submit_run(
            _make_request("ask: what is the case number?")
        )
        events = await self._collect_events(codex_adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("elicitation.requested", event_types)

    # (7) test_permission_request_not_auto_approved
    async def test_permission_request_not_auto_approved(self) -> None:
        """Terminal permission from codex-acp is NOT auto-approved."""
        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        handle = await codex_adapter.submit_run(
            _make_request("permission: run shell command")
        )
        events = await self._collect_events(codex_adapter, handle.run_id)
        event_types = [e.event_type for e in events]
        self.assertIn("permission.requested", event_types)

        # Attempt to auto-approve a terminal permission — must be rejected
        approval = Approval(
            approval_id="a1",
            decision="approved",
            metadata={"kind": "terminal"},
        )
        result = await codex_adapter.submit_approval(handle.run_id, approval)
        self.assertEqual(result.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertFalse(result.metadata.get("approval_decision_recorded", True))

    # (8) test_backend_id_isolated
    def test_backend_id_isolated(self) -> None:
        """backend_id is config-driven, not code-driven — both are ACPBackendAdapter."""
        echo_adapter = self._track(ACPBackendAdapter(_make_echo_config()))
        codex_adapter = self._track(ACPBackendAdapter(_make_codex_config()))
        self.assertEqual(echo_adapter.backend_id(), "echo")
        self.assertEqual(codex_adapter.backend_id(), "codex-acp")
        self.assertIsInstance(echo_adapter, ACPBackendAdapter)
        self.assertIsInstance(codex_adapter, ACPBackendAdapter)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _collect_events(
        self, adapter: ACPBackendAdapter, run_id: str, timeout: float = 15.0
    ) -> list:
        """Collect all events from stream_events with a timeout."""
        events: list = []

        async def _collect() -> None:
            async for event in adapter.stream_events(run_id):
                events.append(event)

        try:
            await asyncio.wait_for(_collect(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        return events


if __name__ == "__main__":
    unittest.main()
