---
phase: 71
slug: smoke-protocol-path-hardening
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-10
---

# Phase 71 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) |
| **Config file** | none — explicit PYTHONPATH |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src:services/qqbot-service/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit.TestProtocolPathDryRun packages.channels.qqbot.tests.test_smoke_toolkit.TestProtocolEvidenceSanitized -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src:services/qqbot-service/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` then `python3 scripts/smoke_test.py --dry-run` |
| **Estimated runtime** | ~10–30s quick; full toolkit + CLI ~20–45s |

---

## Sampling Rate

- **After every task commit:** Run the plan-scoped unittest class listed in the task `<automated>` block
- **After every plan wave:** Run full `test_smoke_toolkit` + `python3 scripts/smoke_test.py --dry-run`
- **Before `/gsd-verify-work`:** Full toolkit green + dry-run CLI exits 0 with Protocol steps present
- **Max feedback latency:** 60 seconds for quick command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 71-01-01 | 01 | 1 | SMOKE-01 | T-71-01 / T-71-02 | RED Protocol-path dry-run tests | unit | `unittest …TestProtocolPathDryRun` (expect fail) | ✅ W0 existing file | ⬜ pending |
| 71-01-02 | 01 | 1 | SMOKE-01 | T-71-01 / T-71-02 | GREEN host Protocol dry-run stage | unit+CLI | `TestProtocolPathDryRun` + `smoke_test.py --dry-run` | ✅ | ⬜ pending |
| 71-02-01 | 02 | 2 | SMOKE-02 | T-71-04 / T-71-05 | RED Protocol evidence sanitize tests | unit | `unittest …TestProtocolEvidenceSanitized` (expect fail) | ✅ W0 existing file | ⬜ pending |
| 71-02-02 | 02 | 2 | SMOKE-02 | T-71-04 / T-71-06 | GREEN allowlist Protocol steps | unit+CLI | evidence tests + ban-list on evidence JSON | ✅ | ⬜ pending |
| 71-03-01 | 03 | 3 | SMOKE-01 / SMOKE-02 | T-71-07 / T-71-08 | CI honesty + runbook Protocol note | unit | `unittest …TestProtocolPathCiHonesty` | ✅ | ⬜ pending |
| 71-03-02 | 03 | 3 | SMOKE-01 / SMOKE-02 | T-71-07 / T-71-09 | Full toolkit + leaf+Protocol regression | unit+CLI | `unittest test_smoke_toolkit` + dry-run all steps ok | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing unittest infrastructure (`packages/channels/qqbot/tests/test_smoke_toolkit.py`) — Phase 67
- [x] Existing smoke CLI (`scripts/smoke_test.py`) — harden in place; no new framework
- [x] Existing `qqbot-channel` V2 gate discover covers toolkit tests — no new gate name
- [x] Host helpers from Phase 70 (`webhook.py`, `wiring.py`) available for import once `services/qqbot-service/src` is on path
- [x] Test classes created in-plan (71-01 / 71-02 / 71-03) — no separate Wave 0 stub plan required

*Existing infrastructure covers runners; new Protocol-path assertions are phase deliverables inside the existing toolkit file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | All Phase 71 behaviors have automated Fake/CLI verification. Live QQ `--live` remains Phase 72 HUMAN GATE. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests created in-plan on existing file)
- [x] No watch-mode flags
- [x] Feedback latency &lt; 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
