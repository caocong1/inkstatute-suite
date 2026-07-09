"""QQBot session resolver and interrupt orchestration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
import json
from typing import Any

from platform_contract.events import JsonObject
from platform_runtime import (
    InMemoryInterruptStore,
    Memory,
    MemoryOrchestrator,
    Run,
    RunRequest,
    RunRuntime,
    SessionResolutionAction,
    SessionResolutionDecision,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
)
from platform_runtime.interrupts import InterruptLifecycleAction, InterruptRecord
from platform_runtime.session_resolver import (
    ActiveTaskSnapshot,
    PendingInterruptSnapshot,
    resolve_session_turn,
)


class QQBotSessionRuntimeAction(StrEnum):
    RESUME_INTERRUPT = "resume_interrupt"
    DUPLICATE_ANSWER_IGNORED = "duplicate_answer_ignored"
    INTERRUPT_EXPIRED = "interrupt_expired"
    INTERRUPT_CANCELLED = "interrupt_cancelled"
    ACTIVE_TASK_FOLLOW_UP = "active_task_follow_up"
    CONTINUE_SESSION = "continue_session"
    START_NEW_SESSION = "start_new_session"
    SKIPPED_NON_MESSAGE = "skipped_non_message"


@dataclass(frozen=True, slots=True)
class QQBotSessionRuntimeOutcome:
    action: QQBotSessionRuntimeAction
    decision: SessionResolutionDecision
    run_id: str | None = None
    evidence: JsonObject = field(default_factory=dict)

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "event": "qqbot_session_runtime",
            "action": self.action.value,
            "decision": self.decision.as_event(),
            "evidence": _safe_json(
                {
                    "privacy": "no_raw_payload_or_answer_text_stored",
                    **self.evidence,
                }
            ),
            "privacy": "no_raw_payload_or_answer_text_stored",
        }
        if self.run_id is not None:
            event["run_id"] = self.run_id
        return _safe_json(event)


class QQBotSessionRuntime:
    """Pure orchestration seam for normalized QQBot turns.

    Composes platform-runtime session resolution and interrupt resume. Does not
    parse callbacks, perform network IO, or couple to other channel services.
    """

    def __init__(
        self,
        *,
        runtime: RunRuntime,
        interrupt_store: InMemoryInterruptStore | None = None,
        policy: SessionResolutionPolicy | None = None,
        memory_orchestrator: MemoryOrchestrator | None = None,
        memory: Memory | None = None,
        memory_policy: Any | None = None,
        clock: Any | None = None,
        id_factory: Any | None = None,
    ) -> None:
        self.runtime = runtime
        self.interrupt_store = interrupt_store
        self.policy = policy or SessionResolutionPolicy()
        self.memory_orchestrator = memory_orchestrator
        self.memory = memory
        self.memory_policy = memory_policy
        self.clock = clock
        self.id_factory = id_factory
        self._outcome_by_idempotency_key: dict[str, QQBotSessionRuntimeOutcome] = {}

    async def handle_turn(
        self,
        *,
        turn: Any,
        scope: SessionScope,
        run_request: RunRequest,
        recent_session: SessionSnapshot | None = None,
        active_task: ActiveTaskSnapshot | Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        now: datetime | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QQBotSessionRuntimeOutcome:
        _validate_turn_scope(turn=turn, scope=scope, run_request=run_request)
        current = now or _clock_now(self.clock)
        raw_payload_ref = _raw_payload_ref(turn)
        turn_text = str(getattr(turn, "content", "") or "")
        turn_id = str(getattr(turn, "turn_id", "") or "unknown-turn")

        if idempotency_key and idempotency_key in self._outcome_by_idempotency_key:
            prior = self._outcome_by_idempotency_key[idempotency_key]
            return QQBotSessionRuntimeOutcome(
                action=QQBotSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED,
                decision=prior.decision,
                run_id=prior.run_id,
                evidence=_duplicate_evidence(
                    prior.decision,
                    interrupt_id=prior.decision.interrupt_id,
                    idempotency_key=idempotency_key,
                    backend_submit_count=1,
                ),
            )

        pending_record = _pending_record_for_scope(self.interrupt_store, scope)
        pending_snapshot = _pending_snapshot(pending_record)
        active_snapshot = _active_snapshot(active_task, scope)

        duplicate_record = _resolved_duplicate_record_for_scope(
            self.interrupt_store,
            scope,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
        )
        if duplicate_record is not None:
            decision = _resolve_decision(
                scope=scope,
                text=turn_text,
                raw_payload_ref=raw_payload_ref,
                recent_session=recent_session,
                pending_interrupt=None,
                active_task=None,
                policy=self.policy,
                now=current,
                id_factory=self.id_factory,
                metadata=metadata,
            )
            return QQBotSessionRuntimeOutcome(
                action=QQBotSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED,
                decision=decision,
                run_id=str(duplicate_record.event.metadata["resumed_backend_run_id"]),
                evidence=_duplicate_evidence(
                    decision,
                    interrupt_id=duplicate_record.event.interrupt_id,
                    idempotency_key=idempotency_key,
                    backend_submit_count=1,
                ),
            )

        if pending_record is not None and _record_is_expired(pending_record, current):
            expired = self.interrupt_store.resolve(
                interrupt_id=pending_record.event.interrupt_id,
                scope=scope,
                turn_id=turn_id,
                answer_text=turn_text,
                idempotency_key=idempotency_key,
                now=current,
            )
            decision = _resolve_decision(
                scope=scope,
                text=turn_text,
                raw_payload_ref=raw_payload_ref,
                recent_session=recent_session,
                pending_interrupt=pending_snapshot,
                active_task=None,
                policy=self.policy,
                now=current,
                id_factory=self.id_factory,
                metadata=metadata,
            )
            return QQBotSessionRuntimeOutcome(
                action=QQBotSessionRuntimeAction.INTERRUPT_EXPIRED,
                decision=decision,
                evidence=_base_evidence(decision)
                | {
                    "interrupt_lifecycle_action": expired.action.value,
                    "interrupt_status": "expired",
                    "resume_attempted": False,
                },
            )

        decision = _resolve_decision(
            scope=scope,
            text=turn_text,
            raw_payload_ref=raw_payload_ref,
            recent_session=recent_session,
            pending_interrupt=pending_snapshot,
            active_task=active_snapshot,
            policy=self.policy,
            now=current,
            id_factory=self.id_factory,
            metadata=metadata,
        )

        if decision.action == SessionResolutionAction.RESUME_INTERRUPT:
            run = await self.runtime.resume_interrupt(
                interrupt_id=str(decision.interrupt_id),
                scope=scope,
                req=run_request,
                idempotency_key=idempotency_key,
            )
            outcome = QQBotSessionRuntimeOutcome(
                action=QQBotSessionRuntimeAction.RESUME_INTERRUPT,
                decision=decision,
                run_id=_run_id(run),
                evidence=_base_evidence(decision)
                | {
                    "resume_attempted": True,
                    "runtime_resume_called": True,
                    "resumed_run_id": _run_id(run),
                },
            )
            if idempotency_key:
                self._outcome_by_idempotency_key[idempotency_key] = outcome
            return outcome

        if decision.action == SessionResolutionAction.ACTIVE_TASK_FOLLOW_UP:
            return QQBotSessionRuntimeOutcome(
                action=QQBotSessionRuntimeAction.ACTIVE_TASK_FOLLOW_UP,
                decision=decision,
                evidence=_base_evidence(decision)
                | {
                    "resume_attempted": False,
                    "active_task_id": decision.task_id,
                    "active_task_status": decision.active_task_status,
                },
            )

        action = (
            QQBotSessionRuntimeAction.CONTINUE_SESSION
            if decision.action == SessionResolutionAction.CONTINUE_SESSION
            else QQBotSessionRuntimeAction.START_NEW_SESSION
        )
        decision_request = _run_request_for_decision(run_request, decision=decision)
        run = await self.runtime.create_run(decision_request)
        outcome = QQBotSessionRuntimeOutcome(
            action=action,
            decision=decision,
            run_id=_run_id(run),
            evidence=_base_evidence(decision)
            | {
                "resume_attempted": False,
                "runtime_create_called": True,
                "created_run_id": _run_id(run),
            },
        )
        if idempotency_key:
            self._outcome_by_idempotency_key[idempotency_key] = outcome
        return outcome


def _validate_turn_scope(*, turn: Any, scope: SessionScope, run_request: RunRequest) -> None:
    mismatches: list[str] = []

    _require_match(mismatches, "turn.user_id", getattr(turn, "user_id", None), scope.user_id)
    _require_match(mismatches, "turn.conversation_id", getattr(turn, "conversation_id", None), scope.conversation_id)
    _require_match(mismatches, "turn.channel", _channel_value(getattr(turn, "channel", None)), scope.channel_id)
    _require_thread_match(mismatches, "turn.metadata.thread_id", getattr(turn, "metadata", None), scope.thread_id)

    req_turn = getattr(run_request, "turn", None)
    _require_match(mismatches, "run_request.turn_id", getattr(req_turn, "turn_id", None), getattr(turn, "turn_id", None))
    _require_match(mismatches, "run_request.turn.user_id", getattr(req_turn, "user_id", None), scope.user_id)
    _require_match(
        mismatches,
        "run_request.turn.conversation_id",
        getattr(req_turn, "conversation_id", None),
        scope.conversation_id,
    )
    _require_match(mismatches, "run_request.turn.channel", _channel_value(getattr(req_turn, "channel", None)), scope.channel_id)
    _require_thread_match(mismatches, "run_request.turn.metadata.thread_id", getattr(req_turn, "metadata", None), scope.thread_id)
    _require_match(mismatches, "run_request.tenant_id", run_request.tenant_id, scope.tenant_id)
    _require_match(mismatches, "run_request.workspace_id", run_request.workspace_id, scope.workspace_id)
    _require_match(mismatches, "run_request.bot_instance_id", run_request.bot_instance_id, scope.bot_instance_id)

    if mismatches:
        raise ValueError("turn/run_request scope mismatch: " + "; ".join(mismatches))


def _require_match(mismatches: list[str], field: str, actual: Any, expected: Any) -> None:
    if expected is None:
        return
    if actual is None or str(actual) != str(expected):
        mismatches.append(f"{field}={actual!r} expected {expected!r}")


def _require_thread_match(
    mismatches: list[str],
    field: str,
    metadata: Any,
    expected_thread_id: str | None,
) -> None:
    if expected_thread_id is None:
        return
    actual = metadata.get("thread_id") if isinstance(metadata, Mapping) else None
    if actual is None or str(actual) != str(expected_thread_id):
        mismatches.append(f"{field}={actual!r} expected {expected_thread_id!r}")


def _channel_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _resolve_decision(
    *,
    scope: SessionScope,
    text: str,
    raw_payload_ref: str | None,
    recent_session: SessionSnapshot | None,
    pending_interrupt: PendingInterruptSnapshot | None,
    active_task: ActiveTaskSnapshot | None,
    policy: SessionResolutionPolicy,
    now: datetime | str,
    id_factory: Any | None,
    metadata: Mapping[str, Any] | None,
) -> SessionResolutionDecision:
    return resolve_session_turn(
        scope=scope,
        text=text,
        raw_payload_ref=raw_payload_ref,
        recent_session=recent_session,
        pending_interrupt=pending_interrupt,
        active_task=active_task,
        policy=policy,
        now=now,
        id_factory=id_factory,
        metadata={
            "source": "qqbot_session_runtime",
            "qqbot_normalization": "already_normalized",
            "session_command_required": False,
            "ordinary_user_command_surface": "none",
            "scope_isolation": "tenant_workspace_channel_user_bot_session_thread",
            **dict(metadata or {}),
        },
    )


def _base_evidence(decision: SessionResolutionDecision) -> JsonObject:
    return {
        "decision_id": decision.decision_id,
        "decision_action": decision.action.value,
        "decision_reason": decision.reason,
        "session_id": decision.session_id,
        "raw_payload_ref": decision.raw_payload_ref,
        "text_sha256_16": decision.text_sha256_16,
        "text_length": decision.text_length,
        "session_command_required": False,
        "ordinary_user_command_surface": "none",
        "scope_isolation": "tenant_workspace_channel_user_bot_session_thread",
        "privacy": "no_raw_payload_or_answer_text_stored",
    }


def _duplicate_evidence(
    decision: SessionResolutionDecision,
    *,
    interrupt_id: str | None,
    idempotency_key: str | None,
    backend_submit_count: int,
) -> JsonObject:
    return _base_evidence(decision) | {
        "duplicate": True,
        "interrupt_id": interrupt_id,
        "idempotency_key": idempotency_key,
        "resume_attempted": False,
        "runtime_resume_called": False,
        "runtime_create_called": False,
        "duplicate_backend_submit_count": backend_submit_count,
    }


def _run_request_for_decision(run_request: RunRequest, *, decision: SessionResolutionDecision) -> RunRequest:
    return replace(
        run_request,
        session_id=decision.session_id,
        metadata=_run_metadata_for_decision(run_request, decision=decision),
    )


def _run_metadata_for_decision(run_request: RunRequest, *, decision: SessionResolutionDecision) -> JsonObject:
    existing = dict(run_request.metadata)
    turn = run_request.turn
    raw_payload_ref = decision.raw_payload_ref or _raw_payload_ref(turn)
    raw_payload_refs = _append_unique(_metadata_sequence(existing.get("raw_payload_refs")), raw_payload_ref)
    current_turn_ref = _string(existing.get("current_turn_ref")) or raw_payload_ref or f"turn://{turn.turn_id}"

    return _safe_json(
        {
            **existing,
            "source": _string(existing.get("source")) or "qqbot_session_runtime",
            "qqbot_normalization": "already_normalized",
            "session_command_required": False,
            "ordinary_user_command_surface": "none",
            "scope_isolation": "tenant_workspace_channel_user_bot_session_thread",
            "session_resolution_decision_id": decision.decision_id,
            "session_resolution_action": decision.action.value,
            "session_resolution_reason": decision.reason,
            "session_id": decision.session_id,
            "current_turn_ref": current_turn_ref,
            "raw_payload_ref": raw_payload_ref,
            "raw_payload_refs": raw_payload_refs,
            "privacy": existing.get("privacy") or "no_raw_payload_or_answer_text_stored",
        }
    )


def _metadata_sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _string(value)
        return (text,) if text is not None else ()
    if isinstance(value, list | tuple):
        return tuple(text for item in value if (text := _string(item)) is not None)
    text = _string(value)
    return (text,) if text is not None else ()


def _append_unique(values: tuple[str, ...], value: str | None) -> list[str]:
    result = list(values)
    if value is not None and value not in result:
        result.append(value)
    return result


def _pending_record_for_scope(
    store: InMemoryInterruptStore | None,
    scope: SessionScope,
) -> InterruptRecord | None:
    if store is None:
        return None
    return store.pending_for_scope(scope)


def _resolved_duplicate_record_for_scope(
    store: InMemoryInterruptStore | None,
    scope: SessionScope,
    *,
    turn_id: str,
    idempotency_key: str | None,
) -> InterruptRecord | None:
    if store is None:
        return None
    for record in reversed(store.records()):
        if record.scope != scope:
            continue
        if str(record.event.status) != InterruptLifecycleAction.RESOLVED.value:
            continue
        metadata = record.event.metadata
        if metadata.get("backend_resume_submitted") is not True or not metadata.get("resumed_backend_run_id"):
            continue
        if metadata.get("resolved_turn_id") == turn_id:
            return record
        if idempotency_key is not None and metadata.get("resolved_idempotency_key") == idempotency_key:
            return record
    return None


def _pending_snapshot(record: InterruptRecord | None) -> PendingInterruptSnapshot | None:
    if record is None:
        return None
    return PendingInterruptSnapshot(
        scope=record.scope,
        interrupt_id=record.event.interrupt_id,
        run_id=record.event.run_id,
        session_id=record.event.session_id,
        status=str(record.event.status),
        created_at=record.event.created_at,
        expires_at=record.event.expires_at,
        prompt_ref=record.event.prompt_ref,
        resume_state_ref=record.event.resume_state_ref,
        metadata=record.event.metadata,
    )


def _active_snapshot(
    active_task: ActiveTaskSnapshot | Mapping[str, Any] | None,
    scope: SessionScope,
) -> ActiveTaskSnapshot | None:
    if active_task is None:
        return None
    if isinstance(active_task, ActiveTaskSnapshot):
        return active_task
    return ActiveTaskSnapshot(
        scope=scope,
        task_id=str(active_task.get("task_id") or "unknown-task"),
        status=str(active_task.get("status") or active_task.get("async_task_state") or active_task.get("stage") or "running"),
        updated_at=str(active_task.get("updated_at") or _timestamp(_clock_now(None))),
        run_id=_string(active_task.get("run_id")),
        session_id=_string(active_task.get("session_id")),
        metadata={key: value for key, value in active_task.items() if key not in {"task_id", "status"}},
    )


def _record_is_expired(record: InterruptRecord, now: datetime | str) -> bool:
    if record.event.expires_at is None:
        return False
    return _coerce_datetime(record.event.expires_at) <= _coerce_datetime(now)


def _raw_payload_ref(turn: Any) -> str | None:
    metadata = getattr(turn, "metadata", {})
    if isinstance(metadata, Mapping):
        return _string(metadata.get("raw_payload_ref"))
    return None


def _run_id(run: Run | Any) -> str | None:
    return _string(getattr(run, "run_id", None))


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _clock_now(clock: Any | None) -> datetime | str:
    if clock is None:
        return datetime.now(timezone.utc)
    if callable(clock):
        return clock()
    now = getattr(clock, "now", None)
    if callable(now):
        return now()
    raise TypeError("clock must be callable or provide now()")


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime | str) -> str:
    return _coerce_datetime(value).isoformat().replace("+00:00", "Z")


def _safe_json(value: Mapping[str, Any]) -> JsonObject:
    _reject_unsafe_keys(value)
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _reject_unsafe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if key_text == "raw_payload" or key_text in _FORBIDDEN_FULL_TEXT_KEYS:
                raise ValueError(f"unsafe QQBot session runtime evidence key at {path}.{key_text}")
            _reject_unsafe_keys(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_unsafe_keys(nested, f"{path}[{index}]")


_FORBIDDEN_FULL_TEXT_KEYS = {
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
}


__all__ = [
    "QQBotSessionRuntime",
    "QQBotSessionRuntimeAction",
    "QQBotSessionRuntimeOutcome",
]
