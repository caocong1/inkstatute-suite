# Phase 72: Controlled Live Integration - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can run a controlled QQ live path with fail-closed env checks and documented enablement, while live acceptance remains an explicit HUMAN GATE.

Requirements: LIVE-01, LIVE-02

Success criteria:
1. Controlled `--live` path remains available with fail-closed env checks and is explicitly marked HUMAN GATE (CI/phase complete must not auto-claim live acceptance).
2. Operator runbook documents host enablement, dual-knob mapping, dry-run vs live, and interaction ACK safety windows.
3. Live evidence, when collected by an operator, stays sanitized/reference-first and is never required for autonomous phase completion.
4. Phase 5 live WeCom UAT and Phase 8 lawyer trial remain carried human gates — not redefined as v1.9 done.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 71 smoke hardening, and existing live smoke fail-closed patterns to guide decisions.

CRITICAL: Do NOT mark live acceptance as complete. Do NOT redefine Phase 5/8 human gates as done. Autonomous phase completion must not require live evidence.

</decisions>

<code_context>
## Existing Code Insights

Phase 71 hardened smoke --dry-run to Protocol path. Phase 72 documents and preserves controlled --live with HUMAN GATE semantics.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Actual live QQ operator runs remain HUMAN GATE outside autonomous completion.

</deferred>
