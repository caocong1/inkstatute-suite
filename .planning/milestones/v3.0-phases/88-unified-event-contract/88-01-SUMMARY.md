---
phase: 88-unified-event-contract
plan: 01
subsystem: contract
tags: [json-schema, events, python, typescript, acp, unified-vocabulary]

requires: []
provides:
  - 13-category unified event vocabulary isomorphic to ACP v1 session/update
  - 15 JSON Schema files for V3 event types (additionalProperties: false)
  - 18 Python payload dataclasses with serialize/deserialize
  - 18 TypeScript event interfaces + UnifiedEventPayload union
  - RunEventType enum expanded to 23 members (9 V2 + 14 V3, additive-only)
affects: [88-02, 88-03, 88-04, 88-05, 88-06]

actuals:
  tokens: 18000
  tasks: 7
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Unified event vocabulary isomorphic to ACP session/update (thin relay)"
    - "Additive-only enum expansion (V2 values preserved, V3 added alongside)"
    - "Industry-neutral schemas with additionalProperties: false"
    - "No auto_approve field in permission_requested schema (safety constraint)"

key-files:
  created:
    - packages/platform-contract/src/platform_contract/schemas/session_started.schema.json
    - packages/platform-contract/src/platform_contract/schemas/message_delta.schema.json
    - packages/platform-contract/src/platform_contract/schemas/message_completed.schema.json
    - packages/platform-contract/src/platform_contract/schemas/thought_delta.schema.json
    - packages/platform-contract/src/platform_contract/schemas/tool_call_started.schema.json
    - packages/platform-contract/src/platform_contract/schemas/tool_call_delta.schema.json
    - packages/platform-contract/src/platform_contract/schemas/tool_call_completed.schema.json
    - packages/platform-contract/src/platform_contract/schemas/plan_updated.schema.json
    - packages/platform-contract/src/platform_contract/schemas/phase_changed.schema.json
    - packages/platform-contract/src/platform_contract/schemas/elicitation_requested.schema.json
    - packages/platform-contract/src/platform_contract/schemas/permission_requested.schema.json
    - packages/platform-contract/src/platform_contract/schemas/artifact_created.schema.json
    - packages/platform-contract/src/platform_contract/schemas/citation_recorded.schema.json
    - packages/platform-contract/src/platform_contract/schemas/run_state_changed.schema.json
    - packages/platform-contract/src/platform_contract/schemas/error_event.schema.json
    - packages/platform-contract/src/platform_contract/unified_events.py
    - packages/platform-sdk-ts/src/events.ts
    - packages/platform-contract/tests/test_unified_events.py
    - packages/platform-contract/tests/test_event_schemas.py
    - packages/platform-sdk-ts/tests/test_event_types.py
  modified:
    - packages/platform-contract/src/platform_contract/enums.py
    - packages/platform-contract/src/platform_contract/schemas/common.schema.json
    - packages/platform-contract/src/platform_contract/__init__.py
    - scripts/run_v2_gates.py
    - services/admin-console-api/src/admin_console_api/gates.py
    - services/admin-web-ui/tests/test_smoke_e2e.py

key-decisions:
  - "Additive-only enum expansion: all 9 V2 RunEventType values preserved, 14 new V3 values added alongside"
  - "15 schema files (not 13): tool_call has 3 sub-types (started/delta/completed), error and run_state_changed are separate"
  - "No auto_approve or default_decision field in permission_requested.schema.json per AGENTS.md safety constraint"
  - "Elicitation questions enforced at 2-4 (minItems: 2, maxItems: 4) per V3-PRD §3.2"
  - "Industry-neutral schemas: no top-level jurisdiction/lawyer/legal/lawfirm/attorney/counsel fields; legal data in metadata.industry_context"
  - "Fixed gate-suite circular dependency: admin-web-ui smoke test → /reports → run_gate_summary() → gate suite → admin-web-ui gate → smoke test (unbounded recursion)"

patterns-established:
  - "Pattern 1: Unified event vocabulary isomorphic to ACP session/update — platform stays a thin relay"
  - "Pattern 2: Additive-only enum expansion — V2 values never removed or renamed"
  - "Pattern 3: Industry-neutral schemas with additionalProperties: false and no forbidden top-level fields"
  - "Pattern 4: Safety-by-omission — permission_requested schema has no auto_approve field by design"

requirements-completed: [EVT-01]

