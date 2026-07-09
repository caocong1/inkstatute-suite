---
phase: 64
slug: qqbotsessionruntime-qqbotingressruntime
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 64 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib, IsolatedAsyncioTestCase for async handle_turn / handle_callback) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing) |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_session_runtime packages.channels.qqbot.tests.test_ingress_runtime -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (session + ingress)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 64-W0-01 | 01 | 0 | SESS-01 | T-64-01 | Wave 0: RED stubs for QQBotSessionRuntime + RecordingRuntime create/resume | unit | `test -f packages/channels/qqbot/tests/test_session_runtime.py` | ❌ W0 | ⬜ pending |
| 64-W0-02 | 02 | 0 | SESS-01 | T-64-02 | Wave 0: RED stubs for QQBotRuntimeIngress callback wiring | unit | `test -f packages/channels/qqbot/tests/test_ingress_runtime.py` | ❌ W0 | ⬜ pending |
| 64-W0-03 | 03 | 0 | SESS-03 | T-64-03 | Wave 0: RED stubs for fail-open memory + orchestrator metadata | unit | `test -f packages/channels/qqbot/tests/test_session_memory_runtime.py` | ❌ W0 | ⬜ pending |
| 64-01-01 | 01 | 1 | SESS-01 | T-64-01 | handle_turn CONTINUE/START calls RunRuntime.create_run; metadata source qqbot | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_session_runtime -v` | ❌ W0 | ⬜ pending |
| 64-01-02 | 01 | 1 | SESS-02 | T-64-04 | pending clarification → resume_interrupt; duplicate answer ignored; expired interrupt | unit | same as 64-01-01 | ❌ W0 | ⬜ pending |
| 64-01-03 | 01 | 1 | SESS-02 | T-64-05 | c2c vs group conversation_id isolation (shared openid, no cross resume) | unit | same as 64-01-01 | ❌ W0 | ⬜ pending |
| 64-02-01 | 02 | 2 | SESS-01 | T-64-02 | ingress: sanitized C2C/GROUP fixture → SessionScope channel_id=qqbot → session runtime | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_ingress_runtime -v` | ❌ W0 | ⬜ pending |
| 64-02-02 | 02 | 2 | SESS-02 | T-64-04 | ingress pending clarification uses resume_interrupt not create_run | unit | same as 64-02-01 | ❌ W0 | ⬜ pending |
| 64-03-01 | 03 | 3 | SESS-03 | T-64-03 | MemoryOrchestrator.recall_and_assemble merges context refs before create_run | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_session_memory_runtime -v` | ❌ W0 | ⬜ pending |
| 64-03-02 | 03 | 3 | SESS-03 | T-64-06 | failing Memory / orchestrator still create_run (fail-open); finalize_memory retain fail-open | unit | same as 64-03-01 | ❌ W0 | ⬜ pending |
| 64-03-03 | 03 | 3 | (invariant) | T-64-07 | no wecom_service in session/ingress; dependencies=[]; contract freeze | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import packages.channels.qqbot.tests.test_v1_8_safety_baseline packages.channels.qqbot.tests.test_contract_freeze_not_violated -v` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_session_runtime.py` — RecordingRuntime + interrupt/continue/scene isolation (RED before `session_runtime.py`)
- [ ] `packages/channels/qqbot/tests/test_ingress_runtime.py` — callback → normalize → handle_turn (RED before `ingress_runtime.py`)
- [ ] `packages/channels/qqbot/tests/test_session_memory_runtime.py` — orchestrator metadata + fail-open (RED before memory wiring)
- [ ] Extend `test_no_wecom_import.py` AST coverage for `session_runtime.py` + `ingress_runtime.py`
- [ ] Privacy assertions: outcome/evidence and RunRequest.metadata contain refs only (no raw answer/legal full text keys)

*Existing unittest infrastructure in `packages/channels/qqbot/` covers framework setup.*

---

## Manual-Only Verifications

*No live QQ network required for Phase 64. Hosts inject Fake/Recording RunRuntime + InMemoryInterruptStore. Live end-to-end is Phase 65/67.*

Optional human gate (not blocking): after Phase 65 flag-on, send two clarification replies in C2C and confirm resume; send same openid in group and confirm separate session.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** researcher drafted 2026-07-09 — planner should map Wave 0 into 64-0x-PLAN.md
