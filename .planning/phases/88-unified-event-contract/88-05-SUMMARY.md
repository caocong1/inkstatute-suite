---
phase: 88-unified-event-contract
plan: 05
subsystem: contract
tags: [bot-degradation, aggregator, deterministic, non-streaming, fold, buffer]

requires:
  - phase: 88-01
    provides: event types
  - phase: 88-02
    provides: RunEvent with payload

provides:
  - DegradationCategory StrEnum with 8 members (SILENT, BUFFER, DELIVER, DISCARD, FOLD, FIRST_THEN_SILENT, ATTACH, ON_FAILURE)
  - DEGRADATION_RULES dict mapping all 15 V3 event type values to degradation categories
  - BotDelivery frozen dataclass — deterministic output of the aggregator
  - aggregate_events pure function — list[dict] → BotDelivery (deterministic, sorts by seq)
  - get_degradation_category helper — returns None for unknown/V2 event types
  - 20 deterministic golden fixture test methods covering all 8 categories

affects: [88-06]

key-files:
  created:
    - packages/platform-contract/src/platform_contract/bot_degradation.py
    - packages/platform-contract/tests/test_bot_degradation.py
  modified:
    - packages/platform-contract/src/platform_contract/__init__.py

key-decisions:
  - "8 degradation categories per V3-PRD §3.2: SILENT, BUFFER, DELIVER, DISCARD, FOLD, FIRST_THEN_SILENT, ATTACH, ON_FAILURE"
  - "DEGRADATION_RULES maps all 15 V3 event type values (13 categories + tool_call 3 sub-types + error/run_state_changed separate)"
  - "aggregate_events is a pure function: same input always produces same BotDelivery output — no random, no time-dependent behaviour, no side effects"
  - "plan.updated and phase.changed share a single first-then-silent flag — the first occurrence of EITHER type delivers '仍在处理', subsequent are silent"
  - "Events sorted by seq ascending before processing — out-of-order delivery does not affect output"
  - "Citations appended to final_message as a formatted reference section when both exist"
  - "get_degradation_category returns None for V2 event types (state_changed, step_started, etc.) — V2 events have no V3 degradation rule"

patterns-established:
  - "Pattern: Declarative degradation rules — DEGRADATION_RULES dict is the single source of truth, not magic conditionals"
  - "Pattern: Pure-function aggregator — deterministic output, no side effects, testable with golden fixtures"
  - "Pattern: Output boundary seed — degradation provides the mechanism for filtering what reaches bot users"

requirements-completed: [EVT-05]

coverage:
  - id: D1
    description: "8 degradation categories defined per V3-PRD §3.2"
    requirement: "EVT-05"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_bot_degradation.py#test_all_13_categories_have_degradation_rules"
        status: pass
    human_judgment: false
  - id: D2
    description: "aggregate_events pure function produces deterministic BotDelivery"
    requirement: "EVT-05"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_bot_degradation.py#test_deterministic_output_same_input_same_output"
        status: pass
    human_judgment: false
  - id: D3
    description: "All 8 degradation behaviors tested: silent, buffer, deliver, discard, fold, first-then-silent, attach, on-failure"
    requirement: "EVT-05"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_bot_degradation.py (20 test methods)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Out-of-order events handled by sorting on seq"
    requirement: "EVT-05"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_bot_degradation.py#test_out_of_order_events_sorted_by_seq"
        status: pass
    human_judgment: false
  - id: D5
    description: "On-failure delivers error prompt only on failure, not on success"
    requirement: "EVT-05"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_bot_degradation.py#test_run_state_changed_success_no_delivery"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-07
status: complete
---

# Phase 88 Plan 05: Bot Degradation Aggregator Summary

**Pure-function bot degradation aggregator with 8 declarative categories and deterministic BotDelivery output — given a sequence of unified events, produces the same final delivery content every time**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 3 (1 new source, 1 new test, 1 modified __init__)

## Accomplishments

- Created `DegradationCategory` StrEnum with 8 members matching V3-PRD §3.2 degradation behaviors
- Created `DEGRADATION_RULES` dict mapping all 15 V3 event type values to their degradation categories
- Created `BotDelivery` frozen dataclass with 7 fields: final_message, intermediate_prompts, cards, files, citations, error_prompt, delivered
- Implemented `aggregate_events` pure function — sorts by seq, processes each event per its degradation category, returns deterministic BotDelivery
- Implemented `get_degradation_category` helper — returns None for unknown/V2 event types
- Created 20 golden fixture test methods covering all 8 categories, determinism, out-of-order, and full lifecycle
- All 106 platform-contract tests pass (86 existing + 20 new)

