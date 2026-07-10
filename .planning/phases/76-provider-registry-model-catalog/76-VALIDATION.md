---
phase: 76
slug: provider-registry-model-catalog
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-11
---

# Phase 76 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` suites collected by `pytest` |
| **Config file** | Existing per-package `tests/` layouts; no new framework config |
| **Quick run command** | `PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src python -m pytest packages/operator-config/tests/test_schemas.py packages/operator-config/tests/test_validate_document.py packages/operator-config/tests/test_catalog.py -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~30 seconds for targeted phase tests |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` command from its plan.
- **After every plan wave:** Run all targeted tests introduced or changed by that wave.
- **Before `$gsd-verify-work`:** `python scripts/run_v2_gates.py` must be green.
- **Max feedback latency:** 30 seconds for targeted task checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 76-01-01 | 01 | 1 | PROV-01, PROV-02, PROV-03 | T-76-01..04 | Reject malformed allowlists, duplicate provider IDs, and secret-bearing validation output | unit | `PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src python -m pytest packages/operator-config/tests/test_schemas.py packages/operator-config/tests/test_validate_document.py packages/operator-config/tests/test_catalog.py -q` | ❌ W0 | ⬜ pending |
| 76-01-02 | 01 | 1 | PROV-01..04 | T-76-SC | Create importable Wave 0 tests without adding runtime dependencies | source | `test -f services/admin-console-api/tests/test_config_providers.py && test -f services/admin-console-api/tests/test_config_catalog.py && test -f services/admin-console-api/tests/test_config_probe.py && test -f services/admin-web-ui/tests/test_providers_form.py && test -f services/admin-web-ui/tests/test_catalog_form.py` | ❌ W0 | ⬜ pending |
| 76-02-01 | 02 | 2 | PROV-04 | T-76-05..09 | Probe fails closed, stays non-mutating, and never reads or returns sensitive bodies | unit + integration | `PYTHONPATH=services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -m pytest services/admin-console-api/tests/test_config_probe.py -q` | ❌ W0 | ⬜ pending |
| 76-02-02 | 02 | 2 | PROV-01..04 | T-76-05..09 | Provider/catalog APIs enforce flag and RBAC gates while preserving refs-only payloads | integration | `PYTHONPATH=services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -m pytest services/admin-console-api/tests/test_config_providers.py services/admin-console-api/tests/test_config_catalog.py services/admin-console-api/tests/test_config_probe.py -q` | ❌ W0 | ⬜ pending |
| 76-03-01 | 03 | 2 | PROV-01, PROV-02, PROV-03 | T-76-10..14 | SSR escapes dynamic content and renders only unresolved secret refs | source + unit | `PYTHONPATH=services/admin-web-ui/src:services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -c "from admin_web_ui.providers import render_providers_page, parse_providers_form, PRIMARY_CTA; from admin_web_ui.catalog import render_catalog_page, parse_catalog_form; from admin_web_ui.dashboard import _page_template; html=_page_template('test',''); assert 'Provider Config' in html and 'Model Catalog' in html; assert PRIMARY_CTA == 'Save provider config'"` | ❌ W0 | ⬜ pending |
| 76-03-02 | 03 | 2 | PROV-01..04 | T-76-10..14 | SSR rejects empty destructive submits, keeps probe output generic, and does not claim live acceptance | unit + integration | `PYTHONPATH=services/admin-web-ui/src:services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -m pytest services/admin-web-ui/tests/test_providers_form.py services/admin-web-ui/tests/test_catalog_form.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/operator-config/tests/test_catalog.py` — catalog integrity and `supports_vision` coverage for PROV-01/PROV-03.
- [ ] `services/admin-console-api/tests/test_config_providers.py` — provider roundtrip, planted-secret, duplicate-ID, flag, and RBAC coverage.
- [ ] `services/admin-console-api/tests/test_config_catalog.py` — catalog metadata and selection roundtrip coverage.
- [ ] `services/admin-console-api/tests/test_config_probe.py` — fail-closed, non-mutating, no-body-read probe coverage.
- [ ] `services/admin-web-ui/tests/test_providers_form.py` — provider SSR render, parse, route, and safety coverage.
- [ ] `services/admin-web-ui/tests/test_catalog_form.py` — catalog SSR render, selection, vision badge, and route coverage.

---

## Manual-Only Verifications

All phase behaviors have automated verification. External provider reachability is represented by mocked probe outcomes; this phase must not claim live provider, WeCom, QQ, or lawyer-trial acceptance.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 dependencies.
- [x] Sampling continuity: no three consecutive tasks lack automated verification.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags.
- [x] Targeted feedback latency is under 30 seconds.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** approved 2026-07-11
