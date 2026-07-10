---
phase: 72
slug: controlled-live-integration
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-10
---

# Phase 72 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) |
| **Config file** | none — explicit PYTHONPATH |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src:services/qqbot-service/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit.TestLiveEnvFailClosed packages.channels.qqbot.tests.test_smoke_toolkit.TestLiveHumanGateHonesty packages.channels.qqbot.tests.test_smoke_toolkit.TestRunbookLiveEnablement -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src:services/qqbot-service/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` then `python3 scripts/smoke_test.py --dry-run` |
| **Estimated runtime** | ~10–30s quick; full toolkit + CLI ~20–45s |

---

## Sampling Rate

- **After every task commit:** Run the plan-scoped unittest class listed in the task `<automated>` block
- **After every plan wave:** Run quick command above + `python3 scripts/smoke_test.py --dry-run`
- **Before `/gsd-verify-work`:** Full toolkit green + dry-run CLI exits 0 with Protocol steps present + live honesty/runbook classes green
- **Max feedback latency:** 60 seconds for quick command

**Critical:** Phase verification must **not** require `scripts/smoke_test.py --live` or live QQ network evidence.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 72-01-01 | 01 | 1 | LIVE-01 | T-72-01 / T-72-02 | RED live human-gate honesty tests (no network) | unit | `unittest …TestLiveHumanGateHonesty` (expect fail or establish baseline) | ✅ W0 existing file | ⬜ pending |
| 72-01-02 | 01 | 1 | LIVE-01 | T-72-01 / T-72-03 | GREEN live path honesty stamps + fail-closed | unit+CLI | `TestLiveEnvFailClosed` + `TestLiveHumanGateHonesty` + `--live` cleared-env exit ≠0 | ✅ | ⬜ pending |
| 72-02-01 | 02 | 2 | LIVE-02 | T-72-05 / T-72-06 | RED runbook LIVE-02 cue tests | unit | `unittest …TestRunbookLiveEnablement` (expect fail) | ✅ W0 existing file | ⬜ pending |
| 72-02-02 | 02 | 2 | LIVE-02 | T-72-05 / T-72-07 / T-72-08 | GREEN runbook host enablement + dual-knob + ACK windows + Phase 5/8 carried | unit | `TestRunbookLiveEnablement` + cue python -c | ✅ | ⬜ pending |
| 72-02-03 | 02 | 2 | LIVE-01 / LIVE-02 | T-72-02 / T-72-04 | Full toolkit + dry-run regression; gates never --live | unit+CLI | `unittest test_smoke_toolkit` + `smoke_test.py --dry-run` + grep gates | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing unittest infrastructure (`packages/channels/qqbot/tests/test_smoke_toolkit.py`) — Phase 67/71
- [x] Existing smoke CLI (`scripts/smoke_test.py`) — honesty harden in place; no new framework
- [x] Existing `qqbot-channel` V2 gate discover covers toolkit tests — no new gate name
- [x] Existing runbook (`runbook/SMOKE_TEST_RUNBOOK.md`) — expand for LIVE-02
- [x] Existing `TestLiveEnvFailClosed` — reuse as LIVE-01 baseline
- [x] Test classes `TestLiveHumanGateHonesty` / `TestRunbookLiveEnablement` created in-plan — no separate Wave 0 stub plan

*Existing infrastructure covers runners; new honesty/runbook assertions are phase deliverables inside the existing toolkit file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator live QQ OpenAPI smoke | LIVE-01 (acceptance) | Requires real Bot credentials + fresh passive-reply `msg_id`; HUMAN GATE; never required for phase complete | 1. Export five value env vars from private store. 2. Obtain fresh `INKSTATUTE_QQBOT_REPLY_MSG_ID` within window. 3. `python3 scripts/smoke_test.py --live --evidence-out /tmp/qqbot-smoke-live.json`. 4. Confirm exit 0, `mode=live`, `not_live_acceptance=true`. 5. Optional human copy to `.planning/phases/72-controlled-live-integration/evidence/YYYYMMDD-smoke-live.json` (sanitized only). |
| Optional live interaction ACK PUT | LIVE-02 (ACK window) | Needs real INTERACTION_CREATE `interaction_id` | Run with `--callback-json` containing real interaction id; do not invent ids. |
| Phase 5 live WeCom UAT | — (carried) | Separate human gate; not Phase 72 | Do **not** mark complete from Phase 72. |
| Phase 8 lawyer trial | — (carried) | Separate human gate; not Phase 72 | Do **not** mark complete from Phase 72. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (tests created in-plan on existing file)
- [ ] No watch-mode flags
- [ ] Feedback latency &lt; 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter (draft until execute completes map statuses)
- [x] Live QQ network **not** required for autonomous phase completion
- [x] CI must not auto-claim live acceptance

**Approval:** pending execution
