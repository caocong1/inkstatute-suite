---
phase: 60-qq-event-normalization
plan: 02
subsystem: api
tags: [qqbot, gateway-envelope, adapter-delegation, normalize-inbound, backward-compat, ast-import-isolation]

# Dependency graph
requires:
  - phase: 60-qq-event-normalization
    plan: 01
    provides: normalization.py with parse_envelope, normalize_message_event, normalize_interaction_event, QQBotEventCategory
provides:
  - adapter.py normalize_inbound gateway envelope delegation to normalization.py
  - _is_gateway_envelope detection function (op+d keys)
  - _normalize_gateway_envelope dispatcher (lazy import from .normalization)
  - test_adapter_normalize.py with 7 tests covering all gateway categories + legacy backward compat
  - test_no_wecom_import.py extended with normalization.py AST import-isolation coverage
affects: [64-ingress-runtime, 65-egress-sender]

# Tech tracking
tech-stack:
  added: []
  patterns: [gateway-envelope-detection, lazy-import-delegation, backward-compat-preservation, ast-import-isolation-coverage]

key-files:
  created:
    - packages/channels/qqbot/tests/test_adapter_normalize.py
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
    - packages/channels/qqbot/tests/test_no_wecom_import.py

key-decisions:
  - "_is_gateway_envelope checks for op+d keys (not op+t+d) because op=13 validation challenge envelopes lack the t field — real QQ Bot gateway structure"
  - "Lazy import from .normalization inside _normalize_gateway_envelope function body avoids circular import risk between adapter.py and normalization.py"
  - "Legacy fixture path preserved unchanged — _is_gateway_envelope returns False for payloads without op/d keys, so existing _turn_from_payload/_feedback_from_payload path is taken"

patterns-established:
  - "Gateway envelope detection: _is_gateway_envelope checks for op+d presence to separate real gateway envelopes from legacy fixture format"
  - "Lazy import delegation: _normalize_gateway_envelope imports from .normalization inside function body to avoid circular imports"
  - "Metadata structure consistency: gateway path uses same metadata keys (channel_id, payload_ref, normalized_type, idempotency_key, fixture_only) as legacy path"

requirements-completed:
  - INGRESS-03
  - INGRESS-04
  - INGRESS-05

# Metrics
duration: 51min
completed: 2026-07-07
---

# Phase 60 Plan 02: Adapter Gateway Envelope Delegation Summary

**adapter.py normalize_inbound delegates real QQ Bot gateway envelopes to normalization.py pure functions while preserving legacy fixture backward compatibility**

## Performance

- **Duration:** 51 min
- **Started:** 2026-07-07T18:48:29Z
- **Completed:** 2026-07-07T19:39:53Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Wired adapter.py normalize_inbound to detect real QQ Bot gateway envelopes ({op, d}) and delegate to normalization.py parse_envelope + normalize_message_event/normalize_interaction_event
- Preserved backward compatibility with legacy fixture format — all existing tests (test_qqbot_channel_loop, test_qqbot_channel_adapter, test_qqbot_idempotency, etc.) remain green
- Created test_adapter_normalize.py with 7 tests covering C2C, GROUP_AT_MESSAGE, INTERACTION_CREATE, VALIDATION_CHALLENGE, UNKNOWN gateway envelopes plus legacy text and feedback backward compat
- Extended test_no_wecom_import.py with test_normalization_does_not_import_wecom_service AST inspection coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor adapter.py normalize_inbound + create test_adapter_normalize.py + extend test_no_wecom_import.py** - `1b749ca` (feat)

## Files Created/Modified
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` - Added _is_gateway_envelope and _normalize_gateway_envelope; refactored normalize_inbound to delegate gateway envelopes to normalization.py
- `packages/channels/qqbot/tests/test_adapter_normalize.py` - 7 unit tests for adapter normalize_inbound gateway delegation + legacy backward compat
- `packages/channels/qqbot/tests/test_no_wecom_import.py` - Added test_normalization_does_not_import_wecom_service AST import-isolation test

## Decisions Made
- Used op+d (not op+t+d) for _is_gateway_envelope detection because op=13 validation challenge envelopes lack the t field — this matches the real QQ Bot gateway structure where only op=0 dispatch events include t
- Lazy import from .normalization inside _normalize_gateway_envelope function body to avoid circular import risk between adapter.py and normalization.py
- Legacy fixture path preserved unchanged — _is_gateway_envelope returns False for payloads without op/d keys, so existing _turn_from_payload/_feedback_from_payload helpers handle legacy fixtures as before

## Deviations from Plan

### Auto-fixed Issues

**1. [Gateway Detection - op=13 Missing t] _is_gateway_envelope adjusted to check op+d instead of op+t+d**
- **Found during:** Task 1 (test_validation_envelope_returns_empty_normalized)
- **Issue:** Plan specified _is_gateway_envelope returns True only when all three keys op, t, d are present. But op=13 validation challenge envelopes lack the t field (real QQ Bot gateway structure), so they were not detected as gateway envelopes and fell through to the legacy path which crashed with "QQBot payload requires conversation_id"
- **Fix:** Changed _is_gateway_envelope to check for op+d presence (not requiring t). Legacy fixtures contain neither op nor d, so this cleanly separates gateway envelopes from the pre-normalized fixture format
- **Files modified:** packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
- **Verification:** test_validation_envelope_returns_empty_normalized passes; all acceptance criteria for _is_gateway_envelope still hold (True for {op:0,t:X,d:{}}, False for {type:message}, False for {})
- **Committed in:** 1b749ca (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 gateway detection fix)
**Impact on plan:** Auto-fix necessary for op=13 validation challenge handling. No scope creep — the acceptance criteria for _is_gateway_envelope still hold with the adjusted check.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- adapter.py normalize_inbound fully delegates real QQ Bot gateway envelopes to normalization.py
- All gateway envelope categories (C2C, GROUP_AT_MESSAGE, INTERACTION, VALIDATION_CHALLENGE, UNKNOWN) handled at adapter level
- Legacy fixture backward compatibility preserved — all existing tests green
- All 24 V2 gates green (ADAPTER-04 cross-cutting safety)
- Ready for Phase 64 (ingress-runtime) to wire the full production ingress flow

## Self-Check: PASSED

- Verified key-files.created exist on disk: test_adapter_normalize.py present
- `git log --oneline --all --grep="60-02"` returns >=1 commit (1b749ca)
- Re-ran all acceptance criteria:
  - test_adapter_normalize: 7/7 tests pass
  - test_no_wecom_import: 8/8 tests pass (including new normalization.py coverage)
  - test_qqbot_channel_loop: 9/9 tests pass (legacy fixture loop)
  - test_qqbot_channel_adapter: 13/13 tests pass (existing adapter tests)
  - test_v1_8_safety_baseline: 6/6 tests pass (dependencies=[], 4 FeedbackSource, 6 Protocol methods)
  - test_contract_freeze_not_violated: 8/8 tests pass
  - test_feedback_source_mapping: 8/8 tests pass
  - test_qqbot_idempotency: 7/7 tests pass
  - test_feature_flag: 8/8 tests pass
  - test_signature: 18/18 tests pass
  - test_ed25519_vectors: 8/8 tests pass
  - run_v2_gates.py: all 24 gates green

---
*Phase: 60-qq-event-normalization*
*Completed: 2026-07-07*
