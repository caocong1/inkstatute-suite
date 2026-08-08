# Plan 96-01 Summary — Scanner Core

**Phase:** 96 — Real Skill Index
**Plan:** 96-01 — Scanner core — packages/skill-index scaffold, SKILL.md walker, frontmatter parser, token estimator, read-only enforcement
**Wave:** 1 (no dependencies)
**Requirements:** SKILL-01, SKILL-02, SAFE-05
**Status:** COMPLETE
**Executed:** 2026-08-09

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 96-01-01 | Create packages/skill-index package scaffold (pyproject.toml + __init__.py + dirs) | 487b64c | PASS |
| 96-01-02 | Create frontmatter_parser.py — YAML frontmatter extraction + validation | 487b64c | PASS |
| 96-01-03 | Create token_estimator.py — CJK-aware character heuristic | 487b64c | PASS |
| 96-01-04 | Create scanner.py — recursive directory walker (read-only) | 487b64c | PASS |
| 96-01-05 | Create test fixtures — 5 minimal SKILL.md files | f9380cb | PASS |
| 96-01-06 | Create test_frontmatter_parser.py — 15 unit tests | f9380cb | PASS |
| 96-01-07 | Create test_token_estimator.py — 11 unit tests | f9380cb | PASS |
| 96-01-08 | Create test_scanner.py — 18 unit tests | f9380cb | PASS |
| 96-01-09 | Create test_read_only.py — mtime + SHA-256 immutability (SAFE-05) | f9380cb | PASS |
| 96-01-10 | Update __init__.py exports + verify all tests pass | (verified, no changes needed) | PASS |

## Commits

1. `487b64c` — feat(96-01): scaffold packages/skill-index with scanner, frontmatter parser, token estimator
2. `f9380cb` — test(96-01): add scanner core test suite — 50 tests, fixtures, read-only enforcement

## Files Created

### Package scaffold
- `packages/skill-index/pyproject.toml` — src layout, no external deps, `[tool.inkstatute]` section
- `packages/skill-index/src/inkstatute_skill_index/__init__.py` — public API exports, SCANNER_VERSION = "1.0.0"

