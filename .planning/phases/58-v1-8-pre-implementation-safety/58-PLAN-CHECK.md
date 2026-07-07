# Plan Check — Phase 58: v1.8 Pre-Implementation Safety

**Checker:** gsd-plan-checker
**Date:** 2026-07-07
**Iteration:** 2 (revision after fixing 2 blockers from iteration 1)
**Plan checked:** 58-01-PLAN.md
**Phase requirement:** ADAPTER-04
**Result:** PLAN CHECK PASSED — 0 blocker(s), 4 warning(s)

---

## Blocker Fix Verification

### B1: Research Resolution — FIXED ✅

**Previous issue:** RESEARCH.md `## Open Questions` section (line 357) lacked `(RESOLVED)` suffix and inline `RESOLVED` markers for both questions.

**Fix verified:**
- Section heading is now `## Open Questions (RESOLVED)` (line 357) ✅
- Question 1 (gate-coverage-meta-test baseline floor): `RESOLVED: Not raising the floor in Phase 58 — it is optional and not a success criterion. The existing floor at 19 is sufficient.` (line 363) ✅
- Question 2 (consolidated test creation): `RESOLVED: Creating the consolidated test for operator visibility — Plan 58-01 Task 02 creates test_v1_8_safety_baseline.py in packages/channels/qqbot/tests/.` (line 369) ✅

Both questions have inline resolution annotations documenting the plan's chosen resolution. Dimension 11 now PASSES.

### B2: Verify Exit Code Masking — FIXED ✅

**Previous issue:** Both tasks' `<automated>` verify commands piped output through `tail -N`, which masks the exit code of test commands (pipeline always returns 0 from tail regardless of test pass/fail).

**Fix verified:**
- Task 01 verify (line 52): `set -o pipefail && python3 -c "import json; ..." && PYTHONPATH="..." python3 -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py -v` — uses `set -o pipefail &&`, no `| tail` piping ✅
- Task 02 verify (line 98): `set -o pipefail && PYTHONPATH="..." python3 -m unittest packages/channels/qqbot/tests/test_v1_8_safety_baseline.py -v && python3 scripts/run_v2_gates.py` — uses `set -o pipefail &&`, no `| tail` piping ✅

Both verify commands now properly propagate test exit codes. `set -o pipefail` ensures any non-zero exit in the chain causes the overall command to fail. Dimension 8 Check 8b now PASSES (no exit code masking).

---

## Goal-Backward Analysis

**Phase goal (ROADMAP.md):** Operator can verify that all cross-cutting v1.8 safety measures (24 V2 gates green baseline, frozen ChannelAdapter Protocol / BackendAdapter Protocol / platform-contract enums / channel-core modules unmodified, `qqbot_channel_enabled` flag default-off, `test_no_wecom_import.py` passes, `dependencies = []` invariant holds) are in place before any v1.8 feature code.

**What must be TRUE for the goal to be achieved:**
1. All V2 gates pass green (contract-test-suite gate currently FAILING due to deleted template file)
2. Frozen Protocol method counts unchanged (ChannelAdapter 6, BackendAdapter 9)
3. platform-contract SHA-256 baseline unchanged
4. `qqbot_channel_enabled` defaults to False
5. QQBot adapter does not import from wecom_service
6. `dependencies = []` invariant holds
7. No frozen surface modified during the phase

**Plan approach:** Task 01 restores the deleted `08-TRIAL-EVIDENCE-TEMPLATE.json` from git history (fixes the failing gate). Task 02 creates a consolidated `test_v1_8_safety_baseline.py` and runs the full 26-gate suite. The approach is sound — the critical regression (missing template file) is addressed first, and the consolidated test provides operator-visible verification of all 5 success criteria.

**Codebase verification performed:**
- `git show 3b12f52^:.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` returns valid JSON ✅
- ChannelAdapter Protocol has exactly 6 methods (channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health) ✅
- BackendAdapter Protocol has exactly 9 methods (backend_id, capabilities, bootstrap_check, submit_run, get_run, stream_events, cancel_run, submit_approval, collect_artifacts) ✅
- `qqbot_channel_enabled: bool = False` at line 23 of feature_flags.py ✅
- `dependencies = []` at line 15 of packages/channels/qqbot/pyproject.toml ✅
- FeedbackSource enum has exactly 4 values (card_button, text_command, web_form, admin_annotation) ✅
- Channel.QQBOT = "qqbot" ✅
- `python3 scripts/run_v2_gates.py --list` returns 26 gates ✅
- test_trial_acceptance.py lines 15-18 and 126-136 match plan's read_first references ✅

