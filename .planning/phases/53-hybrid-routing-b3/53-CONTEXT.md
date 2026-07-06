# Phase 53: Hybrid Routing (B3) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can configure `RouterStrategy.HYBRID` to implement a Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5), where a legal-risk classifier forces high-risk queries to Hermes regardless of confidence score, and `RouteDecision.confidence` is populated for all hybrid routing decisions.

**Depends on:** ?
**Requirements:** HYBRID-01, HYBRID-02, HYBRID-03

**Success Criteria** (what must be TRUE):
1. `RouterStrategy.HYBRID` (router-internal enum, NOT frozen `RouteMode`) implements Rule → Skill → Model cascade with confidence thresholds: route directly when confidence ≥0.8, emit clarification prompt when 0.5–0.8, fall back to safe path when <0.5.
2. Legal-risk classifier forces high-risk queries to Hermes regardless of confidence score; a test asserts that high-risk legal fixtures always route to Hermes, preventing confidence-miscalibrated routing to cheap/weak models.
3. `RouteDecision.confidence` is populated (float 0.0–1.0) for all hybrid routing decisions; the strategy is recorded in `metadata["router_strategy"]` without modifying the frozen `RouteDecision` schema.
4. `hybrid_routing_enabled` defaults to `False`; cold-start defaults to safe (Hermes) path; `ModelClassifierPort` is host-injected with `None` default preserving in-process fallback.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
