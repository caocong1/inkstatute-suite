---
phase: 60
slug: qq-event-normalization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing project stack) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing) |
| **Quick run command** | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -x -q` |
| **Full suite command** | `python -m pytest packages/channels/qqbot/tests/ -x -q && python -m pytest tests/test_no_wecom_import.py -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest packages/channels/qqbot/tests/test_normalization.py -x -q`
- **After every plan wave:** Run `python -m pytest packages/channels/qqbot/tests/ -x -q && python -m pytest tests/test_no_wecom_import.py -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 60-01-01 | 01 | 1 | INGRESS-03 | — | N/A — pure parsing, no IO | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k envelope -x -q` | ❌ W0 | ⬜ pending |
| 60-01-02 | 01 | 1 | INGRESS-03 | — | Reject malformed envelope (op missing) | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k dispatch -x -q` | ❌ W0 | ⬜ pending |
| 60-01-03 | 01 | 2 | INGRESS-04 | — | @-bot prefix stripped, no PII in conversation_id beyond openid | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k c2c -x -q` | ❌ W0 | ⬜ pending |
| 60-01-04 | 01 | 2 | INGRESS-04 | — | Group scene-aware conversation_id partition | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k group -x -q` | ❌ W0 | ⬜ pending |
| 60-01-05 | 01 | 2 | INGRESS-05 | — | FeedbackSource.CARD_BUTTON frozen enum used (no new values) | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k interaction -x -q` | ❌ W0 | ⬜ pending |
| 60-01-06 | 01 | 3 | INGRESS-03 | — | Validation challenge op=13 routed correctly | unit | `python -m pytest packages/channels/qqbot/tests/test_normalization.py -k validation -x -q` | ❌ W0 | ⬜ pending |
| 60-02-01 | 02 | 3 | INGRESS-03,04,05 | — | adapter.normalize_inbound delegates to normalization.py | unit | `python -m pytest packages/channels/qqbot/tests/test_adapter_normalize.py -x -q` | ❌ W0 | ⬜ pending |
| 60-02-02 | 02 | 3 | (invariant) | — | test_no_wecom_import.py covers normalization.py | unit | `python -m pytest tests/test_no_wecom_import.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_normalization.py` — stubs for INGRESS-03, INGRESS-04, INGRESS-05
- [ ] `packages/channels/qqbot/tests/test_adapter_normalize.py` — stubs for adapter delegation
- [ ] `packages/channels/qqbot/tests/fixtures/` — QQ Bot gateway envelope fixtures (c2c, group, interaction, validation)

*Existing pytest infrastructure in `packages/channels/qqbot/` covers framework setup.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — pure-function parsing with fixture replay.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
