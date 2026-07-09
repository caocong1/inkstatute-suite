# Phase 67: One-Click Smoke-Test Toolkit - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

One-click smoke-test CLI validates signature verification, sends text + markdown+keyboard, simulates callback, and collects sanitized evidence via env-var credential injection; `--dry-run` mode runs without live platform for CI; operator runbook documents the full process; evidence output is sanitized. Live run remains a human gate.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- `scripts/smoke_test.py` CLI: validate signature, send text + markdown+keyboard, simulate callback, sanitized evidence
- Credentials via env-var injection only (never commit secrets)
- `--dry-run` for CI (fixture credentials, no live platform)
- `runbook/SMOKE_TEST_RUNBOOK.md` documents setup, commands, expected outputs, evidence format
- Evidence sanitized: no tokens, no raw user payloads, no attachment URLs
- Live run is a HUMAN GATE — not an autonomous deliverable
- Reuse Phase 59–66 qqbot modules; dependencies=[] for qqbot package; smoke script may use stdlib only
- No frozen Protocol/platform-contract/channel-core edits; no wecom imports

</decisions>

<code_context>
## Existing Code Insights

Prior phases built full QQBot channel loop. Smoke toolkit exercises them with dry-run + optional live (human).

</code_context>

<specifics>
## Specific Ideas

Requirements: SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04.

</specifics>

<deferred>
## Deferred Ideas

Live platform smoke execution remains a human gate after this phase ships the toolkit.

</deferred>
