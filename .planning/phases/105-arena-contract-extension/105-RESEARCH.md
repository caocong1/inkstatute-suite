# Phase 105: Arena Contract Extension - Research

**Researched:** 2026-08-08
**Domain:** Event contract / Schema definition / Protocol design
**Confidence:** HIGH

## Summary

Phase 105 extends the existing v3.0 unified event vocabulary with 8 Arena lifecycle event types, 4 Arena dataclasses, and 1 ArenaWorkflow Protocol — all following patterns that are already proven in the codebase. The existing 13-category unified event vocabulary (defined in Phase 88) established a rigorous four-layer contract: Python dataclass + JSON Schema + TypeScript interface + schema validation tests. Arena events must replicate this exact pattern to remain isomorphic with the existing vocabulary, as mandated by CONTRACT-01 and the phase goal ("与现有 13 类事件同构").

The research reveals that every piece of infrastructure needed for Phase 105 already exists: the `serialize_payload`/`deserialize_payload` round-trip harness in `unified_events.py`, the stdlib JSON Schema validator in `contract-test-suite/schema_validation.py`, the fixture replay engine in `fixture_replay.py`/`event_stream_replay.py`, the composability/industry-neutrality test framework in `test_unified_event_composability.py`, the Protocol-with-fakes pattern in `platform-runtime/protocols.py`+`fakes.py`, and the gate-coverage meta-test in `test_gate_coverage.py`. No new infrastructure needs to be built — only new contract artifacts following existing templates.

The one gap is cross-language round-trip testing (Python → JSON → TypeScript → JSON → Python lossless). The existing codebase tests Python-side round-trips (`serialize_payload` → `deserialize_payload`) and TS-side structural inspection (text-based assertions in `test_event_types.py`), but there is no automated harness that serializes a Python dataclass to JSON, parses it as a TypeScript interface shape, re-serializes, and parses back into Python. This harness must be created in Phase 105, but it can be built as a Python-side JSON-shape-conformance test that validates the JSON intermediate against the TS interface field signatures — no TypeScript runtime is needed (the existing TS tests are also stdlib-Python text-inspection, per `test_event_types.py`).

**Primary recommendation:** Replicate the exact four-layer pattern from `unified_events.py` + `schemas/` + `events.ts` + `test_event_schemas.py` for all 8 Arena events; define the 4 Arena dataclasses in a new `arena_contract.py` module in `platform-contract`; define `ArenaWorkflow` Protocol in `platform-runtime/protocols.py` with a `FakeArenaWorkflow` mock in `fakes.py`; add Arena events to the composability test's `NEW_EVENT_SCHEMA_NAMES` list and create Arena-specific fixture replay JSONL files.

## User Constraints

From `105-CONTEXT.md` [VERIFIED: codebase]:

- **Locked decisions:** All implementation choices are at the agent's discretion — discuss phase was skipped per `workflow.skip_discuss`. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.
- **Discretion areas:** All implementation choices.
- **Deferred ideas:** None.
- **Specific ideas:** None — refer to ROADMAP phase description and success criteria.

From `AGENTS.md` binding architecture decisions [VERIFIED: codebase]:

- Event vocabulary is **isomorphic to ACP `session/update`** — Arena events extend this vocabulary, they do not replace it.
- Legal-specific fields belong in `industry_context`; platform-level schemas must remain industry-neutral (verified by `solutions/demo_non_legal` composability tests).
- Every new `packages/*/src` and `services/*/src` directory must be covered by a gate.
- Add tests before or with behavior changes, especially for schemas, event mapping, ordering, dedupe, degradation, and fixture replay.
- Prefer structured parsers and schema validators over ad hoc string parsing.

From `REQUIREMENTS.md` [VERIFIED: codebase]:

- **CONTRACT-01**: Arena lifecycle events: `arena.workflow_started/completed`, `arena.score_recorded`, `arena.review_completed`, `arena.synthesis_started/completed`, `arena.adversarial_challenge_completed`, `arena.early_stop_triggered` (8 types total).
- **CONTRACT-02**: `ArenaWorkflowConfig` / `ArenaHandle` / `ArenaStatus` / `ArenaUserAction` Python dataclasses and TypeScript interfaces defined.
- **CONTRACT-03**: `ArenaWorkflow` Protocol defined in `platform-runtime`.
- **CONTRACT-04**: Arena events validated via JSON Schema, fixture replay, and composability tests.

## Standard Stack

All libraries/tools already used in `platform-contract` that Arena events must use [VERIFIED: codebase]:

