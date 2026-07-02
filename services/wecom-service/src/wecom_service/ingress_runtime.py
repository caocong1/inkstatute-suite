"""Pure WeCom callback-to-runtime orchestration."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from platform_contract.events import AgentTurn, AttachmentRef, JsonObject, OutputConstraints
from platform_runtime import (
    InMemoryInterruptStore,
    RunRequest,
    RunRuntime,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
    SolutionBinding,
)
from platform_runtime.session_resolver import ActiveTaskSnapshot

from .active_task_router import AdapterTaskCapabilities
from .normalization import normalize_wecom_turn
from .session_runtime import WeComSessionRuntime, WeComSessionRuntimeOutcome


class WeComRuntimeIngress:
    """Host-callable WeCom ingress boundary for runtime-backed turns.

    The class intentionally performs no network IO, signature verification,
    database access, queueing, or backend construction. Hosts own those concerns
    and inject already-sanitized callbacks plus runtime/session dependencies.
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
        self.session_runtime = WeComSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            policy=policy,
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
        capabilities: AdapterTaskCapabilities | None = None,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> WeComSessionRuntimeOutcome:
        turn = _agent_turn_from_callback(callback, received_at=received_at, default_thread_id=self.default_thread_id)
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
            capabilities=capabilities,
            idempotency_key=_string(turn.metadata.get("idempotency_key")),
            metadata={"source": "wecom_ingress_runtime"},
        )


def _agent_turn_from_callback(
    callback: Mapping[str, Any],
    *,
    received_at: str,
    default_thread_id: str | None,
) -> AgentTurn:
    event = normalize_wecom_turn(callback, received_at=received_at)
    metadata = dict(event.get("metadata") or {})
    thread_id = _first_string(callback, "thread_id", "ThreadId") or default_thread_id
    if thread_id is not None:
        metadata["thread_id"] = thread_id
    event["metadata"] = _safe_json(metadata)
    attachments = event.get("attachments")
    if isinstance(attachments, list):
        event["attachments"] = [
            AttachmentRef(**dict(item)) if isinstance(item, Mapping) else item for item in attachments
        ]
    output_constraints = event.get("output_constraints")
    if isinstance(output_constraints, Mapping):
        event["output_constraints"] = OutputConstraints(**dict(output_constraints))
    return AgentTurn(**event)


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
            "source": "wecom_ingress_runtime",
            "current_turn_ref": current_turn_ref,
            "raw_payload_refs": _append_unique(raw_payload_refs, raw_payload_ref),
            "request_ref": f"wecom://turn/{turn.turn_id}",
            "wecom_message_id": _string(turn.metadata.get("message_id")),
            "wecom_normalization": "sanitized_callback",
            "privacy": "no_raw_payload_or_legal_text_stored",
        }
    )


def _metadata_sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _string(value)
        return (text,) if text is not None else ()
    if isinstance(value, (list, tuple)):
        return tuple(text for item in value if (text := _string(item)) is not None)
    text = _string(value)
    return (text,) if text is not None else ()


def _append_unique(values: tuple[str, ...], value: str | None) -> list[str]:
    result = list(values)
    if value is not None and value not in result:
        result.append(value)
    return result


def _first_string(fields: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _string(fields.get(key))
        if value is not None:
            return value
    return None


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
                raise ValueError(f"unsafe WeCom ingress metadata key at {path}.{key_text}")
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


__all__ = ["WeComRuntimeIngress"]
