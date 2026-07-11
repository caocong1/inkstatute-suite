---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: Operator Config Console
current_plan: 1
status: executing
stopped_at: Phase 76 UI-SPEC approved
last_updated: "2026-07-10T17:03:36.266Z"
last_activity: 2026-07-10 -- Phase 76 execution started
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 18
  completed_plans: 11
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-10)

**Core value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.
**Current focus:** Phase 76 — provider-registry-model-catalog

## Current Position

Phase: 76 (provider-registry-model-catalog) — EXECUTING
Current Plan: 1
Total Plans in Phase: 4
Plan: 1 of 4
Status: Executing Phase 76
Last activity: 2026-07-10 -- Phase 76 execution started

Progress: [███░░░░░░░] 50% (3/6 v1.10 phases)

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

- Total plans completed: 98
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
| 74 | 01 | 2min | 2 | 6 |

*Updated after each plan completion*
| Phase 74 P01 | 2min | 2 tasks | 6 files |
| Phase 74 P01 | 2min | 2 tasks | 6 files |
| Phase 74 P02 | 3min | 2 tasks | 3 files |
| Phase 74 P03 | 2min | 3 tasks | 4 files |
| Phase 75 P01 | 4min | 2 tasks | 9 files |
| Phase 75 P04 | 2min | 2 tasks | 5 files |
| Phase 75 P03 | 2min | 2 tasks | 4 files |
| Phase 75 P02 | 2min | 2 tasks | 4 files |
| Phase 75 P05 | 5min | 2 tasks | 6 files |

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
- [Phase 74]: /config matrix roles are exactly {ADMIN, OPERATOR}; LAWYER/VIEWER denied at path level
- [Phase 74]: operator_config_src added to all gates that already compose admin_api_src (not lawyer-web-chat)
- [Phase 74]: Freeze allowlist keeps exact-set equality; operator_config_enabled added as v1.10 flag
- [Phase 74]: Sections-only: bare /config and unknown sections → 404; no full-document GET
- [Phase 74]: Providers PUT body prefers list (section value); optional providers unwrap
- [Phase 74]: Auth then method: unauthorized still 401 before operational 405
- [Phase 74]: Evolved test_no_put_handler_exists into put-exists + 405 operational PUT (Pitfall 1)
- [Phase 74]: RBAC /config cases use temp store + operator_config_enabled=True for allow paths
- [Phase 74]: TDD RED skipped: handlers already landed in 74-02; this plan is proof-only
- [Phase 75 planning]: Store wins when OperatorConfigStore.path exists; else env fallback (OQ-1)
- [Phase 75 planning]: WeCom apply helper in wecom-service/channel_wiring.py; from_operator_doc on channel package (OQ-2)
- [Phase 75 planning]: Platform flags read-only on /config/channels; add wecom_channel_enabled (not channel_delivery_enabled)
- [Phase 75 planning]: Restart-to-apply MVP via metadata.apply_semantics=restart_required; no hot-reload
- [Phase 75 planning]: Enhance GET/PUT /config/channels in-place with effective dual-knob block; no platform-flag PUT
- [Phase ?]: wecom_channel_enabled placed next to qqbot_channel_enabled; never reuse channel_delivery_enabled
- [Phase 75]: Wave 0 scaffolds intentionally fail under discover until Plans 02–05 implement production code
- [Phase 75]: operator_config_src added only to qqbot-service and wecom-service gates (admin gates already covered in Phase 74)
- [Phase 75]: Dual-knob AND lives in wecom-service channel_wiring; channel package stays flag-free
- [Phase 75]: enabled = wecom_channel_enabled AND doc.enabled (never channel_delivery_enabled)
- [Phase 75]: Store wins when OperatorConfigStore.path.exists; env is bootstrap fallback only
- [Phase 75]: effective is additive on channels only; non-channels keep prior metadata shape
- [Phase 75]: apply_semantics=restart_required documents restart-to-apply MVP (no hot-reload)
- [Phase 75]: Platform flags remain read-only via RuntimeFeatureFlags — never accepted on PUT
- [Phase 75]: OQ-1: store wins when store.path.exists(); else from_env — not content-heuristic overrides
- [Phase 75]: from_operator_doc accepts Mapping or QQBotChannelDoc-shaped object; no RuntimeFeatureFlags import in config.py
- [Phase 75]: When host_config is None, wiring always calls load_qqbot_host_config (store and/or env) rather than empty QQBotHostConfig()
- [Phase 75]: MVP apply semantics remain restart_required — no hot-reload
- [Phase 75]: Dedicated channels.py module (render + parse) rather than only dashboard section renderer
- [Phase 75]: WeCom platform label uses wecom_channel_enabled (never channel_delivery_enabled)
- [Phase 75]: Minimal csrf_token field included; Phase 78 owns complete CSRF surface verification
- [Phase 75]: POST only on /config/channels; operational routes stay GET-only (405 otherwise)

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

Last session: 2026-07-10T10:40:17.308Z
Stopped at: Phase 76 UI-SPEC approved
Resume file: .planning/phases/76-provider-registry-model-catalog/76-UI-SPEC.md
Architecture basis: .planning/research/SUMMARY.md
Execution plan: .planning/ROADMAP.md
Requirements: .planning/REQUIREMENTS.md (20/20 mapped)
Research summary: .planning/research/SUMMARY.md
Phase 75 plans: .planning/phases/75-channel-config-apply/75-0{1,2,3,4,5}-PLAN.md
Phase 75 validation: .planning/phases/75-channel-config-apply/75-VALIDATION.md
Phase 75 verification: .planning/phases/75-channel-config-apply/75-VERIFICATION.md
Phase 74 verification: .planning/phases/74-admin-config-api-rbac/74-VERIFICATION.md
Phase 74 plans: .planning/phases/74-admin-config-api-rbac/74-0{1,2,3}-PLAN.md
Phase 73 verification: .planning/phases/73-operator-config-foundation/73-VERIFICATION.md
Parallel human gate (do not auto-complete): .planning/phases/08-lawyer-trial-acceptance/
v1.9 archive: .planning/milestones/v1.9-ROADMAP.md

## Operator Next Steps

- Plan Phase 76: `/gsd-plan-phase 76` (or discuss first)
- Carried human gates (Phase 5 / 8 / QQ `--live`) remain open — do not auto-close
