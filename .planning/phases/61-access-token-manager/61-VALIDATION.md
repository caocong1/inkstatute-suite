---
phase: 61
slug: access-token-manager
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib, IsolatedAsyncioTestCase for async tests) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing) |
| **Quick run command** | `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -v` |
| **Full suite command** | `python3 -m unittest discover -s packages/channels/qqbot/tests -v && python3 -m unittest tests.test_no_wecom_import -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -v`
- **After every plan wave:** Run `python3 -m unittest discover -s packages/channels/qqbot/tests -v && python3 -m unittest tests.test_no_wecom_import -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 61-01-01 | 01 | 1 | EGRESS-01 | T-61-01 | No token leakage in errors/logs; credentials injected not hardcoded | unit | `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -v` | ❌ W0 | ⬜ pending |
| 61-01-02 | 01 | 1 | EGRESS-01 | T-61-02 | 7200s TTL + 60s pre-expiry refresh window enforced | unit | `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -k lifecycle -v` | ❌ W0 | ⬜ pending |
| 61-01-03 | 01 | 1 | EGRESS-01 | T-61-03 | asyncio.Lock single-flight: concurrent refresh produces 1 HTTP call | unit | `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -k concurrent -v` | ❌ W0 | ⬜ pending |
| 61-01-04 | 01 | 1 | EGRESS-01 | T-61-04 | HTTP/network/API error handling: TokenError raised, no silent fallback | unit | `python3 -m unittest packages.channels.qqbot.tests.test_token_manager -k error -v` | ❌ W0 | ⬜ pending |
| 61-01-05 | 01 | 1 | (invariant) | — | dependencies = [] holds; no wecom_service import | unit | `python3 -m unittest tests.test_no_wecom_import -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_token_manager.py` — stubs for EGRESS-01 (lifecycle, concurrent, error handling)

*Existing pytest/unittest infrastructure in `packages/channels/qqbot/` covers framework setup.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — token manager is pure logic with injectable transport (no live HTTP in tests).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-08
