# Plan 96-02 Summary — Orchestration/Leaf Classification + Metadata Enrichment

**Phase:** 96 — Real Skill Index
**Plan:** 96-02 — Orchestration/Leaf Classification + Metadata Enrichment — three-way cross-validation + 8 SKILL-03 metadata fields
**Wave:** 2 (depends on 96-01)
**Requirements:** SKILL-02, SKILL-03
**Status:** COMPLETE
**Executed:** 2026-08-09

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 96-02-01 | Create orchestration_classifier.py — three-way cross-validation (directory + plugin.json + body text) | c5677d3 | PASS |
| 96-02-02 | Create metadata_extractor.py — 8 SKILL-03 fields | b54fb55 | PASS |
| 96-02-03 | Create test_orchestration_classifier.py — 12 unit tests | 0b24803 | PASS |
| 96-02-04 | Create test_metadata_extractor.py — 19 unit tests | 2c33d56 | PASS |
| 96-02-05 | Update __init__.py exports + verify all tests pass | 5da36bc | PASS |

## Commits

1. `c5677d3` — feat(96-02): orchestration_classifier.py — three-way cross-validation (directory + plugin.json + body text)
2. `b54fb55` — feat(96-02): metadata_extractor.py — 8 SKILL-03 fields (declared_gates, referenced_resources, practice_profile_dependency, host_assumptions, required_scripts, source_repo, license)
3. `0b24803` — test(96-02): orchestration classifier — 12 unit tests (three-way cross-validation, name collision, precedence)
4. `2c33d56` — test(96-02): metadata extractor — 19 unit tests (8 SKILL-03 fields, read-only static analysis)
5. `5da36bc` — feat(96-02): update __init__.py exports — classify_skill, classify_all_skills, ClassificationResult, extract_metadata, SkillMetadata

## Files Created

### Source modules
- `packages/skill-index/src/inkstatute_skill_index/orchestration_classifier.py` — Three-way cross-validation classifier (directory structure + plugin.json + body text heuristics). Classifies each `ScannedSkill` as `"orchestration"` or `"leaf"`, extracts parent-child relationships. Orchestration takes precedence when a skill is both nested and has children. Handles name collisions via path-based (not name-based) parent-child resolution.
- `packages/skill-index/src/inkstatute_skill_index/metadata_extractor.py` — 8-field metadata extractor for SKILL-03: `token_estimate`, `declared_gates` (research-gate, ask-user-enforcement, citation-audit, de-ai-polish), `referenced_resources` (shared/references/, _shared/, references/), `practice_profile_dependency` (CLAUDE.md, 实践配置, 审查立场, 执业配置), `host_assumptions` (trigger patterns + argument-hint), `required_scripts` (body text + filesystem glob), `source_repo`, `license` (frontmatter or None).

### Test suite (31 new tests, all pass)
- `packages/skill-index/tests/test_orchestration_classifier.py` — 12 tests covering orchestration with children, leaf with parent, body text signals, legal-skills flat, standalone, plugin.json signal, plugin.json missing, classify_all_skills, name collision (ai-governance), shared skill, orchestration takes precedence
- `packages/skill-index/tests/test_metadata_extractor.py` — 19 tests covering all 4 declared_gates, referenced_resources, practice_profile_dependency, host_assumptions, required_scripts (body + dir), license, full extract_metadata, read-only static analysis

### Modified files
- `packages/skill-index/src/inkstatute_skill_index/__init__.py` — Added exports: `classify_skill`, `classify_all_skills`, `ClassificationResult`, `extract_metadata`, `SkillMetadata`. `__all__` now has 24 symbols.

## Acceptance Criteria Results

