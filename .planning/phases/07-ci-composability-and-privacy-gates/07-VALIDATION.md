---
phase: 07
slug: ci-composability-and-privacy-gates
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 07 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` |
| Config file | none |
| Quick run command | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_coverage_report.py packages/contract-test-suite/tests/test_privacy_gates.py packages/contract-test-suite/tests/test_thin_layer_boundaries.py` |
| Full suite command | `python scripts/run_v2_gates.py` |
| Estimated runtime | under 60 seconds |

## Sampling Rate

- After every task commit: run the focused test command for files touched by the task.
- After every plan wave: run `python scripts/run_v2_gates.py` once it exists.
- Before `$gsd-verify-work`: run `python scripts/run_v2_gates.py` and `python -m compileall` through the runner.
- Max feedback latency: 60 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 07-01 | 1 | REQ-contract-test-suite, REQ-v2-thin-contract-layer | T-07-01-runner | Local gate command is authoritative and dependency-free | unit/integration | `python scripts/run_v2_gates.py --help` | W0 | pending |
| 07-01-02 | 07-01 | 1 | REQ-composability-validation | T-07-01-coverage | Coverage distinguishes fixture from missing runtime input | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_coverage_report.py` | W0 | pending |
| 07-01-03 | 07-01 | 1 | REQ-composability-validation | T-07-01-breakage | Relationship breakage threshold remains 5% | unit/integration | `python scripts/run_v2_gates.py` | W0 | pending |
| 07-02-01 | 07-02 | 2 | REQ-security-privacy-baseline | T-07-02-privacy | Data scan fails raw payload and secret leaks while preserving references | unit | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_privacy_gates.py` | W0 | pending |
| 07-02-02 | 07-02 | 2 | REQ-v2-thin-contract-layer | T-07-02-boundary | Platform contract has no service/Hermes imports | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_thin_layer_boundaries.py` | W0 | pending |
| 07-02-03 | 07-02 | 2 | REQ-composability-validation | T-07-02-composability | Legal and non-legal fixtures remain schema-valid with neutral top-level fields | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_composability.py` | W0 | pending |
| 07-03-01 | 07-03 | 3 | REQ-v2-thin-contract-layer | T-07-03-ci | GitHub Actions calls local runner only | text/unit | `python scripts/run_v2_gates.py` | W0 | pending |
| 07-03-02 | 07-03 | 3 | REQ-security-privacy-baseline | T-07-03-artifacts | CI uploads no raw logs, DBs, media, callback bodies, or customer docs | text/unit | `python scripts/run_v2_gates.py` | W0 | pending |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- stdlib `unittest` is already used in all packages and services;
- contract-suite fixture, schema, event-stream, and composability tests already exist;
- no new runtime dependency or test framework is required.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real lawyer-trial coverage at 95% paired AgentTurn/AgentResult | REQ-lawyer-trial-acceptance | Phase 8 owns real runtime logs and lawyer trial metrics | Confirm Phase 7 reports missing runtime input honestly; collect real sanitized runtime evidence in Phase 8. |

## Validation Sign-Off

- [x] All planned tasks have automated verification commands.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers existing infrastructure needs.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 60 seconds.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** planned 2026-06-28

