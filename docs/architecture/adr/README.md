# Architecture Decision Records (ADR)

This directory holds Architecture Decision Records for the InkStatute agent platform.

ADRs are short, append-only documents that capture a single significant decision: its context, the decision, and its consequences. They are the durable record behind the North Star architecture (`.planning/drafts/agent-platform-north-star.md`) and the Platform Foundation milestone (v1.1, Phase 09–13).

## Format

Each ADR uses this skeleton:

```
# ADR-NNNN: <title>

- Status: Proposed | Accepted | Superseded by ADR-MMMM
- Date: YYYY-MM-DD
- Deciders: <who>

## Context
<the forces and constraints>

## Decision
<the choice made>

## Consequences
<positive, negative, and follow-ups>

## Alternatives considered
<options rejected and why>
```

## Index (authored in Phase 09)

| ID | Title | Status |
|----|-------|--------|
| ADR-0001 | Agent platform layering (contract vs runtime vs concrete adapters vs solutions) | Proposed |
| ADR-0002 | Contract extension policy (additive V2 compatibility; extend `AdapterCapabilitySet`/`ArtifactRecord`) | Proposed |
| ADR-0003 | Hermes adapter invocation (capability probe, `/v1/runs` parity, one-shot fallback) | Proposed |
| ADR-0004 | Storage/audit boundaries and the legal human-review invariant | Proposed |
| ADR-0005 | Python core / TypeScript client split; JSON Schema as cross-language contract | Proposed |
| ADR-0006 | Milestone namespace (Phase 09–13 vs PRD §11 M2/M3/M4) | Proposed |
| ADR-0007 | Boundary-scan allowlist (neutral-package policy, backend-mode allowlist, concrete-package exceptions) | Proposed |

> Status note: all ADRs are Proposed until Phase 09 authors and accepts them. Decisions were pre-agreed with the user on 2026-06-29; Phase 09 records them formally.
