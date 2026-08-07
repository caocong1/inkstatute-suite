---
phase: 88-unified-event-contract
plan: 03
subsystem: contract
tags: [elicitation, ask-user-protocol, run-interrupt, interconversion]

requires:
  - phase: 88-01
    provides: elicitation_requested.schema.json + ElicitationRequestedPayload/ElicitationQuestion/ElicitationOption dataclasses

provides:
  - elicitation_question.schema.json — standalone, reusable JSON Schema for ask-user question format (id/question/allow_multiple/options)
  - elicitation.py — bidirectional RunInterrupt interconversion (elicitation_to_run_interrupt / run_interrupt_to_elicitation), validate_question_count (2-4), format_answer_display (single/multi/free-text)
  - 16 test methods covering field mapping, round-trip preservation, allow_multiple, options, answer display, reference-first prompt_ref
  - __init__.py exports for all four new functions

affects: [88-06]

key-files:
  created:
    - packages/platform-contract/src/platform_contract/schemas/elicitation_question.schema.json
    - packages/platform-contract/src/platform_contract/elicitation.py
    - packages/platform-contract/tests/test_elicitation_contract.py
  modified:
    - packages/platform-contract/src/platform_contract/__init__.py

key-decisions:
  - "elicitation_question.schema.json extracted as standalone reusable schema (was inline $def in elicitation_requested.schema.json) — enables expected_response_schema_ref to point at a real URL"
  - "prompt_ref is reference-first: 'elicitation://<interrupt_id>' — never contains full intro/questions text (AGENTS.md constraint)"
  - "Full question structure stored in RunInterrupt.metadata for round-trip fidelity — intro and questions serialized via dataclasses.asdict"
  - "expected_response_schema_ref points to elicitation_question.schema.json URL — the schema that validates question structure"
  - "format_answer_display: single-select shows label, multi-select shows labels joined by '、', free-text shows raw answer — per ASK-USER-PROTOCOL.md"
  - "validate_question_count enforces 2-4 constraint (minItems:2, maxItems:4 from ASK-USER-PROTOCOL.md)"

patterns-established:
  - "Pattern: Reference-first interconversion — prompt_ref is a URI, not full text; full payload in metadata for round-trip"
  - "Pattern: Bidirectional contract interconversion — elicitation ↔ RunInterrupt with lossless round-trip"
  - "Pattern: Standalone reusable schema extraction — $def extracted to standalone .schema.json for $ref-ability"

requirements-completed: [EVT-03]

coverage:
  - id: D1
    description: "elicitation_question.schema.json defines ask-user question format with id/question/allow_multiple/options matching ASK-USER-PROTOCOL.md"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "inline assertion: schema required, allow_multiple default, options items, additionalProperties"
        status: pass
    human_judgment: false
  - id: D2
    description: "elicitation_to_run_interrupt correctly maps all fields from ElicitationRequestedPayload to RunInterrupt (interrupt_id, status, reason, prompt_ref, resume_state_ref, expected_response_schema_ref)"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_elicitation_to_run_interrupt_field_mapping"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_interrupt_to_elicitation correctly reverses the mapping, preserving intro, questions, allow_multiple, options"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_run_interrupt_to_elicitation_roundtrip"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_interconversion_preserves_allow_multiple"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_interconversion_preserves_options"
        status: pass
    human_judgment: false
  - id: D4
    description: "validate_question_count enforces 2-4 question constraint per ASK-USER-PROTOCOL.md"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_two_questions_valid"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_four_questions_valid"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_one_question_invalid"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_five_questions_invalid"
        status: pass
    human_judgment: false
  - id: D5
    description: "format_answer_display produces correct display text for single-select (label), multi-select (labels joined by 、), and free-text (raw answer)"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_format_answer_display_single_select"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_format_answer_display_multi_select"
        status: pass
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_format_answer_display_free_text"
        status: pass
    human_judgment: false
  - id: D6
    description: "prompt_ref is reference-first (starts with elicitation://), not full text (AGENTS.md constraint)"
    requirement: "EVT-03"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/test_elicitation_contract.py#test_prompt_ref_is_reference_not_full_text"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-07
status: complete
---

# Phase 88 Plan 03: Elicitation Contract Summary

**Elicitation contract with ASK-USER-PROTOCOL.md field semantics (2-4 questions, allow_multiple, free-text) and bidirectional RunInterrupt interconversion with reference-first prompt_ref**

## Performance

- **Duration:** ~20 min
- **Tasks:** 4
- **Files modified:** 4 (1 new schema, 1 new Python module, 1 new test file, 1 modified __init__.py)

## Accomplishments

- Created `elicitation_question.schema.json` as a standalone, reusable JSON Schema for the ask-user question format (id, question, allow_multiple default false, options with label/value, additionalProperties false)
- Created `elicitation.py` with four functions:
  - `elicitation_to_run_interrupt` — converts ElicitationRequestedPayload to RunInterrupt with reference-first prompt_ref (`elicitation://<interrupt_id>`), full question structure in metadata
  - `run_interrupt_to_elicitation` — reverses the conversion, reconstructing ElicitationQuestion/ElicitationOption from metadata
  - `validate_question_count` — enforces 2-4 question constraint per ASK-USER-PROTOCOL.md
  - `format_answer_display` — formats answer display text (single-select label, multi-select labels joined by `、`, free-text raw)
- Updated `__init__.py` to export all four new functions
- Created 16 test methods covering field mapping, round-trip preservation, allow_multiple, options, answer display, reference-first prompt_ref
- All 71 platform-contract tests pass (55 existing + 16 new)

## Task Commits