| Layer | Tool/Pattern | Location |
|-------|-------------|----------|
| Python dataclasses | `@dataclass(frozen=True, slots=True)` from stdlib `dataclasses` | `unified_events.py` line 23+ |
| Python enums | `StrEnum` from stdlib `enum` | `enums.py` line 3 |
| JSON Schema | Draft 2020-12, hand-written `.schema.json` files | `schemas/` directory |
| Schema $ref | `common.schema.json#/$defs/...` for shared definitions | All schema files |
| TypeScript interfaces | Hand-written `.ts` file (NOT auto-generated) | `platform-sdk-ts/src/events.ts` |
| Schema validation | Stdlib-only Python validator (no `jsonschema` library) | `contract-test-suite/schema_validation.py` |
| Serialization | `dataclasses.asdict()` for serialize, custom `_dict_to_dataclass` for deserialize | `unified_events.py` lines 186-289 |
| Testing | `unittest` (NOT pytest) | All test files |
| Protocol definitions | `typing.Protocol` signature-only classes | `platform-runtime/protocols.py` |
| Mock implementations | `Fake*` classes in `fakes.py` | `platform-runtime/fakes.py` |
| Gate runner | `scripts/run_v2_gates.py` with `Gate` dataclass | `scripts/` |

**No new dependencies should be introduced.** The entire contract layer is stdlib-only Python + hand-written TypeScript + hand-written JSON Schema [VERIFIED: codebase].

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  packages/platform-contract/src/platform_contract/          │
│                                                             │
│  enums.py                                                   │
│    └── RunEventType (StrEnum)                               │
│        ├── 9 V2 values (state_changed, ...)                 │
│        ├── 14 V3 values (session.started, ...)              │
│        └── 8 NEW Arena values (arena.workflow_started, ...) │
│                                                             │
│  unified_events.py                                          │
│    ├── 15 existing payload dataclasses                      │
│    ├── 8 NEW Arena payload dataclasses                      │
│    ├── EVENT_TYPE_TO_PAYLOAD_CLASS (dict mapping)           │
│    ├── serialize_payload() → dict                           │
│    └── deserialize_payload() → dataclass                    │
│                                                             │
│  arena_contract.py (NEW)                                    │
│    ├── ArenaWorkflowConfig (frozen dataclass)               │
│    ├── ArenaHandle (frozen dataclass)                       │
│    ├── ArenaStatus (frozen dataclass)                       │
│    └── ArenaUserAction (frozen dataclass)                   │
│                                                             │
│  schemas/                                                   │
│    ├── common.schema.json ($defs: shared definitions)       │
│    ├── 15 existing event schemas                            │
│    └── 8 NEW arena_*.schema.json                            │
│                                                             │
│  __init__.py (re-exports all public symbols)                │
└─────────────────────────────────────────────────────────────┘
          ↕ (isomorphic contract)
┌─────────────────────────────────────────────────────────────┐
│  packages/platform-sdk-ts/src/                              │
│    events.ts                                                │
│    ├── 15 existing payload interfaces                       │
│    ├── 8 NEW Arena payload interfaces                       │
│    ├── 4 NEW Arena dataclass interfaces                     │
│    └── UnifiedEventPayload (union type, extended)           │
└─────────────────────────────────────────────────────────────┘
          ↕ (Protocol surface)
┌─────────────────────────────────────────────────────────────┐
│  packages/platform-runtime/src/platform_runtime/            │
│    protocols.py                                             │
│    ├── BackendAdapter, ChannelAdapter, RunRuntime (existing)│
│    └── ArenaWorkflow (NEW Protocol)                         │
│    fakes.py                                                 │
│    └── FakeArenaWorkflow (NEW mock)                         │
└─────────────────────────────────────────────────────────────┘
          ↕ (test validation)
┌─────────────────────────────────────────────────────────────┐
│  packages/contract-test-suite/                              │
│    tests/test_unified_event_composability.py (extended)     │
│    tests/test_arena_contract.py (NEW)                       │
│    fixtures/arena_*.jsonl (NEW fixture replay files)        │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

Arena contract artifacts go into **existing** packages — no new `packages/*/src` directories are created in Phase 105 [VERIFIED: codebase, VERIFIED: success criteria]:

