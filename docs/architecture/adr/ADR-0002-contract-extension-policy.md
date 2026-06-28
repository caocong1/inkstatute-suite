# ADR-0002: Contract Extension Policy

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

Existing V2 contracts already define platform events such as `AgentTurn`,
`AgentResult`, `FeedbackEvent`, `ExecutionTrace`, and `RouteDecision`. Milestone
v1.1 needs additional platform resource and run contracts without breaking
existing fixture replay, Python bindings, or manifest validation.

## Decision

All Phase 09 contract work is additive and backward-compatible.

`AdapterCapabilitySet` may gain new optional fields for run invocation modes,
stream event support, cancel support, approval support, live update support,
parallel task support, and session memory support. Existing constructor defaults
and existing `validate_agent_backend_manifest` behavior must remain valid.

`ArtifactRecord` is introduced as a top-level artifact reference for run and
delivery relationships. It does not replace nested `AgentResult.artifacts`.
`AgentResult.artifacts` remains the result-level user-facing artifact list, while
`ArtifactRecord` supports platform-level references, audit, delivery, and
relationship replay.

New schemas and bindings must keep legal-specific fields out of top-level
required fields. Domain data belongs in `industry_context`, metadata, or
solution-specific descriptors.

## Consequences

Older V2 fixtures and adapter manifests can continue to validate. New platform
runtime and channel work can express richer run and artifact relationships
without forcing existing agent result payloads to change.

The cost is that validators and tests must explicitly check both old and new
contract shapes so drift is caught early.

## Verification Notes

Phase 09 contract plans must verify schema/binding parity, backward-compatible
`AdapterCapabilitySet` defaults, and relationship replay involving both
`AgentResult.artifacts` and top-level `ArtifactRecord`.

