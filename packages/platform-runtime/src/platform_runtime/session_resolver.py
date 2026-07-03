"""Backend-neutral, privacy-safe session resolution support."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
import re
from typing import Any

from platform_contract.events import JsonObject

from .ports import ContractLogStore
from .privacy_keys import ALL_FORBIDDEN_KEYS
from .store import ContractLogPrivacyError


class SessionResolutionAction(StrEnum):
    RESUME_INTERRUPT = "resume_interrupt"
    ACTIVE_TASK_FOLLOW_UP = "active_task_follow_up"
    CONTINUE_SESSION = "continue_session"
    START_NEW_SESSION = "start_new_session"


@dataclass(frozen=True, slots=True)
class SessionScope:
    tenant_id: str
    workspace_id: str
    channel_id: str
    user_id: str
    bot_instance_id: str
    conversation_id: str
    thread_id: str | None = None

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "bot_instance_id": self.bot_instance_id,
            "conversation_id": self.conversation_id,
        }
        if self.thread_id is not None:
            event["thread_id"] = self.thread_id
        return event


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    scope: SessionScope
    session_id: str
    status: str
    updated_at: str
    created_at: str | None = None
    last_run_id: str | None = None
    last_run_status: str | None = None
    thread_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PendingInterruptSnapshot:
    scope: SessionScope
    interrupt_id: str
    run_id: str
    session_id: str
    status: str
    created_at: str
    expires_at: str | None = None
    prompt_ref: str | None = None
    resume_state_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActiveTaskSnapshot:
    scope: SessionScope
    task_id: str
    status: str
    updated_at: str
    run_id: str | None = None
    session_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SessionResolutionPolicy:
    default_idle_window_seconds: float = 1800.0
    new_task_patterns: tuple[str, ...] = (
        r"(^|\s)/(new|start|restart)\b",
        r"(新任务|另一个任务|另外.*任务|重新开始|开启新会话)",
        r"(new task|separate task|start over|new session)",
    )
    terminal_session_statuses: frozenset[str] = frozenset(
        {"closed", "completed", "cancelled", "canceled", "failed", "expired", "archived", "terminal"}
    )
    terminal_run_statuses: frozenset[str] = frozenset(
        {"succeeded", "failed", "cancelled", "canceled", "expired", "completed", "terminal"}
    )
    terminal_task_statuses: frozenset[str] = frozenset(
        {"succeeded", "failed", "cancelled", "canceled", "expired", "completed", "timeout", "terminal"}
    )
    pending_interrupt_statuses: frozenset[str] = frozenset(
        {"waiting_for_user", "pending", "open", "unresolved", "needs_clarification"}
    )


@dataclass(frozen=True, slots=True)
class SessionResolutionDecision:
    decision_id: str
    action: SessionResolutionAction
    reason: str
    scope: SessionScope
    session_id: str
    decided_at: str
    text_sha256_16: str
    text_length: int
    raw_payload_ref: str | None = None
    run_id: str | None = None
    interrupt_id: str | None = None
    task_id: str | None = None
    prior_session_status: str | None = None
    prior_run_status: str | None = None
    active_task_status: str | None = None
    interrupt_status: str | None = None
    metadata: JsonObject = field(default_factory=dict)

    def as_event(self) -> JsonObject:
        event: JsonObject = {
            "event": "session_resolution",
            "decision_id": self.decision_id,
            "action": self.action.value,
            "reason": self.reason,
            "session_id": self.session_id,
            "decided_at": self.decided_at,
            "text_sha256_16": self.text_sha256_16,
            "text_length": self.text_length,
            "raw_payload_ref": self.raw_payload_ref,
            "scope": self.scope.as_event(),
            "metadata": _safe_metadata(
                {
                    "privacy": "no_raw_payload_or_legal_text_stored",
                    **self.metadata,
                }
            ),
            "privacy": "no_raw_payload_or_legal_text_stored",
        }
        optional = {
            "run_id": self.run_id,
            "interrupt_id": self.interrupt_id,
            "task_id": self.task_id,
            "prior_session_status": self.prior_session_status,
            "prior_run_status": self.prior_run_status,
            "active_task_status": self.active_task_status,
            "interrupt_status": self.interrupt_status,
        }
        event.update({key: value for key, value in optional.items() if value is not None})
        _reject_forbidden_payload_storage(event)
        return event


class InMemorySessionResolutionStore:
    """Copy-safe scoped support store for embedded hosts and tests."""

    def __init__(self, *, clock: Any | None = None) -> None:
        self._clock = clock
        self._sessions: dict[tuple[str, ...], SessionSnapshot] = {}
        self._pending_interrupts: dict[tuple[str, ...], PendingInterruptSnapshot] = {}
        self._active_tasks: dict[tuple[str, ...], ActiveTaskSnapshot] = {}
        self._decision_events: list[JsonObject] = []

    def upsert_session(self, snapshot: SessionSnapshot) -> None:
        self._sessions[_scope_key(snapshot.scope)] = _copy_session(snapshot)

    def get_session(self, scope: SessionScope) -> SessionSnapshot | None:
        snapshot = self._sessions.get(_scope_key(scope))
        return _copy_session(snapshot) if snapshot is not None else None

    def upsert_pending_interrupt(self, snapshot: PendingInterruptSnapshot) -> None:
        self._pending_interrupts[_scope_key(snapshot.scope)] = _copy_interrupt(snapshot)

    def get_pending_interrupt(self, scope: SessionScope) -> PendingInterruptSnapshot | None:
        snapshot = self._pending_interrupts.get(_scope_key(scope))
        return _copy_interrupt(snapshot) if snapshot is not None else None

    def upsert_active_task(self, snapshot: ActiveTaskSnapshot) -> None:
        self._active_tasks[_scope_key(snapshot.scope)] = _copy_active_task(snapshot)

    def get_active_task(self, scope: SessionScope) -> ActiveTaskSnapshot | None:
        snapshot = self._active_tasks.get(_scope_key(scope))
        return _copy_active_task(snapshot) if snapshot is not None else None

    def record_decision(
        self,
        decision: SessionResolutionDecision,
        *,
        contract_log_store: ContractLogStore | None = None,
    ) -> JsonObject:
        event = decision.as_event()
        if contract_log_store is not None:
            contract_log_store.append("session_resolution", event)
        stored = _json_clone(event)
        self._decision_events.append(stored)
        return _json_clone(stored)

    def decision_events(self) -> tuple[JsonObject, ...]:
        return tuple(_json_clone(event) for event in self._decision_events)

    def resolve(
        self,
        *,
        scope: SessionScope,
        text: str | None = None,
        raw_payload_ref: str | None = None,
        policy: SessionResolutionPolicy | None = None,
        now: datetime | str | None = None,
        id_factory: Callable[[str], str] | Any | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SessionResolutionDecision:
        return resolve_session_turn(
            scope=scope,
            text=text,
            raw_payload_ref=raw_payload_ref,
            recent_session=self.get_session(scope),
            pending_interrupt=self.get_pending_interrupt(scope),
            active_task=self.get_active_task(scope),
            policy=policy,
            now=now or _clock_now(self._clock),
            id_factory=id_factory,
            metadata=metadata,
        )


def resolve_session_turn(
    *,
    scope: SessionScope,
    text: str | None = None,
    raw_payload_ref: str | None = None,
    recent_session: SessionSnapshot | None = None,
    pending_interrupt: PendingInterruptSnapshot | None = None,
    active_task: ActiveTaskSnapshot | None = None,
    policy: SessionResolutionPolicy | None = None,
    now: datetime | str | None = None,
    id_factory: Callable[[str], str] | Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SessionResolutionDecision:
    cfg = policy or SessionResolutionPolicy()
    current = _coerce_datetime(now or datetime.now(timezone.utc))
    content = str(text or "")
    text_sha = _sha16(content)
    safe_metadata = _safe_metadata(metadata or {})

    scoped_interrupt = pending_interrupt if pending_interrupt and pending_interrupt.scope == scope else None
    scoped_task = active_task if active_task and active_task.scope == scope else None
    scoped_session = recent_session if recent_session and recent_session.scope == scope else None

    if scoped_interrupt and _interrupt_is_pending(scoped_interrupt, cfg, current):
        return _decision(
            action=SessionResolutionAction.RESUME_INTERRUPT,
            reason="pending_interrupt_precedence",
            scope=scope,
            session_id=scoped_interrupt.session_id,
            decided_at=_timestamp(current),
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            run_id=scoped_interrupt.run_id,
            interrupt_id=scoped_interrupt.interrupt_id,
            interrupt_status=scoped_interrupt.status,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if scoped_task and _status_key(scoped_task.status) not in cfg.terminal_task_statuses:
        return _decision(
            action=SessionResolutionAction.ACTIVE_TASK_FOLLOW_UP,
            reason="active_task_precedence",
            scope=scope,
            session_id=scoped_task.session_id or _new_id(id_factory, "session"),
            decided_at=_timestamp(current),
            text_sha256_16=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            run_id=scoped_task.run_id,
            task_id=scoped_task.task_id,
            active_task_status=scoped_task.status,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if _is_new_task_signal(content, cfg):
        return _start_new_decision(
            scope=scope,
            reason="new_task_signal",
            current=current,
            text_sha=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            session=scoped_session,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if scoped_session is None:
        return _start_new_decision(
            scope=scope,
            reason="no_recent_session",
            current=current,
            text_sha=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            session=None,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if _status_key(scoped_session.status) in cfg.terminal_session_statuses:
        return _start_new_decision(
            scope=scope,
            reason="terminal_session_status",
            current=current,
            text_sha=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            session=scoped_session,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if scoped_session.last_run_status and _status_key(scoped_session.last_run_status) in cfg.terminal_run_statuses:
        return _start_new_decision(
            scope=scope,
            reason="terminal_prior_run_status",
            current=current,
            text_sha=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            session=scoped_session,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    if _is_stale(scoped_session.updated_at, current, cfg.default_idle_window_seconds):
        return _start_new_decision(
            scope=scope,
            reason="session_idle_window_expired",
            current=current,
            text_sha=text_sha,
            text_length=len(content),
            raw_payload_ref=raw_payload_ref,
            session=scoped_session,
            id_factory=id_factory,
            metadata=safe_metadata,
        )

    return _decision(
        action=SessionResolutionAction.CONTINUE_SESSION,
        reason="recent_viable_session",
        scope=scope,
        session_id=scoped_session.session_id,
        decided_at=_timestamp(current),
        text_sha256_16=text_sha,
        text_length=len(content),
        raw_payload_ref=raw_payload_ref,
        run_id=scoped_session.last_run_id,
        prior_session_status=scoped_session.status,
        prior_run_status=scoped_session.last_run_status,
        id_factory=id_factory,
        metadata=safe_metadata,
    )


def _decision(
    *,
    action: SessionResolutionAction,
    reason: str,
    scope: SessionScope,
    session_id: str,
    decided_at: str,
    text_sha256_16: str,
    text_length: int,
    raw_payload_ref: str | None,
    id_factory: Callable[[str], str] | Any | None,
    run_id: str | None = None,
    interrupt_id: str | None = None,
    task_id: str | None = None,
    prior_session_status: str | None = None,
    prior_run_status: str | None = None,
    active_task_status: str | None = None,
    interrupt_status: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SessionResolutionDecision:
    return SessionResolutionDecision(
        decision_id=_new_id(id_factory, "session-decision"),
        action=action,
        reason=reason,
        scope=scope,
        session_id=session_id,
        decided_at=decided_at,
        text_sha256_16=text_sha256_16,
        text_length=text_length,
        raw_payload_ref=raw_payload_ref,
        run_id=run_id,
        interrupt_id=interrupt_id,
        task_id=task_id,
        prior_session_status=prior_session_status,
        prior_run_status=prior_run_status,
        active_task_status=active_task_status,
        interrupt_status=interrupt_status,
        metadata=_safe_metadata(metadata or {}),
    )


def _start_new_decision(
    *,
    scope: SessionScope,
    reason: str,
    current: datetime,
    text_sha: str,
    text_length: int,
    raw_payload_ref: str | None,
    session: SessionSnapshot | None,
    id_factory: Callable[[str], str] | Any | None,
    metadata: Mapping[str, Any] | None,
) -> SessionResolutionDecision:
    return _decision(
        action=SessionResolutionAction.START_NEW_SESSION,
        reason=reason,
        scope=scope,
        session_id=_new_id(id_factory, "session"),
        decided_at=_timestamp(current),
        text_sha256_16=text_sha,
        text_length=text_length,
        raw_payload_ref=raw_payload_ref,
        prior_session_status=session.status if session is not None else None,
        prior_run_status=session.last_run_status if session is not None else None,
        id_factory=id_factory,
        metadata=metadata,
    )


def _interrupt_is_pending(
    interrupt: PendingInterruptSnapshot,
    policy: SessionResolutionPolicy,
    current: datetime,
) -> bool:
    if _status_key(interrupt.status) not in policy.pending_interrupt_statuses:
        return False
    if interrupt.expires_at is None:
        return True
    return _coerce_datetime(interrupt.expires_at) > current


def _is_stale(updated_at: str, current: datetime, idle_window_seconds: float) -> bool:
    updated = _coerce_datetime(updated_at)
    return updated + timedelta(seconds=max(0.0, idle_window_seconds)) < current


def _is_new_task_signal(text: str, policy: SessionResolutionPolicy) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in policy.new_task_patterns)


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


def _copy_session(snapshot: SessionSnapshot) -> SessionSnapshot:
    return SessionSnapshot(
        scope=snapshot.scope,
        session_id=snapshot.session_id,
        status=snapshot.status,
        updated_at=snapshot.updated_at,
        created_at=snapshot.created_at,
        last_run_id=snapshot.last_run_id,
        last_run_status=snapshot.last_run_status,
        thread_id=snapshot.thread_id,
        metadata=_safe_metadata(snapshot.metadata),
    )


def _copy_interrupt(snapshot: PendingInterruptSnapshot) -> PendingInterruptSnapshot:
    return PendingInterruptSnapshot(
        scope=snapshot.scope,
        interrupt_id=snapshot.interrupt_id,
        run_id=snapshot.run_id,
        session_id=snapshot.session_id,
        status=snapshot.status,
        created_at=snapshot.created_at,
        expires_at=snapshot.expires_at,
        prompt_ref=snapshot.prompt_ref,
        resume_state_ref=snapshot.resume_state_ref,
        metadata=_safe_metadata(snapshot.metadata),
    )


def _copy_active_task(snapshot: ActiveTaskSnapshot) -> ActiveTaskSnapshot:
    return ActiveTaskSnapshot(
        scope=snapshot.scope,
        task_id=snapshot.task_id,
        status=snapshot.status,
        updated_at=snapshot.updated_at,
        run_id=snapshot.run_id,
        session_id=snapshot.session_id,
        metadata=_safe_metadata(snapshot.metadata),
    )


def _safe_metadata(value: Mapping[str, Any]) -> JsonObject:
    _reject_forbidden_payload_storage(value)
    return _json_clone(value)


def _reject_forbidden_payload_storage(event: Mapping[str, Any]) -> None:
    for path, key in _walk_keys(event):
        if key in ALL_FORBIDDEN_KEYS:
            raise ContractLogPrivacyError(f"contract log event contains forbidden {key} at {path}")


def _walk_keys(value: Any, path: str = "$") -> Any:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            yield child_path, key_text
            yield from _walk_keys(nested, child_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_keys(nested, f"{path}[{index}]")


def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


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
    current = _coerce_datetime(value)
    return current.isoformat().replace("+00:00", "Z")


def _status_key(value: str) -> str:
    return str(value).strip().lower()


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "ActiveTaskSnapshot",
    "InMemorySessionResolutionStore",
    "PendingInterruptSnapshot",
    "SessionResolutionAction",
    "SessionResolutionDecision",
    "SessionResolutionPolicy",
    "SessionScope",
    "SessionSnapshot",
    "resolve_session_turn",
]
