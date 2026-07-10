---
phase: 73
slug: operator-config-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-10
---

# Phase 73 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (stdlib; matches admin-console-api / platform-runtime gates) |
| **Config file** | none — discover via `python -m unittest discover -s packages/operator-config/tests` |
| **Quick run command** | `PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src python -m unittest discover -s packages/operator-config/tests -q` |
| **Full suite command** | Quick command + `PYTHONPATH=packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_feature_flags.py' -q` + `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages.contract-test-suite.tests.test_gate_coverage -q` + `PYTHONPATH=services/admin-console-api/src:packages/platform-runtime/src:packages/rbac/src python -m unittest discover -s services/admin-console-api/tests -p 'test_read_only.py' -q` |
| **Estimated runtime** | ~5–15s quick; ~20–40s full (operator-config + flag + gate-coverage + admin read-only) |

---

## Sampling Rate

- **After every task commit:** Run the task `<automated>` command from the active PLAN.md
- **After every plan wave:** Run quick command (operator-config discover); after Wave 3 also run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for quick command

**Critical:** Phase verification must **not** require admin HTTP PUT, live Hermes filesystem writes, or live channel credentials. Carried human gates (Phase 5 / Phase 8 / QQ `--live`) must not be auto-closed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 73-01-01 | 01 | 1 | CFG-01 | T-73-SC | Empty-deps `inkstatute-operator-config` scaffold imports errors | smoke | `test -f packages/operator-config/pyproject.toml && grep -q 'dependencies = \[\]' … && PYTHONPATH=packages/operator-config/src python -c "from inkstatute_operator_config.errors import …"` | ❌ in-plan TDD | ⬜ pending |
| 73-01-02 | 01 | 1 | CFG-01 | T-73-01 / T-73-02 | Frozen refs-only OperatorConfigDocument shapes; enabled=False; `*_ref` credentials | unit | `PYTHONPATH=packages/operator-config/src python -m unittest discover -s packages/operator-config/tests -p 'test_schemas.py' -q` | ❌ in-plan TDD | ⬜ pending |
| 73-01-03 | 01 | 1 | CFG-01 | T-73-01 | Shape-only secret-ref normalize; planted raw secrets rejected without echo; no qqbot-service import | unit | `PYTHONPATH=packages/operator-config/src python -m unittest discover -s packages/operator-config/tests -p 'test_secret_refs.py' -q` | ❌ in-plan TDD | ⬜ pending |
| 73-02-01 | 02 | 2 | CFG-01 / CFG-03 | T-73-04 / T-73-05 | `validate_document` accepts default doc; Hermes ban + refs-only checks wired | smoke | `PYTHONPATH=packages/operator-config/src python -c "from inkstatute_operator_config.validate import validate_document; … validate_document(OperatorConfigDocument())"` | ❌ in-plan TDD | ⬜ pending |
| 73-02-02 | 02 | 2 | CFG-03 / CFG-01 | T-73-04 / T-73-05 | Hermes `~/.hermes` / profile authority rejected; planted secrets/forbidden keys rejected without echo | unit | `… -p 'test_hermes_banlist.py' -q` && `… -p 'test_validate_document.py' -q` | ❌ in-plan TDD | ⬜ pending |
| 73-03-01 | 03 | 3 | CFG-02 | T-73-07 | `operator_config_enabled` defaults False; `require_enabled` gates | unit | `PYTHONPATH=packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_feature_flags.py' -q` | ⚠️ extend existing | ⬜ pending |
| 73-03-02 | 03 | 3 | CFG-01 / CFG-02 | T-73-07 / T-73-08 / T-73-09 | Atomic refs-only persist when ON; save refuses when OFF with no file side effects | unit | `… -p 'test_store.py' -q` && `… -p 'test_flag_gate.py' -q` | ❌ in-plan TDD | ⬜ pending |
| 73-03-03 | 03 | 3 | CFG-01 / CFG-02 | T-73-10 / T-73-SC | V2 gate covers `packages/operator-config/src`; admin `test_read_only` still green; runtime config gitignored | unit+meta | operator-config discover + `test_gate_coverage` + admin `test_read_only.py` | ⚠️ harness ✅; entry ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → verify crosswalk

| Req | Covered by task verifies | Primary test files |
|-----|--------------------------|--------------------|
| CFG-01 | 73-01-01..03, 73-02-01..02, 73-03-02..03 | `test_schemas.py`, `test_secret_refs.py`, `test_validate_document.py`, `test_store.py` |
| CFG-02 | 73-03-01, 73-03-02, 73-03-03 | `test_feature_flags.py`, `test_flag_gate.py` |
| CFG-03 | 73-02-01, 73-02-02 | `test_hermes_banlist.py`, `test_validate_document.py` |

Exact `<automated>` strings live in `73-01-PLAN.md`, `73-02-PLAN.md`, `73-03-PLAN.md` — executors must run those commands, not paraphrases.

---

## Wave 0 Requirements

**Wave 0 is in-plan TDD** (no separate Wave 0 plan). Each `tdd="true"` task in plans 73-01..73-03 creates its test file(s) with the implementation. Until execute starts, files below are MISSING by design.

- [ ] `packages/operator-config/` package skeleton + `pyproject.toml` (`dependencies = []`) — Plan 01 Task 1
- [ ] `packages/operator-config/tests/test_schemas.py` — CFG-01 document shapes — Plan 01 Task 2
- [ ] `packages/operator-config/tests/test_secret_refs.py` — planted secret rejection — Plan 01 Task 3
- [ ] `packages/operator-config/tests/test_hermes_banlist.py` — CFG-03 — Plan 02 Task 2
- [ ] `packages/operator-config/tests/test_validate_document.py` — CFG-01 document validation — Plan 02 Task 2
- [ ] `packages/operator-config/tests/test_store.py` — atomic persist round-trip — Plan 03 Task 2
- [ ] `packages/operator-config/tests/test_flag_gate.py` — CFG-02 mutate refuse — Plan 03 Task 2
- [ ] `RuntimeFeatureFlags.operator_config_enabled` field + explicit assert in `packages/platform-runtime/tests/test_feature_flags.py` — Plan 03 Task 1
- [ ] `scripts/run_v2_gates.py` operator-config gate + compileall path — Plan 03 Task 3

*Existing infrastructure:* `unittest`, `packages/platform-runtime/tests/test_feature_flags.py` (introspection), `packages/contract-test-suite/tests/test_gate_coverage.py`, `services/admin-console-api/tests/test_read_only.py`.

Mark `wave_0_complete: true` in frontmatter only after the in-plan TDD files above exist and the Per-Task map statuses are green.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *(none for Phase 73 core)* | — | All CFG-01..03 behaviors have automated verifies | — |
| Phase 5 live WeCom UAT | — (carried) | Separate human gate | Do **not** mark complete from Phase 73 |
| Phase 8 lawyer trial | — (carried) | Separate human gate | Do **not** mark complete from Phase 73 |
| QQ `--live` OpenAPI acceptance | — (carried) | Separate human gate | Do **not** mark complete from Phase 73 |

*All phase behaviors for CFG-01..03 have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 (in-plan TDD) dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 gaps documented as in-plan TDD (no separate Wave 0 plan)
- [x] No watch-mode flags
- [x] Feedback latency &lt; 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter (strategy map complete; statuses pending execute)
- [x] Admin HTTP mutate **not** required for Phase 73
- [x] Carried human gates must not be auto-closed

**Approval:** pending execution
