---
phase: 96
slug: real-skill-index
status: draft
created: 2026-08-09
skip_discuss: false
---

# Phase 96 — Real Skill Index

## Phase Goal

396 个真实法律 SKILL.md 首次进入平台视野——平台能在不修改任一 skill 仓的前提下生成机器可读索引

## Requirements

- **SKILL-01**: 真实扫描并索引 `ai-for-china-legal`（345 个 SKILL.md）与 `legal-skills`（51 个 SKILL.md），产出机器可读 `skill-index.json`
- **SKILL-02**: 索引在不修改任一 skill 仓的前提下生成；正确区分约 60 个编排入口与约 285 个叶子子技能；正确解析 frontmatter、父子关系、`plugin.json`
- **SKILL-03**: 索引记录 `token_estimate`、`declared_gates`、`referenced_resources`、`practice_profile_dependency`、`host_assumptions`、`required_scripts`，供路由、可观测与上下文预算使用
- **SKILL-04**: 双仓合并与冲突模型——命名空间隔离、`legal-` 前缀、四态冲突分类（`in-sync` / `upstream-changed` / `both-changed` / `local-missing`），继承 `lawfirm-profile/scripts/sync_legal_skills.py` 语义
- **SAFE-05**: skill 语料以只读 vendoring 引用，平台不写回 skill 仓

## Success Criteria

1. `packages/skill-index` 能扫描 vendored 的 `ai-for-china-legal`（345 个 SKILL.md）与 `legal-skills`（51 个 SKILL.md），产出 `skill-index.json`，总数与实测一致
2. 索引过程只读——有测试断言扫描前后 skill 仓文件的 mtime 与内容哈希不变
3. 索引正确区分约 60 个编排入口与约 285 个叶子子技能，父子关系正确（从目录结构 + `plugin.json` + 编排入口正文三方交叉验证）
4. 每条索引记录含 `token_estimate`、`declared_gates`、`referenced_resources`、`practice_profile_dependency`、`host_assumptions`、`required_scripts`、`source_repo`、`license`
5. 双仓合并生效：命名空间隔离、上游 skill 加 `legal-` 前缀、四态冲突分类（`in-sync` / `upstream-changed` / `both-changed` / `local-missing`）可产出报告
6. 索引器对上游目录结构变化容错——缺失 frontmatter、缺失 `plugin.json`、非常规嵌套都不导致崩溃，而是产出带警告的记录

## Codebase Scout Findings

### Source Repos (read-only vendoring targets)

#### ai-for-china-legal (345 SKILL.md, 13 plugins)

- **Location:** `/home/sorawatcher/workspace/ai-for-china-legal/`
- **Structure:** `<plugin>/skills/<skill-name>/SKILL.md` (orchestration entry) + `<plugin>/skills/<skill-name>/<sub-skill>/SKILL.md` (leaf sub-skill)
- **Plugin count:** 13 plugins, each with `.claude-plugin/plugin.json`
  - Plugins: `ai-governance`, `commercial-legal`, `construction-legal`, `criminal-compliance`, `data-compliance`, `employment-legal`, `family-legal`, `ip-legal`, `law-student`, `legal-aid`, `legal-builder-hub`, `litigation-legal`, `regulatory-legal`
- **Marketplace manifest:** `.claude-plugin/marketplace.json` (lists all 13 plugins with `source` paths)
- **Orchestration entries (direct child of `skills/`):** 73 SKILL.md files
- **Leaf sub-skills (nested 2+ levels):** 270 SKILL.md files
- **Total:** 73 + 270 = 343 (plus 2 in `shared/` = 345 total; `shared/research-gate/SKILL.md` is a cross-cutting skill)
- **Frontmatter:** 100% have YAML frontmatter (0 missing). Fields: `name`, `description`, `argument-hint` (optional). No `version`, `license`, or `author` fields in ai-for-china-legal frontmatter.
- **plugin.json format:** Each plugin's `.claude-plugin/plugin.json` contains `name`, `version`, `description`, `author`, and a `skills` array listing every skill with `name`, `path`, and `description`. This is the authoritative skill registry per plugin.
- **CLAUDE.md practice profiles:** 13 plugin-level `CLAUDE.md` files (one per plugin) + 1 root `CLAUDE.md` + 1 `shared/CLAUDE.md`. These are the practice configuration templates that ~50 skills depend on.
- **shared/inkstatute-integration/:** Contains `ASK-USER-PROTOCOL.md` and `AGENT-UX-OPTIMIZATION.md` — the ask_user protocol and UX requirements written for this platform.
- **shared/research-gate/SKILL.md:** Cross-cutting research gate skill (`name: cn-law-research-gate`). Referenced by 19 SKILL.md files.
- **License:** Not explicitly stated per-skill; project-level license in the repo.

