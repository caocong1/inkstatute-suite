# InkStatute Hermes Backend Adapter

The Hermes backend package implements the concrete `BackendAdapter` for the first supported agent backend. One-shot remains default. The `/v1/runs` lane is present only as an opt-in parity spike and must not be treated as a live rollout approval.

## Default Lane

One-shot remains default because it is the proven lawfirm path. The adapter uses an injected one-shot runner and returns platform `Run`, `RunHandle`, `RunEvent`, and `ArtifactRecord` objects without performing ordinary-user channel I/O.

## Capability Probe

Startup capability probing is non-mutating. The safe probe endpoint set is:

- `/health`
- `/v1/capabilities`
- `/v1/models`

The probe must not create runs, read run-specific state, or send user-visible messages. Probe failures fall back to the reduced one-shot manifest with a sanitized reason code.

## `/v1/runs` Lane

`INKSTATUTE_HERMES_API_RUNS_ENABLED` controls the API-run lane. It is disabled by default and is true only for exact values `1`, `true`, or `yes` case-insensitively.

Even when enabled, `/v1/runs` requires explicit adapter construction with `invocation_mode="runs_api"`. Keeping the flag disabled is the rollback rule.

## Parity Report

Parity fixtures compare one-shot against `/v1/runs` on six sanitized cases: legal Q&A, drafting plus artifact, follow-up, route mismatch, MCP/tool task, and non-legal. The report checks route, skills/gates, MCP/tool trace, artifacts, visible output hash, output policy action, state transitions, and feedback target refs.

`promote_api_runs` is true only when every required dimension passes for every case. This is not live acceptance and does not change the default lane. Later human gates are still required before any live promotion.

## Approval Safety

High-risk legal conclusion approvals, legal skill changes, skill candidates, and legal advice approval markers require human review. The adapter records a rejection reason and does not call the one-shot runner or `/v1/runs` transport for those approvals.
