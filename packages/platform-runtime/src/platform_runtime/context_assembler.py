"""Backend-neutral, privacy-safe short-term context assembly support."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from platform_contract.events import ContextBundle, JsonObject

from .session_resolver import ActiveTaskSnapshot, PendingInterruptSnapshot, SessionScope
from .session_resolver import _clock_now, _coerce_datetime, _json_clone, _new_id, _safe_metadata, _sha16, _timestamp
from .store import ContractLogPrivacyError


class ContextAssemblyBudgetError(ValueError):
    """Raised when protected context alone exceeds the configured budget."""


@dataclass(frozen=True, slots=True)
class RollingSummaryRecord:
    scope: SessionScope
    session_id: str
    summary_ref: str
    task_intent_refs: tuple[str, ...] = ()
    user_constraint_refs: tuple[str, ...] = ()
    unanswered_question_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    outcome_refs: tuple[str, ...] = ()
    text_sha256_16: str | None = None
    text_length: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: JsonObject = field(default_factory=dict)

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "event": "rolling_summary",
            "session_id": self.session_id,
            "summary_ref": self.summary_ref,
            "task_intent_refs": list(self.task_intent_refs),
            "user_constraint_refs": list(self.user_constraint_refs),
            "unanswered_question_refs": list(self.unanswered_question_refs),
            "artifact_refs": list(self.artifact_refs),
            "outcome_refs": list(self.outcome_refs),
            "text_sha256_16": self.text_sha256_16,
            "text_length": self.text_length,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "scope": self.scope.as_event(),
            "metadata": _safe_metadata(
                {
                    "privacy": "no_raw_payload_or_legal_text_stored",
                    **self.metadata,
                }
            ),
            "privacy": "no_raw_payload_or_legal_text_stored",
        }
        return _json_clone(event)


class InMemoryRollingSummaryStore:
    """Copy-safe scoped support store for embedded hosts and tests."""

    def __init__(self, *, clock: Any | None = None) -> None:
        self._clock = clock
        self._summaries: dict[tuple[tuple[str, ...], str], RollingSummaryRecord] = {}

    def upsert(self, record: RollingSummaryRecord) -> None:
        self._summaries[(_scope_key(record.scope), record.session_id)] = _copy_summary(record)

    def get(self, scope: SessionScope, session_id: str) -> RollingSummaryRecord | None:
        record = self._summaries.get((_scope_key(scope), session_id))
        return _copy_summary(record) if record is not None else None

    def list_for_scope(self, scope: SessionScope) -> tuple[RollingSummaryRecord, ...]:
        scope_key = _scope_key(scope)
        return tuple(_copy_summary(record) for (stored_scope, _), record in self._summaries.items() if stored_scope == scope_key)


@dataclass(frozen=True, slots=True)
class ContextAssemblyPolicy:
    budget_tokens: int = 2048
    chars_per_token: int = 4
    max_recent_turn_refs: int = 12
    max_artifact_refs: int = 8
    max_feedback_correction_refs: int = 6
    max_memory_refs: int = 8
    trim_strategy: str = "protected_then_feedback_memory_recent_artifact"


@dataclass(frozen=True, slots=True)
class ContextAssemblyInput:
    scope: SessionScope
    session_id: str
    turn_id: str
    current_turn_ref: str
    current_turn_text: str | None = None
    current_turn_raw_payload_ref: str | None = None
    run_id: str | None = None
    recent_turn_refs: tuple[str, ...] = ()
    active_task: ActiveTaskSnapshot | None = None
    active_task_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    feedback_correction_refs: tuple[str, ...] = ()
    pending_interrupt: PendingInterruptSnapshot | None = None
    rolling_summary: RollingSummaryRecord | None = None
    memory_refs: tuple[str, ...] = ()
    output_constraints_ref: str | None = None
    output_policy_ref: str | None = None
    raw_payload_refs: tuple[str, ...] = ()
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    bundle: ContextBundle
    estimated_tokens: int
    dropped_sections: JsonObject = field(default_factory=dict)
    protected_sections: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)
    privacy: str = "no_raw_payload_or_legal_text_stored"

    def as_event(self) -> JsonObject:
        event = _context_bundle_as_event(self.bundle)
        event["metadata"] = _safe_metadata(
            {
                **event.get("metadata", {}),
                "estimated_tokens": self.estimated_tokens,
                "dropped_sections": _json_clone(self.dropped_sections),
                "protected_sections": list(self.protected_sections),
                "privacy": self.privacy,
                **self.metadata,
            }
        )
        event["privacy"] = self.privacy
        return _json_clone(event)


class ContextAssembler:
    """Assemble bounded context bundles without backend or channel coupling."""

    def __init__(
        self,
        *,
        policy: ContextAssemblyPolicy | None = None,
        clock: Callable[[], datetime | str] | Any | None = None,
        id_factory: Callable[[str], str] | Any | None = None,
    ) -> None:
        self.policy = policy or ContextAssemblyPolicy()
        self.clock = clock
        self.id_factory = id_factory

    def assemble(
        self,
        input: ContextAssemblyInput,
        *,
        policy: ContextAssemblyPolicy | None = None,
        now: datetime | str | None = None,
        id_factory: Callable[[str], str] | Any | None = None,
    ) -> ContextAssemblyResult:
        raise NotImplementedError("ContextAssembler budget assembly is implemented in the next task")


def _copy_summary(record: RollingSummaryRecord) -> RollingSummaryRecord:
    event = record.as_event()
    return RollingSummaryRecord(
        scope=record.scope,
        session_id=str(event["session_id"]),
        summary_ref=str(event["summary_ref"]),
        task_intent_refs=tuple(event.get("task_intent_refs", ())),
        user_constraint_refs=tuple(event.get("user_constraint_refs", ())),
        unanswered_question_refs=tuple(event.get("unanswered_question_refs", ())),
        artifact_refs=tuple(event.get("artifact_refs", ())),
        outcome_refs=tuple(event.get("outcome_refs", ())),
        text_sha256_16=event.get("text_sha256_16"),
        text_length=int(event.get("text_length", 0)),
        created_at=str(event.get("created_at", "")),
        updated_at=str(event.get("updated_at", "")),
        metadata=_safe_metadata(record.metadata),
    )


def _scope_key(scope: SessionScope) -> tuple[str, ...]:
    return (
        scope.tenant_id,
        scope.workspace_id,
        scope.channel_id,
        scope.user_id,
        scope.bot_instance_id,
        scope.conversation_id,
        scope.thread_id or "",
    )


def _context_bundle_as_event(bundle: ContextBundle) -> JsonObject:
    event: JsonObject = {
        "context_bundle_id": bundle.context_bundle_id,
        "tenant_id": bundle.tenant_id,
        "workspace_id": bundle.workspace_id,
        "session_id": bundle.session_id,
        "created_at": bundle.created_at,
        "budget_tokens": bundle.budget_tokens,
        "recent_turn_refs": list(bundle.recent_turn_refs),
        "active_task_refs": list(bundle.active_task_refs),
        "artifact_refs": list(bundle.artifact_refs),
        "memory_refs": list(bundle.memory_refs),
        "raw_payload_refs": list(bundle.raw_payload_refs),
        "industry_context": _safe_metadata(bundle.industry_context),
        "metadata": _safe_metadata(bundle.metadata),
    }
    optional = {
        "run_id": bundle.run_id,
        "turn_id": bundle.turn_id,
        "summary_ref": bundle.summary_ref,
        "interrupt_id": bundle.interrupt_id,
        "trim_strategy": bundle.trim_strategy,
    }
    event.update({key: value for key, value in optional.items() if value is not None})
    return _json_clone(event)


__all__ = [
    "ContextAssembler",
    "ContextAssemblyBudgetError",
    "ContextAssemblyInput",
    "ContextAssemblyPolicy",
    "ContextAssemblyResult",
    "InMemoryRollingSummaryStore",
    "RollingSummaryRecord",
]