#### legal-skills (51 SKILL.md, 37 with scripts/)

- **Location:** `/home/sorawatcher/workspace/legal-skills/`
- **Structure:** `skills/<skill-name>/SKILL.md` (flat, no nesting — 0 nested sub-skills)
- **Plugin manifest:** `.claude-plugin/plugin.json` (single plugin, `name: legal-skills`) + `.claude-plugin/marketplace.json` (lists all skills as plugins with `source` paths)
- **Scripts:** 35 skills have `scripts/` directories, 140 `.py` files total
- **Frontmatter:** 100% have YAML frontmatter. Fields: `name`, `description`, `version` (quoted string like `"1.5.3"`), `license` (`MIT` or `CC-BY-NC`), `author`, `homepage`. Richer frontmatter than ai-for-china-legal.
- **LICENSE.txt:** Per-skill LICENSE files present (CC-BY-NC for legal professional skills, MIT for tool skills)
- **No plugin.json skills array:** Unlike ai-for-china-legal, legal-skills does not enumerate skills in plugin.json. The marketplace.json `plugins` array is the skill registry.
- **No CLAUDE.md practice profiles:** legal-skills does not use the CLAUDE.md practice configuration mechanism.
- **No orchestration/leaf distinction:** All 51 skills are flat leaf skills (no parent-child nesting).

### Existing Platform Infrastructure

#### packages/skill-registry (V2, manifest-based)

- **Location:** `packages/skill-registry/src/inkstatute_skill_registry/`
- **Files:** `__init__.py`, `discovery.py`, `mapper.py`, `registry.py`, `api.py`, `write.py`, `write_api.py`
- **mapper.py:** Converts solution-pack manifest skill dicts → `NeutralSkillDescriptor`. Currently reads from `solutions/lawfirm/manifest.json` (the 4 fake hand-written skills).
- **discovery.py:** Builds `/.well-known/agent-skills/index.json` from `NeutralSkillDescriptor` list (RFC v0.2.0 format with `name`, `type`, `description`, `url`, `digest`).
- **NeutralSkillDescriptor** (platform-contract): `skill_id`, `name`, `description`, `input_schema_ref`, `output_schema_ref`, `required_tool_refs`, `metadata` ( JsonObject).
- **This package reads from manifest JSON, not from real SKILL.md files.** Phase 96 creates a new `packages/skill-index` that scans real SKILL.md files. The skill-registry can later consume the skill-index output.

#### solutions/lawfirm/manifest.json (the 4 fake skills)

- Contains 4 hand-written skill entries: `case_qa`, `contract_draft`, `litigation_summary`, `compliance_review`
- These are V2 fake data for running SolutionLoader — completely unrelated to the 396 real skills
- **Decision (PROJECT.md):** This manifest's `skills` array will be deprecated as a skill source (SKILL-09, Phase 97). Manifest keeps only persona/output_policy/MCP/industry_context/secret_templates.

#### lawfirm-profile/scripts/sync_legal_skills.py (conflict model reference)

