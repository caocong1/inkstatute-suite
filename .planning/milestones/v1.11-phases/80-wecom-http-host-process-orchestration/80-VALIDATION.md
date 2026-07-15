---
phase: 80
slug: wecom-http-host-process-orchestration
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-13
verified: 2026-07-13
---

# Phase 80 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (stdlib) |
| **Config file** | none — tests run with `PYTHONPATH` includes |
| **Quick run command** | `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:packages/channel-core/src:packages/channels/wecom/src:packages/channels/qqbot/src:packages/rbac/src:packages/backends/hermes/src:services/wecom-service/src:services/qqbot-service/src:services/feedback-service/src:services/conversation-read-view/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.wecom-service.tests.test_http_server services.admin-console-api.tests.test_process_supervisor services.admin-web-ui.tests.test_processes -q` |
| **Full suite command** | `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:packages/channel-core/src:packages/channels/wecom/src:packages/channels/qqbot/src:packages/rbac/src:packages/backends/hermes/src:services/wecom-service/src:services/qqbot-service/src:services/feedback-service/src:services/conversation-read-view/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest discover -s services -p 'test_*.py' -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the test files touched by the task.
- **After every plan wave:** Run the full suite command for the affected services.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 80-01-01 | 01 | 1 | ORCH-03 | T-80-03 | No command injection; `name` allowlisted | integration | `PYTHONPATH=... python -m unittest services.wecom-service.tests.test_http_server -q` | ✅ | passed |
| 80-01-02 | 01 | 1 | ORCH-03 | T-80-02 | No secrets in webhook logs | unit | `PYTHONPATH=... python -m unittest services.wecom-service.tests.test_webhook -q` | ✅ | passed |
| 80-01-03 | 01 | 1 | ORCH-03 | T-80-03 | QQBot `__main__.py` gates on `qqbot_channel_enabled` | integration | `PYTHONPATH=... python -m unittest services.qqbot-service.tests.test_main -q` | ✅ | passed |
| 80-02-01 | 01 | 2 | ORCH-02, ORCH-05 | T-80-04 | Children reaped on stop; no orphaned zombies | integration | `PYTHONPATH=... python -m unittest services.admin-console-api.tests.test_process_supervisor -q` | ✅ | passed |
| 80-02-02 | 01 | 2 | ORCH-05 | T-80-07 | `/health` probe response excludes secrets | unit | same as above | ✅ | passed |
| 80-03-01 | 01 | 3 | ORCH-01 | T-80-01 | CSRF on process actions | integration | `PYTHONPATH=... python -m unittest services.admin-web-ui.tests.test_processes -q` | ✅ | passed |
| 80-03-02 | 01 | 3 | ORCH-04 | T-80-05 | Config saved before restart | integration | `PYTHONPATH=... python -m unittest services.admin-console-api.tests.test_config_restart -q` | ✅ | passed |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `services/wecom-service/tests/test_http_server.py` — stub/integration tests for `ORCH-03`
- [x] `services/wecom-service/tests/test_webhook.py` — unit tests for `WeComWebhookServer`/`handle_wecom_webhook_request`
- [x] `services/qqbot-service/tests/test_main.py` — integration tests for `qqbot_service.__main__`
- [x] `services/admin-console-api/tests/test_process_supervisor.py` — integration tests for `ProcessSupervisor` lifecycle and health probes
- [x] `services/admin-web-ui/tests/test_processes.py` — integration tests for `/processes` UI and CSRF
- [x] `services/admin-console-api/tests/test_config_restart.py` — integration tests for config-save → restart wiring

*Existing `unittest` infrastructure covers the phase; Wave 0 creates the new test files listed above.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Graceful console shutdown does not orphan WeCom/QQBot children | ORCH-02 | Cross-process signal timing | Start console + children; send `SIGTERM` to console; assert children exit within 10s. |
| Live `/health` probe from console to a real WeCom host | ORCH-05 | Requires a running child process | Start `wecom_service` on a port; start `admin_console_api`; assert `/processes` shows `live` status. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
