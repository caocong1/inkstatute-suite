---
phase: 65-adapter-integration-promote-to-real-io
plan: 01
subsystem: qqbot-adapter
tags: [qqbot, adapter, two-tier-ack, ingress, put_json]

requires:
  - phase: 59-qqbot-signature
    provides: Ed25519 verify_and_ack + make_signed_raw patterns
  - phase: 60-qqbot-normalization
    provides: INTERACTION_CREATE parse_envelope + interaction_id resolution
  - phase: 61-qqbot-token
    provides: TokenManager + FakeTokenTransport
  - phase: 62-qqbot-sender
    provides: FakeMessageTransport / UrllibMessageTransport POST path
provides:
  - "INGRESS-06 two-tier ACK: http_callback_ack_body op=12 + live PUT /interactions/{id}"
  - "sender.put_json + ack_interaction with interaction_id charset validation"
  - "_live_io_ready() gate (enabled + token_manager + transport)"
  - "Wave 0 test_adapter_real_io stubs for Plan 02 ADAPTER-01 honesty"
affects:
  - 65-02-adapter-real-io-honesty
  - 66-feedback-interaction-recall
  - 67-live-smoke

tech-stack:
  added: []
  patterns:
    - "Metadata-only QQ wire details on AckResponse (no Protocol edits)"
    - "Duck-typed put_json on qqbot-local transports (not channel-core)"
    - "Default-OFF live gate: enabled + token_manager + transport"

key-files:
  created:
    - packages/channels/qqbot/tests/test_adapter_two_tier_ack.py
    - packages/channels/qqbot/tests/test_adapter_real_io.py
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
    - packages/channels/qqbot/tests/test_sender.py

key-decisions:
  - "OQ-1: eager ack_interaction from verify_and_ack when _live_io_ready()"
  - "OQ-2: always set http_callback_ack_body={\"op\": 12} for verified non-op=13 dispatch"
  - "Webhook network_io stays False; interaction PUT tracked via interaction_ack_status"
  - "QQ duplicate code 3 treated non-fatal as interaction_ack_status=sent"

patterns-established:
  - "Pattern: two-tier ACK metadata keys (http_callback_ack_body, ack_tier, interaction_ack_*)"
  - "Pattern: _live_io_ready() shared gate for ACK PUT (Plan 02 reuses for capabilities/health)"

requirements-completed: [INGRESS-06, ADAPTER-02]

duration: 3min
completed: 2026-07-09
---

# Phase 65 Plan 01: Two-Tier ACK + PUT Seam Summary

**INGRESS-06 two-tier ACK with `http_callback_ack_body={"op":12}` and Fake-transport PUT `/interactions/{id}` behind default-OFF `_live_io_ready`**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-09T11:12:01Z
- **Completed:** 2026-07-09T11:14:53Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Wave 0 RED tests encode op=12 webhook body, live interaction PUT, and flag-off skip
- `FakeMessageTransport` / `UrllibMessageTransport` gain `put_json`; `ack_interaction` validates id charset
- `verify_and_ack` emits Tier-1 op=12 metadata always on verified dispatch; Tier-2 PUT only when live

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED two-tier ACK + real-IO stubs** - `db59098` (test)
2. **Task 2: sender put_json + ack_interaction helper** - `eecedc6` (feat)
3. **Task 3: verify_and_ack two-tier ACK wiring** - `cbeabc4` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_adapter_two_tier_ack.py` - INGRESS-06 unit coverage
- `packages/channels/qqbot/tests/test_adapter_real_io.py` - ADAPTER-01 Wave 0 stubs (Plan 02 greens)
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` - `put_json` + `ack_interaction`
- `packages/channels/qqbot/tests/test_sender.py` - PUT/ack_interaction unit tests
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` - `_live_io_ready` + two-tier ACK

## Decisions Made

- Eager interaction PUT from `verify_and_ack` when live (OQ-1 RESOLVED)
- Standardize webhook Reply body in metadata as `{"op": 12}` (OQ-2 RESOLVED)
- Keep webhook `network_io=False`; use `interaction_ack_status` for PUT evidence
- No Protocol / channel-core / platform-contract edits; `dependencies=[]` preserved

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `test_adapter_real_io` remains partially RED for capabilities/health/normalize honesty — expected Plan 02 scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can reuse `_live_io_ready()` for capabilities/health/normalize metadata honesty
- Phase 66 may no-op interaction PUT when `interaction_ack_status=="sent"`
- Host must write `AckResponse.metadata.http_callback_ack_body` on HTTP 200 for dispatch events

## Threat Flags

None — no new trust-boundary surface beyond plan threat model (PUT gated; id charset validated; tokens excluded from Ack metadata).

## Known Stubs

- `test_adapter_real_io.py` expectations for capabilities/health/normalize live metadata remain RED until Plan 02 (intentional Wave 0 stubs)

## Self-Check: PASSED

- FOUND: packages/channels/qqbot/tests/test_adapter_two_tier_ack.py
- FOUND: packages/channels/qqbot/tests/test_adapter_real_io.py
- FOUND: packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py (ack_interaction, put_json)
- FOUND: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py (http_callback_ack_body, _live_io_ready)
- FOUND: commit db59098
- FOUND: commit eecedc6
- FOUND: commit cbeabc4

---
*Phase: 65-adapter-integration-promote-to-real-io*
*Completed: 2026-07-09*