```
packages/platform-contract/src/platform_contract/
├── enums.py                    # ADD 8 ArenaEventType enum values
├── unified_events.py           # ADD 8 Arena payload dataclasses + mapping
├── arena_contract.py           # NEW: 4 Arena dataclasses (Config/Handle/Status/UserAction)
├── __init__.py                 # ADD re-exports for all new symbols
└── schemas/
    ├── common.schema.json      # ADD arena_event_type enum to $defs
    ├── arena_workflow_started.schema.json      # NEW
    ├── arena_workflow_completed.schema.json    # NEW
    ├── arena_score_recorded.schema.json        # NEW
    ├── arena_review_completed.schema.json      # NEW
    ├── arena_synthesis_started.schema.json     # NEW
    ├── arena_synthesis_completed.schema.json   # NEW
    ├── arena_adversarial_challenge_completed.schema.json  # NEW
    └── arena_early_stop_triggered.schema.json  # NEW

packages/platform-sdk-ts/src/
└── events.ts                   # ADD 8 Arena payload interfaces + 4 dataclass interfaces

packages/platform-runtime/src/platform_runtime/
├── protocols.py                # ADD ArenaWorkflow Protocol
├── fakes.py                    # ADD FakeArenaWorkflow mock
└── __init__.py                 # ADD re-exports

packages/platform-contract/tests/
├── test_event_schemas.py       # EXTEND: add Arena schemas to NEW_SCHEMAS list
├── test_unified_events.py      # EXTEND: add Arena round-trip tests
└── test_arena_contract.py      # NEW: Arena dataclass + cross-language round-trip tests

packages/contract-test-suite/
├── tests/test_unified_event_composability.py  # EXTEND: add Arena schemas to list
└── fixtures/arena_event_stream.jsonl          # NEW: fixture replay file
```

### Pattern 1: Event Definition Pattern (THE pattern to replicate)

Each unified event type has exactly four artifacts that must stay in sync [VERIFIED: codebase]:

**1. Enum value in `enums.py`:**
```python
class RunEventType(StrEnum):
    # ... existing values ...
    ARENA_WORKFLOW_STARTED = "arena.workflow_started"
    ARENA_WORKFLOW_COMPLETED = "arena.workflow_completed"
    ARENA_SCORE_RECORDED = "arena.score_recorded"
    ARENA_REVIEW_COMPLETED = "arena.review_completed"
    ARENA_SYNTHESIS_STARTED = "arena.synthesis_started"
    ARENA_SYNTHESIS_COMPLETED = "arena.synthesis_completed"
    ARENA_ADVERSARIAL_CHALLENGE_COMPLETED = "arena.adversarial_challenge_completed"
    ARENA_EARLY_STOP_TRIGGERED = "arena.early_stop_triggered"
```

**2. Python dataclass in `unified_events.py`:**
```python
@dataclass(frozen=True, slots=True)
class ArenaWorkflowStartedPayload:
    arena_id: str
    mode: str  # "standard" | "self_score" | "arena_review" | "adversarial"
    agent_slots: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```
Plus entry in `EVENT_TYPE_TO_PAYLOAD_CLASS` dict and registration in `_NESTED_TYPE_MAP` if nested dataclasses are used.

**3. JSON Schema in `schemas/arena_*.schema.json`:**
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://inkstatute.dev/schemas/platform-contract/arena_workflow_started.schema.json",
  "title": "ArenaWorkflowStartedPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_type", "arena_id", "mode"],
  "properties": {
    "event_type": {"type": "string", "const": "arena.workflow_started"},
    "arena_id": {"type": "string"},
    "mode": {"type": "string", "enum": ["standard", "self_score", "arena_review", "adversarial"]},
    "agent_slots": {"type": "array", "items": {"type": "string"}},
    "metadata": {"$ref": "common.schema.json#/$defs/metadata"}
  }
}
```

**4. TypeScript interface in `events.ts`:**
```typescript
export interface ArenaWorkflowStartedPayload {
  arena_id: string;
  mode: "standard" | "self_score" | "arena_review" | "adversarial";
  agent_slots?: string[];
  metadata?: Record<string, unknown>;
}
```
Plus entry in the `UnifiedEventPayload` union type.

### Pattern 2: Protocol Definition Pattern

Protocols in `platform-runtime/protocols.py` are signature-only `typing.Protocol` classes with `@dataclass(frozen=True, slots=True)` data shapes [VERIFIED: codebase, `protocols.py` lines 209-275]:

```python
class ArenaWorkflow(Protocol):
    def arena_id(self) -> str: ...

    async def start(self, config: ArenaWorkflowConfig) -> ArenaHandle: ...

    async def cancel(self, arena_id: str) -> ArenaHandle: ...

    async def submit_user_action(self, arena_id: str, action: ArenaUserAction) -> ArenaHandle: ...

    async def query_status(self, arena_id: str) -> ArenaStatus: ...
