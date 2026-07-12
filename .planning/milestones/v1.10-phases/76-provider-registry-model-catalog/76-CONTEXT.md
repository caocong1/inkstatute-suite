# Phase 76: Provider Registry + Model Catalog - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can select built-in vendor providers or define custom OpenAI-compatible endpoints, pick a catalog main model with vision capability metadata, and probe connectivity without leaking secrets.

Requirements: PROV-01, PROV-02, PROV-03, PROV-04.

Success criteria:
1. Select built-in vendor provider profile without editing Hermes
2. Define custom OpenAI-compatible provider (api_base_url + api_key_ref + model allowlist)
3. Pick main model from built-in catalog with supports_vision metadata
4. Non-destructive connection probe; fail-closed on missing refs; no response body/secret logging

Depends on Phase 74. Can run parallel with 75 (75 already complete). Incremental SSR forms OK; Phase 78 completes CSRF SSR surface.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
Discuss skipped — use ROADMAP, research, and codebase conventions.

Locked:
- Secrets as refs only; never log/echo resolved secrets or probe response bodies
- No Hermes filesystem as config authority
- Extend admin-console-api + admin-web-ui
- Catalog must include supports_vision for Phase 77

</decisions>

<code_context>
## Existing Code Insights

Phase 73 schemas include provider/catalog/vision docs. Phase 74 `/config/providers` and `/config/catalog` sections exist. Channel SSR patterns from Phase 75.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss skipped.

</specifics>

<deferred>
## Deferred Ideas

Vision routing runtime (77), complete SSR/docs/gate honesty (78).

</deferred>
