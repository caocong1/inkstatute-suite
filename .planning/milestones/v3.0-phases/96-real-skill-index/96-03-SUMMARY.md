# Plan 96-03 Summary — Dual-Repo Merge + Conflict Model

**Phase:** 96 — Real Skill Index
**Plan:** 96-03 — Dual-repo merge + conflict model — namespace isolation (legal- prefix) + 4-state conflict classification + merge_report generation
**Wave:** 2 (depends on 96-01; runs in parallel with 96-02)
**Requirements:** SKILL-04
**Status:** COMPLETE
**Executed:** 2026-08-09

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 96-03-01 | Create conflict_model.py — namespace isolation + 4-state conflict classification + merge report | 191e483 | PASS |
| 96-03-02 | Create test_conflict_model.py — 19 unit tests | 9a3a674 | PASS |
| 96-03-03 | Create fixtures/previous_index.json — sample previous index | 5871c41 | PASS |
| 96-03-04 | Update __init__.py exports + verify all tests pass | b326334 | PASS |
| (fix) | Remove unused field import from conflict_model.py | a93d59a | PASS |

## Commits

1. `191e483` — feat(96-03): conflict_model.py — namespace isolation + 4-state conflict classification + merge report
2. `9a3a674` — test(96-03): conflict model test suite — 19 tests for namespace isolation + 4-state classification + merge report
3. `5871c41` — test(96-03): add fixtures/previous_index.json — sample previous index for conflict classification tests
4. `b326334` — feat(96-03): export conflict model symbols from __init__.py — build_merge_report, classify_conflicts, MergeReport, ConflictEntry
5. `a93d59a` — fix(96-03): remove unused field import from conflict_model.py + merge 96-02 __init__.py exports

## Files Created

### Source modules
- `packages/skill-index/src/inkstatute_skill_index/conflict_model.py` — Dual-repo merge and 4-state conflict classification (read-only)

### Test suite (19 tests, all pass)
- `packages/skill-index/tests/test_conflict_model.py` — 19 unit tests

### Fixtures
- `packages/skill-index/tests/fixtures/previous_index.json` — Sample previous index with 3 skill entries

### Files Modified
- `packages/skill-index/src/inkstatute_skill_index/__init__.py` — Added conflict model exports (additive, no conflict with 96-02's exports)

## Acceptance Criteria Results

### Task 96-03-01: conflict_model.py
- [x] `from inkstatute_skill_index.conflict_model import compute_content_hash, build_namespace_mappings, classify_conflicts, build_merge_report, MergeReport, ConflictEntry` succeeds
- [x] `compute_content_hash("hello")` returns a 64-character hex string
- [x] `build_namespace_mappings` for legal-skills skills returns `{"court-sms": "legal-court-sms", ...}`
- [x] `build_namespace_mappings` for ai-for-china-legal skills returns `{"contract-review": "commercial-legal:contract-review", ...}`
- [x] `classify_conflicts` with `previous_index=None` classifies all skills as `"local-missing"`
- [x] `classify_conflicts` with a previous index where hashes match → `"in-sync"`
- [x] `classify_conflicts` with a previous index where hash differs and no local modification → `"upstream-changed"`
- [x] `classify_conflicts` with a previous index where hash differs and local modification detected → `"both-changed"`
- [x] `build_merge_report` returns a `MergeReport` with `namespace_mappings`, `conflict_classification` (4 keys), `total_skills`, `summary`
- [x] `MergeReport.conflict_classification` has exactly 4 keys: `"in-sync"`, `"upstream-changed"`, `"both-changed"`, `"local-missing"`
- [x] `_detect_local_modification` returns `False` when no marker files exist (does not create markers)
- [x] No write operations, no `shutil.copytree`, no `git checkout` in the module
- [x] `python -m compileall packages/skill-index/src/inkstatute_skill_index/conflict_model.py` exits 0

### Task 96-03-02: test_conflict_model.py
- [x] `python -m unittest packages.skill-index.tests.test_conflict_model` exits 0
- [x] All 19 test cases pass
- [x] Namespace isolation follows `legal-` prefix for legal-skills, `<plugin>:` for ai-for-china-legal
- [x] 4-state classification matches sync_legal_skills.py semantic (adapted to index level)
- [x] `local-meta-only` is collapsed into `in-sync` (4-state model, not 6-state)
- [x] No write operations in conflict_model.py (read-only)
- [x] `python -m compileall packages/skill-index/tests/test_conflict_model.py` exits 0

### Task 96-03-03: fixtures/previous_index.json
- [x] `packages/skill-index/tests/fixtures/previous_index.json` exists and is valid JSON
- [x] Contains a `skills` array with at least 3 entries (3 entries)
- [x] Each entry has `skill_id`, `content_hash`, `has_local_modification`, `version` fields
- [x] At least one entry has `has_local_modification: true` (legal-de-ai-polish)
- [x] `json.load(open("packages/skill-index/tests/fixtures/previous_index.json"))` succeeds

### Task 96-03-04: __init__.py exports + verification
- [x] `from inkstatute_skill_index import build_merge_report, classify_conflicts, MergeReport, ConflictEntry` succeeds
- [x] `python -m unittest discover -s packages/skill-index/tests` exits 0 (100 tests pass)
- [x] `python -m compileall packages/skill-index/src packages/skill-index/tests` exits 0
- [x] `__all__` includes all conflict model symbols
- [x] No conflict with Plan 96-02's __init__.py exports (additive, different symbols)

## Conflict Model Design

### Namespace Isolation

| Repo | Namespace pattern | Example |
|------|------------------|---------|
| ai-for-china-legal (plugin skill) | `<plugin>:<skill>` | `commercial-legal:contract-review` |
| ai-for-china-legal (shared skill) | `shared:<skill>` | `shared:cn-law-research-gate` |
| legal-skills | `legal-<skill>` | `legal-court-sms` |

The `legal-` prefix quirk from `sync_legal_skills.py`'s `local_dir_name()` is preserved: if a legal-skills skill name already starts with `legal-`, the namespace ID doubles the prefix (e.g., `legal-qa-extractor` → `legal-legal-qa-extractor`). This is documented as a known quirk.

### 4-State Conflict Classification

| State | Condition (index-level) | Meaning |
|-------|------------------------|---------|
| `in-sync` | Content hash matches previous index | No change (local-meta-only collapsed into this) |
| `upstream-changed` | Content hash differs, no local modification | Upstream evolved |
| `both-changed` | Content hash differs, local modification detected | Conflict — needs human review |
| `local-missing` | Skill not in previous index | New skill — auto-add |

The `local-meta-only` extra state from `sync_legal_skills.py` is collapsed into `in-sync` (content matches, local metadata-only changes are not a conflict at the index level). The `missing-upstream` extra state is omitted (not part of the 4-state model).

### Merge Report Structure

```json
{
  "namespace_mappings": {"court-sms": "legal-court-sms", ...},
  "conflict_classification": {
    "in-sync": [...],
    "upstream-changed": [...],
    "both-changed": [...],
    "local-missing": [...]
  },
  "total_skills": 396,
  "summary": {"in-sync": N, "upstream-changed": N, "both-changed": N, "local-missing": N}
}
```

### Read-Only Enforcement

- `compute_content_hash` — pure function, no I/O
- `build_namespace_mappings` — pure function, no I/O
- `classify_conflicts` — reads previous index dict (in-memory), calls `_detect_local_modification` (read-only `Path.exists()`)
- `_detect_local_modification` — uses `Path.exists()` only, never creates files
- `_load_previous_index` — uses `Path.read_text()` only, never writes
- No `shutil.copytree`, no `git checkout`, no `write_text`, no `touch`, no `unlink` in the module
- Static analysis test (`test_no_write_operations`) verifies this

## Test Coverage (19 tests)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_compute_content_hash_deterministic` | Same input → same hash |
| 2 | `test_compute_content_hash_different_inputs` | Different inputs → different hashes |
| 3 | `test_namespace_mappings_legal_skills` | legal-skills → `legal-` prefix |
| 4 | `test_namespace_mappings_ai_for_china_legal` | ai-for-china-legal → `<plugin>:` prefix |
| 5 | `test_namespace_mappings_shared` | shared → `shared:` prefix |
| 6 | `test_namespace_mappings_legal_prefix_quirk` | `legal-qa-extractor` → `legal-legal-qa-extractor` |
| 7 | `test_classify_conflicts_no_previous_index` | No previous index → `local-missing` |
| 8 | `test_classify_conflicts_in_sync` | Matching hash → `in-sync` |
| 9 | `test_classify_conflicts_upstream_changed` | Different hash, no local mod → `upstream-changed` |
| 10 | `test_classify_conflicts_both_changed` | Different hash, local mod → `both-changed` |
| 11 | `test_classify_conflicts_local_meta_only_collapsed` | Matching hash + local mod → `in-sync` (collapsed) |
| 12 | `test_build_merge_report_structure` | MergeReport has 4 keys, namespace_mappings, total_skills |
| 13 | `test_build_merge_report_summary_counts` | Summary counts match actual classification |
| 14 | `test_detect_local_modification_no_marker` | No markers → False |
| 15 | `test_detect_local_modification_with_changelog` | LOCAL_CHANGELOG.md → True |
| 16 | `test_detect_local_modification_does_not_create_markers` | No files created after detection |
| 17 | `test_no_write_operations` | Static analysis: no write ops in source |
| 18 | `test_load_previous_index_missing_file` | Missing file → None |
| 19 | `test_load_previous_index_valid_file` | Valid JSON → parsed dict |

## Gate Status

- **skill-index tests:** 100/100 PASS (`python -m unittest discover -s packages/skill-index/tests`)
  - 50 from Plan 96-01 (scanner core)
  - 31 from Plan 96-02 (classification + metadata, parallel)
  - 19 from Plan 96-03 (conflict model)
- **compileall:** PASS (`packages/skill-index/src` + `packages/skill-index/tests`)
- **Existing 33 gates:** Not re-run (gate registration deferred to Plan 96-04)
- **gate-coverage meta-test:** EXPECTED FAILURE — `packages/skill-index/src` not registered in any gate yet. Gate registration is deferred to Plan 96-04.

## Parallel Execution with 96-02

Plan 96-02 (classification + metadata) ran in parallel with Plan 96-03. Both plans modified `__init__.py` with different symbols (additive, no conflict). The combined `__init__.py` exports all symbols from both plans. All 100 tests (50 + 31 + 19) pass together.

## Deviations

None. All tasks executed as planned. The `legal-` prefix quirk is preserved as documented. The 4-state model collapses `local-meta-only` into `in-sync` as specified.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] merger.py (conflict_model.py) created with namespace isolation
- [x] 4-state conflict classification implemented (in-sync / upstream-changed / both-changed / local-missing)
- [x] merge_report generation works (build_merge_report)
- [x] legal- prefix applied to legal-skills entries
- [x] All existing tests stay green (100/100 pass)
- [x] SUMMARY.md with Self-Check: PASSED
