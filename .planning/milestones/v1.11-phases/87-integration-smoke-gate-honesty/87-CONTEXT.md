# Phase 87: Integration, Smoke & Gate Honesty - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Cross-phase verification confirms the console works end-to-end as a product-grade operations control plane and that gate honesty, privacy, and stdlib-only constraints hold across all new surfaces.

**Depends on**: Phases 79–86 (all feature phases complete)
**Requirements**: (no direct requirement mapping — verifies ENTRY-01..POLISH-05 end-to-end)

**Success Criteria** (what must be TRUE):

1. An end-to-end smoke boots the console via the one-click startup script, logs in via session auth, starts a channel host subprocess, views its logs, browses the reports dashboard, and audits a contract event trace — all without errors and within stdlib-only constraints
2. Gate-honesty audit confirms no new page, report, or dashboard auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` preserved across all new surfaces)
3. Privacy/XSS audit confirms every new rendering path passes through `html.escape`/`scrub_contract_payload`, no token/secret/bearer literal appears in log files under tests, and every new state-changing route carries CSRF protection
4. Stdlib-only constraint audit confirms no new third-party dependency, no new DB/queue/SPA, and every new feature flag defaults OFF

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
