"""Tests for ModelProviderGateway composite BackendAdapter (Plan 01)."""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_contract.events import AgentResult, AgentResultStatus, ReplyType
from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory, FakeRuntimeClock

from platform_contract.events import AgentTurn, Channel, MessageType, SolutionBinding

from inkstatute_model_gateway import ModelProviderGateway, ModelProviderGatewayConfig


def _make_turn(turn_id: str = "turn-001") -> AgentTurn:
    return AgentTurn(
        turn_id=turn_id,
        conversation_id="conv-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at="2026-07-06T00:00:00Z",
        content="Hello",
    )


def _make_request(
    backend_id: str = "provider-a",
    turn_id: str = "turn-001",
    tenant_id: str | None = "tenant-001",
) -> RunRequest:
    return RunRequest(
        turn=_make_turn(turn_id),
        solution=SolutionBinding(
            solution_id="sol-001",
            backend_id=backend_id,
        ),
        tenant_id=tenant_id,
    )


class TestModelProviderGatewayBasics(unittest.TestCase):
    """Basic gateway identity and capability tests."""

    def test_backend_id_returns_gateway_id(self) -> None:
        gw = ModelProviderGateway(sub_adapters={})
        self.assertEqual(gw.backend_id(), "model-provider-gateway")

    def test_backend_id_custom_gateway_id(self) -> None:
        cfg = ModelProviderGatewayConfig(gateway_id="custom-gateway")
        gw = ModelProviderGateway(sub_adapters={}, config=cfg)
        self.assertEqual(gw.backend_id(), "custom-gateway")

    def test_capabilities_merges_sub_adapters(self) -> None:
        class AdapterA:
            def backend_id(self) -> str:
                return "provider-a"

            def capabilities(self) -> AdapterCapabilitySet:
                return AdapterCapabilitySet(
                    invocation_mode="direct_llm",
                    stream_event_support=True,
                    no_channel_io=True,
                    run_invocation_modes=["oneshot"],
                )

            async def bootstrap_check(self) -> BootstrapStatus:
                return BootstrapStatus(ok=True, backend_id="provider-a", checked_at="t")

            async def submit_run(self, req: RunRequest) -> RunHandle:
                raise NotImplementedError

            async def get_run(self, run_id: str) -> Run:
                raise NotImplementedError

            async def stream_events(self, run_id: str):
                raise NotImplementedError
                yield  # type: ignore[unreachable]

            async def cancel_run(self, run_id: str) -> Run:
                raise NotImplementedError

            async def submit_approval(self, run_id: str, approval: Approval) -> Run:
                raise NotImplementedError

            async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
                raise NotImplementedError

        class AdapterB:
            def backend_id(self) -> str:
                return "provider-b"

            def capabilities(self) -> AdapterCapabilitySet:
                return AdapterCapabilitySet(
                    invocation_mode="direct_llm",
                    artifact_return_support=True,
                    no_channel_io=True,
                    run_invocation_modes=["oneshot"],
                    cancel_support=True,
                )

            async def bootstrap_check(self) -> BootstrapStatus:
                return BootstrapStatus(ok=True, backend_id="provider-b", checked_at="t")

            async def submit_run(self, req: RunRequest) -> RunHandle:
                raise NotImplementedError

            async def get_run(self, run_id: str) -> Run:
                raise NotImplementedError

            async def stream_events(self, run_id: str):
                raise NotImplementedError
                yield  # type: ignore[unreachable]

            async def cancel_run(self, run_id: str) -> Run:
                raise NotImplementedError

            async def submit_approval(self, run_id: str, approval: Approval) -> Run:
                raise NotImplementedError

            async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
                raise NotImplementedError

        gw = ModelProviderGateway(
            sub_adapters={"provider-a": AdapterA(), "provider-b": AdapterB()},
        )
        caps = gw.capabilities()
        self.assertTrue(caps.stream_event_support)
        self.assertTrue(caps.artifact_return_support)
        self.assertTrue(caps.cancel_support)

    def test_capabilities_empty_sub_adapters(self) -> None:
        gw = ModelProviderGateway(sub_adapters={})
        caps = gw.capabilities()
        self.assertFalse(caps.stream_event_support)
        self.assertFalse(caps.artifact_return_support)


class TestModelProviderGatewayBootstrap(unittest.IsolatedAsyncioTestCase):
    """Bootstrap check aggregation tests."""

    async def test_bootstrap_check_all_ok(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        adapter_b = FakeBackendAdapter(backend_id="provider-b")
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
        )
        status = await gw.bootstrap_check()
        self.assertTrue(status.ok)
        self.assertEqual(status.backend_id, "model-provider-gateway")
        self.assertEqual(status.issues, [])
        self.assertEqual(status.metadata["sub_adapter_count"], 2)

    async def test_bootstrap_check_no_sub_adapters(self) -> None:
        gw = ModelProviderGateway(sub_adapters={})
        status = await gw.bootstrap_check()
        self.assertFalse(status.ok)
        self.assertIn("no_sub_adapters_configured", status.issues)