- **Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/sync_legal_skills.py` (382 lines)
- **Purpose:** Syncs `legal-skills` upstream → `lawfirm` Hermes profile local mirror
- **Conflict classification (4-state + 2 extra):**
  - `in-sync` — local and upstream versions match
  - `upstream-changed` — upstream changed, local unchanged → auto-sync
  - `both-changed` — both changed → conflict, needs human intervention
  - `local-missing` — skill exists upstream but not locally → auto-sync
  - `local-meta-only` — local has only metadata changes
  - `missing-upstream` — skill exists locally but not upstream
- **Namespace isolation:** Upstream skill names get `legal-` prefix when synced to local (e.g., `de-ai-polish` → `legal-de-ai-polish`)
- **Version comparison:** Uses frontmatter `version` field for change detection
- **Phase 96 inherits this semantic** but applies it to the index level (not filesystem sync)

#### Gate registration pattern (scripts/run_v2_gates.py)

- 34 gates currently registered
- Pattern: `Gate("package-name", (py, "-m", "unittest", "discover", "-s", "packages/package-name/tests"), (src_paths...))`
- `gate-coverage` meta-test enforces every `packages/*/src` and `services/*/src` is covered
- New `packages/skill-index` must be registered as a new gate + added to gate-coverage paths

### Key Structural Observations

1. **Orchestration vs leaf distinction:** In ai-for-china-legal, orchestration entries are `skills/<name>/SKILL.md` (73 files) and leaf sub-skills are `skills/<name>/<sub>/SKILL.md` (270 files). The `plugin.json` `skills` array lists ALL skills (both orchestration and leaf) with explicit `path` fields. Cross-validation: directory nesting + plugin.json paths + orchestration entry body text (mentions "子技能" / "编排入口").

2. **legal-skills has no nesting:** All 51 skills are flat. No orchestration/leaf distinction needed for this repo.

3. **Total counts:** 345 (ai-for-china-legal) + 51 (legal-skills) = 396 SKILL.md files. Orchestration entries: ~73 (all from ai-for-china-legal). Leaf skills: ~270 + 51 = ~321. The "~60 orchestration / ~285 leaf" estimate in requirements is approximate; actual is 73/323.

4. **Frontmatter variance:** ai-for-china-legal has minimal frontmatter (name, description, argument-hint). legal-skills has rich frontmatter (name, version, license, author, homepage, description). The scanner must handle both schemas.

5. **Practice profile dependency:** 337 SKILL.md files in ai-for-china-legal reference CLAUDE.md or practice profile concepts. This is a majority — the `practice_profile_dependency` field will be `true` for most ai-for-china-legal skills.

6. **Research-gate dependency:** 19 SKILL.md files explicitly reference `research-gate`. The `declared_gates` field should capture this.

7. **Script dependency:** 37 legal-skills SKILL.md files reference `scripts/`. The `required_scripts` field should list script paths.

8. **No SKILL.md is missing frontmatter** in either repo — but the scanner must be tolerant of future cases.

## Key Decisions (Auto-Selected)

### 1. Package Location: New `packages/skill-index/`

[auto] Q: "Where should the skill index scanner code live?" → Selected: "New package `packages/skill-index/`" (recommended default)

**Rationale:** The existing `packages/skill-registry` reads from manifest JSON (V2 fake data). Phase 96 needs a new package that scans real SKILL.md files from two external repos. Following the package-per-concern pattern, `packages/skill-index` is the scanner+indexer, while `skill-registry` remains the read API (and can later consume the index). The scanner is a build-time tool; the registry is a runtime API.

### 2. Scanner Implementation: YAML frontmatter parser + directory tree walker

[auto] Q: "How to scan SKILL.md files and extract metadata?" → Selected: "Python YAML frontmatter parser + recursive directory walker" (recommended default)

**Rationale:** All 396 SKILL.md files have YAML frontmatter delimited by `---`. Python's `pyyaml` is already a project dependency. The scanner:
- Walks each repo's directory tree recursively
- Finds all `SKILL.md` files
- Parses YAML frontmatter (name, description, version, license, etc.)
- Extracts body text for token estimation and content analysis
- Reads `plugin.json` / `marketplace.json` for plugin-level metadata
- Does NOT modify any source file

### 3. Orchestration vs Leaf Distinction: Three-way cross-validation

[auto] Q: "How to distinguish ~73 orchestration entries from ~323 leaf sub-skills?" → Selected: "Three-way cross-validation: directory nesting + plugin.json + body text heuristics" (recommended default)

**Rationale:** A skill is classified as an orchestration entry if ANY of:
- **Directory structure:** `skills/<name>/SKILL.md` with sub-directories containing more `SKILL.md` files (has children)
- **plugin.json:** Listed in the plugin's `skills` array with child skills also listed (parent-child relationship visible in paths)
- **Body text heuristic:** Contains "编排入口" (orchestration entry) or "子技能" (sub-skill) keywords, or has a sub-skill orchestration table

A skill is classified as a leaf if:
- **Directory structure:** `skills/<name>/<sub>/SKILL.md` (nested under a parent) OR `skills/<name>/SKILL.md` with no sub-directories
- **No child SKILL.md files** in its subtree

For legal-skills: all 51 are flat leaves (no nesting).

The `skill_type` field in the index record will be `"orchestration"` or `"leaf"`, with `parent_skill` for leaf skills pointing to the orchestration entry's skill_id.

### 4. Token Estimation: Character-based heuristic (1 token ≈ 1.5 Chinese chars / 4 English chars)

[auto] Q: "How to estimate token count for each skill?" → Selected: "Character-based heuristic with CJK awareness" (recommended default)

**Rationale:** Skills are predominantly Chinese text. A simple heuristic:
- Count CJK characters × 1.0 (roughly 1 token per CJK char in modern tokenizers)
- Count non-CJK characters / 4 (roughly 4 chars per token for Latin text)
- Sum = `token_estimate`

This is an estimate for routing and budget purposes, not an exact count. No external tokenizer dependency needed. The estimate covers the full SKILL.md file (frontmatter + body).

### 5. Conflict Model: Inherit sync_legal_skills.py 4-state classification

[auto] Q: "How to handle dual-repo merge with conflict classification?" → Selected: "Inherit sync_legal_skills.py semantic with index-level adaptation" (recommended default)

**Rationale:** `lawfirm-profile/scripts/sync_legal_skills.py` already defines the 4-state conflict model:
- `in-sync` — versions match between repos (or local mirror and upstream)
- `upstream-changed` — upstream changed since last index
- `both-changed` — both sides changed (conflict, needs human review)
- `local-missing` — skill exists in upstream but not in local mirror

Phase 96 adapts this to the index level:
- Namespace isolation: `ai-for-china-legal` skills keep their plugin-prefixed names (e.g., `commercial-legal:contract-review`). `legal-skills` skills get `legal-` prefix (e.g., `legal-court-sms`).
- The conflict report compares the index against a previous index snapshot (if available) or against the `lawfirm` profile's existing skill set.
- The 4-state classification is output as a merge report, not used for filesystem sync (Phase 96 is read-only).

### 6. Error Tolerance: Graceful degradation with warning records

[auto] Q: "How to handle missing frontmatter, missing plugin.json, non-standard nesting?" → Selected: "Produce warning records, never crash" (recommended default)

**Rationale:** Success criterion 6 requires the scanner to be tolerant of upstream structure changes. The scanner:
- Missing frontmatter → record with `name` derived from directory name, `description: null`, `warnings: ["missing_frontmatter"]`
- Missing plugin.json → scan directory tree directly, `warnings: ["missing_plugin_json"]`
- Non-standard nesting (e.g., 3+ levels deep) → record with full path, `warnings: ["non_standard_nesting"]`
- Malformed YAML → record with raw text, `warnings: ["malformed_frontmatter"]`
- All warnings are collected in the index for observability

### 7. Index Format: JSON with per-skill records + merge report

[auto] Q: "What's the schema of skill-index.json?" → Selected: "JSON with top-level metadata + skills array + merge_report" (recommended default)

**Rationale:** The `skill-index.json` schema:
```json
{
  "generated_at": "ISO-8601",
  "scanner_version": "1.0.0",
  "repos": {
    "ai-for-china-legal": {"path": "...", "commit": "...", "skill_count": 345},
    "legal-skills": {"path": "...", "commit": "...", "skill_count": 51}
  },
  "skills": [
    {
      "skill_id": "commercial-legal:contract-review",
      "name": "contract-review",
      "source_repo": "ai-for-china-legal",
      "plugin": "commercial-legal",
      "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
      "skill_type": "orchestration",
      "parent_skill": null,
      "child_skills": ["commercial-legal:risk-identification", ...],
      "description": "...",
      "frontmatter": {"name": "...", "description": "...", "argument-hint": "..."},
      "token_estimate": 3500,
      "declared_gates": ["research-gate"],
      "referenced_resources": ["shared/references/document-structures.md"],
      "practice_profile_dependency": true,
      "host_assumptions": ["/commercial-legal:contract-review trigger"],
      "required_scripts": [],
      "license": null,
      "version": null,
      "warnings": []
    }
  ],
  "merge_report": {
    "namespace_mapping": {"court-sms": "legal-court-sms"},
    "conflict_classification": {
      "in-sync": [...],
      "upstream-changed": [...],
      "both-changed": [...],
      "local-missing": [...]
    }
  },
  "warnings": []
}
```

### 8. Read-Only Enforcement: mtime + content hash assertion tests

[auto] Q: "How to verify scan doesn't modify source repos?" → Selected: "Pre-scan and post-scan mtime + SHA-256 hash comparison tests" (recommended default)

**Rationale:** Success criterion 2 requires proof that scanning is read-only. The test:
1. Before scanning: record mtime + SHA-256 content hash of all files in both repos
2. Run the scanner
3. After scanning: re-record mtime + SHA-256 of all files
4. Assert: all mtimes and hashes are unchanged

This test runs in CI and is part of the skill-index gate.

### 9. Gate Registration: New gate in run_v2_gates.py + gate-coverage update

[auto] Q: "How to register the skill-index gate?" → Selected: "Add Gate() entry + add to gate-coverage paths" (recommended default)

**Rationale:** Following the established pattern (STATE.md V6: "新包需加 path 变量 + Gate() 条目 + compileall"):
1. Add `skill_index_src` path variable
2. Add `Gate("skill-index", (py, "-m", "unittest", "discover", "-s", "packages/skill-index/tests"), (skill_index_src, platform_src))` 
3. Add `"packages/skill-index/src"` to the gate-coverage meta-test's path list
4. Run `compileall` on the new package

## Key Files

### New Package to Create
- `packages/skill-index/` — New Python package
  - `src/inkstatute_skill_index/` — Main source
    - `__init__.py`
    - `scanner.py` — Directory tree walker, finds all SKILL.md files
    - `frontmatter_parser.py` — YAML frontmatter extraction + validation
    - `metadata_extractor.py` — Extracts token_estimate, declared_gates, referenced_resources, practice_profile_dependency, host_assumptions, required_scripts
    - `orchestration_classifier.py` — Three-way cross-validation for orchestration vs leaf
    - `conflict_model.py` — 4-state conflict classification (inherits sync_legal_skills.py semantic)
    - `index_builder.py` — Assembles skill-index.json from scanned records
    - `cli.py` — CLI entry point: `python -m inkstatute_skill_index scan --repo <path> --output <path>`
  - `tests/` — Test suite
    - `test_scanner.py` — Directory walking + SKILL.md discovery
    - `test_frontmatter_parser.py` — YAML parsing + edge cases
    - `test_orchestration_classifier.py` — Orchestration vs leaf classification
    - `test_metadata_extractor.py` — Token estimation, gate/resource/script extraction
    - `test_conflict_model.py` — 4-state conflict classification
    - `test_read_only.py` — mtime + hash immutability assertion
    - `test_index_builder.py` — Full index assembly + schema validation
    - `fixtures/` — Minimal fixture SKILL.md files for unit tests
  - `pyproject.toml` — Package configuration

### Existing Files to Reference
- `packages/skill-registry/src/inkstatute_skill_registry/mapper.py` — Existing manifest-to-descriptor mapper (V2 fake data)
- `packages/skill-registry/src/inkstatute_skill_registry/discovery.py` — Discovery index builder (RFC v0.2.0)
- `packages/platform-contract/src/platform_contract/events.py` — `NeutralSkillDescriptor` dataclass (lines 104-112)
- `lawfirm-profile/scripts/sync_legal_skills.py` — Conflict model reference (4-state classification, namespace isolation)
- `solutions/lawfirm/manifest.json` — The 4 fake skills to be deprecated (Phase 97)
- `scripts/run_v2_gates.py` — Gate registration (line 62: skill-registry pattern, line 257: gate-coverage meta-test)
- `ai-for-china-legal/.claude-plugin/marketplace.json` — Plugin registry (13 plugins)
- `ai-for-china-legal/<plugin>/.claude-plugin/plugin.json` — Per-plugin skill registry (13 files)
- `legal-skills/.claude-plugin/marketplace.json` — Skill registry (51 skills as plugins)
- `legal-skills/.claude-plugin/plugin.json` — Plugin metadata

### Source Repos (read-only scan targets)
- `/home/sorawatcher/workspace/ai-for-china-legal/` — 345 SKILL.md, 13 plugins
- `/home/sorawatcher/workspace/legal-skills/` — 51 SKILL.md, flat structure

## Patterns Established

- **Read-only vendoring:** Scanner reads from source repos via filesystem path, never writes back. Immutability proven by mtime + hash tests.
- **Three-way cross-validation:** Orchestration vs leaf classification uses directory structure + plugin.json + body text heuristics, not a single signal.
- **Conflict model inheritance:** The 4-state conflict classification inherits semantic from `sync_legal_skills.py`, adapted to index-level (not filesystem sync).
- **Graceful degradation:** Missing frontmatter, missing plugin.json, non-standard nesting → warning records, never crash.
- **Token estimation without external dependencies:** CJK-aware character heuristic, no tokenizer library needed.
- **Namespace isolation:** `ai-for-china-legal` skills use `<plugin>:<skill>` namespacing; `legal-skills` skills use `legal-<skill>` prefix.