```

Mock implementation in `fakes.py` follows the `FakeBackendAdapter` pattern [VERIFIED: codebase, `fakes.py` lines 56-255]:
- Deterministic `FakeIdFactory` for IDs
- Deterministic `FakeRuntimeClock` for timestamps
- In-memory state dicts (`self.arenas`, `self.events`)
- Records all submitted actions for assertion

### Pattern 3: Schema Validation Test Pattern

Tests in `test_event_schemas.py` follow this structure [VERIFIED: codebase]:
- `NEW_SCHEMAS` list — add Arena schema names here
- `SchemaFileExistenceTests` — verify files load and have `properties`
- `SchemaStructureTests` — verify `additionalProperties: false`, no forbidden top-level fields, references to `common.schema.json`, correct `$id`, `event_type` const
- `FORBIDDEN_TOP_LEVEL` set — already defined, Arena schemas must not add legal fields

### Pattern 4: Composability Test Pattern

`test_unified_event_composability.py` has a `NEW_EVENT_SCHEMA_NAMES` list [VERIFIED: codebase, line 27-43]. Arena schema names must be added to this list so they automatically get:
- No forbidden top-level fields check
- No forbidden required fields check
- `industry_context` not in required check
- `additionalProperties: false` check
- Non-legal fixture validation

### Pattern 5: Fixture Replay Pattern

Fixture replay uses JSONL event streams [VERIFIED: codebase, `event_stream_replay.py`]:
- Each line is a JSON envelope: `{event_key, occurred_at, ingested_at, seq, event}`
- `seq` must be monotonically increasing and unique
- Events are schema-validated on load
- Relationship checks verify cross-event referential integrity
- `assert_event_stream_integrity()` with `max_breakage_rate=0.0` is the assertion pattern

### Anti-Patterns to Avoid

1. **Do NOT create a new `packages/arena-contract/` package** — Arena events go into the existing `platform-contract` package. The phase goal says "与现有 13 类事件同构" (isomorphic with existing 13 event categories), which means same package, same pattern [VERIFIED: codebase, VERIFIED: success criteria].

2. **Do NOT use `pytest`** — all tests in this codebase use `unittest` (`python -m unittest discover`) [VERIFIED: codebase, all test files].

3. **Do NOT use the `jsonschema` library** — the codebase has a custom stdlib-only validator in `schema_validation.py` that handles `$ref`, `oneOf`, `enum`, `additionalProperties`, `required`, and `format: date-time` [VERIFIED: codebase, `schema_validation.py`].

4. **Do NOT auto-generate TypeScript** — `events.ts` is explicitly hand-written ("Hand-written — not auto-generated" per line 1 of `events.ts`). The `index.ts` is auto-generated but `events.ts` is not [VERIFIED: codebase].

5. **Do NOT add legal-specific fields to Arena event top-level `required`** — all legal-specific data goes in `metadata.industry_context`. The composability test enforces this [VERIFIED: codebase, `test_unified_event_composability.py`].

6. **Do NOT introduce `industry_context` as a top-level required field** in Arena schemas — the composability test explicitly checks this is not present in `required` [VERIFIED: codebase, `test_unified_event_composability.py` lines 94-117].

7. **Do NOT create a new gate for Phase 105** — Arena events go into existing `platform-contract/src` and `platform-runtime/src`, both already covered by gates. No new `src` directories are created [VERIFIED: codebase, `run_v2_gates.py` lines 88-89, 266-268].

## Don't Hand-Roll

Reuse these existing infrastructure pieces [VERIFIED: codebase]:

| Need | Reuse This | Location |
|------|-----------|----------|
| Serialize dataclass → dict | `serialize_payload()` | `unified_events.py:186` |
| Deserialize dict → dataclass | `deserialize_payload()` | `unified_events.py:284` |
| Nested dataclass coercion | `_dict_to_dataclass()` + `_coerce_field()` | `unified_events.py:191-238` |
| Forward-ref annotation resolution | `_resolve_annotation()` + `_NESTED_TYPE_MAP` | `unified_events.py:241-281` |
| JSON Schema validation | `_validate_schema()` + `load_schemas()` | `schema_validation.py:72,164` |
| Event bundle validation | `validate_event_bundle()` | `schema_validation.py:119` |
| Fixture replay | `replay_fixtures()` + `assert_relationship_integrity()` | `fixture_replay.py:64,104` |
| Event stream replay | `replay_event_streams()` + `assert_event_stream_integrity()` | `event_stream_replay.py:81,110` |
| Seq-based resume | `resume_from_seq()` + `sort_events_by_seq()` | `event_stream_replay.py:304,318` |
| Composability checks | `FORBIDDEN_TOP_LEVEL_FIELDS` + `assert_schema_required_fields_are_industry_neutral()` | `schema_validation.py:47`, `test_composability.py:113` |
| Protocol pattern | `typing.Protocol` + `@dataclass(frozen=True, slots=True)` | `protocols.py` |
| Fake/mock pattern | `FakeIdFactory` + `FakeRuntimeClock` + in-memory state | `fakes.py` |
| Gate coverage enforcement | `test_gate_coverage.py` meta-test | `contract-test-suite/tests/` |
| TS interface inspection | Text-based `assertIn` on `events.ts` source | `test_event_types.py` |

## Common Pitfalls

1. **Forgetting to update `EVENT_TYPE_TO_PAYLOAD_CLASS`** — if an Arena event type is added to the enum but not to this mapping dict, `deserialize_payload()` will raise `KeyError`. The test in `test_unified_events.py` `EventTypeToPayloadMappingTests` explicitly checks every V3 value is in the mapping [VERIFIED: codebase, `test_unified_events.py:94-120`].

2. **Forgetting to update `common.schema.json` `run_event_type` enum** — the `run_event_type` $def in `common.schema.json` lists all valid event type string values. Arena event types must be added here, or any schema that `$ref`s this enum will reject them [VERIFIED: codebase, `common.schema.json:110-137`].

3. **Forgetting to update the `UnifiedEventPayload` union type in `events.ts`** — the TS union type must include all Arena payload interfaces, or the TS SDK won't type them [VERIFIED: codebase, `events.ts:161-176`].

4. **Nested dataclass deserialization** — if Arena payloads contain nested dataclasses (e.g., a `ScoreBreakdown` inside `ArenaScoreRecordedPayload`), the nested type must be registered in `_NESTED_TYPE_MAP` in `unified_events.py` or deserialization will treat it as a plain dict [VERIFIED: codebase, `unified_events.py:241-247`].

5. **`additionalProperties: false` must be set on every Arena schema** — the composability test explicitly checks this for all schemas in the `NEW_EVENT_SCHEMA_NAMES` list [VERIFIED: codebase, `test_unified_event_composability.py:212-221`].

6. **`event_type` const must be set** — every event schema must have `properties.event_type.const` matching the event type string. The test `test_all_schemas_have_event_type_const` checks this [VERIFIED: codebase, `test_event_schemas.py:136-140`].

7. **Schema `$id` must match the pattern** — `https://inkstatute.dev/schemas/platform-contract/{name}.schema.json`. The test `test_all_schemas_have_correct_id` checks this [VERIFIED: codebase, `test_event_schemas.py:130-134`].

