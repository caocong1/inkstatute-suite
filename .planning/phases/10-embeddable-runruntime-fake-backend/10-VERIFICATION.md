---
phase: 10-embeddable-runruntime-fake-backend
verified: 2026-06-28T20:28:12Z
status: gaps_found
score: 13/14 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Every run event/delta passes through the assistant output boundary before ordinary-user visibility."
    status: failed
    reason: "DefaultRunRuntime.stream invokes AssistantOutputBoundary.apply only when an event has visible text. A verifier spot-check streamed 4 events and observed only 1 boundary call, so non-text run events are yielded without boundary policy/audit."
    artifacts:
      - path: "packages/platform-runtime/src/platform_runtime/runtime.py"
        issue: "_apply_output_boundary returns non-visible events unchanged before calling output_boundary.apply."
      - path: "packages/platform-runtime/tests/test_output_boundary.py"
        issue: "Tests cover visible text in payload/metadata but do not prove boundary invocation or suppression for every yielded non-text run event."
    missing:
      - "Route every yielded RunEvent through boundary policy/audit, or explicitly filter non-user-visible events before yielding and test that contract."
      - "Add a regression test with state_changed plus message_delta events proving the boundary is applied to every yielded event, or that non-visible events are not ordinary-user output."
---

# Phase 10: Embeddable RunRuntime + Fake Backend Verification Report

**Phase Goal:** Implement `RunRuntime` as a dependency-injected, embeddable library and prove the full run lifecycle against fakes with no live system.
**Verified:** 2026-06-28T20:28:12Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `RunRuntime` implements create/poll/stream/cancel/approve against fake adapters. | VERIFIED | `DefaultRunRuntime` exposes all five async methods in `runtime.py`; `FakeBackendAdapter` implements submit/get/stream/cancel/approve/collect; `test_run_runtime_lifecycle.py` covers create, poll, stream, cancel, approve, and fake channel delivery. |
| 2 | Runtime constructs with zero channels and no network server. | VERIFIED | Constructor defaults `channels=()` and stores `tuple(channels)`; test asserts `runtime.channels == ()` and no `server` attribute. Fixture metadata also records `channels: []` and `server: none`. |
| 3 | Every run event/delta passes through assistant output boundary before ordinary-user visibility. | FAILED | `runtime.py` calls `_apply_output_boundary` for every backend event, but `_apply_output_boundary` returns events with no visible text unchanged before calling `output_boundary.apply`. Verifier spot-check: `events=4 boundary_calls=1`, event types `state_changed,state_changed,state_changed,message_delta`. |
| 4 | Leak fixtures prove meta/tool/approval/gateway-like visible notices never surface unchanged. | VERIFIED | `test_output_boundary.py` covers gateway lifecycle rewrites, tool/approval progress rewrites, command/debug/path/secret blocks, visible metadata scrubbing, and no original text in yielded events/audit metadata. |
| 5 | Contract-log store is append-only and raw_payload_ref-first. | VERIFIED | `InMemoryContractLogStore.append` assigns monotonic seq and clones entries; privacy validation rejects nested/top-level `raw_payload` and full-text keys; runtime logs `raw_payload_ref` and `content_sha256`; fixture uses refs/hashes only. |
| 6 | All new lanes are gated behind default-OFF feature flags. | VERIFIED | `RuntimeFeatureFlags` defines run, streaming, channel delivery, approval, and contract-log flags defaulting to `False`; tests prove default-off and explicit opt-in behavior. |
| 7 | Runtime dependencies are injected through neutral ports rather than concrete services. | VERIFIED | `ports.py` defines `RuntimeClock`, `IdFactory`, `ContractLogStore`, and `AssistantOutputBoundary` Protocols; runtime constructor accepts injected backend, channels, flags, store, boundary, clock, and ID factory. |
| 8 | Runtime support code is library-only with no server/channel/database/backend construction side effects. | VERIFIED | Source scan found no HTTP/server/database/queue construction in `packages/platform-runtime/src`; runtime construction only stores injected dependencies and defaults to in-memory/system helpers. |
| 9 | Runtime speaks only the `BackendAdapter` Protocol and embeds no backend-specific logic. | VERIFIED | `runtime.py` imports `BackendAdapter` from `protocols.py` and calls protocol methods; concrete leak names are absent from runtime source and are confined to tests. |
| 10 | Phase 10 lifecycle behavior is proven against fake adapters only, with explicit feature-flag opt-in. | VERIFIED | Runtime tests instantiate `DefaultRunRuntime` with `FakeBackendAdapter`, fake clock/IDs, optional fake channel, and explicit flags; default-off path proves no backend call. |
| 11 | Legal/business conclusions are not semantically rewritten when policy action is allow. | VERIFIED | Boundary tests assert allowed business and legal text are returned byte-for-byte unchanged. |
| 12 | Output-boundary decisions are recorded as sanitized audit metadata only. | VERIFIED | Boundary audit metadata contains rule id, hash prefix, input length, and privacy marker; tests assert blocked/rewrite originals are absent from audit metadata. |
| 13 | Fake runtime events validate through the existing contract-test-suite. | VERIFIED | Focused Phase 10 contract test validates the fixture and relationships; package runner passes all discovered contract tests including Phase 10. |
| 14 | Fixture evidence is embedded fake-only, zero-channel/no-server, and not live acceptance. | VERIFIED | Fixture metadata includes `runtime_mode: embedded`, `backend: fake`, `channels: []`, `server: none`, and `not_live_acceptance: true`; README states it is not live acceptance. |

