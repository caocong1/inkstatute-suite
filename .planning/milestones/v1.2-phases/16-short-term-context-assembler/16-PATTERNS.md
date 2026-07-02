# Phase 16: Short-Term Context Assembler - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 7
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/platform-runtime/src/platform_runtime/context_assembler.py` | service/utility | transform | `packages/platform-runtime/src/platform_runtime/session_resolver.py` | exact |
| `packages/platform-runtime/src/platform_runtime/runtime.py` | service | request-response | `packages/platform-runtime/src/platform_runtime/runtime.py` | exact |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | config | request-response | `packages/platform-runtime/src/platform_runtime/feature_flags.py` | exact |
| `packages/platform-runtime/src/platform_runtime/__init__.py` | config | transform | `packages/platform-runtime/src/platform_runtime/__init__.py` | exact |
| `packages/platform-runtime/tests/test_context_assembler.py` | test | transform | `packages/platform-runtime/tests/test_session_resolution.py` | exact |
| `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` | test | request-response | `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` | exact |
| `packages/contract-test-suite/tests/test_phase16_short_term_context_assembler.py` + fixture | test/fixture | transform | `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py` + `fixtures/phase15_session_interrupt_runtime.json` | role-match |

## Pattern Assignments

### `packages/platform-runtime/src/platform_runtime/context_assembler.py` (service/utility, transform)

**Analog:** `packages/platform-runtime/src/platform_runtime/session_resolver.py`

**Imports pattern** (lines 3-17):
```python
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
from .store import ContractLogPrivacyError
```

Copy this style: stdlib-only runtime module, frozen dataclasses, `JsonObject`, injected `ContractLogStore`, and no Hermes/WeCom/backend imports.

**Dataclass/event serialization pattern** (lines 111-162):
```python
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
            "metadata": _safe_metadata({"privacy": "no_raw_payload_or_legal_text_stored", **self.metadata}),
            "privacy": "no_raw_payload_or_legal_text_stored",
        }
        optional = {"run_id": self.run_id, "interrupt_id": self.interrupt_id, "task_id": self.task_id}
        event.update({key: value for key, value in optional.items() if value is not None})
        _reject_forbidden_payload_storage(event)
        return event
```

Apply to `ContextAssemblyResult.as_event()` or equivalent: construct a `ContextBundle`-compatible mapping, include refs/hashes/lengths only, omit `None` optionals, and run the privacy guard before returning.

**Copy-safe in-memory store pattern** (lines 165-210):
```python
class InMemorySessionResolutionStore:
    """Copy-safe scoped support store for embedded hosts and tests."""

    def __init__(self, *, clock: Any | None = None) -> None:
        self._clock = clock
        self._sessions: dict[tuple[str, ...], SessionSnapshot] = {}
        self._pending_interrupts: dict[tuple[str, ...], PendingInterruptSnapshot] = {}
        self._active_tasks: dict[tuple[str, ...], ActiveTaskSnapshot] = {}
        self._decision_events: list[JsonObject] = []

    def get_session(self, scope: SessionScope) -> SessionSnapshot | None:
        snapshot = self._sessions.get(_scope_key(scope))
        return _copy_session(snapshot) if snapshot is not None else None

    def record_decision(self, decision: SessionResolutionDecision, *, contract_log_store: ContractLogStore | None = None) -> JsonObject:
        event = decision.as_event()
        if contract_log_store is not None:
            contract_log_store.append("session_resolution", event)
        stored = _json_clone(event)
        self._decision_events.append(stored)
        return _json_clone(stored)
```

Use for `InMemoryRollingSummaryStore`: key by `SessionScope`, copy records on write/read, optionally append a `context_bundle` event to `ContractLogStore`.

**Core transform pattern** (lines 237-373):
```python
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
```

Follow this function shape for `ContextAssembler.assemble(...)`: policy default, deterministic `now`, hash/length from current turn content, safe metadata, pure branch/trim decisions from inputs.

**Privacy/helpers pattern** (lines 522-608):
```python
def _safe_metadata(value: Mapping[str, Any]) -> JsonObject:
    _reject_forbidden_payload_storage(value)
    return _json_clone(value)

def _reject_forbidden_payload_storage(event: Mapping[str, Any]) -> None:
    for path, key in _walk_keys(event):
        if key == "raw_payload":
            raise ContractLogPrivacyError(f"contract log event contains forbidden raw_payload at {path}")
        if key in _FORBIDDEN_FULL_TEXT_KEYS:
            raise ContractLogPrivacyError(f"contract log event contains forbidden full-text payload field at {path}")

def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))

