---
phase: 67-one-click-smoke-test-toolkit
verified: 2026-07-09T12:18:56Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Live OpenAPI --live execution against real QQ Bot"
    addressed_in: "Operator HUMAN GATE (not a later phase)"
    evidence: "ROADMAP SC5 + 67-VALIDATION Manual-Only: live is HUMAN GATE and does not block phase verification; runbook documents operator live path"
human_verification: []
---

# Phase 67: One-Click Smoke-Test Toolkit Verification Report

**Phase Goal:** One-click smoke-test CLI with `--dry-run`, sanitized evidence, runbook; live is HUMAN GATE.
**Verified:** 2026-07-09T12:18:56Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | `scripts/smoke_test.py` CLI validates signature, sends text + markdown+keyboard, simulates callback, and collects sanitized evidence via env-var credential injection | ✓ VERIFIED | Dry-run CLI exit 0; steps `signature`/`send_text`(msg_type=0)/`send_keyboard`(msg_type=2)/`callback`(normalized) all `ok`; live path uses `load_live_credentials()` value env vars only |
| 2 | `--dry-run` mode runs without live QQ Bot platform connection (CI-able), validating envelope structure, signature logic, and evidence format with fixture credentials | ✓ VERIFIED | `python3 scripts/smoke_test.py --dry-run` exit 0; Fake transports only; `TestDryRunNoNetwork`/`TestDryRunEgress`/`TestDryRunCallback` green (9/9 toolkit tests) |
| 3 | `runbook/SMOKE_TEST_RUNBOOK.md` documents credential setup, env-var injection, command sequence, expected outputs, and evidence collection format | ✓ VERIFIED | Runbook present with env table (value vars, not `*_REF`), dry-run/live commands, expected outputs, evidence schema + archival path; `TestRunbookExists` green |
| 4 | Evidence output is sanitized (no tokens, no raw user payloads, no attachment URLs) | ✓ VERIFIED | Evidence file ban-list clean (`Authorization`, `access_token`, DEMO BotSecret, `fixture-token`, `http(s)://` absent); schema `inkstatute.qqbot.smoke_evidence.v1`; `TestEvidenceSanitized`/`TestEvidenceSchema` green |
| 5 | Live run remains a human gate (not an autonomous deliverable) | ✓ VERIFIED | Default mode dry-run; `--live` without env exits 1 with key names only (no secret echo); Urllib transports only after env validation; runbook + VALIDATION state live is HUMAN GATE / not required for CI |

**Score:** 5/5 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Live OpenAPI `--live` against real QQ | Operator HUMAN GATE (not a later phase) | ROADMAP SC5; 67-VALIDATION Manual-Only; runbook live section — does not block phase verification |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `scripts/smoke_test.py` | One-click smoke CLI (dry-run default + live fail-closed) | ✓ VERIFIED | Substantive (~700 LOC); wired to signature/sender/feedback; `sanitize_evidence` + `load_live_credentials` |
| `packages/channels/qqbot/tests/test_smoke_toolkit.py` | Seven named coverage classes | ✓ VERIFIED | All 9 tests green; discoverable under qqbot tests |
| `runbook/SMOKE_TEST_RUNBOOK.md` | Operator runbook | ✓ VERIFIED | Env, dry-run, live HUMAN GATE, expected outputs, evidence/archival |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `scripts/smoke_test.py` | `inkstatute_channels_qqbot.signature` | `derive_keypair` + `verify_callback_signature` DEMO vector | ✓ WIRED | DEMO vector step A present |
| `scripts/smoke_test.py` | `inkstatute_channels_qqbot.sender` | `build_*` + `FakeMessageTransport` / live Urllib | ✓ WIRED | Fake on dry-run; Urllib only after live env validation |
| `scripts/smoke_test.py` | `inkstatute_channels_qqbot.feedback_ingress` | `handle_feedback_callback` + fixture | ✓ WIRED | Normalize-only dry-run; no ACK PUT |
| `sanitize_evidence` | evidence JSON | allowlist + ban-list | ✓ WIRED | stdout + `--evidence-out` sanitized |
| `runbook/SMOKE_TEST_RUNBOOK.md` | `scripts/smoke_test.py` | documented commands + value env vars | ✓ WIRED | Commands and `INKSTATUTE_QQBOT_*` value vars present |
| `--live` | env value vars | fail-closed before Urllib | ✓ WIRED | Missing env → exit 1, key names only |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| dry-run evidence | `steps.*` | DEMO sig + Fake send + fixture callback | Yes (fixture/Fake results, hashed ids) | ✓ FLOWING |
| sanitize_evidence | allowlisted dict | recursive strip + step allowlist | Yes (structured, ban-list clean) | ✓ FLOWING |
| live credentials | `LIVE_ENV_KEYS` | `os.environ` value vars | Fail-closed when absent (tested); live network not exercised | ✓ FLOWING (gate path) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Toolkit unittests | `python3 -m unittest …test_smoke_toolkit -v` | 9 tests OK | ✓ PASS |
| Dry-run CLI | `python3 scripts/smoke_test.py --dry-run --evidence-out …` | exit 0; schema/mode/steps ok | ✓ PASS |
| Evidence ban-list | JSON scan for tokens/URLs/DEMO secret | clean | ✓ PASS |
| Live fail-closed | `python3 scripts/smoke_test.py --live` (cleared env) | exit 1; missing key names only | ✓ PASS |
| No wecom / deps=[] | safety baseline + source grep | green; `dependencies = []` | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| N/A | — | No `scripts/*/tests/probe-*.sh` declared for this phase | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| SMOKE-01 | 67-01, 67-03 | One-click CLI: signature + text + keyboard + callback + sanitized evidence; env-var credentials | ✓ SATISFIED | CLI + Fake/live paths + fail-closed env loader |
| SMOKE-02 | 67-01, 67-03 | `--dry-run` CI-able without live QQ | ✓ SATISFIED | Dry-run CLI + Fake transports + unittest green |
| SMOKE-03 | 67-02 | Operator runbook | ✓ SATISFIED | `runbook/SMOKE_TEST_RUNBOOK.md` + `TestRunbookExists` |
| SMOKE-04 | 67-02 | Sanitized structured evidence | ✓ SATISFIED | `sanitize_evidence` + ban-list tests + evidence file |

No orphaned phase-67 requirements found beyond SMOKE-01..04.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TBD/FIXME/XXX/TODO debt markers in phase artifacts | — | — |

### Human Verification Required

None required to close the phase. Live OpenAPI execution is an **operator HUMAN GATE** (documented in runbook / VALIDATION Manual-Only) and is **explicitly deferred** from autonomous phase delivery — it does not block `passed`.

Optional operator follow-up (non-blocking):

1. **Live smoke (HUMAN GATE)**  
   **Test:** Export five value env vars; obtain fresh `INKSTATUTE_QQBOT_REPLY_MSG_ID` within passive-reply window; run `python3 scripts/smoke_test.py --live --evidence-out /tmp/qqbot-smoke-live.json`.  
   **Expected:** Exit 0; sanitized evidence `mode=live`; optional ACK PUT only with real `--callback-json` interaction id.  
   **Why human:** Requires real QQ credentials and live network; must not run in CI.

### Gaps Summary

No gaps. All five roadmap success criteria are verified in code and by automated dry-run/fail-closed checks. Live QQ remains an intentional human gate outside the autonomous deliverable.

---

_Verified: 2026-07-09T12:18:56Z_
_Verifier: Claude (gsd-verifier)_
