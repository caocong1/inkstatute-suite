# Phase 34: V2 Code Gap Closure - Plan

**Planned:** 2026-07-03
**Phase:** 34
**Milestone:** v1.5 V2 Acceptance Closure
**Requirements:** GAP-01, GAP-02, GAP-03, GAP-04, GAP-05, GAP-06, GAP-07, GAP-08, GAP-09
**Depends on:** Phase 33 (V2 Requirement Audit & Traceability Infrastructure)

## Goal

Every genuine code gap identified by the Phase 33 audit is closed in-place with tests, and all existing V2 gate suites pass green with no regressions.

## Approach

The Phase 33 audit found 9 satisfied, 0 partial, 0 gap, and 1 human_gate. Spot-check verification (RQ-1) confirmed all evidence paths exist on disk — the audit results are correct. Therefore GAP-01 through GAP-06 have no genuine code gaps to close; the deliverable for those requirements is verification documentation.

The real work is in the differentiator deliverables:
- **GAP-08**: Build a composability fixture coverage report mapping all 7 §10.3 synthetic task types to fixtures (all 7 already covered — report is the deliverable).
- **GAP-09**: Close a fixture gap found during spot-check (output boundary fixture missing explicit "update" and "meta" category cases per §10.2), then build a privacy/output-boundary fixture evidence summary proving all 4 categories (gateway/update/command/meta) are blocked or rewritten.
- **GAP-07**: Run full gate-suite regression check after all changes.

All work is in-place edits to existing packages (contract-test-suite evidence producers, fixtures) and a new stdlib-only report generator script. No new services, no new dependencies.

## Architecture

```
packages/contract-test-suite/src/contract_test_suite/
  coverage_report.py        (MODIFIED — add composability coverage report)
    └── SYNTHETIC_TASK_TYPES: tuple of 7 task type specs
    └── ComposabilityCoverageEntry: dataclass (task_type, covered, fixtures, evidence)
    └── ComposabilityCoverageReport: dataclass (entries, covered_count, missing_count)
    └── build_composability_coverage_report(): maps §10.3 task types to fixtures

  boundary_checks.py        (MODIFIED — add output boundary evidence summary)
    └── OUTPUT_BOUNDARY_CATEGORIES: tuple of 4 category specs (gateway/update/command/meta)
    └── OutputBoundaryEvidenceEntry: dataclass (category, action, fixture_case, proof)
    └── OutputBoundaryEvidenceReport: dataclass (entries, all_categories_covered)
    └── build_output_boundary_evidence_summary(): scans fixture + proves block/rewrite

packages/contract-test-suite/fixtures/
  phase55_output_policy_cases.json  (MODIFIED — add update + meta cases)

scripts/
  generate_gap_evidence_reports.py  (NEW — ~200 lines, stdlib-only)
    ├── Calls build_composability_coverage_report() → writes acceptance/v2-composability-coverage.json
    ├── Calls build_output_boundary_evidence_summary() → writes acceptance/v2-output-boundary-evidence.json
    ├── --check flag: exits non-zero if any task type uncovered or any category missing
    └── Deterministic output (sorted keys, no timestamps)

  run_v2_gates.py             (MODIFIED — add generate_gap_evidence_reports.py to compileall)

acceptance/
  v2-composability-coverage.json    (NEW — generated, committed)
  v2-output-boundary-evidence.json  (NEW — generated, committed)

packages/contract-test-suite/tests/
  test_gap_evidence_reports.py      (NEW — tests for both report functions)
```

## Tasks

### Task 1: Spot-check audit evidence bundles (GAP-01 through GAP-06)

**Files:** None (verification only)

**What:**
The Phase 33 audit classified all 9 code requirements as `satisfied`. This task verifies that classification is correct by confirming every evidence path in `acceptance/v2-traceability.json` exists on disk.

Verification completed during research (RQ-1):
- Ran `python scripts/audit_v2_requirements.py` for all 10 requirements
- Programmatically verified all implementation files, test modules, and fixtures exist
- Result: 0 missing files across all 10 requirements