---

## Dimension Results

### Dimension 1: Requirement Coverage — PASS

| Requirement | Plans | Tasks | Status |
|-------------|-------|-------|--------|
| ADAPTER-04 | 01 | Task 01 (gate fix), Task 02 (consolidated verification) | COVERED |

ADAPTER-04 appears in plan frontmatter `requirements: [ADAPTER-04]`. Task 01 addresses the gate regression (SC-1 prerequisite). Task 02 verifies all 5 success criteria (SC-1 through SC-5). Full coverage confirmed.

### Dimension 2: Task Completeness — PASS

`gsd-tools query verify.plan-structure` reports `valid: true`, 0 errors, 0 warnings.

| Task | Type | Files | Action | Verify | Done | read_first |
|------|------|-------|--------|-------|------|------------|
| 01 | auto | ✅ | ✅ specific | ✅ has `<automated>` | ✅ measurable | ✅ |
| 02 | auto | ✅ | ✅ specific | ✅ has `<automated>` | ✅ measurable | ✅ |

Both tasks have `<read_first>` blocks with specific file paths and line numbers. Actions include concrete commands (`git show 3b12f52^:`, `mkdir -p`, `python3 -c`) and detailed test method specifications. Done criteria are measurable (file exists, test passes, exit code 0).

### Dimension 3: Dependency Correctness — PASS

- `depends_on: []` → Wave 1 (correct for single plan)
- `wave: 1` consistent with `depends_on`
- Single plan, no cycles possible
- No forward references

### Dimension 4: Key Links Planned — WARNING

**Issue W1:** `must_haves` in frontmatter is a flat list of 8 strings (truths only). The agent definition expects structured format with `truths`, `artifacts`, and `key_links` keys. Artifacts are documented in the separate "Artifacts this phase produces" section (which is good), but not in the frontmatter structure. Key_links are not applicable for a verification-only phase (no component wiring needed), so this is a minor structural deviation, not a coverage gap.

### Dimension 5: Scope Sanity — PASS

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Tasks/plan | 2 | 2-3 target | ✅ |
| Files/plan | 2 | 5-8 target | ✅ |
| Complexity | Low (file restore + test creation) | — | ✅ |

### Dimension 6: Verification Derivation — PASS

must_haves truths are user-observable and testable:
- "All 26 V2 gates pass green (exit 0)" — operator-observable ✅
- "ChannelAdapter Protocol has exactly 6 methods" — testable via runtime introspection ✅
- "qqbot_channel_enabled feature flag defaults to False" — testable via assertIs ✅
- "dependencies = [] invariant holds" — testable via file content check ✅

No implementation-focused truths detected. All truths map to concrete test methods in Task 02.

### Dimension 7: Context Compliance — PASS

CONTEXT.md exists but discuss was skipped (`workflow.skip_discuss`). All choices at Claude's discretion. No locked decisions to contradict. No deferred ideas to exclude. Plan operates entirely within discretion area.

### Dimension 7b: Scope Reduction Detection — PASS

