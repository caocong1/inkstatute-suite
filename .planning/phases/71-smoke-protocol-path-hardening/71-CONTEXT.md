# Phase 71: Smoke Protocol-Path Hardening - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

CI dry-run proves the full adapter/session Protocol stack (not leaf helpers only) and emits sanitized non-acceptance evidence.

Requirements: SMOKE-01, SMOKE-02

Success criteria:
1. `scripts/smoke_test.py --dry-run` exercises verify_and_ack → ingress/session → deliver using Fake transports (not leaf helpers only).
2. Protocol-path dry-run emits sanitized evidence under the existing allowlist schema with `not_live_acceptance=true` and no secrets/raw bodies.
3. Dry-run exits 0 in CI without network/Urllib live transports.
4. Smoke steps call the same host/package helpers the webhook composition uses (no parallel leaf-only path claimed as host-complete).

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 70 webhook composition helpers, and existing smoke_test.py patterns to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Phase 70 delivered webhook.py + http_server.py composing verify_and_ack → ingress/session/feedback → deliver. Phase 71 must harden smoke dry-run to exercise that same Protocol path.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Live path remains Phase 72 HUMAN GATE.

</deferred>