coverage:
  - id: D1
    description: "13-category unified event vocabulary with JSON Schema, Python bindings, and TypeScript interfaces"
    requirement: "EVT-01"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_unified_events.py"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_event_schemas.py"
        status: pass
      - kind: unit
        ref: "packages/platform-sdk-ts/tests/test_event_types.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "RunEventType enum expanded to 23 members (9 V2 + 14 V3, additive-only)"
    requirement: "EVT-01"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_unified_events.py#test_enum_preservation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Permission requested schema has no auto_approve or default_decision field (safety constraint)"
    requirement: "EVT-01"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_event_schemas.py#test_no_auto_approve"
        status: pass
    human_judgment: false
  - id: D4
    description: "All 15 schemas are industry-neutral (no forbidden top-level fields, additionalProperties: false)"
    requirement: "EVT-01"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_event_schemas.py#test_no_forbidden_fields"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-08-07
status: complete
---

# Phase 88 Plan 01: Core 13 Unified Event Types Summary

**13-category unified event vocabulary (15 JSON Schemas, 18 Python dataclasses, 18 TypeScript interfaces) isomorphic to ACP v1 session/update — the foundational protocol layer for V3**

## Performance

- **Duration:** ~40 min
- **Tasks:** 7
- **Files modified:** 20 (15 new schemas, 4 new code/test files, 5 modified)

## Accomplishments
- Defined 13-category unified event vocabulary with 15 JSON Schema files (additionalProperties: false, industry-neutral)
- Expanded RunEventType enum from 9 to 23 members (additive-only — all V2 values preserved)
- Created 18 Python payload dataclasses with serialize_payload/deserialize_payload round-trip
- Created 18 TypeScript event interfaces + UnifiedEventPayload union + RunEventEnvelope
- Enforced safety constraints: no auto_approve in permission_requested, 2-4 questions in elicitation
- Fixed gate-suite circular dependency (admin-web-ui smoke test ↔ /reports endpoint recursion)
- Fixed PYTHONPATH for wecom-service, qqbot-channel, and related gates (pre-existing infrastructure debt)

## Task Commits

1. **Task 88-01-01: Reversibility checkpoint** — `a0d1f1d` (feat: expand RunEventType enum)
2. **Task 88-01-02: Expand enum + common.schema.json** — `a0d1f1d` (feat)
3. **Task 88-01-03: Create 15 JSON Schema files** — `ab381cb` (feat)
4. **Task 88-01-04: Create unified_events.py + update __init__.py** — `d59042e` (feat)
5. **Task 88-01-05: Create TypeScript event interfaces** — `80e24c9` (feat)
6. **Task 88-01-06: Create test suites** — `92e0102` (test)
7. **Task 88-01-07: Gate suite verification** — `f930d0d` + `c1ef376` (fix: gate infrastructure)

