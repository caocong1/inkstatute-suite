# Phase 15: Session Resolver and Interrupt Runtime - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 10 likely new/modified files
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `packages/platform-contract/src/platform_contract/schemas/session_decision.schema.json` | schema | request-response | `packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json` | role-match |
| `packages/platform-contract/src/platform_contract/events.py` | model | transform | `Session`, `RunInterrupt`, `MemoryRecord` in same file | exact |
| `packages/platform-contract/src/platform_contract/enums.py` | model | state machine | `AsyncTaskState`, `InterruptStatus` in same file | exact |
| `packages/platform-runtime/src/platform_runtime/session_resolver.py` | service | request-response | `services/wecom-service/src/wecom_service/active_task_router.py` | exact |
| `packages/platform-runtime/src/platform_runtime/interrupts.py` | service | event-driven | `packages/platform-runtime/src/platform_runtime/runtime.py` | role-match |
| `packages/platform-runtime/src/platform_runtime/store.py` | utility | event-driven | same file `InMemoryContractLogStore` | exact |
| `packages/platform-runtime/src/platform_runtime/protocols.py` | provider | request-response | same file `RunRequest`, `BackendAdapter`, `RunRuntime` | exact |
| `services/wecom-service/src/wecom_service/session_runtime.py` | service | request-response | `services/wecom-service/src/wecom_service/task_flow.py` | exact |
| `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | service | transform | same file `map_agent_end_context` | exact |
| tests under `packages/platform-runtime/tests`, `services/wecom-service/tests`, `packages/contract-test-suite/tests` | test | transform/request-response | `test_active_task_router.py`, `test_task_flow.py`, `test_privacy_gates.py` | exact |

## Pattern Assignments

### `packages/platform-contract/src/platform_contract/schemas/session_decision.schema.json` (schema, request-response)

**Analog:** `packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json`

**Schema shape** (lines 1-17):
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://inkstatute.dev/schemas/platform-contract/run_interrupt.schema.json",
  "title": "RunInterrupt",
  "description": "Persisted waiting-for-user state for resumable backend or skill clarification.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "interrupt_id",
    "run_id",
    "session_id",
    "status",
    "reason",
    "created_at",
    "prompt_ref",
    "resume_state_ref"
  ],
```

**Reference-first fields** (lines 43-63):
```json
"prompt_ref": {
  "type": "string"
},
"resume_state_ref": {
  "type": "string"
},
"expected_response_schema_ref": {
  "type": "string"
},
"metadata": {
  "$ref": "common.schema.json#/$defs/metadata"
}
```

Use the same `additionalProperties: false`, required ID/timestamp fields, and `*_ref` convention. For session decisions, prefer fields like `decision_id`, `conversation_id`, `session_id`, `reason`, `created_at`, `raw_payload_ref`, `metadata`; do not add raw user text.

### `packages/platform-contract/src/platform_contract/events.py` (model, transform)

**Analog:** `Session`, `MemoryRecord`, `RunInterrupt`

**Dataclass convention** (lines 374-386):
```python
@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    tenant_id: str
    workspace_id: str
    created_at: str
    updated_at: str
    user_id: str | None = None
    channel: Channel | str | None = None
    channel_conversation_id: str | None = None
    status: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

**Privacy-safe memory/reference pattern** (lines 458-478):
```python
@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    tenant_id: str
    workspace_id: str
    scope: MemoryScope | str
    status: MemoryStatus | str
    sensitivity: MemorySensitivity | str
    created_at: str
    updated_at: str
    source_refs: list[str]
    summary: str | None = None
    subject: str | None = None
    related_user_id: str | None = None
    session_id: str | None = None
    raw_payload_ref: str | None = None
```

**Interrupt binding** (lines 539-553):
```python
@dataclass(frozen=True, slots=True)
class RunInterrupt:
    interrupt_id: str
    run_id: str
    session_id: str
    status: InterruptStatus | str
    reason: str
    created_at: str
    prompt_ref: str
    resume_state_ref: str
    expected_response_schema_ref: str | None = None
```

Add new bindings in this style only if schemas require them. Use `JsonObject = dict[str, Any]`, `field(default_factory=dict/list)`, `Enum | str` unions, and update `__all__`.

### `packages/platform-contract/src/platform_contract/enums.py` (model, state machine)

**Analog:** same file

**Task and result states** (lines 6-15, 73-79):
```python
class AsyncTaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"
```

**Interrupt state** (lines 199-203):
```python
class InterruptStatus(StrEnum):
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
```

Phase 15 state mapping should reuse `waiting_for_user` for paused runs and `needs_clarification` for backend result status. If adding a resolver enum, use `StrEnum`, lowercase snake-case values, and add it to `__all__`.

### `packages/platform-runtime/src/platform_runtime/session_resolver.py` (service, request-response)

**Analog:** `services/wecom-service/src/wecom_service/active_task_router.py`

**Imports and dataclass style** (lines 3-10, 15-21, 39-51):
```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import re
from typing import Any, Mapping

