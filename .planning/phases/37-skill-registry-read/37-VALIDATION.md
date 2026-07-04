---
phase: 37
slug: skill-registry-read
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-04
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x / unittest (existing) |
| **Config file** | `packages/skill-registry/pyproject.toml` (new — Wave 0 creates) |
| **Quick run command** | `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src python -m pytest packages/skill-registry/tests/ -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~70 seconds (10 gates including new skill-registry gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (skill-registry tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 10 gates)
- **Max feedback latency:** 70 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | SKILL-01 | — | SkillRegistry list/get/search return NeutralSkillDescriptor | unit | `pytest packages/skill-registry/tests/test_registry.py` | ❌ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | SKILL-01 | — | Manifest-to-descriptor mapper produces correct fields | unit | `pytest packages/skill-registry/tests/test_mapper.py` | ❌ W0 | ⬜ pending |
| 37-01-03 | 01 | 1 | SKILL-01 | — | Read-only enforcement (no write methods) | unit | `pytest packages/skill-registry/tests/test_registry.py -k read_only` | ❌ W0 | ⬜ pending |
| 37-02-01 | 02 | 1 | SKILL-02 | — | Discovery index follows Cloudflare RFC v0.2.0 format | unit | `pytest packages/skill-registry/tests/test_discovery.py` | ❌ W0 | ⬜ pending |
| 37-02-02 | 02 | 1 | SKILL-02 | — | /.well-known/agent-skills/index.json route returns 200 | unit | `pytest packages/skill-registry/tests/test_discovery.py -k well_known` | ❌ W0 | ⬜ pending |
| 37-02-03 | 02 | 1 | SKILL-01 | — | Feature flag default-off rejects requests when disabled | unit | `pytest packages/skill-registry/tests/test_api.py -k feature_flag` | ❌ W0 | ⬜ pending |
| 37-03-01 | 03 | 2 | SKILL-01, SKILL-02 | — | V2 gate integration (new skill-registry gate + compileall update) | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 37-03-02 | 03 | 2 | — | — | Contract freeze not violated (existing freeze tests green) | unit | `pytest packages/contract-test-suite/tests/test_contract_freeze.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/skill-registry/pyproject.toml` — package definition
- [ ] `packages/skill-registry/src/inkstatute_skill_registry/__init__.py` — package init
- [ ] `packages/skill-registry/tests/test_registry.py` — stub for SkillRegistry tests
- [ ] `packages/skill-registry/tests/test_mapper.py` — stub for manifest mapper tests
- [ ] `packages/skill-registry/tests/test_api.py` — stub for API handler tests
- [ ] `packages/skill-registry/tests/test_discovery.py` — stub for discovery endpoint tests
- [ ] `packages/skill-registry/tests/fixtures/` — test manifest fixtures

*Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — read-only registry with assertion-based tests.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 70s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
