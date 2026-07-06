"""Tests for fallback chains, circuit breakers, and tried-provider tracking (Plan 02)."""

from __future__ import annotations

import unittest
from typing import AsyncIterator

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
from platform_runtime.fakes import FakeIdFactory

from platform_contract.events import AgentTurn, Channel, MessageType, SolutionBinding

from inkstatute_model_gateway import (
    CircuitBreakerConfig,
    ModelProviderGateway,
    ModelProviderGatewayConfig,
    RateLimitConfig,
)
from inkstatute_model_gateway.circuit_breaker import CircuitBreakerRegistry, CircuitState


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


class _ScriptedAdapter:
    """Fake sub-adapter with configurable success/failure per request."""

    def __init__(
        self,
        backend_id: str,
        *,
        id_factory: FakeIdFactory | None = None,
        fail_statuses: list[AsyncTaskState] | None = None,
    ) -> None:
        self._backend_id = backend_id
        self._id_factory = id_factory or FakeIdFactory()
        self._fail_statuses = list(fail_statuses or [])
        self._call_count = 0
        self.submitted_requests: list[RunRequest] = []
        self.runs: dict[str, Run] = {}

    def backend_id(self) -> str:
        return self._backend_id

    def capabilities(self) -> AdapterCapabilitySet:
        return AdapterCapabilitySet(
            invocation_mode="direct_llm",
            no_channel_io=True,
            run_invocation_modes=["oneshot"],
        )

    async def bootstrap_check(self) -> BootstrapStatus:
        return BootstrapStatus(ok=True, backend_id=self._backend_id, checked_at="t")

    async def submit_run(self, req: RunRequest) -> RunHandle:
        self.submitted_requests.append(req)
        run_id = self._id_factory.new_id("run")
        self._call_count += 1

        if self._fail_statuses and self._call_count <= len(self._fail_statuses):
            status = self._fail_statuses[self._call_count - 1]
        else:
            status = AsyncTaskState.SUCCEEDED

        run = Run(
            run_id=run_id,
            status=status,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            result=AgentResult(
                result_id=f"result-{run_id}",
                turn_id=req.turn.turn_id,
                status=AgentResultStatus.SUCCESS if status == AsyncTaskState.SUCCEEDED else AgentResultStatus.FAILED,
                reply_type=ReplyType.TEXT,
                content="ok" if status == AsyncTaskState.SUCCEEDED else None,
            ),
            metadata={
                "backend_id": self._backend_id,
                "provider_usage": {"input_tokens": 100, "output_tokens": 50},
            },
        )
        self.runs[run_id] = run
        return RunHandle(
            run_id=run_id,
            backend_run_id=f"{self._backend_id}:{run_id}",
            status=status,
            metadata={"backend_id": self._backend_id},
        )

    async def get_run(self, run_id: str) -> Run:
        return self.runs[run_id]

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        return
        yield  # type: ignore[unreachable]

    async def cancel_run(self, run_id: str) -> Run:
        return self.runs[run_id]

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        return self.runs[run_id]

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        return []


