---
phase: 40
slug: provider-model-adapter-prototype
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x / unittest (existing) |
| **Config file** | `packages/backends/provider_model/pyproject.toml` (new — Wave 1 creates) |
| **Quick run command** | `PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src python -m pytest packages/backends/provider_model/tests/ -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~90 seconds (13 gates including new provider-model-backend gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (provider-model-backend tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 13 gates)
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | ADAPTER-02 | — | Provider_model adapter package structure + ProviderModelBackendAdapter with 9 BackendAdapter methods + AgentBackendManifest (production_ready=false, no_channel_io=true, invocation_mode=direct_llm) | unit | `PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/provider_model/tests -p "test_adapter.py"` | ❌ W0 | ⬜ pending |
| 40-01-02 | 01 | 1 | ADAPTER-02 | — | Capability probe returns AdapterCapabilitySet with 14 fields (SAFETY-02 freeze) + probe checks openai SDK importability without importing it | unit | `PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/provider_model/tests -p "test_probe.py"` | ❌ W0 | ⬜ pending |
| 40-02-01 | 02 | 2 | ADAPTER-02 | — | OpenAIClientRunner with AsyncOpenAI lazy SDK import (importlib) + fixture-driven submit_run → AgentResult mapping + package imports cleanly without openai SDK installed | unit | `PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/provider_model/tests -p "test_runner.py"` | ❌ W0 | ⬜ pending |
| 40-02-02 | 02 | 2 | ADAPTER-02 | — | Error normalization on first failure (RateLimitError/AuthError/APIError → FAILED with ErrorInfo, no success flip) + error message sanitization (no model names, URLs, tokens) | unit | `PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/provider_model/tests -p "test_error_normalization.py"` | ❌ W0 | ⬜ pending |
| 40-03-01 | 03 | 3 | ADAPTER-03 | — | Output boundary fixture tests proving Codex + provider_model backend noise (function call traces, model names, API errors, rate-limit notices) is blocked or rewritten by DefaultAssistantOutputBoundary | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_output_boundary_backend_noise.py` | ❌ W0 | ⬜ pending |
| 40-03-02 | 03 | 3 | ADAPTER-02 | — | V2 gate integration (new provider-model-backend gate + compileall update + gate count 12→13) + contract-test-suite test feeding real build_provider_model_manifest() through select_agent_backend | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 40-03-03 | 03 | 3 | — | — | Contract freeze not violated (existing freeze tests green) + SAFETY-02 count freeze (9 methods, 14 fields, 6 channel methods) | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py packages/contract-test-suite/tests/test_contract_count_freeze.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 package structure is created as the first step of Plan 40-01 Task 01. The following files are created by that task:

- [ ] `packages/backends/provider_model/pyproject.toml` — package definition (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/README.md` — package readme (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` — package init (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/config.py` — ProviderModelBackendConfig (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` — AgentBackendManifest factory (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/probe.py` — capability probe (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` — ProviderModelBackendAdapter (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` — OpenAIClientRunner with lazy import (Plan 40-02 Task 01)
- [ ] `packages/backends/provider_model/tests/__init__.py` — test init (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/tests/test_adapter.py` — adapter tests (Plan 40-01 Task 01)
- [ ] `packages/backends/provider_model/tests/test_probe.py` — probe tests (Plan 40-01 Task 02)
- [ ] `packages/backends/provider_model/tests/test_runner.py` — runner tests (Plan 40-02 Task 01)
- [ ] `packages/backends/provider_model/tests/test_error_normalization.py` — error normalization tests (Plan 40-02 Task 02)
- [ ] `packages/backends/provider_model/tests/fixtures/` — JSON fixture files (Plan 40-02 Task 01)
- [ ] `packages/contract-test-suite/tests/test_provider_model_backend_contract.py` — contract tests (Plan 40-03 Task 02)
- [ ] `packages/contract-test-suite/tests/test_output_boundary_backend_noise.py` — output boundary noise tests (Plan 40-03 Task 01)

*No separate Wave 0 task needed — package structure is created inline by Plan 40-01 Task 01. Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — fixture-driven adapter tests with no real API calls required. The AsyncOpenAI lazy import is verified by importing the package with `openai` absent from `sys.modules`.*

---

## Validation Sign-Off

- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-04
