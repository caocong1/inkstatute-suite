---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: Operator Config Console
current_plan: 01
status: ready_to_execute
stopped_at: Phase 74 planned — ready to execute
last_updated: "2026-07-10T07:47:24Z"
last_activity: 2026-07-10 — Phase 74 plans created (3 plans / 3 waves)
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 6
  completed_plans: 3
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-10)

**Core value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.
**Current focus:** v1.10 Operator Config Console — Phase 74 planned (Admin Config API + RBAC); ready to execute

## Current Position

Phase: 74 of 78 (Admin Config API + RBAC) — 2 of 6 v1.10 phases
Current Plan: 01 (of 03)
Total Plans in Phase: 3
Plan: 74-01 — Wave 0 freeze/PYTHONPATH + `/config` RBAC matrix
Status: Ready to execute
Last activity: 2026-07-10 — Phase 74 plans created (3 plans / 3 waves)

Progress: [█░░░░░░░░░] 17% (1/6 v1.10 phases)

### Deferred Items

#### Remaining Deferred Items (carried forward)

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 08 lawyer-trial UAT | passed (0 open scenarios; human gate remains carried) |
| verification_gap | Phase 05 shadow-loop verification | human_needed (pre-existing v1.0 gate) |
| uat_gap | v1.8/v1.9 live QQ smoke (`scripts/smoke_test.py --live`) | HUMAN GATE remains — live OpenAPI acceptance not claimed |

### Parallel Human Gate (v1.0)

Phase: 08 (lawyer-trial-acceptance) — HUMAN_NEEDED (carried forward)
Status: Fresh live WeCom task-flow UAT and five-workday lawyer trial evidence still required
Note: Autonomous v1.10 work must never mark these complete or substitute fixtures for live evidence.

## Performance Metrics

**Velocity:**

- Total plans completed: 90
- Average duration: N/A
- Total execution time: ~0.03 hours

**Recent Trend:**

- Last 5 plans: Phase 73 P03 (3 min); Phase 73 P02 (3 min); Phase 73 P01 (2 min); Phase 72 P01/P02 (2–3 min)
- Trend: N/A (new milestone)

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 73 | 01 | 2min | 3 | 8 |
| 73 | 02 | 3min | 2 | 4 |

| 73 | 03 | 3min | 3 | 11 |

*Updated after each plan completion*

## Accumulated Context

### Roadmap Evolution

- v1.10 roadmap created: Phases 73–78 (Operator Config Foundation → Admin Config API + RBAC → Channel Config Apply → Provider Registry + Model Catalog → Vision Routing Runtime → Console SSR, Docs & Gate Honesty)
- ADM-02 (SSR UI) owned by Phase 78; domain phases 75–77 may ship incremental forms, Phase 78 verifies complete CSRF-protected SSR surface
- After Phase 74, Phases 75 and 76 can run in parallel waves; Phase 77 waits on catalog `supports_vision`
- Prior: v1.9 Phases 68–72 shipped; v1.8 Phases 58–67; Phase 57.1 TenantGuard gap closure; v1.5–v1.7 as archived

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Start milestone v1.10 Operator Config Console — configure QQ/WeCom, providers, models, vision without editing Hermes
- Config secrets stay as refs; values resolve at process edge only
- Vision routing: dedicated vision model when main model lacks image understanding
- Extend existing admin-console-api + admin-web-ui (stdlib SSR); no new SPA/DB/queue for MVP
- `operator_config_enabled` default OFF; dual-knob channel enablement preserved
- [Phase 73]: Channels nested as ChannelsDoc.qqbot/wecom (not a keyed map)
- [Phase 73]: Providers stored as tuple[ProviderDoc, ...] on the root document
- [Phase 73]: secret:// requires two+ slash-separated safe segments (generalized beyond QQ REF_TO_VALUE_ENV)
- [Phase 73]: No resolve_secret_ref and no process-environment reads in operator-config package
- [Phase 73]: validate_document raises on errors; OperatorConfigValidator collects issues
- [Phase 73]: Hermes authority banned via path substrings + hermes_* field names in nested walks
- [Phase 73]: Validation errors expose codes@paths only — never planted secrets
- [Phase 73]: OperatorConfigDisabledError wraps RuntimeFeatureDisabledError for package-level CFG-02 clarity
- [Phase 73]: Default store path is .inkstatute/operator-config.json when INKSTATUTE_OPERATOR_CONFIG_PATH unset
- [Phase 73]: save order is mandatory: flag gate then validate_document then atomic write
- [Phase 74 planning]: `/config` sections-only (no full GET `/config`); operational PUT → 405; lawyer/viewer denied GET+PUT; import `document_*` from store submodule
- [Phase 74 planning]: Map `OperatorConfigDisabledError` → 403 `operator_config_disabled`; evolve (do not delete) `test_read_only.py`

### Pending Todos

None yet.

### Blockers/Concerns

- Carried human gates must not be auto-closed by config console smoke (DOC-02 / `not_live_acceptance`)
- Phase 77 vision injection format (structured vs caption) deferred to plan-phase research
- Hot-reload vs restart-to-apply: MVP documents restart unless a phase plan proves safe in-process reload

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Human gate | Phase 8 Lawyer Trial Acceptance | Deferred (parallel human gate) | v1.1 archive |
| Human gate | Phase 5 live WeCom UAT | Deferred (human gate) | v1.1 archive |
| Human gate | QQ `--live` OpenAPI acceptance | HUMAN GATE | v1.9 archive |
| v1.10 future | CFG-F01..F03, PROV-F01..F03, VIS-F01..F02, HOST-F01..F03 | Deferred beyond v1.10 | v1.10 init |

## Session Continuity

Last session: 2026-07-10T07:47:24Z
Stopped at: Phase 74 planned — ready to execute
Resume file: None
Architecture basis: .planning/research/SUMMARY.md
Execution plan: .planning/ROADMAP.md
Requirements: .planning/REQUIREMENTS.md (20/20 mapped)
Research summary: .planning/research/SUMMARY.md
Phase 74 plans: .planning/phases/74-admin-config-api-rbac/74-0{1,2,3}-PLAN.md
Phase 74 validation: .planning/phases/74-admin-config-api-rbac/74-VALIDATION.md
Phase 73 verification: .planning/phases/73-operator-config-foundation/73-VERIFICATION.md
Phase 73 research/context: .planning/phases/73-operator-config-foundation/
Parallel human gate (do not auto-complete): .planning/phases/08-lawyer-trial-acceptance/
v1.9 archive: .planning/milestones/v1.9-ROADMAP.md

## Operator Next Steps

- Execute Phase 74: `/gsd-execute-phase 74`
- Carried human gates (Phase 5 / 8 / QQ `--live`) remain open — do not auto-close