def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
```

Reuse or import existing privacy helpers where feasible; do not introduce a second forbidden-key definition unless implementation constraints force it.

---

### `packages/platform-runtime/src/platform_runtime/runtime.py` (service, request-response)

**Analog:** `packages/platform-runtime/src/platform_runtime/runtime.py`

**Constructor dependency injection pattern** (lines 27-47):
```python
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
) -> None:
    self.backend = backend
    self.channels = tuple(channels)
    self.feature_flags = feature_flags or RuntimeFeatureFlags()
    self.contract_log_store = contract_log_store
    self.output_boundary = output_boundary or DefaultAssistantOutputBoundary()
    self.clock = clock or _SystemRuntimeClock()
    self.id_factory = id_factory or _SequentialIdFactory()
    self.interrupt_store = interrupt_store
```

Add `context_assembler`/stores as optional injected dependencies. Keep runtime embeddable and avoid creating services, DBs, queues, or network dependencies.

**Feature flag and additive metadata pattern** (lines 49-64, 90-103):
```python
async def create_run(self, req: RunRequest) -> Run:
    self.feature_flags.require_enabled("run_runtime_enabled")
    self._require_contract_log_store_if_enabled()
    handle = await self.backend.submit_run(req)
    if self.feature_flags.contract_log_enabled:
        self._append_run_record(req, handle.run_id, handle.status, handle.backend_run_id)
        self._append_state_event(..., metadata={"source": "runtime_create"})
```

```python
resume_metadata = {
    **req.metadata,
    "source": "runtime_resume_interrupt",
    "interrupt_id": interrupt.event.interrupt_id,
    "resume_state_ref": interrupt.event.resume_state_ref,
    "answer_text_sha256_16": _sha256_16(answer),
    "answer_text_length": len(answer),
    "privacy": "no_raw_answer_text_stored",
}
resume_req = replace(req, metadata=resume_metadata)
```

Wire context assembly behind `context_assembly_enabled`. Use `dataclasses.replace(req, metadata={**req.metadata, "context_bundle": ...})` before `backend.submit_run`; do not mutate callers' request objects.

**Contract log append pattern** (lines 232-277):
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

If context assembly records a contract event, append `context_bundle` with schema-compatible fields and reference-first metadata.

---

### `packages/platform-runtime/src/platform_runtime/feature_flags.py` (config, request-response)

**Analog:** `packages/platform-runtime/src/platform_runtime/feature_flags.py`

**Default-off config pattern** (lines 12-25):
```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")
```

Add `context_assembly_enabled: bool = False`. Tests should assert default-off behavior and unknown flag protection remains intact.

---

### `packages/platform-runtime/src/platform_runtime/__init__.py` (config, transform)

**Analog:** `packages/platform-runtime/src/platform_runtime/__init__.py`

**Export pattern** (lines 35-56, 58-114):
```python
from .feature_flags import RuntimeFeatureDisabledError, RuntimeFeatureFlags
from .runtime import DefaultRunRuntime, RunRuntimeStateError
from .session_resolver import (
    ActiveTaskSnapshot,
    InMemorySessionResolutionStore,
    PendingInterruptSnapshot,
    SessionResolutionAction,
    SessionResolutionDecision,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
    resolve_session_turn,
)

__all__ = [
    "ActiveTaskSnapshot",
    "DefaultRunRuntime",
    "InMemorySessionResolutionStore",
    "RuntimeFeatureFlags",
    "SessionScope",
    "resolve_session_turn",
]
```

Export new public runtime surface: `ContextAssembler`, `ContextAssemblyPolicy`, `ContextAssemblyInput`, `ContextAssemblyResult`, `RollingSummaryRecord`, `InMemoryRollingSummaryStore`.

---

### `packages/platform-runtime/tests/test_context_assembler.py` (test, transform)

**Analog:** `packages/platform-runtime/tests/test_session_resolution.py`

**Test import/helper pattern** (lines 1-19, 22-51):
```python
from __future__ import annotations

from dataclasses import replace
import unittest

from platform_runtime import (
    ActiveTaskSnapshot,
    InMemoryContractLogStore,
    InMemorySessionResolutionStore,
    PendingInterruptSnapshot,
    SessionResolutionAction,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
    resolve_session_turn,
)

FIXED_NOW = "2026-07-01T08:00:00Z"

def make_scope(...) -> SessionScope:
    return SessionScope(...)
