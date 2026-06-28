---
phase: 04
slug: hermes-shadow-event-layer
status: implemented
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 04 - Validation Strategy

Per-phase validation contract for Hermes shadow event layer planning and execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| **Full suite command** | `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests packages/contract-test-suite/src packages/contract-test-suite/tests && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py && cd ../.. && PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| **Estimated runtime** | under 5 seconds in the current repo |

## Sampling Rate

- **After every task commit touching hook, mapper, writer, replay, or fixtures:** Run the quick command if service tests exist.
- **After every plan wave:** Run the full suite command.
- **Before verification:** Full suite must be green and Phase 4 stream fixtures must validate with zero broken required relationships.
- **Max feedback latency:** 10 seconds for local automated checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | REQ-hermes-contract-layer | T-04-01-I/R | Hook artifact sorts after `response_filter` and handler does not alter outbound context. | unit/source | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src python -m unittest discover -s services/hermes-contract-layer/tests -p 'test_hook.py' -v` | yes | passed |
| 04-02-01 | 02 | 2 | REQ-hermes-contract-layer, REQ-observability-and-replay | T-04-02-T/I/R | Mapper and writer produce schema-valid event payloads, monotonic log envelopes, and reference-first payload metadata. | unit/schema | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` | yes | passed |
| 04-03-01 | 03 | 3 | REQ-observability-and-replay | T-04-03-T/I | Phase 4 hook-output streams replay through contract-test-suite without fake FeedbackEvent records or privacy leakage. | unit/fixture | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | yes | passed |

## Wave 0 Requirements

- [x] `services/hermes-contract-layer/tests/` - service-local unittest suite exists before mapper/writer behavior is considered complete.
- [x] Contract-test-suite stream replay tests are added before Phase 4 claims hook-output replay support.
- [x] Phase 4 fixtures use `fixture://` or `raw_payload_ref` references only.

## Manual-Only Verifications

| Behavior | Requirement | Gate | Why Manual | Test Instructions |
|----------|-------------|------|------------|-------------------|
| Live Hermes profile deployment | REQ-hermes-contract-layer | deferred | Phase 4 creates repo-owned artifacts and local tests; live deployment would mutate external runtime state. | Defer to Phase 5 or explicit user deployment instruction. |
| Real WeCom task-to-reply loop | REQ-observability-and-replay | deferred | Phase 5 owns WeCom daily loop validation. | Run after Phase 4 artifacts are deployed into a test Hermes profile. |

## Validation Sign-Off

- [x] All planned tasks must have automated verify commands or explicit manual-only evidence gates.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 gaps are listed and phase-owned.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-28 for planning