8. **Schema must reference `common.schema.json`** — the test `test_all_schemas_reference_common` checks that every schema file's raw text contains `"common.schema.json"` [VERIFIED: codebase, `test_event_schemas.py:120-128`].

9. **Gate count baseline** — `test_gate_count_meets_baseline` asserts `len(_gates()) >= 19`. Current count is 34 (per PROJECT.md). Phase 105 does NOT add gates, so this is not a concern, but the baseline must not drop [VERIFIED: codebase, `test_gate_coverage.py:58-60`].

10. **Cross-language round-trip has no existing harness** — the success criteria requires "Python → JSON → TypeScript → JSON → Python lossless" but no such test exists in the codebase. The existing tests are: (a) Python-only `serialize_payload` → `deserialize_payload` round-trips in `test_unified_events.py`, and (b) TS text-inspection in `test_event_types.py`. A new test must be created that validates JSON intermediate shape conformance against TS interface field signatures [VERIFIED: codebase].

## Code Examples

### Existing Event Payload Dataclass (the template to copy)

From `unified_events.py` [VERIFIED: codebase]:
```python
@dataclass(frozen=True, slots=True)
class SessionStartedPayload:
    backend_id: str
    capabilities: list[str] = field(default_factory=list)
    session_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

### Existing EVENT_TYPE_TO_PAYLOAD_CLASS mapping

From `unified_events.py` [VERIFIED: codebase]:
```python
EVENT_TYPE_TO_PAYLOAD_CLASS: dict[str, type] = {
    RunEventType.SESSION_STARTED.value: SessionStartedPayload,
    # ... 14 more entries ...
    RunEventType.ERROR.value: ErrorEventPayload,
}
```

### Existing serialize/deserialize round-trip test

From `test_unified_events.py` [VERIFIED: codebase]:
```python
def test_session_started_roundtrip(self) -> None:
    payload = SessionStartedPayload(
        backend_id="hermes",
        capabilities=["tool_use", "elicitation"],
        session_id="s1",
    )
    data = serialize_payload(payload)
    restored = deserialize_payload("session.started", data)
    self.assertEqual(restored.backend_id, "hermes")
    self.assertEqual(restored.capabilities, ["tool_use", "elicitation"])
    self.assertEqual(restored.session_id, "s1")
