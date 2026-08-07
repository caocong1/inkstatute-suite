# Phase 96 — Real Skill Index: Discussion Log

**Mode:** --auto (all gray areas auto-selected with recommended options)
**Date:** 2026-08-09
**Phase:** 96 — Real Skill Index
**Requirements:** SKILL-01, SKILL-02, SKILL-03, SKILL-04, SAFE-05
**Depends on:** Phase 90 (complete)

---

## Gray Area Analysis

9 gray areas identified, all auto-selected with recommended options.

---

### Gray Area 1: Scanner Implementation — How to scan SKILL.md files and extract metadata?

**Options considered:**
- A) Python YAML frontmatter parser + recursive directory walker (recommended)
- B) Shell script with grep/awk for frontmatter extraction
- C) External tool (e.g., markdown parser library) with custom plugin

**Auto-selected: A — Python YAML frontmatter parser + recursive directory walker**

**Rationale:** All 396 SKILL.md files have YAML frontmatter delimited by `---`. Python's `pyyaml` is already a project dependency. The scanner walks each repo's directory tree, finds all `SKILL.md` files, parses YAML frontmatter, and extracts body text. This is consistent with the platform's Python-first architecture and the existing `skill-registry` package patterns. Structured parsing per AGENTS.md: "Prefer structured parsers and schema validators over ad hoc string parsing."

---

### Gray Area 2: Orchestration vs Leaf Distinction — How to distinguish ~73 orchestration entries from ~323 leaf sub-skills?

**Options considered:**
- A) Three-way cross-validation: directory nesting + plugin.json + body text heuristics (recommended)
- B) Directory nesting only (has children = orchestration)
- C) plugin.json skills array only (listed as parent = orchestration)

**Auto-selected: A — Three-way cross-validation**

**Rationale:** No single signal is sufficient:
- Directory nesting alone misses the case where an orchestration entry has no children (standalone skill at `skills/<name>/SKILL.md`)
- plugin.json alone may not always list parent-child relationships explicitly
- Body text alone is fragile (keyword matching)

Cross-validation: a skill is orchestration if it has child SKILL.md files in its subtree OR is listed in plugin.json with child skills OR contains orchestration keywords ("编排入口", "子技能") with a sub-skill table. For legal-skills, all 51 are flat leaves (no nesting, no plugin.json skills array).

**Scout data:** ai-for-china-legal has 73 orchestration entries (direct child of `skills/`) and 270 leaf sub-skills (nested). legal-skills has 51 flat leaves, 0 nested.

---

### Gray Area 3: Token Estimation — How to estimate token count for each skill?

**Options considered:**
- A) Character-based heuristic with CJK awareness (recommended)
- B) tiktoken/transformers tokenizer library
- C) Word count × fixed multiplier

**Auto-selected: A — Character-based heuristic with CJK awareness**

**Rationale:** Skills are predominantly Chinese text. Modern tokenizers (GPT-4, Claude) tokenize CJK characters at roughly 1 token per character. A simple heuristic:
- CJK characters × 1.0
- Non-CJK characters / 4.0
- Sum = `token_estimate`

No external tokenizer dependency needed. This is an estimate for routing and context budget purposes (SKILL-03), not an exact count. Adding a tokenizer library would introduce a heavy dependency for minimal accuracy gain at this layer. The self-built core (Phase 100) can use a real tokenizer when exact budgets matter.

---

### Gray Area 4: Conflict Model — How to handle dual-repo merge with namespace isolation and 4-state conflict classification?

**Options considered:**
- A) Inherit sync_legal_skills.py semantic with index-level adaptation (recommended)
- B) New conflict model designed from scratch
- C) Git-based diff (use git to compare repos)

**Auto-selected: A — Inherit sync_legal_skills.py semantic**

**Rationale:** `lawfirm-profile/scripts/sync_legal_skills.py` (382 lines) already defines a proven 4-state conflict model:
- `in-sync` — versions match
- `upstream-changed` — upstream changed, local unchanged
- `both-changed` — both changed (conflict)
- `local-missing` — upstream has skill, local doesn't

SKILL-04 explicitly requires "继承 `lawfirm-profile/scripts/sync_legal_skills.py` 语义". The index-level adaptation:
- Namespace isolation: ai-for-china-legal skills use `<plugin>:<skill>` namespacing; legal-skills skills get `legal-` prefix (matching sync_legal_skills.py's `local_dir_name()` function)
- Conflict report compares current index against previous index snapshot or lawfirm profile skill set
- Output is a report, not filesystem sync (Phase 96 is read-only per SAFE-05)

---

### Gray Area 5: Error Tolerance — How to handle missing frontmatter, missing plugin.json, non-standard nesting?

**Options considered:**
- A) Produce warning records, never crash (recommended)
- B) Skip files with errors, log to stderr
- C) Fail fast on any structural anomaly

**Auto-selected: A — Produce warning records, never crash**

**Rationale:** Success criterion 6 explicitly requires: "索引器对上游目录结构变化容错——缺失 frontmatter、缺失 plugin.json、非常规嵌套都不导致崩溃，而是产出带警告的记录". The scanner produces records with `warnings` arrays:
- `missing_frontmatter` — name from directory, description null
- `missing_plugin_json` — scan directory tree directly
- `non_standard_nesting` — record with full path
- `malformed_frontmatter` — record with raw text