**Score:** 13/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `packages/platform-runtime/src/platform_runtime/ports.py` | Neutral injected ports | VERIFIED | Protocols for clock, ID factory, contract log, and output boundary exist and are exported. |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | Default-off lane flags | VERIFIED | Five booleans default to `False`; `require_enabled` fails closed. |
| `packages/platform-runtime/src/platform_runtime/store.py` | Append-only ref-first store | VERIFIED | Monotonic seq, copy-safe reads, privacy rejection, and ref acceptance are tested. |
| `packages/platform-runtime/src/platform_runtime/runtime.py` | `DefaultRunRuntime` lifecycle | PARTIAL | Lifecycle and flag gates are implemented; boundary coverage for non-text stream events is incomplete. |
| `packages/platform-runtime/src/platform_runtime/fakes.py` | Fake backend/channel/clock/IDs | VERIFIED | Deterministic fakes implement protocol methods without network I/O. |
| `packages/platform-runtime/src/platform_runtime/output_boundary.py` | Assistant output boundary | VERIFIED | Allow/rewrite/block decisions and sanitized audit metadata are implemented. |
| `packages/contract-test-suite/fixtures/phase10_runruntime_fake_backend.json` | Sanitized fake runtime fixture | VERIFIED | Schema-valid fixture with refs, hashes, zero channels, no server, and not-live markers. |
| `packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py` | Contract replay checks | VERIFIED | Validates relationships, seq ordering, privacy, output-policy evidence, and fake-only metadata. |
| `packages/platform-runtime/README.md` | Fake-only runtime documentation | VERIFIED | Documents `DefaultRunRuntime`, `FakeBackendAdapter`, `RuntimeFeatureFlags`, zero channels, boundary, refs/hashes, and not live acceptance. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `DefaultRunRuntime` | `BackendAdapter` | Constructor injection and protocol method calls | WIRED | Runtime uses submit/get/stream/cancel/approval calls through the injected backend. |
| `DefaultRunRuntime.stream` | `AssistantOutputBoundary` | `_apply_output_boundary` | PARTIAL | Boundary is applied to visible text events, but non-text events are yielded unchanged without policy/audit. |
| `DefaultRunRuntime` | `InMemoryContractLogStore` | Injected `ContractLogStore.append` | WIRED | Create/cancel/approve append run and run_event records when `contract_log_enabled=True`; preflight prevents backend mutation without a store. |
| `RuntimeFeatureFlags` | Runtime lifecycle methods | `require_enabled` | WIRED | create/poll/stream/cancel/approve check runtime flag; stream and approve also check lane-specific flags. |
| Phase 10 fixture | Contract test suite | `test_phase10_runruntime_contracts.py` and runner path setup | WIRED | Focused and package-wide contract tests load and validate the fixture. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `DefaultRunRuntime.create_run` | `Run` | `FakeBackendAdapter.submit_run` then `get_run` | Yes | VERIFIED |
| `DefaultRunRuntime.stream` | `RunEvent` | `FakeBackendAdapter.stream_events` | Yes | PARTIAL - non-text events do not receive boundary decision metadata. |
| `DefaultRunRuntime.cancel` | cancelled `Run` | `FakeBackendAdapter.cancel_run` | Yes | VERIFIED |
| `DefaultRunRuntime.approve` | updated `Run` | `FakeBackendAdapter.submit_approval` | Yes | VERIFIED |
| `InMemoryContractLogStore` | log entries | runtime append calls and direct store append | Yes | VERIFIED |
| Phase 10 fixture | contract bundle | static sanitized JSON fixture | Yes | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Compile runtime, tests, contract tests, scripts | `python -m compileall packages/platform-runtime/src packages/platform-runtime/tests packages/contract-test-suite/tests packages/contract-test-suite/scripts` | exit 0 | PASS |
| Runtime unit suites | `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_feature_flags.py packages/platform-runtime/tests/test_contract_log_store.py packages/platform-runtime/tests/test_run_runtime_lifecycle.py packages/platform-runtime/tests/test_output_boundary.py` | exit 0, 35 tests OK | PASS |
| Focused Phase 10 contract tests | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py` | exit 0, 5 tests OK | PASS |
| Full contract-test-suite runner | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python packages/contract-test-suite/scripts/run_contract_tests.py` | exit 0, 107 tests OK | PASS |
| Exported runtime API surface | Python import spot-check for `DefaultRunRuntime`, fakes, flags, boundary, store | exit 0, exports ok | PASS |
| Default-off no side effect | Python spot-check calling `create_run` without opt-in | exit 0, backend not called | PASS |
| Contract-log privacy fail-closed | Python spot-check appending `raw_payload` | exit 0, privacy error raised | PASS |
| Boundary on every yielded stream event | Python spot-check with counting boundary | exit 0, `events=4 boundary_calls=1` | FAIL |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| None declared or discovered | `find scripts -path '*/tests/probe-*.sh' -type f` and phase artifact grep | no probes | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REQ-platform-run-runtime | 10-01, 10-02, 10-03, 10-04 | Python-first `RunRuntime` owns lifecycle, session/output boundary/audit/feature flags through injected ports. | PARTIAL | Lifecycle, audit, and flags are implemented and tested, but the output-boundary path does not cover every yielded run event. |
| REQ-runtime-embeddability | 10-01, 10-02, 10-04 | Embeddable library with no hard dependency on network server or specific channel. | SATISFIED | Zero-channel runtime construction, no server attribute, fake-only fixture metadata, and no live acceptance claims verified. |
| REQ-runlane-output-boundary | 10-03, 10-04 | Every run event/delta path must pass through assistant output boundary before ordinary-user delivery. | BLOCKED | Visible text deltas pass boundary; non-text stream events are yielded without `AssistantOutputBoundary.apply`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `packages/platform-runtime/src/platform_runtime/runtime.py` | 204 | empty dict initialization | INFO | Internal ID counter state, not a stub. |
| `packages/platform-runtime/src/platform_runtime/fakes.py` | 77-82, 127, 248 | empty list/dict initialization | INFO | In-memory fake adapter state, not user-visible stub data. |
| `packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py` | 182 | comparison to `[]` | INFO | Intentional zero-channel assertion, not hardcoded empty runtime output. |

### Human Verification Required

None. This phase is library/test/fixture scoped with no live service, UI, or external integration behavior to manually inspect.

### Gaps Summary

Phase 10 is mostly implemented and strongly tested, but the roadmap contract is not fully met because the runtime does not apply output-boundary policy to every yielded stream event. It only applies the boundary when visible text is found in payload or metadata. That is enough for the current leak-text tests, but not enough to prove "output boundary on every event/delta" before ordinary-user visibility.

Later Phase 12 will add channel and Web/SSE hosts, but this gap is not deferred: Phase 10 explicitly owns the fake runtime stream boundary contract.

---

_Verified: 2026-06-28T20:28:12Z_
_Verifier: the agent (gsd-verifier)_
