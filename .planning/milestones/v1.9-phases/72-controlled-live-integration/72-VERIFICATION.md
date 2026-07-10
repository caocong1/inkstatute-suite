---
phase: 72-controlled-live-integration
verified: 2026-07-10T05:24:00Z
status: passed
score: 8/8 must-haves verified
no_transition: true
---

# Phase 72: Controlled Live Integration Verification Report

**Phase Goal:** Operators can run a controlled QQ live path with fail-closed env checks and documented enablement, while live acceptance remains an explicit HUMAN GATE.
**Verified:** 2026-07-10T05:24:00Z
**Status:** passed (autonomous proofs only — live QQ acceptance remains HUMAN GATE)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `--live` remains available with fail-closed env checks; missing keys listed by name only | ✓ VERIFIED | `load_live_credentials` + `TestLiveEnvFailClosed`; cleared-env `--live` exits non-zero |
| 2 | Live path explicitly marked HUMAN GATE; CI/phase complete must not auto-claim acceptance | ✓ VERIFIED | `--help` HUMAN GATE; `TestLiveHumanGateHonesty`; `sanitize_evidence` forces `not_live_acceptance=True` |
| 3 | Script never auto-claims live acceptance (`not_live_acceptance=true` always) | ✓ VERIFIED | `_run_smoke_live` stamp + sanitize force-True; tainted payload test |
| 4 | CI / V2 gates do not invoke `smoke_test.py --live` | ✓ VERIFIED | `test_ci_gates_do_not_invoke_live`; grep on `run_v2_gates.py` |
| 5 | Runbook documents host enablement (`CHANNEL_ENABLED`, `*_REF`) and dual-knob AND mapping | ✓ VERIFIED | `TestRunbookLiveEnablement.test_host_enablement_and_dual_knob` |
| 6 | Runbook documents dry-run vs live, ACK / passive-reply safety windows | ✓ VERIFIED | dry-run vs live + ACK/passive-reply cue tests |
| 7 | Live evidence archival path is Phase 72 sanitized human copy; not required for phase complete | ✓ VERIFIED | `.planning/phases/72-controlled-live-integration/evidence/` documented |
| 8 | Phase 5 live WeCom UAT and Phase 8 lawyer trial remain carried human gates | ✓ VERIFIED | Runbook “Carried human gates” section + cue test; **not** marked complete |

**Score:** 8/8 truths verified (without live QQ network)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/smoke_test.py` | Fail-closed `--live` + honesty stamps | ✓ EXISTS + SUBSTANTIVE | `load_live_credentials`, `_run_smoke_live`, sanitize force-True |
| `packages/channels/qqbot/tests/test_smoke_toolkit.py` | LIVE-01/02 honesty + runbook cues | ✓ EXISTS + SUBSTANTIVE | `TestLiveHumanGateHonesty`, `TestRunbookLiveEnablement` |
| `runbook/SMOKE_TEST_RUNBOOK.md` | LIVE-02 enablement docs | ✓ EXISTS + SUBSTANTIVE | Host enablement, dual-knob, ACK windows, Phase 5/8, archival |
| `72-01-SUMMARY.md` / `72-02-SUMMARY.md` | Plan summaries | ✓ EXISTS | Both present |

**Artifacts:** 4/4 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `smoke_test.py` | `load_live_credentials` | fail-closed before Urllib | ✓ WIRED | Env validated before transports |
| `test_smoke_toolkit.py` | `run_v2_gates.py` | CI honesty scan | ✓ WIRED | No `--live` smoke |
| `SMOKE_TEST_RUNBOOK.md` | `qqbot_service.wiring` | dual-knob docs | ✓ WIRED | Cross-link README |
| Runbook | Phase 5 / Phase 8 | carried-gate language | ✓ WIRED | Explicit not-v1.9-done |

**Wiring:** 4/4 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| LIVE-01: Controlled `--live` fail-closed + HUMAN GATE honesty | ✓ SATISFIED (autonomous proofs) | Live QQ acceptance remains HUMAN GATE |
| LIVE-02: Operator runbook enablement + ACK windows | ✓ SATISFIED | - |

**Coverage:** 2/2 requirements satisfied for autonomous phase goal. Live OpenAPI acceptance is **not** claimed.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None in Phase 72 deliverables | — | — |

**Anti-patterns:** 0 found

Checked: no live acceptance claimed; no Phase 5/8 marked complete; no `--live` in CI gates; no secrets in runbook; leaf OpenAPI live path preserved (no Protocol-path live rewrite).

## Human Verification Required (HUMAN GATE — remaining)

These remain **operator-only** and are **not** required for this verification pass:

1. **Controlled live QQ OpenAPI smoke** — export five value env vars; fresh passive-reply `msg_id`; `python3 scripts/smoke_test.py --live --evidence-out /tmp/qqbot-smoke-live.json`; confirm exit 0, `mode=live`, `not_live_acceptance=true`
2. **Optional live ACK PUT** — `--callback-json` with real INTERACTION `interaction_id` only (never invent ids)
3. **Optional sanitized archive** — human copy to `.planning/phases/72-controlled-live-integration/evidence/YYYYMMDD-smoke-live.json` (never required for CI/phase complete)
4. **Phase 5 live WeCom UAT** — carried human gate; **do not mark complete** from Phase 72
5. **Phase 8 lawyer trial** — carried human gate; **do not mark complete** from Phase 72

## Gaps Summary

**No gaps** for autonomous Phase 72 goal (LIVE-01/02 verifiable without live network).

### Explicitly not claimed

- Live QQ `--live` acceptance / operator archive
- Phase 5 WeCom UAT complete
- Phase 8 lawyer trial complete
- Host Protocol-path live rewrite (leaf OpenAPI `--live` preserved per RESEARCH R-01)

## Test Summary

| Suite | Result |
|-------|--------|
| `TestLiveEnvFailClosed` | 2/2 OK |
| `TestLiveHumanGateHonesty` | 4/4 OK |
| `TestRunbookLiveEnablement` | 6/6 OK |
| Full `test_smoke_toolkit` | 29/29 OK |
| `python3 scripts/smoke_test.py --dry-run` | exit 0; Protocol steps ok; `not_live_acceptance=true` |
| Cleared-env `python3 scripts/smoke_test.py --live` | exit ≠ 0; key names only |
| Live QQ `--live` against real hosts | **NOT RUN** (HUMAN GATE) |

## Plan Commits

| Plan | Commits |
|------|---------|
| 72-01 | `7def74b` test, `cae5021` feat, `cb8bc28` docs |
| 72-02 | `7ab1da4` test, `92b6710` feat |

## Verification Decision

**PASSED** — Phase 72 autonomous success criteria met. `--no-transition` honored: do not start next milestone from this report. Live acceptance and Phase 5/8 remain HUMAN GATE.