```

### Existing JSON Schema (the template to copy)

From `session_started.schema.json` [VERIFIED: codebase]:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://inkstatute.dev/schemas/platform-contract/session_started.schema.json",
  "title": "SessionStartedPayload",
  "description": "Payload for the session.started unified event (ACP session/new response).",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_type", "backend_id"],
  "properties": {
    "event_type": {"type": "string", "const": "session.started"},
    "backend_id": {"type": "string"},
    "capabilities": {"type": "array", "items": {"type": "string"}},
    "session_id": {"type": "string"},
    "metadata": {"$ref": "common.schema.json#/$defs/metadata"}
  }
}
```

### Existing TypeScript interface (the template to copy)

From `events.ts` [VERIFIED: codebase]:
```typescript
export interface SessionStartedPayload {
  backend_id: string;
  capabilities?: string[];
  session_id?: string;
  metadata?: Record<string, unknown>;
}
```

### Existing Protocol definition (the template to copy)

From `protocols.py` [VERIFIED: codebase]:
```python
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...
    def capabilities(self) -> AdapterCapabilitySet: ...
    async def bootstrap_check(self) -> BootstrapStatus: ...
    async def submit_run(self, req: RunRequest) -> RunHandle: ...
    async def get_run(self, run_id: str) -> Run: ...
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...
    async def cancel_run(self, run_id: str) -> Run: ...
    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...
    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...
```

### Existing Fake/mock pattern (the template to copy)

From `fakes.py` [VERIFIED: codebase]:
```python
class FakeBackendAdapter:
    def __init__(self, *, backend_id="fake-backend", clock=None, id_factory=None, ...):
        self._backend_id = backend_id
        self._clock = clock or FakeRuntimeClock()
        self._id_factory = id_factory or FakeIdFactory()
        self.submitted_requests: list[RunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}

    def backend_id(self) -> str:
        return self._backend_id

    async def submit_run(self, req: RunRequest) -> RunHandle:
        self.submitted_requests.append(req)
        run_id = self._id_factory.new_id("run")
        # ... deterministic state transitions ...
        return RunHandle(run_id=run_id, ...)
```

### Existing composability test list (to extend)

From `test_unified_event_composability.py` [VERIFIED: codebase]:
```python
NEW_EVENT_SCHEMA_NAMES = [
    "session_started",
    "message_delta",
    # ... 13 more ...
    "error_event",
]
# Arena schemas must be added here:
#   "arena_workflow_started",
#   "arena_workflow_completed",
#   ... etc.
```

### Existing fixture replay JSONL format

From `phase4_success_event_stream.jsonl` pattern [VERIFIED: codebase, `event_stream_replay.py`]:
```json
{"event_key": "agent_turn", "occurred_at": "2026-06-28T02:30:00Z", "ingested_at": "2026-06-28T02:30:01Z", "seq": 0, "event": {...}}
```
For Arena events, the `event_key` would be the Arena event type string (e.g., `"arena.workflow_started"`) and `event` would be the payload dict.

### Existing gate registration

From `run_v2_gates.py` [VERIFIED: codebase]:
```python
Gate(
    "platform-contract",
    (py, "-m", "unittest", "discover", "-s", "packages/platform-contract/tests"),
    (platform_src,),
),
```
Phase 105 does NOT need new gate entries — `platform-contract/src` and `platform-runtime/src` are already registered.

## Validation Architecture

### Required Tests for Phase 105