All warnings collected in the index for observability. Scout confirmed 0/345 and 0/51 missing frontmatter currently, but the scanner must be future-proof.

---

### Gray Area 6: Index Format — What's the schema of skill-index.json?

**Options considered:**
- A) JSON with top-level metadata + skills array + merge_report (recommended)
- B) JSONL (one record per line)
- C) SQLite database

**Auto-selected: A — JSON with top-level metadata + skills array + merge_report**

**Rationale:** JSON is the platform's cross-language contract format (PROJECT.md: "JSON Schema 为跨语言契约格式"). A single JSON file is:
- Easy to validate with JSON Schema
- Easy to consume from Python (platform) and TypeScript (UI)
- Human-readable for debugging
- Versionable in git (if committed as a build artifact)

The schema includes: `generated_at`, `scanner_version`, `repos` (paths + commits + counts), `skills` array (per-skill records with all SKILL-03 fields), `merge_report` (namespace mapping + 4-state conflict classification), and top-level `warnings`.

Each skill record contains: `skill_id`, `name`, `source_repo`, `plugin`, `relative_path`, `skill_type` (orchestration/leaf), `parent_skill`, `child_skills`, `description`, `frontmatter`, `token_estimate`, `declared_gates`, `referenced_resources`, `practice_profile_dependency`, `host_assumptions`, `required_scripts`, `license`, `version`, `warnings`.

---

### Gray Area 7: Read-Only Enforcement — How to verify scan doesn't modify source repos?

**Options considered:**
- A) Pre-scan and post-scan mtime + SHA-256 hash comparison tests (recommended)
- B) Filesystem permission check (read-only mount)
- C) strace/ftrace to verify no write syscalls

**Auto-selected: A — mtime + SHA-256 hash comparison tests**

**Rationale:** Success criterion 2 requires: "有测试断言扫描前后 skill 仓文件的 mtime 与内容哈希不变". The test:
1. Before scanning: record mtime + SHA-256 of all files in both repos
2. Run the scanner
3. After scanning: re-record mtime + SHA-256
4. Assert all unchanged

This is deterministic, CI-friendly, and directly proves the read-only property. SAFE-05 ("skill 语料以只读 vendoring 引用，平台不写回 skill 仓") is verified by this test.

---

### Gray Area 8: Gate Registration — How to register the skill-index gate?

**Options considered:**
- A) Add Gate() entry + add to gate-coverage paths (recommended)
- B) Separate test runner script
- C) Manual test execution only

**Auto-selected: A — Add Gate() entry + add to gate-coverage paths**

**Rationale:** STATE.md V6 established the pattern: "新包需加 path 变量 + Gate() 条目 + compileall". Following the existing `skill-registry` gate pattern (run_v2_gates.py line 62, 109-110):
1. Add `skill_index_src = repo_root / "packages" / "skill-index" / "src"` path variable
2. Add `Gate("skill-index", (py, "-m", "unittest", "discover", "-s", "packages/skill-index/tests"), (skill_index_src, platform_src))` 
3. Add `"packages/skill-index/src"` to gate-coverage meta-test path list
4. Run `compileall` on the new package

This brings the gate count from 34 to 35. The gate-coverage meta-test enforces every `packages/*/src` is covered.

---

### Gray Area 9: Package Relationship — skill-index vs skill-registry, how do they relate?

**Options considered:**
- A) skill-index is the scanner (build-time), skill-registry is the API (runtime); skill-registry consumes skill-index output (recommended)
- B) Merge skill-index into skill-registry (extend existing package)
- C) Replace skill-registry with skill-index entirely

**Auto-selected: A — Separate packages, skill-index feeds skill-registry**

**Rationale:** The existing `skill-registry` package reads from manifest JSON (V2 fake data) and provides a runtime read API (`list`, `get`, `search` + `/.well-known/agent-skills/index.json`). Phase 96 creates `skill-index` as a build-time scanner that produces `skill-index.json` from real SKILL.md files. Keeping them separate:
- `skill-index` = scanner + indexer (build-time, produces JSON artifact)
- `skill-registry` = runtime read API (consumes the JSON artifact, serves Gateway `/v1/skills`)
- Phase 97/98 will wire skill-registry to read from skill-index output instead of manifest JSON
- The `NeutralSkillDescriptor` in platform-contract remains the shared contract type

This follows the existing package-per-concern pattern and avoids disrupting the 34 existing gates.

---

## Summary

| # | Gray Area | Auto-Selected Decision |
|---|-----------|----------------------|
| 1 | Scanner implementation | Python YAML frontmatter parser + recursive directory walker |
| 2 | Orchestration vs leaf distinction | Three-way cross-validation (directory + plugin.json + body text) |
| 3 | Token estimation | CJK-aware character heuristic (no external tokenizer) |
| 4 | Conflict model | Inherit sync_legal_skills.py 4-state classification, index-level |
| 5 | Error tolerance | Warning records, never crash |
| 6 | Index format | JSON with metadata + skills array + merge_report |
| 7 | Read-only enforcement | mtime + SHA-256 hash comparison tests |
| 8 | Gate registration | New Gate() + gate-coverage path update |
| 9 | Package relationship | skill-index (build-time scanner) feeds skill-registry (runtime API) |

**Gray areas auto-selected:** 9/9
**Gray areas requiring user input:** 0/9 (auto mode)