### Task 96-02-01: orchestration_classifier.py
- [x] `from inkstatute_skill_index.orchestration_classifier import classify_skill, classify_all_skills, ClassificationResult` succeeds
- [x] `ClassificationResult` has fields: `skill_type`, `parent_skill`, `child_skills`, `classification_signals`, `warnings`
- [x] Orchestration entry (depth=0, has children, body contains "编排入口") → `skill_type == "orchestration"`, `child_skills` non-empty
- [x] Leaf sub-skill (depth=1, body contains "迁移说明") → `skill_type == "leaf"`, `parent_skill` is parent's skill_id
- [x] legal-skills flat skill (depth=0, no children, no orchestration body text) → `skill_type == "leaf"`, `parent_skill == None`
- [x] Standalone ai-for-china-legal skill (depth=0, no children, no orchestration body text) → `skill_type == "leaf"`, `parent_skill == None`
- [x] `classify_all_skills` returns a dict with all skill_ids as keys
- [x] Classifier handles `plugin_json_skills = None` without crashing
- [x] Classifier handles ai-governance name collision correctly (uses path, not name)
- [x] `python -m compileall` exits 0

### Task 96-02-02: metadata_extractor.py
- [x] `from inkstatute_skill_index.metadata_extractor import extract_metadata, SkillMetadata` succeeds
- [x] `SkillMetadata` has all 8 fields: `token_estimate`, `declared_gates`, `referenced_resources`, `practice_profile_dependency`, `host_assumptions`, `required_scripts`, `source_repo`, `license`
- [x] `_extract_declared_gates("...research-gate...")` returns list containing `"research-gate"`
- [x] `_extract_referenced_resources("...shared/references/document-structures.md...")` returns list containing the path
- [x] `_check_practice_profile_dependency("...CLAUDE.md...")` returns `True`
- [x] `_check_practice_profile_dependency("no practice profile reference")` returns `False`
- [x] `_extract_host_assumptions(".../commercial-legal:contract-review...", {"argument-hint": "[合同]"})` returns list with trigger pattern and argument hint
- [x] `_extract_license({"license": "MIT"}, "legal-skills")` returns `"MIT"`
- [x] `_extract_license({}, "ai-for-china-legal")` returns `None`
- [x] `extract_metadata` returns `SkillMetadata` with all fields populated
- [x] No write operations in the module (grep verified)
- [x] `python -m compileall` exits 0

### Task 96-02-03: test_orchestration_classifier.py
- [x] `python -m unittest packages.skill-index.tests.test_orchestration_classifier` exits 0
- [x] All 12 test cases pass
- [x] Three-way cross-validation correctly identifies orchestration vs leaf
- [x] Name collision edge case handled correctly (path-based, not name-based)
- [x] `python -m compileall` exits 0

### Task 96-02-04: test_metadata_extractor.py
- [x] `python -m unittest packages.skill-index.tests.test_metadata_extractor` exits 0
- [x] All 19 test cases pass
- [x] All 8 metadata fields correctly extracted
- [x] No write operations in metadata_extractor.py (static analysis test passes)
- [x] `python -m compileall` exits 0

### Task 96-02-05: __init__.py exports + verification
- [x] `from inkstatute_skill_index import classify_skill, classify_all_skills, extract_metadata, SkillMetadata` succeeds
- [x] `python -m unittest discover -s packages/skill-index/tests` exits 0 (100 tests pass)
- [x] `python -m compileall packages/skill-index/src packages/skill-index/tests` exits 0
- [x] `__all__` includes all new symbols (24 total)

## Classification Logic Summary

### Three-way cross-validation signals

| Signal | Source | Orchestration trigger | Leaf trigger |
|--------|--------|----------------------|-------------|
| Directory structure | Filesystem | Skill's directory has sub-directories with SKILL.md | Skill is nested (depth >= 1) |
| plugin.json | `.claude-plugin/plugin.json` skills[] | Skill's path is a parent of other paths | Skill's path is nested under another |
| Body text | SKILL.md body | "编排入口", "子技能编排顺序", "子技能" in table | "迁移说明" (migration note) |

**Precedence:** Orchestration takes precedence over leaf. If ANY orchestration signal triggers, the skill is `"orchestration"` even if it is also nested under a parent.

