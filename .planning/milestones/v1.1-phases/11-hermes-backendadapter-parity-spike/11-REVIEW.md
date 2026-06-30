---
phase: 11-hermes-backendadapter-parity-spike
status: clean
reviewed_at: 2026-06-29T00:24:00Z
depth: standard
files_reviewed: 16
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
---

# Phase 11 Code Review

## Scope

- `packages/backends/hermes/pyproject.toml`
- `packages/backends/hermes/README.md`
- `packages/backends/hermes/fixtures/parity_cases.json`
- `packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/config.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/probe.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/runs_api.py`
- `packages/backends/hermes/src/inkstatute_backends_hermes/parity.py`
- `packages/backends/hermes/tests/test_hermes_backend_adapter.py`
- `packages/backends/hermes/tests/test_capability_probe.py`
- `packages/backends/hermes/tests/test_runs_lane.py`
- `packages/backends/hermes/tests/test_parity_report.py`
- `packages/contract-test-suite/scripts/run_contract_tests.py`
- `packages/contract-test-suite/tests/test_phase11_hermes_parity.py`

## Findings

No open code review findings remain.

## Review Notes

- Pre-review fix applied in `d09c317`: API-run approvals now require explicit `api_approval_support=True`; otherwise non-high-risk approvals remain unsupported and do not call the transport.
- Hermes code stays under `packages/backends/hermes`; neutral `platform-runtime` source remains free of concrete Hermes imports.
- Probe implementation is dependency-injected and limited to `/health`, `/v1/capabilities`, and `/v1/models`.
- `/v1/runs` remains default-off and requires both enabled config and explicit adapter invocation mode.
- High-risk legal approval markers return a human-review rejection without runner or transport calls.
- Parity fixtures are refs/hashes only and report `promote_api_runs=False` for the intentional route mismatch.

## Verification Reviewed

- `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests packages/contract-test-suite/tests` - PASS
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_runs_lane.py` - PASS, 10 tests OK
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` - PASS, 30 tests OK
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py` - PASS, 110 tests OK

