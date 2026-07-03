---
phase: 35-v2-acceptance-readiness-report-traceability-update
reviewed: 2026-07-03T09:43:23Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/generate_v2_readiness_report.py
  - scripts/run_v2_gates.py
  - packages/contract-test-suite/tests/test_v2_readiness_report.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 35: Code Review Report

**Reviewed:** 2026-07-03T09:43:23Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the three source files changed during Phase 35: the new V2 readiness
report generator (571 lines, stdlib-only), the modified V2 gate runner (added
generator to compileall gate), and the new test suite (187 lines, 14 tests).

The code is well-structured, stdlib-only, and produces deterministic output
(verified: two runs produce byte-identical MD5). The two-tier status model
("Autonomous Code Closure: READY" vs "V2 Acceptance: BLOCKED ON HUMAN GATES")
is correctly implemented and never conflated. TRIAL-01 remains unchecked `[ ]`
in PROJECT.md. All 9 V2 gates pass green (465 tests).

No Critical issues found. Two Warnings identified — one latent logic bug in
the output boundary coverage fraction (only manifests if categories are
missing) and one cross-platform determinism concern in `write_text`. Five
Info-level items for maintainability and robustness improvements.

## Warnings

### WR-01: Output boundary coverage fraction is tautological (N/N)

**File:** `scripts/generate_v2_readiness_report.py:162`
**Issue:** The executive summary computes the output boundary coverage as
`{ob_count}/{ob_count}` where `ob_count = len(ob_evidence.get("entries", []))`.
Both numerator and denominator are the same value, making the fraction always
N/N regardless of whether categories are missing. When
`all_categories_covered` is False, the report would show e.g. "3/3 categories
covered (gaps remain)" — a contradictory statement. The JSON sidecar has a
`missing_categories` field that should be included in the denominator.

Currently `all_categories_covered` is True and `missing_categories` is empty,
so the bug does not manifest. But it is a latent logic error that would
produce contradictory output if the data changes.

**Fix:**
```python
# In _section_executive_summary, replace:
ob_count = len(ob_evidence.get("entries", []))
# ...later in the f-string:
# {ob_count}/{ob_count}

# With:
ob_count = len(ob_evidence.get("entries", []))
ob_missing = len(ob_evidence.get("missing_categories", []))
ob_total = ob_count + ob_missing
# ...in the f-string:
# {ob_count}/{ob_total}
```

### WR-02: write_text lacks explicit newline parameter (cross-platform determinism risk)

**File:** `scripts/generate_v2_readiness_report.py:509`
**Issue:** `report_path.write_text(report_text, encoding="utf-8")` uses the
default `newline=None`, which translates `\n` to `os.linesep` on Windows
(`\r\n`). The module docstring (line 14) explicitly promises "byte-identical
output across runs" — a key project constraint. On Linux this is a no-op
(`os.linesep == "\n"`), but on Windows the output would differ, breaking the
determinism guarantee. The `--check` flag validates the existing file, so a
Windows-generated file with `\r\n` would still pass `--check` but would not
be byte-identical to a Linux-generated file.

**Fix:**
```python
# In write_report, replace:
report_path.write_text(report_text, encoding="utf-8")
# With:
report_path.write_text(report_text, encoding="utf-8", newline="\n")
```

## Info

### IN-01: Hardcoded test and fixture counts in report sections

**File:** `scripts/generate_v2_readiness_report.py:160,355-356`
**Issue:** The executive summary hardcodes "465 tests across 9 V2 gates" and
the Phase 5 section hardcodes "71 tests pass" and "15 implementation files,
10 test modules, 5 fixtures, 2 schemas". These numbers will become stale as
the codebase evolves. Since the report is regenerated deterministically,
these could be computed from sidecars or gate output. However, computing
test counts dynamically would require running the gates, conflicting with
the fast-generation design. Acceptable as point-in-time snapshots, but
should be documented as such.
**Fix:** Add a comment noting these are point-in-time snapshots from Phase 35,
or compute from sidecars where feasible.

### IN-02: Leading space in docstring

**File:** `scripts/generate_v2_readiness_report.py:184`
**Issue:** The docstring `""" mirrors PRD §10.1..."""` has a stray leading
space after the triple quotes. Minor style inconsistency — all other
docstrings in the file start without a leading space.
**Fix:** Remove the leading space: `"""Mirrors PRD §10.1..."""`.

### IN-03: No error handling for missing JSON sidecar files

**File:** `scripts/generate_v2_readiness_report.py:90-93`
**Issue:** `_load_json` will raise a raw `FileNotFoundError` traceback if a
sidecar file does not exist. For a CLI tool, a friendlier error message
indicating which sidecar is missing and how to generate it would improve the
developer experience.
**Fix:** Wrap the `open()` call in a try/except and print a clear error
message to stderr before exiting.

### IN-04: sys.modules mutation in test module loader

**File:** `packages/contract-test-suite/tests/test_v2_readiness_report.py:37`
**Issue:** `_load_report_module` sets `sys.modules["generate_v2_readiness_report"] = module`,
mutating global state. If another test module loads a module with the same
name, it could receive the cached version. Low risk given the specific name,
but could cause subtle ordering-dependent test failures in large suites.
**Fix:** Acceptable for now. If issues arise, use a unique module name or
clean up in `tearDownClass`.

### IN-05: Split-based section extraction in tests raises unhelpful IndexError

**File:** `packages/contract-test-suite/tests/test_v2_readiness_report.py:102,114,182`
**Issue:** Tests extract report sections using `text.split("## Section")[1].split("## Next")[0]`.
If a section header is missing or renamed, this raises `IndexError` with no
context about which section was missing. Using `str.partition()` with an
explicit assertion would produce a clearer failure message.
**Fix:** Replace `split(...)[1]` patterns with `partition()` + assertion, e.g.:
```python
_, exec_section, rest = self.report_text.partition("## Executive Summary")
self.assertTrue(exec_section, "Report missing '## Executive Summary' header")
```

---

_Reviewed: 2026-07-03T09:43:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
