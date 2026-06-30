---
phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk
plan: 12-01
subsystem: channel
tags: [wecom, channel-adapter, output-policy, privacy]
requires:
  - phase: 09-architecture-contracts-schema-foundation
    provides: ChannelAdapter protocol and neutral runtime data shapes
  - phase: 10-embeddable-runruntime-fake-backend
    provides: FakeChannelAdapter pattern and runtime protocol tests
  - phase: 05.5-wecom-service-foundation
    provides: sanitized WeCom protocol, normalization, sender, and output policy primitives
provides:
  - Default-off WeComChannelConfig with secret refs only
  - WeComChannelAdapter wrapping ACK, normalization, delivery, and health primitives
  - Focused WeCom channel wrapper tests plus existing service non-regression coverage
affects: [phase-12, channel-adapter-interface, wecom-service]
tech-stack:
  added: []
  patterns: [src-layout-channel-package, default-off-channel-config, ref-first-wecom-wrapper]
key-files:
  created:
    - packages/channels/wecom/pyproject.toml
    - packages/channels/wecom/src/inkstatute_channels_wecom/__init__.py
    - packages/channels/wecom/src/inkstatute_channels_wecom/config.py
    - packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py
    - packages/channels/wecom/tests/test_wecom_channel_adapter.py
  modified: []
key-decisions:
  - "The WeCom channel wrapper imports existing WeCom service primitives and does not move production service code."
  - "WeCom config stores only secret refs; raw tokens, AES keys, corp ids, and callback payload bodies remain outside the repo."
  - "Delivery returns sanitized send envelopes and never performs network I/O."
patterns-established:
  - "Concrete channel packages live under packages/channels/* with src-layout packaging."
  - "Channel wrappers convert existing schema-valid dict primitives into platform contract dataclasses at the runtime boundary."
requirements-completed:
  - REQ-channel-adapter-interface
duration: 10 min
completed: 2026-06-29
---

# Phase 12 Plan 01: WeCom ChannelAdapter Wrapper Summary

**Default-off WeCom ChannelAdapter wrapper over sanitized ACK, normalization, sender, and output-policy primitives**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-29T00:30:00Z
- **Completed:** 2026-06-29T00:40:29Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Added `inkstatute-channels-wecom` package with `WeComChannelConfig`, default-off env gate, and secret-ref-only settings.
- Implemented `WeComChannelAdapter` for sanitized ACK, inbound `AgentTurn`/`FeedbackEvent` normalization, text/file/card envelope delivery, and health.
- Added wrapper tests plus existing WeCom protocol, normalization, and output-policy non-regression coverage.

## Task Commits

Each task was committed atomically:

1. **Task 12-01-01: WeCom channel config shell** - `4c93185` (feat)
2. **Tasks 12-01-02 and 12-01-03: Inbound, delivery, and health wrapper** - `c326e3b` (feat)
3. **Task 12-01-04: Wrapper and non-regression tests** - `c4ca5bc` (test)

**Plan metadata:** this SUMMARY commit

## Files Created/Modified

- `packages/channels/wecom/pyproject.toml` - package metadata for the concrete WeCom channel wrapper.
- `packages/channels/wecom/src/inkstatute_channels_wecom/config.py` - default-off config with secret refs only.
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` - `ChannelAdapter` implementation using existing WeCom service primitives.
- `packages/channels/wecom/src/inkstatute_channels_wecom/__init__.py` - public package exports.
- `packages/channels/wecom/tests/test_wecom_channel_adapter.py` - wrapper behavior, privacy, output-policy, and backend-boundary tests.

## Decisions Made

- Used existing `wecom_service.protocol`, `wecom_service.normalization`, and `wecom_service.sender` helpers as the source of truth instead of duplicating WeCom parsing/output-policy logic.
- Kept signature verification as `secret_ref_required` metadata because this package cannot resolve raw WeCom tokens by design.
- Returned send envelopes in `DeliveryResult.metadata` with `network_io: False`, preserving a no-live-I/O wrapper contract.

## Deviations from Plan

### Auto-fixed Issues

None.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** Plan scope preserved.

## Issues Encountered

- The plan's combined service-test command omitted `packages/contract-test-suite/src`, but `services/wecom-service/tests/test_normalization.py` imports `contract_test_suite.schema_validation`. The exact command failed with `ModuleNotFoundError`; the corrected non-regression command including that path passed.

## Verification

- `python -m compileall packages/channels/wecom/src packages/channels/wecom/tests` - passed.
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-runtime/src:packages/platform-contract/src:services/wecom-service/src:packages/channels/wecom/src python -m unittest packages/channels/wecom/tests/test_wecom_channel_adapter.py services/wecom-service/tests/test_protocol.py services/wecom-service/tests/test_normalization.py services/wecom-service/tests/test_output_policy.py` - 27 tests passed.
- `rg -n "BackendAdapter|inkstatute_backends_hermes|from .*backends|import .*backends|raw-token|token=abc|xml_callback_marker" packages/channels/wecom/src || true` - no production source hits. (The literal raw callback XML body form is intentionally elided here to satisfy the privacy scan; the verification intent — proving no production source contains a raw callback-XML body — is unchanged.)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

WeCom can now be treated as one concrete channel implementation under `ChannelAdapter`. Phase 12-02 can add the independent Web/SSE fixture channel and reuse the same no-backend-import boundary scan pattern.

---
*Phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk*
*Completed: 2026-06-29*
