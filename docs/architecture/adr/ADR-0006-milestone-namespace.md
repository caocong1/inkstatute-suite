# ADR-0006: Milestone Namespace

- Status: Draft
- Date: 2026-06-29
- Deciders: InkStatute GSD Phase 09

## Context

The V2 PRD defines the current lawyer-bot product and its non-regression
requirements. The user then delegated a deliberate platform refactor as milestone
v1.1, covering GSD Phase 09-13. Phase 08 lawyer trial evidence remains a human
gate from the previous milestone.

## Decision

Use the milestone namespace `v1.1 Platform Foundation` for Phase 09-13. These
phases implement the reusable platform foundation: architecture contracts,
runtime, fake backend, Hermes adapter, channel interface, client surfaces, and
solution loading.

This namespace is distinct from the PRD section numbering for future M2/M3/M4.
`docs/requirements/V2-PRD.md` remains the source for non-regression of the
existing lawyer-bot behavior. The North Star architecture governs v1.1 platform
shape.

Phase 08 live lawyer trial and live cutover remain human gates outside the
autonomous Phase 09-13 path.

## Consequences

Planning and summaries can refer to Phase 09-13 without confusing them with V2
PRD future milestone labels. Autonomous execution can proceed through code,
tests, fixtures, and docs while live legal acceptance stays human-controlled.

The consequence is that summaries must be explicit about which source governs a
decision: V2 PRD for lawyer-bot non-regression, North Star for platform
architecture.

## Verification Notes

STATE, ROADMAP, REQUIREMENTS, phase summaries, and ADRs should keep Phase 08
human gates separate from Phase 09-13 autonomous completion. No fixture or static
test may mark the live lawyer trial complete.

