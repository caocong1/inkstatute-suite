---
phase: 60
status: findings
depth: standard
reviewed_files: 10
critical_count: 0
warning_count: 2
info_count: 3
---

# Phase 60 — Code Review

**Reviewer:** gsd-code-reviewer (standard depth)
**Date:** 2026-07-07
**Verdict:** No critical issues. 2 warnings, 3 info findings.

## Files Reviewed (10)

**Created (7):**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py`
- `packages/channels/qqbot/tests/test_normalization.py`
- `packages/channels/qqbot/tests/test_adapter_normalize.py`
- `packages/channels/qqbot/fixtures/qqbot_c2c_message.json`
- `packages/channels/qqbot/fixtures/qqbot_group_at_message.json`
- `packages/channels/qqbot/fixtures/qqbot_interaction_create.json`
- `packages/channels/qqbot/fixtures/qqbot_validation_challenge.json`

**Modified (3):**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
- `packages/channels/qqbot/tests/test_no_wecom_import.py`
- `scripts/run_v2_gates.py`

## Findings

### Warning 1: Missing test coverage for guild (chat_type=0) interaction normalization

- **File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` (lines 228-238)
- **Issue:** The guild chat_type path is implemented but has no corresponding test in `test_normalization.py`
- **Impact:** Edge case handling is untested; guild interactions may fail in production
- **Recommendation:** Add `test_normalize_interaction_guild` test case covering chat_type=0 scenario

### Warning 2: Code duplication between normalization.py and adapter.py

- **Files:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` (lines 82-109) and `adapter.py` (lines 466-494)
- **Issue:** Helper functions `_optional_string`, `_required_string`, `_stable_id`, `_dataclass_from_mapping`, `_mapping_or_empty` are duplicated
- **Impact:** Maintenance burden; changes must be made in two places
- **Recommendation:** Consider extracting shared helpers to a common module or accept duplication as intentional for standalone normalization module (documented in line 78 comment)

### Info 1: Typo handling in QQ Bot API

- **File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` (lines 234, 244)
- **Issue:** Code handles "resoloved" typo in QQ Bot API (both "resolved" and "resoloved" checked)
- **Impact:** Defensive coding; appropriate for handling vendor API inconsistencies
- **Recommendation:** Document this workaround in comments for future maintainers

### Info 2: Empty string fallbacks in interaction normalization

- **File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` (lines 222, 226, 237, 238)
- **Issue:** User IDs and scene IDs fall back to empty strings when missing
- **Impact:** May produce invalid conversation_ids like "qqbot:guild::" for guild interactions
- **Recommendation:** Consider raising ValueError for missing required fields instead of silent empty string fallbacks

### Info 3: Fixture metadata consistency

- **Files:** All fixture JSON files
- **Issue:** Fixtures properly sanitized with `not_live_acceptance: true`, `evidence_scope: "sanitized_fixture_only"`, `raw_payload_policy: "raw_payload_ref_and_hashes_only"`
- **Impact:** Positive — follows security best practices
- **Recommendation:** None — this is exemplary

## Project Rule Compliance

- ✅ No wecom_service imports (verified via AST inspection in test_no_wecom_import.py)
- ✅ FeedbackSource enum not modified (uses only "card_button" from frozen enum)
- ✅ ChannelAdapter Protocol maintained (6 methods implemented in adapter.py)
- ✅ dependencies = [] invariant holds (stdlib only: hashlib, re, dataclasses, enum, typing)
- ✅ Raw payload references only (no sensitive full text stored)
- ✅ Structured parsing used (no ad hoc string parsing for envelope structure)

## Security Assessment

- No injection risks identified
- No sensitive data exposure (fixtures sanitized, raw_payload_ref used)
- Input validation present (required fields raise ValueError)
- Forbidden payload key checking in adapter.py (`_assert_no_forbidden_payload_keys`)

## Test Coverage

- Envelope parsing: Comprehensive (8 test cases)
- Message normalization: Good (C2C and group covered)
- Interaction normalization: Good (up, down, needs_fix, route_wrong, aliases covered)
- Edge cases: Missing guild chat_type=0 test
- Schema validation: Included via contract_test_suite
- Backward compatibility: Tested in test_adapter_normalize.py
