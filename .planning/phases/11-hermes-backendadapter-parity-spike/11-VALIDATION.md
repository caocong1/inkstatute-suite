---
phase: 11
slug: hermes-backendadapter-parity-spike
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-29
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | `packages/backends/hermes/pyproject.toml` |
| **Quick run command** | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` |
| **Full suite command** | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py` |
| **Estimated runtime** | ~5 seconds locally |

---

## Sampling Rate

- **After every task commit:** Run the focused `python -m unittest ...` command named by the task.
- **After every plan wave:** Run `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests`.
- **Before `$gsd-verify-work`:** Run the full contract-test-suite command with `packages/backends/hermes/src` on `PYTHONPATH`.
- **Max feedback latency:** 30 seconds for focused suites.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | REQ-hermes-backend-adapter | T-11-01-concrete-boundary | Concrete Hermes code stays outside neutral runtime packages. | source/unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_hermes_backend_adapter.py` | W0 | pending |
| 11-01-02 | 01 | 1 | REQ-hermes-backend-adapter | T-11-01-oneshot-default | One-shot reduced capabilities are default and no channel I/O is declared. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_hermes_backend_adapter.py` | W0 | pending |
| 11-01-03 | 01 | 1 | REQ-hermes-backend-adapter | T-11-01-raw-transcript | Adapter result metadata uses refs/hashes, not transcripts. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_hermes_backend_adapter.py` | W0 | pending |
| 11-02-01 | 02 | 2 | REQ-adapter-capability-probe | T-11-02-mutating-probe | Probe only calls `/health`, `/v1/capabilities`, and `/v1/models`. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_capability_probe.py` | W0 | pending |
| 11-02-02 | 02 | 2 | REQ-adapter-capability-probe | T-11-02-probe-leak | Probe fallback audit reasons are sanitized. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_capability_probe.py` | W0 | pending |
| 11-02-03 | 02 | 2 | REQ-adapter-capability-probe | T-11-02-no-channel-io | Probe-derived capabilities preserve `no_channel_io=True`. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_capability_probe.py` | W0 | pending |
| 11-03-01 | 03 | 3 | REQ-hermes-run-parity-spike | T-11-03-default-off-runs | `/v1/runs` submission is refused unless `INKSTATUTE_HERMES_API_RUNS_ENABLED` is true. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_runs_lane.py` | W0 | pending |
| 11-03-02 | 03 | 3 | REQ-hermes-run-parity-spike | T-11-03-parity-false-positive | Parity report can fail without promoting API-run lane. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_parity_report.py` | W0 | pending |
| 11-03-03 | 03 | 3 | REQ-hermes-run-parity-spike | T-11-03-approval-safety | High-risk legal conclusion approval cannot auto-approve. | unit | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_runs_lane.py` | W0 | pending |
| 11-04-01 | 04 | 4 | REQ-hermes-run-parity-spike | T-11-04-fixture-privacy | Six parity fixtures contain only sanitized refs, hashes, and summaries. | unit/privacy | `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_parity_report.py` | W0 | pending |
| 11-04-02 | 04 | 4 | REQ-hermes-run-parity-spike | T-11-04-contract-integration | Phase 11 evidence participates in package verification without live acceptance claims. | contract | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py` | W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

Existing Python stdlib `unittest` infrastructure covers all phase requirements. No additional test framework installation is required.

---

## Manual-Only Verifications

All Phase 11 behaviors have automated verification. Live promotion of `/v1/runs` remains a later human gate and is not part of this phase.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 30s.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-29