class ActiveTaskRoute(StrEnum):
    STATUS_REQUEST = "status_request"
    CANCEL_REQUEST = "cancel_request"
    TASK_UPDATE = "task_update"
    NEW_PARALLEL_TASK = "new_parallel_task"
    UNSUPPORTED_UPDATE_ACK = "unsupported_update_ack"

@dataclass(frozen=True, slots=True)
class ActiveTaskRoutingDecision:
    route: ActiveTaskRoute
    task_id: str
    accepted_by_backend: bool
    notice_kind: str
    reason: str
    intent_class: str
    text_sha256_16: str
    text_length: int
```

**Decision serialization/privacy** (lines 52-66):
```python
def as_event(self) -> JsonObject:
    return {
        "event": "wecom_active_task_route",
        "task_id": self.task_id,
        "route": self.route.value,
        "intent_class": self.intent_class,
        "accepted_by_backend": self.accepted_by_backend,
        "notice_kind": self.notice_kind,
        "reason": self.reason,
        "text_sha256_16": self.text_sha256_16,
        "text_length": self.text_length,
        "raw_payload_ref": self.raw_payload_ref,
        "privacy": "no_raw_payload_or_legal_text_stored",
    }
```

**Rule-based routing pattern** (lines 69-83, 168-187):
```python
def route_active_task_turn(*, text: str | None, active_task: Mapping[str, Any], capabilities: AdapterTaskCapabilities, raw_payload_ref: str | None = None) -> ActiveTaskRoutingDecision:
    content = str(text or "")
    task_id = str(active_task.get("task_id") or "unknown-task")
    intent = _classify_intent(content)
    text_sha = _sha16(content)

def _classify_intent(text: str) -> ActiveTaskRoute:
    normalized = text.strip().lower()
    if not normalized:
        return ActiveTaskRoute.STATUS_REQUEST
    if _STATUS_RE.search(normalized):
        return ActiveTaskRoute.STATUS_REQUEST
    if _CANCEL_RE.search(normalized):
        return ActiveTaskRoute.CANCEL_REQUEST
    if _NEW_TASK_RE.search(normalized):
        return ActiveTaskRoute.NEW_PARALLEL_TASK
    return ActiveTaskRoute.TASK_UPDATE
```

Copy this pattern for `SessionResolutionDecision`: deterministic classifier over channel/user/bot, active task, pending interrupt, idle window, and new-task signal. Store `text_sha256_16`, `text_length`, `raw_payload_ref`, not raw text. Expected routes: continue session, resume interrupt, start new session, reject/expire stale interrupt, or active-task follow-up.

### `packages/platform-runtime/src/platform_runtime/interrupts.py` (service, event-driven)

**Analog:** `packages/platform-runtime/src/platform_runtime/runtime.py`

**Dependency-injected runtime** (lines 22-43):
```python
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
    ) -> None:
        self.backend = backend
        self.channels = tuple(channels)
        self.feature_flags = feature_flags or RuntimeFeatureFlags()
        self.contract_log_store = contract_log_store
        self.output_boundary = output_boundary or DefaultAssistantOutputBoundary()
        self.clock = clock or _SystemRuntimeClock()
        self.id_factory = id_factory or _SequentialIdFactory()
```

**Contract log append pattern** (lines 104-127):
```python
def _append_run_record(self, req: RunRequest, run_id: str, status: AsyncTaskState | str, backend_run_id: str | None) -> None:
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
```

Implement interrupt persist/resolve as injected runtime helpers. Append `run_interrupt` and `run_event` records only through `ContractLogStore`; include `prompt_ref`, `resume_state_ref`, `resolved_turn_id`, timestamps, and content hashes/refs. Do not call Hermes directly from generic runtime code.

### `packages/platform-runtime/src/platform_runtime/store.py` (utility, event-driven)

**Analog:** same file

**Append-only cloned records** (lines 18-33, 36-64):
```python
@dataclass(frozen=True, slots=True)
class ContractLogEntry:
    event_key: str
    occurred_at: str
    ingested_at: str
    seq: int
    event: JsonObject

