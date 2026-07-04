---
phase: 41
slug: conversation-read-view-completion
status: planning
researcher: gsd-planner
created: 2026-07-04
---

# Phase 41 Research — Conversation Read-View Completion

> Requirements: **READVIEW-01** — Operator can query `conversation-read-view` with cursor-based pagination, time-range filters (`from`, `to`), and dimension filters (`user_id`, `channel`, `status`) on list endpoints, with enforced max result limits.
> **READVIEW-02** — Operator can query `conversation-read-view` by `trace_id` and receive all related events (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent) reconstructed in occurrence order.
> **READVIEW-03** — Operator can export conversation-read-view query results as CSV or JSON, and verify that all new endpoints apply read-time privacy scrubbing to response payloads.

## 1. Summary

Phase 41 **extends the existing `services/conversation-read-view/` service** — it does not create a new service, database, queue, or runtime dependency. The service is a dependency-light, pure-Python read model derived from V2 contract log JSONL records. Today it exposes three single-resource GET routes (`/conversations/{id}`, `/tasks/{id}`, `/feedback?status=pending`) with no pagination, no list endpoints, no time-range/dimension filters, no trace reconstruction endpoint, and no export.

Phase 41 adds four **additive** capabilities without changing any existing response shape:

1. **List endpoints with cursor-based pagination** (`/conversations`, `/tasks`) plus time-range (`from`, `to`) and dimension (`user_id`, `channel`, `status`) filters, with an enforced configurable max result limit.
2. **Trace reconstruction by `trace_id`** (`/traces/{trace_id}`) joining AgentTurn, RouteDecision, ExecutionTrace, AgentResult, and FeedbackEvent in occurrence order.
3. **CSV/JSON export** of list-query results (`/export?resource=conversations|tasks&format=csv|json`).
4. **Read-time privacy scrubbing** on every new endpoint, reusing the existing `scrub_contract_payload` helper, plus **backward-compatibility tests** proving existing endpoint response shapes are unchanged, and a **V2 gate update** confirming the `conversation-read-view` gate stays green.

The work is **contract-safe**: no changes to `packages/platform-contract/` or `packages/platform-runtime/protocols.py` (SAFETY-02, SAFETY-06). The read model already imports `platform_runtime.privacy_keys.ALL_FORBIDDEN_KEYS` for scrubbing — Phase 41 reuses that import path, it does not modify it.

Key findings:

- The read model is built by `ContractLogReadModel.from_records(records)` (`services/conversation-read-view/src/conversation_read_view/read_model.py:44-127`). Records are `EventStreamRecord`-shaped objects with `event_key`, `occurred_at`, `ingested_at`, `seq`, `event`, loaded via `load_event_stream` from `contract_test_suite.event_stream_replay`.
- The read model already indexes `trace_to_task_id` (`read_model.py:117-121`) by extracting `trace_id` from `ExecutionTrace.trace_id` and `AgentResult.metadata.trace_id`. This index is the seed for the trace-reconstruction endpoint.
- The API entry point is `handle_get(path, query, read_model, feedback_queue=None)` (`api.py:11-58`). It splits path/query, routes by prefix, and applies `scrub_contract_payload` via `_with_contract_metadata` (`api.py:93-99`) on every 200 response. New endpoints must go through the same scrub path.
- Privacy scrubbing is **read-time and raises on forbidden keys** (`privacy.py:51-62`). It walks mappings/lists recursively and raises `ValueError` if any key in `ALL_FORBIDDEN_KEYS` is present. The existing `test_privacy_scrub.py` proves all API response paths apply it. New endpoints must be covered by an equivalent test.
- The `conversation-read-view` V2 gate already exists (`scripts/run_v2_gates.py:83-87`, gate #4) and discovers all tests under `services/conversation-read-view/tests/`. New tests are picked up automatically — no new gate is required. The Phase 41 "gate update" is a verification task confirming the gate stays green and that the `contract-test-suite` gate (which has `read_view_src` on its PYTHONPATH, line 127) can still import the extended package.
- The package has `dependencies = []` (`pyproject.toml:11`) and must stay dependency-light. CSV export must use only the stdlib `csv` module — no new runtime dependency.
- There is **no feature flag** for the read view (it is a read-only derived view, not a runtime lane). Phase 41 does not add one; the read view is always available to operators. This is consistent with the existing design where the read view has no `RuntimeFeatureFlags` entry.

## 2. Existing Conversation Read-View Implementation

### 2.1 Package layout

**Path:** `services/conversation-read-view/`

```
src/conversation_read_view/
  __init__.py     # public API surface
  api.py          # handle_get route dispatcher (pure GET)
  models.py       # ConversationTurnView, ConversationView, TaskView, EventReference, ReadModelIssue
  read_model.py   # ContractLogReadModel.from_records + get_conversation/get_task/get_task_by_trace_id
  privacy.py      # scrub_contract_payload, find_forbidden_key_path, find_forbidden_raw_payload_path
tests/
  test_api.py            # route-level tests (conversations, tasks, feedback)
  test_read_model.py     # read model build + lookup + ordering tests
  test_privacy_scrub.py  # read-time scrub tests (SAFETY-03 unification)
pyproject.toml   # name=inkstatute-conversation-read-view, dependencies=[]
README.md
```

### 2.2 API routes (current, must NOT change shape)

**File:** `services/conversation-read-view/src/conversation_read_view/api.py:11-58`

| Route | Method | Returns | Scrubbed? |
|-------|--------|---------|-----------|
| `/conversations/{conversation_id}` | GET | `ConversationView.to_dict()` + `metadata.derived_from_contract_log=True` | Yes — `_with_contract_metadata` |
| `/tasks/{identifier}` | GET | `TaskView.to_dict()` (lookup by task_id, turn_id, or trace_id) | Yes — `_with_contract_metadata` |
| `/feedback?status=pending` | GET | `{"items": [...], "count": N, "metadata": {...}}` | Yes — per-item `scrub_contract_payload` |
| anything else | GET | 404 `not_found_response` | n/a |

**Backward-compat constraint:** These three routes' response shapes (top-level keys, `metadata.derived_from_contract_log`, `source_status`, `lookup_aliases`, etc.) are asserted by `tests/test_api.py`, `tests/test_read_model.py`, and `packages/contract-test-suite/tests/test_phase6_read_feedback_apis.py`. Phase 41 must not alter them.

### 2.3 Read model data flow

**File:** `services/conversation-read-view/src/conversation_read_view/read_model.py:44-127`

`from_records` sorts records by `(occurred_at, ingested_at, seq)`, groups by `turn_id`, and for each turn picks the first `agent_turn` (anchor), `route_decision`, `execution_trace`, `agent_result`, plus all `feedback_event`s. It builds:

- `conversations: dict[str, ConversationView]` keyed by `conversation_id`.
- `tasks: dict[str, TaskView]` keyed by both `task_id` and `turn_id` (alias).
- `trace_to_task_id: dict[str, str]` keyed by `trace_id` (from `execution_trace.trace_id` or `agent_result.metadata.trace_id`).

This gives us the join keys needed for trace reconstruction: every event carries `turn_id`, and `trace_id` links to a turn/task. To reconstruct a trace we need to collect **all** events sharing the same `trace_id` (directly on `ExecutionTrace`, via `metadata.trace_id` on `AgentResult`, and via the `turn_id` join for `AgentTurn`/`RouteDecision`/`FeedbackEvent`).

### 2.4 Privacy scrubbing

**File:** `services/conversation-read-view/src/conversation_read_view/privacy.py:51-62`

`scrub_contract_payload(value)` recursively walks mappings/lists and **raises `ValueError`** if any key in `ALL_FORBIDDEN_KEYS` is present. It does not silently redact — it rejects. `ALL_FORBIDDEN_KEYS` is imported from `platform_runtime.privacy_keys` (the unified source of truth established by SAFETY-03) and includes `raw_payload`, `case_facts`, `document_text`, `full_text`, `prompt_content`, `completion_text`, `function_call_result`, `tool_output`, etc.

Every new endpoint must route its response through `scrub_contract_payload` (either via `_with_contract_metadata` or an equivalent wrapper). The existing `test_privacy_scrub.py:27-44` proves the current API paths raise on forbidden keys — Phase 41 adds the same proof for new paths.

### 2.5 Record loading

**File:** `services/conversation-read-view/src/conversation_read_view/read_model.py:20-25`

`load_records_from_jsonl(path)` delegates to `contract_test_suite.event_stream_replay.load_event_stream`, which schema-validates each JSONL line and returns `EventStreamRecord` objects. The read model coerces both `Mapping` and attribute-style records (`_coerce_record`, `read_model.py:165-183`). Phase 41 list/filter logic operates on the already-built `ContractLogReadModel` indexes — it does not re-parse JSONL.

## 3. Contract Event Types (read-only, frozen)

**File:** `packages/platform-contract/src/platform_contract/events.py` (SAFETY-02/06 — read only, no modification)

| Event | Dataclass | Key fields for read-view | Join key |
|-------|-----------|--------------------------|----------|
| AgentTurn | `events.py:125-137` | `turn_id`, `conversation_id`, `channel`, `user_id`, `message_type`, `received_at` | `turn_id` |
| RouteDecision | `events.py:206-222` | `route_decision_id`, `turn_id`, `primary_skill`, `mode`, `created_at`, `route_mismatch` | `turn_id` |
| ExecutionTrace | `events.py:183-203` | `trace_id`, `turn_id`, `started_at`, `ended_at`, `occurred_at`, `seq`, `steps`, `tool_calls`, `errors` | `turn_id` + `trace_id` |
| AgentResult | `events.py:140-155` | `result_id`, `turn_id`, `status`, `reply_type`, `content`, `artifacts`, `metadata.trace_id` | `turn_id` (+ `metadata.trace_id`) |
| FeedbackEvent | `events.py:158-180` | `feedback_id`, `turn_id`, `conversation_id`, `user_id`, `source`, `event_type`, `status`, `created_at` | `turn_id` |

**Trace reconstruction join:** Given a `trace_id`, resolve `turn_id` via `trace_to_task_id[trace_id]` → `task_id` (which equals `turn_id` or maps to it), then collect every event whose `turn_id` matches. Occurrence order is `(occurred_at, ingested_at, seq)` — the same sort key already used by `from_records`.

## 4. Cursor-Based Pagination Approach

### 4.1 Design: opaque cursors, not offset/limit

Offset/limit pagination is unstable under inserts and encourages unbounded scans. Phase 41 uses **opaque cursors** encoding the sort key of the last item returned.

- **Sort key:** `(occurred_at, seq)` for events; for conversations/tasks list, sort by `(conversation_id|task_id)` with `occurred_at` of the anchor turn as a secondary tiebreaker. The simplest stable approach: sort list items by a deterministic string key derived from the read model (e.g. `conversation_id` for `/conversations`, `task_id` for `/tasks`) and encode the last key in the cursor.
- **Cursor encoding:** base64url of a compact JSON `{"k": "<last_key>", "t": "<occurred_at>"}`. Opaque to the caller — they just pass it back as `cursor=<value>`.
- **Page size:** `limit` query param, clamped to `[1, MAX_RESULT_LIMIT]`. Default page size (e.g. 50). `MAX_RESULT_LIMIT` configurable via env `CONVERSATION_READ_VIEW_MAX_LIMIT`, default 100, hard-clamped so a caller requesting `limit=10000` receives at most 100.
- **Response shape (new):**
  ```json
  {
    "items": [ ... ],
    "count": <int>,
    "next_cursor": "<opaque or null>",
    "has_more": <bool>,
    "metadata": {
      "derived_from_contract_log": true,
      "limit": <int>,
      "max_result_limit": <int>,
      "filters": {"from": "...", "to": "...", "user_id": "...", "channel": "...", "status": "..."}
    }
  }
  ```
- **Backward compat:** This is a **new** response shape for **new** list endpoints. The existing single-resource `/conversations/{id}` and `/tasks/{id}` shapes are untouched.

### 4.2 Max result limit enforcement

A module-level `DEFAULT_MAX_RESULT_LIMIT = 100` and a `resolve_max_result_limit(env)` helper reading `CONVERSATION_READ_VIEW_MAX_LIMIT` (int, clamped to `[10, 1000]`). Every list query clamps `limit` to `min(requested_limit, max_result_limit)` and the response `metadata.max_result_limit` echoes the enforced cap. This prevents unbounded memory usage (READVIEW-01 success criterion 1).

## 5. Time-Range and Dimension Filters

### 5.1 Time-range filters (`from`, `to`)

- `from` / `to` query params are ISO-8601 timestamps (e.g. `2026-06-28T03:20:00Z`).
- Applied to the anchor event's `occurred_at` (for conversations, the first turn's `agent_turn.received_at` or `occurred_at`; for tasks, the turn's `occurred_at`).
- Inclusive on both ends. Invalid timestamp format → 400 `invalid_time_filter`.

### 5.2 Dimension filters

| Filter | Applies to | Source field |
|--------|-----------|--------------|
| `user_id` | conversations, tasks | `agent_turn.user_id` |
| `channel` | conversations, tasks | `agent_turn.channel` |
| `status` | tasks only | `agent_result.status` (e.g. `success`, `failed`, `unknown`) |

Filters are combined with AND semantics. Unknown filter keys → 400 `unsupported_filter` (fail closed, consistent with the existing `/feedback` `unsupported_status` 400 pattern at `api.py:36-47`).

## 6. Trace Reconstruction by trace_id

### 6.1 New endpoint: `/traces/{trace_id}`

**Response shape (new):**
```json
{
  "trace_id": "<trace_id>",
  "turn_id": "<turn_id>",
  "task_id": "<task_id>",
  "conversation_id": "<conversation_id>",
  "events": [
    {"event_key": "agent_turn", "occurred_at": "...", "seq": 0, "event": {...}},
    {"event_key": "route_decision", "occurred_at": "...", "seq": 1, "event": {...}},
    {"event_key": "execution_trace", "occurred_at": "...", "seq": 2, "event": {...}},
    {"event_key": "agent_result", "occurred_at": "...", "seq": 3, "event": {...}},
    {"event_key": "feedback_event", "occurred_at": "...", "seq": 4, "event": {...}}
  ],
  "metadata": {
    "derived_from_contract_log": true,
    "event_count": 5,
    "reconstruction_complete": true
  }
}
```

### 6.2 Implementation approach

The read model currently discards per-event records after building turn views (it keeps only the first of each event type per turn). To reconstruct **all** events in occurrence order (including multiple feedback events and the raw event payloads), Phase 41 extends `ContractLogReadModel` to retain a `trace_events: dict[str, list[_Record]]` index built during `from_records`. Each record is keyed by `trace_id` (resolved from `execution_trace.trace_id` or `agent_result.metadata.trace_id`, with `turn_id` fallback for events that lack a direct `trace_id`).

The reconstruction:
1. Look up `trace_id` in `trace_events`. If present, return those records sorted by `(occurred_at, ingested_at, seq)`.
2. If absent, fall back to `trace_to_task_id[trace_id]` → `turn_id`, then collect all records for that turn.
3. If still absent, 404 `not_found`.

`reconstruction_complete` is `True` when an `execution_trace` event is present (the trace anchor); `False` when only partial events were found via turn_id fallback.

## 7. CSV/JSON Export

### 7.1 New endpoint: `/export`

**Query params:** `resource=conversations|tasks`, `format=csv|json`, plus the same `from`/`to`/`user_id`/`channel`/`status` filters and `limit` (clamped to `MAX_RESULT_LIMIT`). Cursor pagination is **not** supported on export (export returns a single bounded batch up to `MAX_RESULT_LIMIT`).

- `format=json` → `200` with `Content-Type: application/json`, body is the same `items` array as the list endpoint (scrubbed).
- `format=csv` → `200` with `Content-Type: text/csv`, body is a CSV with a header row of flattened field names. CSV uses the stdlib `csv.DictWriter` over a flattened projection of each item (no nested objects — nested fields are JSON-encoded into a single cell to keep CSV flat). No new dependency.
- Unknown `resource` or `format` → 400.

### 7.2 CSV field projection

For `resource=conversations`: columns `conversation_id, turn_count, user_ids, occurred_at`. For `resource=tasks`: columns `task_id, turn_id, conversation_id, trace_id, status, occurred_at`. Nested fields (e.g. `agent_result`, `route_decision`) are omitted from CSV by default to keep rows flat; the JSON export preserves full structure. This is documented in the response `metadata.csv_projection`.

## 8. Read-Time Privacy Scrubbing on New Endpoints

All four new endpoints (`/conversations` list, `/tasks` list, `/traces/{trace_id}`, `/export`) route responses through `scrub_contract_payload`:

- List endpoints: scrub each item + the envelope metadata.
- Trace endpoint: scrub each event in `events` + the envelope.
- Export: scrub the items **before** CSV/JSON serialization. CSV cells are derived from already-scrubbed items, so no double-scrub needed, but the JSON export body is scrubbed as a whole.

A new test (mirroring `test_privacy_scrub.py:27-44`) feeds a fake read model returning forbidden keys and asserts each new endpoint raises `ValueError`.

## 9. Backward Compatibility Strategy

1. **No existing route signature changes.** `handle_get(path, query, read_model, feedback_queue=None)` keeps the same signature; new routes are added as new `if` branches.
2. **No existing response shape changes.** The existing `/conversations/{id}`, `/tasks/{id}`, `/feedback` shapes are frozen. A dedicated `test_backward_compat.py` snapshots the exact top-level keys of each existing response and asserts they are unchanged after Phase 41.
3. **Read model extensions are additive.** `ContractLogReadModel.__init__` gains optional new indexes (`trace_events`) with safe defaults. `get_conversation`/`get_task`/`get_task_by_trace_id` return the same dicts. New methods (`list_conversations`, `list_tasks`, `get_trace_reconstruction`) are added.
4. **No new runtime dependencies.** `pyproject.toml` stays `dependencies = []`. CSV uses stdlib `csv`.
5. **No contract changes.** `packages/platform-contract/` and `packages/platform-runtime/protocols.py` are read-only (SAFETY-02, SAFETY-06).

## 10. V2 Gate Integration Approach

- The `conversation-read-view` gate (`scripts/run_v2_gates.py:83-87`) already discovers all tests under `services/conversation-read-view/tests/` with PYTHONPATH `(read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src)`. New tests are picked up automatically — **no gate definition change is required**.
- The `contract-test-suite` gate (line 124-128) has `read_view_src` on its PYTHONPATH, so cross-package contract tests can import the extended package.
- The `compileall` gate (line 133-155) already includes `services/conversation-read-view/src`.
- Phase 41 Wave 3 is a **verification** task: run `python scripts/run_v2_gates.py --list` (expect 13 gates, unchanged), run the full suite (expect all green), and run the SAFETY-02/06 contract freeze tests to confirm no contract drift. If any new test requires an additional fixture, it is added under `packages/contract-test-suite/fixtures/` (the privacy scan `default_privacy_data_paths` already covers that directory).

## 11. Files Touched (summary)

| Wave | File | Change |
|------|------|--------|
| 1 | `services/conversation-read-view/src/conversation_read_view/pagination.py` | NEW — cursor encode/decode, max limit resolver |
| 1 | `services/conversation-read-view/src/conversation_read_view/read_model.py` | EXTEND — `list_conversations`, `list_tasks` with filters |
| 1 | `services/conversation-read-view/src/conversation_read_view/api.py` | EXTEND — `/conversations`, `/tasks` list routes |
| 1 | `services/conversation-read-view/src/conversation_read_view/__init__.py` | EXTEND — export new symbols |
| 1 | `services/conversation-read-view/tests/test_pagination.py` | NEW — cursor + filter + max limit tests |
| 2 | `services/conversation-read-view/src/conversation_read_view/read_model.py` | EXTEND — `trace_events` index, `get_trace_reconstruction` |
| 2 | `services/conversation-read-view/src/conversation_read_view/export.py` | NEW — CSV/JSON export serializer |
| 2 | `services/conversation-read-view/src/conversation_read_view/api.py` | EXTEND — `/traces/{trace_id}`, `/export` routes |
| 2 | `services/conversation-read-view/tests/test_trace_reconstruction.py` | NEW |
| 2 | `services/conversation-read-view/tests/test_export.py` | NEW |
| 3 | `services/conversation-read-view/tests/test_privacy_scrub.py` | EXTEND — new endpoint scrub assertions |
| 3 | `services/conversation-read-view/tests/test_backward_compat.py` | NEW — existing shape snapshot |
| 3 | `scripts/run_v2_gates.py` | VERIFY ONLY (no change expected) |
| 3 | `packages/contract-test-suite/tests/test_contract_count_freeze.py` | VERIFY ONLY (no change expected) |

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| New list endpoint shape collides with existing `/conversations/{id}` | Route by trailing structure: `/conversations` (no id) → list; `/conversations/{id}` → existing single. Tested explicitly. |
| Trace reconstruction returns forbidden keys | Route through `scrub_contract_payload`; test with forbidden-key fixture. |
| CSV export leaks nested sensitive fields | CSV projection omits nested objects; JSON export scrubbed wholesale. |
| Max limit bypass via huge `limit` param | Clamp in `pagination.py` before query; echo enforced cap in metadata. |
| Backward-compat regression in existing routes | Dedicated snapshot test in Wave 3. |
| Contract drift (SAFETY-02/06) | No edits to `platform-contract/` or `protocols.py`; freeze tests run in Wave 3. |
