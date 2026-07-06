"""Integration tests for ModelProviderGateway — full flow with all features (Plan 03)."""

from __future__ import annotations

import asyncio
import unittest
from typing import AsyncIterator

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_contract.events import (
    AgentResult,
    AgentResultStatus,
    AgentTurn,
    Channel,
    MessageType,
    ReplyType,
    SolutionBinding,
)
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

from inkstatute_model_gateway import (
    BudgetCeiling,
    CircuitBreakerConfig,
    ModelProviderGateway,
    ModelProviderGatewayConfig,
    PricingRate,
    RateLimitConfig,
)
from inkstatute_model_gateway.circuit_breaker import CircuitState


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
    matter_id: str | None = None,
) -> RunRequest:
    metadata: dict[str, object] = {}
    if matter_id is not None:
        metadata["matter_id"] = matter_id
    return RunRequest(
        turn=_make_turn(turn_id),
        solution=SolutionBinding(
            solution_id="sol-001",
            backend_id=backend_id,
        ),
        tenant_id=tenant_id,
        metadata=metadata,
    )


class _ScriptedAdapter:
    """Fake sub-adapter with configurable success/failure and usage metadata."""

    def __init__(
        self,
        backend_id: str,
        *,
        id_factory: FakeIdFactory | None = None,
        fail_statuses: list[AsyncTaskState] | None = None,
        usage: dict[str, int] | None = None,
    ) -> None:
        self._backend_id = backend_id
        self._id_factory = id_factory or FakeIdFactory()
        self._fail_statuses = list(fail_statuses or [])
        self._call_count = 0
        self._usage = usage or {"input_tokens": 100, "output_tokens": 50}
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
                "provider_usage": dict(self._usage),
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


