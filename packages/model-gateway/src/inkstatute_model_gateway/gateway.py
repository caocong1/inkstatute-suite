"""ModelProviderGateway — composite BackendAdapter wrapping multiple sub-adapters.

The gateway implements the frozen 9-method ``BackendAdapter`` Protocol via
structural subtyping (no explicit inheritance).  It wraps a
``dict[str, BackendAdapter]`` of sub-adapters keyed by ``backend_id`` and
delegates ``submit_run`` by ``solution.backend_id``.

When ``config.enabled`` is ``False`` (default), the gateway is transparent —
``submit_run`` delegates directly to the matching sub-adapter with no rate
limiting, circuit breaking, fallback, or cost tracking.

When ``config.enabled`` is ``True``, the gateway applies:
- Per-tenant/provider rate limiting (RPM/TPM/concurrency)
- Circuit breakers with fallback chains and tried-provider tracking
- Per-tenant/matter cost tracking with budget ceilings (Plan 03)
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)

from .circuit_breaker import CircuitBreakerConfig, CircuitBreakerRegistry, CircuitState
from .config import ModelProviderGatewayConfig
from .cost_tracker import CostTracker, PricingRate, BudgetCeiling
from .rate_limiter import RateLimitConfig, RateLimiter


class ModelProviderGateway:
    """Composite BackendAdapter wrapping multiple provider_model sub-adapters.

    Sub-adapters are injected as a ``dict[str, BackendAdapter]`` keyed by
    ``backend_id``.  The gateway does NOT import provider_model packages
    directly — it only depends on ``platform_contract`` and
    ``platform_runtime``, preserving the ``dependencies = []`` invariant.
    """

    def __init__(
        self,
        *,
        sub_adapters: dict[str, Any],
        config: ModelProviderGatewayConfig | None = None,
        clock: Any | None = None,
    ) -> None:
        self.config = config or ModelProviderGatewayConfig()
        self._sub_adapters = dict(sub_adapters)
        self._clock = clock or _SystemClock()
        self._run_to_adapter: dict[str, str] = {}
        self._run_requests: dict[str, RunRequest] = {}
        self._rate_limiter = RateLimiter(self.config.rate_limit_configs)
        self._circuit_registry = CircuitBreakerRegistry(self.config.circuit_breaker_config)
        self._cost_tracker = CostTracker(self.config.pricing, self.config.budgets)

    # ------------------------------------------------------------------
    # BackendAdapter Protocol — 9 methods
    # ------------------------------------------------------------------

    def backend_id(self) -> str:
        return self.config.gateway_id

    def capabilities(self) -> AdapterCapabilitySet:
        return _merge_capabilities(self._sub_adapters)

    async def bootstrap_check(self) -> BootstrapStatus:
        issues: list[str] = []
        all_ok = True
        for adapter in self._sub_adapters.values():
            status = await adapter.bootstrap_check()
            if not status.ok:
                all_ok = False
            issues.extend(status.issues)
        if not self._sub_adapters:
            all_ok = False
            issues.append("no_sub_adapters_configured")
        return BootstrapStatus(
            ok=all_ok,
            backend_id=self.config.gateway_id,
            checked_at=self._clock.now(),
            issues=issues,
            metadata={
                "sub_adapter_count": len(self._sub_adapters),
                "sub_adapter_ids": list(self._sub_adapters.keys()),
                "enabled": self.config.enabled,
            },
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        if self.config.enabled:
            return await self._submit_run_enabled(req)
        return await self._submit_run_passthrough(req)

    async def get_run(self, run_id: str) -> Run:
        adapter = self._resolve_adapter(run_id)
        return await adapter.get_run(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        adapter = self._resolve_adapter(run_id)
        async for event in adapter.stream_events(run_id):
            yield event

    async def cancel_run(self, run_id: str) -> Run:
        adapter = self._resolve_adapter(run_id)
        return await adapter.cancel_run(run_id)

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        adapter = self._resolve_adapter(run_id)
        return await adapter.submit_approval(run_id, approval)

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        adapter = self._resolve_adapter(run_id)
        return await adapter.collect_artifacts(run_id)

    # ------------------------------------------------------------------
    # Pass-through mode (disabled)
    # ------------------------------------------------------------------

    async def _submit_run_passthrough(self, req: RunRequest) -> RunHandle:
        """Transparent delegation — no gateway logic."""
        backend_id = req.solution.backend_id
        if backend_id is None:
            raise KeyError("solution.backend_id is None; cannot route to sub-adapter")
        adapter = self._sub_adapters.get(backend_id)
        if adapter is None:
            raise KeyError(
                f"no sub-adapter registered for backend_id={backend_id!r}; "
                f"available: {list(self._sub_adapters.keys())}"
            )
        handle = await adapter.submit_run(req)
        self._run_to_adapter[handle.run_id] = backend_id
        self._run_requests[handle.run_id] = req
        return handle

    # ------------------------------------------------------------------
    # Enabled mode — rate limiting, circuit breakers, fallback
    # ------------------------------------------------------------------

    async def _submit_run_enabled(self, req: RunRequest) -> RunHandle:
        """Enabled mode with rate limiting, circuit breakers, fallback, and cost tracking."""
        tenant_id = req.tenant_id or "default"
        matter_id = req.metadata.get("matter_id") if req.metadata else None
        primary = req.solution.backend_id

        # Check budget before attempting any provider.
        within_budget, accumulated, ceiling = await self._cost_tracker.check_budget(tenant_id, matter_id)
        if not within_budget:
            return RunHandle(
                run_id=f"gateway-budget-exceeded-{id(req)}",
                backend_run_id=None,
                status=AsyncTaskState.FAILED,
                metadata={
                    "error_code": "model_gateway_budget_exceeded",
                    "error_message": f"budget ceiling exceeded for tenant {tenant_id}",
                    "accumulated_cost": accumulated,
                    "budget_ceiling": ceiling,
                    "gateway_enabled": True,
                    "tried_providers": [],
                },
            )

        # Build provider order: primary first, then fallback chain.
        provider_order: list[str] = []
        if primary is not None:
            provider_order.append(primary)
        for pid in self.config.fallback_chain:
            if pid not in provider_order:
                provider_order.append(pid)

        tried_providers: list[str] = []
        last_error: str | None = None

        for provider_id in provider_order:
            adapter = self._sub_adapters.get(provider_id)
            if adapter is None:
                tried_providers.append(provider_id)
                last_error = f"sub-adapter not registered: {provider_id}"
                continue

            # Check circuit breaker.
            if not self._circuit_registry.can_execute(provider_id):
                tried_providers.append(provider_id)
                last_error = f"circuit breaker open: {provider_id}"
                continue

            # Check rate limits.
            rpm_ok = await self._rate_limiter.check_rpm(tenant_id, provider_id)
            if not rpm_ok:
                tried_providers.append(provider_id)
                last_error = f"rate limited (RPM): {provider_id}"
                continue

            # Acquire concurrency semaphore.
            sem = await self._rate_limiter.acquire_concurrency(tenant_id, provider_id)
            if sem is not None:
                await sem.acquire()

            try:
                handle = await adapter.submit_run(req)
                tried_providers.append(provider_id)

                # Check result status.
                run = await adapter.get_run(handle.run_id)
                status = _status_value(run.status)

                if status == AsyncTaskState.SUCCEEDED.value:
                    # Success — record success in circuit breaker.
                    self._circuit_registry.record_success(provider_id)
                    # Record request in rate limiter.
                    await self._rate_limiter.record_request(tenant_id, provider_id)
                    # Record cost from run metadata.
                    usage = _extract_usage_from_run(run)
                    if usage:
                        await self._cost_tracker.record_usage(tenant_id, matter_id, provider_id, usage)
                    # Augment handle metadata with tried_providers.
                    augmented_metadata = dict(handle.metadata)
                    augmented_metadata["tried_providers"] = list(tried_providers)
                    augmented_metadata["gateway_enabled"] = True
                    self._run_to_adapter[handle.run_id] = provider_id
                    self._run_requests[handle.run_id] = req
                    return RunHandle(
                        run_id=handle.run_id,
                        backend_run_id=handle.backend_run_id,
                        status=handle.status,
                        metadata=augmented_metadata,
                    )
                else:
                    # Failure — record failure in circuit breaker.
                    self._circuit_registry.record_failure(provider_id)
                    await self._rate_limiter.record_request(tenant_id, provider_id)
                    last_error = f"provider failed: {provider_id} (status={status})"
                    continue
            except Exception as exc:  # noqa: BLE001
                tried_providers.append(provider_id)
                self._circuit_registry.record_failure(provider_id)
                last_error = f"provider exception: {provider_id} ({type(exc).__name__})"
                continue
            finally:
                if sem is not None:
                    sem.release()

        # All providers exhausted.
        return RunHandle(
            run_id=f"gateway-failed-{id(req)}",
            backend_run_id=None,
            status=AsyncTaskState.FAILED,
            metadata={
                "tried_providers": list(tried_providers),
                "gateway_enabled": True,
                "error_code": "model_gateway_all_providers_failed",
                "error_message": last_error or "all providers exhausted",
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_adapter(self, run_id: str) -> Any:
        backend_id = self._run_to_adapter.get(run_id)
        if backend_id is None:
            raise KeyError(f"unknown gateway run: {run_id}")
        adapter = self._sub_adapters.get(backend_id)
        if adapter is None:
            raise KeyError(f"sub-adapter {backend_id!r} no longer registered")
        return adapter


# ---------------------------------------------------------------------------
# Capability merging
# ---------------------------------------------------------------------------


def _merge_capabilities(sub_adapters: dict[str, Any]) -> AdapterCapabilitySet:
    """Merge sub-adapter capabilities into a single AdapterCapabilitySet.

    Boolean fields are OR'd (True if any sub-adapter has True).
    List fields are unioned (deduplicated, order preserved).
    String fields take the first non-None value.
    """

    hook_events: list[str] = []
    invocation_mode: str | None = None
    feedback_target: str | None = None
    session_read = False
    artifact_return = False
    trace = False
    no_channel_io: bool | None = None
    run_modes: list[str] = []
    stream_event = False
    cancel = False
    approval = False
    live_update = False
    parallel = False
    session_memory = False

    for adapter in sub_adapters.values():
        caps = adapter.capabilities()
        for item in caps.hook_event_support:
            if item not in hook_events:
                hook_events.append(item)
        if invocation_mode is None:
            invocation_mode = caps.invocation_mode
        if feedback_target is None:
            feedback_target = caps.feedback_target_support
        session_read = session_read or caps.session_read_support
        artifact_return = artifact_return or caps.artifact_return_support
        trace = trace or caps.trace_support
        if no_channel_io is None:
            no_channel_io = caps.no_channel_io
        elif caps.no_channel_io is True:
            no_channel_io = True
        for mode in caps.run_invocation_modes:
            if mode not in run_modes:
                run_modes.append(mode)
        stream_event = stream_event or caps.stream_event_support
        cancel = cancel or caps.cancel_support
        approval = approval or caps.approval_support
        live_update = live_update or caps.live_update_support
        parallel = parallel or caps.parallel_task_support
        session_memory = session_memory or caps.session_memory_support

    return AdapterCapabilitySet(
        hook_event_support=hook_events,
        invocation_mode=invocation_mode,
        feedback_target_support=feedback_target,
        session_read_support=session_read,
        artifact_return_support=artifact_return,
        trace_support=trace,
        no_channel_io=no_channel_io,
        run_invocation_modes=run_modes,
        stream_event_support=stream_event,
        cancel_support=cancel,
        approval_support=approval,
        live_update_support=live_update,
        parallel_task_support=parallel,
        session_memory_support=session_memory,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_value(status: AsyncTaskState | str) -> str:
    if isinstance(status, AsyncTaskState):
        return status.value
    return str(status)


def _extract_usage_from_run(run: Run) -> dict[str, Any]:
    """Extract provider_usage from a Run's metadata.

    Returns an empty dict if no usage is found.
    """
    usage = run.metadata.get("provider_usage") if run.metadata else None
    if isinstance(usage, dict):
        return usage
    return {}


class _SystemClock:
    def now(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["ModelProviderGateway"]
