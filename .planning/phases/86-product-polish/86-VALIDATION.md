---
phase: 86
slug: product-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-14
---

# Phase 86 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (stdlib, not pytest) |
| **Config file** | none — gates use `python -m unittest discover` |
| **Quick run command** | `python -m unittest discover -s services/admin-web-ui/tests -v` (with PYTHONPATH set) |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~30 seconds |

**PYTHONPATH for admin-web-ui tests** (from `run_v2_gates.py`):
```
services/admin-web-ui/src
services/admin-console-api/src
packages/rbac/src
services/conversation-read-view/src
services/feedback-service/src
packages/platform-contract/src
packages/platform-runtime/src
packages/operator-config/src
```

---

## Sampling Rate

- **After every task commit:** Run `python -m unittest discover -s services/admin-web-ui/tests -v` (with PYTHONPATH)
- **After every plan wave:** Run `python scripts/run_v2_gates.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 86-01-01 | 01 | 1 | POLISH-01 | T-86-01 / V7 Error Handling | 404 page escaped, no stack trace | unit | `python -m unittest services.admin_web_ui.tests.test_server.TestErrorPages.test_404_dedicated_page -v` | ❌ W0 | ⬜ pending |
| 86-01-02 | 01 | 1 | POLISH-01 | T-86-01 / V7 Error Handling | 500 page on uncaught exception, no stack trace leak | unit | `python -m unittest services.admin_web_ui.tests.test_server.TestErrorPages.test_500_on_uncaught_exception -v` | ❌ W0 | ⬜ pending |
| 86-01-03 | 01 | 1 | POLISH-01 | T-86-01 / V7 Error Handling | 500 page does not contain str(exc) or traceback | unit | `python -m unittest services.admin_web_ui.tests.test_server.TestErrorPages.test_500_no_stack_trace_leak -v` | ❌ W0 | ⬜ pending |
| 86-02-01 | 02 | 1 | POLISH-02 | — | Nav renders on all pages with active-state indication | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestNavActiveState.test_active_link_has_aria_current -v` | ❌ W0 | ⬜ pending |
| 86-02-02 | 02 | 1 | POLISH-02 | — | Nav is consistent (same nav_items on every page) | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestNavActiveState.test_nav_consistent_across_pages -v` | ❌ W0 | ⬜ pending |
| 86-02-03 | 02 | 1 | POLISH-03 | — | No horizontal scroll at 1280px (CSS audit) | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestResponsive.test_no_fixed_width_exceeds_1280 -v` | ❌ W0 | ⬜ pending |
| 86-03-01 | 03 | 1 | POLISH-04 | — | start-console.sh launches both services with env loading | integration | `bash scripts/start-console.sh --dry-run` | ❌ W0 | ⬜ pending |
| 86-03-02 | 03 | 1 | POLISH-04 | — | start-console.sh writes PID file | integration | `bash scripts/start-console.sh --dry-run && test -f .inkstatute/console-pids.json` | ❌ W0 | ⬜ pending |
| 86-04-01 | 04 | 1 | POLISH-05 | — | .env.example documents ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_TTL_SECONDS, ADMIN_WEB_UI_SECURE_COOKIE | unit | `python -m unittest services.admin_web_ui.tests.test_env_docs.test_auth_vars_documented -v` | ❌ W0 | ⬜ pending |
| 86-04-02 | 04 | 1 | POLISH-05 | — | .env.example has inline comments for all new vars | unit | `python -m unittest services.admin_web_ui.tests.test_env_docs.test_inline_comments_present -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/admin-web-ui/tests/test_server.py` — add `TestErrorPages` class covering POLISH-01 (404/500 dedicated pages, no stack trace leak)
- [ ] `services/admin-web-ui/tests/test_dashboard.py` — add `TestNavActiveState` and `TestResponsive` classes covering POLISH-02, POLISH-03
- [ ] `services/admin-web-ui/tests/test_env_docs.py` — NEW file covering POLISH-05 (.env.example completeness)
- [ ] `services/admin-web-ui/tests/test_startup_script.py` — NEW file covering POLISH-04 (script logic, PID tracking)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual layout at 1280px width | POLISH-03 | CSS rendering cannot be verified by unit test alone | Open console at 1280px viewport, confirm no horizontal scroll, readable layout |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