class _ExceptionAdapter:
    """Fake sub-adapter that always raises on submit_run."""

    def __init__(self, backend_id: str) -> None:
        self._backend_id = backend_id
        self.submitted_requests: list[RunRequest] = []

    def backend_id(self) -> str:
        return self._backend_id

    def capabilities(self) -> AdapterCapabilitySet:
        return AdapterCapabilitySet(
            invocation_mode="direct_llm",
            no_channel_io=True,
            run_invocation_modes=["oneshot"],
        )

    async def bootstrap_check(self) -> BootstrapStatus:
        return BootstrapStatus(ok=True, backend_id=self._backend_id, checked_at="t")

    async def submit_run(self, req: RunRequest) -> RunHandle:
        self.submitted_requests.append(req)
        raise RuntimeError(f"provider {self._backend_id} crashed")

    async def get_run(self, run_id: str) -> Run:
        raise KeyError(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        return
        yield  # type: ignore[unreachable]

    async def cancel_run(self, run_id: str) -> Run:
        raise KeyError(run_id)

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        raise KeyError(run_id)

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        return []


class TestFallbackChain(unittest.IsolatedAsyncioTestCase):
    """Fallback chain and tried_providers tracking tests."""

    async def test_fallback_on_failure(self) -> None:
        """Adapter A fails, adapter B succeeds; fallback chain tries both."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        # Should have tried both
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        self.assertEqual(len(adapter_b.submitted_requests), 1)
        # Result should be from B (succeeded)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        # tried_providers should list both
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])

    async def test_fallback_on_circuit_breaker_open(self) -> None:
        """Adapter A circuit breaker open; skips to B."""
        adapter_a = _ScriptedAdapter("provider-a")
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2),
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        # Pre-trip the circuit breaker for provider-a
        gw._circuit_registry.record_failure("provider-a")
        gw._circuit_registry.record_failure("provider-a")
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.OPEN)

        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        # A should be skipped (circuit open), B should handle
        self.assertEqual(len(adapter_a.submitted_requests), 0)
        self.assertEqual(len(adapter_b.submitted_requests), 1)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])

    async def test_all_providers_fail(self) -> None:
        """All adapters fail; RunHandle with FAILED status."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        adapter_b = _ScriptedAdapter("provider-b", fail_statuses=[AsyncTaskState.FAILED], id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        self.assertEqual(handle.status, AsyncTaskState.FAILED)
        self.assertEqual(handle.metadata["error_code"], "model_gateway_all_providers_failed")
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])

    async def test_fallback_on_exception(self) -> None:
        """Adapter A raises exception; falls back to B."""
        adapter_a = _ExceptionAdapter("provider-a")
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])

    async def test_no_fallback_chain_single_provider(self) -> None:
        """Only one provider, it fails → all_providers_failed error."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        cfg = ModelProviderGatewayConfig(enabled=True, fallback_chain=[])
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a}, config=cfg)
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        self.assertEqual(handle.status, AsyncTaskState.FAILED)
        self.assertEqual(handle.metadata["error_code"], "model_gateway_all_providers_failed")
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a"])


class TestCircuitBreakerIntegration(unittest.IsolatedAsyncioTestCase):
    """Circuit breaker integration with the gateway."""

    async def test_circuit_breaker_trips_after_threshold(self) -> None:
        """Adapter A fails N times; circuit breaker opens; next request skips A."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[
            AsyncTaskState.FAILED,
            AsyncTaskState.FAILED,
            AsyncTaskState.FAILED,  # 3rd call would succeed but breaker is open
        ])
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2),
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        # First request: A fails, B succeeds
        req1 = _make_request(backend_id="provider-a", turn_id="t1")
        await gw.submit_run(req1)
        # Second request: A fails again, B succeeds; breaker should trip
        req2 = _make_request(backend_id="provider-a", turn_id="t2")
        await gw.submit_run(req2)
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.OPEN)
        # Third request: A should be skipped (breaker open), B handles
        req3 = _make_request(backend_id="provider-a", turn_id="t3")
        handle3 = await gw.submit_run(req3)
        self.assertEqual(len(adapter_a.submitted_requests), 2)  # A only called twice
        self.assertEqual(handle3.status, AsyncTaskState.SUCCEEDED)

    async def test_circuit_breaker_half_open_success_closes(self) -> None:
        """Force breaker to half-open, successful request closes it."""
        adapter_a = _ScriptedAdapter("provider-a")
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=[],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=0.0),
        )
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a}, config=cfg)
        # Trip the breaker
        gw._circuit_registry.record_failure("provider-a")
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.OPEN)
        # With cooldown=0, can_execute should transition to HALF_OPEN
        self.assertTrue(gw._circuit_registry.can_execute("provider-a"))
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.HALF_OPEN)
        # Successful request should close it
        req = _make_request(backend_id="provider-a")
        await gw.submit_run(req)
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.CLOSED)


class TestRateLimitIntegration(unittest.IsolatedAsyncioTestCase):
    """Rate limiting integration with the gateway."""

    async def test_rate_limit_skips_provider(self) -> None:
        """RPM=1 for provider A; 2nd request within window skips A, goes to B."""
        adapter_a = _ScriptedAdapter("provider-a")
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            rate_limit_configs={"provider-a": RateLimitConfig(rpm=1)},
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        # First request: A succeeds (RPM=1, first request)
        req1 = _make_request(backend_id="provider-a", turn_id="t1")
        handle1 = await gw.submit_run(req1)
        self.assertEqual(handle1.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        # Second request: A is rate-limited, B handles
        req2 = _make_request(backend_id="provider-a", turn_id="t2")
        handle2 = await gw.submit_run(req2)
        self.assertEqual(len(adapter_a.submitted_requests), 1)  # A not called again
        self.assertEqual(len(adapter_b.submitted_requests), 1)  # B handles
        self.assertEqual(handle2.status, AsyncTaskState.SUCCEEDED)


class TestDisabledGatewayNoFallback(unittest.IsolatedAsyncioTestCase):
    """When disabled, no fallback is attempted."""

    async def test_disabled_gateway_no_fallback(self) -> None:
        """config.enabled=False; adapter A fails; no fallback attempted."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(enabled=False, fallback_chain=["provider-b"])
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        # Only A should be called (pass-through, no fallback)
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        self.assertEqual(len(adapter_b.submitted_requests), 0)
        # Handle should have A's FAILED status
        self.assertEqual(handle.status, AsyncTaskState.FAILED)
        # No tried_providers in pass-through mode
        self.assertNotIn("tried_providers", handle.metadata)


class TestTriedProvidersMetadata(unittest.IsolatedAsyncioTestCase):
    """tried_providers list is correctly tracked in run metadata."""

    async def test_tried_providers_in_metadata(self) -> None:
        """Verify tried_providers list is in RunHandle.metadata."""
        adapter_a = _ScriptedAdapter("provider-a")
        cfg = ModelProviderGatewayConfig(enabled=True, fallback_chain=[])
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a}, config=cfg)
        req = _make_request(backend_id="provider-a")
        handle = await gw.submit_run(req)
        self.assertIn("tried_providers", handle.metadata)
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a"])
        self.assertTrue(handle.metadata["gateway_enabled"])


if __name__ == "__main__":
    unittest.main()
