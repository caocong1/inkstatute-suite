"""InProcessAgentCoreAdapter — BackendAdapter Protocol implementation over run_turn().

This is the in-process entry point for the self-built agent core (Plan 103-01).
It implements all 9 :class:`BackendAdapter` Protocol methods by wrapping the
agent-core's ``run_turn()`` async generator — no IPC, no subprocess, full
observability.

The adapter is the default backend (``backend_id="inkstatute"``) and has **no
architectural privilege**: it follows the same ``BackendAdapter`` contract as
the ACP-based :class:`ACPBackendAdapter`.  Swapping ``backend_id`` from
``"hermes"`` to ``"inkstatute"`` requires zero changes to any channel or UI
code.

Key design:
- **Event buffering** — each ``submit_run`` starts ``run_turn()`` as a
  background ``asyncio.Task``.  Events are pushed into a per-run
  ``asyncio.Queue``.  ``stream_events`` pulls from the queue until the
  background task completes (terminal state).
- **Approval safety** — ``terminal`` and ``execute_code`` permissions are
  never auto-approved, matching the ACP adapter and AGENTS.md SAFE-04.
- **No fs/* or terminal/* capabilities** — the capability set declares
  streaming, cancel, approval, and session memory support only.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_contract.events import Artifact, RunEvent
from platform_runtime.protocols import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunHandle,
    RunRequest,
)

from .backend_config import AgentCoreBackendConfig
from .event_emitter import EventEmitter
from .turn_loop import run_turn

logger = logging.getLogger(__name__)

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# Permission safety — kinds that must NEVER be auto-approved
# ---------------------------------------------------------------------------

_DANGEROUS_PERMISSION_KINDS: frozenset[str] = frozenset({"terminal", "execute_code"})


# ---------------------------------------------------------------------------
# Sentinel for signalling stream completion
# ---------------------------------------------------------------------------

_STREAM_DONE: object = object()


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


class _SystemClock:
    """Default clock — returns current UTC time as ISO-8601 string."""

    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# InProcessAgentCoreAdapter
# ---------------------------------------------------------------------------


class InProcessAgentCoreAdapter:
    """In-process BackendAdapter implementing all 9 Protocol methods.

    Wraps the agent-core's ``run_turn()`` for direct use by the Gateway.
    No IPC, no subprocess — full observability of the event stream.

    Args:
        config: :class:`AgentCoreBackendConfig` providing the turn loop
            config, provider factory, and optional tool executor factory.
    """

    def __init__(self, config: AgentCoreBackendConfig) -> None:
        self.config = config
        self._clock = _SystemClock()

        # Run state
        self._runs: dict[str, Run] = {}
        self._events: dict[str, list[RunEvent]] = {}
        self._artifacts: dict[str, list[ArtifactRecord]] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._bg_tasks: dict[str, asyncio.Task] = {}
        self._emitters: dict[str, EventEmitter] = {}

        # Approvals pending consumption by the turn loop
        self._pending_approvals: dict[str, list[Approval]] = {}

        # Runs whose sentinel was already pushed by cancel_run
        self._sentinel_pushed: set[str] = set()

        # Counters
        self._next_run = 1

    # ------------------------------------------------------------------
    # Protocol method 1: backend_id
    # ------------------------------------------------------------------

    def backend_id(self) -> str:
        """Return the unique backend identifier."""
        return self.config.backend_id

    # ------------------------------------------------------------------
    # Protocol method 2: capabilities
    # ------------------------------------------------------------------

    def capabilities(self) -> AdapterCapabilitySet:
        """Return the capability set.

        Declares streaming, cancel, approval, and session memory support.
        Does NOT declare ``fs/*`` or ``terminal/*`` capabilities — the
        self-built core has no architectural privilege and must not
        expose dangerous permissions.
        """
        return AdapterCapabilitySet(
            stream_event_support=True,
            cancel_support=True,
            approval_support=True,
            session_memory_support=True,
        )

    # ------------------------------------------------------------------
    # Protocol method 3: bootstrap_check
    # ------------------------------------------------------------------

    async def bootstrap_check(self) -> BootstrapStatus:
        """Verify the model provider is configured and available.

        Calls ``provider_factory()`` to ensure a provider can be created.
        Returns ``BootstrapStatus(ok=True, ...)`` on success, or
        ``BootstrapStatus(ok=False, ...)`` with issues on failure.
        """
        try:
            provider = self.config.provider_factory()
            model = provider.model_name()
            return BootstrapStatus(
                ok=True,
                backend_id=self.config.backend_id,
                checked_at=self._clock.now(),
                issues=[],
                metadata={
                    "model_name": model,
                    "entry_point": "in_process",
                },
            )
        except Exception as exc:
            return BootstrapStatus(
                ok=False,
                backend_id=self.config.backend_id,
                checked_at=self._clock.now(),
                issues=[f"provider_unavailable: {exc}"],
                metadata={
                    "entry_point": "in_process",
                },
            )

    # ------------------------------------------------------------------
    # Protocol method 4: submit_run
    # ------------------------------------------------------------------

    async def submit_run(self, req: RunRequest) -> RunHandle:
        """Start ``run_turn()`` as a background task and return a RunHandle.

        Extracts the user prompt from ``req.turn``, creates an
        :class:`EventEmitter` and :class:`LlmProvider` from config,
        starts ``run_turn()`` as a background ``asyncio.Task``, and
        buffers events in an ``asyncio.Queue``.
        """
        run_id = self._new_run_id()

        # 1. Create provider and tool executor from config factories
        provider = self.config.provider_factory()
        tool_executor = None
        if self.config.tool_executor_factory is not None:
            tool_executor = self.config.tool_executor_factory()

        # 2. Create EventEmitter
        emitter = EventEmitter(run_id, self.config.config)
        self._emitters[run_id] = emitter

        # 3. Build messages from RunRequest
        messages = self._build_messages(req)

        # 4. Create Run
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={
                "backend_id": self.config.backend_id,
                "entry_point": "in_process",
                "model_name": provider.model_name(),
            },
        )
        self._runs[run_id] = run
        self._events[run_id] = []
        self._artifacts[run_id] = []
        self._queues[run_id] = asyncio.Queue()

        # 5. Start background task to run run_turn() and buffer events
        task = asyncio.create_task(
            self._run_turn_background(
                run_id=run_id,
                messages=messages,
                tools=None,
                provider=provider,
                emitter=emitter,
                tool_executor=tool_executor,
            )
        )
        self._bg_tasks[run_id] = task

        # 6. Return handle
        return RunHandle(
            run_id=run_id,
            backend_run_id=run_id,
            status=AsyncTaskState.RUNNING,
            metadata={
                "backend_id": self.config.backend_id,
                "entry_point": "in_process",
            },
        )

    # ------------------------------------------------------------------
    # Protocol method 5: get_run
    # ------------------------------------------------------------------

    async def get_run(self, run_id: str) -> Run:
        """Return the current Run state, or raise KeyError."""
        if run_id not in self._runs:
            raise KeyError(f"unknown inkstatute run: {run_id}")
        return self._runs[run_id]

    # ------------------------------------------------------------------
    # Protocol method 6: stream_events
    # ------------------------------------------------------------------

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        """Yield events for a run in seq order from the event queue.

        Pulls events from the per-run ``asyncio.Queue`` until the
        ``_STREAM_DONE`` sentinel is encountered (signalling the
        background task has completed).

        Raises KeyError for unknown run_id.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown inkstatute run: {run_id}")

        queue = self._queues[run_id]
        while True:
            item = await queue.get()
            if item is _STREAM_DONE:
                break
            yield item

    # ------------------------------------------------------------------
    # Protocol method 7: cancel_run
    # ------------------------------------------------------------------

    async def cancel_run(self, run_id: str) -> Run:
        """Cancel the background task and emit run.state_changed to cancelled.

        Calls ``task.cancel()`` on the background ``asyncio.Task``.  The
        turn loop's async generator receives ``asyncio.CancelledError``
        and stops.  A ``run.state_changed`` event with status
        ``"cancelled"`` is pushed to the event queue.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown inkstatute run: {run_id}")

        run = self._runs[run_id]
        task = self._bg_tasks.get(run_id)

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Emit run.state_changed to cancelled via the emitter
        emitter = self._emitters.get(run_id)
        if emitter is not None:
            cancel_event = emitter.emit_run_state_changed("cancelled")
            await self._queues[run_id].put(cancel_event)

        # Mark that we've pushed the sentinel so the background task's
        # finally block doesn't push a duplicate.
        self._sentinel_pushed.add(run_id)

        # Push sentinel so stream_events consumers can finish
        await self._queues[run_id].put(_STREAM_DONE)

        updated = replace(run, status=AsyncTaskState.CANCELLED)
        self._runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 8: submit_approval
    # ------------------------------------------------------------------

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        """Submit an approval response.

        CRITICAL: ``terminal`` and ``execute_code`` permissions must NEVER
        be auto-approved.  If the approval metadata indicates a dangerous
        permission kind and the decision is ``"approved"``, the run is
        set to ``WAITING_FOR_USER`` and the approval is rejected —
        matching the ACP adapter and AGENTS.md SAFE-04.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown inkstatute run: {run_id}")

        run = self._runs[run_id]

        # Permission safety: reject auto-approval of dangerous permissions
        kind = str(approval.metadata.get("kind", "")).lower()
        if approval.decision == "approved" and kind in _DANGEROUS_PERMISSION_KINDS:
            updated = replace(
                run,
                status=AsyncTaskState.WAITING_FOR_USER,
                metadata={
                    **run.metadata,
                    "approval_rejected": f"dangerous_permission_{kind}",
                    "approval_id": approval.approval_id,
                    "approval_decision_recorded": False,
                    "issue": f"permission kind '{kind}' must not be auto-approved",
                },
            )
            self._runs[run_id] = updated
            return updated

        # Normal approval — store for the turn loop to consume
        self._pending_approvals.setdefault(run_id, []).append(approval)
        updated = replace(
            run,
            metadata={
                **run.metadata,
                "approval_id": approval.approval_id,
                "approval_decision": approval.decision,
                "approval_decision_recorded": True,
            },
        )
        self._runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 9: collect_artifacts
    # ------------------------------------------------------------------

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        """Return artifacts for a run (possibly empty).

        Artifacts are collected from ``artifact.created`` events in the
        event stream during the background task.
        """
        if run_id not in self._runs:
            raise KeyError(f"unknown inkstatute run: {run_id}")
        return list(self._artifacts.get(run_id, []))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Cancel all background tasks and clear run state."""
        for task in self._bg_tasks.values():
            task.cancel()
        self._bg_tasks.clear()
        self._runs.clear()
        self._events.clear()
        self._artifacts.clear()
        self._queues.clear()
        self._emitters.clear()
        self._pending_approvals.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_run_id(self) -> str:
        value = self._next_run
        self._next_run += 1
        return f"inkstatute-run-{value:03d}"

    def _build_messages(self, req: RunRequest) -> list[dict]:
        """Build the messages list for ``run_turn()`` from a RunRequest.

        Uses ``build_system_prompt()`` from Phase 102 to assemble the
        full legal system prompt with research-gate and citation spec,
        ensuring parity with the ACP server entry point.
        """
        from .prompt_assembler import AgentMode, build_system_prompt

        content = req.turn.content or ""
        system_prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.CHAT,
            retrieval_tools=[],
        )
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        return messages

    async def _run_turn_background(
        self,
        *,
        run_id: str,
        messages: list[dict],
        tools: list[dict] | None,
        provider: Any,
        emitter: EventEmitter,
        tool_executor: Any,
    ) -> None:
        """Background task: run ``run_turn()`` and push events to the queue.

        Iterates over the ``run_turn()`` async generator, pushing each
        ``RunEvent`` to the per-run ``asyncio.Queue``.  When the
        generator completes (normally or via exception), updates the run
        status and pushes the ``_STREAM_DONE`` sentinel.

        Also collects ``artifact.created`` events into the artifacts list.
        """
        queue = self._queues[run_id]
        try:
            async for event in run_turn(
                messages=messages,
                tools=tools,
                provider=provider,
                emitter=emitter,
                config=self.config.config,
                tool_executor=tool_executor,
                run_id=run_id,
            ):
                # Collect artifact.created events
                if event.event_type == "artifact.created":
                    self._collect_artifact(run_id, event)

                # Track run.state_changed for status updates
                if event.event_type == "run.state_changed":
                    status = event.payload.get("status", "")
                    self._update_run_status(run_id, status)

                self._events[run_id].append(event)
                await queue.put(event)

        except asyncio.CancelledError:
            logger.debug("run_turn cancelled for run %s", run_id)
            # cancel_run handles status + sentinel
            raise
        except Exception as exc:
            logger.warning("run_turn error for run %s: %s", run_id, exc)
            run = self._runs.get(run_id)
            if run is not None:
                self._runs[run_id] = replace(
                    run,
                    status=AsyncTaskState.FAILED,
                    metadata={**run.metadata, "error": str(exc)},
                )
        finally:
            # Only push sentinel if cancel_run hasn't already pushed one.
            # cancel_run marks the run in _sentinel_pushed before pushing
            # its own sentinel + cancelled event.
            if run_id not in self._sentinel_pushed:
                await queue.put(_STREAM_DONE)

    def _update_run_status(self, run_id: str, status: str) -> None:
        """Update the run status from a run.state_changed event payload."""
        run = self._runs.get(run_id)
        if run is None:
            return
        status_map = {
            "succeeded": AsyncTaskState.SUCCEEDED,
            "failed": AsyncTaskState.FAILED,
            "cancelled": AsyncTaskState.CANCELLED,
            "waiting_for_user": AsyncTaskState.WAITING_FOR_USER,
        }
        new_status = status_map.get(status)
        if new_status is not None:
            self._runs[run_id] = replace(run, status=new_status)

    def _collect_artifact(self, run_id: str, event: RunEvent) -> None:
        """Extract an ArtifactRecord from an artifact.created event."""
        payload = event.payload
        artifact_data = payload.get("artifact")
        if artifact_data is None:
            return

        # artifact_data may be an Artifact dataclass or a dict
        if isinstance(artifact_data, Artifact):
            artifact_id = artifact_data.artifact_id
            kind = str(artifact_data.kind)
            uri_ref = artifact_data.uri
            name = artifact_data.name
            metadata = dict(artifact_data.metadata)
        elif isinstance(artifact_data, dict):
            artifact_id = artifact_data.get("artifact_id", str(uuid.uuid4()))
            kind = str(artifact_data.get("kind", "other"))
            uri_ref = artifact_data.get("uri", "")
            name = artifact_data.get("name")
            metadata = dict(artifact_data.get("metadata", {}))
        else:
            artifact_id = getattr(artifact_data, "artifact_id", str(uuid.uuid4()))
            kind = str(getattr(artifact_data, "kind", "other"))
            uri_ref = getattr(artifact_data, "uri", "")
            name = getattr(artifact_data, "name", None)
            metadata = dict(getattr(artifact_data, "metadata", {}))

        record = ArtifactRecord(
            artifact_id=artifact_id,
            kind=kind,
            uri_ref=uri_ref,
            name=name,
            metadata=metadata,
        )
        self._artifacts[run_id].append(record)


__all__ = ["InProcessAgentCoreAdapter"]
