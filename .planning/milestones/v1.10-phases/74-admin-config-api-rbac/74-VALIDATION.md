---
phase: 74
slug: admin-config-api-rbac
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-10
---

# Phase 74 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (stdlib; matches admin-console-api / rbac / operator-config gates) |
| **Config file** | none — discover via `python -m unittest discover` |
| **Quick run command** | `PYTHONPATH=services/admin-console-api/src:packages/operator-config/src:packages/platform-runtime/src:packages/rbac/src:packages/platform-contract/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest services.admin-console-api.tests.test_config_api services.admin-console-api.tests.test_read_only -q` |
| **Full suite command** | Quick command + `… test_rbac_integration test_contract_freeze test_routes -q` + `PYTHONPATH=packages/rbac/src:services/admin-console-api/src:packages/platform-runtime/src:packages/platform-contract/src:services/conversation-read-view/src:services/feedback-service/src:packages/operator-config/src python -m unittest discover -s packages/rbac/tests -q` + `PYTHONPATH=… python scripts/scan_rbac_annotations.py` |
| **Estimated runtime** | ~10–20s quick; ~30–60s full (admin + rbac + annotation scan) |

---

## Sampling Rate

- **After every task commit:** Run the task `<automated>` command from the active PLAN.md
- **After every plan wave:** Wave 1 → freeze + matrix/routes + scan; Wave 2 → import smoke for config_api/api; Wave 3 → quick command then full suite
- **Before `/gsd-verify-work`:** Full suite must be green (admin-console-api discover + rbac discover + annotation scan)
- **Max feedback latency:** 60 seconds for quick command

**Critical:** Phase verification must **not** require live WeCom/QQ credentials, Hermes filesystem writes, or SSR UI. Carried human gates (Phase 5 / Phase 8 / QQ `--live`) must not be auto-closed. Tests must inject temp-path `OperatorConfigStore` — never commit or rely on `.inkstatute/operator-config.json`.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 74-01-01 | 01 | 1 | ADM-01 / carry | T-74-SC | Freeze allowlist includes `operator_config_enabled`; operator-config on admin-related gate PYTHONPATH | unit+meta | `… test_contract_freeze -q` + assert `operator_config_src` count | ⚠️ exists (broken freeze) | ⬜ pending |
| 74-01-02 | 01 | 1 | ADM-01 | T-74-01 / T-74-02 | `/config` → ADMIN+OPERATOR; ROUTE_PREFIXES parity; scan green | unit+CI | `… test_matrix test_routes -q` + `scan_rbac_annotations.py` | ⚠️ extend existing | ⬜ pending |
| 74-02-01 | 02 | 2 | ADM-01 / ADM-03 | T-74-04 / T-74-05 / T-74-06 | Section GET/PUT over store; disabled→403; validation no-echo; sections-only | smoke | import `CONFIG_SECTIONS` + handlers | ❌ Wave 0 | ⬜ pending |
| 74-02-02 | 02 | 2 | ADM-01 / ADM-03 | T-74-03 / T-74-04 | `handle_admin_put` exported; operational PUT 405; GET dispatches `/config/*` | smoke | import `handle_admin_put` from package | ❌ Wave 0 | ⬜ pending |
| 74-03-01 | 03 | 3 | ADM-01 / SC#4 | T-74-04 / T-74-05 | Flag OFF 403 + no file side effects; planted secrets 400 no-echo; section happy paths | unit | `… test_config_api -q` | ❌ Wave 0 | ⬜ pending |
| 74-03-02 | 03 | 3 | ADM-01 / ADM-03 | T-74-01 / T-74-03 | Evolve read-only → 405 operational PUT; lawyer/viewer `/config` 403 | unit | `… test_read_only test_rbac_integration -q` | ⚠️ evolve existing | ⬜ pending |
| 74-03-03 | 03 | 3 | ADM-01 / ADM-03 | T-74-01..05 | Full admin + rbac discovers green; README documents surface | unit+docs | admin discover + rbac discover | ⚠️ README exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / exists-needs-evolve*

### Requirement → verify crosswalk

| Req | Covered by task verifies | Primary test files |
|-----|--------------------------|--------------------|
| ADM-01 | 74-01-02, 74-02-01..02, 74-03-01..03 | `test_matrix.py`, `test_config_api.py`, `test_rbac_integration.py` |
| ADM-03 | 74-02-02, 74-03-01..02 | `test_read_only.py`, `test_config_api.py` |
| SC#4 (ROADMAP) | 74-02-01, 74-03-01 | `test_config_api.py` (flag OFF) |

Exact `<automated>` strings live in `74-01-PLAN.md`, `74-02-PLAN.md`, `74-03-PLAN.md` — executors must run those commands, not paraphrases.

---

## Wave 0 Requirements

Wave 0 gaps are closed **in-plan** (Plan 01 Task 1 + Plan 03 test creation), not a separate Wave 0 plan:

- [ ] Fix `services/admin-console-api/tests/test_contract_freeze.py` expected flags (`operator_config_enabled`) — Plan 01 Task 1
- [ ] Add `packages/operator-config/src` to admin-console-api / admin-web-ui / rbac / rbac-annotation-scan gate PYTHONPATH — Plan 01 Task 1
- [ ] Create `services/admin-console-api/tests/test_config_api.py` — Plan 03 Task 1
- [ ] Evolve `services/admin-console-api/tests/test_read_only.py` write-denial contract — Plan 03 Task 2
- [ ] Extend `services/admin-console-api/tests/test_rbac_integration.py` for `/config` — Plan 03 Task 2
- [ ] Framework install: none

*Existing infrastructure:* `unittest`, `packages/rbac` matrix+scan, `packages/operator-config` store/flag tests, admin auth/RBAC GET pipeline.

Mark `wave_0_complete: true` in frontmatter only after freeze is fixed, gate PYTHONPATH updated, and Plan 03 test files exist with green Per-Task statuses.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *(none for Phase 74 core)* | — | All ADM-01/03 + SC#4 behaviors have automated verifies | — |
| Phase 5 live WeCom UAT | — (carried) | Separate human gate | Do **not** mark complete from Phase 74 |
| Phase 8 lawyer trial | — (carried) | Separate human gate | Do **not** mark complete from Phase 74 |
| QQ `--live` OpenAPI acceptance | — (carried) | Separate human gate | Do **not** mark complete from Phase 74 |

*All phase behaviors for ADM-01/ADM-03 have automated verification.*

---

## Resolved Research Open Questions

| # | Question | Resolution (planning) |
|---|----------|------------------------|
| OQ1 | Whole-document GET `/config`? | **Sections-only** — implement `/config/{channels,providers,catalog,vision}` only; bare `/config` → 404 |
| OQ2 | PUT on `/sessions` → 405 or 404? | **405** `method_not_allowed` after auth |
| OQ3 | Re-export `document_from_payload` from package `__init__`? | **No** — import from `inkstatute_operator_config.store` |
| A1 | Lawyer/viewer GET deny? | **Yes** — path-level ADMIN+OPERATOR for GET and PUT |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 (in-plan) dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 gaps documented as in-plan (Plans 01 + 03)
- [x] No watch-mode flags
- [x] Feedback latency &lt; 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter (strategy map complete; statuses pending execute)
- [x] SSR / channel apply / live acceptance **not** required for Phase 74
- [x] Carried human gates must not be auto-closed

**Approval:** pending execution
