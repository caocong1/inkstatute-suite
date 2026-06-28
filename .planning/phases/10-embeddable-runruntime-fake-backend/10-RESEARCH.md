# Phase 10: Embeddable RunRuntime + Fake Backend - Research

**Researched:** 2026-06-29
**Status:** Complete
**Mode:** Inline GSD research, no subagent spawn available

## Research Question

What does Phase 10 need to know before planning an embeddable, dependency-injected `RunRuntime` with fake adapters, default-off lanes, output-boundary enforcement, and append-only reference-first run logs?

## Findings

### Source of Truth and Phase Boundary

- `docs/requirements/V2-PRD.md` remains the active product source; V1 must not be reintroduced.
- Phase 10 is the first runtime-behavior phase for milestone v1.1. Phase 09 intentionally left `packages/platform-runtime` signature-only.
- Phase 10 must implement runtime behavior as an embeddable Python library, not as a server, channel gateway, Hermes rebuild, or live WeCom path.
- Phase 10 depends on Phase 09 contracts and must preserve the four North Star interfaces: `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, and `RunRuntime`.
- All new runtime lanes must stay behind default-off feature flags. Tests may enable flags explicitly to prove fake-backend behavior.
- Live promotion remains out of scope. Phase 10 proves behavior against fakes and sanitized fixtures only.

### Existing Codebase Shape

- `packages/platform-runtime/src/platform_runtime/protocols.py` defines signature-only Protocols and neutral data shapes for `RunRuntime`, `BackendAdapter`, `ChannelAdapter`, and `SolutionLoader`.
- `packages/platform-runtime/README.md` states runtime behavior is deferred to Phase 10 and the package has no dependencies.
- `packages/platform-contract/src/platform_contract/events.py` already provides contract dataclasses for `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `AgentTurn`, `AgentResult`, and channel objects.
- `packages/platform-contract/src/platform_contract/enums.py` defines the locked run states: `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`, plus `RunEventType` values for state, step, message delta, tool, approval, artifact, and error events.
- `services/wecom-service/src/wecom_service/output_policy.py` already models the assistant output boundary with `allow`, `rewrite`, and `block` decisions plus hash-only audit metadata. Runtime core should not import this service module, but the policy shape and fixture expectations are useful.
- `packages/contract-test-suite/fixtures/phase55_output_policy_cases.json` contains allow/rewrite/block examples for output-boundary behavior.
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` provides a prior append-only JSONL writer pattern with monotonic `seq`, but Phase 10 runtime should keep storage injected and not depend on Hermes services.

### Runtime Design Constraints

- Keep `packages/platform-runtime` standard-library-only and backend/channel-neutral.
- Do not import `services`, `wecom_service`, `hermes_contract_layer`, or concrete channel/backend packages from runtime core.
- Avoid concrete backend/channel names in `packages/platform-runtime/src` because the boundary allowlist scans neutral source files. Concrete leak samples belong in tests or sanitized contract-test-suite fixtures.
- Use dependency injection for backend, optional channels, output boundary, contract-log store, feature flags, clock, and id factory.
- Support construction with zero channels and no server. Channel adapters should be optional delivery sinks, not construction requirements.
- Use `platform_contract.events` dataclasses for persisted contract log records or deterministic fixture evidence, while preserving the existing runtime Protocol surface.
- Contract-log records must be append-only and reference-first: store `raw_payload_ref`, artifact refs, hashes, IDs, status, and sanitized metadata, never raw sensitive payload text by default.
- Output boundary must be applied to every user-visible run event and message delta before channel delivery or stream exposure. Blocked/rewritten events should record sanitized summaries or hash-only audit metadata.

### Missing Phase 10 Capabilities

- No concrete runtime class exists yet that satisfies `RunRuntime.create_run`, `poll`, `stream`, `cancel`, and `approve`.
- No feature-flag helper exists to ensure new runtime lanes default to off.
- No runtime-owned output-boundary port exists in `platform-runtime`.
- No append-only runtime contract log store exists under `platform-runtime`.
- No fake backend or fake channel adapters exist to prove lifecycle behavior without a live system.
- No Phase 10 contract-test-suite fixture proves `ChannelMessage -> AgentTurn -> Run -> RunEvent/RunStep -> AgentResult/ArtifactRecord -> ChannelDelivery` behavior for a fake run.

## Proposed Plan Architecture

### Plan 10-01: Runtime Ports, Feature Flags, and Store

Add injected runtime ports, default-off feature flags, hash-only audit helpers, and an append-only in-memory contract log store. Keep the package dependency-free and neutral.

### Plan 10-02: Fake Adapters and Lifecycle Runtime

Implement fake backend/channel adapters and a concrete runtime class that supports create, poll, cancel, and approve against fakes with no server and optional zero channels.

### Plan 10-03: Streaming Output Boundary

Route every stream event and message delta through an injected output boundary. Add leak tests proving backend meta/tool/approval/gateway-like text is blocked or rewritten before ordinary-user visibility, without rewriting business/legal conclusions.

### Plan 10-04: Contract Fixture and Replay Evidence

Add a sanitized Phase 10 fake-runtime fixture and focused contract-test-suite coverage that proves append-only event ordering, reference-first payload handling, and relationship integrity.

## Verification Strategy

| Proof | Command or Assertion |
|-------|----------------------|
| Runtime package compiles | `python -m compileall packages/platform-runtime/src packages/platform-runtime/tests` |
| Runtime lifecycle passes against fakes | `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_run_runtime_lifecycle.py` |
| Feature flags default off | focused tests in `packages/platform-runtime/tests/test_feature_flags.py` |
| Append-only logs are reference-first | focused tests in `packages/platform-runtime/tests/test_contract_log_store.py` |
| Output boundary filters all visible stream deltas | focused tests in `packages/platform-runtime/tests/test_output_boundary.py` |
| Contract fixture validates | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py` |
| Existing contract suite still passes | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python packages/contract-test-suite/scripts/run_contract_tests.py` |
| Neutral package boundary still passes | focused boundary allowlist tests continue to pass on `packages/platform-runtime/src` |

## Risks

- Runtime code can accidentally become a server or channel gateway. Mitigate by keeping hosts out of Phase 10 and testing zero-channel construction.
- Fake backend code can become too concrete or Hermes-shaped. Mitigate by using synthetic IDs, neutral event scripts, and no private backend paths.
- Output-boundary source can trip neutral boundary scans if it embeds concrete backend/channel names. Mitigate by keeping concrete leak strings in tests/fixtures, not neutral runtime source.
- Contract logs can accidentally store raw payload text. Mitigate with store-level rejection tests and hash/ref-only assertions.
- Default-off flags can be bypassed by tests that enable everything implicitly. Mitigate with explicit default-off tests and explicit opt-in in lifecycle tests.

## Research Complete

Phase 10 can be planned as four slices: runtime ports/flags/store, fake adapters plus lifecycle, streaming output-boundary enforcement, and contract fixture/replay evidence.