1. **Task 88-03-01: Create elicitation_question.schema.json** — `e2baf02` (feat)
2. **Task 88-03-02: Create elicitation.py + update __init__.py** — `ff55bef` (feat)
3. **Task 88-03-03: Create test_elicitation_contract.py** — `af5ade1` (test)
4. **Task 88-03-04: Gate suite verification** — (verification only, no commit)

## Files Created/Modified

- `packages/platform-contract/src/platform_contract/schemas/elicitation_question.schema.json` — standalone reusable schema for ask-user question format
- `packages/platform-contract/src/platform_contract/elicitation.py` — interconversion functions + validation + display formatting
- `packages/platform-contract/src/platform_contract/__init__.py` — added exports for 4 new functions
- `packages/platform-contract/tests/test_elicitation_contract.py` — 16 test methods

## Decisions Made

1. **Standalone schema extraction** — `elicitation_question.schema.json` extracted from the inline `$def` in `elicitation_requested.schema.json` to a standalone, reusable schema. This enables `expected_response_schema_ref` to point at a real URL (`https://inkstatute.dev/schemas/platform-contract/elicitation_question.schema.json`).

2. **Reference-first prompt_ref** — `prompt_ref` is `elicitation://<interrupt_id>`, not the full intro/questions text. This follows the AGENTS.md constraint that contract logs prefer references. The full question structure is stored in `RunInterrupt.metadata` for round-trip fidelity.

3. **Full question structure in metadata** — `RunInterrupt.metadata` contains `intro` (string) and `questions` (list of serialized question dicts via `dataclasses.asdict`). This ensures lossless round-trip conversion. Remaining metadata keys (excluding `intro` and `questions`) are preserved in the returned payload's `metadata`.

4. **Answer display format** — `format_answer_display` produces a numbered list per ASK-USER-PROTOCOL.md: single-select shows the label for the selected value, multi-select shows labels joined by `、`, free-text (no options) shows the raw answer string.

5. **validate_question_count enforces 2-4** — Raises `ValueError` for <2 or >4 questions, matching the `minItems: 2, maxItems: 4` constraint in the schema and ASK-USER-PROTOCOL.md.

## Deviations from Plan

### Pre-existing Issues (not auto-fixed, out of scope)

**1. [Pre-existing] qqbot-channel gate 18 failures (7 tests)**
- **Found during:** Task 88-03-04 (gate suite verification)
- **Issue:** Gate 18 (qqbot-channel) has 7 pre-existing test failures related to `qqbot_passive_reply_window_expired` instead of expected upload-related issue codes. This blocks gates 19-28 from running.
- **Verification:** Confirmed pre-existing — my changes only touch platform-contract (new files: elicitation.py, elicitation_question.schema.json, test_elicitation_contract.py, modified __init__.py). No changes to packages/channels/qqbot/. Same issue documented in 88-01-SUMMARY and 88-02-SUMMARY.
- **Impact:** Gates 1-17 pass (including platform-contract gate with 71 tests). Gate 18 fails on pre-existing qqbot issues. Gates 19-28 cannot run.
- **Resolution:** Out of scope to fix (Rule: don't auto-fix unrelated pre-existing issues). Needs a separate fix before Plan 88-06 can verify all 28 gates green.

---

**Total deviations:** 1 pre-existing (out of scope, not auto-fixed)
**Impact on plan:** None — the elicitation contract is purely additive and non-breaking. Platform-contract gate green with 16 new tests.

## Issues Encountered

- **Pre-existing qqbot-channel gate 18 failures (7 tests):** Same `qqbot_passive_reply_window_expired` issue documented in 88-01-SUMMARY and 88-02-SUMMARY. Blocks gates 19-28 from running. Unrelated to 88-03 — my changes only touch platform-contract.
- **Pre-existing contract-test-suite failures (5 tests, from 88-01):** Documented in 88-02-SUMMARY. Not caused by 88-03 changes.

## Next Phase Readiness

- Elicitation contract fully defined and tested — ready for Plan 88-04 (five-phase progress) and Plan 88-05 (bot degradation aggregator)
- Bidirectional RunInterrupt interconversion enables Phase 90 (ACP event bridge) to map ACP `elicitation/create` ↔ `elicitation.requested` ↔ `RunInterrupt`
- `format_answer_display` ready for bot channel degradation (Phase 95) to render clarification answers in non-streaming channels
- `validate_question_count` ready for Gateway (Phase 91) to validate elicitation payloads at the API boundary
- **Blocker (carried from 88-01/88-02):** Pre-existing qqbot-channel test failures (gate 18) need a separate fix before Plan 88-06 can verify all 28 gates green

## Self-Check: PASSED

- [x] All 4 tasks executed and committed
- [x] elicitation_question.schema.json exists and is valid JSON with required=["id","question"], allow_multiple default false, options with label/value, additionalProperties false
- [x] ElicitationQuestion dataclass with id/question/allow_multiple/options fields (from 88-01, validated in tests)
- [x] elicitation_to_run_interrupt correctly maps all fields (interrupt_id, status, reason, prompt_ref, resume_state_ref, expected_response_schema_ref)
- [x] run_interrupt_to_elicitation correctly reverses the mapping, preserving intro, questions, allow_multiple, options
- [x] validate_question_count enforces 2-4 question constraint
- [x] format_answer_display produces correct display text for single-select, multi-select, and free-text
- [x] prompt_ref is reference-first (starts with elicitation://), not full text
- [x] Round-trip interconversion preserves all semantic fields
- [x] platform-contract tests pass: 71 tests (55 existing + 16 new)
- [x] python -m compileall packages/platform-contract/src exits 0
- [x] Gates 1-17 pass (platform-contract through rbac-annotation-scan)
- [x] V2's 5 persistence schemas not modified

---
*Phase: 88-unified-event-contract*
*Completed: 2026-08-07*
