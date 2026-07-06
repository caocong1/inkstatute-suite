# Phase 47: Artifact Return (A2) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can call `collect_artifacts(run_id)` on Codex and provider_model adapters and receive `ArtifactRecord` entries with ref-based schema (`content_ref`, `sha256`, `size_bytes` — never inline binaries), and `AgentResult.artifacts` is populated with terminal artifacts, with output boundary enforcement on artifact metadata.

**Depends on:** Phase 45
**Requirements:** ARTIFACT-01, ARTIFACT-02

**Success Criteria** (what must be TRUE):
1. Adapters return artifacts via frozen `collect_artifacts()` and populate `AgentResult.artifacts` with ref-based schema (`content_ref`, `sha256`, `size_bytes`); no inline binary content appears in any artifact record or contract event.
2. Artifact metadata enforces the output boundary — backend noise (model names, API error traces, function call internals) is filtered from artifact metadata fields via an allowlist.
3. Codex adapter populates `AgentResult.artifacts` and `_artifacts[run_id]` store from existing `CodexExecResult.artifact_refs`, and provider_model adapter populates artifacts from provider response file outputs.

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
