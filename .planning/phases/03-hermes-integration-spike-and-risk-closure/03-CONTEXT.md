# Phase 03: Hermes Integration Spike and Risk Closure - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning
**Source:** Autonomous planning from V2 PRD, ROADMAP, REQUIREMENTS, and completed Phase 1/2 artifacts.

<domain>
## Phase Boundary

Phase 3 closes the V2 implementation risks that would otherwise make Phase 4 hook work speculative. It must produce documented, testable decisions for Hermes hook ordering, AgentTurn input strategy, message and feedback association, long-task state mapping, idempotency, raw payload retention, and redaction.

The current repository does not contain the Hermes runtime source. Phase 3 must therefore be planned as an evidence-first spike using the available PRD, GSD state, contract schemas, contract-test-suite, and synthetic fixtures. If Hermes source is later added or mounted, Phase 3 plans should inspect it directly before finalizing decisions. Until then, Phase 3 outputs must mark Hermes-source-dependent assumptions explicitly.

</domain>

<decisions>
## Implementation Decisions

### D-01 Phase 3 is a risk-closure spike, not production hook implementation.
- Production `contract_result_recorder`, mapper, writer, WeCom loop validation, read APIs, and feedback-service implementation remain Phase 4+ scope.
- Phase 3 may create docs, spike probes, mapper decision tables, and non-happy-path contract fixtures only where they unblock Phase 4.

### D-02 Hermes source absence is a first-class evidence gap.
- If no Hermes runtime code is available in this repository, plans must not invent hook APIs or callback fields as confirmed facts.
- Source-dependent decisions must be recorded as `confirmed`, `assumed`, or `requires Hermes source`.

### D-03 Hook order decision must resolve the `response_filter` dependency.
- Phase 3 must decide whether `contract_result_recorder` can run after `response_filter`.
- If ordering cannot be confirmed, plans must document the fallback: either record inside/adjacent to `response_filter` or make Phase 4 block until Hermes hook ordering evidence exists.

### D-04 AgentTurn input strategy must be explicit.
- Preferred outcome: identify a stable inbound hook/source for AgentTurn.
- Fallback outcome: document `agent:end` reverse-inference limits, including which AgentTurn fields may be incomplete and how `raw_payload_ref` should preserve reference-only access.

### D-05 Feedback association rules must produce one traceable target per response.
- Phase 3 must define how `message_id`, `feedback_target`, template card id, callback payload, `result_id`, and `turn_id` relate.
- The plan must include handling for multiple cards or repeated card callbacks without losing idempotency.

### D-06 Long-task state mapping must target platform enum values exactly.
- Required target states are `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`.
- If Hermes has no direct signal for a state, plans must record the mapping as unavailable or derived, not silently approximate it.

### D-07 Raw payload and privacy decisions are blocking for Phase 4.
- Contract logs must prefer `raw_payload_ref` and must not store sensitive full text by default.
- Phase 3 must define retention, storage location assumptions, and redaction minimums for callback/input payload references.

### D-08 Non-happy-path fixtures are Phase 3 deliverables.
- Fixtures must cover route errors, long-task failures, repeated feedback clicks, and at least one non-legal task.
- Fixtures must validate through `packages/contract-test-suite` and keep legal/sensitive source content as `fixture://` or `raw_payload_ref` references.

### D-09 Automatic legal skill modification remains out of scope.
- Phase 3 must preserve the V2 safety rule that route mismatch and skill candidate feedback require human review and cannot auto-modify high-risk legal conclusions.

</decisions>

<canonical_refs>
## Canonical References

Downstream agents must read these before planning or implementation.

### Product and Scope
- `docs/requirements/V2-PRD.md` - active V2 PRD, especially section 13 implementation risks and event relationship definitions.
- `.planning/PROJECT.md` - project source-of-truth decisions and thin-contract boundary.
- `.planning/REQUIREMENTS.md` - `REQ-implementation-risk-resolution` acceptance requirements.
- `.planning/ROADMAP.md` - Phase 3 success criteria and downstream Phase 4/5/6/7 boundaries.
- `.planning/STATE.md` - current progress, accumulated decisions, and blockers.

### Completed Upstream Evidence
- `.planning/phases/01-platform-contract-foundation/01-VERIFICATION.md` - confirmed contract schema and fixture foundation.
- `.planning/phases/02-contract-test-suite-foundation/02-VERIFICATION.md` - confirmed schema validation, replay, relationship checks, and package-local runner.
- `packages/platform-contract/src/platform_contract/schemas/` - platform event schema source of truth.
- `packages/platform-contract/fixtures/` - Phase 1 relationship-focused golden fixtures.
- `packages/contract-test-suite/` - Phase 2 validation and replay harness that Phase 3 fixtures must pass.

</canonical_refs>

<specifics>
## Specific Ideas

- Create an integration decision record that lists every V2 risk from PRD section 13 and marks it `confirmed`, `assumed`, `deferred`, or `blocked`.
- Add a source inventory/probe artifact that records whether this repository contains Hermes runtime hooks, WeCom callback shims, feedback JSONL examples, or long-task state sources.
- Add mapper rules as data/docs rather than production code: hook order, AgentTurn inference, result/feedback identifiers, async states, idempotency keys, raw payload refs, and redaction.
- Add non-happy-path fixtures under a Phase 3-owned fixture location and run them through `packages/contract-test-suite`.
- Keep all outputs stdlib/testable where code is needed; do not introduce package-manager dependencies.

</specifics>

<deferred>
## Deferred Ideas

- Production Hermes hook, mapper, writer, and event log persistence: Phase 4.
- WeCom end-to-end daily-use validation: Phase 5.
- Feedback-service normalization and pending queues: Phase 6.
- `.github` CI enforcement, real task 95% coverage, and broader privacy gates: Phase 7.
- Lawyer trial metrics: Phase 8.

</deferred>

<scope_fence>
## Scope Fence

Phase 3 should not add runtime services, external network calls, database migrations, `.github` workflows, production Hermes hook files, new WeCom gateway behavior, read APIs, or automatic legal skill modification.
</scope_fence>

---

*Phase: 03-hermes-integration-spike-and-risk-closure*
*Context gathered: 2026-06-27 via autonomous GSD planning*
