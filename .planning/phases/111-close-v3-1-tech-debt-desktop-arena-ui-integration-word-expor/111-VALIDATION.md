---
phase: 111
slug: close-v3-1-tech-debt-desktop-arena-ui-integration-word-expor
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-09
---

# Phase 111 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (TS)** | vitest ^3.0.0 (apps/desktop, packages/ui-core) |
| **Framework (Python)** | unittest stdlib (arena-service, arena-engine, contract-test-suite) |
| **Config file (desktop)** | apps/desktop/vite.config.ts (test.environment=jsdom, setupFiles=tests/setup.ts) |
| **Config file (ui-core)** | packages/ui-core/vite.config.ts |
| **Quick run command (desktop)** | `cd apps/desktop && npx vitest run` |
| **Quick run command (arena-service)** | `python -m unittest discover -s services/arena-service/tests` |
| **Quick run command (arena-engine)** | `python -m unittest discover -s packages/arena-engine/tests` |
| **Full suite command** | `python scripts/run_v2_gates.py` (41 gates) |
| **Estimated runtime** | ~120 seconds (full gate suite) |

---

## Sampling Rate

- **After every task commit:** Run the relevant quick command (desktop vitest OR arena-service unittest OR arena-engine unittest)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (full 41-gate suite)
- **Before `/gsd-verify-work`:** Full gate suite green (qqbot-channel recall test failure accepted as carry — 40 gates fully green + qqbot-channel green except recall test)
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 111-01-01 | 01 | 1 | UI-06 | — | N/A | unit (TS) | `cd packages/ui-core && npx vitest run tests/test_arena_stream.ts` | ✅ | ⬜ pending |
| 111-01-02 | 01 | 1 | UI-06 | — | N/A | source assertion | `grep -E "createArenaStream|arenaEventReducer|arenaMetaReducer" packages/ui-core/src/index.ts` | ✅ | ⬜ pending |
| 111-02-01 | 02 | 1 | SC-7 | T-111-01 | BackendAdapter method count reflects SAFE-06 addition | unit (Python) | `python -m unittest packages/channels/qqbot/tests/test_v1_8_safety_baseline.py packages/services/qqbot-service/tests/test_host_safety_baseline.py packages/contract-test-suite/tests/test_contract_count_freeze.py` | ✅ | ⬜ pending |
| 111-02-02 | 02 | 1 | SC-7 | T-111-01 | contract_freeze_baseline.json hash matches protocols.py | unit (Python) | `python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py` | ✅ | ⬜ pending |
| 111-03-01 | 03 | 2 | UI-01..UI-06 | — | N/A | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ W0 | ⬜ pending |
| 111-04-01 | 04 | 2 | UI-05, GATE-01 | T-111-02 | Export endpoint validates arena_id + delegates to agent-core (no re-implementation) | integration (Python) | `python -m unittest services/arena-service/tests/test_export_endpoint.py` | ❌ W0 | ⬜ pending |
| 111-05-01 | 05 | 3 | GATE-01, SC-8 | T-111-02 | E2E export flow: create → stream → synthesis → export docx (mocked track-changes) | integration (Python) | `python -m unittest packages/contract-test-suite/tests/test_arena_e2e.py` | ✅ (add test) | ⬜ pending |
| 111-06-01 | 06 | 3 | UI-05 | T-111-03 | onExport calls export endpoint + writes docx via desktopFileAdapter | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ W0 | ⬜ pending |
| 111-07-01 | 07 | 3 | SC-9 | — | All 41 gates green (recall carry accepted) | gate suite | `python scripts/run_v2_gates.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/desktop/tests/arena-page.test.tsx` — stubs for UI-01..UI-06 (arena page wiring with mocked arena client + SSE)
- [ ] `apps/desktop/src/config/arena.ts` — arena-service PlatformApiClient (needed before arena-page test)
- [ ] `packages/ui-core/src/index.ts` — add exports for `createArenaStream`, `ArenaStreamStore`, `arenaEventReducer`, `arenaMetaReducer` (needed before desktop can import them)
- [ ] `services/arena-service/tests/test_export_endpoint.py` — export endpoint integration test (mocked track-changes)
- [ ] `packages/contract-test-suite/tests/test_arena_e2e.py` — add `test_export_flow` test covering create → stream → synthesis → export docx (GATE-01 / SC-8); mock `_load_trackchanges_module` or set `INKSTATUTE_TRACKCHANGES_SCRIPT` to a fixture
- [ ] Test-fix: update 4 BackendAdapter count assertions (9→10) + `contract_freeze_baseline.json` hash — no new files, just edits

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Arena page visible in desktop app with real arena-service running | UI-01..UI-07 | Requires running arena-service + real ACP agent subprocesses | Launch arena-service + desktop app, navigate to arena page, create a workflow, observe streaming |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
