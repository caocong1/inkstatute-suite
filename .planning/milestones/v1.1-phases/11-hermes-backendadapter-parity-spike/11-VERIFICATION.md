---
phase: 11-hermes-backendadapter-parity-spike
verified: 2026-06-29T00:27:00Z
status: passed
score: 12/12 must-haves verified
gaps: []
human_verification: []
---

# Phase 11: Hermes BackendAdapter + Parity Spike Verification Report

**Phase Goal:** Implement the Hermes `BackendAdapter` one-shot lane, non-mutating capability probe, default-off `/v1/runs` seam, and fixture-based lawfirm parity spike.
**Verified:** 2026-06-29T00:27:00Z
**Status:** passed

## Goal Achievement

Phase 11 achieved its goal. Hermes now exists as a concrete backend package outside neutral runtime code; one-shot remains the default lane; `/v1/runs` is testable only through an explicit default-off seam; and parity evidence refutes promotion by keeping `promote_api_runs=False` when route parity fails.

## Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Hermes is implemented as a concrete `BackendAdapter` outside neutral platform-runtime code. | VERIFIED | `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py`; neutral runtime scan reports no concrete Hermes imports. |
| 2 | One-shot is the default invocation lane and declares reduced capabilities. | VERIFIED | `build_hermes_oneshot_manifest()` returns `run_invocation_modes=["oneshot"]`, `no_channel_io=True`, and no streaming/cancel/approval/live/parallel support. |
| 3 | Adapter outputs use platform objects with refs/hashes rather than transcripts. | VERIFIED | `HermesBackendAdapter.submit_run` returns `RunHandle`/`Run`; metadata stores `raw_payload_ref`, `request_content_sha256`, artifact refs, trace refs, and sanitized runner metadata. |
| 4 | Adapter declares no channel I/O and performs no ordinary-user delivery. | VERIFIED | Manifest and capabilities set `no_channel_io=True`; adapter has no channel delivery methods or WeCom calls. |
| 5 | Startup probe uses only `/health`, `/v1/capabilities`, and `/v1/models`. | VERIFIED | `SAFE_PROBE_PATHS`; probe tests assert exact path order and no `/v1/runs` access. |
| 6 | Probe never creates or reads run-specific state. | VERIFIED | `HermesCapabilityProbe` only calls injected `get_json` for safe paths and contains no network/run-state client code. |
| 7 | Probe results map into `AdapterCapabilitySet` with `no_channel_io=True`. | VERIFIED | `test_capability_probe.py` covers partial and API-capable reports; manifest validation passes. |
| 8 | Probe failure falls back to one-shot with sanitized audit reason. | VERIFIED | Failing transport test with URL/token/private path text yields `fallback_reason="probe_endpoint_unavailable"` and no raw error text in repr. |
| 9 | `/v1/runs` is behind `INKSTATUTE_HERMES_API_RUNS_ENABLED` and is not default. | VERIFIED | `HermesBackendConfig.from_env`; disabled client raises before transport; adapter defaults to one-shot unless explicit `invocation_mode="runs_api"` plus enabled config/client. |
| 10 | API-run lane can be exercised by fixtures without promotion. | VERIFIED | `HermesRunsClient` fake transport tests and `parity_cases.json`; `ParityReport.default_lane` remains `oneshot`. |
| 11 | Approval cannot auto-approve high-risk legal conclusions. | VERIFIED | `is_high_risk_legal_approval`; high-risk approval tests record zero runner/transport calls and `approval_rejected="high_risk_legal_human_review_required"`. |
| 12 | Six sanitized parity fixtures compare required dimensions and keep one-shot default on failure. | VERIFIED | `parity_cases.json` has six required cases; evaluator checks route, skills/gates, tool trace, artifacts, output hash, output policy, states, feedback target; intentional route mismatch sets `promote_api_runs=False`. |

## Required Artifacts

| Artifact | Status | Notes |
|---|---|---|
| `packages/backends/hermes` package | VERIFIED | Stdlib-only source package and tests. |
| `HermesBackendConfig` | VERIFIED | Includes API-run env gate. |
| `HermesBackendAdapter` | VERIFIED | Implements all `BackendAdapter` methods. |
| `HermesCapabilityProbe` | VERIFIED | Non-mutating safe endpoint probe. |
| `HermesRunsClient` | VERIFIED | Default-off `/v1/runs` seam. |
| `ParityReport` evaluator | VERIFIED | Deterministic no-promotion-on-failure report. |
| Phase 11 contract-suite test | VERIFIED | `test_phase11_hermes_parity.py` included in runner. |
| Hermes backend README | VERIFIED | Documents one-shot default, probe endpoints, default-off flag, parity semantics, approval safety, and rollback. |

## Automated Checks

| Command | Result | Status |
|---|---|---|
| `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests packages/contract-test-suite/tests` | exit 0 | PASS |
| `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` | 30 tests OK | PASS |
| `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python -m unittest packages/contract-test-suite/tests/test_phase11_hermes_parity.py` | 3 tests OK | PASS |
| `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py` | 110 tests OK | PASS |
| Neutral runtime import scan | no `inkstatute_backends_hermes` or `HermesBackendAdapter` matches | PASS |
| Parity fixture forbidden-marker scan | no transcripts, token markers, private Hermes paths, runtime logs, or customer markers | PASS |
| Schema drift gate | `drift_detected=false` | PASS |
| Code review | `11-REVIEW.md` status clean | PASS |

## Requirement Traceability

| Requirement | Status | Evidence |
|---|---|---|
| `REQ-hermes-backend-adapter` | SATISFIED | Concrete Hermes package implements one-shot `BackendAdapter`; default remains one-shot; API-run lane is opt-in. |
| `REQ-adapter-capability-probe` | SATISFIED | Probe is injected, non-mutating, safe-endpoint-only, and falls back to one-shot with sanitized reasons. |
| `REQ-hermes-run-parity-spike` | SATISFIED | Six-case parity spike exists and currently refutes promotion (`promote_api_runs=False`) while preserving one-shot default. |

## Residual Risk

- `/v1/runs` is not promoted. The parity fixture intentionally records a route mismatch, so the safe operational state remains one-shot default with `INKSTATUTE_HERMES_API_RUNS_ENABLED` disabled.
- This is not live acceptance and does not replace any later human gate.
- Existing carried human gates from Phase 05 and Phase 08 remain open and unrelated to Phase 11 automated verification.

## Gaps Summary

No Phase 11 implementation gaps remain.

---
_Verified: 2026-06-29T00:27:00Z_
_Verifier: Codex inline verifier_