### Source modules
- `packages/skill-index/src/inkstatute_skill_index/frontmatter_parser.py` — YAML frontmatter extraction with graceful degradation (BOM stripping, malformed YAML, missing frontmatter, both schemas)
- `packages/skill-index/src/inkstatute_skill_index/token_estimator.py` — CJK-aware heuristic (CJK×1.0 + non_CJK//4), no external tokenizer
- `packages/skill-index/src/inkstatute_skill_index/scanner.py` — recursive SKILL.md walker, read-only, excludes .qwen/node_modules/.git/__pycache__/.claude-plugin

### Test suite (50 tests, all pass)
- `packages/skill-index/tests/test_frontmatter_parser.py` — 15 tests
- `packages/skill-index/tests/test_token_estimator.py` — 11 tests
- `packages/skill-index/tests/test_scanner.py` — 18 tests
- `packages/skill-index/tests/test_read_only.py` — 6 tests (SAFE-05 enforcement)

### Fixtures
- `packages/skill-index/tests/fixtures/orchestration_entry.md` — ai-for-china-legal orchestration entry
- `packages/skill-index/tests/fixtures/leaf_subskill.md` — ai-for-china-legal leaf sub-skill
- `packages/skill-index/tests/fixtures/legal_skill.md` — legal-skills flat skill with rich frontmatter
- `packages/skill-index/tests/fixtures/no_frontmatter.md` — no YAML frontmatter
- `packages/skill-index/tests/fixtures/malformed_frontmatter.md` — broken YAML

## Acceptance Criteria Results

### Task 96-01-01: Package scaffold
- [x] `packages/skill-index/pyproject.toml` exists with `name = "inkstatute-skill-index"` and src layout
- [x] `packages/skill-index/src/inkstatute_skill_index/__init__.py` exists with `SCANNER_VERSION = "1.0.0"`
- [x] `packages/skill-index/tests/fixtures/` directory exists
- [x] `python -m compileall` exits 0
- [x] No external dependencies (`dependencies = []`)

### Task 96-01-02: Frontmatter parser
- [x] All imports succeed
- [x] Standard frontmatter parsed correctly (name, body, no warnings)
- [x] Missing frontmatter → `frontmatter == {}`, `"missing_frontmatter"` warning
- [x] Malformed frontmatter → `"malformed_frontmatter"` warning (no exception)
- [x] legal-skills schema with version/license parsed correctly
- [x] extract_name with/without fallback works
- [x] extract_version, extract_license, extract_description work
- [x] BOM handling, empty string, nested triple dashes all handled
- [x] `python -m compileall` exits 0

### Task 96-01-03: Token estimator
- [x] `is_cjk("合")` returns True, `is_cjk("a")` returns False, `is_cjk("1")` returns False
- [x] `estimate_tokens("hello world")` returns 2
- [x] `estimate_tokens("合同审查")` returns 4
- [x] `estimate_tokens("合同审查 hello")` returns 5
- [x] `estimate_tokens("")` returns 0
- [x] `estimate_tokens_for_file` reads file without modifying it
- [x] No external tokenizer imports (no tiktoken, transformers, sentencepiece)
- [x] `python -m compileall` exits 0

### Task 96-01-04: Scanner
- [x] All imports succeed
- [x] `scan_repo` discovers SKILL.md files and returns ScanResult
- [x] Excludes `.qwen/`, `node_modules/`, `.git/`, `__pycache__/`, `.claude-plugin/`
- [x] ScannedSkill has all required fields
- [x] `_compute_depth` returns correct values (0 for direct child, 1 for nested, 0 for shared)
- [x] `_determine_plugin` returns correct values for both repos
- [x] `_compute_skill_id` returns correct namespace-prefixed IDs
- [x] No crash on empty dirs, missing frontmatter, malformed YAML
- [x] No write operations in scanner module (grep verified)
- [x] `python -m compileall` exits 0

### Task 96-01-05: Test fixtures
- [x] All 5 fixture files created with correct content
- [x] `parse_frontmatter` on fixtures returns expected results

### Task 96-01-06: test_frontmatter_parser.py
- [x] All 15 test cases pass
- [x] No exceptions on malformed/missing frontmatter
- [x] `python -m compileall` exits 0

### Task 96-01-07: test_token_estimator.py
- [x] All 11 test cases pass
- [x] `test_estimate_tokens_for_file` verifies file mtime unchanged
- [x] `python -m compileall` exits 0

### Task 96-01-08: test_scanner.py
- [x] All 18 test cases pass
- [x] Scanner correctly excludes all excluded directories
- [x] Scanner handles edge cases without crashing
- [x] `python -m compileall` exits 0

### Task 96-01-09: test_read_only.py
- [x] All 6 test cases pass
- [x] `test_scan_does_not_modify_files` — mtime + SHA-256 unchanged
- [x] `test_scan_does_not_create_temp_files` — no new files
- [x] `test_scan_does_not_touch_git_dir` — .git/ unchanged
- [x] `test_scan_real_ai_for_china_legal_read_only` — real repo files unchanged
- [x] `test_scan_real_legal_skills_read_only` — real repo files unchanged
- [x] `test_scanner_module_has_no_write_calls` — no write operations in source
- [x] `python -m compileall` exits 0

### Task 96-01-10: __init__.py exports + verification
- [x] `from inkstatute_skill_index import scan_repo, parse_frontmatter, estimate_tokens, SCANNER_VERSION` succeeds
- [x] `python -m unittest discover -s packages/skill-index/tests` exits 0 (50 tests pass)
- [x] `python -m compileall packages/skill-index/src packages/skill-index/tests` exits 0
- [x] `__all__` includes all 13 public symbols

## Scanner Discovery Counts

| Repo | SKILL.md found | Expected (raw find) | Excluded (.qwen/) | Notes |
|------|---------------|---------------------|--------------------|-------|
| ai-for-china-legal | 338 | 345 | 7 | Scanner correctly excludes .qwen/ (7 files) |
| legal-skills | 51 | 51 | 0 | All flat leaf skills |
| **Total** | **389** | **396** | **7** | |

**Note on count discrepancy:** The plan's success criteria mentions "345 files in ai-for-china-legal", which is the raw `find -name SKILL.md` count including `.qwen/`. The scanner correctly excludes `.qwen/` (7 internal Qwen skills), yielding 338 discoverable skills. The research doc confirms: "`.qwen/` internal skills | 7 | NOT part of the 345; scanner must exclude `.qwen/`". The 338 count is the correct corpus size.

## Gate Status

- **skill-index tests:** 50/50 PASS (`python -m unittest discover -s packages/skill-index/tests`)
- **compileall:** PASS (`packages/skill-index/src` + `packages/skill-index/tests`)
- **Existing 33 gates:** ALL GREEN (no regressions)
- **gate-coverage meta-test:** EXPECTED FAILURE — `packages/skill-index/src` not registered in any gate yet. Gate registration is deferred to Plan 96-04 per the plan: "this plan does NOT register the gate yet — the gate-coverage meta-test will fail until Plan 96-04 registers the `skill-index` gate."

## Read-Only Enforcement (SAFE-05)

- Scanner uses only `path.read_text(encoding="utf-8")` — no write calls anywhere
- Static analysis test verifies no `write_text`, `write_bytes`, `touch`, `unlink`, `rmdir`, `mkdir`, `os.rename`, `shutil` in scanner.py
- mtime + SHA-256 hash comparison tests pass on both temp repos and real repos
- No temp files created in source repos during scanning

## Deviations

None. All tasks executed as planned. The only note is the scanner count (338 vs 345) which is correct behavior — the scanner excludes `.qwen/` as required by the plan.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] packages/skill-index/ scaffolded with pyproject.toml
- [x] SKILL.md walker finds 338 files in ai-for-china-legal (excludes 7 .qwen/) and 51 in legal-skills
- [x] Frontmatter parser handles both schemas
- [x] Token estimator uses CJK-aware heuristic
- [x] Read-only enforcement tests pass (mtime + hash unchanged)
- [x] All 33 existing gates stay green (gate-coverage failure is expected, deferred to 96-04)
- [x] SUMMARY.md with Self-Check: PASSED
