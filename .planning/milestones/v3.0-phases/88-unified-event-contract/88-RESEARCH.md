---
phase: 88
researcher: gsd-phase-researcher
date: 2026-08-07
status: complete
---

# Phase 88 Research: Unified Event Contract

## Executive Summary

Phase 88 establishes `packages/platform-contract` as the protocol foundation for the entire v3.0 milestone. The existing V2 codebase already has a `RunEvent` dataclass, a `run_event.schema.json`, a `RunEventType` enum with 9 values, and a `common.schema.json` with shared definitions. Phase 88 must **expand** the event vocabulary from 9 to 13 unified event types, **respecify** `RunEvent` as the carrier, add the elicitation/permission/citation/phase/plan contracts, define bot degradation rules as testable code, and do all of this without modifying V2's 5 persistence schemas or breaking the 28 gates.

The V3-PRD §3.2 provides the complete event table with ACP mappings and bot degradation behavior — this is the authoritative spec.

---

## 1. V2's 5 Persistence Schemas (MUST NOT MODIFY)

**Location:** `packages/platform-contract/src/platform_contract/schemas/`

| Schema | File | Python Binding | Key Fields |
|---|---|---|---|
| AgentTurn | `agent_turn.schema.json` | `AgentTurn` (events.py:126) | `turn_id`, `conversation_id`, `channel`, `user_id`, `message_type`, `received_at`, `content`, `attachments`, `output_constraints`, `industry_context` |
| AgentResult | `agent_result.schema.json` | `AgentResult` (events.py:141) | `result_id`, `turn_id`, `status`, `reply_type`, `content`, `artifacts`, `clarifying_questions`, `execution_trace`, `skill_candidate`, `error` |
| ExecutionTrace | `execution_trace.schema.json` | `ExecutionTrace` (events.py:184) | `trace_id`, `turn_id`, `started_at`, `ended_at`, `occurred_at`, `ingested_at`, `seq`, `steps`, `tool_calls`, `route_decision`, `gates` |
| FeedbackEvent | `feedback_event.schema.json` | `FeedbackEvent` (events.py:159) | `feedback_id`, `turn_id`, `source`, `event_type`, `status`, `rating`, `action`, `skill_candidate`, `raw_payload_ref` |
| RouteDecision | `route_decision.schema.json` | `RouteDecision` (events.py:207) | `route_decision_id`, `turn_id`, `primary_skill`, `confidence`, `mode`, `required_tools`, `matched_rule` |

