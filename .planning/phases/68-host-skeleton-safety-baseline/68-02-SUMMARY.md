---
phase: 68-host-skeleton-safety-baseline
plan: 02
subsystem: qqbot-host
tags: [qqbot, secrets, safety, host]

requires:
  - phase: 68-01
    provides: qqbot-service package skeleton and gate PYTHONPATH
provides:
  - QQBotHostConfig refs-only dataclass with from_env
  - resolve_secret_ref process-edge resolver with injected env
affects: [69, 70]

tech-stack:
  added: []
  patterns: [refs-only frozen dataclass, process-edge secret resolve with injected Mapping]

key-files:
  created:
    - services/qqbot-service/src/qqbot_service/config.py
    - services/qqbot-service/src/qqbot_service/secrets.py
    - services/qqbot-service/tests/test_secret_refs.py
  modified:
    - services/qqbot-service/src/qqbot_service/__init__.py
    - services/qqbot-service/README.md

key-decisions:
  - "secret://qqbot/app-secret maps to INKSTATUTE_QQBOT_CLIENT_SECRET (smoke live naming)"
  - "resolve_secret_ref never reads os.environ; callers inject env Mapping"

patterns-established:
  - "Pattern: host config stores *_ref only; values appear only from resolve_secret_ref"
  - "Pattern: fail-closed unknown secret:// paths return None without raising secret material"

requirements-completed: [SAFE-02]

duration: 10min
completed: 2026-07-10
---

# Phase 68 Plan 02: Secret Refs + Process-Edge Resolve Summary

**Host config stores secret references only; `resolve_secret_ref` returns values solely from an injected env mapping at process edge.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-10T04:23:25Z
- **Completed:** 2026-07-10T04:25:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added frozen `QQBotHostConfig` with `enabled=False` default and `*_ref` fields only.
- `from_env` reads REF keys / enable flag only; planted raw secret env keys never land on config or `asdict`.
- Implemented fail-closed `resolve_secret_ref` for `env:`, bare keys, and `secret://qqbot/*` map; README documents schemes.

## Task Commits

1. **Task 1–2 (RED):** `8c362eb` — test(68-02): add failing test for secret refs
2. **Task 1–2 (GREEN):** `de110ed` — feat(68-02): implement host secret refs and process-edge resolve

## Files Created/Modified

- `services/qqbot-service/src/qqbot_service/config.py` — refs-only host config
- `services/qqbot-service/src/qqbot_service/secrets.py` — process-edge resolver
- `services/qqbot-service/tests/test_secret_refs.py` — SAFE-02 proof tests
- `services/qqbot-service/__init__.py` — exports `QQBotHostConfig`, `resolve_secret_ref`
- `services/qqbot-service/README.md` — ref scheme + mapping table

## Decisions Made

- Mapped `secret://qqbot/app-secret` → `INKSTATUTE_QQBOT_CLIENT_SECRET` to align with smoke live env naming.
- Token path uses `INKSTATUTE_QQBOT_TOKEN` as documented host key.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED
