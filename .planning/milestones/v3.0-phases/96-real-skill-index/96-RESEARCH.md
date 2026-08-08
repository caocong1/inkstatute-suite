# Phase 96 Research — Real Skill Index

**Phase:** 96 — Real Skill Index
**Created:** 2026-08-09
**Status:** Complete
**Requirements:** SKILL-01, SKILL-02, SKILL-03, SKILL-04, SAFE-05

---

## 1. Source Repo Inventory

### 1.1 ai-for-china-legal (345 SKILL.md, 13 plugins)

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/`

**Verified counts (filesystem scan):**

| Category | Count | Notes |
|----------|-------|-------|
| Total SKILL.md | 345 | Confirmed via `find -name SKILL.md` |
| Plugin-level orchestration entries | 73 | Direct child of `<plugin>/skills/<name>/SKILL.md` |
| Leaf sub-skills (nested) | 270 | `<plugin>/skills/<name>/<sub>/SKILL.md` |
| Shared cross-cutting skills | 2 | `shared/research-gate/SKILL.md`, `shared/feedback-refinement/SKILL.md` |
| `.qwen/` internal skills | 7 | NOT part of the 345; scanner must exclude `.qwen/` |
| Max nesting depth | 2 levels | No 3+ level deep SKILL.md found |

**13 plugins (all with `.claude-plugin/plugin.json`):**

| Plugin | Orchestration | Leaf | plugin.json skills[] | Notes |
|--------|--------------|------|---------------------|-------|
| ai-governance | 5 | 20 | 25 | 1 plugin.json entry has no matching SKILL.md on disk (`algorithm-filing-material-preparation` — actual path is `algorithm-filing/filing-material-preparation/SKILL.md`, name collision with `deep-synthesis-filing/filing-material-preparation`) |
| commercial-legal | 4 | 19 | 23 | Clean match |
| construction-legal | 5 | 20 | 25 | Clean match |
| criminal-compliance | 5 | 20 | 25 | Clean match |
| data-compliance | 5 | 20 | 25 | Clean match |
| employment-legal | 6 | 25 | 31 | Clean match |
| family-legal | 5 | 20 | 25 | Clean match |
| ip-legal | 5 | 20 | 25 | Clean match |
| law-student | 5 | 20 | 25 | Clean match |
| legal-aid | 5 | 20 | 25 | Clean match |
| legal-builder-hub | 5 | 20 | 25 | Clean match |
| litigation-legal | 6 | 26 | 32 | Clean match |
| regulatory-legal | 5 | 20 | 25 | Clean match |
| **Total** | **73** | **270** | **336** | 336 plugin.json entries vs 343 on-disk (73+270); discrepancy from ai-governance name collision + shared skills not in any plugin.json |

**Key structural finding:** `plugin.json` `skills[]` arrays list ALL skills (both orchestration and leaf) with explicit `name`, `path`, and `description` fields. Total across all 13 plugin.json files = 336 entries. The 343 on-disk skills under `*/skills/` (73+270) don't all appear in plugin.json — the `shared/` skills (2) are outside plugin directories, and the ai-governance name collision causes a mismatch.

**Directory structure pattern:**
```
ai-for-china-legal/
├── .claude-plugin/marketplace.json        # 13 plugins, source=./<plugin>
├── <plugin>/
│   ├── .claude-plugin/plugin.json         # name, version, description, author, skills[]
│   ├── CLAUDE.md                          # Practice profile template (13 total)
│   ├── README.md
│   └── skills/
│       ├── _shared/                       # Domain-shared references (NOT skills)
│       │   ├── legal-basis-conventions.md
│       │   ├── practice-profile-schema.md
│       │   └── <plugin-specific>.md
│       ├── <orchestration-entry>/
│       │   ├── SKILL.md                   # Orchestration entry
│       │   └── <leaf-sub-skill>/
│       │       └── SKILL.md              # Leaf sub-skill
│       └── <standalone-skill>/
│           └── SKILL.md                   # Leaf with no children
├── shared/
│   ├── CLAUDE.md                          # Shared practice config
│   ├── research-gate/SKILL.md             # Cross-cutting research gate
│   ├── feedback-refinement/SKILL.md       # Cross-cutting feedback skill
│   ├── references/                        # Shared templates
│   └── inkstatute-integration/            # Platform integration protocols
│       ├── ASK-USER-PROTOCOL.md
│       └── AGENT-UX-OPTIMIZATION.md
├── .qwen/skills/                          # 7 internal Qwen skills — EXCLUDE from scan
└── connectors/                            # MCP connectors
```

**`_shared/` directories:** Found in 10+ plugins. Contain `.md` reference files (legal-basis-conventions, practice-profile-schema, etc.) but NO `SKILL.md` files. Scanner must skip `_shared/` directories — they are reference material, not skills.

### 1.2 legal-skills (51 SKILL.md, flat structure)

**Location:** `/home/sorawatcher/workspace/legal-skills/`

**Verified counts:**

| Category | Count | Notes |
|----------|-------|-------|
| Total SKILL.md | 51 | All under `skills/<name>/SKILL.md` |
| Skills with `scripts/` directory | 35 | 140 `.py` files total |
| Skills with `LICENSE.txt` | 45 | 6 skills missing LICENSE.txt |
| Nesting depth | 0 | All flat — no sub-skills |
| Orchestration entries | 0 | All are leaf skills |

**License distribution (from frontmatter `license:` field):**

| License | Count |
|---------|-------|
| MIT | 31 |
| CC-BY-NC | 10 |
| Complete terms in LICENSE.txt | 6 |
| MIT License - 详见 LICENSE.txt | 2 |
| CC BY-NC-SA 4.0 - 详见 LICENSE.txt | 1 |
| CC BY-NC-SA 4.0 | 1 |

**Marketplace vs filesystem mismatch:** `marketplace.json` lists 35 plugins, but 51 SKILL.md files exist on disk. 19 skills have SKILL.md but are NOT in marketplace.json (e.g., `court-sms`, `de-ai-polish`, `legal-case-analysis`, `contract-copilot`). Scanner must use filesystem as source of truth, not marketplace.json.

**Directory structure:**
```
legal-skills/
├── .claude-plugin/
│   ├── plugin.json              # Single plugin metadata (no skills[] array)
│   └── marketplace.json         # 35 plugins listed (incomplete vs 51 on disk)
├── skills/
│   ├── <skill-name>/
│   │   ├── SKILL.md             # Flat, no nesting
│   │   ├── scripts/             # 35 skills have this
│   │   │   └── *.py             # 140 total Python files
│   │   ├── LICENSE.txt           # 45 skills have this
│   │   ├── references/           # Optional
│   │   ├── CHANGELOG.md          # Skill-level changelog
│   │   └── DECISIONS.md          # Skill-level decisions
│   └── ...
└── AGENTS.md                     # Project conventions
```

---

## 2. SKILL.md Frontmatter Schema

### 2.1 ai-for-china-legal frontmatter (343 skills under `*/skills/`)

**Frontmatter coverage:** 100% — all 343 skills have YAML frontmatter delimited by `---`.

**Field frequency (full scan of 343 skills):**

| Field | Count | Percentage | Notes |
|-------|-------|------------|-------|
| `name` | 343 | 100% | Always present |
| `description` | 343 | 100% | Always present; uses YAML `>` folded scalar for multi-line |
| `argument-hint` | 325 | 94.8% | Optional; appears in most orchestration entries and many leaves |
| `source` | 7 | 2% | Only in `.qwen/` skills (excluded from scan) |
| `extracted_at` | 7 | 2% | Only in `.qwen/` skills (excluded from scan) |

**Schema (ai-for-china-legal):**
```yaml
---
name: contract-review
description: >
  Multi-line folded scalar description...
argument-hint: "[合同文件路径或内容]"
---
```

**No `version`, `license`, `author`, or `homepage` fields** in ai-for-china-legal frontmatter. License is project-level, not per-skill.

### 2.2 legal-skills frontmatter (51 skills)

**Frontmatter coverage:** 100% — all 51 skills have YAML frontmatter.

**Field frequency (full scan of 51 skills):**

| Field | Count | Percentage | Notes |
|-------|-------|------------|-------|
| `name` | 51 | 100% | Always present |
| `description` | 51 | 100% | Always present |
| `license` | 51 | 100% | MIT, CC-BY-NC, or reference to LICENSE.txt |
| `author` | 49 | 96% | Usually "杨卫薪律师（微信ywxlaw）" |
| `version` | 47 | 92% | Quoted string like `"1.5.3"` |
| `homepage` | 47 | 92% | GitHub URL |
| `argument-hint` | 0 | 0% | NOT used in legal-skills |

**Schema (legal-skills):**
```yaml
---
name: court-sms
homepage: https://github.com/cat-xierluo/legal-skills
author: 杨卫薪律师（微信ywxlaw）
version: "1.5.0"
license: MIT
description: 本技能应在用户收到法院短信...
---
```

### 2.3 Frontmatter variance summary

The scanner must handle two distinct schemas:

| Field | ai-for-china-legal | legal-skills |
|-------|-------------------|--------------|
| `name` | ✓ (always) | ✓ (always) |
| `description` | ✓ (always, folded scalar) | ✓ (always, inline) |
| `argument-hint` | ✓ (95%) | ✗ (never) |
| `version` | ✗ | ✓ (92%, quoted string) |
| `license` | ✗ | ✓ (100%) |
| `author` | ✗ | ✓ (96%) |
| `homepage` | ✗ | ✓ (92%) |

**Parsing approach:** Use `pyyaml` (already a project dependency). Parse frontmatter between `---` delimiters. Handle folded scalar `>` for `description`. Treat all fields as optional except `name` (fall back to directory name if missing).

---

## 3. Orchestration vs Leaf Classification

### 3.1 Three-way cross-validation method

A skill is classified as **orchestration** if ANY of:

1. **Directory structure:** `<plugin>/skills/<name>/SKILL.md` AND has sub-directories containing more `SKILL.md` files (has children)
2. **plugin.json:** Listed in `skills[]` with child skills whose `path` starts with `skills/<name>/`
3. **Body text heuristic:** Contains "编排入口" (orchestration entry) or references "子技能" (sub-skill) with explicit sub-skill paths

A skill is classified as **leaf** if:
- `<plugin>/skills/<name>/<sub>/SKILL.md` (nested under a parent) OR
- `<plugin>/skills/<name>/SKILL.md` with no sub-directories containing SKILL.md

### 3.2 Verified classification signals

| Signal | Count | Source |
|--------|-------|--------|
| "编排入口" keyword in body | 255 SKILL.md | grep across all SKILL.md |
| "子技能" keyword in body | 330 SKILL.md | grep across all SKILL.md |
| `/plugin:skill` trigger patterns | 319 SKILL.md | grep for `/<plugin>:<skill>` patterns |
| `shared/references` or `_shared/` references | 305 SKILL.md | grep for resource paths |
| `CLAUDE.md` references | 336 SKILL.md | grep for CLAUDE.md mentions |
| `research-gate` references | 19 SKILL.md | grep for research-gate |

### 3.3 Orchestration entry body text pattern

Orchestration entries contain explicit sub-skill orchestration tables:

```markdown
## 子技能编排顺序