| GAP Req | Audit Req | Status | Evidence Verified |
|---------|-----------|--------|-------------------|
| GAP-01 | WECOM-01 | satisfied | 15 impl, 10 tests, 5 fixtures — all exist |
| GAP-02 | OUTPUT-01 | satisfied | 15 impl, 1 test, 1 fixture — all exist |
| GAP-03 | FEEDBACK-01 | satisfied | 4 impl, 3 tests, 3 fixtures — all exist |
| GAP-04 | READVIEW-01 | satisfied | 4 impl, 2 tests, 1 fixture — all exist |
| GAP-05 | COMPOSE-01 | satisfied | 8 impl, 3 tests, 6 fixtures — all exist |
| GAP-06 | OBSERVE-01 | satisfied | 15 impl, 3 tests, 3 fixtures — all exist |

**No code changes needed.** The spot-check confirms the audit found no genuine code gaps for GAP-01 through GAP-06.

**Tests:** N/A — verification is documented in RESEARCH.md and VERIFICATION.md.

### Task 2: Close output boundary fixture gap (GAP-09 partial)

**Files:**
- `packages/contract-test-suite/fixtures/phase55_output_policy_cases.json` (MODIFIED)

**What:**
The spot-check (RQ-4) found that `phase55_output_policy_cases.json` only has 3 cases covering gateway (rewrite) and command (block). §10.2 requires fixture evidence for all 4 categories: gateway, update, command, meta.

Add two new cases to the fixture:

```json
{
  "id": "block-self-update-notice",
  "input": "Self-update available: run /update now to get the latest version",
  "expected_action": "block"
},
{
  "id": "block-meta-tool-progress",
  "input": "tool progress: memory sync complete, insights generated for this session",
  "expected_action": "block"
}
```

After this change, the fixture has 5 cases covering all 4 §10.2 categories:
- gateway → rewrite (rewrite-gateway-lifecycle)
- update → block (block-self-update-notice)
- command → block (block-command-debug-stack)
- meta → block (block-meta-tool-progress)
- allow → allow (allow-legal-answer, legal business output)

**Test-first:** The existing test `test_output_policy_cases_cover_allow_rewrite_and_block` in `test_phase55_wecom_service_loop.py` iterates all cases and checks `expected_action`. The new cases use `block` which is already in the expected actions set. The test will pass without modification. However, add a new test asserting all 4 categories are covered (see Task 5).

**Tests:**
- Existing `test_output_policy_cases_cover_allow_rewrite_and_block` continues to pass (new cases use `block`)
- New test in Task 5 verifies all 4 categories have dedicated fixture cases

### Task 3: Build composability fixture coverage report (GAP-08)

**Files:**
- `packages/contract-test-suite/src/contract_test_suite/coverage_report.py` (MODIFIED)
- `packages/contract-test-suite/tests/test_gap_evidence_reports.py` (NEW — shared with Task 4)

**What:**
Add a composability fixture coverage report that maps V2-PRD §10.3's 7 synthetic task types to fixture files and reports which are covered and which are missing.

New types and function in `coverage_report.py`:

```python
@dataclass(frozen=True)
class ComposabilityCoverageEntry:
    task_type: str          # e.g. "simple_legal_qa"
    prd_label: str          # e.g. "简单法律问答（短任务）"
    covered: bool
    fixtures: tuple[str, ...]
    evidence: str           # human-readable evidence description

@dataclass(frozen=True)
class ComposabilityCoverageReport:
    entries: tuple[ComposabilityCoverageEntry, ...]
    covered_count: int
    missing_count: int
    all_covered: bool

    def to_dict(self) -> dict[str, Any]: ...

SYNTHETIC_TASK_TYPES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (task_type, prd_label, fixture_paths)
    ("simple_legal_qa", "简单法律问答（短任务）", (
        "packages/contract-test-suite/fixtures/phase4_simple_qa_event_stream.jsonl",
        "packages/contract-test-suite/fixtures/phase3_non_legal_wild_task_contract_fixture.json",
    )),
    ("contract_review", "合同审查（长任务 + skill + gate + Artifact）", (
        "packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl",
        "packages/platform-contract/fixtures/legal_wecom_contract_review.json",
    )),
    ("legal_retrieval", "法律检索（MCP tool trace）", (
        "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
    )),
    ("route_error", "路由错误模拟（route_mismatch）", (
        "packages/contract-test-suite/fixtures/phase3_route_error_contract_fixture.json",
        "packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl",
        "packages/contract-test-suite/fixtures/phase6_read_feedback_bundle.json",
    )),
    ("wecom_feedback", "WeCom 反馈（模板卡片 → FeedbackEvent）", (
        "packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json",
        "packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json",
    )),
    ("long_task_failure", "长任务失败（AsyncTask.status=failed）", (
        "packages/contract-test-suite/fixtures/phase3_long_task_failure_contract_fixture.json",
        "packages/contract-test-suite/fixtures/phase4_failed_long_task_event_stream.jsonl",
    )),
    ("non_legal_synthetic", "非法律合成任务（财税、工程、教育）", (
        "packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json",
        "packages/contract-test-suite/fixtures/non_legal_education_task.json",
        "packages/platform-contract/fixtures/non_legal_engineering_task.json",
        "packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json",
    )),
)

def build_composability_coverage_report(
    repo_root: str | Path = REPO_ROOT,
) -> ComposabilityCoverageReport:
    """Map §10.3 synthetic task types to fixtures and report coverage."""
    ...
```

The function checks that each fixture path exists and is non-empty. A task type is `covered=True` if at least one fixture file exists. The `evidence` field describes what in the fixture proves the task type (e.g., "route_decision.mode=simple_qa").

**Tests:**
- `test_composability_coverage_all_7_task_types`: report has 7 entries
- `test_composability_coverage_all_covered`: `all_covered=True`, `missing_count=0`
- `test_composability_coverage_fixtures_exist`: every listed fixture path exists
- `test_composability_coverage_non_legal_has_3_domains`: non_legal_synthetic entry lists finance_tax, engineering, education fixtures

### Task 4: Build output boundary evidence summary (GAP-09)

**Files:**
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` (MODIFIED)
- `packages/contract-test-suite/tests/test_gap_evidence_reports.py` (NEW — shared with Task 3)

**What:**
Add an output boundary evidence summary that scans `phase55_output_policy_cases.json` and proves all 4 §10.2 categories (gateway/update/command/meta) are blocked or rewritten.

New types and function in `boundary_checks.py`:

```python
@dataclass(frozen=True)
class OutputBoundaryEvidenceEntry:
    category: str           # "gateway" | "update" | "command" | "meta"
    action: str             # "block" | "rewrite"
    fixture_case_id: str    # e.g. "rewrite-gateway-lifecycle"
    proof: str              # human-readable proof description

@dataclass(frozen=True)
class OutputBoundaryEvidenceReport:
    entries: tuple[OutputBoundaryEvidenceEntry, ...]
    all_categories_covered: bool
    missing_categories: tuple[str, ...]
    no_visible_backend_terms: bool   # no gateway/hermes/help/token in visible_text

    def to_dict(self) -> dict[str, Any]: ...

OUTPUT_BOUNDARY_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (category, keyword_patterns that identify this category in fixture input)
    ("gateway", ("gateway",)),
    ("update", ("update", "self-update", "/update")),
    ("command", ("/help", "/status", "/credits", "command", "dangerous command")),
    ("meta", ("admin_notice", "tool progress", "memory sync", "insights", "debug", "stack trace")),
)

def build_output_boundary_evidence_summary(
    fixture_path: str | Path | None = None,
    repo_root: str | Path = REPO_ROOT,
) -> OutputBoundaryEvidenceReport:
    """Scan output policy fixture and prove all 4 §10.2 categories are blocked/rewritten."""
    ...
