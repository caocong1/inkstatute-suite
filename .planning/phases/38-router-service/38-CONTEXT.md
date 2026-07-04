---
phase: 38
slug: router-service
status: planning
discuss_skipped: true
created: 2026-07-04
---

# Phase 38 Context — Router Service

> Discuss phase skipped (`workflow.skip_discuss=true`). Minimal context generated from ROADMAP.md and REQUIREMENTS.md.

## Phase Boundary

**Goal:** Operator can inject a standalone router library into `hermes-contract-layer/mapper.py` that produces `RouteDecision` events with the same JSONL shape as the inline implementation, supporting RULE and SKILL routing modes with a `None` default that preserves in-process fallback behavior.

**Depends on:** Phase 37 (COMPLETE — Skill Registry provides metadata for SKILL routing)

**Requirements:** ROUTER-01, ROUTER-02

## Success Criteria (from ROADMAP.md)

1. Operator can inject the standalone router library into `hermes-contract-layer/mapper.py` and verify that `RouteDecision` events retain the same JSONL shape as the inline implementation, with a `None` default that preserves in-process fallback behavior and all 9 V2 gates staying green.
2. Operator can configure `RouteMode.RULE` and `RouteMode.SKILL` routing modes in the router service, with stateless skill lookup from the Skill Registry and intent classification via keyword/regex, producing normalized `RouteDecision` records.
3. Operator can verify that `router_service_enabled` defaults to `False` and that the router is injectable as a `RouterPort` Protocol with fallback policy for router unavailable.

## Decisions

No user decisions gathered (discuss skipped). Planner has discretion per RESEARCH.md findings.

## Code Context

- `router_service_enabled` feature flag already added in Phase 36 (defaults to `False`)
- Skill Registry from Phase 37 provides `NeutralSkillDescriptor` records for SKILL routing mode
- Existing inline router in `hermes-contract-layer/mapper.py` produces `RouteDecision` events — the standalone router must produce the same JSONL shape
- `RouteDecision` schema may already exist in `packages/platform-contract/`