**Constraint (EVT-06, SC#6):** No fields may be added, removed, or renamed in these 5 schemas. They remain as persistence/audit/replay/feedback contracts. The new unified event vocabulary is a **transport contract** that projects into these schemas.

**Shared definitions** in `common.schema.json`:
- `datetime` (ISO 8601 string)
- `metadata` (extensible object)
- `industry_context` (extensible object — legal-specific fields go here)
- `error_info` (category/code/message/stage/retryable/details)
- `artifact` (artifact_id/kind/name/uri/mime_type/template_ref/features/source_refs)
- `skill_candidate` (detected/source/proposed_name/risk_level/requires_human_review/evidence)

---

## 2. Existing 28 Gates

**Location:** `scripts/run_v2_gates.py`
**Coverage test:** `packages/contract-test-suite/tests/test_gate_coverage.py`

The 28 gates (confirmed via `python scripts/run_v2_gates.py --list`):

1. platform-contract
2. wecom-service
3. hermes-contract-layer
4. conversation-read-view
5. skill-registry
6. operator-config
7. router-service
8. mcp-registry
9. codex-backend
10. provider-model-backend
11. model-gateway
12. multi-agent-adapter
13. admin-console-api
14. admin-web-ui
15. lawyer-web-chat
16. rbac
17. rbac-annotation-scan
18. qqbot-channel
19. qqbot-service
20. web-sse-channel
21. wecom-channel
22. platform-sdk-ts
23. feedback-service
24. phase7-privacy-boundary
25. contract-test-suite
26. v2-acceptance-traceability
27. gate-coverage-meta-test
28. compileall

**Gate structure:** Each gate runs `python -m pytest` or `python -m compileall` against a specific package's `src/` directory with appropriate `PYTHONPATH`. The `gate-coverage-meta-test` enforces that every `packages/*/src` directory is covered by at least one gate.

**Constraint:** All 28 must remain green. New code in `packages/platform-contract/src` is already covered by gate #1. New test files in `packages/contract-test-suite/tests/` are covered by gate #25. The gate-coverage meta-test (gate #27) will catch any new `packages/*/src` directory that lacks a gate.

---

## 3. ASK-USER-PROTOCOL.md (FOUND)

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md`

**Key protocol fields:**
- `intro`: string — introductory text for the clarification batch
- `questions`: array of 2-4 question objects
  - `id`: string — question identifier
  - `question`: string — question text
  - `allow_multiple`: boolean (default false) — single-select vs multi-select
  - `options`: array of `{label: string, value: string}` objects
- Free-text: questions without `options` array (implied free-text)

**Answer format (host → model):**
- Single-select: `answer` is a single `value`
- Multi-select: `answer` is multiple `value`s joined by `|` (e.g. `lease|sale`)
- Display: Chinese labels joined by `、`

**Constraint for elicitation.requested event:** The event payload must carry `intro`, `questions[]` with `id`/`question`/`allow_multiple`/`options[]`, and be bidirectionally convertible with V2 `RunInterrupt` (`interrupt_id` → event's interrupt identifier, `resume_state_ref` → event's resume reference, `expected_response_schema_ref` → derived from questions schema).

---

## 4. V2 RunInterrupt Structure

**Location:** `packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json` + `events.py:540`

**Fields:**
- `interrupt_id`: string (required)
- `run_id`: string (required)
- `session_id`: string (required)
- `status`: enum `waiting_for_user` / `resolved` / `expired` / `cancelled` (required)
- `reason`: string (required)
- `created_at`: datetime (required)
- `prompt_ref`: string (required)
- `resume_state_ref`: string (required)
- `expected_response_schema_ref`: string (optional)
- `expires_at`: datetime (optional)
- `resolved_at`: datetime (optional)
- `resolved_turn_id`: string (optional)
- `metadata`: object (optional)

**Interconversion with `elicitation.requested`:**
- `interrupt_id` ↔ elicitation event's interrupt identifier
- `resume_state_ref` ↔ elicitation event's resume reference
- `expected_response_schema_ref` ↔ JSON Schema derived from questions (id/question/allow_multiple/options)
- `prompt_ref` ↔ reference to the `intro` + `questions` payload
- `reason` ↔ "clarification" or similar

---

## 5. ACP v1 session/update Event Structure

**Source:** V3-PRD §3.2 (authoritative event table) + agentclientprotocol.com

**13 ACP SessionUpdate variants → 13 unified events:**

| Unified Event | ACP Variant | Bot Degradation |
|---|---|---|
| `session.started` | `session/new` response | 静默 (silent) |
| `message.delta` | `agent_message_chunk` | 缓冲 (buffer) |
| `message.completed` | `agent_message` (v2) | 投递 (deliver) |
| `thought.delta` | `agent_thought_chunk` | 丢弃 (discard) |
| `tool_call.started` / `.delta` / `.completed` | `tool_call_update` | 折叠为业务化提示 (fold) |
| `plan.updated` | `plan` / `plan_update` | 首次投递"仍在处理"，后续静默 |
| `phase.changed` | `_meta` extension | 同 plan |
| `elicitation.requested` | `elicitation/create` | 投递为模板卡片 |
| `permission.requested` | `session/request_permission` | 投递为审批卡片 |
| `artifact.created` | Artifact content block | 投递为文件 |
| `citation.recorded` | `_meta` extension | 附在最终消息 |
| `run.state_changed` | status update | 失败时投递业务化提示 |
| `error` | JSON-RPC error | 投递业务化提示 |

**Isomorphism principle:** Platform is a thin relay — same shape in, same shape out. Only adds tenant/persistence/degradation.

**ACP ToolCall key fields:** `toolCallId`, `title`, `kind` (read/edit/delete/move/search/execute/think/fetch/other), `status` (pending/in_progress/completed/failed), `content`, `fileLocations`, `rawInput`, `rawOutput`.

---

## 6. Existing packages/ Directory Structure

**15 packages:**
- `platform-contract` — Core contract definitions (schemas, events, enums)
- `contract-test-suite` — Contract validation tests (39 test files)
- `channel-core` — Channel-generic logic (output_policy, delivery_guard, owned_notices)
- `platform-sdk-ts` — TypeScript SDK (auto-generated from OpenAPI)
- `backends/` — Backend adapters (hermes, codex, provider_model)
- `channels/` — Channel adapters (wecom, qqbot, web_sse)
- `platform-runtime` — Runtime orchestration
- `solution-loader` — Solution package loading
- `skill-registry` — Skill registry
- `router-service` — Routing service
- `mcp-registry` — MCP server registry
- `model-gateway` — Model gateway
- `multi-agent-adapter` — Multi-agent adapter
- `operator-config` — Operator configuration
- `rbac` — Role-based access control

**Also:** `solutions/lawfirm/` and `solutions/demo_non_legal/` for composability testing.

---

## 7. Current Event Infrastructure (V2 Baseline)

**`RunEventType` enum** (enums.py:100-109) — 9 values:
```
state_changed, step_started, step_completed, message_delta,
tool_call_started, tool_call_completed, approval_requested,
artifact_created, error
```

**`RunEvent` dataclass** (events.py:289-302):
```python
@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: str
    run_id: str
    event_type: RunEventType | str
    occurred_at: str
    seq: int
    status: AsyncTaskState | str | None = None
    step_id: str | None = None
    tool_call_id: str | None = None
    approval_id: str | None = None
    artifact_id: str | None = None
    message_delta: str | None = None
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)
```

**`run_event.schema.json`** — JSON Schema with `event_id`, `run_id`, `event_type` (ref to common), `status`, `step_id`, `tool_call_id`, `approval_id`, `artifact_id`, `message_delta`, `error`, `occurred_at`, `seq`, `metadata`.

**Gap analysis — V2 has 9 event types, V3 needs 13:**

| V3 Event | V2 Status | Action |
|---|---|---|
| `session.started` | Missing | Add |
| `message.delta` | Exists as `message_delta` | Rename/respecify |
| `message.completed` | Missing | Add |
| `thought.delta` | Missing | Add |
| `tool_call.started` | Exists as `tool_call_started` | Rename |
| `tool_call.delta` | Missing | Add |
| `tool_call.completed` | Exists as `tool_call_completed` | Rename |
| `plan.updated` | Missing | Add |
| `phase.changed` | Missing | Add |
| `elicitation.requested` | Partially: `approval_requested` | Add new (keep approval) |
| `permission.requested` | Partially: `approval_requested` | Add new (keep approval) |
| `artifact.created` | Exists as `artifact_created` | Rename |
| `citation.recorded` | Missing | Add |
| `run.state_changed` | Exists as `state_changed` | Rename |
| `error` | Exists | Keep |

**Note:** The V3-PRD says 13 event types. Counting the distinct types: session.started, message.delta, message.completed, thought.delta, tool_call.started/delta/completed (3 sub-types), plan.updated, phase.changed, elicitation.requested, permission.requested, artifact.created, citation.recorded, run.state_changed, error = 13 distinct event type names (with tool_call having 3 variants).

**`RunEvent` respecification (EVT-02):**
- Must add `ingested_at` field (currently only `occurred_at` exists in the schema; `ExecutionTrace` has both `occurred_at` and `ingested_at`)
- `event_type` enum must expand to the 13 unified types
- `payload` field needed for typed event data (or use discriminated union via `event_type`)
- `seq` must support replay: out-of-order replay + resume from any breakpoint without duplicates or loss

---

## 8. Bot Degradation Behavior Patterns

**Existing infrastructure:** `packages/channel-core/src/channel_core/`

**`output_policy.py`** — Classifies backend output before user delivery:
- Actions: `block`, `rewrite`, `allow`
- Reasons: `internal_or_secret_bearing_notice`, `backend_lifecycle_notice`, `business_output`
- Pattern: Regex-based classification with audit metadata (SHA256 hash, no original text stored)

**`delivery_guard.py`** — Detects incomplete file delivery:
- Returns `DeliveryCompletionAssessment` with `completed` boolean

**`owned_notices.py`** — Owned notice templates for backend lifecycle messages

**V3 degradation categories (from V3-PRD §3.2):**

| Category | Chinese | Events | Behavior |
|---|---|---|---|
| Silent | 静默 | session.started | Drop entirely |
| Buffer | 缓冲 | message.delta | Accumulate, deliver on message.completed |
| Deliver | 投递 | message.completed, elicitation.requested, permission.requested, artifact.created | Send as final message/card/file |
| Discard | 丢弃 | thought.delta | Drop (no business value for bots) |
| Fold | 折叠 | tool_call.started/delta/completed | Collapse to "正在检索法规…" business prompt |
| First-then-silent | 首次投递后静默 | plan.updated, phase.changed | First occurrence: "仍在处理", subsequent: silent |
| Attach | 附在最终消息 | citation.recorded | Append to final delivered message |
| On-failure | 失败时投递 | run.state_changed, error | Only deliver on failure, as business prompt |

**Implementation approach:** Declarative degradation rules — given a sequence of events, the aggregator produces deterministic final delivery content. Must be testable: input event sequence → expected output.

---

## 9. Industry Neutrality Constraints

**Location:** `packages/contract-test-suite/tests/test_composability.py`

**Tests:**
- `test_non_legal_event_top_levels_do_not_contain_forbidden_fields`
- `test_platform_required_fields_do_not_introduce_lawfirm_only_requirements`
- `test_mutated_non_legal_fixture_with_legal_top_level_field_fails`

**Forbidden top-level fields:** `jurisdiction`, `lawyer`, `legal`, `lawfirm`, `attorney`, `counsel`

**Rule:** Legal-specific fields must go in `industry_context` object, never at top level. New event schemas must be validated against this.

**Composability test fixture:** `solutions/demo_non_legal/` with `manifest.json` containing `output_policy` and `industry_context`.

---

## 10. TypeScript Binding Generation Pattern

**Location:** `packages/platform-sdk-ts/`

**Generator:** `scripts/generate_sdk.py` (297 lines) — auto-generates `src/index.ts`
**Output:** `src/index.ts` with SSE frame parsing (`parseSseFrame`), async iterable streaming, `PlatformApiClient` class, `PlatformApiError` error class

**Pattern:** Deterministic generation (sorting for byte-identical output), remote/thin SDK (no local runtime).

**Applicability:** The 13 unified event types need TypeScript interfaces. Can extend the existing generator or add a new event-specific generator. The SDK already has SSE frame parsing — event types just need TypeScript interface definitions.

---

## 11. Five-Phase Progress Contract (EVT-04)

**Five phases:** research → intake → retrieval → draft → review

**Mapping to UI concepts (from V3-PRD §3.1):**
- ACP `agent_thought_chunk` → thinking phase
- `tool_call_update` → tool phase
- `agent_message_chunk` → streaming phase
- review → review phase

**The `phase.changed` event carries the five-phase state.** The mapping table must document:
- Which events belong to which phase
- How phase transitions are signaled
- How the five phases map to thinking/tool/streaming/review UI concepts

**No existing five-phase implementation found in the codebase** — this is a new V3 concept.

---

## 12. Contract Test Suite

**Location:** `packages/contract-test-suite/`

**39 test files** covering:
- Schema validation (`test_schema_validation.py`)
- Contract freeze (`test_contract_freeze.py`, `test_contract_count_freeze.py`)
- Composability (`test_composability.py`)
- Fixture replay (`test_fixture_replay.py`)
- Event stream replay (`test_event_stream_replay.py`)
- Output boundary (`test_output_boundary_backend_noise.py`)
- Gate coverage (`test_gate_coverage.py`)
- Phase-specific contracts (test_phase3 through test_phase25)
- Privacy gates (`test_privacy_gates.py`)
- V2 acceptance traceability (`test_v2_readiness_report.py`)

**New tests needed for Phase 88:**
- Unified event schema validation (13 types)
- RunEvent replay tests (out-of-order, seq-based resume)
- Elicititation ↔ RunInterrupt interconversion
- Five-phase progress mapping
- Bot degradation aggregator determinism
- Industry neutrality for new event types

---

## Validation Architecture

### Required Tests

1. **Schema validation:** Each of the 13 event types has a JSON Schema; all schemas validate against fixtures
2. **Python binding tests:** Each event type has a frozen dataclass; serialization round-trips
3. **TypeScript binding tests:** Generated TS interfaces compile; type-check passes
4. **RunEvent replay tests:**
   - Out-of-order events replay correctly by `seq`
   - Resume from any `seq` breakpoint: no duplicates, no loss
   - `occurred_at` + `ingested_at` + `seq` semantics preserved
5. **Elicitation ↔ RunInterrupt interconversion:**
   - `elicitation.requested` → `RunInterrupt` (field mapping)
   - `RunInterrupt` → `elicitation.requested` (reverse mapping)
   - `allow_multiple` field present and correct
   - 2-4 questions constraint enforced
6. **Five-phase progress mapping:**
   - research → intake → retrieval → draft → review transitions
   - Mapping to thinking/tool/streaming/review
7. **Bot degradation aggregator:**
   - Given event sequence X, produces deterministic delivery Y
   - All 8 degradation categories tested (silent/buffer/deliver/discard/fold/first-then-silent/attach/on-failure)
8. **V2 schema preservation:**
   - 5 V2 schemas unchanged (field-level diff test)
   - 28 gates green
9. **Industry neutrality:**
   - New event types pass composability tests
   - No legal-specific top-level fields

### Test Placement

- Schema/binding tests → `packages/platform-contract/tests/` (covered by gate #1)
- Contract/replay/degradation tests → `packages/contract-test-suite/tests/` (covered by gate #25)
- Composability tests → extend existing `test_composability.py`

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Expanding `RunEventType` enum breaks existing gates | High | Keep old enum values as aliases; run gates after each change |
| `RunEvent` respecification breaks V2 consumers | High | Add new fields as optional; don't remove existing fields; `ingested_at` is new optional |
| New event schemas violate industry neutrality | Medium | Run composability tests after each schema; use `industry_context` for legal fields |
| ACP isomorphism not perfectly achievable | Medium | Document any required translations; keep them minimal and reversible |
| Bot degradation rules non-deterministic | Medium | Design as pure functions: input sequence → deterministic output |
| TypeScript binding generation breaks | Low | Extend existing generator pattern; deterministic output |

---

## Recommendations

1. **Evolutionary approach:** Expand `RunEventType` enum with new values, keep old values as aliases for backward compat. Don't remove `state_changed` — add `run.state_changed` as the canonical name with `state_changed` as alias.

2. **`RunEvent` respecification:** Add `ingested_at` (optional), expand `event_type` enum, add `payload` field (typed per event_type) or use discriminated union pattern. Keep all existing fields.

3. **New schemas:** Create one JSON Schema per event type (13 files), all referencing `common.schema.json` for shared definitions. Add `elicitation_question.schema.json` for the ask-user protocol fields.

4. **Bot degradation:** Implement as a pure-function aggregator in `packages/platform-contract/src/platform_contract/bot_degradation.py`. Each event type has a declared degradation category. The aggregator takes `list[RunEvent]` → `BotDelivery` (deterministic).

5. **Five-phase contract:** Add `FivePhase` enum (research/intake/retrieval/draft/review) and a mapping table from event types to phases. `phase.changed` event carries the current phase.

6. **Elicititation contract:** New `ElicititationRequest` dataclass with `intro`, `questions[]` (each with `id`/`question`/`allow_multiple`/`options[]`). Bidirectional converter functions to/from `RunInterrupt`.

7. **TypeScript bindings:** Add event type interfaces to `platform-sdk-ts`, following the existing auto-generation pattern.

8. **Test strategy:** Add tests to both `platform-contract/tests/` and `contract-test-suite/tests/`. Run `python scripts/run_v2_gates.py` after each change to verify 28 gates stay green.

## RESEARCH COMPLETE
