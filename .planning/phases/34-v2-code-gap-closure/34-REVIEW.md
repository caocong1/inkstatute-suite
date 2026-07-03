---
phase: 34-v2-code-gap-closure
reviewed: 2026-07-03T16:30:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - packages/contract-test-suite/fixtures/phase55_output_policy_cases.json
  - packages/contract-test-suite/src/contract_test_suite/coverage_report.py
  - packages/contract-test-suite/src/contract_test_suite/boundary_checks.py
  - packages/contract-test-suite/tests/test_gap_evidence_reports.py
  - packages/contract-test-suite/tests/test_audit_v2_requirements.py
  - scripts/generate_gap_evidence_reports.py
  - scripts/run_v2_gates.py
  - scripts/audit_v2_requirements.py
  - acceptance/v2-composability-coverage.json
  - acceptance/v2-output-boundary-evidence.json
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 34: Code Review Report

**Reviewed:** 2026-07-03T16:30:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 34 closes the V2 code gap by adding two fixture cases (update + meta categories), a composability coverage report function (GAP-08), an output boundary evidence summary function (GAP-09), a stdlib-only generator script, 17 new tests, and two generated JSON sidecars. Additional changes improve the audit script's robustness (exception handling in probe execution, multi-probe aggregation) and clean up audit tests (backup/restore pattern for sidecar, stdout suppression in gap simulation).

**Verification performed:**
- All 17 new tests pass; all 9 V2 gates pass green (465 total tests, 0 failures).
- Fixture cases verified against production `apply_output_policy()` — all 5 cases produce the expected action (`allow`/`rewrite`/`block`) with correct `visible_text`.
- Generator output is deterministic: two consecutive runs produce byte-identical JSON sidecars.
- `--check` flag exits 0 when coverage is complete.
- No hardcoded secrets, no `eval`/`exec` usage, no injection vectors, no unsafe deserialization.
- All new code is stdlib-only (argparse, json, sys, pathlib, dataclasses, typing, collections.abc, re, ast).

**Key concerns:** The `no_visible_backend_terms` field in the output boundary evidence report is functionally inert — it checks for a `visible_text` field that doesn't exist in the fixture schema. A test contains dead code from iterative development. The `--check` flag writes files before checking, which could fail in read-only CI environments.

## Warnings

### WR-01: Dead code with missing assertion in test_output_boundary_missing_category_detected

**File:** `packages/contract-test-suite/tests/test_gap_evidence_reports.py:127-144`
**Issue:** The first half of the test creates `modified_cases` (removing only `block-meta-tool-progress`), writes it to `modified_path`, calls `build_output_boundary_evidence_summary(fixture_path=modified_path, repo_root=REPO_ROOT)`, and stores the result in `report` — but `report` is never asserted on. Only `report_2` (from a second modified fixture that removes both `block-meta-tool-progress` and `block-command-debug-stack`) is checked. The comments on lines 146-149 are stream-of-consciousness debugging notes ("Actually, block-command-debug-stack matches meta keywords too. Let's remove both meta-specific cases.") that should have been cleaned up before committing. The dead code and missing assertion make the test harder to maintain and could mask a regression if someone modifies the first half expecting it to be verified.
**Fix:** Remove the first modified fixture block (lines 127-144) and the debugging comments (lines 146-149). Keep only the second block that removes both cases and asserts on `report_2`:

```python
def test_output_boundary_missing_category_detected(self) -> None:
    """Removing meta and command cases causes all_categories_covered=False."""
    fixture_path = LOCAL_FIXTURE_ROOT / "phase55_output_policy_cases.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        # Remove both meta-matching cases to ensure meta category is missing.
        # block-command-debug-stack matches both command and meta keywords,
        # so both must be removed to make meta truly uncovered.
        modified_cases = [
            c for c in fixture["cases"]
            if c["id"] not in ("block-meta-tool-progress", "block-command-debug-stack")
        ]
        modified_fixture = {
            "fixture_id": fixture["fixture_id"],
            "cases": modified_cases,
        }
        modified_path = Path(tmpdir) / "modified_cases.json"
        modified_path.write_text(
            json.dumps(modified_fixture, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        report = build_output_boundary_evidence_summary(
            fixture_path=modified_path, repo_root=REPO_ROOT
        )

        self.assertFalse(report.all_categories_covered)
        self.assertIn("meta", report.missing_categories)
        self.assertIn("command", report.missing_categories)
```

