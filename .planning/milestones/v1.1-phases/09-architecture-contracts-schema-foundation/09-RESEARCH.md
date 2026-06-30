# Phase 09: Architecture Contracts & Schema Foundation - Research

**Researched:** 2026-06-29
**Status:** Complete
**Mode:** Inline GSD research, no subagent spawn available

## Research Question

What does Phase 09 need to know before planning the North Star architecture contracts, signature-only runtime stubs, additive platform-contract schemas, relationship fixtures, and allowlist boundary gates without changing runtime behavior?

## Findings

### Source of Truth and Phase Boundary

- Active product source is `docs/requirements/V2-PRD.md`; retired V1 must not be reintroduced as a requirement source.
- Milestone v1.1 is governed by `.planning/drafts/agent-platform-north-star.md` and `.planning/drafts/agent-platformization-plan-v5.md`.
- Phase 09 is non-runtime foundation work: architecture docs, Protocol signatures, additive JSON Schemas/Python bindings, contract tests, ADR drafts, and allowlist gates.
- Phase 09 must not implement `RunRuntime` behavior, channel wrappers, Hermes adapter behavior, solution loading behavior, new databases, queues, or live WeCom changes. Those belong to later phases.
- Phase 08 live lawyer trial remains a parallel human gate and is not a dependency of Phase 09.

### Existing Contract Package Patterns

- `packages/platform-contract/src/platform_contract/events.py` uses frozen, slotted dataclasses and a shared `JsonObject = dict[str, Any]` alias.
- `packages/platform-contract/src/platform_contract/enums.py` already defines `AsyncTaskState`, `Channel`, `MessageType`, artifact, feedback, route, and error enums.
- `packages/platform-contract/src/platform_contract/agent_adapter.py` defines `AgentBackendMode`, `AdapterCapabilitySet`, `AgentBackendManifest`, and `validate_agent_backend_manifest`.
- Existing JSON Schemas live under `packages/platform-contract/src/platform_contract/schemas/*.schema.json` and use JSON Schema draft 2020-12.
- `packages/platform-contract/scripts/self_check.py` validates schema shape, fixture required fields, relationship integrity, forbidden top-level legal/sensitive fields, and Python binding/schema parity.
- The package is dependency-free and should remain standard-library-only.

### Existing Contract Test Suite Patterns

- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` and `fixture_replay.py` are the existing schema and bundle validation entry points.
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` checks ordered event stream relationships.
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` currently enforces thin-layer import/schema boundaries with a denylist-style implementation.
- Existing tests are stdlib `unittest` with explicit `PYTHONPATH` commands.
- Existing non-legal fixtures already prove platform event neutrality for finance/tax, engineering, and education scenarios. Phase 09 should add a platform-foundation fixture for the new resource/run/channel contracts.

### Missing Phase 09 Capabilities

- `docs/architecture/` currently has only `docs/architecture/adr/README.md`; the North Star architecture doc still lives in `.planning/drafts/`.
- `docs/architecture/adr/ADR-0001.md` through `ADR-0007.md` do not exist yet.
- `packages/platform-runtime/` does not exist. Phase 09 should create only Protocol signatures and package scaffolding, with no orchestration implementation.
- `platform-contract` does not yet define `ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest`, neutral skill/MCP descriptors, `BotInstance`, or `ChannelBinding`.
- `AdapterCapabilitySet` needs additive fields for run invocation modes, stream event support, cancel/approval/live-update/parallel/session memory support while preserving existing constructor defaults and manifest validation.
- Boundary checks need an allowlist policy for neutral packages so terms like `hermes`, `codex`, `provider_model`, `wecom`, and `lawfirm` are allowed only in the correct contexts.
- No new relationship replay currently proves `ChannelMessage -> AgentTurn -> Run -> RunEvent/RunStep -> AgentResult/ArtifactRecord -> ChannelDelivery -> FeedbackEvent`.

### Implementation Constraints for Executors

- Keep all contract additions additive and backward-compatible.
- Keep legal-specific fields out of top-level required schema fields; use `industry_context`, `metadata`, or solution-specific descriptors.
- `Run.status` must reference the existing `AsyncTaskState` values instead of inventing a second run-state enum.
- `ArtifactRecord` is a top-level artifact reference and must not replace nested `AgentResult.artifacts`.
- `ChannelBinding` and solution descriptors must use `secret_ref` or secret template names only, never runtime secret values.
- Protocol stubs in `packages/platform-runtime` should use `typing.Protocol`, `AsyncIterator`, dataclasses or lightweight typed objects as needed, and raise no runtime side effects.
- Do not import Hermes, WeCom service modules, or other runtime services from `platform-contract`.
- Do not rely on private Hermes paths or live WeCom payload fields in neutral packages.

## Proposed Plan Architecture

### Plan 09-01: Architecture Docs and Protocol Stubs

Promote the North Star doc into `docs/architecture/`, add ADR-0001 through ADR-0007 drafts, and create `packages/platform-runtime` with signature-only `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, and `RunRuntime` contracts.

### Plan 09-02: Contract Schemas and Python Bindings

Extend `platform-contract` with new schema files, dataclasses, enum additions, and backward-compatible `AdapterCapabilitySet` fields. Update exports and self-check schema/binding parity.

### Plan 09-03: Relationship Fixtures and Replay Coverage

Add sanitized non-legal platform-foundation fixtures and extend self-check/contract-test-suite validation so the new channel/run/artifact/delivery relationship chain validates without requiring legal fields.

### Plan 09-04: Boundary Allowlist Gates

Replace brittle blanket text banning for neutral packages with an allowlist-aware boundary scan. Preserve strict failures for private Hermes paths, WeCom protocol payload internals, lawfirm-only required schema fields, raw payloads, secrets, runtime logs, DBs, and customer materials.

## Verification Strategy

| Proof | Command or Assertion |
|-------|----------------------|
| Platform contract schemas and bindings compile | `PYTHONPATH=packages/platform-contract/src python packages/platform-contract/scripts/self_check.py` |
| Existing contract suite still passes | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python packages/contract-test-suite/scripts/run_contract_tests.py` |
| New platform-foundation fixture validates | a focused `unittest` in `packages/contract-test-suite/tests/` exits 0 |
| Protocol stubs are importable and signature-only | focused `unittest` or `compileall` for `packages/platform-runtime/src` exits 0 and tests assert no runtime behavior is implemented |
| Boundary allowlist works | focused boundary test accepts allowed enum/package contexts and rejects forbidden private/runtime/secret/legal-top-level cases |
| No runtime behavior change | no production services, adapters, channels, Hermes code, databases, queues, or live WeCom paths are modified |

## Risks

- The schema set is large enough to invite over-modeling. Mitigate by keeping fields minimal, additive, and neutral, with extension containers for future detail.
- A too-strict boundary scan can block legitimate neutral enum values. Mitigate with explicit path/context allowlists and tests for allowed `hermes`, `codex`, `provider_model`, `wecom`, and `lawfirm` contexts.
- A too-loose boundary scan can miss real coupling. Mitigate by keeping hard failures for private paths, runtime payload internals, raw payload fields, secrets, and legal-only top-level required fields.
- Protocol stubs can accidentally become runtime behavior. Mitigate by restricting Phase 09 to Protocol signatures, dataclasses/types, imports, and compile tests only.
- Existing dirty planning files are user-owned context. Phase 09 planning should not rewrite or commit unrelated dirty planning state.

## Research Complete

Phase 09 can be planned as four sequential slices: architecture/protocols, schemas/bindings, relationship fixtures/replay, and boundary allowlist gates.

