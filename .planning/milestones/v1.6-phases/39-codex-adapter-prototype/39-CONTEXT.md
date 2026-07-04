---
phase: 39
slug: codex-adapter-prototype
status: planning
discuss_skipped: true
created: 2026-07-04
---

# Phase 39 Context — Codex Adapter Prototype

> Discuss phase skipped (`workflow.skip_discuss=true`). Minimal context generated from ROADMAP.md and REQUIREMENTS.md.

## Phase Boundary

**Goal:** Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `codex exec --json` subprocess.

**Depends on:** Phase 36 (COMPLETE — safety baselines in place, codex_backend_enabled feature flag exists)

**Requirements:** ADAPTER-01

## Success Criteria (from ROADMAP.md)

1. Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter that returns a valid `AgentBackendManifest` with `production_ready: false` and `no_channel_io: true`.
2. Operator can run a capability probe against the Codex adapter and verify it passes, returning `AdapterCapabilitySet` consistent with the v1.5 baseline field count.
3. Operator can run a fixture-driven `submit_run → AgentResult` flow through the Codex adapter via `codex exec --json` subprocess and verify the result maps to the platform contract `AgentResult` schema with error normalization on first failure.

## Decisions

No user decisions gathered (discuss skipped). Planner has discretion per RESEARCH.md findings.

## Code Context

- `codex_backend_enabled` feature flag already added in Phase 36 (defaults to `False`)
- SAFETY-01 selection gate bypass was fixed in Phase 36 — non-Hermes modes with `production_ready=true` cannot bypass live_acceptance
- The Codex adapter is a PROTOTYPE with `production_ready: false` and `no_channel_io: true`
- Existing backend adapter pattern: `services/wecom-service/src/wecom_service/agent_backend.py`
- `BackendAdapter` Protocol has 9 methods (frozen per SAFETY-02 contract-count freeze)
- `AdapterCapabilitySet` has 14 fields (frozen per SAFETY-02)
- `codex exec --json` subprocess is the execution mechanism