### WR-02: no_visible_backend_terms check is functionally inert

**File:** `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py:688-705`
**Issue:** The `no_visible_backend_terms` check iterates all fixture cases looking for a `visible_text` field containing backend terms (`_BACKEND_VISIBLE_TERMS`). However, the fixture schema (`phase55_output_policy_cases.json`) does not include a `visible_text` field — `visible_text` is generated at runtime by the production `apply_output_policy()` function. The check at line 699 (`visible_text = case.get("visible_text")`) will always return `None` for every case, so `no_visible_backend_terms` will always be `True`. The field name implies active verification that backend terms don't leak to user-visible text, but the actual verification happens in `test_phase55_wecom_service_loop.py` which runs the production code. This could give false confidence to future maintainers who see `no_visible_backend_terms: true` in the evidence report and assume it means the production output was verified. The extensive comments (lines 694-698) acknowledge this but the code structure still misleads.
**Fix:** Either (a) rename the field to `fixture_has_no_visible_text_field` to accurately describe what's checked, or (b) add a comment in `to_dict()` output clarifying that this is a fixture-level guard rail, not a production-output verification, or (c) integrate with the production `apply_output_policy()` to actually verify `visible_text` output:

```python
# Option (c): Actually verify production output for block/rewrite cases.
from wecom_service.output_policy import apply_output_policy  # deferred import

no_visible_backend_terms = True
for case in cases:
    if not isinstance(case, Mapping):
        continue
    expected_action = str(case.get("expected_action", ""))
    if expected_action not in ("block", "rewrite"):
        continue
    decision = apply_output_policy(str(case.get("input", "")))
    if decision.visible_text is not None:
        normalized = decision.visible_text.lower()
        for term in _BACKEND_VISIBLE_TERMS:
            if term in normalized:
                no_visible_backend_terms = False
                break
```

Note: Option (c) would add a cross-package dependency from `contract_test_suite` to `wecom_service`, which may conflict with the thin-layer boundary constraints. Option (a) or (b) is safer.

## Info

### IN-01: --check flag writes files before checking

**File:** `scripts/generate_gap_evidence_reports.py:52-66`
**Issue:** The `--check` flag is described as "suitable for CI gates" but the script always writes JSON sidecars (lines 52-66) before running the check logic (lines 80-101). In a read-only CI environment, the write would fail with a permission error even when coverage is complete. Since the output is deterministic and byte-identical to committed files, this won't create spurious diffs in writable environments, but the `--check` path should ideally be read-only.
**Fix:** Consider skipping the write when `--check` is passed, or wrapping the write in a try/except that tolerates permission errors in check mode:

```python
if not args.check:
    comp_path.write_text(...)
    ob_path.write_text(...)
else:
    # In check mode, only write if the content differs (or skip entirely).
    pass
```

---

## Fix Applied (Iteration 1/3)

**Status:** WR-01 and WR-02 fixed. IN-01 deferred (Info severity, not in default fix scope).

### WR-01 Fix: Dead code removed

**File:** `packages/contract-test-suite/tests/test_gap_evidence_reports.py:121-150`
**Change:** Removed the first modified-fixture block (dead code with missing assertion on `report`) and stream-of-consciousness debugging comments. The test now has a single clean block that removes both meta-matching cases (`block-meta-tool-progress` and `block-command-debug-stack`) and asserts on the result. Test passes.

### WR-02 Fix: Clarifying docstring added

**File:** `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py:578-590`
**Change:** Added a class-level docstring to `OutputBoundaryEvidenceReport` explaining that `no_visible_backend_terms` is a fixture-level guard rail, not a production-output verification. Cleaned up redundant inline comments in `build_output_boundary_evidence_summary()`. No output change — generated JSON sidecars are byte-identical to pre-fix versions.

### Post-Fix Verification

- All 17 gap evidence tests pass.
- All 9 V2 gates pass green (465 total tests, 0 failures).
- Generator output is deterministic (byte-identical across runs).
- No new findings introduced by fixes.

---

_Reviewed: 2026-07-03T16:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