```

Use a fixed timestamp, helper factories for `SessionScope`, current `AgentTurn`, summaries, recent turn refs, artifacts, feedback refs, and active/pending snapshots.

**Behavior assertions pattern** (lines 152-172, 195-224):
```python
def test_serialized_decision_is_reference_first_and_excludes_input_text(self) -> None:
    text = "客户说合同里有很长的具体事实，不应该进入决策记录。"
    decision = resolve_session_turn(...)
    event = decision.as_event()

    self.assertEqual(event["text_length"], len(text))
    self.assertRegex(event["text_sha256_16"], r"^[0-9a-f]{16}$")
    self.assertEqual(event["raw_payload_ref"], "fixture://payloads/turn-privacy")
    self.assertNotIn("text", event)
    self.assertNotIn(text, repr(event))
```

```python
returned = store.get_session(scope)
returned.metadata["safe_ref"] = "mutated"
self.assertEqual(store.get_session(scope).metadata["safe_ref"], "fixture://sessions/1")
```

Assert deterministic budget trimming, never-droppable `current_turn_ref`/pending clarification/output policy refs, copy-safe store reads, and no raw text in serialized results.

**Privacy rejection pattern** (lines 244-274):
```python
with self.assertRaisesRegex(ValueError, "forbidden raw_payload"):
    store.upsert_session(make_session(scope=scope, metadata={"raw_payload": "secret"}))

unsafe_decision = replace(decision, metadata={"full_text": "secret"})

with self.assertRaisesRegex(ValueError, "full-text payload"):
    store.record_decision(unsafe_decision)
```

Mirror this for `RollingSummaryRecord` and `ContextAssemblyInput.metadata`/result metadata forbidden keys.

---

### `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` (test, request-response)

**Analog:** `packages/platform-runtime/tests/test_run_runtime_lifecycle.py`

**Fake runtime setup pattern** (lines 105-138):
```python
clock = FakeRuntimeClock(start=FIXED_NOW)
id_factory = FakeIdFactory()
backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
store = InMemoryContractLogStore(clock=clock.now)
runtime = DefaultRunRuntime(
    backend=backend,
    channels=(),
    feature_flags=RuntimeFeatureFlags(
        run_runtime_enabled=True,
        contract_log_enabled=True,
    ),
    contract_log_store=store,
    clock=clock,
    id_factory=id_factory,
)

run = await runtime.create_run(make_run_request())
entries = store.entries()

self.assertEqual(len(backend.submitted_requests), 1)
self.assertEqual([entry.event_key for entry in entries], ["run", "run_event"])
self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in entries]))
```

Add lifecycle tests that enable `context_assembly_enabled`, inject a deterministic assembler/store, assert backend receives metadata with `context_bundle_id`/refs, and assert contract log entries remain reference-first.

**Default-off/no backend call pattern** (lines 93-103):
```python
with self.assertRaisesRegex(
    RuntimeFeatureDisabledError,
    "runtime feature flag disabled: run_runtime_enabled",
):
    await runtime.create_run(make_run_request())

self.assertEqual(backend.submitted_requests, [])
```

Add a test that context assembly does not run unless `context_assembly_enabled=True`.

---

### `packages/contract-test-suite/tests/test_phase16_short_term_context_assembler.py` and fixture (test/fixture, transform)

**Analog:** `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py`

**Fixture loading/schema validation pattern** (lines 1-14, 41-49):
```python
from __future__ import annotations

import json
import hashlib
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle

PHASE15_FIXTURE = LOCAL_FIXTURE_ROOT / "phase15_session_interrupt_runtime.json"

class Phase15SessionInterruptRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE15_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase15-session-interrupt-runtime-001")
        validate_event_bundle(self.fixture, self.schemas)
```

Create `phase16_short_term_context_assembler.json`; validate it with existing schemas and assert fixture id.

**Privacy and forbidden text scan pattern** (lines 102-119, 148-166):
```python
text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
self.assertIn("raw_payload_ref", text)
self.assertIn("fixture://", text)

for object_path, value in iter_mapping_values(self.fixture):
    with self.subTest(path=object_path):
        self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

for text_path, value in iter_string_values(self.fixture):
    with self.subTest(path=text_path):
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")
```

Reuse this privacy scan for the Phase 16 fixture, especially against summary/turn/user-message raw text.

**Hash/length evidence pattern** (lines 121-136):
```python
content = events["agent_turn"]["content"]
expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
expected_length = len(content.encode("utf-8"))

