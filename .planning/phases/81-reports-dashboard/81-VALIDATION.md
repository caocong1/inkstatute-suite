---
phase: 81
slug: reports-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-13
---

# Phase 81 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (existing repo convention) |
| **Config file** | none — uses `python -m unittest` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.conversation-read-view.tests.test_reports_aggregator services.conversation-read-view.tests.test_reports_perf services.admin-console-api.tests.test_reports services.admin-web-ui.tests.test_dashboard_reports -q` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest discover -s services -p "test_*.py" -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command.
- **After every plan wave:** Run the full suite command.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 60 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 81-01-01 | 01 | 1 | OBS-01, OBS-03 | T-81-01 / T-81-03 | Bounded scanner returns correct counts and does not load full file | unit | `python -m unittest services.conversation-read-view.tests.test_reports_aggregator -q` | pending | ⬜ pending |
| 81-01-02 | 01 | 1 | OBS-03 | T-81-03 | 50k-event fixture completes in <1s with bounded memory | perf | `python -m unittest services.conversation-read-view.tests.test_reports_perf -q` | pending | ⬜ pending |
| 81-01-03 | 01 | 1 | OBS-02 | T-81-01 | `/reports` API returns aggregate JSON from existing sources | unit | `python -m unittest services.admin-console-api.tests.test_reports -q` | pending | ⬜ pending |
| 81-01-04 | 01 | 1 | OBS-01 | T-81-02 / T-81-05 | `/reports` page renders escaped metrics with time selector | unit | `python -m unittest services.admin-web-ui.tests.test_dashboard_reports -q` | pending | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing `unittest` infrastructure covers all phase requirements.
- No new framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual report layout on a laptop browser | POLISH-03 | Automated SSR assertions cannot verify exact visual layout | Open `/reports`, select `30d`, confirm metric cards are readable without horizontal scroll at 1280px. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