class InMemoryContractLogStore:
    def append(self, event_key: str, event: Mapping[str, Any], *, occurred_at: str | None = None, ingested_at: str | None = None) -> ContractLogEntry:
        _reject_forbidden_payload_storage(event)
        now = _timestamp(_clock_now(self._clock))
        stored = ContractLogEntry(..., event=_json_clone(event))
        self._entries.append(stored)
        self._next_seq += 1
        return _copy_entry(stored)
```

**Privacy guard** (lines 108-137):
```python
def _reject_forbidden_payload_storage(event: Mapping[str, Any]) -> None:
    for path, key in _walk_keys(event):
        if key == "raw_payload":
            raise ContractLogPrivacyError(f"contract log event contains forbidden raw_payload at {path}")
        if key in _FORBIDDEN_FULL_TEXT_KEYS:
            raise ContractLogPrivacyError(
                f"contract log event contains forbidden full-text payload field at {path}"
            )
```

If Phase 15 adds store query helpers, preserve copy-on-read, append-only behavior, timestamp normalization, and these forbidden key checks.

### `packages/platform-runtime/src/platform_runtime/protocols.py` (provider, request-response)

**Analog:** same file

**Protocol/dataclass boundary** (lines 105-115, 220-237, 253-262):
```python
@dataclass(frozen=True, slots=True)
class RunRequest:
    turn: AgentTurn
    solution: SolutionBinding
    tenant_id: str | None = None
    workspace_id: str | None = None
    bot_instance_id: str | None = None
    session_id: str | None = None
    output_constraints: OutputConstraints | None = None
    metadata: JsonObject = field(default_factory=dict)

class BackendAdapter(Protocol):
    async def submit_run(self, req: RunRequest) -> RunHandle: ...
    async def get_run(self, run_id: str) -> Run: ...
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...
    async def cancel_run(self, run_id: str) -> Run: ...

class RunRuntime(Protocol):
    async def create_run(self, req: RunRequest) -> Run: ...
    async def poll(self, run_id: str) -> Run: ...
```

Add `SessionResolver` / `InterruptRuntime` protocols here only as signature-only surfaces with pure dataclasses. Keep implementation out of `protocols.py`.

### `services/wecom-service/src/wecom_service/session_runtime.py` (service, request-response)

**Analog:** `services/wecom-service/src/wecom_service/task_flow.py`

**Service-owned boundary statement** (lines 1-19):
```python
"""Backend-neutral WeCom task-flow primitives.

The task flow intentionally separates service-owned progress from model
reasoning. User-visible progress is generated by InkStatute from these stages;
hidden reasoning, Hermes gateway output, paths, commands, tokens, and runtime
details are never forwarded as progress.
"""
```

**Task/session state machine style** (lines 36-67, 123-145):
```python
class WeComTaskStage(StrEnum):
    RECEIVED = "received"
    TURN_READY = "turn_ready"
    QUEUED = "queued"
    RUNNING = "running"
    PROGRESS_NOTICE_DUE = "progress_notice_due"
    ARTIFACT_READY = "artifact_ready"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

TERMINAL_TASK_STAGES = {
    WeComTaskStage.COMPLETED,
    WeComTaskStage.FAILED,
    WeComTaskStage.TIMEOUT,
    WeComTaskStage.CANCELLED,
}
```

**Stable IDs and minimized task metadata** (lines 167-219, 286-302):
```python
identity = ":".join(["wecom-task", str(conversation_id), str(user_id), str(message_id), input_summary.text_sha256_16, str(input_summary.media_count)])
task_id = f"wecom-task-{_sha16(identity)}"
trace_id = f"trace-{_sha16(task_id + ':trace')}"
...
"service_boundary": "inkstatute_wecom_service",
"agent_backend_boundary": "adapter_only",
"wecom_ingress_egress_owner": "inkstatute",
"active_task_followup_route": "fast_control_plane",
...
def task_snapshot(task: TaskFlow) -> JsonObject:
    return {
        "task_id": task.task_id,
        "trace_id": task.trace_id,
        "conversation_id": task.conversation_id,
        "user_id_hash": task.user_id_hash,
        "privacy": "no_raw_payload_or_legal_text_stored",
    }
