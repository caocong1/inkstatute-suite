---
phase: 22
slug: recall-orchestrator-context-injection
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
verified: 2026-07-02
---

# Phase 22 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` / pytest 9.1.1 |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase22_recall_orchestrator_context_injection.py' && PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_memory_runtime.py services/wecom-service/tests/test_ingress_memory_runtime.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green and Phase 22 verification artifact must be present.
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | REC-01 | T-22-01 | MemoryOrchestrator retrieves approved memory refs for resolved session scope before backend submission | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` | Yes | green |
| 22-01-02 | 01 | 1 | REC-02 | T-22-02 | ContextBundle carries memory refs, summary refs, recent turn refs, feedback correction refs, artifact refs, and output-policy refs only | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` | Yes | green |
| 22-01-03 | 01 | 1 | REC-03 | T-22-03 | Tenant/workspace/user/session scope isolation enforced with fail-closed behavior on cross-scope retrieval | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` | Yes | green |
| 22-01-04 | 01 | 1 | REC-04 | T-22-04 | MemoryUse evidence records selected memories and context-bundle association without raw legal/customer text | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` | Yes | green |
| 22-01-05 | 01 | 1 | REC-05 | T-22-05 | Ordinary WeCom continue/start flows can use the orchestrator while preserving interrupt resume and active-task behavior | integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_memory_runtime.py -q` | Yes | green |
| 22-02-01 | 02 | 2 | REC-01..REC-05 | T-22-06 | Synthetic fixture represents recall orchestrator evidence with refs-only source material and MemoryUse records | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase22_recall_orchestrator_context_injection.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | Yes | green |
| 25.1-01-01 | 25.1-01 | 1 | REC-01, REC-02, REC-05 | T-25.1-01 | WeCom continue/start paths invoke memory recall before backend submission | integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_memory_runtime.py -q` | Yes | green |
| 25.1-01-02 | 25.1-01 | 1 | REC-02, REC-05 | T-25.1-02 | Ingress passes optional memory and feedback-correction-ref dependencies into session runtime and attaches bounded refs-only context metadata | integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_ingress_memory_runtime.py -q` | Yes | green |
| 25.1-01-03 | 25.1-01 | 1 | REC-04 | T-25.1-03 | MemoryUse evidence failure is fail-closed or explicit degraded status, not silent fail-open | unit + integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest packages/platform-runtime/tests/test_memory_orchestrator.py services/wecom-service/tests/test_session_memory_runtime.py -q` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_memory_orchestrator.py` — covers REC-01 through REC-04.
- [x] `services/wecom-service/tests/test_session_memory_runtime.py` — covers REC-01, REC-02, REC-05 runtime wiring.
- [x] `services/wecom-service/tests/test_ingress_memory_runtime.py` — covers ingress memory dependency injection and refs-only metadata.
- [x] `packages/contract-test-suite/fixtures/phase22_recall_orchestrator_context_injection.json` — synthetic fixture.
- [x] `packages/contract-test-suite/tests/test_phase22_recall_orchestrator_context_injection.py` — contract tests.
- [x] `.planning/phases/22-recall-orchestrator-context-injection/22-VERIFICATION.md` — formal verification artifact.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live WeCom UAT | Carried Phase 5/8 gates | Requires operator-confirmed live WeCom environment and real lawyer trial evidence | Keep carried as human gate; do not claim closure from Phase 22 automated fixtures |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — all tasks verified; runtime, service, and contract tests pass; Phase 22 verification artifact references Phase 25.1-01 runtime wiring evidence.