No scope reduction language detected in task actions. No "v1", "simplified", "static for now", "placeholder" (except in reference to the template's placeholder data, which is the correct content), "future enhancement", or "skip for now" language. Plan delivers exactly what ADAPTER-04 requires.

### Dimension 7c: Architectural Tier Compliance — PASS

RESEARCH.md has Architectural Responsibility Map. Tasks place work in correct tiers:
- Template restoration → `.planning/` data file tier ✅
- Consolidated test → `packages/channels/qqbot/tests/` test tier ✅
- Gate execution → `scripts/run_v2_gates.py` entry point ✅

No tier mismatches. No security-sensitive capabilities assigned to wrong tiers.

### Dimension 8: Nyquist Compliance — PASS (with 3 warnings on VALIDATION.md)

**Check 8e — VALIDATION.md Existence:** ✅ PASS (file exists)

**Check 8a — Automated Verify Presence:** ✅ Both tasks have `<automated>` commands with `set -o pipefail &&`.

**Check 8b — Feedback Latency:** ✅ No watch-mode flags. No E2E suite (playwright/cypress). `run_v2_gates.py` estimated ~60s which is at the threshold but appropriate for a full safety baseline verification phase. No exit code masking (B2 fixed).

**Check 8c — Sampling Continuity:** 2 tasks, both have automated verify. ✅ 2/2 verified.

**Check 8d — Wave 0 Completeness:** No MISSING references. ✅

**Issue W2 (WARNING):** VALIDATION.md frontmatter has `nyquist_compliant: false` and `wave_0_complete: false`. Validation Sign-Off section has all checkboxes unchecked and approval is "pending". The plan tasks themselves have automated verify, but the validation strategy document has not been finalized.

**Issue W3 (WARNING):** VALIDATION.md Per-Task Verification Map lists 4 task IDs (58-01-01 through 58-01-04) but the plan has only 2 tasks. The task decomposition in VALIDATION.md does not correspond to the actual plan tasks.

**Issue W4 (WARNING):** VALIDATION.md Per-Task Verification Map references incorrect file paths:
- `services/qqbot-channel/tests/test_no_wecom_import.py` → actual: `packages/channels/qqbot/tests/test_no_wecom_import.py`
- `tests/test_contract_count_freeze.py` → actual: `packages/contract-test-suite/tests/test_contract_count_freeze.py`
- `tests/test_feature_flags_default.py` → file does not exist at this path

The plan itself uses correct paths; only VALIDATION.md is inconsistent.

### Dimension 9: Cross-Plan Data Contracts — N/A

Single plan, no cross-plan data flows.

### Dimension 10: CLAUDE.md Compliance — PASS (via AGENTS.md)

No `CLAUDE.md` exists; `AGENTS.md` is the project instruction file.

AGENTS.md directives checked:
- "Add tests before or with behavior changes" — Task 02 creates tests ✅
- "Keep changes scoped to the active GSD phase" — only 2 files modified, both phase-relevant ✅
- "Do not introduce a new service, database, queue, or runtime dependency" — `dependencies = []` invariant is explicitly preserved ✅
- "Never commit secrets" — template contains only placeholder/sanitized data ✅
- "Prefer structured parsers and schema validators over ad hoc string parsing" — tests use `json.load`, `dir()` introspection, AST scanning ✅

### Dimension 11: Research Resolution — PASS ✅ (B1 fixed)

RESEARCH.md `## Open Questions (RESOLVED)` section at line 357. Both questions have inline `RESOLVED:` markers documenting the plan's chosen resolution. Dimension 11 PASSES.

### Dimension 12: Pattern Compliance — PASS

PATTERNS.md exists with File Classification table (2/2 analogs found).

| File | Analog Referenced in Plan | Status |
|------|--------------------------|--------|
| `08-TRIAL-EVIDENCE-TEMPLATE.json` | Restoration command + full content in PATTERNS.md Pattern Assignments | ✅ |
| `test_v1_8_safety_baseline.py` | `test_contract_freeze_not_violated.py` analog referenced in read_first + action | ✅ |

Shared patterns all referenced:
- Runtime introspection (`dir()` for Protocol methods) ✅
- Feature flag `assertIs(..., False)` assertion ✅
- unittest TestCase structure ✅
- Path resolution convention (`Path(__file__).resolve().parents[N]`) ✅
- AST-based import isolation (noted as already covered, not duplicated) ✅
- SHA-256 baseline (noted as already covered, not duplicated) ✅

---

## Structural Compliance Check

| Requirement | Status |
|-------------|--------|
| Frontmatter: `wave` | ✅ `wave: 1` |
| Frontmatter: `depends_on` | ✅ `depends_on: []` |
| Frontmatter: `files_modified` | ✅ 2 files listed |
| Frontmatter: `autonomous` | ✅ `autonomous: true` |
| Frontmatter: `requirements` | ✅ `ADAPTER-04` present |
| Frontmatter: `must_haves` | ⚠️ Flat list, not structured (W1) |
| Task XML: `<read_first>` | ✅ Both tasks have read_first with specific files/lines |
| Task XML: `<acceptance_criteria>` (`<done>`) | ✅ Both tasks have measurable done criteria |
| Verification criteria | ✅ Both tasks have `<verify><automated>` with `set -o pipefail &&` |
| "Artifacts this phase produces" section | ✅ Present with 4 artifacts listed |
| Requirement coverage (ADAPTER-04) | ✅ Appears in frontmatter + task names + must_haves |
| Threat model block | ✅ `<threat_model>` with trust boundaries + STRIDE register (6 threats) |
| Anti-shallow execution | ✅ Actions specify exact commands, file paths, line numbers, expected behavior |
| Multi-source coverage | ✅ RESEARCH.md, PATTERNS.md, VALIDATION.md all referenced in read_first |

---

## Threat Model Review

The threat model is well-constructed:
- 3 trust boundaries identified (git→working tree, test→contract surface, operator→gate suite)
- 6 STRIDE threats catalogued (T-58-01 through T-58-05 + T-58-SC)
- All tampering threats on frozen surfaces have mitigation plans
- T-58-04 (cross-channel import) correctly accepted — already mitigated by existing test
- T-58-SC (pip/npm installs) correctly accepted — phase is verification-only

No issues with threat model.

---

## Structured Issues

```yaml
issues:
  - id: W1
    dimension: key_links_planned
    severity: WARNING
    description: "must_haves is a flat list of strings rather than structured truths/artifacts/key_links format. Artifacts documented separately in 'Artifacts this phase produces' section."
    plan: "58-01"
    fix_hint: "Optional: restructure must_haves into truths/artifacts/key_links keys. Not blocking since content is complete."

  - id: W2
    dimension: nyquist_compliance
    severity: WARNING
    description: "VALIDATION.md frontmatter has nyquist_compliant: false and wave_0_complete: false. Validation Sign-Off is pending with unchecked boxes."
    plan: "58-01"
    file: "58-VALIDATION.md"
    fix_hint: "After confirming all validation criteria are met, set nyquist_compliant: true and check the sign-off boxes"

  - id: W3
    dimension: nyquist_compliance
    severity: WARNING
    description: "VALIDATION.md Per-Task Verification Map lists 4 task IDs (58-01-01 through 58-01-04) but plan has only 2 tasks. Task decomposition mismatch."
    plan: "58-01"
    file: "58-VALIDATION.md"
    fix_hint: "Update Per-Task Verification Map to match the actual 2-task plan structure (58-01-T1, 58-01-T2)"

  - id: W4
    dimension: nyquist_compliance
    severity: WARNING
    description: "VALIDATION.md references non-existent file paths: services/qqbot-channel/tests/test_no_wecom_import.py, tests/test_contract_count_freeze.py, tests/test_feature_flags_default.py"
    plan: "58-01"
    file: "58-VALIDATION.md"
    fix_hint: "Correct paths to: packages/channels/qqbot/tests/test_no_wecom_import.py, packages/contract-test-suite/tests/test_contract_count_freeze.py, packages/platform-runtime/tests/test_feature_flags.py"
```

---

## Coverage Summary

| Requirement | Plans | Status |
|-------------|-------|--------|
| ADAPTER-04 | 01 | Covered (Task 01 fixes gate regression, Task 02 verifies all 5 SCs) |

## Plan Summary

| Plan | Tasks | Files | Wave | Status |
|------|-------|-------|------|--------|
| 58-01 | 2 | 2 | 1 | Valid — ready for execution |

---

## Recommendation

**0 blocker(s) — plan is ready for execution.**

Both blockers from iteration 1 have been properly fixed:
1. **B1 (Research Resolution):** RESEARCH.md Open Questions section now has `(RESOLVED)` suffix and inline `RESOLVED:` markers on both questions. ✅
2. **B2 (Verify Exit Code Masking):** Both tasks' `<automated>` verify commands now use `set -o pipefail &&` with no `| tail -N` piping. Exit codes properly propagate. ✅

4 warning(s) remain but do not block execution:
- W1: must_haves flat-list structure (optional, content is complete)
- W2-W4: VALIDATION.md inconsistencies (stale task map, incorrect paths, pending sign-off) — these are documentation issues in VALIDATION.md only; the plan itself uses correct paths and structure.

**Phase 58 is a safety verification phase — the verify commands now reliably detect failures. The plan is approved for execution.**
