# Phase 54: Model Provider Gateway (B4) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can configure a Model Provider Gateway (`packages/model-gateway/`) as a composite `BackendAdapter` wrapping multiple provider_model sub-adapters, with per-tenant/provider rate limiting (RPM/TPM/concurrency), fallback chains with circuit breakers and tried-provider tracking, and per-tenant/matter cost tracking with budget ceilings.

**Depends on:** ?
**Requirements:** MODELGW-01, MODELGW-02

**Success Criteria** (what must be TRUE):
1. `packages/model-gateway/` implements a composite `BackendAdapter` wrapping multiple provider_model sub-adapters (Anthropic, Ollama, OpenAI) behind the frozen 9-method Protocol; injected into `DefaultRunRuntime` as `backend` with no runtime change.
2. Gateway enforces per-tenant/provider rate limiting (RPM, TPM, concurrency) via a pure-Python token-bucket implementation using `asyncio.monotonic()` + `collections.deque` + `asyncio.Lock` (~30 lines, no external dependency).
3. Gateway implements fallback chains with circuit breakers (open/half-open/closed states) and tried-provider tracking; cascading failures are prevented by circuit breaker isolation and cost ceiling enforcement.
4. Gateway tracks per-tenant/matter cost with budget ceilings; when a budget is exceeded, the gateway refuses the request and emits an error event — no auto-downgrade for legal tasks (legal-risk classifier forces high-risk queries to Hermes regardless of cost).

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