## Task Commits

1. **Task 88-05-01: Create bot_degradation.py** — `93c2508` (feat)
2. **Task 88-05-02: Create test_bot_degradation.py** — `e47dbc7` (test)
3. **Task 88-05-03: Gate verification** — no commit (verification-only, pre-existing qqbot failures unchanged)

## Files Created/Modified

- `packages/platform-contract/src/platform_contract/bot_degradation.py` — DegradationCategory enum, DEGRADATION_RULES, BotDelivery dataclass, aggregate_events, get_degradation_category
- `packages/platform-contract/src/platform_contract/__init__.py` — exports for all new symbols
- `packages/platform-contract/tests/test_bot_degradation.py` — 20 test methods

## Decisions Made

1. **8 degradation categories** — SILENT, BUFFER, DELIVER, DISCARD, FOLD, FIRST_THEN_SILENT, ATTACH, ON_FAILURE. Each maps to a specific behavior per V3-PRD §3.2.

2. **15 DEGRADATION_RULES entries** — 13 event categories but tool_call has 3 sub-types (started/delta/completed) and error/run_state_changed are separate, yielding 15 total.

3. **plan.updated and phase.changed share a single first-then-silent flag** — The plan says "if this is the first plan.updated or phase.changed event", meaning the first occurrence of EITHER type delivers "仍在处理". Subsequent occurrences of both types are silent. This prevents duplicate "仍在处理" prompts when both plan and phase events fire.

4. **Citations appended to final_message** — When both final_message and citations exist, citations are appended as a formatted reference section (引用：[1] source（status）).

5. **Business prompts are industry-neutral Chinese** — "正在检索法规…" (tool fold), "仍在处理" (plan/phase first), "处理失败，请稍后重试或联系管理员" (failure). These are user-facing bot messages.

6. **Buffer falls back to payload.delta** — message.delta events can carry delta text in either `message_delta` (top-level RunEvent field) or `payload.delta` (typed payload). The aggregator checks both.

## Deviations from Plan

No deviations. All tasks executed as planned.

## Issues Encountered

- **Pre-existing qqbot-channel gate 18 failures (7 tests):** Same `qqbot_passive_reply_window_expired` issue documented in 88-01-SUMMARY and 88-02-SUMMARY. Verified pre-existing — my changes only touch `packages/platform-contract/`. Blocks gates 19-28 from running. Unrelated to 88-05.

## Next Phase Readiness

- Bot degradation aggregator is complete and tested — ready for Plan 88-06 (gate verification)
- The aggregator is a pure function that Phase 95 (Bot Channel Degradation) can consume directly
- `get_degradation_category` returns None for V2 types, ensuring V2 events are safely skipped
- **Blocker (carried from 88-01/88-02):** Pre-existing qqbot-channel test failures (gate 18) need a separate fix before Plan 88-06 can verify all 28 gates green

## Self-Check: PASSED

- [x] All 3 tasks executed and committed
- [x] DegradationCategory enum has 8 members matching V3-PRD §3.2
- [x] DEGRADATION_RULES maps all 15 V3 event type values
- [x] aggregate_events is a pure function — same input → same output (determinism test passes)
- [x] Silent events (session.started) dropped entirely
- [x] Buffer events (message.delta) accumulate and deliver on message.completed
- [x] Discard events (thought.delta) dropped
- [x] Fold events (tool_call.*) collapse to single business prompt
- [x] First-then-silent (plan.updated, phase.changed) delivers only first occurrence
- [x] Deliver events (elicitation, permission, artifact) produce cards/files
- [x] Attach events (citation.recorded) append to final message
- [x] On-failure events deliver error prompt only on failure (not on success)
- [x] Out-of-order events sorted by seq before processing
- [x] platform-contract tests pass: 106 tests (86 existing + 20 new)
- [x] compileall exits 0
- [x] V2's 5 persistence schemas not modified
- [x] Permission requests delivered as approval cards, never auto-approved

---
*Phase: 88-unified-event-contract*
*Completed: 2026-08-07*
