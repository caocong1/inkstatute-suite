"""ArenaEngine — ArenaWorkflow Protocol implementation (ENGINE-01, ENGINE-02).

The :class:`ArenaEngine` is the top-level orchestration entry point that
implements the :class:`ArenaWorkflow` Protocol from
``platform_runtime.protocols``.  It wires Mode 1 (Standard Parallel),
Mode 2 (Self-score Iteration), Mode 3 (Arena Review), and Mode 4
(Adversarial) together with:

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
from .guardrail_boundary import GuardrailResult, apply_post_hoc_guardrails
from .mode1 import EventEmitter, Mode1Result, run_mode1_parallel
from .mode2 import Mode2Result, run_mode2_iteration
from .mode3 import Mode3Result, run_mode3_arena_review
from .mode4 import Mode4Result, run_mode4_adversarial
from .provenance import ProvenanceLogger
from .slot_runner import SlotResult


# ---------------------------------------------------------------------------
# ArenaEngine
# ---------------------------------------------------------------------------


class ArenaEngine:
    """Top-level arena orchestration engine implementing ``ArenaWorkflow``.

    Coordinates Mode 1 / Mode 2 / Mode 3 / Mode 4 execution, applies the
    post-hoc guardrail boundary to every external agent output, persists
    artifacts, and logs per-claim provenance.  Supports user stop / pause
    / resume / cancel with graceful shutdown of all background tasks and
    adapter sessions.

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
        self._results: dict[str, Mode1Result | Mode2Result | Mode3Result | Mode4Result] = {}
        self._synthesis_adapters: dict[str, BackendAdapter] = {}
        self._adversarial_adapters: dict[str, BackendAdapter] = {}

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

    def register_synthesis_adapter(
        self,
        arena_id: str,
        adapter: BackendAdapter,
    ) -> None:
        """Register the synthesis adapter for Mode 3 / Mode 4.

        The synthesis adapter must be a **separate** :class:`BackendAdapter`
        instance — not one of the candidate slot adapters.  The orchestrator
        never produces content; synthesis is delegated to this adapter.
        """
        self._synthesis_adapters[arena_id] = adapter

    def register_adversarial_adapter(
        self,
        arena_id: str,
        adapter: BackendAdapter,
    ) -> None:
        """Register the adversarial adapter for Mode 4.

        The adversarial adapter must be a **separate** :class:`BackendAdapter`
        instance — not one of the candidate slot adapters or the synthesis
        adapter.  The orchestrator never produces content; adversarial
        challenges are delegated to this adapter.
        """
        self._adversarial_adapters[arena_id] = adapter

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
        """Dispatch to Mode 1, 2, 3, or 4 based on ``config.mode``.

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
            await self._apply_guardrails_and_provenance(
                arena_id,
                result.slot_results,
                self._external_map(agent_adapters),
            )
        elif config.mode == "mode2_iteration":
            result = await run_mode2_iteration(
                config=config,
                agent_adapters=agent_adapters,
                event_emitter=event_emitter,
                artifact_store=self._artifact_store,
                stop_signal=stop_signal,
            )
            self._results[arena_id] = result
            # Mode 2 best results → SlotResult-shaped dict for guardrails.
            slot_results: dict[str, SlotResult] = {}
            for slot_id, state in result.best_results.items():
                slot_results[slot_id] = SlotResult(
                    slot_id=slot_id,
                    status="success",
                    content=state.content,
                    metadata=dict(state.metadata),
                )
            await self._apply_guardrails_and_provenance(
                arena_id,
                slot_results,
                self._external_map(agent_adapters),
            )
        elif config.mode == "mode3_arena_review":
            # Build backend_families dict from each slot adapter.
            backend_families = self._build_backend_families(agent_adapters)
            synthesis_adapter = self._synthesis_adapters[arena_id]
            result = await run_mode3_arena_review(
                config=config,
                agent_adapters=agent_adapters,
                synthesis_adapter=synthesis_adapter,
                event_emitter=event_emitter,
                stop_signal=stop_signal,
                artifact_store=self._artifact_store,
                backend_families=backend_families,
                provenance_logger=self._provenance_logger,
            )
            self._results[arena_id] = result
            # Apply guardrails to synthesis output.
            if result.synthesis_content is not None:
                synthesis_slot_results: dict[str, SlotResult] = {
                    "synthesis": SlotResult(
                        slot_id="synthesis",
                        status="success",
                        content=result.synthesis_content,
                        metadata={},
                    ),
                }
                synthesis_external = {
                    "synthesis": synthesis_adapter.backend_id() != "inkstatute-agent",
                }
                await self._apply_guardrails_and_provenance(
                    arena_id,
                    synthesis_slot_results,
                    synthesis_external,
                )
        elif config.mode == "mode4_adversarial":
            # Build backend_families dict from each slot adapter.
            backend_families = self._build_backend_families(agent_adapters)
            synthesis_adapter = self._synthesis_adapters[arena_id]
            adversarial_adapter = self._adversarial_adapters[arena_id]
            result = await run_mode4_adversarial(
                config=config,
                agent_adapters=agent_adapters,
                synthesis_adapter=synthesis_adapter,
                adversarial_adapter=adversarial_adapter,
                event_emitter=event_emitter,
                stop_signal=stop_signal,
                artifact_store=self._artifact_store,
                backend_families=backend_families,
                provenance_logger=self._provenance_logger,
            )
            self._results[arena_id] = result
            # Apply guardrails to final synthesis output.
            if result.final_synthesis_content is not None:
                final_slot_results: dict[str, SlotResult] = {
                    "synthesis": SlotResult(
                        slot_id="synthesis",
                        status="success",
                        content=result.final_synthesis_content,
                        metadata={},
                    ),
                }
                final_external = {
                    "synthesis": synthesis_adapter.backend_id() != "inkstatute-agent",
                }
                await self._apply_guardrails_and_provenance(
                    arena_id,
                    final_slot_results,
                    final_external,
                )
        else:
            raise ValueError(f"unknown arena mode: {config.mode}")

        # Mark the arena completed if it was still running.
        current = self._arenas.get(arena_id)
        if current is not None and current.status == "running":
            self._update_status(arena_id, status="completed")

    # ------------------------------------------------------------------
    # Guardrail + provenance wiring (SAFE-01..04, SAFE-07)
    # ------------------------------------------------------------------

    async def _apply_guardrails_and_provenance(
        self,
        arena_id: str,
        slot_results: dict[str, SlotResult],
        is_external: dict[str, bool],
    ) -> None:
        """Apply the post-hoc guardrail boundary and log per-claim provenance.

        For every slot with content, this:

        1. Calls :func:`apply_post_hoc_guardrails` — non-bypassable for
           external agents (SAFE-01).  No code path delivers external
           agent content to the user without this call.
        2. Records ``GuardrailResult.requires_human_review`` in the arena
           status metadata (SAFE-04).
        3. Logs one :class:`ProvenanceChain` per extracted claim via
           :class:`ProvenanceLogger` (SAFE-07).
        """
        review_metadata: dict[str, Any] = {}
        for slot_id, slot_result in slot_results.items():
            if slot_result.content is None:
                continue
            external = is_external.get(slot_id, True)
            guardrail: GuardrailResult = await apply_post_hoc_guardrails(
                content=slot_result.content,
                is_external=external,
            )
            review_metadata[f"{slot_id}_requires_human_review"] = (
                guardrail.requires_human_review
            )
            review_metadata[f"{slot_id}_guardrail_skipped"] = guardrail.skipped

            # Provenance — log one chain per extracted claim.  When the
            # citation audit produced items, log each citation reference;
            # otherwise log the polished content as a single claim so the
            # agent → source chain is always traceable.
            if self._provenance_logger is not None:
                claims = self._extract_claims(guardrail, slot_result.content)
                for claim in claims:
                    self._provenance_logger.log_claim(
                        arena_id=arena_id,
                        claim=claim,
                        agent_slot=slot_id,
                        citation_audit=guardrail.citation_audit,
                    )

        if review_metadata:
            self._update_status(arena_id, metadata=review_metadata)

    @staticmethod
    def _extract_claims(
        guardrail: GuardrailResult,
        content: str,
    ) -> list[str]:
        """Extract claim strings for provenance logging.

        When the citation audit produced items, each citation's
        ``reference`` is a claim.  When there are no citations, the
        (polished) content itself is logged as a single claim so the
        chain is never empty.
        """
        audit = guardrail.citation_audit
        if audit is not None and getattr(audit, "items", None):
            return [item.reference for item in audit.items]
        return [guardrail.polished_content or content]

    def _external_map(
        self,
        agent_adapters: dict[str, BackendAdapter],
    ) -> dict[str, bool]:
        """Build a slot → is_external map.

        An adapter is considered external when its ``backend_id`` is not
        the self-built core (``inkstatute-agent``).  The self-built core
        already runs guardrails inside ``turn_loop.py`` (SAFE-01), so
        post-hoc application is skipped for it.
        """
        external_map: dict[str, bool] = {}
        for slot_id, adapter in agent_adapters.items():
            backend_id = ""
            try:
                backend_id = adapter.backend_id()
            except Exception:
                pass
            external_map[slot_id] = backend_id != "inkstatute-agent"
        return external_map

    @staticmethod
    def _build_backend_families(
        agent_adapters: dict[str, BackendAdapter],
    ) -> dict[str, str]:
        """Build a slot → backend_family map for cross-family enforcement.

        Calls ``adapter.backend_family()`` for each slot adapter to
        determine the model family.  Used by Mode 3 and Mode 4 to
        enforce cross-family review pairing (SAFE-06).
        """
        families: dict[str, str] = {}
        for slot_id, adapter in agent_adapters.items():
            try:
                families[slot_id] = adapter.backend_family()
            except Exception:
                # Fallback: use backend_id as family if backend_family()
                # is not available.
                families[slot_id] = adapter.backend_id()
        return families

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
