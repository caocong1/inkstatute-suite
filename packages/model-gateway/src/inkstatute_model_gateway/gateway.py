"""ModelProviderGateway — composite BackendAdapter wrapping multiple sub-adapters.

The gateway implements the frozen 9-method ``BackendAdapter`` Protocol via
structural subtyping (no explicit inheritance).  It wraps a
``dict[str, BackendAdapter]`` of sub-adapters keyed by ``backend_id`` and
delegates ``submit_run`` by ``solution.backend_id``.

When ``config.enabled`` is ``False`` (default), the gateway is transparent —
``submit_run`` delegates directly to the matching sub-adapter with no rate
limiting, circuit breaking, fallback, or cost tracking.

When ``config.enabled`` is ``True``, the gateway applies:
- Per-tenant/provider rate limiting (RPM/TPM/concurrency) — Plan 02
- Circuit breakers with fallback chains and tried-provider tracking — Plan 02
- Per-tenant/matter cost tracking with budget ceilings — Plan 03
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

from .config import ModelProviderGatewayConfig


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
# Clock
# ---------------------------------------------------------------------------


class _SystemClock:
    def now(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["ModelProviderGateway"]