| Test | Location | What It Validates | Feedback Latency |
|------|----------|-------------------|-----------------|
| Arena schema file existence | `test_event_schemas.py` (extend `NEW_SCHEMAS`) | 8 schema files exist, load, have `properties` | <1s |
| Arena schema structure | `test_event_schemas.py` (auto-covered by extending list) | `additionalProperties: false`, `$id` correct, `event_type` const, references `common.schema.json` | <1s |
| Arena enum values | `test_unified_events.py` (extend `V3_MEMBERS`) | 8 Arena values exist in `RunEventType` | <1s |
| Arena payload mapping | `test_unified_events.py` (extend `V3_VALUES`) | All 8 Arena event types in `EVENT_TYPE_TO_PAYLOAD_CLASS` | <1s |
| Arena payload round-trip | `test_unified_events.py` (add 8 test methods) | `serialize_payload` → `deserialize_payload` lossless for each Arena type | <1s |
| Arena dataclass definition | `test_arena_contract.py` (NEW) | 4 dataclasses exist with correct fields | <1s |
| Arena dataclass round-trip | `test_arena_contract.py` (NEW) | Python → JSON → Python lossless for each dataclass | <1s |
| Cross-language round-trip | `test_arena_contract.py` (NEW) | Python → JSON shape conforms to TS interface signatures → JSON → Python lossless | <1s |
| Arena composability | `test_unified_event_composability.py` (extend list) | No forbidden top-level fields, no forbidden required, `additionalProperties: false`, industry-neutral | <1s |
| Arena fixture replay | `test_arena_contract.py` or `test_event_stream_replay.py` (NEW fixture) | Given event sequences, replay deterministic, no duplicates, no loss | <1s |
| Arena Protocol validation | `test_arena_contract.py` (NEW) | `FakeArenaWorkflow` passes `isinstance` Protocol check, all methods callable | <1s |
| demo_non_legal composability | `test_demo_non_legal_solution.py` (extend or verify) | Arena events don't introduce legal-specific fields in top-level required | <1s |

### Sampling Continuity

All tests run in the `platform-contract` gate and `contract-test-suite` gate, both of which are part of the 34-gate CI suite [VERIFIED: codebase, `run_v2_gates.py`]. Every gate run exercises every test — no sampling, no flaky tests, deterministic by design (all fakes use `FakeIdFactory` + `FakeRuntimeClock`).

### Nyquist Validation

The contract layer has the fastest possible feedback loop: pure Python dataclass instantiation + JSON serialization + stdlib schema validation. No network, no subprocess, no I/O. The feedback latency is <1s per test class. The "signal" being sampled is structural conformance (field names, types, required/optional, enum values) — this is a discrete signal with no analog noise, so the Nyquist criterion is trivially satisfied: every change to the contract is immediately tested.

## State of the Art

### Current Approach (v3.0, shipped)

The v3.0 platform-contract package defines 13 event categories (15 event types with sub-types) using a four-layer contract [VERIFIED: codebase]:
- **Python**: `RunEventType` StrEnum + `unified_events.py` payload dataclasses + `serialize_payload`/`deserialize_payload`
- **JSON Schema**: 15 `.schema.json` files in `schemas/` with `common.schema.json` shared definitions
- **TypeScript**: Hand-written interfaces in `events.ts` with `UnifiedEventPayload` union type
- **Tests**: `test_event_schemas.py` (schema structure) + `test_unified_events.py` (Python round-trip) + `test_unified_event_composability.py` (industry neutrality)