## Files Created/Modified
- `packages/platform-contract/src/platform_contract/enums.py` — 14 new V3 RunEventType members
- `packages/platform-contract/src/platform_contract/schemas/common.schema.json` — expanded run_event_type enum (23 values)
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json` — 15 new event-type schemas
- `packages/platform-contract/src/platform_contract/unified_events.py` — 18 dataclasses + serialize/deserialize + EVENT_TYPE_TO_PAYLOAD_CLASS
- `packages/platform-contract/src/platform_contract/__init__.py` — exports for all new types
- `packages/platform-sdk-ts/src/events.ts` — 18 TS interfaces + union type
- `packages/platform-contract/tests/test_unified_events.py` — 8 test methods
- `packages/platform-contract/tests/test_event_schemas.py` — 8 test methods
- `packages/platform-sdk-ts/tests/test_event_types.py` — 6 test methods
- `scripts/run_v2_gates.py` — PYTHONPATH fixes for wecom-service, qqbot-channel, codex-backend, provider-model-backend, feedback-service, contract-test-suite gates
- `services/admin-console-api/src/admin_console_api/gates.py` — INKSTATUTE_SKIP_GATE_SUMMARY env var check
- `services/admin-web-ui/tests/test_smoke_e2e.py` — set env var in setUp/tearDown

## Decisions Made
1. **Additive-only enum expansion** — all 9 V2 RunEventType values preserved; 14 new V3 values added alongside. No V2 value removed, renamed, or changed.
2. **15 schema files (not 13)** — 13 event categories, but tool_call has 3 sub-types (started/delta/completed) and error/run_state_changed are separate, yielding 15 total.
3. **No auto-approval fields** — permission_requested.schema.json deliberately omits auto_approve and default_decision per AGENTS.md safety constraint.
4. **Elicitation questions 2-4** — elicitation_requested.schema.json enforces minItems: 2, maxItems: 4 per V3-PRD §3.2.
5. **Industry-neutral schemas** — no top-level fields named jurisdiction, lawyer, legal, lawfirm, attorney, or counsel. Legal-specific data goes in metadata.industry_context.
6. **Gate-suite circular dependency fix** — admin-web-ui smoke test hits /reports → run_gate_summary() → gate suite subprocess → admin-web-ui gate → smoke test → /reports (unbounded recursion ~30s). Fixed with INKSTATUTE_SKIP_GATE_SUMMARY env var.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Gate-suite circular dependency (admin-web-ui)**
- **Found during:** Task 88-01-07 (gate suite verification)
- **Issue:** admin-web-ui smoke test hits /reports endpoint, which calls run_gate_summary(), which runs the full gate suite as subprocess, which includes the admin-web-ui gate, which re-runs the smoke test → unbounded recursion (~30s timeout)
- **Fix:** Added INKSTATUTE_SKIP_GATE_SUMMARY env var check in run_gate_summary() to return stub result instantly; set env var in test setUp/tearDown
- **Files modified:** services/admin-console-api/src/admin_console_api/gates.py, services/admin-web-ui/tests/test_smoke_e2e.py
- **Verification:** admin-web-ui gate now passes (273 tests pass in 4.6s)
- **Committed in:** f930d0d

**2. [Rule 3 - Blocking] Gate PYTHONPATH fixes (wecom-service, qqbot-channel, and related gates)**
- **Found during:** Task 88-01-07 (gate suite verification)
- **Issue:** Multiple gates had incomplete PYTHONPATH — wecom-service missing wecom_channel_src, qqbot-channel missing qqbot_service_src and operator_config_src. These caused the gate suite to stop early, preventing verification of "28 gates green"
- **Fix:** Added missing src directories to PYTHONPATH tuples for affected gates
- **Files modified:** scripts/run_v2_gates.py
- **Verification:** Gate suite now progresses through gate 18 (was stopping at gate 2)
- **Committed in:** f930d0d, c1ef376

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both auto-fixes were necessary to verify the "28 gates green" success criterion. No scope creep — fixes are gate infrastructure, not event type logic.

## Issues Encountered
- **Pre-existing qqbot-channel test failures (gate 18):** 4 tests in test_qqbot_channel_adapter.py fail with `qqbot_passive_reply_window_expired` instead of expected upload-related issue codes. Verified pre-existing at commit 6a171d7 (before Plan 88-01) — unrelated to event types. These block gates 19-28 from running. Need a separate fix before Plan 88-06 can verify EVT-06 ("28 gates green").

## Next Phase Readiness
- 13-category unified event vocabulary fully defined and tested — ready for Plans 88-02 through 88-06
- RunEvent enum expanded additively — Plan 88-02 can add ingested_at field
- Elicitation schema created — Plan 88-03 can build the elicitation contract
- Phase mapping enum present — Plan 88-04 can build five-phase progress
- Bot degradation categories defined in schemas — Plan 88-05 can build the aggregator
- **Blocker:** Pre-existing qqbot-channel test failures (gate 18) need a separate fix before Plan 88-06 can verify all 28 gates green

## Self-Check: PASSED

- [x] All 7 tasks executed and committed
- [x] RunEventType enum has 23 members (9 V2 + 14 V3)
- [x] All 15 schema files are valid JSON with additionalProperties: false
- [x] serialize_payload/deserialize_payload round-trip works for all 13 event types
- [x] permission_requested.schema.json has no auto_approve or default_decision field
- [x] No forbidden top-level fields (jurisdiction, lawyer, legal, lawfirm, attorney, counsel) in any schema
- [x] platform-contract tests pass: `python -m pytest packages/platform-contract/tests/ -x`
- [x] platform-sdk-ts tests pass: `python -m pytest packages/platform-sdk-ts/tests/ -x`
- [x] Gates 1-17 pass (platform-contract through rbac-annotation-scan)
- [x] V2's 5 persistence schemas not modified

---
*Phase: 88-unified-event-contract*
*Completed: 2026-08-07*
