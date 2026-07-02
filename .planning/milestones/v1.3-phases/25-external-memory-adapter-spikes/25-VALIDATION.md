---
phase: 25
slug: external-memory-adapter-spikes
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
verified: 2026-07-02
---

# Phase 25 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` / pytest 9.1.1 |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase25_external_memory_adapter_spikes.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green and Phase 25 verification artifact must be present.
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | XMEM-01 | T-25-01 | Zep/Hindsight adapter spike evaluated behind sanitized adapter boundary without live legal payload | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` | Yes | green |
| 25-01-02 | 01 | 1 | XMEM-02 | T-25-02 | OpenViking/ReMe adapter spike evaluated behind sanitized adapter boundary without live legal payload | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` | Yes | green |
| 25-01-03 | 01 | 1 | XMEM-03 | T-25-03 | Mem0-style adapter spike evaluated behind sanitized adapter boundary without live legal payload | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` | Yes | green |
| 25-01-04 | 01 | 1 | XMEM-04 | T-25-04 | Spike comparison reports privacy, deletion/export, tenant isolation, human-review, latency, runbook, and procurement gates | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` | Yes | green |
| 25-01-05 | 01 | 1 | XMEM-05 | T-25-05 | Final recommendation states platform-native memory as default and defers all external adapters pending future gates | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_spikes.py` | Yes | green |
| 25-02-01 | 02 | 2 | XMEM-01..XMEM-05 | T-25-06 | Synthetic fixture represents sanitized spike comparison, final recommendation, and gate evidence using refs only | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase25_external_memory_adapter_spikes.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_memory_adapter_spikes.py` — covers XMEM-01 through XMEM-05.
- [x] `packages/contract-test-suite/fixtures/phase25_external_memory_adapter_spikes.json` — synthetic fixture.
- [x] `packages/contract-test-suite/tests/test_phase25_external_memory_adapter_spikes.py` — contract tests.
- [x] `.planning/phases/25-external-memory-adapter-spikes/25-VERIFICATION.md` — formal verification artifact.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live external provider UAT | XMEM-01..XMEM-05 | External providers are evaluated as sanitized spikes only; live provider execution is a future procurement gate | Do not claim live provider execution; keep spikes sanitized and adapter-boundary-only |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — all tasks verified; runtime and contract tests pass; Phase 25 verification artifact states sanitized spike scope only and defers external adapters.
