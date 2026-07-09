"""Pure QQBot callback-to-runtime orchestration.

Host-callable ingress boundary: sanitized gateway envelope → Phase 60
normalization → SessionScope / RunRequest → QQBotSessionRuntime. Performs no
network IO, signature verification, database access, or queueing.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from typing import Any

from platform_contract.events import AgentTurn, JsonObject
from platform_runtime import (
    InMemoryInterruptStore,
    Memory,
    MemoryOrchestrator,
    RunRequest,
    RunRuntime,
    SessionResolutionAction,
    SessionResolutionDecision,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
    SolutionBinding,
)
from platform_runtime.session_resolver import ActiveTaskSnapshot

from .normalization import QQBotEventCategory, normalize_message_event, parse_envelope
from .session_runtime import (
    QQBotSessionRuntime,
    QQBotSessionRuntimeAction,
    QQBotSessionRuntimeOutcome,
)

_MESSAGE_CATEGORIES = frozenset(
    {
        QQBotEventCategory.C2C_MESSAGE,
        QQBotEventCategory.GROUP_AT_MESSAGE,
    }
)


class QQBotRuntimeIngress:
    """Host-callable QQBot ingress boundary for runtime-backed turns.

    Accepts already-sanitized gateway envelopes. Signature verification, ACK,
    and transport remain host / Phase 65 concerns.
    """

    def __init__(
        self,
        *,
        runtime: RunRuntime,
        solution: SolutionBinding,
        tenant_id: str,
        workspace_id: str,
        bot_instance_id: str,
        interrupt_store: InMemoryInterruptStore | None = None,
        policy: SessionResolutionPolicy | None = None,
        memory_orchestrator: MemoryOrchestrator | None = None,
        memory: Memory | None = None,
        memory_policy: Any | None = None,
        clock: Any | None = None,
        id_factory: Any | None = None,
        default_thread_id: str | None = None,
        base_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.runtime = runtime
        self.solution = solution
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.bot_instance_id = bot_instance_id
        self.default_thread_id = default_thread_id
        self.base_metadata = _safe_json(dict(base_metadata or {}))
        self.clock = clock
        self.id_factory = id_factory
        self.session_runtime = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            policy=policy,
            memory_orchestrator=memory_orchestrator,
            memory=memory,
            memory_policy=memory_policy,
            clock=clock,
            id_factory=id_factory,
        )

    async def handle_callback(
        self,
        callback: Mapping[str, Any],
        *,
        received_at: str,
        recent_session: SessionSnapshot | None = None,
        active_task: ActiveTaskSnapshot | Mapping[str, Any] | None = None,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QQBotSessionRuntimeOutcome:
        event = parse_envelope(callback)
        if event.category not in _MESSAGE_CATEGORIES:
            return self._skipped_non_message(event.category, received_at=received_at)

        turn = normalize_message_event(
            event,
            received_at=received_at,
            payload_ref=_string(callback.get("raw_payload_ref")) or event.raw_payload_ref,
        )
        if self.default_thread_id is not None and "thread_id" not in turn.metadata:
            turn.metadata["thread_id"] = self.default_thread_id

        scope = _scope_from_turn(
            turn,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            bot_instance_id=self.bot_instance_id,
        )
        run_request = RunRequest(
            turn=turn,
            solution=self.solution,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            bot_instance_id=self.bot_instance_id,
            session_id=session_id or (recent_session.session_id if recent_session is not None else None),
            output_constraints=turn.output_constraints,
            metadata=_run_metadata(turn, base_metadata=self.base_metadata, metadata=metadata),
        )
        return await self.session_runtime.handle_turn(
            turn=turn,
            scope=scope,
            run_request=run_request,
            recent_session=recent_session,
            active_task=active_task,
            idempotency_key=(
                _string(turn.metadata.get("idempotency_key"))
                or _string(turn.metadata.get("message_id"))
                or turn.turn_id
            ),
            metadata={"source": "qqbot_ingress_runtime"},
        )

    def _skipped_non_message(
        self,
        category: QQBotEventCategory,
        *,
        received_at: str,
    ) -> QQBotSessionRuntimeOutcome:
        scope = SessionScope(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            channel_id="qqbot",
            user_id="unknown",
            bot_instance_id=self.bot_instance_id,
            conversation_id="qqbot:skipped:non_message",
            thread_id=self.default_thread_id,
        )
        decision = SessionResolutionDecision(
            decision_id=_new_id(self.id_factory, "decision"),
            action=SessionResolutionAction.START_NEW_SESSION,
            reason="ingress_skipped_non_message",
            scope=scope,
            session_id=_new_id(self.id_factory, "session"),
            decided_at=_timestamp(received_at),
            text_sha256_16="0" * 16,
            text_length=0,
            metadata={
                "source": "qqbot_ingress_runtime",
                "privacy": "no_raw_payload_or_legal_text_stored",
            },
        )
        return QQBotSessionRuntimeOutcome(
            action=QQBotSessionRuntimeAction.SKIPPED_NON_MESSAGE,
            decision=decision,
            run_id=None,
            evidence={
                "ingress_status": "skipped_non_message",
                "category": category.value,
                "resume_attempted": False,
                "runtime_create_called": False,
                "runtime_resume_called": False,
            },
        )


def _scope_from_turn(
    turn: AgentTurn,
    *,
    tenant_id: str,
    workspace_id: str,
    bot_instance_id: str,
) -> SessionScope:
    return SessionScope(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        channel_id=str(getattr(turn.channel, "value", turn.channel)),
        user_id=turn.user_id,
        bot_instance_id=bot_instance_id,
        conversation_id=turn.conversation_id,
        thread_id=_string(turn.metadata.get("thread_id")),
    )


def _run_metadata(
    turn: AgentTurn,
    *,
    base_metadata: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
) -> JsonObject:
    raw_payload_ref = _string(turn.metadata.get("raw_payload_ref"))
    current_turn_ref = raw_payload_ref or f"turn://{turn.turn_id}"
    raw_payload_refs = _metadata_sequence(base_metadata.get("raw_payload_refs")) + _metadata_sequence(
        (metadata or {}).get("raw_payload_refs")
    )
    return _safe_json(
        {
            **dict(base_metadata),
            **dict(metadata or {}),
            "source": "qqbot_ingress_runtime",
            "current_turn_ref": current_turn_ref,
            "raw_payload_refs": _append_unique(raw_payload_refs, raw_payload_ref),
            "request_ref": f"qqbot://turn/{turn.turn_id}",
            "qqbot_message_id": _string(turn.metadata.get("message_id")),
            "qqbot_normalization": "sanitized_callback",
            "privacy": _string((metadata or {}).get("privacy"))
            or _string(base_metadata.get("privacy"))
            or "no_raw_payload_or_legal_text_stored",
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


def _new_id(id_factory: Any | None, prefix: str) -> str:
    if id_factory is None:
        return f"{prefix}-skipped"
    if callable(id_factory):
        return str(id_factory(prefix))
    make = getattr(id_factory, "new_id", None)
    if callable(make):
        return str(make(prefix))
    return f"{prefix}-skipped"


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(value)
    if text.endswith("Z") or "+" in text[10:] or text.endswith("+00:00"):
        return text if text.endswith("Z") else text
    return text


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _safe_json(value: Mapping[str, Any]) -> JsonObject:
    _reject_unsafe_keys(value)
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _reject_unsafe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if key_text == "raw_payload" or key_text in _FORBIDDEN_FULL_TEXT_KEYS:
                raise ValueError(f"unsafe QQBot ingress metadata key at {path}.{key_text}")
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


__all__ = ["QQBotRuntimeIngress"]