class TestFullFlowIntegration(unittest.IsolatedAsyncioTestCase):
    """Full flow with rate limiting, circuit breaker, fallback, and cost tracking."""

    async def test_full_flow_with_rate_limiting_fallback_and_cost_tracking(self) -> None:
        """Two providers, rate limiting, fallback, cost tracking, budget ceiling."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            rate_limit_configs={
                "provider-a": RateLimitConfig(rpm=60),
                "provider-b": RateLimitConfig(rpm=60),
            },
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3),
            pricing={
                "provider-a": PricingRate(input_token_cost=0.01, output_token_cost=0.02),
                "provider-b": PricingRate(input_token_cost=0.01, output_token_cost=0.02),
            },
            budgets={"tenant-001:matter-001": BudgetCeiling(max_cost=10000.0)},
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a", matter_id="matter-001")
        handle = await gw.submit_run(req)

        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])
        self.assertTrue(handle.metadata["gateway_enabled"])

        # Verify cost was recorded from provider-b's usage
        accumulated = await gw._cost_tracker.get_accumulated("tenant-001", "matter-001")
        # 100 * 0.01 + 50 * 0.02 = 2.0
        self.assertAlmostEqual(accumulated, 2.0)

    async def test_budget_exceeded_rejects_request(self) -> None:
        """Low budget; first request succeeds; second rejected with budget_exceeded."""
        adapter_a = _ScriptedAdapter("provider-a", usage={"input_tokens": 100, "output_tokens": 0})
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=[],
            pricing={"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)},
            budgets={"tenant-001:matter-001": BudgetCeiling(max_cost=100.0)},
        )
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a}, config=cfg)

        # First request: succeeds, cost = 100
        req1 = _make_request(backend_id="provider-a", turn_id="t1", matter_id="matter-001")
        handle1 = await gw.submit_run(req1)
        self.assertEqual(handle1.status, AsyncTaskState.SUCCEEDED)

        # Second request: budget exceeded
        req2 = _make_request(backend_id="provider-a", turn_id="t2", matter_id="matter-001")
        handle2 = await gw.submit_run(req2)
        self.assertEqual(handle2.status, AsyncTaskState.FAILED)
        self.assertEqual(handle2.metadata["error_code"], "model_gateway_budget_exceeded")
        self.assertIn("budget ceiling exceeded", handle2.metadata["error_message"])

    async def test_disabled_gateway_fully_transparent(self) -> None:
        """config.enabled=False; no rate limiting, circuit breaking, cost tracking, or fallback."""
        adapter_a = _ScriptedAdapter("provider-a", fail_statuses=[AsyncTaskState.FAILED])
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=False,
            fallback_chain=["provider-b"],
            rate_limit_configs={"provider-a": RateLimitConfig(rpm=1)},
            pricing={"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)},
            budgets={"tenant-001:matter-001": BudgetCeiling(max_cost=1.0)},
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a", matter_id="matter-001")
        handle = await gw.submit_run(req)
        # Only A called, no fallback, no budget check
        self.assertEqual(len(adapter_a.submitted_requests), 1)
        self.assertEqual(len(adapter_b.submitted_requests), 0)
        self.assertEqual(handle.status, AsyncTaskState.FAILED)
        self.assertNotIn("tried_providers", handle.metadata)
        self.assertNotIn("error_code", handle.metadata)

    async def test_circuit_breaker_isolation(self) -> None:
        """Provider A breaker opens; provider B still works independently."""
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
        # Trip A's breaker
        gw._circuit_registry.record_failure("provider-a")
        gw._circuit_registry.record_failure("provider-a")
        self.assertEqual(gw._circuit_registry.get_state("provider-a"), CircuitState.OPEN)
        self.assertEqual(gw._circuit_registry.get_state("provider-b"), CircuitState.CLOSED)

        # Request to B should work fine
        req = _make_request(backend_id="provider-b")
        handle = await gw.submit_run(req)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)

    async def test_concurrent_requests_thread_safe(self) -> None:
        """Multiple concurrent submit_run calls don't corrupt rate limiter state."""
        adapter_a = _ScriptedAdapter("provider-a")
        adapter_b = _ScriptedAdapter("provider-b", id_factory=FakeIdFactory(start=200))
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            rate_limit_configs={
                "provider-a": RateLimitConfig(rpm=100, max_concurrency=10),
                "provider-b": RateLimitConfig(rpm=100, max_concurrency=10),
            },
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        # Launch 5 concurrent requests
        requests = [_make_request(backend_id="provider-a", turn_id=f"t{i}") for i in range(5)]
        handles = await asyncio.gather(*[gw.submit_run(r) for r in requests])
        # All should succeed
        for handle in handles:
            self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)

    async def test_all_features_combined(self) -> None:
        """Rate limiting + circuit breaker + fallback + cost tracking + budget ceiling."""
        adapter_a = _ScriptedAdapter(
            "provider-a",
            fail_statuses=[AsyncTaskState.FAILED],
            usage={"input_tokens": 200, "output_tokens": 100},
        )
        adapter_b = _ScriptedAdapter(
            "provider-b",
            id_factory=FakeIdFactory(start=200),
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=["provider-b"],
            rate_limit_configs={
                "provider-a": RateLimitConfig(rpm=60, tpm=10000, max_concurrency=5),
                "provider-b": RateLimitConfig(rpm=60, tpm=10000, max_concurrency=5),
            },
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=60.0),
            pricing={
                "provider-a": PricingRate(input_token_cost=0.02, output_token_cost=0.03),
                "provider-b": PricingRate(input_token_cost=0.01, output_token_cost=0.02),
            },
            budgets={"tenant-001:matter-001": BudgetCeiling(max_cost=1000.0)},
        )
        gw = ModelProviderGateway(
            sub_adapters={"provider-a": adapter_a, "provider-b": adapter_b},
            config=cfg,
        )
        req = _make_request(backend_id="provider-a", matter_id="matter-001")
        handle = await gw.submit_run(req)

        # A failed, B succeeded
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(handle.metadata["tried_providers"], ["provider-a", "provider-b"])

        # Circuit breaker for A recorded a failure
        cb_a = gw._circuit_registry.get_or_create("provider-a")
        self.assertEqual(cb_a.consecutive_failures, 1)

        # Cost recorded from B's usage: 100*0.01 + 50*0.02 = 2.0
        accumulated = await gw._cost_tracker.get_accumulated("tenant-001", "matter-001")
        self.assertAlmostEqual(accumulated, 2.0)

        # Budget not exceeded
        within, _, _ = await gw._cost_tracker.check_budget("tenant-001", "matter-001")
        self.assertTrue(within)

    async def test_budget_exceeded_no_fallback_attempted(self) -> None:
        """Budget check happens before any provider is tried."""
        adapter_a = _ScriptedAdapter("provider-a")
        cfg = ModelProviderGatewayConfig(
            enabled=True,
            fallback_chain=[],
            pricing={"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)},
            budgets={"tenant-001:matter-001": BudgetCeiling(max_cost=50.0)},
        )
        gw = ModelProviderGateway(sub_adapters={"provider-a": adapter_a}, config=cfg)

        # First request: cost = 100, exceeds budget of 50 immediately
        # But wait — budget check is BEFORE the request, so first request should pass
        # (accumulated=0 < 50), then after recording cost=100, second request fails.
        adapter_a._usage = {"input_tokens": 30, "output_tokens": 0}  # cost = 30
        req1 = _make_request(backend_id="provider-a", turn_id="t1", matter_id="matter-001")
        handle1 = await gw.submit_run(req1)
        self.assertEqual(handle1.status, AsyncTaskState.SUCCEEDED)

        # Now accumulated = 30, budget = 50, so 30 < 50 → still within
        # Second request: cost = 30, accumulated would be 60 > 50
        # But budget check is BEFORE recording, so 30 < 50 → allowed, then 60 recorded
        req2 = _make_request(backend_id="provider-a", turn_id="t2", matter_id="matter-001")
        handle2 = await gw.submit_run(req2)
        self.assertEqual(handle2.status, AsyncTaskState.SUCCEEDED)

        # Now accumulated = 60 > 50 → third request rejected
        req3 = _make_request(backend_id="provider-a", turn_id="t3", matter_id="matter-001")
        handle3 = await gw.submit_run(req3)
        self.assertEqual(handle3.status, AsyncTaskState.FAILED)
        self.assertEqual(handle3.metadata["error_code"], "model_gateway_budget_exceeded")
        # No providers tried when budget exceeded
        self.assertEqual(handle3.metadata["tried_providers"], [])


if __name__ == "__main__":
    unittest.main()
