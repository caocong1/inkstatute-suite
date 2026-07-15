# Phase 82: Log Viewing - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can view runtime logs in the console with level filtering and keyword search via byte-offset HTTP polling, with every line privacy-scrubbed and no full-file reads.

Success criteria:
1. Operator can view runtime logs (contract events, runtime audit, feedback, child-process stdout/stderr) in the console with level filtering (DEBUG/INFO/WARN/ERROR) and keyword search, with a per-host source selector
2. Log viewing uses byte-offset tail-follow polling (seek + read-to-end + next_offset) so the browser refreshes without re-reading the full file; respects CSP (no EventSource/WebSocket, HTTP polling only); rotation-aware cursor resets on file shrink/inode change
3. Log viewer passes every line through existing privacy scrubbing (`scrub_contract_payload`) so secrets and raw legal payloads never appear in the console; a path-traversal guard validates service/file names against a fixed allowlist and rejects `..`/absolute/symlink paths

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