```

WeCom integration should call the platform session resolver before creating/submitting a run. Use InkStatute-owned clarification wording and keep backend/Hermes terminology out of ordinary-user messages.

### `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` (service, transform)

**Analog:** same file

**Backend-to-contract mapping pattern** (lines 29-49, 51-61):
```python
def map_agent_end_context(context: Mapping[str, Any], *, now: datetime | str, seq_start: int = 0) -> OrderedDict[str, dict[str, Any]]:
    timestamp = _timestamp(now)
    session_id = _string(context.get("session_id"), "unknown-session")
    user_id = _string(context.get("user_id"), "unknown-user")
    chat_id = _string(context.get("chat_id"), "unknown-chat")
    message = _string_or_none(context.get("message"))
    response = _string_or_none(context.get("response"))
    message_id = _string_or_none(context.get("message_id"))
    raw_payload_ref = _raw_payload_ref(context, session_id=session_id)

    turn_id = stable_hash_id("turn", session_id, user_id, message_id or message, timestamp)
    route_decision_id = stable_hash_id("route", turn_id, session_id, user_id, timestamp)
    trace_id = stable_hash_id("trace", turn_id, route_decision_id, timestamp)
    result_id = stable_hash_id("result", turn_id, message_id or response, timestamp)
```

**Clarification result fields already mapped** (lines 143-166):
```python
agent_result = {
    "result_id": result_id,
    "turn_id": turn_id,
    "status": status,
    "reply_type": reply_type,
    "artifacts": _artifacts(context.get("artifacts")),
    "clarifying_questions": _string_list(context.get("clarifying_questions")),
    "route_mismatch": route_mismatch,
    "industry_context": industry_context,
    "metadata": {
        "trace_id": trace_id,
        "route_decision_id": route_decision_id,
        "raw_payload_ref": raw_payload_ref,
        "source_event": "agent:end",
    },
}
```

Hermes-layer changes should map backend clarification output to `AgentResult.status == "needs_clarification"` plus `RunInterrupt`, but must keep Hermes as backend logic only. Use `raw_payload_ref` generation (lines 287-294) when source refs are missing.

## Shared Patterns

### Naming and IDs
**Sources:** `active_task_router.py` lines 186-187, `task_flow.py` lines 183-194, `normalization.py` lines 205-207

Use stable hash IDs with readable prefixes: `session-decision-*`, `session-*`, `interrupt-*`, `run-event-*`. Hash text for audit (`text_sha256_16`) and include length; never serialize raw legal text in decisions.

### State Mapping
**Sources:** `enums.py` lines 6-15, 73-79, 199-203; `task_flow.py` lines 49-60

Map backend clarification to:
- `AgentResult.status`: `needs_clarification`
- `AsyncTaskState`: `waiting_for_user`
- `RunInterrupt.status`: `waiting_for_user`

Terminal sessions/tasks must not be resumed after `succeeded`, `failed`, `cancelled`, `expired`, or timeout-derived failure.

### Privacy Checks
**Sources:** `store.py` lines 108-137; `test_active_task_router.py` lines 88-102; `test_task_flow.py` lines 86-98

Every session decision and interrupt record needs `raw_payload_ref` or `source_refs`, plus hashes/lengths for user text. Tests should `json.dumps(..., ensure_ascii=False)` and assert sensitive Chinese fixture phrases are absent.

### Service Boundary
**Sources:** `task_flow.py` lines 1-19 and 209-216; `output_policy.py` lines 21-51

WeCom ingress/egress stays InkStatute-owned. Hermes gateway/meta/system/update/command/help/debug text must not appear in clarification/resume notices. User-visible clarification should be ordinary assistant output, not `/resume` or backend terminology.

### Test Style
**Sources:** `test_active_task_router.py` lines 13-112; `test_task_flow.py` lines 20-116; `test_platform_foundation_contracts.py` lines 29-80

Use `unittest`, deterministic timestamps, small helper fixtures, direct assertions on enum/string states, and negative privacy assertions. Contract tests should validate schemas and relationship chains, then mutate one field to prove failure behavior.

### Runtime Fakes
**Source:** `packages/platform-runtime/src/platform_runtime/fakes.py` lines 29-53, 55-83, 107-144, 209-230

Add fake resolver/interrupt dependencies with deterministic `FakeIdFactory` and `FakeRuntimeClock`. Store submitted requests/events in lists or dicts for direct assertions.

## No Analog Found

None. Phase 15 has close analogs for schemas, dataclasses, state machines, privacy-safe logs, WeCom control-plane routing, backend mapping, and fixture tests.

## Metadata

**Analog search scope:** `packages/platform-contract/src/platform_contract/**`, `packages/platform-runtime/src/**`, `services/wecom-service/src/**`, `services/wecom-service/tests/**`, `services/hermes-contract-layer/src/**`, `services/hermes-contract-layer/tests/**`, `packages/contract-test-suite/src/**`, `packages/contract-test-suite/tests/**`
**Files scanned:** 55 listed files plus phase artifacts
**Pattern extraction date:** 2026-07-01
