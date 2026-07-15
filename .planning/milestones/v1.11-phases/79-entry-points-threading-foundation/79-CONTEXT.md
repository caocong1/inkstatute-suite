# Phase 79: Entry Points & Threading Foundation - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Every service is runnable as `python -m <pkg>` with configurable host/port, signal-handling graceful shutdown, and a `ThreadingHTTPServer` threading model that has been explicitly decided and audited for thread-safety of all shared mutable state before any feature work begins.

### Requirements

This phase covers:

- **ENTRY-01**: Operator can start `admin-web-ui` as a standalone HTTP server via `python -m admin_web_ui` (or entry script) with configurable host/port, signal-handling graceful shutdown, and feature-flag gate.
- **ENTRY-02**: Operator can start `admin-console-api` as a standalone HTTP server via `python -m admin_console_api` (or entry script) with configurable host/port, signal-handling graceful shutdown, and feature-flag gate.
- **ENTRY-03**: `admin-web-ui` and `admin-console-api` use `ThreadingHTTPServer` (not single-threaded) so blocking operations (log reads, report aggregation, subprocess waits) do not freeze the UI; thread-safety of shared mutable state is audited and guarded.

### Success Criteria (what must be TRUE)

1. Operator can start `admin-web-ui` and `admin-console-api` as standalone HTTP servers via `python -m <pkg>` (or entry script) with configurable host/port, SIGINT/SIGTERM graceful shutdown, and a feature-flag gate that refuses to boot when the service flag is OFF.
2. Both services bind `ThreadingHTTPServer` (not single-threaded `HTTPServer`) so blocking operations (log reads, report aggregation, subprocess waits) do not freeze the UI; a socket-level integration test boots each service on an ephemeral port and asserts concurrent requests do not serialize.
3. A threading-model decision artifact documents the `ThreadingHTTPServer` choice, and a thread-safety audit guards every shared mutable store (`OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, process table) with per-store `threading.Lock` or copy-on-rebuild semantics — no unguarded read-modify-write cycle remains.

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
