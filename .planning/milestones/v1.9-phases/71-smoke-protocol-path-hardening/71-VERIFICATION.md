---
phase: 71-smoke-protocol-path-hardening
verified: 2026-07-10T05:14:30Z
status: passed
score: 10/10 must-haves verified
---

# Phase 71: Smoke Protocol-Path Hardening Verification Report

**Phase Goal:** CI dry-run proves the full adapter/session Protocol stack (not leaf helpers only) and emits sanitized non-acceptance evidence.
**Verified:** 2026-07-10T05:14:30Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `--dry-run` exercises verify_and_ack → ingress/session → deliver via host webhook helpers with Fake transports | ✓ VERIFIED | `_step_protocol_path_dry_run` calls `handle_qqbot_webhook_request` + `build_qqbot_wired_runtime`; `TestProtocolPathDryRun` green |
| 2 | Dry-run fails closed if Protocol steps missing/not ok — leaf-only insufficient | ✓ VERIFIED | `run_smoke` SystemExit on Protocol failure; `test_protocol_path_required_for_success` |
| 3 | Dry-run never constructs UrllibMessageTransport / UrllibTokenTransport | ✓ VERIFIED | Dry-run section AST/source asserts; Fake* outcome classes; `TestDryRunNoNetwork` |
| 4 | Evidence schema `inkstatute.qqbot.smoke_evidence.v1` with `not_live_acceptance=true` | ✓ VERIFIED | CLI evidence JSON + `TestProtocolEvidenceSanitized` / `TestEvidenceSchema` |
| 5 | Protocol steps allowlisted: adapter_ack / session_ingress / adapter_deliver (RESEARCH keys) | ✓ VERIFIED | `_STEP_KEY_ALLOW` + sanitize survival tests |
| 6 | Secrets/tokens/raw bodies/URLs/calls never appear in serialized evidence | ✓ VERIFIED | Ban-list asserts on dirty Protocol payload + CLI evidence |
| 7 | CI dry-run exits 0 without network / live env | ✓ VERIFIED | `TestProtocolPathCiHonesty.test_cli_dry_run_exits_zero`; INKSTATUTE_QQBOT_* stripped |
| 8 | Smoke uses same host helpers as webhook composition (no parallel leaf-only host-complete claim) | ✓ VERIFIED | Source imports `qqbot_service.webhook` / `wiring`; runbook + CI honesty tests |
| 9 | Runbook dry-run documents Protocol path + not_live_acceptance | ✓ VERIFIED | `runbook/SMOKE_TEST_RUNBOOK.md` + `test_runbook_documents_protocol_path` |
| 10 | Full toolkit leaf + Protocol regression green | ✓ VERIFIED | 19/19 `test_smoke_toolkit` OK; dry-run all required steps ok |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/smoke_test.py` | Protocol-path dry-run + allowlist | ✓ EXISTS + SUBSTANTIVE | Host path bootstrap; `_step_protocol_path_dry_run`; mandatory Protocol steps |
| `packages/channels/qqbot/tests/test_smoke_toolkit.py` | SMOKE-01/02 proofs | ✓ EXISTS + SUBSTANTIVE | TestProtocolPathDryRun, TestProtocolEvidenceSanitized, TestProtocolPathCiHonesty |
| `runbook/SMOKE_TEST_RUNBOOK.md` | Protocol dry-run note | ✓ EXISTS + SUBSTANTIVE | verify_and_ack → ingress/session → deliver documented |
| `71-01-SUMMARY.md` / `71-02-SUMMARY.md` / `71-03-SUMMARY.md` | Plan summaries | ✓ EXISTS | All three present |

**Artifacts:** 4/4 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `smoke_test.py` | `qqbot_service.webhook` | `handle_qqbot_webhook_request` | ✓ WIRED | Protocol dry-run stage |
| `smoke_test.py` | `qqbot_service.wiring` | `build_qqbot_wired_runtime` Fake DI | ✓ WIRED | Dual knobs ON + Fake transports |
| Protocol evidence | `_STEP_KEY_ALLOW` | `sanitize_evidence` | ✓ WIRED | RESEARCH key sets only |
| Runbook | dry-run CLI | Protocol documentation | ✓ WIRED | Operator-facing note |

**Wiring:** 4/4 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| SMOKE-01: Protocol-path dry-run via host helpers | ✓ SATISFIED | - |
| SMOKE-02: Sanitized non-acceptance Protocol evidence | ✓ SATISFIED | - |

**Coverage:** 2/2 requirements satisfied

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None in Phase 71 deliverables | — | — |

**Anti-patterns:** 0 found (0 blockers, 0 warnings)

Checked: no leaf-only host-complete claim; no Urllib in dry-run; no `not_live_acceptance=false` on dry-run; no live acceptance claimed.

## Human Verification Required

None for Phase 71 automated Fake/CLI proofs.

**Explicitly not claimed:** live QQ `--live` acceptance (Phase 72 HUMAN GATE). Do not treat dry-run exit 0 as live acceptance.

## Gaps Summary

**No gaps found** for Phase 71 goal achievement under Fake-only dry-run verification.

### Out-of-scope (not Phase 71 blockers)

1. **Phase 72** — controlled live `--live` HUMAN GATE (do not auto-claim)
2. Optional host `protocol_feedback` INTERACTION Protocol step — message path mandatory; leaf callback remains normalize-only
3. New `run_v2_gates.py` gate name — intentionally not added (reuse `qqbot-channel`)

## Test Summary

| Suite | Result |
|-------|--------|
| `TestProtocolPathDryRun` | 4/4 OK |
| `TestProtocolEvidenceSanitized` | 2/2 OK |
| `TestProtocolPathCiHonesty` | 4/4 OK |
| Full `test_smoke_toolkit` | 19/19 OK |
| `python3 scripts/smoke_test.py --dry-run` | exit 0; leaf + Protocol steps all ok; `not_live_acceptance=true` |
| Live QQ `--live` | NOT RUN (Phase 72 HUMAN GATE) |

### Smoke dry-run evidence steps (all ok)

`signature`, `send_text`, `send_keyboard`, `callback`, `adapter_ack`, `session_ingress`, `adapter_deliver`

## Plans Completed

| Plan | Summary | Key commits |
|------|---------|-------------|
| 71-01 | Mandatory Protocol-path dry-run via host helpers | `650ff3d` test, `5f18b99` feat, `46b8e0c` docs |
| 71-02 | Protocol evidence allowlist + sanitization | `caa256b` test, `d38133c` feat, `e9656bf` docs |
| 71-03 | CI honesty + runbook + full regression | `3d2524e` feat (+ verification-only Task 2) |

## Transition

`--no-transition` honored: Phase 72 **not** started; no live acceptance claimed; live remains HUMAN GATE.

## Recommended Fix Plans

None for Phase 71.

## Blockers

None.

---
*Verified: 2026-07-10*
*Verifier: gsd-executor (execute-phase --no-transition)*
