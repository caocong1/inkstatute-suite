---
phase: 70-webhook-composition-path
plan: 01
subsystem: qqbot-host
tags: [qqbot, host, webhook, ack-first]

requires:
  - phase: 69-runtime-registration-wiring
    provides: build_qqbot_wired_runtime / QQBotWiredRuntime dual-knob DI
provides:
  - Pure ACK-first handle_qqbot_webhook_request
  - build_raw_inbound_from_http with exact request_body bytes
  - map_ack_to_http_response for op=13 / op=12 / refuse
  - Injectable post_ack_scheduler for HOST-02 ordering proofs
affects: [70-02-composition, 70-03-http-server]

tech-stack:
  added: []
  patterns:
    - "ACK-first: await only verify_and_ack before HTTP return; schedule post-ACK via injectable callable"
    - "Raw body identity: metadata.request_body is the same bytes object passed into the builder"

key-files:
  created:
    - services/qqbot-service/src/qqbot_service/webhook.py
    - services/qqbot-service/tests/test_webhook_ack_first.py
  modified: []

key-decisions:
  - "Handler is async and returns (status, body_bytes, headers); tests drive via asyncio.run"
  - "Plan 01 post-ACK thunk calls stub run_post_ack_composition; Plan 02 fills composition"
  - "bot_secret resolved via resolve_secret_ref(host_config.bot_secret_ref, env) at process edge"

patterns-established:
  - "Pure handler pattern (admin-web-ui style) — no port bind for unit proofs"
  - "RecordingScheduler proves thunk scheduled but not executed before return"

requirements-completed: [HOST-02]

duration: 2min
completed: 2026-07-10
---

# Phase 70 Plan 01: ACK-First Webhook Handler Summary

**Pure host webhook returns op=13 challenge / op=12 body ACK / refuse before any ingress work, with exact raw-body identity for signature verify.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-07-10T04:53:11Z
- **Completed:** 2026-07-10T04:54:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- HOST-02 ACK-first pure handler with Fake-only unit proofs
- Exact `request_body` byte identity preserved for Ed25519 verify
- Injectable scheduler proves post-ACK work is deferred until after HTTP return

## Task Commits

1. **Task 1: RED — ACK-first host webhook tests** - `a3f3bad` (test)
2. **Task 2: GREEN — pure webhook ACK handler** - `0e53ac4` (feat)

## Files Created/Modified

- `services/qqbot-service/src/qqbot_service/webhook.py` — pure handler + RawInbound builder + ACK mapper
- `services/qqbot-service/tests/test_webhook_ack_first.py` — HOST-02 Fake proofs

## Decisions Made

- Async pure handler; sync HTTP wrapper lands in Plan 03
- Stub `run_post_ack_composition` exported for Plan 02 to replace

## Deviations from Plan

None - plan executed exactly as written.

## Verification

```text
PYTHONPATH=... python3 -m unittest discover -s services/qqbot-service/tests -p 'test_webhook_ack_first.py' -v
# 7 tests OK
```

## Self-Check: PASSED

- FOUND: services/qqbot-service/src/qqbot_service/webhook.py
- FOUND: services/qqbot-service/tests/test_webhook_ack_first.py
- FOUND: a3f3bad
- FOUND: 0e53ac4
