"""Backend-neutral, privacy-safe short-term context assembly support."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any

from platform_contract.events import ContextBundle, JsonObject

from .session_resolver import ActiveTaskSnapshot, PendingInterruptSnapshot, SessionScope
from .session_resolver import _clock_now, _json_clone, _new_id, _safe_metadata, _sha16, _timestamp


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
        cfg = policy or self.policy
        current = _timestamp(now or _clock_now(self.clock))
        id_source = id_factory or self.id_factory
        safe_input_metadata = _safe_metadata(input.metadata)
        safe_industry_context = _safe_metadata(input.industry_context)

        recent_turn_refs = list(input.recent_turn_refs[: max(0, cfg.max_recent_turn_refs)])
        artifact_refs = list(input.artifact_refs[: max(0, cfg.max_artifact_refs)])
        feedback_correction_refs = list(input.feedback_correction_refs[: max(0, cfg.max_feedback_correction_refs)])
        memory_refs = list(input.memory_refs[: max(0, cfg.max_memory_refs)])
        active_task_refs = _active_task_refs(input)
        raw_payload_refs = _raw_payload_refs(input)
        summary = _copy_summary(input.rolling_summary) if input.rolling_summary is not None else None

        dropped_sections: JsonObject = {
            "recent_turn_refs": max(0, len(input.recent_turn_refs) - len(recent_turn_refs)),
            "artifact_refs": max(0, len(input.artifact_refs) - len(artifact_refs)),
            "feedback_correction_refs": max(0, len(input.feedback_correction_refs) - len(feedback_correction_refs)),
            "memory_refs": max(0, len(input.memory_refs) - len(memory_refs)),
            "active_task_refs": 0,
        }
        protected_sections = _protected_sections(input)

        protected_bundle = self._bundle(
            input=input,
            policy=cfg,
            created_at=current,
            context_bundle_id=_new_id(id_source, "context-bundle"),
            recent_turn_refs=(),
            active_task_refs=(),
            artifact_refs=(),
            memory_refs=(),
            raw_payload_refs=raw_payload_refs,
            summary_ref=None,
            metadata=_protected_bundle_metadata(
                input=input,
                dropped_sections=dropped_sections,
                protected_sections=protected_sections,
                safe_input_metadata=safe_input_metadata,
            ),
            industry_context=safe_industry_context,
        )
        protected_tokens = _estimate_tokens(_context_bundle_as_event(protected_bundle), cfg)
        if protected_tokens > cfg.budget_tokens:
            raise ContextAssemblyBudgetError(
                f"protected context requires {protected_tokens} estimated tokens, budget is {cfg.budget_tokens}"
            )

        context_bundle_id = _new_id(id_source, "context-bundle")
        bundle = self._bundle(
            input=input,
            policy=cfg,
            created_at=current,
            context_bundle_id=context_bundle_id,
            recent_turn_refs=recent_turn_refs,
            active_task_refs=active_task_refs,
            artifact_refs=artifact_refs,
            memory_refs=memory_refs,
            raw_payload_refs=raw_payload_refs,
            summary_ref=summary.summary_ref if summary is not None else None,
            metadata=_bundle_metadata(
                input=input,
                feedback_correction_refs=feedback_correction_refs,
                dropped_sections=dropped_sections,
                estimated_tokens=0,
                protected_sections=protected_sections,
                safe_input_metadata=safe_input_metadata,
                active_task_refs=active_task_refs,
            ),
            industry_context=safe_industry_context,
        )
        estimated = _estimate_tokens(_context_bundle_as_event(bundle), cfg)

        trim_order = (
            ("feedback_correction_refs", feedback_correction_refs),
            ("memory_refs", memory_refs),
            ("recent_turn_refs", recent_turn_refs),
            ("artifact_refs", artifact_refs),
            ("active_task_refs", active_task_refs),
        )
        while estimated > cfg.budget_tokens:
            trimmed = False
            for section, values in trim_order:
                if values:
                    values.pop()
                    dropped_sections[section] = int(dropped_sections.get(section, 0)) + 1
                    trimmed = True
                    break
            if not trimmed:
                break
            bundle = self._bundle(
                input=input,
                policy=cfg,
                created_at=current,
                context_bundle_id=context_bundle_id,
                recent_turn_refs=recent_turn_refs,
                active_task_refs=active_task_refs,
                artifact_refs=artifact_refs,
                memory_refs=memory_refs,
                raw_payload_refs=raw_payload_refs,
                summary_ref=summary.summary_ref if summary is not None else None,
                metadata=_bundle_metadata(
                    input=input,
                    feedback_correction_refs=feedback_correction_refs,
                    dropped_sections=dropped_sections,
                    estimated_tokens=0,
                    protected_sections=protected_sections,
                    safe_input_metadata=safe_input_metadata,
                    active_task_refs=active_task_refs,
                ),
                industry_context=safe_industry_context,
            )
            estimated = _estimate_tokens(_context_bundle_as_event(bundle), cfg)

        if estimated > cfg.budget_tokens:
            raise ContextAssemblyBudgetError(
                f"context requires {estimated} estimated tokens after trimming, budget is {cfg.budget_tokens}"
            )

        bundle = self._bundle(
            input=input,
            policy=cfg,
            created_at=current,
            context_bundle_id=context_bundle_id,
            recent_turn_refs=recent_turn_refs,
            active_task_refs=active_task_refs,
            artifact_refs=artifact_refs,
            memory_refs=memory_refs,
            raw_payload_refs=raw_payload_refs,
            summary_ref=summary.summary_ref if summary is not None else None,
            metadata=_bundle_metadata(
                input=input,
                feedback_correction_refs=feedback_correction_refs,
                dropped_sections=dropped_sections,
                estimated_tokens=estimated,
                protected_sections=protected_sections,
                safe_input_metadata=safe_input_metadata,
                active_task_refs=active_task_refs,
            ),
            industry_context=safe_industry_context,
        )
        return ContextAssemblyResult(
            bundle=bundle,
            estimated_tokens=estimated,
            dropped_sections=_json_clone(dropped_sections),
            protected_sections=protected_sections,
        )

    def _bundle(
        self,
        *,
        input: ContextAssemblyInput,
        policy: ContextAssemblyPolicy,
        created_at: str,
        context_bundle_id: str,
        recent_turn_refs: Sequence[str],
        active_task_refs: Sequence[str],
        artifact_refs: Sequence[str],
        memory_refs: Sequence[str],
        raw_payload_refs: Sequence[str],
        summary_ref: str | None,
        metadata: Mapping[str, Any],
        industry_context: Mapping[str, Any],
    ) -> ContextBundle:
        return ContextBundle(
            context_bundle_id=context_bundle_id,
            tenant_id=input.scope.tenant_id,
            workspace_id=input.scope.workspace_id,
            session_id=input.session_id,
            created_at=created_at,
            budget_tokens=policy.budget_tokens,
            run_id=input.run_id,
            turn_id=input.turn_id,
            recent_turn_refs=list(recent_turn_refs),
            summary_ref=summary_ref,
            active_task_refs=list(active_task_refs),
            artifact_refs=list(artifact_refs),
            memory_refs=list(memory_refs),
            interrupt_id=input.pending_interrupt.interrupt_id if input.pending_interrupt is not None else None,
            trim_strategy=policy.trim_strategy,
            raw_payload_refs=list(raw_payload_refs),
            industry_context=_safe_metadata(industry_context),
            metadata=_safe_metadata(metadata),
        )


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


def _active_task_refs(input: ContextAssemblyInput) -> list[str]:
    refs = list(input.active_task_refs)
    if input.active_task is not None and not refs:
        task_ref = input.active_task.metadata.get("state_ref")
        if task_ref is not None:
            refs.append(str(task_ref))
        else:
            refs.append(input.active_task.task_id)
    return refs


def _raw_payload_refs(input: ContextAssemblyInput) -> list[str]:
    refs: list[str] = []
    if input.current_turn_raw_payload_ref is not None:
        refs.append(input.current_turn_raw_payload_ref)
    refs.extend(input.raw_payload_refs)
    return list(dict.fromkeys(refs))


def _protected_sections(input: ContextAssemblyInput) -> tuple[str, ...]:
    sections = ["current_turn"]
    if input.pending_interrupt is not None:
        sections.append("pending_clarification")
    if input.output_constraints_ref is not None or input.output_policy_ref is not None:
        sections.append("output_policy")
    return tuple(sections)


def _bundle_metadata(
    *,
    input: ContextAssemblyInput,
    feedback_correction_refs: Sequence[str],
    dropped_sections: Mapping[str, Any],
    estimated_tokens: int,
    protected_sections: Sequence[str],
    safe_input_metadata: Mapping[str, Any],
    active_task_refs: Sequence[str],
) -> JsonObject:
    current_turn_text = input.current_turn_text or ""
    metadata: JsonObject = {
        **_safe_metadata(safe_input_metadata),
        "privacy": "no_raw_payload_or_legal_text_stored",
        "current_turn_ref": input.current_turn_ref,
        "current_turn_text_sha256_16": _sha16(current_turn_text),
        "current_turn_text_length": len(current_turn_text),
        "feedback_correction_refs": list(feedback_correction_refs),
        "dropped_sections": _json_clone(dropped_sections),
        "estimated_tokens": estimated_tokens,
        "protected_sections": list(protected_sections),
    }
    if input.pending_interrupt is not None:
        metadata["pending_clarification_ref"] = input.pending_interrupt.prompt_ref
        metadata["resume_state_ref"] = input.pending_interrupt.resume_state_ref
        metadata["pending_interrupt_status"] = input.pending_interrupt.status
    if input.output_constraints_ref is not None:
        metadata["output_constraints_ref"] = input.output_constraints_ref
    if input.output_policy_ref is not None:
        metadata["output_policy_ref"] = input.output_policy_ref
    if input.active_task is not None and active_task_refs:
        metadata["active_task_id"] = input.active_task.task_id
        metadata["active_task_status"] = input.active_task.status
        if input.active_task.run_id is not None:
            metadata["active_task_run_id"] = input.active_task.run_id
        metadata["active_task_refs"] = list(active_task_refs)
    if input.rolling_summary is not None:
        metadata["rolling_summary"] = {
            "summary_ref": input.rolling_summary.summary_ref,
            "task_intent_refs": list(input.rolling_summary.task_intent_refs),
            "user_constraint_refs": list(input.rolling_summary.user_constraint_refs),
            "unanswered_question_refs": list(input.rolling_summary.unanswered_question_refs),
            "artifact_refs": list(input.rolling_summary.artifact_refs),
            "outcome_refs": list(input.rolling_summary.outcome_refs),
            "text_sha256_16": input.rolling_summary.text_sha256_16,
            "text_length": input.rolling_summary.text_length,
        }
    return _safe_metadata(metadata)


def _protected_bundle_metadata(
    *,
    input: ContextAssemblyInput,
    dropped_sections: Mapping[str, Any],
    protected_sections: Sequence[str],
    safe_input_metadata: Mapping[str, Any],
) -> JsonObject:
    current_turn_text = input.current_turn_text or ""
    metadata: JsonObject = {
        **_safe_metadata(safe_input_metadata),
        "privacy": "no_raw_payload_or_legal_text_stored",
        "current_turn_ref": input.current_turn_ref,
        "current_turn_text_sha256_16": _sha16(current_turn_text),
        "current_turn_text_length": len(current_turn_text),
        "dropped_sections": _json_clone(dropped_sections),
        "protected_sections": list(protected_sections),
    }
    if input.pending_interrupt is not None:
        metadata["pending_clarification_ref"] = input.pending_interrupt.prompt_ref
        metadata["resume_state_ref"] = input.pending_interrupt.resume_state_ref
        metadata["pending_interrupt_status"] = input.pending_interrupt.status
    if input.output_constraints_ref is not None:
        metadata["output_constraints_ref"] = input.output_constraints_ref
    if input.output_policy_ref is not None:
        metadata["output_policy_ref"] = input.output_policy_ref
    return _safe_metadata(metadata)


def _estimate_tokens(event: Mapping[str, Any], policy: ContextAssemblyPolicy) -> int:
    chars_per_token = max(1, int(policy.chars_per_token))
    return math.ceil(_estimated_value_chars(event) / chars_per_token)


def _estimated_value_chars(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, bool):
        return 4 if value else 5
    if isinstance(value, int | float):
        return len(str(value))
    if isinstance(value, Mapping):
        return sum(_estimated_value_chars(nested) for nested in value.values())
    if isinstance(value, list | tuple):
        return sum(_estimated_value_chars(nested) for nested in value)
    return len(str(value))


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