class TestModelProviderGatewaySubmitRun(unittest.IsolatedAsyncioTestCase):
    """submit_run delegation and routing tests."""

    async def test_submit_run_delegates_by_backend_id(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a", id_factory=FakeIdFactory(start=100))
        adapter_b = FakeBackendAdapter(backend_id="provider-b", id_factory=FakeIdFactory(start=200))
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        self.assertEqual(len(adapter_b.submitted_requests), 0)
        self.assertIn(handle.run_id, adapter_a.runs)

    async def test_submit_run_unknown_backend_id_raises_keyerror(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        req = _make_request(backend_id="provider-unknown")
        with self.assertRaises(KeyError):
            await gw.submit_run(req)

    async def test_submit_run_none_backend_id_raises_keyerror(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        req = RunRequest(
            turn=_make_turn(),
            solution=SolutionBinding(solution_id="sol-001", backend_id=None),
        )
        with self.assertRaises(KeyError):
            await gw.submit_run(req)

    async def test_get_run_routes_to_correct_adapter(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a", id_factory=FakeIdFactory(start=100))
        adapter_b = FakeBackendAdapter(backend_id="provider-b", id_factory=FakeIdFactory(start=200))
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
        )
        req_a = _make_request(backend_id="provider-a", turn_id="turn-a")
        handle_a = await gw.submit_run(req_a)
        req_b = _make_request(backend_id="provider-b", turn_id="turn-b")
        handle_b = await gw.submit_run(req_b)

        run_a = await gw.get_run(handle_a.run_id)
        self.assertEqual(run_a.run_id, handle_a.run_id)
        self.assertIn(handle_a.run_id, adapter_a.runs)
        self.assertNotIn(handle_a.run_id, adapter_b.runs)

        run_b = await gw.get_run(handle_b.run_id)
        self.assertEqual(run_b.run_id, handle_b.run_id)
        self.assertIn(handle_b.run_id, adapter_b.runs)

    async def test_stream_events_routes_to_correct_adapter(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a", id_factory=FakeIdFactory(start=100))
        adapter_b = FakeBackendAdapter(backend_id="provider-b", id_factory=FakeIdFactory(start=200))
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
        )
        req_b = _make_request(backend_id="provider-b", turn_id="turn-b")
        handle_b = await gw.submit_run(req_b)

        events = []
        async for event in gw.stream_events(handle_b.run_id):
            events.append(event)
        self.assertTrue(len(events) > 0)
        for event in events:
            self.assertEqual(event.run_id, handle_b.run_id)

    async def test_cancel_run_routes_to_correct_adapter(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        await gw.cancel_run(handle.run_id)
        self.assertIn(handle.run_id, adapter_a.cancelled_run_ids)

    async def test_submit_approval_routes_to_correct_adapter(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        approval = Approval(approval_id="appr-001", decision="approved")
        await gw.submit_approval(handle.run_id, approval)
        self.assertEqual(len(adapter_a.submitted_approvals), 1)

    async def test_collect_artifacts_routes_to_correct_adapter(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        artifacts = await gw.collect_artifacts(handle.run_id)
        self.assertTrue(len(artifacts) > 0)

    async def test_get_run_unknown_run_id_raises_keyerror(self) -> None:
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a})
        with self.assertRaises(KeyError):
            await gw.get_run("nonexistent-run")


class TestModelProviderGatewayDisabled(unittest.IsolatedAsyncioTestCase):
    """Tests for disabled (pass-through) gateway behavior."""

    async def test_disabled_gateway_is_pass_through(self) -> None:
        """When enabled=False, submit_run delegates directly with no gateway logic."""
        adapter_a = FakeBackendAdapter(backend_id="provider-a")
        cfg = ModelProviderGatewayConfig(enabled=False)
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        # Verify it delegated directly to the sub-adapter
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        # Verify run_id mapping works for subsequent calls
        run = await gw.get_run(handle.run_id)
        self.assertIsNotNone(run)

    async def test_disabled_gateway_default_config(self) -> None:
        """Default config has enabled=False."""
        cfg = ModelProviderGatewayConfig()
        self.assertFalse(cfg.enabled)


class TestPackageImportsCleanly(unittest.TestCase):
    """Verify the package imports without external SDK dependencies."""

    def test_package_imports_cleanly(self) -> None:
        import inkstatute_model_gateway

        self.assertTrue(hasattr(inkstatute_model_gateway, "ModelProviderGateway"))
        self.assertTrue(hasattr(inkstatute_model_gateway, "ModelProviderGatewayConfig"))


if __name__ == "__main__":
    unittest.main()
