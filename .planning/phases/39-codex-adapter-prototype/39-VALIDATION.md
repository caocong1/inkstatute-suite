---
phase: 39
slug: codex-adapter-prototype
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x / unittest (existing) |
| **Config file** | `packages/backends/codex/pyproject.toml` (new — Wave 0 creates) |
| **Quick run command** | `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m pytest packages/backends/codex/tests/ -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~80 seconds (12 gates including new codex-backend gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (codex-backend tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 12 gates)
- **Max feedback latency:** 80 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | ADAPTER-01 | — | Codex adapter package structure + CodexBackendAdapter with 9 BackendAdapter methods + AgentBackendManifest (production_ready=false, no_channel_io=true) | unit | `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_adapter.py"` | ❌ W0 | ⬜ pending |
| 39-01-02 | 01 | 1 | ADAPTER-01 | — | Capability probe returns AdapterCapabilitySet with 14 fields (SAFETY-02 freeze) | unit | `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_probe.py"` | ❌ W0 | ⬜ pending |
| 39-02-01 | 02 | 2 | ADAPTER-01 | — | CodexExecRunner parses codex exec --json JSONL output + fixture-driven submit_run → AgentResult mapping | unit | `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_runner.py"` | ❌ W0 | ⬜ pending |
| 39-02-02 | 02 | 2 | ADAPTER-01 | — | Error normalization on first failure (turn.failed/error → FAILED with ErrorInfo, no success flip) | unit | `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_error_normalization.py"` | ❌ W0 | ⬜ pending |
| 39-03-01 | 03 | 3 | ADAPTER-01 | — | V2 gate integration (new codex-backend gate + compileall update + gate count 11→12) | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 39-03-02 | 03 | 3 | — | — | Contract freeze not violated (existing freeze tests green) + SAFETY-02 count freeze (9 methods, 14 fields) | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py packages/contract-test-suite/tests/test_contract_count_freeze.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 package structure is created as the first step of Plan 39-01 Task 01. The following files are created by that task:

- [ ] `packages/backends/codex/pyproject.toml` — package definition (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/src/inkstatute_codex_backend/__init__.py` — package init (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/src/inkstatute_codex_backend/adapter.py` — CodexBackendAdapter (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/src/inkstatute_codex_backend/manifest.py` — AgentBackendManifest factory (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/src/inkstatute_codex_backend/probe.py` — capability probe (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/src/inkstatute_codex_backend/runner.py` — CodexExecRunner (Plan 39-02 Task 01)
- [ ] `packages/backends/codex/tests/test_adapter.py` — adapter tests (Plan 39-01 Task 01)
- [ ] `packages/backends/codex/tests/test_probe.py` — probe tests (Plan 39-01 Task 02)
- [ ] `packages/backends/codex/tests/test_runner.py` — runner tests (Plan 39-02 Task 01)
- [ ] `packages/backends/codex/tests/test_error_normalization.py` — error normalization tests (Plan 39-02 Task 02)
- [ ] `packages/backends/codex/tests/fixtures/` — JSONL fixture files (Plan 39-02 Task 01)

*No separate Wave 0 task needed — package structure is created inline by Plan 39-01 Task 01. Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — fixture-driven adapter tests with no real codex binary required.*

---

## Validation Sign-Off

- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-04