self.assertEqual(events["agent_turn"]["metadata"]["content_sha256_16"], expected_hash)
self.assertEqual(events["agent_turn"]["metadata"]["content_length"], expected_length)
branch = self.fixture["metadata"]["branch_evidence"]["pending_interrupt_resume"]
self.assertEqual(branch["text_sha256_16"], expected_hash)
self.assertEqual(branch["text_length"], expected_length)
```

For Phase 16, assert `context_bundle.metadata.current_turn_sha256_16`/length and fixture branch evidence match the synthetic current turn.

**Fixture structure pattern** (`packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json`, lines 1-39, 69-89, 217-256):
```json
{
  "fixture_id": "phase15-session-interrupt-runtime-001",
  "description": "Sanitized evidence for Phase 15 session resolution and interrupt resume behavior.",
  "metadata": {
    "phase": "15",
    "requirements": ["CTX-01", "CTX-02", "CTX-03", "CTX-04"],
    "privacy": "refs_hashes_lengths_statuses_only",
    "branch_evidence": {
      "pending_interrupt_resume": {
        "decision_action": "resume_interrupt",
        "raw_payload_ref": "fixture://phase15/payloads/turn-answer-001",
        "text_sha256_16": "0a91875b1a12f139",
        "text_length": 33
      }
    }
  },
  "events": {
    "agent_turn": {
      "turn_id": "turn-phase15-answer-001",
      "metadata": {
        "raw_payload_ref": "fixture://phase15/payloads/turn-answer-001",
        "content_sha256_16": "0a91875b1a12f139",
        "content_length": 33
      }
    },
    "run": {
      "metadata": {
        "raw_payload_ref": "fixture://phase15/payloads/turn-answer-001",
        "content_sha256_16": "0a91875b1a12f139",
        "content_length": 33,
        "privacy": "no_raw_payload_or_answer_text_stored"
      }
    }
  }
}
```

Phase 16 fixture should add `events.context_bundle` and evidence for STM-01..STM-04: bounded refs, budget/trim strategy, summary ref, pending interrupt ref, output constraints ref, and no raw summary or legal payload text.

## Shared Patterns

### Reference-First Privacy
**Source:** `packages/platform-runtime/src/platform_runtime/store.py` lines 42-61, 104-137  
**Apply to:** `context_assembler.py`, runtime metadata append, unit tests, contract fixture
```python
def append(self, event_key: str, event: Mapping[str, Any], *, occurred_at: str | None = None, ingested_at: str | None = None) -> ContractLogEntry:
    _reject_forbidden_payload_storage(event)
    now = _timestamp(_clock_now(self._clock))
    stored = ContractLogEntry(..., event=_json_clone(event))
    self._entries.append(stored)
    self._next_seq += 1
    return _copy_entry(stored)

def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
```

### Runtime Protocol Dataclasses
**Source:** `packages/platform-runtime/src/platform_runtime/protocols.py` lines 107-117, 157-163  
**Apply to:** assembler input/result dataclasses and runtime integration
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

@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    uri_ref: str
    name: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

### ContextBundle Contract Shape
**Source:** `packages/platform-contract/src/platform_contract/events.py` lines 517-536  
**Apply to:** `ContextAssemblyResult.bundle` and Phase 16 fixture
```python
@dataclass(frozen=True, slots=True)
class ContextBundle:
    context_bundle_id: str
    tenant_id: str
    workspace_id: str
    session_id: str
    created_at: str
    budget_tokens: int
    run_id: str | None = None
    turn_id: str | None = None
    recent_turn_refs: list[str] = field(default_factory=list)
    summary_ref: str | None = None
    active_task_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)
    interrupt_id: str | None = None
    trim_strategy: str | None = None
    raw_payload_refs: list[str] = field(default_factory=list)
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

### Deterministic IDs, Time, Hashes
**Source:** `packages/platform-runtime/src/platform_runtime/runtime.py` lines 364-391 and `session_resolver.py` lines 553-598  
**Apply to:** assembler budget events, tests, fixtures
```python
class _SequentialIdFactory:
    def new_id(self, prefix: str) -> str:
        next_value = self._next_by_prefix.get(prefix, 1)
        self._next_by_prefix[prefix] = next_value + 1
        return f"{prefix}-{next_value:06d}"

def _sha256_16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
```

### Contract-Suite Fixture Gate
**Source:** `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py` lines 47-49, 102-119  
**Apply to:** Phase 16 contract-suite test
```python
def test_fixture_validates_with_existing_bundle_validator(self) -> None:
    self.assertEqual(self.fixture["fixture_id"], "phase15-session-interrupt-runtime-001")
    validate_event_bundle(self.fixture, self.schemas)

def test_fixture_is_reference_first_and_has_no_user_session_command_requirement(self) -> None:
    text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
    self.assertIn("raw_payload_ref", text)
    for object_path, value in iter_mapping_values(self.fixture):
        self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())
```

## No Analog Found

None. Every planned file has a same-role or same-package analog.

## Metadata

**Analog search scope:** `packages/platform-runtime`, `packages/contract-test-suite`, `packages/platform-contract`  
**Files scanned:** 79 paths from `rg --files`; targeted `rg` over runtime/contract keywords  
**Pattern extraction date:** 2026-07-01
