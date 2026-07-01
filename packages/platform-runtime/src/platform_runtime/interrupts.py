"""Backend-neutral interrupt lifecycle support."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Any

from platform_contract.enums import AgentResultStatus, AsyncTaskState, InterruptStatus
from platform_contract.events import JsonObject, RunInterrupt

from .session_resolver import SessionScope
from .store import ContractLogPrivacyError


class InterruptLifecycleAction(StrEnum):
    CREATED = "created"
    RESOLVED = "resolved"
    DUPLICATE_ANSWER_IGNORED = "duplicate_answer_ignored"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SCOPE_MISMATCH = "scope_mismatch"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class InterruptRecord:
    scope: SessionScope
    event: RunInterrupt

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "interrupt_id": self.event.interrupt_id,
            "run_id": self.event.run_id,
            "session_id": self.event.session_id,
            "status": _enum_value(self.event.status),
            "reason": self.event.reason,
            "created_at": self.event.created_at,
            "prompt_ref": self.event.prompt_ref,
            "resume_state_ref": self.event.resume_state_ref,
            "scope": self.scope.as_event(),
            "metadata": _safe_metadata(self.event.metadata),
            "privacy": "no_raw_prompt_or_answer_text_stored",
        }
        optional = {
            "expected_response_schema_ref": self.event.expected_response_schema_ref,
            "expires_at": self.event.expires_at,
            "resolved_at": self.event.resolved_at,
            "resolved_turn_id": self.event.resolved_turn_id,
        }
        event.update({key: value for key, value in optional.items() if value is not None})
        _reject_forbidden_payload_storage(event)
        return event


@dataclass(frozen=True, slots=True)
class InterruptLifecycleDecision:
    action: InterruptLifecycleAction
    interrupt: InterruptRecord | None
    decided_at: str
    reason: str
    duplicate: bool = False
    metadata: JsonObject = field(default_factory=dict)

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "event": "interrupt_lifecycle",
            "action": self.action.value,
            "decided_at": self.decided_at,
            "reason": self.reason,
            "duplicate": self.duplicate,
            "metadata": _safe_metadata(
                {
                    "async_task_state": AsyncTaskState.WAITING_FOR_USER.value,
                    "agent_result_status": AgentResultStatus.NEEDS_CLARIFICATION.value,
                    "privacy": "no_raw_prompt_or_answer_text_stored",
                    **self.metadata,
                }
            ),
            "privacy": "no_raw_prompt_or_answer_text_stored",
        }
        if self.interrupt is not None:
            event["interrupt"] = self.interrupt.as_event()
        _reject_forbidden_payload_storage(event)
        return event


class InMemoryInterruptStore:
    """Copy-safe scoped interrupt store for embedded hosts and tests."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime | str] | Any | None = None,
        id_factory: Callable[[str], str] | Any | None = None,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory
        self._records: dict[str, InterruptRecord] = {}
        self._pending_by_scope: dict[tuple[str, ...], str] = {}
        self._decisions: list[InterruptLifecycleDecision] = []

    def create_clarification(
        self,
        *,
        scope: SessionScope,
        run_id: str,
        session_id: str,
        prompt_ref: str,
        resume_state_ref: str,
        reason: str,
        expected_response_schema_ref: str | None = None,
        expires_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> InterruptRecord:
        now = _timestamp(_clock_now(self._clock))
        interrupt = RunInterrupt(
            interrupt_id=_new_id(self._id_factory, "interrupt"),
            run_id=run_id,
            session_id=session_id,
            status=InterruptStatus.WAITING_FOR_USER,
            reason=reason,
            created_at=now,
            prompt_ref=prompt_ref,
            resume_state_ref=resume_state_ref,
            expected_response_schema_ref=expected_response_schema_ref,
            expires_at=expires_at,
            metadata=_safe_metadata(
                {
                    "async_task_state": AsyncTaskState.WAITING_FOR_USER.value,
                    "agent_result_status": AgentResultStatus.NEEDS_CLARIFICATION.value,
                    "privacy": "no_raw_prompt_or_answer_text_stored",
                    **dict(metadata or {}),
                }
            ),
        )
        record = InterruptRecord(scope=scope, event=interrupt)
        self._records[interrupt.interrupt_id] = _copy_record(record)
        self._pending_by_scope[_scope_key(scope)] = interrupt.interrupt_id
        self._decisions.append(
            InterruptLifecycleDecision(
                action=InterruptLifecycleAction.CREATED,
                interrupt=_copy_record(record),
                decided_at=now,
                reason="clarification_interrupt_created",
            )
        )
        return _copy_record(record)

    def get(self, interrupt_id: str) -> InterruptRecord | None:
        record = self._records.get(interrupt_id)
        return _copy_record(record) if record is not None else None

    def records(self) -> tuple[InterruptRecord, ...]:
        return tuple(_copy_record(record) for record in self._records.values())

    def decisions(self) -> tuple[InterruptLifecycleDecision, ...]:
        return tuple(_copy_decision(decision) for decision in self._decisions)

    def pending_for_scope(self, scope: SessionScope) -> InterruptRecord | None:
        interrupt_id = self._pending_by_scope.get(_scope_key(scope))
        if interrupt_id is None:
            return None
        record = self._records.get(interrupt_id)
        if record is None:
            return None
        if _status_value(record.event.status) != InterruptStatus.WAITING_FOR_USER.value:
            return None
        return _copy_record(record)

    def resolve(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        turn_id: str,
        answer_text: str | None,
        idempotency_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | str | None = None,
    ) -> InterruptLifecycleDecision:
        current = _timestamp(now or _clock_now(self._clock))
        record = self._records.get(interrupt_id)
        if record is None:
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.NOT_FOUND,
                    interrupt=None,
                    decided_at=current,
                    reason="interrupt_not_found",
                )
            )
        if record.scope != scope:
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.SCOPE_MISMATCH,
                    interrupt=_copy_record(record),
                    decided_at=current,
                    reason="interrupt_scope_mismatch",
                )
            )

        status = _status_value(record.event.status)
        if status == InterruptStatus.RESOLVED.value:
            if _is_duplicate_resolution(record, turn_id=turn_id, idempotency_key=idempotency_key):
                return self._remember_decision(
                    InterruptLifecycleDecision(
                        action=InterruptLifecycleAction.DUPLICATE_ANSWER_IGNORED,
                        interrupt=_copy_record(record),
                        decided_at=current,
                        reason="duplicate_answer_ignored",
                        duplicate=True,
                    )
                )
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.DUPLICATE_ANSWER_IGNORED,
                    interrupt=_copy_record(record),
                    decided_at=current,
                    reason="already_resolved",
                    duplicate=True,
                )
            )
        if status == InterruptStatus.CANCELLED.value:
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.CANCELLED,
                    interrupt=_copy_record(record),
                    decided_at=current,
                    reason="interrupt_cancelled",
                )
            )
        if status == InterruptStatus.EXPIRED.value or _is_expired(record, current):
            expired = self._transition(record, status=InterruptStatus.EXPIRED, now=current, reason="interrupt_expired")
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.EXPIRED,
                    interrupt=expired,
                    decided_at=current,
                    reason="interrupt_expired",
                )
            )

        answer = str(answer_text or "")
        resolution_metadata = {
            "resolved_turn_id": turn_id,
            "resolved_at": current,
            "answer_text_sha256_16": _sha16(answer),
            "answer_text_length": len(answer),
            "resolved_idempotency_key": idempotency_key,
            **dict(metadata or {}),
        }
        resolved = self._transition(
            record,
            status=InterruptStatus.RESOLVED,
            now=current,
            reason=record.event.reason,
            resolved_turn_id=turn_id,
            metadata=resolution_metadata,
        )
        return self._remember_decision(
            InterruptLifecycleDecision(
                action=InterruptLifecycleAction.RESOLVED,
                interrupt=resolved,
                decided_at=current,
                reason="interrupt_resolved",
                metadata=resolution_metadata,
            )
        )

    def expire_due(self, *, now: datetime | str | None = None) -> tuple[InterruptLifecycleDecision, ...]:
        current = _timestamp(now or _clock_now(self._clock))
        decisions: list[InterruptLifecycleDecision] = []
        for record in tuple(self._records.values()):
            if _status_value(record.event.status) == InterruptStatus.WAITING_FOR_USER.value and _is_expired(record, current):
                expired = self._transition(record, status=InterruptStatus.EXPIRED, now=current, reason="interrupt_expired")
                decisions.append(
                    self._remember_decision(
                        InterruptLifecycleDecision(
                            action=InterruptLifecycleAction.EXPIRED,
                            interrupt=expired,
                            decided_at=current,
                            reason="interrupt_expired",
                        )
                    )
                )
        return tuple(decisions)

    def cancel(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        reason: str = "interrupt_cancelled",
        now: datetime | str | None = None,
    ) -> InterruptLifecycleDecision:
        current = _timestamp(now or _clock_now(self._clock))
        record = self._records.get(interrupt_id)
        if record is None:
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.NOT_FOUND,
                    interrupt=None,
                    decided_at=current,
                    reason="interrupt_not_found",
                )
            )
        if record.scope != scope:
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=InterruptLifecycleAction.SCOPE_MISMATCH,
                    interrupt=_copy_record(record),
                    decided_at=current,
                    reason="interrupt_scope_mismatch",
                )
            )
        if _status_value(record.event.status) != InterruptStatus.WAITING_FOR_USER.value:
            action = InterruptLifecycleAction(_status_value(record.event.status))
            return self._remember_decision(
                InterruptLifecycleDecision(
                    action=action,
                    interrupt=_copy_record(record),
                    decided_at=current,
                    reason=f"interrupt_{action.value}",
                )
            )
        cancelled = self._transition(record, status=InterruptStatus.CANCELLED, now=current, reason=reason)
        return self._remember_decision(
            InterruptLifecycleDecision(
                action=InterruptLifecycleAction.CANCELLED,
                interrupt=cancelled,
                decided_at=current,
                reason=reason,
            )
        )

    def _transition(
        self,
        record: InterruptRecord,
        *,
        status: InterruptStatus,
        now: str,
        reason: str,
        resolved_turn_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> InterruptRecord:
        combined_metadata = _safe_metadata({**record.event.metadata, **dict(metadata or {})})
        updated = InterruptRecord(
            scope=record.scope,
            event=RunInterrupt(
                interrupt_id=record.event.interrupt_id,
                run_id=record.event.run_id,
                session_id=record.event.session_id,
                status=status,
                reason=reason,
                created_at=record.event.created_at,
                prompt_ref=record.event.prompt_ref,
                resume_state_ref=record.event.resume_state_ref,
                expected_response_schema_ref=record.event.expected_response_schema_ref,
                expires_at=record.event.expires_at,
                resolved_at=now if status in {InterruptStatus.RESOLVED, InterruptStatus.EXPIRED, InterruptStatus.CANCELLED} else None,
                resolved_turn_id=resolved_turn_id,
                metadata=combined_metadata,
            ),
        )
        self._records[record.event.interrupt_id] = _copy_record(updated)
        if status != InterruptStatus.WAITING_FOR_USER:
            self._pending_by_scope.pop(_scope_key(record.scope), None)
        return _copy_record(updated)

    def _remember_decision(self, decision: InterruptLifecycleDecision) -> InterruptLifecycleDecision:
        stored = _copy_decision(decision)
        self._decisions.append(stored)
        return _copy_decision(stored)


def _copy_record(record: InterruptRecord) -> InterruptRecord:
    return InterruptRecord(
        scope=record.scope,
        event=RunInterrupt(
            interrupt_id=record.event.interrupt_id,
            run_id=record.event.run_id,
            session_id=record.event.session_id,
            status=record.event.status,
            reason=record.event.reason,
            created_at=record.event.created_at,
            prompt_ref=record.event.prompt_ref,
            resume_state_ref=record.event.resume_state_ref,
            expected_response_schema_ref=record.event.expected_response_schema_ref,
            expires_at=record.event.expires_at,
            resolved_at=record.event.resolved_at,
            resolved_turn_id=record.event.resolved_turn_id,
            metadata=_safe_metadata(record.event.metadata),
        ),
    )


def _copy_decision(decision: InterruptLifecycleDecision) -> InterruptLifecycleDecision:
    return InterruptLifecycleDecision(
        action=decision.action,
        interrupt=_copy_record(decision.interrupt) if decision.interrupt is not None else None,
        decided_at=decision.decided_at,
        reason=decision.reason,
        duplicate=decision.duplicate,
        metadata=_safe_metadata(decision.metadata),
    )


def _is_duplicate_resolution(
    record: InterruptRecord,
    *,
    turn_id: str,
    idempotency_key: str | None,
) -> bool:
    metadata = record.event.metadata
    return metadata.get("resolved_turn_id") == turn_id or (
        idempotency_key is not None and metadata.get("resolved_idempotency_key") == idempotency_key
    )


def _is_expired(record: InterruptRecord, now: str) -> bool:
    if record.event.expires_at is None:
        return False
    return _coerce_datetime(record.event.expires_at) <= _coerce_datetime(now)


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


def _new_id(id_factory: Callable[[str], str] | Any | None, prefix: str) -> str:
    if id_factory is None:
        return f"{prefix}-{_sha16(prefix + ':' + datetime.now(timezone.utc).isoformat())}"
    if callable(id_factory):
        return str(id_factory(prefix))
    new_id = getattr(id_factory, "new_id", None)
    if callable(new_id):
        return str(new_id(prefix))
    raise TypeError("id_factory must be callable or provide new_id(prefix)")


def _clock_now(clock: Callable[[], datetime | str] | Any | None) -> datetime | str:
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


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _status_value(status: InterruptStatus | str) -> str:
    if isinstance(status, InterruptStatus):
        return status.value
    return str(status)


def _enum_value(value: object) -> str:
    return getattr(value, "value", str(value))


def _safe_metadata(value: Mapping[str, Any]) -> JsonObject:
    _reject_forbidden_payload_storage(value)
    return _json_clone(value)


def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _reject_forbidden_payload_storage(event: Mapping[str, Any]) -> None:
    for path, key in _walk_keys(event):
        if key == "raw_payload":
            raise ContractLogPrivacyError(f"interrupt event contains forbidden raw_payload at {path}")
        if key in _FORBIDDEN_FULL_TEXT_KEYS:
            raise ContractLogPrivacyError(f"interrupt event contains forbidden full-text payload field at {path}")


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            yield child_path, key_text
            yield from _walk_keys(nested, child_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_keys(nested, f"{path}[{index}]")


_FORBIDDEN_FULL_TEXT_KEYS = {
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
}


__all__ = [
    "InMemoryInterruptStore",
    "InterruptLifecycleAction",
    "InterruptLifecycleDecision",
    "InterruptRecord",
]
