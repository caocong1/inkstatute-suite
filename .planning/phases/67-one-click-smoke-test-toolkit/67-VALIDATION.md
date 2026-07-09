---
phase: 67
slug: one-click-smoke-test-toolkit
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 67 — Validation Strategy

> Per-phase validation contract for smoke-toolkit sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib; asyncio where send/ack async) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (`dependencies = []`) |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v && python3 scripts/smoke_test.py --dry-run` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v && python3 scripts/smoke_test.py --dry-run` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's narrowed `<automated>` verify (sanitize-only / CLI dry-run / runbook file check as specified)
- **After every plan wave:** Run full suite command (qqbot discover + `scripts/smoke_test.py --dry-run`)
- **Before `/gsd-verify-work`:** Full suite must be green; **`--live` is not required**
- **Max feedback latency:** 40 seconds (matches estimated quick-run runtime; optional budget, not a hard CI timeout)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 67-W0-01 | 01 | 0 | SMOKE-01 | T-67-01 | Wave 0: RED stubs for smoke CLI dry-run step orchestration | unit | `test -f packages/channels/qqbot/tests/test_smoke_toolkit.py` | ❌ W0 | ⬜ pending |
| 67-W0-02 | 01 | 0 | SMOKE-04 | T-67-02 | Wave 0: RED stubs for evidence sanitization ban-list | unit | same file `TestEvidenceSanitized` | ❌ W0 | ⬜ pending |
| 67-W0-03 | 01 | 0 | SMOKE-03 | T-67-03 | Wave 0: RED stub asserting runbook path/sections | unit/file | `test_smoke_toolkit.TestRunbookExists` or `test -f runbook/SMOKE_TEST_RUNBOOK.md` | ❌ W0 | ⬜ pending |
| 67-01-01 | 01 | 1 | SMOKE-02 | T-67-01 | `--dry-run` uses Fake transports; signature DEMO vector passes; no live host required | unit + CLI | `… test_smoke_toolkit.TestDryRunNoNetwork` + `python3 scripts/smoke_test.py --dry-run` | ❌ W0 | ⬜ pending |
| 67-01-02 | 01 | 1 | SMOKE-01 | T-67-04 | Dry-run builds text + markdown+keyboard envelopes and records send steps | unit | `… test_smoke_toolkit.TestDryRunEgress` | ❌ W0 | ⬜ pending |
| 67-01-03 | 01 | 1 | SMOKE-01 | T-67-05 | Dry-run simulates INTERACTION callback via fixture → feedback normalize | unit | `… test_smoke_toolkit.TestDryRunCallback` | ❌ W0 | ⬜ pending |
| 67-02-01 | 02 | 2 | SMOKE-04 | T-67-02 | Evidence JSON has no tokens, Authorization, raw user payloads, attachment URLs | unit | `… test_smoke_toolkit.TestEvidenceSanitized` | ❌ W0 | ⬜ pending |
| 67-02-02 | 02 | 2 | SMOKE-04 | T-67-02 | Evidence schema stamps `mode`, `not_live_acceptance`, step ok flags | unit | `… test_smoke_toolkit.TestEvidenceSchema` | ❌ W0 | ⬜ pending |
| 67-02-03 | 02 | 2 | SMOKE-03 | T-67-03 | `runbook/SMOKE_TEST_RUNBOOK.md` documents env vars, commands, expected outputs, evidence format, human gate | file | `test -f runbook/SMOKE_TEST_RUNBOOK.md` + section grep/unittest | ❌ W0 | ⬜ pending |
| 67-03-01 | 03 | 3 | SMOKE-01 | T-67-06 | Live mode fails closed when env missing (no partial secret print) | unit | `… test_smoke_toolkit.TestLiveEnvFailClosed` | ❌ W0 | ⬜ pending |
| 67-03-02 | 03 | 3 | ADAPTER-03/04 | T-67-07 | no wecom imports; Protocol/platform-contract/channel-core untouched; deps=[] | unit | `… test_no_wecom_import test_contract_freeze_not_violated test_v1_8_safety_baseline` | ✅ | ⬜ pending |
| 67-03-03 | 03 | 3 | SMOKE-02 | T-67-01 | Existing `qqbot-channel` gate still green with new smoke tests | gate | `python3 scripts/run_v2_gates.py` (or qqbot discover subset) | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_smoke_toolkit.py` — dry-run orchestration, Fake transport assertions, evidence sanitize ban-list, live env fail-closed, runbook presence
- [ ] Stub or RED expectations for `scripts/smoke_test.py` CLI entry (implementation wave turns green)
- [ ] Stub or RED expectations for `runbook/SMOKE_TEST_RUNBOOK.md` required sections:
  - credential / env-var setup
  - dry-run command
  - live command (HUMAN GATE)
  - expected outputs
  - evidence format + archival guidance
- [ ] Privacy assertions: serialized evidence must not contain `Authorization`, `access_token`, BotSecret values, raw message `content`, or `http(s)://` attachment URLs
- [ ] Keep `test_no_wecom_import.py`, `test_contract_freeze_not_violated.py`, and Phase 58–66 qqbot suites green

*Existing unittest infrastructure covers framework setup; Wave 0 adds missing requirement-mapped files.*

---

## Manual-Only Verifications

*No live QQ network required for Phase 67 CI. Live `--live` execution is a HUMAN GATE and does not block phase verification.*

Human gate (not blocking phase complete):
1. Operator exports `INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_CLIENT_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`, `INKSTATUTE_QQBOT_USER_OPENID`, `INKSTATUTE_QQBOT_REPLY_MSG_ID` from a private secret store (never commit).
2. Within an active C2C passive-reply window, run `python3 scripts/smoke_test.py --live --evidence-out /tmp/qqbot-smoke.json`.
3. Confirm sanitized evidence: all steps `ok`, no secrets in file; optionally archive copy under `.planning/phases/67-one-click-smoke-test-toolkit/evidence/` per runbook.
4. Optional: paste a real INTERACTION_CREATE JSON via `--callback-json` to exercise live ACK PUT.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Live platform run explicitly manual-only (not phase gate)

**Approval:** researcher drafted 2026-07-09 — planner mapped Wave 0 into 67-01-PLAN.md (Task 1); Plans 02–03 green remaining classes
