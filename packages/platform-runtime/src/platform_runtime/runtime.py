"""Dependency-injected embeddable run runtime."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from typing import Any, AsyncIterator, Iterable, Mapping

from platform_contract.enums import AgentResultStatus, AsyncTaskState, InterruptStatus, RunEventType

from .context_assembler import ContextAssembler, ContextAssemblyInput
from .feature_flags import RuntimeFeatureFlags
from .memory_orchestrator import MemoryOrchestrator
from .interrupts import InMemoryInterruptStore, InterruptLifecycleAction, InterruptRecord
from .output_boundary import BoundaryAction, DefaultAssistantOutputBoundary
from .ports import AssistantOutputBoundary, ContractLogStore, IdFactory, RuntimeClock
from .protocols import Approval, BackendAdapter, ChannelAdapter, Run, RunEvent, RunRequest
from .session_resolver import PendingInterruptSnapshot, SessionScope


class RunRuntimeStateError(RuntimeError):
    """Raised when runtime dependencies are inconsistent with enabled lanes."""


class DefaultRunRuntime:
    """RunRuntime implementation that speaks only injected protocol ports."""

    def __init__(
        self,
        *,
        backend: BackendAdapter,
        channels: Iterable[ChannelAdapter] = (),
        feature_flags: RuntimeFeatureFlags | None = None,
        contract_log_store: ContractLogStore | None = None,
        output_boundary: AssistantOutputBoundary | None = None,
        clock: RuntimeClock | None = None,
        id_factory: IdFactory | None = None,
        interrupt_store: InMemoryInterruptStore | None = None,
        context_assembler: ContextAssembler | None = None,
        memory_orchestrator: MemoryOrchestrator | None = None,
    ) -> None:
        self.backend = backend
        self.channels = tuple(channels)
        self.feature_flags = feature_flags or RuntimeFeatureFlags()
        self.contract_log_store = contract_log_store
        self.output_boundary = output_boundary or DefaultAssistantOutputBoundary()
        self.clock = clock or _SystemRuntimeClock()
        self.id_factory = id_factory or _SequentialIdFactory()
        self.interrupt_store = interrupt_store
        self.context_assembler = context_assembler
        self.memory_orchestrator = memory_orchestrator
        self._resumed_run_by_key: dict[tuple[str, str | None, str | None], str] = {}

    async def create_run(self, req: RunRequest) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self._require_contract_log_store_if_enabled()
        backend_req = self._attach_context_bundle(req)
        handle = await self.backend.submit_run(backend_req)
        if self.feature_flags.contract_log_enabled:
            self._append_run_record(backend_req, handle.run_id, handle.status, handle.backend_run_id)
            self._append_state_event(
                run_id=handle.run_id,
                turn_id=backend_req.turn.turn_id,
                status=handle.status,
                event_id=self.id_factory.new_id("run-event"),
                metadata={"source": "runtime_create"},
            )
        run = await self.backend.get_run(handle.run_id)
        self._record_clarification_interrupt_if_needed(req=req, run=run)
        return run

    async def resume_interrupt(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        req: RunRequest,
        idempotency_key: str | None = None,
    ) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self._require_interrupt_store()
        self._require_contract_log_store_if_enabled()
        answer = str(req.turn.content or "")
        current = self.clock.now()
        interrupt = await self._pending_interrupt_for_resume(
            interrupt_id=interrupt_id,
            scope=scope,
            turn_id=req.turn.turn_id,
            answer_text=answer,
            idempotency_key=idempotency_key,
            now=current,
        )
        if isinstance(interrupt, Run):
            return interrupt

        resume_metadata = {
            **req.metadata,
            "source": "runtime_resume_interrupt",
            "interrupt_id": interrupt.event.interrupt_id,
            "resume_state_ref": interrupt.event.resume_state_ref,
            "resuming_run_id": interrupt.event.run_id,
            "resolved_turn_id": req.turn.turn_id,
            "answer_text_sha256_16": _sha256_16(answer),
            "answer_text_length": len(answer),
            "resolved_idempotency_key": idempotency_key,
            "privacy": "no_raw_answer_text_stored",
        }
        resume_req = replace(req, metadata=resume_metadata)
        backend_req = self._attach_context_bundle(resume_req, pending_interrupt=interrupt)
        handle = await self.backend.submit_run(backend_req)
        decision = self.interrupt_store.resolve(
            interrupt_id=interrupt_id,
            scope=scope,
            turn_id=req.turn.turn_id,
            answer_text=answer,
            idempotency_key=idempotency_key,
            metadata={
                "backend_resume_submitted": True,
                "resumed_backend_run_id": handle.run_id,
                "resumed_backend_run_status": _status_value(handle.status),
                "resumed_backend_handle_id": handle.backend_run_id,
            },
            now=current,
        )
        if decision.action != InterruptLifecycleAction.RESOLVED:
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {decision.action.value}")

        self._resumed_run_by_key[_resume_key(interrupt_id, req.turn.turn_id, idempotency_key)] = handle.run_id
        if self.feature_flags.contract_log_enabled:
            self._append_run_record(backend_req, handle.run_id, handle.status, handle.backend_run_id)
            self._append_state_event(
                run_id=handle.run_id,
                turn_id=req.turn.turn_id,
                status=handle.status,
                event_id=self.id_factory.new_id("run-event"),
                metadata={
                    "source": "runtime_resume_interrupt",
                    "interrupt_id": interrupt.event.interrupt_id,
                    "resume_state_ref": interrupt.event.resume_state_ref,
                    "resuming_run_id": interrupt.event.run_id,
                    "answer_text_sha256_16": _sha256_16(answer),
                    "answer_text_length": len(answer),
                    "resolved_idempotency_key": idempotency_key,
                    "privacy": "no_raw_answer_text_stored",
                },
            )
        return await self.backend.get_run(handle.run_id)

    def _attach_context_bundle(
        self,
        req: RunRequest,
        *,
        pending_interrupt: InterruptRecord | None = None,
    ) -> RunRequest:
        if self.feature_flags.session_memory_enabled:
            return self._attach_context_bundle_with_memory(req, pending_interrupt=pending_interrupt)
        if not self.feature_flags.context_assembly_enabled:
            return req
        if self.context_assembler is None:
            raise RunRuntimeStateError("context_assembly_enabled requires context_assembler")

        assembly_input = self._context_assembly_input(req, pending_interrupt=pending_interrupt)
        result = self.context_assembler.assemble(assembly_input)
        context_event = result.as_event()
        metadata = {
            **dict(req.metadata),
            "context_bundle_id": context_event["context_bundle_id"],
            "context_bundle": context_event,
        }
        if self.feature_flags.contract_log_enabled:
            self._contract_log().append("context_bundle", context_event)
        return replace(req, metadata=metadata)

    def _attach_context_bundle_with_memory(
        self,
        req: RunRequest,
        *,
        pending_interrupt: InterruptRecord | None = None,
    ) -> RunRequest:
        if self.memory_orchestrator is None:
            raise RunRuntimeStateError("session_memory_enabled requires memory_orchestrator")

        assembly_input = self._context_assembly_input(req, pending_interrupt=pending_interrupt)
        result = self.memory_orchestrator.recall_and_assemble(
            scope=assembly_input.scope,
            session_id=assembly_input.session_id,
            turn_id=assembly_input.turn_id,
            current_turn_ref=assembly_input.current_turn_ref,
            current_turn_text=assembly_input.current_turn_text,
            recent_turn_refs=assembly_input.recent_turn_refs,
            artifact_refs=assembly_input.artifact_refs,
            feedback_correction_refs=assembly_input.feedback_correction_refs,
            output_policy_ref=assembly_input.output_policy_ref,
        )
        context_event = result.as_event()
        metadata = {
            **dict(req.metadata),
            "context_bundle_id": context_event["context_bundle_id"],
            "context_bundle": context_event,
        }
        if self.feature_flags.contract_log_enabled:
            self._contract_log().append("context_bundle", context_event)
        return replace(req, metadata=metadata)

    def _context_assembly_input(
        self,
        req: RunRequest,
        *,
        pending_interrupt: InterruptRecord | None = None,
    ) -> ContextAssemblyInput:
        metadata = dict(req.metadata)
        current_turn_ref = _first_text(
            metadata.get("current_turn_ref"),
            req.turn.metadata.get("current_turn_ref"),
            req.turn.metadata.get("raw_payload_ref"),
            f"turn://{req.turn.turn_id}",
        )
        output_constraints_ref = _optional_first_text(
            metadata.get("output_constraints_ref"),
            _output_constraints_metadata(req).get("output_constraints_ref"),
            _output_constraints_metadata(req).get("constraints_ref"),
        )
        output_policy_ref = _optional_first_text(
            metadata.get("output_policy_ref"),
            _output_constraints_metadata(req).get("output_policy_ref"),
        )
        return ContextAssemblyInput(
            scope=_scope_from_request(req),
            session_id=str(req.session_id or ""),
            turn_id=req.turn.turn_id,
            current_turn_ref=current_turn_ref,
            current_turn_text=req.turn.content,
            current_turn_raw_payload_ref=_raw_payload_ref(req),
            run_id=_optional_text(metadata.get("run_id")),
            recent_turn_refs=_metadata_sequence(metadata.get("recent_turn_refs")),
            artifact_refs=_metadata_sequence(metadata.get("artifact_refs")),
            feedback_correction_refs=_metadata_sequence(metadata.get("feedback_correction_refs")),
            pending_interrupt=_pending_interrupt_snapshot(pending_interrupt) if pending_interrupt is not None else None,
            memory_refs=_metadata_sequence(metadata.get("memory_refs")),
            output_constraints_ref=output_constraints_ref,
            output_policy_ref=output_policy_ref,
            raw_payload_refs=_metadata_sequence(metadata.get("raw_payload_refs")),
            industry_context=_metadata_mapping(metadata.get("industry_context")),
            metadata={
                "source": metadata.get("source", "runtime_create"),
                "privacy": "no_raw_payload_or_legal_text_stored",
            },
        )

    async def _pending_interrupt_for_resume(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        turn_id: str,
        answer_text: str,
        idempotency_key: str | None,
        now: datetime | str,
    ) -> InterruptRecord | Run:
        record = self.interrupt_store.get(interrupt_id)
        if record is None:
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {InterruptLifecycleAction.NOT_FOUND.value}")
        if record.scope != scope:
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {InterruptLifecycleAction.SCOPE_MISMATCH.value}")

        status = _enum_value(record.event.status)
        if status == InterruptStatus.RESOLVED.value:
            run_id = self._resumed_run_by_key.get(_resume_key(interrupt_id, turn_id, idempotency_key))
            if run_id is None and _same_resume(record, turn_id=turn_id, idempotency_key=idempotency_key):
                metadata = record.event.metadata
                durable_run_id = metadata.get("resumed_backend_run_id")
                if metadata.get("backend_resume_submitted") is True and durable_run_id:
                    run_id = str(durable_run_id)
                    self._resumed_run_by_key[_resume_key(interrupt_id, turn_id, idempotency_key)] = run_id
            if run_id is None:
                raise RunRuntimeStateError("duplicate interrupt resume has no recorded backend run")
            return await self.backend.get_run(run_id)

        if status == InterruptStatus.CANCELLED.value:
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {InterruptLifecycleAction.CANCELLED.value}")
        if status == InterruptStatus.EXPIRED.value or _interrupt_is_expired(record, now):
            decision = self.interrupt_store.resolve(
                interrupt_id=interrupt_id,
                scope=scope,
                turn_id=turn_id,
                answer_text=answer_text,
                idempotency_key=idempotency_key,
                now=now,
            )
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {decision.action.value}")
        if status != InterruptStatus.WAITING_FOR_USER.value:
            raise RunRuntimeStateError(f"interrupt cannot be resumed: {status}")
        return record

    async def poll(self, run_id: str) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        return await self.backend.get_run(run_id)

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self.feature_flags.require_enabled("streaming_lane_enabled")
        gen = self.backend.stream_events(run_id)
        try:
            async for event in gen:
                bounded_event = self._apply_output_boundary(event)
                if bounded_event is not None:
                    yield bounded_event
        finally:
            await gen.aclose()

    async def cancel(self, run_id: str) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self._require_contract_log_store_if_enabled()
        run = await self.backend.cancel_run(run_id)
        if self.feature_flags.contract_log_enabled:
            self._append_state_event(
                run_id=run.run_id,
                turn_id=run.turn_id,
                status=AsyncTaskState.CANCELLED,
                event_id=self.id_factory.new_id("run-event"),
                metadata={"source": "runtime_cancel"},
            )
        return run

    async def approve(self, run_id: str, approval: Approval) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self.feature_flags.require_enabled("approval_lane_enabled")
        self._require_contract_log_store_if_enabled()
        run = await self.backend.submit_approval(run_id, approval)
        if self.feature_flags.contract_log_enabled:
            self._append_state_event(
                run_id=run.run_id,
                turn_id=run.turn_id,
                status=run.status,
                event_id=self.id_factory.new_id("run-event"),
                metadata={
                    "source": "runtime_approval",
                    "approval_id": approval.approval_id,
                    "approval_decision": approval.decision,
                },
            )
        return run

    def _append_run_record(
        self,
        req: RunRequest,
        run_id: str,
        status: AsyncTaskState | str,
        backend_run_id: str | None,
    ) -> None:
        self._contract_log().append(
            "run",
            {
                "run_id": run_id,
                "backend_run_id": backend_run_id,
                "turn_id": req.turn.turn_id,
                "solution_id": req.solution.solution_id,
                "tenant_id": req.tenant_id,
                "workspace_id": req.workspace_id,
                "session_id": req.session_id,
                "status": _status_value(status),
                "occurred_at": self.clock.now(),
                "raw_payload_ref": _raw_payload_ref(req),
                "content_sha256": _sha256_or_none(req.turn.content),
                "metadata": {"runtime": "default"},
            },
        )

    def _append_state_event(
        self,
        *,
        run_id: str,
        turn_id: str,
        status: AsyncTaskState | str,
        event_id: str,
        metadata: dict[str, object],
    ) -> None:
        self._contract_log().append(
            "run_event",
            {
                "event_id": event_id,
                "run_id": run_id,
                "turn_id": turn_id,
                "event_type": RunEventType.STATE_CHANGED.value,
                "status": _status_value(status),
                "occurred_at": self.clock.now(),
                "metadata": metadata,
            },
        )

    def _contract_log(self) -> ContractLogStore:
        if self.contract_log_store is None:
            raise RunRuntimeStateError("contract_log_enabled requires contract_log_store")
        return self.contract_log_store

    def _require_interrupt_store(self) -> InMemoryInterruptStore:
        if self.interrupt_store is None:
            raise RunRuntimeStateError("interrupt resume requires interrupt_store")
        return self.interrupt_store

    def _require_contract_log_store_if_enabled(self) -> None:
        if self.feature_flags.contract_log_enabled:
            self._contract_log()

    def _record_clarification_interrupt_if_needed(self, *, req: RunRequest, run: Run) -> None:
        if not _is_clarification_run(run):
            return
        store = self._require_interrupt_store()
        result_metadata = dict(run.result.metadata if run.result is not None else {})
        prompt_ref = _required_ref(result_metadata, "prompt_ref")
        resume_state_ref = _required_ref(result_metadata, "resume_state_ref")
        record = store.create_clarification(
            scope=_scope_from_request(req),
            run_id=run.run_id,
            session_id=req.session_id or "",
            prompt_ref=prompt_ref,
            resume_state_ref=resume_state_ref,
            reason=str(result_metadata.get("reason") or "backend_needs_clarification"),
            expected_response_schema_ref=_optional_ref(result_metadata, "expected_response_schema_ref"),
            expires_at=_optional_ref(result_metadata, "expires_at"),
            metadata=_clarification_metadata(result_metadata),
        )
        if self.feature_flags.contract_log_enabled:
            self._append_interrupt_record(record)
            self._append_state_event(
                run_id=run.run_id,
                turn_id=run.turn_id,
                status=AsyncTaskState.WAITING_FOR_USER,
                event_id=self.id_factory.new_id("run-event"),
                metadata={
                    "source": "runtime_clarification_interrupt",
                    "interrupt_id": record.event.interrupt_id,
                    "interrupt_status": InterruptStatus.WAITING_FOR_USER.value,
                    "agent_result_status": AgentResultStatus.NEEDS_CLARIFICATION.value,
                    "privacy": "no_raw_prompt_or_answer_text_stored",
                },
            )

    def _append_interrupt_record(self, record: InterruptRecord) -> None:
        self._contract_log().append("run_interrupt", record.as_event())

    def _apply_output_boundary(self, event: RunEvent) -> RunEvent | None:
        visible_text = _event_visible_text(event)
        decision = self.output_boundary.apply(
            visibility_target="ordinary_user",
            text=visible_text,
            event_metadata=event.metadata,
            event_type=event.event_type,
        )
        policy_metadata = {
            "action": _boundary_action_value(decision.action),
            "reason": getattr(decision, "reason", None),
            "audit": dict(decision.audit_metadata),
        }

        if _boundary_action_value(decision.action) == BoundaryAction.BLOCK.value:
            return replace(
                event,
                payload=_without_visible_text(event.payload),
                metadata={**_without_visible_text(event.metadata), "output_boundary": policy_metadata},
            )

        if _boundary_action_value(decision.action) == BoundaryAction.REWRITE.value:
            return replace(
                event,
                payload=_replace_visible_text(event.payload, decision.visible_text),
                metadata={**_without_visible_text(event.metadata), "output_boundary": policy_metadata},
            )

        return replace(
            event,
            payload=dict(event.payload),
            metadata={**event.metadata, "output_boundary": policy_metadata},
        )


class _SystemRuntimeClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _SequentialIdFactory:
    def __init__(self) -> None:
        self._next_by_prefix: dict[str, int] = {}

    def new_id(self, prefix: str) -> str:
        next_value = self._next_by_prefix.get(prefix, 1)
        self._next_by_prefix[prefix] = next_value + 1
        return f"{prefix}-{next_value:06d}"


def _raw_payload_ref(req: RunRequest) -> str | None:
    value = req.turn.metadata.get("raw_payload_ref")
    return str(value) if value is not None else None


def _sha256_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _status_value(status: AsyncTaskState | str) -> str:
    if isinstance(status, AsyncTaskState):
        return status.value
    return str(status)


def _enum_value(value: object) -> str:
    return getattr(value, "value", str(value))


def _interrupt_is_expired(record: InterruptRecord, now: datetime | str) -> bool:
    if record.event.expires_at is None:
        return False
    return _coerce_datetime(record.event.expires_at) <= _coerce_datetime(now)


def _same_resume(record: InterruptRecord, *, turn_id: str, idempotency_key: str | None) -> bool:
    metadata = record.event.metadata
    return metadata.get("resolved_turn_id") == turn_id or (
        idempotency_key is not None and metadata.get("resolved_idempotency_key") == idempotency_key
    )


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


_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")


def _event_visible_text(event: RunEvent) -> str | None:
    for mapping in (event.payload, event.metadata):
        for key in _VISIBLE_TEXT_KEYS:
            value = mapping.get(key)
            if isinstance(value, str):
                return value
    return None


def _without_visible_text(mapping: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in mapping.items() if key not in _VISIBLE_TEXT_KEYS}


def _replace_visible_text(mapping: Mapping[str, object], value: str | None) -> dict[str, object]:
    updated = dict(mapping)
    for key in _VISIBLE_TEXT_KEYS:
        if key in updated:
            updated[key] = value
            return updated
    updated["message_delta"] = value
    return updated


def _boundary_action_value(action: object) -> str:
    if isinstance(action, BoundaryAction):
        return action.value
    return str(action)


def _is_clarification_run(run: Run) -> bool:
    if _status_value(run.status) != AsyncTaskState.WAITING_FOR_USER.value:
        return False
    if run.result is None:
        return False
    status = run.result.status
    if isinstance(status, AgentResultStatus):
        return status == AgentResultStatus.NEEDS_CLARIFICATION
    return str(status) == AgentResultStatus.NEEDS_CLARIFICATION.value


def _scope_from_request(req: RunRequest) -> SessionScope:
    return SessionScope(
        tenant_id=str(req.tenant_id or ""),
        workspace_id=str(req.workspace_id or ""),
        channel_id=_channel_id(req),
        user_id=req.turn.user_id,
        bot_instance_id=str(req.bot_instance_id or ""),
        conversation_id=req.turn.conversation_id,
        thread_id=_optional_text(req.turn.metadata.get("thread_id")),
    )


def _channel_id(req: RunRequest) -> str:
    channel = req.turn.channel
    return getattr(channel, "value", str(channel))


def _required_ref(metadata: Mapping[str, object], key: str) -> str:
    value = metadata.get(key)
    if value is None or str(value) == "":
        raise RunRuntimeStateError(f"clarification result missing {key}")
    return str(value)


def _optional_ref(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _first_text(*values: object) -> str:
    for value in values:
        if value is not None and str(value) != "":
            return str(value)
    raise RunRuntimeStateError("context assembly requires a current_turn_ref")


def _optional_first_text(*values: object) -> str | None:
    for value in values:
        if value is not None and str(value) != "":
            return str(value)
    return None


def _metadata_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if item is not None and str(item) != "")
    return (str(value),)


def _metadata_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): nested for key, nested in value.items()}
    return {}


def _output_constraints_metadata(req: RunRequest) -> Mapping[str, object]:
    if req.output_constraints is None:
        return {}
    return req.output_constraints.metadata


def _pending_interrupt_snapshot(record: InterruptRecord) -> PendingInterruptSnapshot:
    return PendingInterruptSnapshot(
        scope=record.scope,
        interrupt_id=record.event.interrupt_id,
        run_id=record.event.run_id,
        session_id=record.event.session_id,
        status=_enum_value(record.event.status),
        created_at=record.event.created_at,
        expires_at=record.event.expires_at,
        prompt_ref=record.event.prompt_ref,
        resume_state_ref=record.event.resume_state_ref,
        metadata=dict(record.event.metadata),
    )


def _clarification_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    allowed_keys = {
        "question_kind",
        "choice_refs",
        "expected_response_schema_ref",
        "raw_payload_ref",
        "privacy",
    }
    return {key: value for key, value in metadata.items() if key in allowed_keys}


def _resume_key(interrupt_id: str, turn_id: str | None, idempotency_key: str | None) -> tuple[str, str | None, str | None]:
    return (interrupt_id, turn_id, idempotency_key)


__all__ = [
    "DefaultRunRuntime",
    "RunRuntimeStateError",
]
