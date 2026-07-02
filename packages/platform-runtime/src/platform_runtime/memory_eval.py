"""Repeatable in-process evaluation harness for the native memory stack."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from platform_contract.events import MemoryCandidate, MemoryRecord

from .memory import FeedbackLearningInput, FeedbackLearningPolicy, MemoryQuery, MemoryStorePolicy
from .memory_review import (
    InMemoryMemoryCandidateReviewStore,
    MemoryCandidateReviewAction,
    MemoryCandidateReviewDecider,
)
from .session_resolver import _new_id, _sha16, _timestamp


FIXED_EVAL_TENANT_A = "eval-tenant-alpha"
FIXED_EVAL_TENANT_B = "eval-tenant-beta"
FIXED_EVAL_WORKSPACE = "eval-workspace-001"
FIXED_EVAL_USER = "eval-user-001"
FIXED_EVAL_SESSION_A = "eval-session-001"
FIXED_EVAL_SESSION_B = "eval-session-002"


class MemoryEvalGateError(AssertionError):
    """Raised when one or more hard gates fail in MemoryEvalReport.assert_gates()."""


@dataclass(frozen=True, slots=True)
class MemoryEvalResult:
    """Outcome of one evaluation scenario."""

    scenario: str
    passed: bool
    relevance_score: float
    source_traceability: bool
    deletion_correctness: bool
    privacy_passed: bool
    cross_tenant_leaked: bool
    latency_ms: float | None = None
    context_size_tokens: int | None = None
    export_evidence_present: bool = False
    export_record_count: int = 0
    notes: str = ""


@dataclass(frozen=True, slots=True)
class MemoryEvalReport:
    """Aggregated report from all evaluation scenarios."""

    results: tuple[MemoryEvalResult, ...]
    baseline_score: float
    hard_gate_failures: tuple[str, ...]

    def assert_gates(self) -> None:
        """Raise MemoryEvalGateError if any hard gate has failed."""
        if self.hard_gate_failures:
            failures = "; ".join(self.hard_gate_failures)
            raise MemoryEvalGateError(f"memory eval hard gate failures: {failures}")

    @staticmethod
    def compute_baseline(results: Iterable[MemoryEvalResult]) -> float:
        """Simple pass-rate: number of passed scenarios / total scenarios."""
        all_results = list(results)
        if not all_results:
            return 0.0
        return sum(1 for r in all_results if r.passed) / len(all_results)


class MemoryEvalRunner:
    """Run the six canonical memory evaluation scenarios against the native stack.

    All scenarios are synthetic and deterministic — no external I/O, no live
    inference, no network calls.  The runner uses ``InMemoryMemoryStore`` by
    default; a custom factory can be injected for durable store testing.
    """

    def __init__(
        self,
        *,
        memory_store_factory: Callable[[], Any] | None = None,
        clock: Any | None = None,
        id_factory: Any | None = None,
    ) -> None:
        self._factory = memory_store_factory or _default_store_factory
        self._clock = clock
        self._id_factory = id_factory

    def run(self) -> MemoryEvalReport:
        """Run all six scenarios and return a gated MemoryEvalReport."""
        results = [
            self._run_multi_turn_recall(),
            self._run_cross_session_continuity(),
            self._run_deletion_and_export(),
            self._run_tenant_isolation(),
            self._run_feedback_learning_integration(),
            self._run_false_recall_rejection(),
        ]
        hard_failures = _collect_hard_gate_failures(results)
        return MemoryEvalReport(
            results=tuple(results),
            baseline_score=MemoryEvalReport.compute_baseline(results),
            hard_gate_failures=tuple(hard_failures),
        )

    # ------------------------------------------------------------------
    # Scenario implementations
    # ------------------------------------------------------------------

    def _run_multi_turn_recall(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        t0 = time.perf_counter()
        for i in range(3):
            store.upsert(_synthetic_record(
                memory_id=f"eval-multi-turn-{i:03d}",
                tenant_id=FIXED_EVAL_TENANT_A,
                scope="session",
                session_id=FIXED_EVAL_SESSION_A,
                now=now,
            ))
        results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            session_id=FIXED_EVAL_SESSION_A,
            now=now,
        ))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        passed = len(results) == 3
        return MemoryEvalResult(
            scenario="multi_turn_recall",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=_all_source_traceability(results),
            deletion_correctness=True,
            privacy_passed=_privacy_passed(results),
            cross_tenant_leaked=False,
            latency_ms=round(elapsed_ms, 2),
            notes=f"recalled {len(results)}/3",
        )

    def _run_cross_session_continuity(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        store.upsert(_synthetic_record(
            memory_id="eval-cross-session-user-001",
            tenant_id=FIXED_EVAL_TENANT_A,
            scope="user",
            related_user_id=FIXED_EVAL_USER,
            now=now,
        ))
        results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            session_id=FIXED_EVAL_SESSION_B,  # different session
            now=now,
        ))
        user_scope_results = [r for r in results if r.record.scope == "user"]
        passed = len(user_scope_results) >= 1
        return MemoryEvalResult(
            scenario="cross_session_continuity",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=_all_source_traceability(results),
            deletion_correctness=True,
            privacy_passed=_privacy_passed(results),
            cross_tenant_leaked=False,
            notes=f"user-scope records recalled across sessions: {len(user_scope_results)}",
        )

    def _run_deletion_and_export(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        store.upsert(_synthetic_record(
            memory_id="eval-delete-001",
            tenant_id=FIXED_EVAL_TENANT_A,
            scope="session",
            session_id=FIXED_EVAL_SESSION_A,
            now=now,
        ))
        store.mark_deleted("eval-delete-001", reason="eval_test_deletion")
        results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            session_id=FIXED_EVAL_SESSION_A,
            now=now,
        ))
        deleted_recalled = any(r.record.memory_id == "eval-delete-001" for r in results)
        deletion_correct = not deleted_recalled

        export_evidence_present = False
        export_record_count = 0
        export_includes_deleted = False
        if callable(getattr(store, "export_records", None)):
            exported = store.export_records(MemoryQuery(
                tenant_id=FIXED_EVAL_TENANT_A,
                workspace_id=FIXED_EVAL_WORKSPACE,
                now=now,
            ))
            export_record_count = len(exported)
            export_evidence_present = export_record_count > 0
            export_includes_deleted = any(
                r.memory_id == "eval-delete-001" for r in exported
            )

        passed = deletion_correct and (not export_evidence_present or export_includes_deleted)
        notes_parts = [f"deleted record not in results" if deletion_correct else "FAIL: deleted record recalled"]
        if export_evidence_present:
            if export_includes_deleted:
                notes_parts.append(f"export evidence includes deleted record ({export_record_count} records)")
            else:
                notes_parts.append(f"FAIL: export evidence missing deleted record ({export_record_count} records)")
                passed = False
        return MemoryEvalResult(
            scenario="deletion_and_export",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=True,
            deletion_correctness=deletion_correct,
            privacy_passed=_privacy_passed(results),
            cross_tenant_leaked=False,
            export_evidence_present=export_evidence_present,
            export_record_count=export_record_count,
            notes="; ".join(notes_parts),
        )

    def _run_tenant_isolation(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        store.upsert(_synthetic_record(
            memory_id="eval-tenant-isolation-001",
            tenant_id=FIXED_EVAL_TENANT_A,
            scope="user",
            related_user_id=FIXED_EVAL_USER,
            now=now,
        ))
        # Query with TENANT_B — must return nothing
        results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_B,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            now=now,
        ))
        leaked = any(r.record.tenant_id == FIXED_EVAL_TENANT_A for r in results)
        passed = not leaked
        return MemoryEvalResult(
            scenario="tenant_isolation",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=True,
            deletion_correctness=True,
            privacy_passed=_privacy_passed(results),
            cross_tenant_leaked=leaked,
            notes="no cross-tenant leak" if passed else "FAIL: tenant-A record returned for tenant-B query",
        )

    def _run_feedback_learning_integration(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        review_store = InMemoryMemoryCandidateReviewStore()
        decider = MemoryCandidateReviewDecider(
            memory_store=store,
            review_store=review_store,
            clock=self._clock,
            id_factory=self._id_factory,
        )

        policy = FeedbackLearningPolicy(repeated_negative_threshold=2, default_candidate_scope="user")
        learning_input = FeedbackLearningInput(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            session_id=FIXED_EVAL_SESSION_A,
            user_id=FIXED_EVAL_USER,
            feedback_events=(
                {
                    "feedback_id": "eval-fbk-001",
                    "feedback_target": "eval-result-001",
                    "event_type": "rating",
                    "action": "down",
                    "status": "resolved",
                    "user_id": FIXED_EVAL_USER,
                    "raw_payload_ref": "fixture://eval/feedback/eval-fbk-001/raw",
                },
                {
                    "feedback_id": "eval-fbk-002",
                    "feedback_target": "eval-result-001",
                    "event_type": "rating",
                    "action": "down",
                    "status": "resolved",
                    "user_id": FIXED_EVAL_USER,
                    "raw_payload_ref": "fixture://eval/feedback/eval-fbk-002/raw",
                },
            ),
            context_bundle_id="eval-bundle-001",
            run_id="eval-run-001",
            turn_id="eval-turn-001",
            now=now,
        )

        result = policy.learn(learning_input)
        for candidate in result.memory_candidates:
            # Enrich metadata with user_id so the decider can set related_user_id on the record.
            enriched_meta = dict(candidate.metadata or {})
            enriched_meta["user_id"] = FIXED_EVAL_USER
            enriched = MemoryCandidate(
                candidate_id=candidate.candidate_id,
                tenant_id=candidate.tenant_id,
                workspace_id=candidate.workspace_id,
                status=candidate.status,
                source_refs=candidate.source_refs,
                created_at=candidate.created_at,
                proposed_scope=candidate.proposed_scope,
                proposed_sensitivity=candidate.proposed_sensitivity,
                proposed_action=candidate.proposed_action,
                proposed_record_ref=candidate.proposed_record_ref,
                reason=candidate.reason,
                confidence=candidate.confidence,
                requires_human_review=candidate.requires_human_review,
                raw_payload_ref=candidate.raw_payload_ref,
                metadata=enriched_meta,
            )
            review_store.queue(enriched)

        promoted_count = 0
        for candidate in review_store.get_pending(tenant_id=FIXED_EVAL_TENANT_A):
            if candidate.proposed_action == "create_memory_candidate":
                decision = decider.decide(
                    candidate_id=candidate.candidate_id,
                    action=MemoryCandidateReviewAction.approve,
                    reviewer_id="eval-harness",
                )
                if decision.promotion_status == "promoted":
                    promoted_count += 1

        # Verify promoted records are recalled
        query_results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            now=now,
        ))
        passed = promoted_count > 0 and len(query_results) >= promoted_count
        return MemoryEvalResult(
            scenario="feedback_learning_integration",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=_all_source_traceability(query_results),
            deletion_correctness=True,
            privacy_passed=_privacy_passed(query_results),
            cross_tenant_leaked=False,
            notes=f"promoted {promoted_count} candidate(s), recalled {len(query_results)}",
        )

    def _run_false_recall_rejection(self) -> MemoryEvalResult:
        now = _now(self._clock)
        store = self._factory()
        store.upsert(_synthetic_record(
            memory_id="eval-false-recall-001",
            tenant_id=FIXED_EVAL_TENANT_A,
            scope="session",
            session_id=FIXED_EVAL_SESSION_A,
            now=now,
        ))
        # Query with session B — must return nothing
        results = store.search(MemoryQuery(
            tenant_id=FIXED_EVAL_TENANT_A,
            workspace_id=FIXED_EVAL_WORKSPACE,
            user_id=FIXED_EVAL_USER,
            session_id=FIXED_EVAL_SESSION_B,
            now=now,
        ))
        false_recalled = any(r.record.memory_id == "eval-false-recall-001" for r in results)
        passed = not false_recalled
        return MemoryEvalResult(
            scenario="false_recall_rejection",
            passed=passed,
            relevance_score=1.0 if passed else 0.0,
            source_traceability=True,
            deletion_correctness=True,
            privacy_passed=True,
            cross_tenant_leaked=False,
            notes="session-scoped record not leaked to other session" if passed else "FAIL: session scope leak",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_store_factory() -> Any:
    from .memory import InMemoryMemoryStore
    return InMemoryMemoryStore()


def _now(clock: Any | None) -> str:
    if clock is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if callable(clock):
        r = clock()
        return r if isinstance(r, str) else str(r)
    return str(clock)


def _synthetic_record(
    *,
    memory_id: str,
    tenant_id: str,
    scope: str,
    session_id: str | None = None,
    related_user_id: str | None = None,
    now: str,
) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        tenant_id=tenant_id,
        workspace_id=FIXED_EVAL_WORKSPACE,
        scope=scope,
        status="active",
        sensitivity="internal",
        created_at=now,
        updated_at=now,
        source_refs=[f"fixture://eval/memory/{memory_id}"],
        summary=f"Synthetic eval record {memory_id}",
        subject="eval",
        related_user_id=related_user_id or FIXED_EVAL_USER,
        session_id=session_id,
        confidence=0.8,
        metadata={"privacy": "refs_hashes_lengths_statuses_only"},
    )


def _all_source_traceability(results: Any) -> bool:
    for r in results:
        if not r.record.source_refs:
            return False
        for ref in r.record.source_refs:
            if "://" not in str(ref):
                return False
    return True


def _privacy_passed(results: Any) -> bool:
    _bad_keys = {
        "raw_payload", "raw_text", "payload_text", "full_text",
        "document_text", "customer_document_text", "case_facts", "callback_body",
    }
    for r in results:
        meta = r.record.metadata or {}
        if _bad_keys & set(meta):
            return False
    return True


def _collect_hard_gate_failures(results: list[MemoryEvalResult]) -> list[str]:
    failures: list[str] = []
    for r in results:
        if r.cross_tenant_leaked:
            failures.append(f"HARD: cross-tenant leak in scenario '{r.scenario}'")
        if not r.privacy_passed:
            failures.append(f"HARD: privacy gate failure in scenario '{r.scenario}'")
    deletion_result = next((r for r in results if r.scenario == "deletion_and_export"), None)
    if deletion_result is not None and not deletion_result.deletion_correctness:
        failures.append("HARD: deletion_and_export — deleted record was recalled")
    false_result = next((r for r in results if r.scenario == "false_recall_rejection"), None)
    if false_result is not None and not false_result.passed:
        failures.append("HARD: false_recall_rejection — session-scoped record leaked to wrong session")
    return failures


__all__ = [
    "MemoryEvalGateError",
    "MemoryEvalReport",
    "MemoryEvalResult",
    "MemoryEvalRunner",
]
