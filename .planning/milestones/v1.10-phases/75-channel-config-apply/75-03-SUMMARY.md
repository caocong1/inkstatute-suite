---
phase: 75-channel-config-apply
plan: 03
subsystem: channel-config
tags: [qqbot, operator-config, store-wins, dual-knob, restart-to-apply, CHAN-01]

requires:
  - phase: 75-01
    provides: "operator_config_src on qqbot-service gate + Wave 0 test_store_apply scaffold"
  - phase: 73-operator-config-foundation
    provides: "OperatorConfigStore + QQBotChannelDoc refs-only schemas"
provides:
  - "QQBotHostConfig.from_operator_doc maps store qqbot fields (refs only)"
  - "load_qqbot_host_config store-wins-if-exists else from_env (OQ-1)"
  - "build_qqbot_wired_runtime optional config_store → host load at compose time"
  - "Restart-to-apply documented in qqbot-service README"
affects: [75-05, qqbot-host-compose]

tech-stack:
  added: []
  patterns:
    - "Store path.exists() gates SoT; missing file → from_env bootstrap"
    - "Materialize copies refs via normalize_config_secret_ref; resolve only at live injection"
    - "config_store supplies host_config only — dual-knob AND stays in build_qqbot_channel_config"

key-files:
  created: []
  modified:
    - services/qqbot-service/src/qqbot_service/config.py
    - services/qqbot-service/src/qqbot_service/wiring.py
    - services/qqbot-service/tests/test_store_apply.py
    - services/qqbot-service/README.md

key-decisions:
  - "OQ-1: store wins when store.path.exists(); else from_env — not content-heuristic overrides"
  - "from_operator_doc accepts Mapping or QQBotChannelDoc-shaped object; no RuntimeFeatureFlags import in config.py"
  - "When host_config is None, wiring always calls load_qqbot_host_config (store and/or env) rather than empty QQBotHostConfig()"
  - "MVP apply semantics remain restart_required — no hot-reload"

patterns-established:
  - "Host load helper lives beside from_env; wiring only adds optional config_store DI"
  - "T-75-06 proven by patching resolve_secret_ref during materialize"

requirements-completed: [CHAN-01, CHAN-03]

duration: 2min
completed: 2026-07-10
---

# Phase 75 Plan 03: QQ Store→Host Load Summary

**QQ host compose loads operator-config store when the file exists (else env), preserves dual-knob AND, and documents restart-to-apply.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-10T08:25:07Z
- **Completed:** 2026-07-10T08:27:10Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Added `QQBotHostConfig.from_operator_doc` + module-level `load_qqbot_host_config` with store-wins-if-exists precedence
- Extended `build_qqbot_wired_runtime` with optional `config_store`; host loads at compose when `host_config` is omitted
- Greened `test_store_apply` (store-on / env-fallback / dual-knob / no-resolve / wired store path)
- Documented restart-to-apply operator store load in qqbot-service README (no live acceptance claim)

## Task Commits

Each task was committed atomically:

1. **Task 1: QQBotHostConfig from operator doc + load_qqbot_host_config**
   - `91351b3` (test) — RED: extend store-apply for from_operator_doc, no-resolve, wiring config_store
   - `9a5cefe` (feat) — GREEN: from_operator_doc + load_qqbot_host_config
2. **Task 2: Wire build_qqbot_wired_runtime + README** — `a19e78b` (feat)

**Plan metadata:** `bc0451c` (docs: complete plan)

## Files Created/Modified

- `services/qqbot-service/src/qqbot_service/config.py` — `from_operator_doc` + `load_qqbot_host_config`
- `services/qqbot-service/src/qqbot_service/wiring.py` — optional `config_store` → host load
- `services/qqbot-service/tests/test_store_apply.py` — store/env/dual-knob/wiring proofs
- `services/qqbot-service/README.md` — restart-to-apply store apply section

## Decisions Made

- Store SoT gated by `path.exists()` only (OQ-1); empty/missing file uses `from_env`
- Wiring treats omitted `host_config` as “load via store/env helper” so compose-time DI matches process-start semantics
- Dual-knob AND left untouched in `build_qqbot_channel_config` (T-75-07)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Parallel Wave 2 agents touched `config_api.py` / WeCom files; this plan staged only qqbot-service paths.

## User Setup Required

None — no new external services or secrets. Operator store path remains `INKSTATUTE_OPERATOR_CONFIG_PATH` / default `.inkstatute/operator-config.json`.

## Known Stubs

None — store apply path is fully wired for QQ host compose.

## Threat Flags

None beyond plan register (T-75-06 mitigated by no-resolve materialize; T-75-07 dual-knob preserved).

## Next Phase Readiness

- QQ CHAN-01 ops→runtime gap closed for store→host load
- WeCom mirror owned by 75-04; SSR form by 75-05
- Ready for phase verification after remaining Wave 2/3 plans complete

## Self-Check: PASSED

- Files: config.py, wiring.py, test_store_apply.py, 75-03-SUMMARY.md present
- Commits: 91351b3, 9a5cefe, a19e78b present
- Symbols: from_operator_doc, load_qqbot_host_config, config_store, restart docs present
