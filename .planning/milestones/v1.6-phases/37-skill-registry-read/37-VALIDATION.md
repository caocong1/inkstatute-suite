---
phase: 37
slug: skill-registry-read
status: draft
nyquist_compliant: true
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
| 37-01-01 | 01 | 1 | SKILL-01 | — | Package structure + manifest-to-descriptor mapper produces correct fields | unit | `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src python -m unittest discover -s packages/skill-registry/tests -p "test_mapper.py"` | ❌ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | SKILL-01 | — | SkillRegistry list/get/search return NeutralSkillDescriptor + read-only enforcement (no write methods) | unit | `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src python -m unittest discover -s packages/skill-registry/tests -p "test_registry.py"` | ❌ W0 | ⬜ pending |
| 37-02-01 | 02 | 2 | SKILL-02 | — | Discovery index follows Cloudflare RFC v0.2.0 format ($schema, skills[] with name/type/description/url/digest) | unit | `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src python -m unittest discover -s packages/skill-registry/tests -p "test_discovery.py"` | ❌ W0 | ⬜ pending |
| 37-02-02 | 02 | 2 | SKILL-01, SKILL-02 | — | API handler returns 200 for /skills, /skills/{id}, /skills/search, /.well-known/agent-skills/index.json + feature flag default-off rejects requests | unit | `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/skill-registry/tests -p "test_api.py"` | ❌ W0 | ⬜ pending |
| 37-03-01 | 03 | 3 | SKILL-01, SKILL-02 | — | V2 gate integration (new skill-registry gate + compileall update) | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 37-03-02 | 03 | 3 | — | — | Contract freeze not violated (existing freeze tests green) | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 package structure is created as the first step of Plan 37-01 Task 01 (package structure + manifest mapper). The following files are created by that task:

- [ ] `packages/skill-registry/pyproject.toml` — package definition (Plan 37-01 Task 01)
- [ ] `packages/skill-registry/src/inkstatute_skill_registry/__init__.py` — package init (Plan 37-01 Task 01)
- [ ] `packages/skill-registry/tests/test_mapper.py` — mapper tests (Plan 37-01 Task 01)
- [ ] `packages/skill-registry/tests/test_registry.py` — registry tests (Plan 37-01 Task 02)
- [ ] `packages/skill-registry/tests/test_discovery.py` — discovery tests (Plan 37-02 Task 01)
- [ ] `packages/skill-registry/tests/test_api.py` — API tests (Plan 37-02 Task 02)

*No separate Wave 0 task needed — package structure is created inline by Plan 37-01 Task 01 as its first action step. Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

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
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-04