```

The function:
1. Loads `phase55_output_policy_cases.json` (or the provided path)
2. For each case, classifies it into one or more categories based on keyword patterns
3. For each category, finds at least one case with `expected_action` in {block, rewrite}
4. Verifies no `visible_text` in block/rewrite cases contains backend terms (gateway, hermes, /help, token, stack trace)
5. Reports `all_categories_covered=True` only when all 4 categories have block/rewrite evidence

**Tests:**
- `test_output_boundary_all_4_categories_covered`: report has entries for gateway, update, command, meta
- `test_output_boundary_all_categories_block_or_rewrite`: every entry action is block or rewrite
- `test_output_boundary_no_visible_backend_terms`: no backend terms in visible_text
- `test_output_boundary_missing_category_detected`: if a category is removed, `all_categories_covered=False`

### Task 5: Write tests for gap evidence reports (GAP-08, GAP-09)

**Files:**
- `packages/contract-test-suite/tests/test_gap_evidence_reports.py` (NEW)

**What:**
Comprehensive test suite for both report functions:

1. `test_composability_coverage_all_7_task_types` — report has 7 entries
2. `test_composability_coverage_all_covered` — `all_covered=True`, `missing_count=0`
3. `test_composability_coverage_fixtures_exist` — every listed fixture path exists on disk
4. `test_composability_coverage_non_legal_has_3_domains` — non_legal entry lists finance_tax, engineering, education fixtures
5. `test_composability_coverage_report_serializes_to_json` — `to_dict()` produces valid JSON
6. `test_output_boundary_all_4_categories_covered` — gateway, update, command, meta all present
7. `test_output_boundary_all_categories_block_or_rewrite` — every entry action is block or rewrite
8. `test_output_boundary_no_visible_backend_terms` — no backend terms in visible text
9. `test_output_boundary_missing_category_detected` — removing a category case → `all_categories_covered=False`
10. `test_output_boundary_report_serializes_to_json` — `to_dict()` produces valid JSON
11. `test_output_boundary_fixture_has_5_cases` — fixture has exactly 5 cases after gap closure
12. `test_output_boundary_fixture_covers_all_4_categories` — fixture cases map to all 4 categories

**Test placement:** `packages/contract-test-suite/tests/` — discovered by the existing `contract-test-suite` gate.

**Tests:** Self-testing — the test file IS the deliverable.

### Task 6: Create gap evidence report generator script (GAP-08, GAP-09)

**Files:**
- `scripts/generate_gap_evidence_reports.py` (NEW — ~200 lines, stdlib-only)
- `scripts/run_v2_gates.py` (MODIFIED — add script to compileall path list)

**What:**
A stdlib-only script that calls the evidence producer functions and writes two deterministic JSON sidecars:

```python
# scripts/generate_gap_evidence_reports.py
import argparse, json, sys
from pathlib import Path

# PYTHONPATH setup: contract-test-suite/src must be importable
# The gate runner sets PYTHONPATH; for standalone runs, use sys.path.insert

def main(argv=None):
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--check", action="store_true", help="Exit non-zero if coverage incomplete")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    # Add contract-test-suite src to path
    sys.path.insert(0, str(repo_root / "packages" / "contract-test-suite" / "src"))
    sys.path.insert(0, str(repo_root / "packages" / "platform-contract" / "src"))

    from contract_test_suite.coverage_report import build_composability_coverage_report
    from contract_test_suite.boundary_checks import build_output_boundary_evidence_summary

    # Generate composability coverage
    comp_report = build_composability_coverage_report(repo_root)
    comp_path = repo_root / "acceptance" / "v2-composability-coverage.json"
    comp_path.write_text(json.dumps(comp_report.to_dict(), indent=2, sort_keys=True))

    # Generate output boundary evidence
    ob_report = build_output_boundary_evidence_summary(repo_root=repo_root)
    ob_path = repo_root / "acceptance" / "v2-output-boundary-evidence.json"
    ob_path.write_text(json.dumps(ob_report.to_dict(), indent=2, sort_keys=True))

    print(f"Wrote {comp_path}")
    print(f"Wrote {ob_path}")
    print(f"Composability: {comp_report.covered_count}/{len(comp_report.entries)} task types covered")
    print(f"Output boundary: {'all' if ob_report.all_categories_covered else 'PARTIAL'} categories covered")

    if args.check:
        if not comp_report.all_covered or not ob_report.all_categories_covered:
            print("FAIL: coverage incomplete", file=sys.stderr)
            return 1
    return 0
