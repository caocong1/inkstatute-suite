---
phase: 11-hermes-backendadapter-parity-spike
status: complete
created: 2026-06-29
---

# Phase 11 Pattern Map

## Target Files To Create

| Target | Role | Closest Existing Analog |
|--------|------|-------------------------|
| `packages/backends/hermes/src/inkstatute_backends_hermes/config.py` | Adapter config and default-off env parsing | `packages/platform-runtime/src/platform_runtime/feature_flags.py` |
| `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` | Concrete `BackendAdapter` implementation | `packages/platform-runtime/src/platform_runtime/fakes.py`, `packages/platform-runtime/src/platform_runtime/protocols.py` |
| `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` | Reduced one-shot and API-run capability manifests | `services/hermes-contract-layer/src/hermes_contract_layer/adapter_manifest.py` |
| `packages/backends/hermes/src/inkstatute_backends_hermes/probe.py` | Non-mutating HTTP capability probe | `services/hermes-contract-layer/src/hermes_contract_layer/bootstrap.py` |
| `packages/backends/hermes/src/inkstatute_backends_hermes/parity.py` | One-shot vs `/v1/runs` parity comparison/report | `packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py` |
| `packages/backends/hermes/tests/*.py` | Focused stdlib unit tests | `packages/platform-runtime/tests/test_run_runtime_lifecycle.py`, `packages/platform-runtime/tests/test_output_boundary.py` |
| `packages/backends/hermes/fixtures/*.json` | Sanitized parity fixture observations | `packages/contract-test-suite/fixtures/phase10_runruntime_fake_backend.json` |

## Reusable Patterns

### Protocol Implementation

`FakeBackendAdapter` implements all `BackendAdapter` methods with deterministic state and platform dataclasses. The Hermes adapter should expose the same methods but route one-shot behavior through an injected runner so tests can use a fake runner.

### Default-Off Gates

`RuntimeFeatureFlags.require_enabled()` fails closed with a deterministic message. Phase 11 should use an adapter-local equivalent for `INKSTATUTE_HERMES_API_RUNS_ENABLED`, keeping the flag out of neutral runtime unless later phases need a shared field.

### Manifest Shape

`build_hermes_adapter_manifest()` already returns `mode="hermes"` and `capabilities.no_channel_io=True`. Phase 11 should produce a reduced one-shot capability set and an API-runs capability set, both valid under `validate_agent_backend_manifest`.

### Non-Mutating Checks

`probe_hermes_capabilities()` records capability booleans and issues without mutating Hermes paths. The new HTTP probe should similarly return a report object instead of raising on ordinary endpoint failures, and tests should lock that it never calls `/v1/runs/{id}`.

### Privacy Fixtures

Phase 10 fixture tests assert no raw payload-like keys, no sensitive payload text, and zero live acceptance claims. Phase 11 parity fixtures should copy that style: fixture IDs, refs, hashes, sanitized summaries, and explicit `not_live_acceptance: true`.

### Human-Review Boundary

ADR-0004 requires high-risk legal changes to stay human-reviewed. `submit_approval` tests must reject or preserve pending status for metadata indicating legal conclusion approval, legal skill modification, or legal advice auto-acceptance.

## Anti-Patterns To Avoid

- Do not add concrete Hermes imports or private profile paths to `packages/platform-runtime`.
- Do not probe by creating runs or by reading `GET /v1/runs/{id}` during startup.
- Do not make `/v1/runs` the default lane, even when probe fixtures pass.
- Do not commit raw prompts, transcripts, runtime response bodies, customer legal payloads, secrets, runtime DB/log/media paths, or generated confidential artifacts.
- Do not model high-risk legal conclusion approval as a successful automatic `Approval`.
