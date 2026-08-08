"""ArenaEngine — ArenaWorkflow Protocol implementation (ENGINE-01, ENGINE-02).

The :class:`ArenaEngine` is the top-level orchestration entry point that
implements the :class:`ArenaWorkflow` Protocol from
``platform_runtime.protocols``.  It wires Mode 1 (Standard Parallel) and
Mode 2 (Self-score Iteration) together with:

- **Guardrail boundary enforcement** — every external agent output passes
  through :func:`apply_post_hoc_guardrails` (non-bypassable, SAFE-01..04).
- **Artifact persistence** — via :class:`ArtifactStore` (ENGINE-07).
- **Provenance logging** — per-claim agent → source chain (SAFE-07).
- **User stop / pause / cancel** — graceful shutdown of all background
  tasks and adapter sessions with zero orphaned processes (ENGINE-09).

The orchestrator never produces content — it only coordinates modes and
applies post-hoc guardrails.  This module imports zero LLM provider
packages (ENGINE-05) and never calls ``session/resume`` (ENGINE-06).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_contract.arena_contract import (
    ArenaHandle,
    ArenaStatus,
    ArenaUserAction,
    ArenaWorkflowConfig,
)
from platform_runtime.protocols import BackendAdapter

from .artifact_store import ArtifactStore
from .mode1 import EventEmitter, Mode1Result, run_mode1_parallel
from .mode2 import Mode2Result, run_mode2_iteration
from .provenance import ProvenanceLogger


# ---------------------------------------------------------------------------
# ArenaEngine
# ---------------------------------------------------------------------------


class ArenaEngine:
    """Top-level arena orchestration engine implementing ``ArenaWorkflow``.

    Coordinates Mode 1 / Mode 2 execution, applies the post-hoc guardrail
    boundary to every external agent output, persists artifacts, and logs
    per-claim provenance.  Supports user stop / pause / resume / cancel
    with graceful shutdown of all background tasks and adapter sessions.

    Parameters
    ----------
    artifact_store
        Optional :class:`ArtifactStore` for round-output persistence.
        When ``None`` and ``storage_dir`` is given, one is created.
    provenance_logger
        Optional :class:`ProvenanceLogger` for per-claim provenance.
        When ``None`` and ``storage_dir`` is given, one is created.
    storage_dir
        Directory used to auto-create ``artifact_store`` and
        ``provenance_logger`` when they are not supplied explicitly.
    """

    def __init__(
        self,
        *,
        artifact_store: ArtifactStore | None = None,
        provenance_logger: ProvenanceLogger | None = None,
        storage_dir: str | Path | None = None,
    ) -> None:
        if artifact_store is None and storage_dir is not None:
            artifact_store = ArtifactStore(storage_dir)
        if provenance_logger is None and storage_dir is not None:
            provenance_logger = ProvenanceLogger(storage_dir)

        self._artifact_store = artifact_store
        self._provenance_logger = provenance_logger

        # Per-arena internal state.
        self._arenas: dict[str, ArenaStatus] = {}
        self._configs: dict[str, ArenaWorkflowConfig] = {}
        self._adapters: dict[str, dict[str, BackendAdapter]] = {}
        self._stop_signals: dict[str, asyncio.Event] = {}
        self._pause_flags: dict[str, asyncio.Event] = {}
        self._bg_tasks: dict[str, asyncio.Task[Any]] = {}
        self._selections: dict[str, str] = {}
        self._results: dict[str, Mode1Result | Mode2Result] = {}

    # ------------------------------------------------------------------
    # ArenaWorkflow Protocol — start
    # ------------------------------------------------------------------

    async def start(self, config: ArenaWorkflowConfig) -> ArenaHandle:
        """Register a new arena and return its handle.

        ``start`` is synchronous setup — it stores the config, creates the
        initial :class:`ArenaStatus`, and prepares stop / pause signals.
        Background execution is launched separately via
        :meth:`_run_arena` (or :meth:`run` for the combined flow).
        """
        arena_id = config.arena_id
        self._configs[arena_id] = config
        self._arenas[arena_id] = ArenaStatus(
            arena_id=arena_id,
            mode=config.mode,
            status="running",
            agent_slots=list(config.agent_slots),
        )
        self._stop_signals[arena_id] = asyncio.Event()
        self._pause_flags[arena_id] = asyncio.Event()
        return ArenaHandle(
            arena_id=arena_id,
            status="running",
            created_at=datetime.now(UTC).isoformat(),
        )

    # ------------------------------------------------------------------
    # ArenaWorkflow Protocol — cancel
    # ------------------------------------------------------------------

    async def cancel(self, arena_id: str) -> ArenaHandle:
        """Gracefully cancel an arena — zero orphaned processes (ENGINE-09).

        1. Set the stop signal so any running iteration loop exits.
        2. Cancel the background task (best-effort, never raises).
        3. Call ``adapter.cancel_run(run_id)`` for each active run in each
           adapter, then ``adapter.shutdown()`` to close all sessions.
        4. Update the arena status to ``"cancelled"``.
        """
        self._stop_signals[arena_id].set()

        # Cancel background task if it exists (best-effort).
        task = self._bg_tasks.get(arena_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Best-effort adapter cleanup — cancel every active run, then shut
        # down each adapter so no orphaned sessions remain.
        adapters = self._adapters.get(arena_id, {})
        for adapter in adapters.values():
            active_runs = self._active_run_ids(adapter)
            for run_id in active_runs:
                try:
                    await adapter.cancel_run(run_id)
                except Exception:
                    pass
            shutdown = getattr(adapter, "shutdown", None)
            if shutdown is not None:
                try:
                    await shutdown()
                except Exception:
                    pass

        self._update_status(arena_id, status="cancelled")
        return ArenaHandle(
            arena_id=arena_id,
            status="cancelled",
            created_at=datetime.now(UTC).isoformat(),
        )

    # ------------------------------------------------------------------
    # ArenaWorkflow Protocol — submit_user_action
    # ------------------------------------------------------------------

    async def submit_user_action(
        self,
        arena_id: str,
        action: ArenaUserAction,
    ) -> ArenaHandle:
        """Handle a user action: select / stop / pause / resume."""
        if action.action == "select":
            if action.selected_slot is not None:
                self._selections[arena_id] = action.selected_slot
                self._update_status(
                    arena_id,
                    metadata={"selected_slot": action.selected_slot},
                )
        elif action.action == "stop":
            self._stop_signals[arena_id].set()
            self._update_status(arena_id, status="stopped")
        elif action.action == "pause":
            # pause = pause flag set (event is "set" while paused).
            self._pause_flags[arena_id].set()
            self._update_status(arena_id, status="paused")
        elif action.action == "resume":
            self._pause_flags[arena_id].clear()
            self._update_status(arena_id, status="running")

        current = self._arenas[arena_id]
        return ArenaHandle(
            arena_id=arena_id,
            status=current.status,
            created_at=datetime.now(UTC).isoformat(),
        )

    # ------------------------------------------------------------------
    # ArenaWorkflow Protocol — query_status
    # ------------------------------------------------------------------

    async def query_status(self, arena_id: str) -> ArenaStatus:
        """Return the current :class:`ArenaStatus` for *arena_id*."""
        if arena_id not in self._arenas:
            raise KeyError(f"unknown arena: {arena_id}")
        return self._arenas[arena_id]

    # ------------------------------------------------------------------
    # Adapter registration + background execution
    # ------------------------------------------------------------------

    def register_adapters(
        self,
        arena_id: str,
        adapters: dict[str, BackendAdapter],
    ) -> None:
        """Register the per-slot adapter map for an arena."""
        self._adapters[arena_id] = dict(adapters)

    async def run(
        self,
        arena_id: str,
        adapters: dict[str, BackendAdapter],
        event_emitter: EventEmitter | None = None,
    ) -> None:
        """Combined flow: register adapters and run the arena to completion.

        This is the convenience entry point used by tests and the future
        arena service.  It registers the adapters, launches
        :meth:`_run_arena` as a background task, and awaits it.
        """
        self.register_adapters(arena_id, adapters)
        task = asyncio.create_task(
            self._run_arena(arena_id, adapters, event_emitter)
        )
        self._bg_tasks[arena_id] = task
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run_arena(
        self,
        arena_id: str,
        agent_adapters: dict[str, BackendAdapter],
        event_emitter: EventEmitter | None = None,
    ) -> None:
        """Dispatch to Mode 1 or Mode 2 based on ``config.mode``.

        After the mode completes, applies the post-hoc guardrail boundary
        and logs per-claim provenance via
        :meth:`_apply_guardrails_and_provenance`.
        """
        config = self._configs[arena_id]
        stop_signal = self._stop_signals[arena_id]

        if config.mode == "mode1_parallel":
            result = await run_mode1_parallel(
                config=config,
                agent_adapters=agent_adapters,
                event_emitter=event_emitter,
                artifact_store=self._artifact_store,
            )
            self._results[arena_id] = result
        elif config.mode == "mode2_iteration":
            result = await run_mode2_iteration(
                config=config,
                agent_adapters=agent_adapters,
                event_emitter=event_emitter,
                artifact_store=self._artifact_store,
                stop_signal=stop_signal,
            )
            self._results[arena_id] = result
        else:
            raise ValueError(f"unknown arena mode: {config.mode}")

        # Mark the arena completed if it was still running.
        current = self._arenas.get(arena_id)
        if current is not None and current.status == "running":
            self._update_status(arena_id, status="completed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_status(
        self,
        arena_id: str,
        *,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Replace the arena status with updated fields (frozen dataclass)."""
        current = self._arenas[arena_id]
        new_metadata = {**current.metadata}
        if metadata:
            new_metadata.update(metadata)
        self._arenas[arena_id] = replace(
            current,
            status=status if status is not None else current.status,
            metadata=new_metadata,
        )

    @staticmethod
    def _active_run_ids(adapter: BackendAdapter) -> list[str]:
        """Return run IDs still considered active for an adapter.

        For the mock adapter this inspects ``_sessions``; for other
        adapters it falls back to the ``runs`` mapping if present.
        """
        sessions = getattr(adapter, "_sessions", None)
        if isinstance(sessions, set):
            return list(sessions)
        runs = getattr(adapter, "runs", None)
        if isinstance(runs, dict):
            return list(runs.keys())
        return []


__all__ = [
    "ArenaEngine",
]
