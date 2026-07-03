---
phase: 36
plan: 03
title: "Privacy Scrub Unification + Generic Output Boundary Rules"
wave: 2
requirements:
  - SAFETY-03
  - SAFETY-05
status: complete
commits:
  - b225eda
  - d64724a
---

# Plan 03 Summary: Privacy Scrub Unification + Generic Output Boundary Rules

## Tasks Completed

### Task 01: Create shared privacy_keys module, unify forbidden keys, and scrub all API paths (SAFETY-03)

**Commit:** `b225eda`

Created a shared `privacy_keys.py` module in platform-runtime that defines 11 unified forbidden keys:
- `raw_payload` (existing)
- 6 existing full-text keys: `case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`
- 4 new backend field names: `prompt_content`, `completion_text`, `function_call_result`, `tool_output`

Updated `store.py`, `interrupts.py`, and `session_resolver.py` to import from the shared module (removed all local `_FORBIDDEN_FULL_TEXT_KEYS` definitions). Updated `privacy.py` in conversation-read-view to reject all 11 forbidden keys at read-time via new `find_forbidden_key_path` function. Fixed API scrub gap: `_with_contract_metadata` now applies `scrub_contract_payload` to all response paths (`/conversations/`, `/tasks/`, `/feedback`).

### Task 02: Add generic output boundary patterns for provider/model noise (SAFETY-05)

**Commit:** `d64724a`

Added 3 hard-block rules (`provider_leak`, `api_error`, `function_trace`) and 2 rewrite rules (`rate_limit_notice`, `context_window`) to `output_boundary.py`. Created `provider_noise_cases.json` fixture with hard_block, rewrite, and allow test cases. Added 4 fixture-based tests including a false-positive guard for legal business text containing "model clause".

## Test Results

### Task 01 Tests
- `pytest packages/platform-runtime/tests/test_privacy_keys.py`: **7 passed, 15 subtests passed**
- `pytest services/conversation-read-view/tests/test_privacy_scrub.py`: **6 passed, 29 subtests passed**

### Task 02 Tests
- `pytest packages/platform-runtime/tests/test_output_boundary.py -k provider`: **1 passed, 8 subtests passed**
- `pytest packages/platform-runtime/tests/test_output_boundary.py` (full): **17 passed, 29 subtests passed**

### Full V2 Gate Suite (all 9 gates)
| Gate | Tests | Status |
|------|-------|--------|
| platform-contract | 21 | PASS |
| wecom-service | 72 | PASS |
| hermes-contract-layer | 30 | PASS |
| conversation-read-view | 24 | PASS |
| feedback-service | 31 | PASS |
| phase7-privacy-boundary | 13 | PASS |
| contract-test-suite | 300 | PASS |
| v2-acceptance-traceability | — | PASS |
| compileall | — | PASS |
| **Total** | **491 tests** | **All 9 gates green** |

## Files Modified

### New files
- `packages/platform-runtime/src/platform_runtime/privacy_keys.py` — shared forbidden keys module (11 keys)
- `packages/platform-runtime/tests/test_privacy_keys.py` — PrivacyKeysTests (7 test methods)
- `services/conversation-read-view/tests/test_privacy_scrub.py` — PrivacyScrubTests (6 test methods)
- `packages/contract-test-suite/fixtures/provider_noise_cases.json` — output boundary fixture (hard_block, rewrite, allow)

### Modified files
- `packages/platform-runtime/src/platform_runtime/store.py` — import from privacy_keys, single-pass ALL_FORBIDDEN_KEYS check
- `packages/platform-runtime/src/platform_runtime/interrupts.py` — import from privacy_keys, single-pass check
- `packages/platform-runtime/src/platform_runtime/session_resolver.py` — import from privacy_keys, single-pass check
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — 3 hard-block + 2 rewrite rules added
- `services/conversation-read-view/src/conversation_read_view/privacy.py` — find_forbidden_key_path, scrub all 11 keys
- `services/conversation-read-view/src/conversation_read_view/api.py` — _with_contract_metadata applies scrub
- `services/conversation-read-view/src/conversation_read_view/__init__.py` — export find_forbidden_key_path
- `packages/platform-runtime/tests/test_output_boundary.py` — 4 new fixture-based test methods
- `packages/platform-runtime/tests/test_session_resolution.py` — updated error message regex (2 assertions)
- `packages/platform-runtime/tests/test_context_assembler.py` — updated error message regex (1 assertion)

## Deviations from Plan

1. **Error message format (Task 01):** The plan specified error message `f"contract log event contains forbidden key at {path}"` but this broke existing tests that assert regex `"forbidden raw_payload"` (test_contract_log_store.py line 48) and `"full-text payload"` (test_session_resolution.py, test_context_assembler.py). Deviated to include the key name: `f"contract log event contains forbidden {key} at {path}"`. This preserves backward compatibility with the `"forbidden raw_payload"` regex while maintaining the unified single-pass check. Updated 3 existing test assertions that checked for `"full-text payload"` to check for `"forbidden {key}"` instead.

2. **provider_leak pattern fix (Task 02):** The plan's `provider_leak` pattern included `rate[_-]?limit` which would hard-block "Rate limit exceeded" (a rewrite fixture case) before the rewrite rule could match. Removed `rate[_-]?limit` from `provider_leak` and `context window exceeded` from `api_error` to prevent hard-block/rewrite overlap. The rewrite rules `rate_limit_notice` and `context_window` now correctly catch these cases.

3. **model[:\s] pattern lookahead (Task 02):** The plan's `model[:\s]` with trailing `\b` was logically flawed — it did NOT match "model: glm" (should block) but DID match "model clause" (should allow), because `\b` after `:` fails (non-word to non-word) but `\b` after space succeeds (non-word to word). Fixed by replacing the trailing `\b` with `(?!\w)` negative lookahead for the `provider_leak` pattern, which correctly blocks "model: glm" while allowing "model clause". Also fixed `token[_-]?usage` to `token[_\s-]?usage` to match "token usage" with space separator.

## EXECUTION COMPLETE