| 顺序 | 子技能 | 职责 | 子技能路径 | 单独触发 |
| 1 | **risk-identification** | ... | `skills/contract-review/risk-identification/SKILL.md` | `/commercial-legal:risk-identification` |
| 2 | **legal-basis** | ... | `skills/contract-review/legal-basis/SKILL.md` | `/commercial-legal:legal-basis` |
```

Leaf sub-skills contain "迁移说明" (migration note) referencing their parent:
```markdown
> **迁移说明**：本子技能包含原 contract-review/SKILL.md 中的...
```

### 3.4 Parent-child relationship extraction

**From directory structure:** `skills/contract-review/risk-identification/SKILL.md` → parent = `contract-review`, child = `risk-identification`.

**From plugin.json:** Each entry's `path` field encodes the hierarchy: `skills/contract-review/risk-identification/SKILL.md` → parent directory = `contract-review`.

**From body text:** Orchestration entries list child paths explicitly in markdown tables.

### 3.5 legal-skills classification

All 51 legal-skills are **flat leaf skills** — no nesting, no orchestration entries, no parent-child relationships. The `skill_type` field will be `"leaf"` with `parent_skill: null` for all.

---

## 4. plugin.json Format

### 4.1 ai-for-china-legal plugin.json

Each of the 13 plugins has `.claude-plugin/plugin.json` with:

```json
{
  "name": "commercial-legal",
  "version": "0.3.0",
  "description": "...",
  "author": { "name": "AI for China Legal Contributors" },
  "skills": [
    {
      "name": "contract-review",
      "path": "skills/contract-review/SKILL.md",
      "description": "合同审查编排入口..."
    },
    {
      "name": "risk-identification",
      "path": "skills/contract-review/risk-identification/SKILL.md",
      "description": "合同审查子技能..."
    }
  ]
}
```

**Key properties:**
- `skills[]` lists ALL skills (orchestration + leaf) with explicit `path` fields
- `path` is relative to the plugin root
- Total across all 13 plugins: 336 entries
- Parent-child relationship is encoded in the path nesting

**Edge case discovered:** ai-governance plugin.json has `algorithm-filing-material-preparation` with path `skills/algorithm-filing/filing-material-preparation/SKILL.md`, but the `name` field doesn't match the directory name (`filing-material-preparation`). This is because two different parents both have a child named `filing-material-preparation`, so the plugin.json uses a disambiguated name. The scanner must use the `path` field (not `name`) as the authoritative identifier, and derive `name` from frontmatter or directory name.

### 4.2 legal-skills plugin.json

```json
{
  "name": "legal-skills",
  "version": "1.0.0",
  "description": "...",
  "author": { "name": "杨卫薪律师（微信ywxlaw）" },
  "repository": "https://github.com/cat-xierluo/legal-skills",
  "license": "Apache-2.0",
  "keywords": [...]
}
```

**No `skills[]` array.** The skill registry for legal-skills is in `marketplace.json` `plugins[]`, but that is incomplete (35 of 51). Scanner must use filesystem as source of truth.

### 4.3 marketplace.json format

**ai-for-china-legal:** 13 plugins listed with `source: ./<plugin>` paths. This is a plugin-level registry, not a skill-level registry.

**legal-skills:** 35 entries in `plugins[]` with `name`, `description`, `version`, `source` (e.g., `skills/yuandian-law-search`), `category`, `tags`. This is the skill-level registry but is incomplete (16 skills missing).

---

## 5. Existing Platform Infrastructure

### 5.1 packages/skill-registry (V2, manifest-based)

**Location:** `packages/skill-registry/src/inkstatute_skill_registry/`

**Files:** `__init__.py`, `discovery.py`, `mapper.py`, `registry.py`, `api.py`, `write.py`, `write_api.py`

**mapper.py** (64 lines): Converts solution-pack manifest skill dicts → `NeutralSkillDescriptor`. Reads from `solutions/lawfirm/manifest.json` (the 4 fake hand-written skills). Field mapping: `name` → `skill_id` (prefixed as `{solution_id}/{name}`), `description`, `required_tools` → `required_tool_refs`, `intent`/`risk_level` → `metadata`.

**discovery.py** (81 lines): Builds `/.well-known/agent-skills/index.json` from `NeutralSkillDescriptor` list (RFC v0.2.0 format with `name`, `type`, `description`, `url`, `digest`). Uses SHA-256 for digest computation.

**NeutralSkillDescriptor** (platform-contract, lines 105-112):
```python
@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

**Relationship to Phase 96:** `skill-registry` reads from manifest JSON (V2 fake data). Phase 96 creates a NEW `packages/skill-index` that scans real SKILL.md files. The skill-registry can later consume the skill-index output. The scanner is a build-time tool; the registry is a runtime API.

### 5.2 solutions/lawfirm/manifest.json (4 fake skills)

Contains 4 hand-written skill entries:
- `case_qa` — Answer factual legal questions with citations
- `contract_draft` — Draft contract clauses with citation hooks
- `litigation_summary` — Summarize case materials for litigation strategy
- `compliance_review` — Review contract or policy for compliance issues

These are V2 fake data for running SolutionLoader — completely unrelated to the 396 real skills. Will be deprecated in Phase 97 (SKILL-09).

### 5.3 packages/skill-index — does NOT exist yet

Confirmed: no `packages/skill-index/` or `packages/skill_catalog/` directory exists. This is a new package to be created.

### 5.4 lawfirm-profile/scripts/sync_legal_skills.py (conflict model reference)

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/sync_legal_skills.py` (382 lines)

**Purpose:** Syncs `legal-skills` upstream → `lawfirm` Hermes profile local mirror.

**Key functions:**

- `parse_frontmatter_version(text)` — regex `^version:\s*["']?([0-9.]+)` extracts version from frontmatter
- `parse_frontmatter_name(text)` — regex `^name:\s*([^\n]+)` extracts name
- `list_upstream_skills()` — `git ls-tree -d --name-only` on `skills/` directory
- `list_local_skills()` — scans `~/.hermes/profiles/lawfirm/skills/` for dirs starting with `legal-` and containing `.sync_source` marker file
- `local_dir_name(skill_name)` — namespace isolation: `de-ai-polish` → `legal-de-ai-polish`; if already starts with `legal-`, keeps it
- `compare_skill(skill_name)` — 4-state + 2 extra state classification

**Conflict classification (6 states):**

| State | Condition | Action |
|-------|-----------|--------|
| `in-sync` | Content matches AND no local changelog | No action needed |
| `local-meta-only` | Content matches BUT has local changelog | Metadata-only local changes |
| `upstream-changed` | Content differs AND no local changelog | Auto-sync |
| `both-changed` | Content differs AND has local changelog | Conflict — needs human intervention |
| `local-missing` | Skill exists upstream but not locally | Auto-sync |
| `missing-upstream` | Skill exists locally but not upstream | Orphan — investigate |

**Namespace isolation rule:**
```python
def local_dir_name(skill_name):
    if skill_name.startswith("legal-"):
        return f"legal-{skill_name}"  # already has legal-, keep it
    return f"legal-{skill_name}"
```

This means: `de-ai-polish` → `legal-de-ai-polish`, `legal-qa-extractor` → `legal-legal-qa-extractor` (the code comment says "保留" but the implementation doubles the prefix — this is a known quirk).

**Phase 96 adaptation:** The 4-state classification is inherited but applied at the index level (not filesystem sync). The conflict report compares the current index against a previous index snapshot or against the lawfirm profile's existing skill set.

---

## 6. Token Estimation

### 6.1 Approach: CJK-aware character heuristic

No external tokenizer dependency. The heuristic:

```
token_estimate = (CJK_character_count × 1.0) + (non_CJK_character_count / 4)
```

Rationale: Modern tokenizers (GPT-4, Claude) tokenize CJK characters at roughly 1 token per character. Latin text averages ~4 characters per token.

### 6.2 Verified sample estimates

**ai-for-china-legal samples:**

| Skill | Chars | CJK | Token Est |
|-------|-------|-----|-----------|
| filing-requirement-analysis | 15,154 | 3,768 | 6,614 |
| algorithm-type-identification | 18,014 | 4,525 | 7,897 |
| algorithm-filing | 8,758 | 2,112 | 3,773 |
| deep-synthesis-scope-identification | 19,508 | 4,976 | 8,609 |

**legal-skills samples:**

| Skill | Chars | CJK | Token Est |
|-------|-------|-----|-----------|
| contract-copilot | 24,797 | 5,916 | 10,636 |
| de-ai-polish | 30,931 | 7,511 | 13,366 |
| git-batch-commit | 7,421 | 1,290 | 2,822 |
| court-sms | 23,391 | 4,278 | 9,056 |

**Range:** ~2,800 to ~13,400 tokens per skill. This confirms the PRD's "2K–20K token" range for skill body injection (CORE-04, Phase 100).

### 6.3 Implementation

```python
def estimate_tokens(text: str) -> int:
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_cjk_count = len(text) - cjk_count
    return cjk_count + non_cjk_count // 4
```

The estimate covers the full SKILL.md file (frontmatter + body). For routing/budget purposes, this is sufficient — exact counts would require a tokenizer dependency that the platform doesn't need.

---

## 7. Conflict Model (Dual-Repo Merge)

### 7.1 Namespace isolation

| Repo | Namespace pattern | Example |
|------|------------------|---------|
| ai-for-china-legal | `<plugin>:<skill>` | `commercial-legal:contract-review` |
| legal-skills | `legal-<skill>` | `legal-court-sms` |

The `legal-` prefix for legal-skills is inherited from `sync_legal_skills.py`'s `local_dir_name()` function. The `<plugin>:<skill>` pattern for ai-for-china-legal follows the Claude Code plugin convention (`/commercial-legal:contract-review`).

### 7.2 4-state conflict classification (index-level)

Phase 96 adapts the sync model to the index level:

| State | Condition (index-level) | Meaning |
|-------|------------------------|---------|
| `in-sync` | Skill exists in both current index and previous snapshot, content hash matches | No change |
| `upstream-changed` | Skill exists in both, content hash differs, no local modification marker | Upstream evolved |
| `both-changed` | Skill exists in both, content hash differs, local modification detected | Conflict — needs human review |
| `local-missing` | Skill exists in upstream repo but not in previous index | New skill — auto-add |

**What constitutes a "conflict"?** A conflict (`both-changed`) occurs when:
1. A skill exists in both the current scan and a previous index snapshot
2. The content hash (SHA-256 of SKILL.md) differs from the snapshot
3. The skill has been marked as locally modified (e.g., via a `.local_modification` marker or a local changelog)

**Phase 96 is read-only:** The conflict report is output as a merge report in `skill-index.json`, not used for filesystem sync. No files are modified.

### 7.3 Merge report structure

```json
{
  "merge_report": {
    "namespace_mapping": {
      "court-sms": "legal-court-sms",
      "de-ai-polish": "legal-de-ai-polish"
    },
    "conflict_classification": {
      "in-sync": ["commercial-legal:contract-review", ...],
      "upstream-changed": ["legal-court-sms", ...],
      "both-changed": [],
      "local-missing": ["legal-new-skill", ...]
    }
  }
}
```

---

## 8. Read-Only Enforcement

### 8.1 Verification method

**Test approach:** mtime + SHA-256 content hash comparison before and after scan.

```python
def test_scan_is_read_only():
    # 1. Before scan: record mtime + SHA-256 of all files in both repos
    before = record_file_states(repo_path)
    
    # 2. Run the scanner
    scanner.scan(repo_path, output_path)
    
    # 3. After scan: re-record mtime + SHA-256
    after = record_file_states(repo_path)
    
    # 4. Assert: all mtimes and hashes unchanged
    assert before == after
```

### 8.2 What to check

- All files in `ai-for-china-legal/` (excluding `.qwen/`, `node_modules/`, `logs/`)
- All files in `legal-skills/skills/`
- Include `plugin.json`, `marketplace.json`, `CLAUDE.md`, `SKILL.md`, reference files, scripts

### 8.3 Edge cases

- Scanner must NOT create any temp files in the source repos
- Scanner must NOT touch `.git/` directories
- Scanner reads via `path.read_text()` / `path.read_bytes()` only
- If scanner writes output, it writes to a location OUTSIDE the source repos (e.g., `build/skill-index.json` or a path specified by `--output`)

---

## 9. Metadata Extraction Fields

Each index record must contain (SKILL-03):

| Field | Source | Extraction method |
|-------|--------|-------------------|
| `token_estimate` | SKILL.md full content | CJK-aware character heuristic (§6) |
| `declared_gates` | SKILL.md body text | grep for `research-gate`, `ask-user`, `citation`, `de-ai-polish` references |
| `referenced_resources` | SKILL.md body text | Extract paths matching `shared/references/`, `_shared/`, `references/` patterns |
| `practice_profile_dependency` | SKILL.md body text | `true` if references `CLAUDE.md` or practice profile concepts |
| `host_assumptions` | SKILL.md body text + plugin.json | Extract `/plugin:skill` trigger patterns and `argument-hint` |
| `required_scripts` | SKILL.md body text + filesystem | List `scripts/*.py` paths referenced or present in skill directory |
| `source_repo` | Scanner context | `"ai-for-china-legal"` or `"legal-skills"` |
| `license` | Frontmatter (legal-skills) or project-level (ai-for-china-legal) | From `license:` field or `null` for ai-for-china-legal |

### 9.1 Declared gates extraction

The `declared_gates` field captures which legal guardrails a skill declares:

- `research-gate` — 19 SKILL.md files reference `research-gate`
- `ask-user` — skills referencing the ask-user protocol
- `citation` — skills with citation requirements
- `de-ai-polish` — skills referencing de-AI polish

### 9.2 Practice profile dependency

336 of 343 ai-for-china-legal skills reference `CLAUDE.md` (97.9%). This field will be `true` for the vast majority of ai-for-china-legal skills and `false` for all legal-skills (which don't use CLAUDE.md practice profiles).

### 9.3 Referenced resources

305 SKILL.md files reference `shared/references/`, `shared/research-gate/`, or `_shared/` paths. These are the `referenced_resources` entries.

---

## 10. Gate Registration

### 10.1 Current gate system

**File:** `scripts/run_v2_gates.py` (318 lines)
**Current gate count:** 34 gates
**Gate-coverage meta-test:** `packages/contract-test-suite/tests/test_gate_coverage.py` — auto-discovers all `packages/*/src` and `services/*/src` directories and asserts each is covered by at least one gate's PYTHONPATH or the compileall gate's command paths.

### 10.2 Registration pattern for new packages

Following the established pattern (STATE.md V6):

1. **Add path variable** (line ~86 in `run_v2_gates.py`):
```python
skill_index_src = repo_root / "packages" / "skill-index" / "src"
```

2. **Add Gate() entry** (in the `_gates()` return tuple):
```python
Gate(
    "skill-index",
    (py, "-m", "unittest", "discover", "-s", "packages/skill-index/tests"),
    (skill_index_src, platform_src),
),
```

3. **Add to compileall gate** (line ~273):
```python
"packages/skill-index/src",
```

4. **Gate-coverage meta-test** auto-discovers the new `packages/skill-index/src` directory. If it's not in any gate's PYTHONPATH or compileall, the meta-test fails. Adding it to steps 1-3 satisfies the meta-test.

### 10.3 Gate baseline

The gate-coverage meta-test asserts `len(_gates()) >= 19` (line 60). Current count is 34. Adding one gate for skill-index brings it to 35.

---

## 11. Error Tolerance & Edge Cases

### 11.1 Discovered edge cases

| Edge case | Source | Impact | Scanner behavior |
|-----------|--------|--------|-----------------|
| plugin.json name ≠ directory name | ai-governance: `algorithm-filing-material-preparation` vs dir `filing-material-preparation` | Name collision when two parents have same child name | Use `path` field as authoritative; derive `name` from frontmatter or directory |
| Marketplace.json incomplete | legal-skills: 35 of 51 skills listed | 16 skills missing from marketplace | Use filesystem as source of truth, not marketplace.json |
| `.qwen/` internal skills | ai-for-china-legal: 7 SKILL.md in `.qwen/` | Not part of the 345 corpus | Exclude `.qwen/` from scan |
| `node_modules/` | ai-for-china-legal | Contains third-party files | Exclude `node_modules/` from scan |
| `_shared/` directories | 10+ plugins | Contain reference `.md` files, NOT skills | Skip `_shared/` directories (no SKILL.md inside) |
| `shared/` cross-cutting skills | 2 SKILL.md outside plugins | `research-gate` and `feedback-refinement` | Include in scan; `source_repo=ai-for-china-legal`, `plugin=shared` |
| Missing frontmatter | 0 currently | Future-proofing | Record with `name` from directory, `warnings: ["missing_frontmatter"]` |
| Missing plugin.json | 0 currently | Future-proofing | Scan directory tree directly, `warnings: ["missing_plugin_json"]` |
| Malformed YAML | 0 currently | Future-proofing | Record with raw text, `warnings: ["malformed_frontmatter"]` |

### 11.2 Graceful degradation principle

The scanner never crashes on upstream structure changes. Every error produces a warning record in the index. The `warnings` array in each skill record and the top-level `warnings` array in the index provide observability.

---

## 12. Index Format (skill-index.json)

### 12.1 Schema

```json
{
  "generated_at": "ISO-8601",
  "scanner_version": "1.0.0",
  "repos": {
    "ai-for-china-legal": {
      "path": "/home/sorawatcher/workspace/ai-for-china-legal",
      "commit": "<git SHA or null>",
      "skill_count": 345
    },
    "legal-skills": {
      "path": "/home/sorawatcher/workspace/legal-skills",
      "commit": "<git SHA or null>",
      "skill_count": 51
    }
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
      "child_skills": ["commercial-legal:risk-identification", "..."],
      "description": "...",
      "frontmatter": {
        "name": "contract-review",
        "description": "...",
        "argument-hint": "[合同文件路径或内容]"
      },
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
      "in-sync": [],
      "upstream-changed": [],
      "both-changed": [],
      "local-missing": []
    }
  },
  "warnings": []
}
```

### 12.2 Skill ID naming convention

| Repo | Pattern | Example |
|------|---------|---------|
| ai-for-china-legal (plugin skill) | `<plugin>:<skill-name>` | `commercial-legal:contract-review` |
| ai-for-china-legal (shared skill) | `shared:<skill-name>` | `shared:cn-law-research-gate` |
| legal-skills | `legal-<skill-name>` | `legal-court-sms` |

---

## 13. Package Structure (to be created)

```
packages/skill-index/
├── pyproject.toml
├── src/
│   └── inkstatute_skill_index/
│       ├── __init__.py
│       ├── scanner.py              # Directory tree walker, finds all SKILL.md
│       ├── frontmatter_parser.py   # YAML frontmatter extraction + validation
│       ├── metadata_extractor.py   # token_estimate, declared_gates, referenced_resources,
│       │                           # practice_profile_dependency, host_assumptions, required_scripts
│       ├── orchestration_classifier.py  # Three-way cross-validation
│       ├── conflict_model.py       # 4-state conflict classification
│       ├── index_builder.py        # Assembles skill-index.json
│       └── cli.py                  # CLI: python -m inkstatute_skill_index scan --repo <path> --output <path>
└── tests/
    ├── test_scanner.py             # Directory walking + SKILL.md discovery
    ├── test_frontmatter_parser.py  # YAML parsing + edge cases
    ├── test_orchestration_classifier.py  # Orchestration vs leaf classification
    ├── test_metadata_extractor.py  # Token estimation, gate/resource/script extraction
    ├── test_conflict_model.py      # 4-state conflict classification
    ├── test_read_only.py           # mtime + hash immutability assertion
    ├── test_index_builder.py       # Full index assembly + schema validation
    └── fixtures/                   # Minimal fixture SKILL.md files for unit tests
```

---

## 14. Key Findings Summary

1. **345 + 51 = 396 SKILL.md confirmed** — filesystem scan matches the PRD count exactly.

2. **73 orchestration entries, 323 leaf skills** — the PRD's "~60 / ~285" estimate is approximate; actual is 73 (all from ai-for-china-legal) + 323 (270 nested + 51 flat + 2 shared).

3. **Two distinct frontmatter schemas** — ai-for-china-legal has minimal (name, description, argument-hint); legal-skills has rich (name, version, license, author, homepage, description). Scanner must handle both.

4. **plugin.json is authoritative for ai-for-china-legal** (336 entries listing all skills with paths) but **marketplace.json is incomplete for legal-skills** (35 of 51). Scanner uses filesystem as source of truth.

5. **Name collision edge case** in ai-governance: `filing-material-preparation` exists under two parents. plugin.json disambiguates with `algorithm-filing-material-preparation`. Scanner must use `path` field, not `name`, as the identifier.

6. **Conflict model inherits from `sync_legal_skills.py`** — 4-state classification (in-sync / upstream-changed / both-changed / local-missing) plus 2 extra states (local-meta-only / missing-upstream). Phase 96 adapts to index level (read-only, no filesystem sync).

7. **Token estimation: CJK-aware heuristic** — `CJK_count × 1.0 + non_CJK_count / 4`. Sample range: 2,800–13,400 tokens. No external tokenizer needed.

8. **Read-only enforcement** — mtime + SHA-256 hash comparison before/after scan. Test runs in CI as part of the skill-index gate.

9. **Gate registration** — add `skill_index_src` path variable, `Gate("skill-index", ...)` entry, and `"packages/skill-index/src"` to compileall. Gate-coverage meta-test auto-discovers and enforces.

10. **`packages/skill-index` does not exist yet** — confirmed. New package to be created. `packages/skill-registry` (V2, manifest-based) remains as the runtime API; skill-index is the build-time scanner.

11. **`.qwen/` and `node_modules/` must be excluded** — 7 `.qwen/` SKILL.md files are internal tooling, not part of the 345 corpus.

12. **`_shared/` directories contain references, not skills** — no SKILL.md inside. Scanner skips them.

13. **Practice profile dependency is near-universal** in ai-for-china-legal (336/343 = 97.9% reference CLAUDE.md). All legal-skills have `practice_profile_dependency = false`.

14. **19 skills declare research-gate dependency** — the `declared_gates` field captures this for routing and guardrail enforcement.

15. **35 legal-skills have scripts/ directories** with 140 Python files total. The `required_scripts` field lists these for materialization (Phase 97).
