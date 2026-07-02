"""Memory recall orchestration: retrieve, assemble, and record MemoryUse evidence."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from platform_contract.events import MemoryRecord, MemoryUse

from .context_assembler import ContextAssembler, ContextAssemblyInput, ContextAssemblyResult
from .context_assembler import InMemoryRollingSummaryStore
from .memory import MemoryQuery, MemorySearchResult, MemoryStorePolicy
from .memory_adapters import MemoryStoreAdapter
from .session_resolver import SessionScope, _new_id, _timestamp


class OrchestratorIsolationError(ValueError):
    """Raised when a recall query scope does not match the resolved session scope."""


class MemoryUseEvidenceFailureMode(StrEnum):
    """Policy for evidence-capable MemoryUse sinks that fail while recording."""

    FAIL_CLOSED = "fail_closed"
    DEGRADED = "degraded"
    IGNORE_IF_UNSUPPORTED = "ignore_if_unsupported"


class MemoryUseEvidenceError(RuntimeError):
    """Raised when MemoryUse evidence cannot be recorded under fail-closed policy."""

    def __init__(
        self,
        code: str,
        *,
        memory_ids: tuple[str, ...] = (),
        failed_count: int = 0,
        error_class: str = "",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.memory_ids = memory_ids
        self.failed_count = failed_count
        self.error_class = error_class


@dataclass(frozen=True, slots=True)
class MemoryOrchestratorPolicy:
    """Recall policy: limits and behaviour toggles for the memory orchestration pipeline."""

    max_memory_refs: int = 8
    """Maximum number of memory refs to pass into ContextAssemblyInput."""

    max_recent_turn_refs: int = 12
    """Passed through to ContextAssemblyPolicy as a reference limit."""

    max_artifact_refs: int = 8
    """Passed through to ContextAssemblyPolicy as a reference limit."""

    max_feedback_correction_refs: int = 6
    """Passed through to ContextAssemblyPolicy as a reference limit."""

    memory_search_text: str = ""
    """Text used for memory relevance search; empty string matches all records."""

    record_memory_use: bool = True
    """When True, record a MemoryUse for each selected memory (if store supports it)."""

    memory_use_evidence_failure_mode: MemoryUseEvidenceFailureMode = MemoryUseEvidenceFailureMode.DEGRADED
    """How to handle failures from evidence-capable MemoryUse sinks."""


class MemoryOrchestrator:
    """Compose MemoryStoreAdapter + InMemoryRollingSummaryStore + ContextAssembler.

    Retrieves recalled memory refs for the resolved scope, builds a bounded
    ``ContextBundle``, and records ``MemoryUse`` evidence — all without
    embedding raw legal/customer text.

    ``DefaultRunRuntime`` and WeCom channel constructors are unchanged;
    hosts that want orchestrated recall inject this class optionally.
    """

    def __init__(
        self,
        *,
        memory_store: MemoryStoreAdapter,
        summary_store: InMemoryRollingSummaryStore | None = None,
        context_assembler: ContextAssembler | None = None,
        policy: MemoryOrchestratorPolicy | None = None,
        clock: Any | None = None,
        id_factory: Any | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._summary_store = summary_store
        self._assembler = context_assembler or ContextAssembler()
        self._policy = policy or MemoryOrchestratorPolicy()
        self._clock = clock
        self._id_factory = id_factory

    def recall_and_assemble(
        self,
        *,
        scope: SessionScope,
        session_id: str,
        turn_id: str,
        current_turn_ref: str,
        current_turn_text: str | None = None,
        recent_turn_refs: tuple[str, ...] = (),
        artifact_refs: tuple[str, ...] = (),
        feedback_correction_refs: tuple[str, ...] = (),
        output_policy_ref: str | None = None,
        run_id: str | None = None,
        now: str | None = None,
    ) -> ContextAssemblyResult:
        """Recall memories, assemble context, and record MemoryUse evidence.

        Args:
            scope: Session scope for tenant/workspace/user/session isolation.
            session_id: Current session identifier.
            turn_id: Current turn identifier.
            current_turn_ref: Reference URI for the current turn.
            current_turn_text: Optional safe current turn text (for token estimation).
            recent_turn_refs: Recent turn reference URIs.
            artifact_refs: Artifact reference URIs.
            feedback_correction_refs: Feedback correction reference URIs.
            output_policy_ref: Optional output policy reference URI.
            run_id: Optional run identifier for ContextAssemblyInput.
            now: Optional ISO timestamp string; defaults to current UTC time.

        Returns:
            ContextAssemblyResult with recalled memory refs and optional summary ref.

        Raises:
            OrchestratorIsolationError: If the scope does not match what was queried.
        """
        now_str = now or _clock_now(self._clock)

        # Build and isolation-check the memory query.
        query = MemoryQuery(
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            user_id=scope.user_id,
            session_id=session_id,
            text=self._policy.memory_search_text,
            now=now_str,
        )
        _check_isolation(query, scope)

        # Recall: search and select top-N results.
        search_results: tuple[MemorySearchResult, ...] = self._memory_store.search(query)
        selected = search_results[: max(0, self._policy.max_memory_refs)]
        memory_refs = tuple(r.record.memory_id for r in selected)

        # Retrieve rolling summary if available.
        summary = None
        if self._summary_store is not None:
            summary = self._summary_store.get(scope, session_id)

        # Build ContextAssemblyInput.
        assembly_input = ContextAssemblyInput(
            scope=scope,
            session_id=session_id,
            turn_id=turn_id,
            current_turn_ref=current_turn_ref,
            current_turn_text=current_turn_text,
            run_id=run_id,
            recent_turn_refs=recent_turn_refs,
            artifact_refs=artifact_refs,
            feedback_correction_refs=feedback_correction_refs,
            memory_refs=memory_refs,
            output_policy_ref=output_policy_ref,
            rolling_summary=summary,
        )

        result = self._assembler.assemble(assembly_input, now=now_str, id_factory=self._id_factory)

        evidence_metadata = _record_memory_use_evidence(
            memory_store=self._memory_store,
            selected=selected,
            result=result,
            policy=self._policy,
            now=now_str,
            run_id=run_id,
            turn_id=turn_id,
            id_factory=self._id_factory,
        )

        return replace(
            result,
            metadata={
                **result.metadata,
                **evidence_metadata,
            },
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_isolation(query: MemoryQuery, scope: SessionScope) -> None:
    """Raise OrchestratorIsolationError if query scope does not match session scope."""
    if query.tenant_id != scope.tenant_id:
        raise OrchestratorIsolationError(
            f"recall query tenant_id {query.tenant_id!r} does not match scope tenant_id {scope.tenant_id!r}"
        )
    if query.workspace_id is not None and query.workspace_id != scope.workspace_id:
        raise OrchestratorIsolationError(
            f"recall query workspace_id {query.workspace_id!r} does not match scope workspace_id {scope.workspace_id!r}"
        )


def _clock_now(clock: Any | None) -> str:
    if clock is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if callable(clock):
        result = clock()
        if isinstance(result, str):
            return result
        if isinstance(result, datetime):
            return result.isoformat()
        return str(result)
    if isinstance(clock, str):
        return clock
    return str(clock)


def _record_memory_use_evidence(
    *,
    memory_store: MemoryStoreAdapter,
    selected: tuple[MemorySearchResult, ...],
    result: ContextAssemblyResult,
    policy: MemoryOrchestratorPolicy,
    now: str,
    run_id: str | None,
    turn_id: str,
    id_factory: Any | None,
) -> dict[str, Any]:
    selected_count = len(selected)
    base = {
        "memory_use_evidence_selected_count": selected_count,
        "memory_use_evidence_recorded_count": 0,
        "memory_use_evidence_failed_count": 0,
        "memory_use_evidence_privacy": "refs_ids_counts_statuses_only",
    }
    if selected_count == 0:
        return {
            **base,
            "memory_use_evidence_status": "not_applicable",
        }
    if not policy.record_memory_use:
        return {
            **base,
            "memory_use_evidence_status": "disabled",
        }
    if not hasattr(memory_store, "record_memory_use"):
        return {
            **base,
            "memory_use_evidence_status": "unsupported",
            "memory_use_evidence_error_code": "memory_use_evidence_unsupported",
        }

    context_bundle_id = result.bundle.context_bundle_id
    recorded_count = 0
    failed_memory_ids: list[str] = []
    error_class = ""
    for search_result in selected:
        memory_id = search_result.record.memory_id
        use = MemoryUse(
            use_id=_new_id(id_factory, "memory-use"),
            memory_id=memory_id,
            context_bundle_id=context_bundle_id,
            used_at=now,
            purpose="context_assembly",
            run_id=run_id,
            turn_id=turn_id,
            relevance_score=search_result.relevance_score,
            policy_result="selected",
            source_refs=[f"memory://{memory_id}"],
            metadata={"privacy": "no_raw_payload_or_legal_text_stored"},
        )
        try:
            memory_store.record_memory_use(use)  # type: ignore[attr-defined]
            recorded_count += 1
        except Exception as exc:  # noqa: BLE001
            failed_memory_ids.append(memory_id)
            if not error_class:
                error_class = type(exc).__name__

    if failed_memory_ids:
        code = "memory_use_evidence_record_failed"
        if policy.memory_use_evidence_failure_mode == MemoryUseEvidenceFailureMode.FAIL_CLOSED:
            raise MemoryUseEvidenceError(
                code,
                memory_ids=tuple(failed_memory_ids),
                failed_count=len(failed_memory_ids),
                error_class=error_class,
            )
        return {
            **base,
            "memory_use_evidence_status": "degraded",
            "memory_use_evidence_recorded_count": recorded_count,
            "memory_use_evidence_failed_count": len(failed_memory_ids),
            "memory_use_evidence_error_code": code,
            "memory_use_evidence_error_class": error_class,
            "memory_use_evidence_memory_ids": list(failed_memory_ids),
        }

    return {
        **base,
        "memory_use_evidence_status": "recorded",
        "memory_use_evidence_recorded_count": recorded_count,
    }


__all__ = [
    "MemoryUseEvidenceError",
    "MemoryUseEvidenceFailureMode",
    "MemoryOrchestratorPolicy",
    "MemoryOrchestrator",
    "OrchestratorIsolationError",
]