### Edge cases handled
- **Name collision (ai-governance):** `filing-material-preparation` exists under two parents (`algorithm-filing` and `deep-synthesis-filing`). Classifier uses path-based parent-child resolution, so both instances are correctly classified as leaf with different parents.
- **Missing plugin.json:** `plugin_json_skills = None` → classification falls back to directory + body text only.
- **Standalone skills:** depth=0 with no children and no orchestration body text → `"leaf"` with `parent_skill = None`.
- **Shared skills:** `shared/research-gate/SKILL.md` → `"leaf"` with `parent_skill = None`.

## Metadata Fields Summary

| Field | Extraction method | Example |
|-------|-------------------|---------|
| `token_estimate` | From scanner (CJK-aware heuristic) | 3500 |
| `declared_gates` | Body text grep for 4 guardrail patterns | `["research-gate", "ask-user-enforcement"]` |
| `referenced_resources` | Regex for shared/references/, _shared/, references/ paths | `["shared/references/document-structures.md"]` |
| `practice_profile_dependency` | Body text check for CLAUDE.md, 实践配置, 审查立场, 执业配置 | `True` (336/343 ai-for-china-legal skills) |
| `host_assumptions` | Regex for `/<plugin>:<skill>` triggers + frontmatter argument-hint | `["/commercial-legal:contract-review", "[合同]"]` |
| `required_scripts` | Body text grep for scripts/*.py + filesystem glob | `["scripts/parse_contract.py"]` |
| `source_repo` | From scanner context | `"ai-for-china-legal"` |
| `license` | Frontmatter `license` field (legal-skills) or None (ai-for-china-legal) | `"MIT"` or `None` |

## Gate Status

- **skill-index tests:** 100/100 PASS (`python -m unittest discover -s packages/skill-index/tests`)
  - 50 from Plan 96-01 (scanner core)
  - 12 from Plan 96-02 (orchestration classifier)
  - 19 from Plan 96-02 (metadata extractor)
  - 19 from Plan 96-03 (conflict model, parallel wave)
- **compileall:** PASS (`packages/skill-index/src` + `packages/skill-index/tests`)
- **Existing 33 gates:** ALL GREEN (no regressions)
- **gate-coverage meta-test:** EXPECTED FAILURE — `packages/skill-index/src` not registered in any gate yet. Gate registration is deferred to Plan 96-04.

## Read-Only Enforcement (SAFE-05)

- `orchestration_classifier.py` — no filesystem operations at all (works purely on `ScannedSkill` data structures)
- `metadata_extractor.py` — reads body text and optionally lists files via `Path.glob("*.py")` (read-only). Static analysis test verifies no `write_text`, `write_bytes`, `touch`, `unlink`, `rmdir`, `os.rename`, `shutil` calls.
- No modifications to external repos (ai-for-china-legal, legal-skills)

## Deviations

**One minor deviation from action spec (auto-fixed per Rule 1-3):**

The plan's action spec for `_check_practice_profile_dependency` listed `"practice profile"` as one of the markers. However, the acceptance criteria requires `_check_practice_profile_dependency("no practice profile reference")` to return `False`. These are contradictory — the test string contains the substring `"practice profile"`.

**Resolution:** Removed `"practice profile"` from the marker list. The remaining 4 markers (`CLAUDE.md`, `实践配置`, `审查立场`, `执业配置`) are sufficient to detect practice profile dependency. Per research §9.2, 336/343 ai-for-china-legal skills reference `CLAUDE.md` directly (97.9%), so `CLAUDE.md` alone covers the vast majority. The acceptance criteria is the hard gate and takes precedence over the action spec.

**No other deviations.** All tasks executed as planned.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] orchestration_classifier.py created with three-way cross-validation (directory + plugin.json + body text)
- [x] metadata_extractor.py created with 8 field extractors
- [x] Classification distinguishes orchestration vs leaf correctly (12 tests pass)
- [x] All 8 metadata fields extracted (19 tests pass)
- [x] All existing tests stay green (100/100 pass)
- [x] No write operations in either module (read-only enforced)
- [x] No modifications to external repos
- [x] SUMMARY.md with Self-Check: PASSED