The v3.0 platform-runtime defines 4 Protocols (`ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, `RunRuntime`) with `Fake*` mock implementations [VERIFIED: codebase, `protocols.py`, `fakes.py`].

### What Arena Introduces

Phase 105 extends the existing vocabulary with 8 new event types (same four-layer pattern), 4 new dataclasses (new `arena_contract.py` module), and 1 new Protocol (`ArenaWorkflow`). No existing patterns are changed — only extended. The key novelty is the cross-language round-trip test, which doesn't exist for the 13 original event types but is required by the Phase 105 success criteria [VERIFIED: codebase, success criteria #2].

## Assumptions Log

1. **[ASSUMED]** Arena event types use the `arena.*` prefix (e.g., `arena.workflow_started`) as specified in CONTRACT-01. These will be added to the existing `RunEventType` enum rather than a new enum, because the existing `EVENT_TYPE_TO_PAYLOAD_CLASS` mapping and all test infrastructure keys off `RunEventType`.

2. **[ASSUMED]** The 4 Arena dataclasses (`ArenaWorkflowConfig`, `ArenaHandle`, `ArenaStatus`, `ArenaUserAction`) are NOT event payloads — they are configuration/state dataclasses used by the `ArenaWorkflow` Protocol. They go in a new `arena_contract.py` module, not in `unified_events.py`. This follows the pattern where `events.py` has dataclasses like `Run`, `RunHandle`, `Session` that are not event payloads but are contract data shapes.

3. **[ASSUMED]** The `ArenaWorkflow` Protocol has 4 methods: `start`, `cancel`, `submit_user_action`, `query_status` — matching the success criteria "启动/取消/用户动作/状态查询方法". The return types are `ArenaHandle` (for start/cancel/user_action) and `ArenaStatus` (for query_status), following the `BackendAdapter` pattern where `submit_run` returns `RunHandle` and `get_run` returns `Run`.

4. **[ASSUMED]** The cross-language round-trip test can be implemented as a Python-side test that: (a) serializes a Python dataclass to JSON dict, (b) validates the JSON dict's field names and types against the TS interface field signatures (parsed from `events.ts` text), (c) re-serializes the JSON dict, (d) deserializes back to Python dataclass, (e) asserts equality. No TypeScript runtime is needed — this matches the existing `test_event_types.py` approach which is stdlib-Python text-inspection of `events.ts`.

5. **[ASSUMED]** Arena event payloads will need an `arena_id` field (the Arena workflow identifier, analogous to `run_id` in `RunEvent`) and an `agent_slot` field where relevant (per SVC-03: "每个事件带 `metadata.agent_slot`"). The `agent_slot` goes in `metadata` per the existing pattern where `metadata` is the extensibility point.

6. **[ASSUMED]** The `mode` field in Arena events uses the 4 workflow modes defined in PROJECT.md: `standard` (Mode 1), `self_score` (Mode 2), `arena_review` (Mode 3), `adversarial` (Mode 4). These are the canonical names from the v3.1 milestone definition.

7. **[ASSUMED]** No new `packages/*/src` directory is created in Phase 105. All artifacts go into existing `platform-contract/src`, `platform-runtime/src`, and `platform-sdk-ts/src`. Therefore no new gate registration is needed. The gate-coverage meta-test will continue to pass without changes.

8. **[ASSUMED]** The `common.schema.json` `run_event_type` enum must be extended with the 8 Arena event type strings. This is required because the `run_event_type` $def is referenced by schemas that validate event type values.

## Open Questions

1. **Should Arena events have an `arena_id` field or reuse `run_id`?** The existing `RunEvent` uses `run_id`. Arena workflows may spawn multiple runs (one per agent slot). The success criteria and requirements don't specify. **Recommendation:** Use `arena_id` as the top-level identifier in Arena event payloads, with `run_id` and `agent_slot` in `metadata` for cross-referencing. This keeps Arena events self-describing without overloading `run_id`.

2. **Should the `ArenaWorkflow` Protocol include a `stream_events` method?** The success criteria says "启动/取消/用户动作/状态查询方法" (start/cancel/user-action/status-query) — 4 methods. Streaming is handled by the Arena Service (Phase 109), not the Protocol. **Recommendation:** Do NOT include `stream_events` in the Protocol for Phase 105; it will be added in Phase 109 when the service layer is built.

3. **Should Arena dataclasses have JSON Schemas?** The success criteria says "round-trip 序列化测试通过" but only mentions JSON Schema for the 8 event types (success criteria #1). **Recommendation:** Define JSON Schemas for the 4 dataclasses as well, since they are part of the contract and will be serialized over HTTP in Phase 109. This follows the pattern where `Run`, `Session`, etc. all have schemas in the `schemas/` directory.

4. **Should Arena events be added to the `EVENT_TYPE_TO_PHASE` mapping in `five_phase.py`?** Arena events are workflow-level events, not agent-run-phase events. **Recommendation:** Do NOT add Arena events to `EVENT_TYPE_TO_PHASE` — they exist at a different abstraction level (workflow orchestration, not agent turn phases). The five-phase mapping is for single-agent runs; Arena is multi-agent orchestration.

5. **Should the `demo_non_legal` composability test be extended with Arena-specific assertions?** The success criteria #4 says "`solutions/demo_non_legal` 不因 arena 事件引入法律专用字段到顶层 required". **Recommendation:** Add Arena schema names to the `NEW_EVENT_SCHEMA_NAMES` list in `test_unified_event_composability.py` — this automatically covers the "no legal fields in top-level required" check. Additionally, create an Arena-specific non-legal fixture (e.g., an engineering code-review arena) to verify Arena events work in non-legal domains.
