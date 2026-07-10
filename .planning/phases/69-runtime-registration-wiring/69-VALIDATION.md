---
phase: 69
slug: runtime-registration-wiring
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-10
---

# Phase 69 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) |
| **Config file** | none — explicit PYTHONPATH |
| **Quick run command** | `PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src" python3 -m unittest discover -s services/qqbot-service/tests -v` |
| **Full suite command** | `python3 scripts/run_v2_gates.py` (at minimum gate `qqbot-service`; optionally `qqbot-channel` + `gate-coverage-meta-test`) |
| **Estimated runtime** | ~10–20s quick; full gates longer |

---

## Sampling Rate

- **After every task commit:** Run quick unittest discover for `services/qqbot-service/tests`
- **After every plan wave:** Run `qqbot-service` gate (or full `run_v2_gates.py`)
- **Before `/gsd-verify-work`:** Full suite / host discover must be green
- **Max feedback latency:** 60 seconds for quick command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 69-01-01 | 01 | 1 | REG-01 | T-69-01 / T-69-03 | Flag→config mapping tests (RED) | unit | `unittest discover -p 'test_wiring_flag_config.py'` | ❌ W0→in-plan | ✅ green |
| 69-01-02 | 01 | 1 | REG-01 | T-69-02 / T-69-04 | Factory injects transports only when live-ready | unit | same | ❌ W0→in-plan | ✅ green |
| 69-02-01 | 02 | 2 | REG-02 | T-69-05 | Explicit `channels=(adapter,)` + no platform-runtime qqbot import | unit | `unittest discover -p 'test_runtime_registration.py'` | ❌ W0→in-plan | ✅ green |
| 69-02-02 | 02 | 2 | REG-02 | T-69-06 | Full host discover regression | unit | `unittest discover -s services/qqbot-service/tests` | ✅ infra | ✅ green |
| 69-03-01 | 03 | 2 | HOST-03 | T-69-07 / T-69-08 | Disabled composed path 503/refuse + call_count==0 | unit | `unittest discover -p 'test_wiring_disabled_refuse.py'` | ❌ W0→in-plan | ✅ green |
| 69-03-02 | 03 | 2 | HOST-03 | T-69-07 | Full host suite green after refuse tests | unit | `unittest discover -s services/qqbot-service/tests` | ✅ infra | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing unittest + `qqbot-service` V2 gate PYTHONPATH (Phase 68) — no new framework
- [x] Test files created in-plan (69-01 / 69-02 / 69-03) — no separate Wave 0 stub plan required
- [x] `services/qqbot-service/tests/test_wiring_flag_config.py` — created in Plan 01
- [x] `services/qqbot-service/tests/test_runtime_registration.py` — created in Plan 02
- [x] `services/qqbot-service/tests/test_wiring_disabled_refuse.py` — created in Plan 03

*Existing infrastructure covers runners; new wiring tests are phase deliverables.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | All phase behaviors have automated verification. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests created in-plan)
- [x] No watch-mode flags
- [x] Feedback latency < 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-07-10 (passed)
