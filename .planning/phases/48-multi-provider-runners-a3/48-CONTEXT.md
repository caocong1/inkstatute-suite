# Phase 48: Multi-Provider Runners (A3) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can configure `AnthropicRunner` and `OllamaRunner` as `ProviderRunner` Protocol implementations behind the provider_model adapter, with Messages API normalization for Anthropic, OpenAI-compatible endpoint for Ollama, and multi-provider error normalization reusing the v1.6 `ErrorInfo`/`ErrorCategory` pattern.

**Depends on:** Phase 46, Phase 47
**Requirements:** MULTIPROV-01, MULTIPROV-02, MULTIPROV-03

**Success Criteria** (what must be TRUE):
1. `AnthropicRunner` implements `ProviderRunner` Protocol with Messages API normalization (system prompt handling, message format conversion, tool use format), lazy SDK import, and `dependencies = []` invariant.
2. `OllamaRunner` implements `ProviderRunner` Protocol using OpenAI-compatible endpoint (`/v1/chat/completions`), lazy HTTP client import, and `dependencies = []` invariant.
3. Multi-provider error normalization reuses the v1.6 `ErrorInfo`/`ErrorCategory` pattern — provider-specific errors (rate limits, auth failures, timeouts, content filter) map to the existing `ErrorCategory` enum with provider-specific detail in `ErrorInfo.detail`.

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
