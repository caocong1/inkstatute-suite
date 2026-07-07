---
phase: 59
slug: ed25519-signature-verification-validation-challenge
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages/channels/qqbot/tests/test_signature.py -v` |
| **Full suite command** | `python3 scripts/run_v2_gates.py` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run `python3 scripts/run_v2_gates.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 59-01-01 | 01 | 1 | INGRESS-01 | T-59-01 | Ed25519 key derivation from BotSecret, signature verification over timestamp+raw_body | unit | `python3 -m unittest packages/channels/qqbot/tests/test_signature.py -v` | ❌ W0 | ⬜ pending |
| 59-01-02 | 01 | 1 | INGRESS-02 | T-59-02 | op=13 validation challenge signing {event_ts + plain_token} | unit | `python3 -m unittest packages/channels/qqbot/tests/test_signature.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_signature.py` — tests for Ed25519 key derivation, signature verification, validation challenge
- [ ] Official QQ demo test vectors for signature verification

*Existing infrastructure (run_v2_gates.py) covers gate-level verification.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live QQ Bot webhook signature verification | INGRESS-01 | Requires live QQ Bot platform with real BotSecret | Run `scripts/smoke_test.py` (Phase 67) with real credentials |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
