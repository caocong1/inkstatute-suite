---
phase: 68
slug: host-skeleton-safety-baseline
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-10
verified: 2026-07-10
---

# Phase 68 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) |
| **Config file** | none — explicit PYTHONPATH |
| **Quick run command** | `PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest discover -s services/qqbot-service/tests -v` |
| **Full suite command** | `python3 scripts/run_v2_gates.py` (must include new `qqbot-service` gate + `gate-coverage-meta-test` + `compileall`) |
| **Estimated runtime** | ~5–15s quick; full gates longer |

---

## Sampling Rate

- **After every task commit:** Run quick unittest discover for `services/qqbot-service/tests`
- **After every plan wave:** Run `python3 scripts/run_v2_gates.py` (or at minimum gates `qqbot-service`, `qqbot-channel`, `gate-coverage-meta-test`, `compileall`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for quick command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 68-01-01 | 01 | 1 | SAFE-01 | T-68-01 | Host package exists with `dependencies = []` | unit | `python3 -m unittest services/qqbot-service/tests/test_host_skeleton.py -v` (with PYTHONPATH) | ✅ | ✅ green |
| 68-01-02 | 01 | 1 | SAFE-01 | T-68-02 | New service src covered by V2 gate PYTHONPATH/compileall | unit/meta | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python3 -m unittest packages/contract-test-suite/tests/test_gate_coverage.py -v` | ✅ | ✅ green |
| 68-02-01 | 02 | 2 | SAFE-02 | T-68-03 | Host config stores refs only | unit | `... unittest ... test_secret_refs.py` | ✅ | ✅ green |
| 68-02-02 | 02 | 2 | SAFE-02 | T-68-04 | Values resolve only at process edge via injected env | unit | `... unittest ... test_secret_refs.py` | ✅ | ✅ green |
| 68-03-01 | 03 | 2 | SAFE-01 | T-68-05 | No `wecom_service` in host src | unit | `... unittest ... test_no_wecom_import.py` | ✅ | ✅ green |
| 68-03-02 | 03 | 2 | SAFE-01 | T-68-06 / T-68-07 | Protocol 6/9 frozen; `qqbot_channel_enabled` default False; Phase 08 present | unit | `... unittest ... test_host_safety_baseline.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `services/qqbot-service/tests/test_host_skeleton.py` — created in Plan 01 (with implementation)
- [x] `services/qqbot-service/tests/test_secret_refs.py` — created in Plan 02
- [x] `services/qqbot-service/tests/test_no_wecom_import.py` — created in Plan 03
- [x] `services/qqbot-service/tests/test_host_safety_baseline.py` — created in Plan 03

*Existing infrastructure (unittest + run_v2_gates) covers runners; new host tests are phase deliverables.*

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

**Approval:** verified 2026-07-10 — see `68-VERIFICATION.md` (status: passed)
