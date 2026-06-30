---
phase: 11-hermes-backendadapter-parity-spike
status: complete
researched: 2026-06-29
source: inline codex research
---

# Phase 11 Research: Hermes BackendAdapter + Parity Spike

## Question

What do we need to know to plan Phase 11 well?

## Source Anchors

- `.planning/REQUIREMENTS.md` maps Phase 11 to `REQ-hermes-backend-adapter`, `REQ-adapter-capability-probe`, and `REQ-hermes-run-parity-spike`.
- `docs/architecture/adr/ADR-0003-hermes-invocation-boundary.md` states one-shot remains default, probes must be non-mutating, and `/v1/runs` is behind a parity gate.
- `docs/architecture/adr/ADR-0004-storage-audit-human-review.md` requires reference-first audit storage and human review for high-risk legal evolution.
- `docs/architecture/agent-platform-north-star.md` says `BackendAdapter` is the Hermes seam and `/v1/runs` is not assumed equivalent to one-shot.
- `.planning/drafts/agent-platformization-plan-v5.md` names `backends/hermes` as the intended concrete adapter lane and `INKSTATUTE_HERMES_API_RUNS_ENABLED` as the default-off `/v1/runs` switch.
- `packages/platform-runtime/src/platform_runtime/protocols.py` defines the `BackendAdapter`, `RunRequest`, `RunHandle`, `Run`, `RunEvent`, `Approval`, and `ArtifactRecord` runtime contract.
- `packages/platform-runtime/src/platform_runtime/runtime.py` uses only `BackendAdapter` and feature flags; concrete Hermes behavior belongs outside neutral runtime code.
- `services/hermes-contract-layer/src/hermes_contract_layer/adapter_manifest.py` and `bootstrap.py` already provide Phase 5.5 manifest/bootstrap helpers that can be mirrored or reused conceptually.

## Existing Code Patterns

- New concrete backend code should live outside neutral runtime packages. `packages/backends/hermes` is already allowlisted by boundary tests as a concrete backend context.
- Protocol conformance tests should instantiate the concrete adapter and exercise every `BackendAdapter` method without real Hermes, secrets, customer documents, or live network calls.
- Existing fake runtime tests use deterministic in-memory fakes and stdlib `unittest`; Phase 11 should follow the same dependency-light pattern.
- Existing manifest validation requires `capabilities.invocation_mode` and `capabilities.no_channel_io`.
- Existing runtime feature flags do not yet include the Hermes API runs flag. Phase 11 can keep `INKSTATUTE_HERMES_API_RUNS_ENABLED` as adapter-local configuration instead of changing neutral `RuntimeFeatureFlags`.

## Implementation Findings

### One-Shot Default

The first Hermes adapter should implement `BackendAdapter` through a subprocess one-shot lane. It should:

- expose reduced capabilities: `invocation_mode="sync"`, `run_invocation_modes=["oneshot"]`, no streaming, no cancel, no approval, no live update, no parallel tasks, `no_channel_io=True`;
- translate `RunRequest` into a sanitized invocation envelope using refs and hashes instead of raw transcripts in committed fixtures;
- return `RunHandle` and `Run` objects with platform `AsyncTaskState` values;
- expose unsupported async methods deterministically without mutating backend state.

### Non-Mutating Probe

Capability probe must call only safe endpoints:

- `/health`
- `/v1/capabilities`
- `/v1/models`

It must never call `GET /v1/runs/{id}` because that requires a run id and can couple startup probing to runtime state. Probe failure should return a one-shot fallback capability set and a sanitized audit reason such as `probe_unavailable`, without hostnames, tokens, paths, or raw response bodies.

### `/v1/runs` Lane

The API run lane is a spike path, not the default. It should be represented by:

- adapter config/env gate `INKSTATUTE_HERMES_API_RUNS_ENABLED`;
- a client seam that can be tested with fake HTTP responses;
- behavior that refuses API-run submission when the flag is false;
- parity report artifacts that compare API-run fixture observations to one-shot fixture observations.

### Parity Fixtures

Fixture cases must cover:

- legal Q&A;
- drafting plus artifact;
- follow-up;
- route mismatch;
- MCP/tool task;
- non-legal task.

The comparison should check routing/skill/gate/MCP trace, artifact refs, final user-facing text after output policy, and state transitions. It should produce pass/fail evidence, and any failure must keep one-shot as default.

### Approval Safety

`Approval` is for run/tool approval only. The Hermes adapter must refuse or mark unsupported any approval whose metadata indicates high-risk legal conclusion approval, skill modification, legal conclusion mutation, or automatic legal advice acceptance. Tests should prove `submit_approval` cannot auto-approve high-risk legal conclusions.

## Suggested Plan Shape

1. Build the concrete `packages/backends/hermes` package shell, config, one-shot adapter, reduced capability manifest, and protocol conformance tests.
2. Add the non-mutating capability probe with fake HTTP transport tests and sanitized fallback audit reasons.
3. Add the default-off `/v1/runs` lane seam plus parity fixture/reporting framework.
4. Add the six-case parity fixtures, approval safety tests, privacy scan, and docs tying promotion/rollback to parity results.

## Validation Architecture

Phase 11 validation should run in layers:

1. `python -m compileall packages/backends/hermes packages/platform-runtime/src packages/platform-contract/src`
2. `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_hermes_backend_adapter.py`
3. `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_capability_probe.py`
4. `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_runs_lane.py packages/backends/hermes/tests/test_parity_report.py`
5. `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py`
6. Privacy/source scans must prove committed parity fixtures contain no transcripts, secrets, raw legal payloads, runtime DB/log/media paths, or private Hermes profile paths outside approved concrete backend contexts.

## Risks And Mitigations

- `/v1/runs` may not match lawfirm one-shot behavior. Mitigation: parity report can fail without blocking one-shot; one-shot remains default.
- Probe behavior can drift across Hermes versions. Mitigation: fake transport tests lock request set and fallback behavior; compatibility notes record assumptions.
- Concrete Hermes names can leak into neutral packages. Mitigation: keep Phase 11 code under `packages/backends/hermes` and avoid changes to neutral runtime package unless protocol gaps are discovered.
- Raw task text can leak into fixtures. Mitigation: use fixture ids, refs, hashes, and sanitized summaries only.

## Research Complete

The phase is ready for detailed planning.