```

**Determinism:** JSON output uses `sort_keys=True`, no timestamps, sorted lists. Same codebase → same output byte-for-byte.

**run_v2_gates.py modification:** Add `scripts/generate_gap_evidence_reports.py` to the `compileall` gate's path list (same as `scripts/audit_v2_requirements.py`).

**Tests:**
- The script is tested implicitly via the evidence producer function tests (Task 5)
- Determinism verified by running twice and diffing output

### Task 7: Generate and commit evidence sidecars (GAP-08, GAP-09)

**Files:**
- `acceptance/v2-composability-coverage.json` (NEW — generated)
- `acceptance/v2-output-boundary-evidence.json` (NEW — generated)

**What:**
1. Run `python scripts/generate_gap_evidence_reports.py`
2. Verify both JSON files are created in `acceptance/`
3. Verify composability report shows 7/7 task types covered
4. Verify output boundary report shows all 4 categories covered
5. Verify determinism — two runs produce byte-identical output
6. Commit the generated files (deterministic and reproducible)

**Tests:**
- Verification by running the generator twice and diffing output

### Task 8: Full gate-suite regression check (GAP-07)

**Files:** None (verification only)

**What:**
Run `python scripts/run_v2_gates.py` after all changes and verify all 9 gates pass green with no regressions.

Baseline (pre-change): all 9 gates pass.
Post-change: all 9 gates must still pass.

Expected gate results:
```
==> platform-contract          OK   (unchanged)
==> wecom-service              OK   (unchanged — output_policy.py not modified)
==> hermes-contract-layer      OK   (unchanged)
==> conversation-read-view     OK   (unchanged)
==> feedback-service           OK   (unchanged)
==> phase7-privacy-boundary    OK   (unchanged)
==> contract-test-suite        OK   (new tests added in test_gap_evidence_reports.py)
==> v2-acceptance-traceability OK   (unchanged — audit script not modified)
==> compileall                 OK   (generate_gap_evidence_reports.py added to path list)
```

**Tests:** N/A — the gate suite IS the test.

## Requirement Coverage

| REQ-ID | Task(s) | How Verified |
|--------|---------|-------------|
| GAP-01 | Task 1 | Spot-check confirms WECOM-01 satisfied — 15 impl, 10 tests, 5 fixtures all exist |
| GAP-02 | Task 1 | Spot-check confirms OUTPUT-01 satisfied — 15 impl, 1 test, 1 fixture all exist |
| GAP-03 | Task 1 | Spot-check confirms FEEDBACK-01 satisfied — 4 impl, 3 tests, 3 fixtures all exist |
| GAP-04 | Task 1 | Spot-check confirms READVIEW-01 satisfied — 4 impl, 2 tests, 1 fixture all exist |
| GAP-05 | Task 1 | Spot-check confirms COMPOSE-01 satisfied — 8 impl, 3 tests, 6 fixtures all exist |
| GAP-06 | Task 1 | Spot-check confirms OBSERVE-01 satisfied — 15 impl, 3 tests, 3 fixtures all exist |
| GAP-07 | Task 8 | All 9 V2 gates pass green post-change with no regressions |
| GAP-08 | Task 3, 6, 7 | Composability coverage report shows 7/7 §10.3 task types covered by fixtures |
| GAP-09 | Task 2, 4, 6, 7 | Output boundary fixture gap closed (update + meta cases added) + evidence summary proves all 4 categories blocked/rewritten |

## Risks

1. **Risk: Adding fixture cases may break existing test assertions** — `test_output_policy_cases_cover_allow_rewrite_and_block` checks `actions == {"allow", "rewrite", "block"}`. New cases use `block` which is already in the set. **Mitigation:** The test iterates all cases and checks `expected_action` per case; new block cases are compatible.

2. **Risk: Report generator script may fail if PYTHONPATH not set** — the script imports from `contract_test_suite` which requires `packages/contract-test-suite/src` on PYTHONPATH. **Mitigation:** The script uses `sys.path.insert(0, ...)` for standalone runs; the gate runner sets PYTHONPATH for the contract-test-suite gate which discovers the tests.

3. **Risk: Determinism may break if fixture listing order varies** — `Path.iterdir()` order is not guaranteed. **Mitigation:** all lists are sorted before JSON serialization; `sort_keys=True` in `json.dumps`.

4. **Risk: §10.3 task type mapping may be subjective** — the 7 task types are in Chinese in the PRD. **Mitigation:** mapping is reviewed against PRD text; each task type has clear distinguishing features (mode, skill, tool_calls, state) that are verified in fixture content.

## Dependencies

- **None external** — stdlib-only (Python 3.11+: `pathlib`, `json`, `re`, `sys`, `argparse`, `dataclasses`, `typing`)
- **Internal:** `packages/contract-test-suite/src/contract_test_suite/` (modified: `coverage_report.py`, `boundary_checks.py`), `packages/contract-test-suite/fixtures/phase55_output_policy_cases.json` (modified), `scripts/run_v2_gates.py` (modified: compileall path list)

## Definition of Done

- [ ] Spot-check verification confirms all 9 code requirements have valid evidence (GAP-01–06)
- [ ] `phase55_output_policy_cases.json` has 5 cases covering all 4 §10.2 categories (gateway/update/command/meta)
- [ ] `build_composability_coverage_report()` in `coverage_report.py` maps all 7 §10.3 task types to fixtures
- [ ] `build_output_boundary_evidence_summary()` in `boundary_checks.py` proves all 4 categories blocked/rewritten
- [ ] `scripts/generate_gap_evidence_reports.py` generates both JSON sidecars deterministically
- [ ] `acceptance/v2-composability-coverage.json` exists with 7/7 task types covered
- [ ] `acceptance/v2-output-boundary-evidence.json` exists with all 4 categories covered
- [ ] `test_gap_evidence_reports.py` has 12+ test cases, all passing
- [ ] `scripts/run_v2_gates.py` compileall gate includes `generate_gap_evidence_reports.py`
- [ ] All 9 V2 gates pass green with no regressions (GAP-07)
- [ ] No new runtime dependencies introduced (stdlib-only)
- [ ] No new services, databases, or queues introduced

## Verification

**Automated checks:**
1. `python scripts/audit_v2_requirements.py` — still reports 9 satisfied, 0 gap, 1 human_gate
2. `python scripts/generate_gap_evidence_reports.py` — generates both sidecars, exit 0
3. `python scripts/generate_gap_evidence_reports.py --check` — exits 0 (all coverage complete)
4. `python -m unittest discover -s packages/contract-test-suite/tests` — all tests pass including new `test_gap_evidence_reports.py`
5. `python scripts/run_v2_gates.py` — all 9 gates pass green
6. `diff <(python scripts/generate_gap_evidence_reports.py 2>/dev/null && cat acceptance/v2-composability-coverage.json) <(python scripts/generate_gap_evidence_reports.py 2>/dev/null && cat acceptance/v2-composability-coverage.json)` — no diff (deterministic)

**Manual checks:**
- Review `acceptance/v2-composability-coverage.json` — confirm 7 task types map to real fixtures
- Review `acceptance/v2-output-boundary-evidence.json` — confirm all 4 categories have block/rewrite evidence
- Confirm `phase55_output_policy_cases.json` has explicit update and meta cases

## Notes

- GAP-01 through GAP-06 require no code changes — the Phase 33 audit correctly found no genuine code gaps. The spot-check verification (Task 1) is the deliverable for these requirements.
- The output boundary fixture gap (Task 2) is the only genuine code gap found during spot-check. It is a fixture evidence gap, not a production behavior gap — `output_policy.py` already blocks/rewrites all 4 categories correctly.
- The report generator script follows the same stdlib-only, deterministic pattern as `scripts/audit_v2_requirements.py` (Phase 33).
- The `acceptance/` directory gains two new generated JSON files — no runtime infrastructure.
- All changes are in-place edits to existing packages (`contract-test-suite`) and scripts — no new services.
