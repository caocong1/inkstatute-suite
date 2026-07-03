---
phase: 29
slug: wecom-runtime-integration
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 29 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` |
| **Full suite command** | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests && python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `test_session_memory_integration.py`.
- **After every plan wave:** Run full `services/wecom-service/tests/` discover.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-1 | 29 | 1 | MEM-11 | T-29-01 | `WeComSessionRuntime` accepts `Memory` and performs pre-turn recall via `_with_recall_context` | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` | Yes | green |
| 29-2 | 29 | 1 | MEM-11, MEM-13 | T-29-02 | Recall result injected as safe metadata (`memory_recall_summary`: refs + count only; raw texts stay in backend) | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` | Yes | green |
| 29-3 | 29 | 1 | MEM-11 | T-29-03 | Post-turn retention exposed as `finalize_memory()` | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` | Yes | green |
| 29-4 | 29 | 1 | MEM-15 | T-29-04 | Memory failures do not block response (`test_memory_failure_does_not_block_response`, default `fail_open`) | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` | Yes | green |
| 29-5 | 29 | 1 | MEM-12 | T-29-05 | Hermes one-shot adapter unchanged (no edits to `hermes-contract-layer`) | git | `git diff --quiet e1738de~1 e1738de -- services/hermes-contract-layer/` | Yes | green |
| 29-6 | 29 | 1 | MEM-19 | T-29-06 | V2 gate suite passes with no regressions | gate | `python scripts/run_v2_gates.py` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `services/wecom-service/src/wecom_service/memory_integration.py` — memory integration helpers.
- [x] `services/wecom-service/src/wecom_service/session_runtime.py` — `WeComSessionRuntime` accepts `Memory`, pre-turn recall, post-turn retention.
- [x] `services/wecom-service/tests/test_session_memory_integration.py` — 3 integration tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-11, MEM-12, MEM-13 | All phase behaviors have automated verification paths | N/A |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — 3 integration tests pass; 63 wecom-service tests pass; V2 gates green.
