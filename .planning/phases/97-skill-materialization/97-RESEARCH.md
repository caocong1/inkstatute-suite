# Phase 97 Research — Skill Materialization

**Phase:** 97 — Skill Materialization
**Created:** 2026-08-09
**Status:** Complete
**Requirements:** SKILL-05, SKILL-06, SKILL-09

---

## 1. Hermes Profile Layout

### 1.1 Hermes Installation & ACP Mode

**Hermes binary:** `/home/sorawatcher/.local/bin/hermes` (Hermes Agent v0.19.0)

**ACP verification:**
```
$ hermes acp --check
Hermes ACP check OK
```

The `hermes acp` subcommand starts Hermes in ACP mode for editor integration. It accepts `--check` (verify dependencies), `--setup`, `--setup-browser`, `--yes` flags. The ACP mode loads skills from the profile directory.

### 1.2 Profile Directory Structure

**Hermes home:** `~/.hermes/`
**Profile location:** `~/.hermes/profiles/<profile>/skills/<skill-name>/SKILL.md`

The production lawfirm profile is at `~/.hermes/profiles/lawfirm/skills/` and contains **101 skill directories** (excluding hidden files like `.curator_state`, `.hub`, `.usage.json`).

### 1.3 Symlink vs Copy Strategy (Production Pattern)

The production lawfirm profile uses a **mixed symlink/copy strategy**:

| Type | Count | Pattern | Example |
|------|-------|---------|---------|
| **Symlinks** | 68 | `→ /home/sorawatcher/workspace/ai-for-china-legal/<plugin>//skills/<skill>/` | `commercial-contract-review → .../commercial-legal//skills/contract-review/` |
| **Copies (legal-skills)** | ~20 | `legal-` prefixed, `.sync_source = "legal-skills"` marker | `legal-court-sms/` (regular directory) |
| **Copies (lawfirm-local)** | ~3 | `.sync_source = "lawfirm-local"` marker | `ask-user-enforcement/`, `wecom-template-card/` |
| **Other local** | ~10 | Regular directories, no marker | `document`, `feedback-collection`, `feedback-refinement` |

**Symlink naming convention:** `<plugin-prefix>-<skill-name>`
- `commercial-contract-review` (plugin=`commercial-legal`, skill=`contract-review`)
- `ai-governance-algorithm-filing` (plugin=`ai-governance`, skill=`algorithm-filing`)
- `builder-hub-skill-discovery` (plugin=`legal-builder-hub`, skill=`skill-discovery`)

**Copy naming convention for legal-skills:** `legal-<skill-name>`
- `legal-court-sms`, `legal-de-ai-polish`, `legal-contract-copilot`
- `.sync_source` marker file contains `"legal-skills\n"` or `"lawfirm-local\n"`

**Key observation:** Symlinks point to the source repo directly (zero-copy, always current). The double-slash in symlink targets (`commercial-legal//skills/`) is a cosmetic artifact of the symlink creation script — it works because POSIX collapses consecutive slashes.

### 1.4 HERMES_HOME Integration

The ACP adapter sets `HERMES_HOME` for the Hermes subprocess:

```python
# packages/acp-client/src/inkstatute_acp_client/adapter.py (line 487-488)
if self.config.hermes_home:
    env["HERMES_HOME"] = self.config.hermes_home
```

`ACPBackendConfig.hermes_home` (line 94) is a `str | None` field. When set, the subprocess inherits `HERMES_HOME` pointing to the profile directory. Hermes then loads skills from `$HERMES_HOME/profiles/<profile>/skills/`.

### 1.5 SKILL.md Format Expected by Hermes

Hermes expects each skill directory to contain a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: ask-user-enforcement
description: 全局强制 ask_user 模式...
---
```

The frontmatter `name` and `description` fields are the minimum required. Hermes uses these for skill discovery and activation. No `plugin.json` is needed at the profile level — the skill directory structure alone is sufficient.

---

## 2. ACP Agent Skills Layout

### 2.1 ACP Does Not Define a Skill Directory

ACP (Agent Client Protocol) does not have a built-in "agent skills" directory concept. ACP agents receive capabilities via `initialize` negotiation and `session/update` events. Skill loading is the agent's own responsibility — opaque to the ACP client.

### 2.2 Claude Code Plugin Format (Both Source Repos Use It)

Both source repos already use the Claude Code plugin format:

**ai-for-china-legal:**
```
<plugin>/
├── .claude-plugin/plugin.json    # name, version, description, author, skills[]
├── CLAUDE.md                     # Practice profile template
└── skills/
    └── <skill-name>/SKILL.md
```

**legal-skills:**
```
.claude-plugin/
├── plugin.json                   # Single plugin metadata (no skills[] array)
└── marketplace.json              # 35 plugins listed (incomplete vs 51 on disk)
skills/
└── <skill-name>/SKILL.md
```

### 2.3 Materialization for ACP Targets

For ACP-speaking agents that support Claude Code plugin format (Claude Code, Codex), the materializer produces:
1. A target directory with plugin structure (`.claude-plugin/plugin.json`)
2. Skill directories with `SKILL.md` files (symlink-first, same as Hermes)
3. Host assumption rewriting at the SKILL.md content level (not directory structure)

The directory layout is identical to Hermes — the difference is in **content rewriting** (host assumptions), not structure.

---

## 3. Host Assumption Rewriting Rules

### 3.1 `/plugin:skill` Trigger Patterns

**Prevalence:** 319 SKILL.md files in ai-for-china-legal contain `/<plugin>:<skill>` trigger patterns.

**Example from `commercial-legal/skills/contract-review/SKILL.md`:**
```markdown
| 1 | **risk-identification** | ... | `skills/contract-review/risk-identification/SKILL.md` | `/commercial-legal:risk-identification` |
```

The pattern appears in:
- Orchestration tables (sub-skill trigger commands)
- Standalone trigger examples: `/commercial-legal:risk-identification [合同]`
- Auto-load references: `由 /commercial-legal:contract-review 在检测到合同时自动加载`

**Rewriting rule for ACP:** `/plugin:skill` → natural language trigger description. The rewriter extracts the skill name from the pattern and generates a natural language equivalent (e.g., "When the user asks about risk identification..."). This is needed because ACP agents that don't support slash commands can't interpret `/commercial-legal:risk-identification`.

**Extraction pattern (from `metadata_extractor.py` line 122-124):**
```python
_TRIGGER_PATTERN: re.Pattern[str] = re.compile(
    r"/[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+"
)
```

### 3.2 `ask_user` → `elicitation`

**Prevalence in SKILL.md bodies:** 0 direct `ask_user` references in ai-for-china-legal SKILL.md files. The `ask_user` protocol is defined in `shared/inkstatute-integration/ASK-USER-PROTOCOL.md` and referenced by the `ask-user-enforcement` gate skill (which is a lawfirm-local skill, not in the source repos).

**However**, the `ask-user` / `ask_user` pattern IS detected by the metadata extractor's gate pattern (line 58):
```python
("ask-user-enforcement", ["ask-user", "ask_user", "澄清"]),
```

**ACP protocol mapping:** The platform already maps `elicitation/create` (ACP) ↔ `elicitation.requested` (unified event) in the ACP event bridge:
- `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/output_filter.py` line 324: `if method == "elicitation/create":`
- `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/reverse_mapping.py`: elicitation answer response handling

**Rewriting rule for ACP:** `ask_user` / `ask-user` → `elicitation` in SKILL.md body text. This aligns skill corpus terminology with the ACP protocol term. The rewriter performs a simple text substitution and logs each occurrence.

### 3.3 `CLAUDE.md` Practice Profile References

**Prevalence:** 336 SKILL.md files in ai-for-china-legal reference `CLAUDE.md`.

**Example:**
```markdown
**在阅读合同之前，读取实践配置文件 `commercial-legal/CLAUDE.md`。**
```

**Rewriting rule for ACP:** `CLAUDE.md` references are **flagged but not rewritten**. The rewriter logs them as `practice_profile_dependency` entries in the rewrite report. Phase 99 handles practice profile multi-tenant configuration.

### 3.4 Rewrite Report Structure

Each rewrite is logged with:
- `original_text` — the text before rewriting
- `rewritten_text` — the text after rewriting
- `rule_applied` — which rule triggered (`trigger_to_natural_language`, `ask_user_to_elicitation`, `claude_md_flag`)
- `location` — file path + line number (or section identifier)

The rewriter is:
- **Deterministic** — same input → same output (regex-based, no LLM)
- **Auditable** — every rewrite logged in the report
- **Reversible** — the report allows reconstructing the original
- **Testable** — fixture SKILL.md files with known patterns

---

## 4. solutions/lawfirm/manifest.json — The 4 Fake Skills

### 4.1 Current Structure (64 lines)

**Location:** `solutions/lawfirm/manifest.json`

**Full current contents:**
```json
{
  "solution_id": "lawfirm",
  "version": "1.0.0",
  "manifest_ref": "solutions/lawfirm/manifest.json",
  "metadata": {
    "materialize_targets": ["hermes"],
    "compatibility": "lawyer_pack_v1",
    "not_live_acceptance": true,
    "privacy_profile": "reference_first_only"
  },
  "persona_ref": "personas/lawfirm_persona.md",
  "skills": [
    {"name": "case_qa", "description": "Answer factual legal questions with citations.", "intent": "factual_qa", "required_tools": ["law_search"], "risk_level": "medium"},
    {"name": "contract_draft", "description": "Draft contract clauses with citation hooks.", "intent": "drafting", "required_tools": ["docx_writer"], "risk_level": "high"},
    {"name": "litigation_summary", "description": "Summarize case materials for litigation strategy.", "intent": "analysis", "required_tools": ["law_search"], "risk_level": "high"},
    {"name": "compliance_review", "description": "Review contract or policy for compliance issues.", "intent": "review", "required_tools": ["law_search"], "risk_level": "medium"}
  ],
  "mcp": [{"name": "law_search", "transport": "stdio", "secret_ref": "LAW_SEARCH_TOKEN"}],
  "output_policy": {"allow_legal_conclusions": true, "require_citation": true, "redact_pii": true, "block_meta_leak": true},
  "eval": ["fixtures/case_qa_eval.json"],
  "default_adapter_config": {"backend_id": "hermes", "run_invocation_mode": "oneshot"},
  "secret_templates": ["HERMES_API_KEY", "LAW_SEARCH_TOKEN", "LAW_PAYMENT_TOKEN"],
  "industry_context": {"legal_domain": {"jurisdiction_scope": "CN", "high_risk_topics": [...], "human_review_required_for": [...]}}
}
```

### 4.2 The 4 Hand-Written Skill Metadata Entries

| Skill | Intent | Required Tools | Risk Level |
|-------|--------|---------------|------------|
| `case_qa` | `factual_qa` | `law_search` | `medium` |
| `contract_draft` | `drafting` | `docx_writer` | `high` |
| `litigation_summary` | `analysis` | `law_search` | `high` |
| `compliance_review` | `review` | `law_search` | `medium` |

These are V2 fake data — completely unrelated to the 389 real skills indexed in Phase 96. They exist only to make `SolutionLoader` and `SkillRegistry` functional for testing.

### 4.3 What Remains After SKILL-09 Removal

After removing the `skills` array, manifest retains:

| Field | Content | Purpose |
|-------|---------|---------|
| `solution_id` | `"lawfirm"` | Solution identity |
| `version` | `"1.0.0"` | Version tracking |
| `manifest_ref` | path | Self-reference |
| `metadata` | materialize_targets, compatibility, etc. | Solution metadata |
| `persona_ref` | `"personas/lawfirm_persona.md"` | Persona template |
| `mcp` | law_search config | MCP tool configurations |
| `output_policy` | allow_legal_conclusions, require_citation, etc. | Output boundary rules |
| `eval` | `["fixtures/case_qa_eval.json"]` | Evaluation fixtures |
| `default_adapter_config` | backend_id, run_invocation_mode | Backend selection |
| `secret_templates` | HERMES_API_KEY, LAW_SEARCH_TOKEN, etc. | Secret references |
| `industry_context` | legal_domain config | Legal-specific fields |

**`skills` array is REMOVED entirely.**

### 4.4 How solution-loader and skill-registry Consume It

**solution-loader** (`packages/solution-loader/`):
- `DefaultSolutionLoader` reads manifest JSON → `SolutionPackageManifest`
- Extracts `solution_id`, `version`, `manifest_ref` as top-level fields
- Everything else (including `skills`) goes into `metadata` dict
- The `LawfirmHermesMaterializer._render_skill_template()` reads `manifest.metadata.get("skills", [])` (line 190)

**skill-registry** (`packages/skill-registry/`):
- `mapper.py` → `load_skills_from_manifests([manifest_paths])` reads `data["skills"]` from each manifest
- Converts each skill dict → `NeutralSkillDescriptor` via `manifest_skill_to_descriptor()`
- `registry.py` → `SkillRegistry(skills)` provides `list_skills()`, `get_skill()`, `search()`
- `discovery.py` → builds `/.well-known/agent-skills/index.json` from descriptor list
- `api.py` → HTTP-like handler for skill queries

### 4.5 demo_non_legal Manifest (Also Has 4 Fake Skills)

`solutions/demo_non_legal/manifest.json` also has 4 fake skills (`lesson_qa`, `homework_review`, `syllabus_lookup`, `quiz_generator`). These are used for composability testing (SAFE-06). After Phase 97, the skill-registry tests that load from both manifests expecting 8 total skills will need updating — only the 4 demo_non_legal skills will remain (lawfirm's 4 are removed).

---

## 5. packages/skill-registry — Current Consumption Pattern

### 5.1 Source Files

**Location:** `packages/skill-registry/src/inkstatute_skill_registry/`

| File | Lines | Purpose |
|------|-------|---------|
| `mapper.py` | 64 | Manifest skill dict → `NeutralSkillDescriptor` |
| `registry.py` | 87 | Read-only `SkillRegistry` with list/get/search |
| `discovery.py` | 81 | Builds `/.well-known/agent-skills/index.json` (RFC v0.2.0) |
| `api.py` | — | HTTP-like handler for skill queries |
| `write.py` | — | Write operations (separate from read-only registry) |
| `write_api.py` | — | Write API handler |

### 5.2 Data Flow

```
manifest.json → load_skills_from_manifests() → [NeutralSkillDescriptor]
                                                    ↓
                                              SkillRegistry(skills)
                                                    ↓
                                    list_skills() / get_skill() / search()
                                                    ↓
                                          build_discovery_index()
                                                    ↓
                                    /.well-known/agent-skills/index.json
```

### 5.3 mapper.py — The Key File for Phase 97

`load_skills_from_manifests()` (line 48-64):
```python
def load_skills_from_manifests(manifest_paths: list[Path]) -> list[NeutralSkillDescriptor]:
    skills: list[NeutralSkillDescriptor] = []
    for path in manifest_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        solution_id = data.get("solution_id", path.parent.name)
        for skill in data.get("skills", []):
            skills.append(manifest_skill_to_descriptor(solution_id, skill))
    return skills
```

**After Phase 97:** A new function `index_to_descriptors(skill_index)` needs to be added that converts `IndexRecord` (from skill-index) → `NeutralSkillDescriptor`. The manifest-based `load_skills_from_manifests` remains for backward compatibility but is no longer the primary skill source for lawfirm.

### 5.4 Tests That Reference the 4 Fake Skills

| Test File | References | What Needs Updating |
|-----------|-----------|---------------------|
| `test_registry.py` | `get_skill("lawfirm/case_qa")`, expects 8 total skills | Remove lawfirm assertions; update count to 4 (demo only) or use skill-index data |
| `test_discovery.py` | Loads from both manifests, expects 8 entries | Update expected count; lawfirm skills removed |
| `test_api.py` | `handle_get("/skills/lawfirm/case_qa")` | Remove lawfirm endpoint test |
| `test_mapper.py` | `manifest_skill_to_descriptor` with `case_qa` | Keep function tests (backward compat); remove lawfirm-specific assertions |

---

## 6. packages/router-service — Current Routing

### 6.1 Source Files

**Location:** `packages/router-service/src/inkstatute_router_service/`

| File | Purpose |
|------|---------|
| `strategies.py` | `RouterStrategy` enum: `RULE`, `SKILL`, `HYBRID` |
| `service.py` | `RouterService` with `decide()`, `_decide_rule()`, `_decide_skill()`, `_decide_hybrid()` |
| `classifier.py` | `classify_intent()` keyword/regex intent classification |
| `legal_risk.py` | `LegalRiskAssessment`, `LegalRiskClassifierPort` |
| `model_classifier.py` | `ModelClassifierPort` for LLM-based classification |
| `tool_resolver.py` | Tool resolution |

### 6.2 Three Strategies

- **RULE** — keyword/regex intent classification via `classify_intent()`. If registry is available, looks up skills by intent category. Falls back to `SIMPLE_QA` or `ZERO_MATCH`.
- **SKILL** — stateless Skill Registry lookup. Direct `skill_id` lookup via `get_skill()`, or message-based `search()`.
- **HYBRID** — Rule → Skill → Model cascade with confidence thresholds (≥0.8 matched, 0.5-0.8 clarify, <0.5 fallback) and legal-risk override (high-risk forced to Hermes).

### 6.3 How Router Currently Gets Skill Data

The router receives a `SkillRegistryPort` (Protocol) at construction:
```python
def __init__(self, skill_registry: "SkillRegistryPort | None" = None, ...):
```

When `skill_registry` is `None`, the router falls back to inline inference. When provided, it calls:
- `registry.search(category=intent)` — RULE strategy
- `registry.get_skill(skill_id)` — SKILL strategy
- `registry.search(name_substring=first_word)` — message-based search

### 6.4 Phase 97 Scope for Router

Router-service is **NOT directly modified** in Phase 97 (that's Phase 98: SKILL-07, SKILL-08). However:
- The materializer must produce output that the router CAN consume
- The three-separation principle means the router only uses index metadata, never skill bodies
- Tests referencing `lawfirm/compliance_review` and `lawfirm/case_qa` fixtures need updating

### 6.5 Router Tests Referencing Fake Skills

`packages/router-service/tests/test_hybrid_strategy.py` uses:
- `lawfirm/compliance_review` descriptor (lines 118, 356, 567)
- `lawfirm/case_qa` descriptor (lines 165, 537, 591)
- `lawfirm/contract_drafting` descriptor (line 190)

These are test fixtures created inline (not loaded from manifest), so they need fixture updates, not manifest changes.

---

## 7. Context Budget Injection

### 7.1 Existing Budget Logic

**Location:** `packages/platform-runtime/src/platform_runtime/context_assembler.py`

**Key classes:**
- `ContextAssemblyPolicy` (line 82-90): `budget_tokens=2048`, `chars_per_token=4`, `trim_strategy="protected_then_feedback_memory_recent_artifact"`
- `ContextAssemblyResult` (line 117-139): includes `estimated_tokens`, `dropped_sections`, `protected_sections`
- `ContextAssemblyBudgetError` (line 17): raised when protected context exceeds budget

**Trim algorithm (lines 237-276):**
1. Calculate `estimated_tokens` for the full bundle
2. While `estimated > budget_tokens`:
   - Iterate trim order: `feedback_correction_refs` → `memory_refs` → `recent_turn_refs` → `artifact_refs` → `active_task_refs`
   - Pop one item from the first non-empty section
   - Record in `dropped_sections`
   - Re-estimate
3. If still over budget after all trimming, raise `ContextAssemblyBudgetError`

**Token estimation (line 475-477):**
```python
def _estimate_tokens(event: Mapping[str, Any], policy: ContextAssemblyPolicy) -> int:
    chars_per_token = max(1, int(policy.chars_per_token))
    return math.ceil(_estimated_value_chars(event) / chars_per_token)
```

### 7.2 Phase 97 Adaptation for Skill Body Injection

The skill body injector needs similar budget logic, adapted for markdown SKILL.md content:

**Section-priority deterministic trim:**
1. Parse SKILL.md into sections (markdown headers `##`)
2. Assign priorities:
   - **Protected (never trimmed):** frontmatter + description + first section
   - **High priority:** gate sections (research-gate, ask-user-enforcement)
   - **Medium priority:** core instructions, orchestration tables
   - **Low priority:** examples, appendices, references
3. Trim from lowest priority until under budget
4. Produce `SkillBodyInjectionResult`:
   - `injected_text` — the trimmed body
   - `original_token_estimate` — full body token count
   - `injected_token_estimate` — trimmed body token count
   - `trimmed_sections` — list of `{section_name, priority, original_tokens, reason}`
   - `budget_used` — tokens consumed
5. **Deterministic:** same input + same budget → same output

### 7.3 Token Range Verification (from Phase 96 Research)

Phase 96 research confirmed the 2K-20K token range:

| Skill | Token Estimate |
|-------|---------------|
| git-batch-commit (legal-skills) | 2,822 |
| algorithm-filing (ai-for-china-legal) | 3,773 |
| filing-requirement-analysis | 6,614 |
| court-sms (legal-skills) | 9,056 |
| contract-copilot (legal-skills) | 10,636 |
| de-ai-polish (legal-skills) | 13,366 |

The CJK-aware heuristic: `token_estimate = (CJK_chars × 1.0) + (non_CJK_chars / 4)`

---

## 8. Three-Separation Principle (Metadata / Body / Tools)

### 8.1 Current State

The skill-index (Phase 96) already separates at the data level:
- **Metadata:** `IndexRecord` with 21 fields (skill_id, name, description, token_estimate, declared_gates, etc.)
- **Body:** SKILL.md files remain in source repos (read-only vendoring)
- **Tools:** `required_scripts` field in index; actual tool satisfaction is per-backend

### 8.2 Phase 97 Enforcement in Code

The materializer enforces three-separation through its output structure:

**1. Routing manifest (metadata only):**
- JSON file containing only index-level fields
- No skill bodies copied into routing artifacts
- Router consumes this for routing decisions

**2. Skill bodies (on-demand):**
- SKILL.md files remain in source repos
- Read on-demand at execution time via the source path in the index
- Body injector reads from source, applies budget, injects into agent context
- Never pre-copied into routing artifacts

**3. Tool dependencies (per-backend):**
- `required_scripts` and MCP tool dependencies listed in index
- Each backend satisfies them independently
- Materializer does NOT copy scripts; it records tool requirements for the backend to resolve

### 8.3 Enforcement Mechanism

- `three_separation.py` module produces the metadata-only routing manifest
- The manifest contains: `skill_id`, `name`, `description`, `token_estimate`, `declared_gates`, `host_assumptions`, `required_scripts`, `source_path` (for on-demand body reading)
- No `body` or `content` field in the routing manifest
- Tests assert: routing manifest does NOT contain skill body text

---

## 9. lawfirm-profile/scripts/sync_legal_skills.py — Existing Materialization Reference

### 9.1 Overview (382 lines)

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/sync_legal_skills.py`

**Purpose:** Syncs `legal-skills` upstream → `~/.hermes/profiles/lawfirm/skills/` with `legal-` prefix.

**CLI subcommands:**
- `status` — view sync state of all skills
- `sync` — apply upstream changes (only `upstream-changed`)
- `diff <name>` — show upstream vs local diff
- `list` — list synced skills

### 9.2 Key Functions

| Function | Purpose |
|----------|---------|
| `parse_frontmatter_version(text)` | Regex `^version:\s*["']?([0-9.]+)` extracts version |
| `parse_frontmatter_name(text)` | Regex `^name:\s*([^\n]+)` extracts name |
| `list_upstream_skills()` | `git ls-tree -d --name-only` on `skills/` directory |
| `list_local_skills()` | Scans for `legal-` prefixed dirs with `.sync_source` marker |
| `local_dir_name(skill_name)` | Namespace isolation: `de-ai-polish` → `legal-de-ai-polish` |
| `compare_skill(skill_name)` | 6-state conflict classification |
| `mark_as_synced(skill_name)` | Creates `.sync_source = "legal-skills"` marker file |

### 9.3 Conflict Classification (6 States)

| State | Condition | Action |
|-------|-----------|--------|
| `in-sync` | Content matches AND no local changelog | No action |
| `local-meta-only` | Content matches BUT has local changelog | Metadata-only local changes |
| `upstream-changed` | Content differs AND no local changelog | Auto-sync |
| `both-changed` | Content differs AND has local changelog | Conflict — human intervention |
| `local-missing` | Skill exists upstream but not locally | Auto-sync |
| `missing-upstream` | Skill exists locally but not upstream | Orphan — investigate |

### 9.4 Sync Operation (cmd_sync, lines 256-297)

For `upstream-changed` skills:
1. `git checkout origin/main -- skills/<skill>/` in upstream repo
2. `shutil.rmtree(dst)` — remove old local copy
3. `shutil.copytree(src, dst)` — copy from upstream to lawfirm profile
4. `mark_as_synced(skill, local_name)` — write `.sync_source` marker

### 9.5 Namespace Isolation Rule

```python
def local_dir_name(skill_name):
    if skill_name.startswith("legal-"):
        return f"legal-{skill_name}"  # keeps existing legal- prefix
    return f"legal-{skill_name}"
```

**Known quirk:** `legal-qa-extractor` → `legal-legal-qa-extractor` (doubles the prefix). The code comment says "保留" but the implementation doubles it.

### 9.6 Patterns to Reuse for Phase 97 Materializer

- **`.sync_source` marker** — identifies materialized skills and their origin
- **`shutil.copytree` for skills with scripts/** — copies are needed when local modification is possible
- **Conflict classification** — 4-state model already inherited by Phase 96's conflict_model.py
- **Namespace prefixing** — `legal-` prefix for legal-skills, `<plugin>-` prefix for ai-for-china-legal

**Key difference:** Phase 97 uses **symlinks first** (for skills without scripts), while sync_legal_skills.py always uses copies. This is because the production lawfirm profile already uses symlinks for ai-for-china-legal skills (zero-copy).

---

## 10. Self-Built Core Path — No Materialization

### 10.1 How It Works

The self-built Python agent core (Phase 100+) does NOT need materialization. It reads:

1. **`skill-index.json` directly** — for routing decisions (metadata only)
   - `IndexRecord` fields: skill_id, name, description, token_estimate, declared_gates, etc.
   - The core loads this at startup or on-demand

2. **SKILL.md bodies on-demand** — at execution time, when a skill is activated
   - The index record contains `relative_path` and `source_repo`
   - The core reads the SKILL.md from the source repo path
   - The body injector applies context budget trimming
   - The trimmed body is injected into the agent's context

### 10.2 API for On-Demand Body Reading

The core uses:
```python
# Pseudo-code for on-demand body reading
def read_skill_body(skill_id: str, index: SkillIndex, budget_tokens: int) -> SkillBodyInjectionResult:
    record = index.get(skill_id)  # IndexRecord
    source_path = resolve_source_path(record)  # absolute path to SKILL.md
    skill_text = Path(source_path).read_text(encoding="utf-8")
    injector = SkillBodyInjector(budget_tokens=budget_tokens)
    return injector.inject(skill_text)
```

The `SkillBodyInjector` (from `packages/skill-materializer/body_injector.py`) is shared between:
- The self-built core (on-demand reading)
- Any other consumer that needs skill body injection with budget

### 10.3 Why No Materialization for Self-Built Core

- The core is Python and can read files directly
- The index already contains all metadata needed for routing
- No need for a profile directory or plugin format
- No need for host assumption rewriting (the core understands `/plugin:skill` and `ask_user` natively)
- This is the simplest path — avoids any copy, maintains read-only vendoring

---

## 11. Existing V2 Materializer (solutions/lawfirm/)

### 11.1 hermes_materializer.py (213 lines)

**Location:** `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py`

**Purpose:** V2 solution-pack-level materializer. Produces a sanitized Hermes profile bundle with 4 files:
1. `SKILL.md.template` — lists all skills from manifest
2. `SAMPLE_PERSONA.md` — placeholder persona
3. `tools.json` — MCP + output_policy
4. `SANITIZATION_REPORT.md` — hash + refused items

**Key method:** `_render_skill_template()` (line 188-204):
```python
@staticmethod
def _render_skill_template(manifest: SolutionPackageManifest) -> str:
    skills = manifest.metadata.get("skills", []) if manifest.metadata else []
    chunks = []
    for skill in skills:
        chunks.append(_SKILL_TEMPLATE.format(...))
    if not chunks:
        chunks.append("(no skills declared in manifest)")
    return "\n".join(chunks)
```

This reads `metadata.get("skills")` — the 4 fake skills. After SKILL-09, this needs to handle empty/missing skills array gracefully (it already does: `if not chunks: chunks.append("(no skills declared in manifest)")`).

### 11.2 Phase 97 Distinction

| Aspect | V2 Materializer | Phase 97 Materializer |
|--------|----------------|----------------------|
| Input | manifest.json (4 fake skills) | skill-index.json (389 real skills) |
| Output | Sanitized Hermes profile bundle (4 files) | Per-backend skill layouts (Hermes profile / ACP plugin format) |
| Scope | Solution-pack concerns (persona, MCP, output_policy) | Skill corpus materialization |
| Symlink strategy | No (writes template files) | Yes (symlink-first for SKILL.md directories) |
| Host assumption rewriting | No | Yes (trigger patterns, ask_user, CLAUDE.md) |
| Body injection | No | Yes (budget-constrained) |

The V2 materializer **remains** for solution-pack concerns. The Phase 97 materializer handles skill corpus materialization. They are complementary, not replacements.

---

## 12. Gate Registration Pattern

### 12.1 Current Gate State (35 gates)

**Location:** `scripts/run_v2_gates.py`

Phase 96 added the `skill-index` gate (gate 35):
```python
skill_index_src = repo_root / "packages" / "skill-index" / "src"
Gate("skill-index",
     (py, "-m", "unittest", "discover", "-s", "packages/skill-index/tests"),
     (skill_index_src, platform_src)),
```

Gate count assertion in `packages/contract-test-suite/tests/test_audit_v2_requirements.py` (line 459):
```python
self.assertEqual(len(gate_names), 35)
```

### 12.2 Phase 97 Gate Registration

Following the Phase 96 pattern:
1. Add `skill_materializer_src` path variable
2. Add `Gate("skill-materializer", (py, "-m", "unittest", "discover", "-s", "packages/skill-materializer/tests"), (skill_materializer_src, ...))`
3. Add `"packages/skill-materializer/src"` to compileall paths
4. Add `"packages/skill-materializer/src"` to gate-coverage meta-test path list
5. Update gate count assertion: 35 → 36

---

## 13. Test Impact Analysis for SKILL-09 (manifest.json Cleanup)

### 13.1 Tests Requiring Updates

| Test File | Current Behavior | Required Change |
|-----------|-----------------|-----------------|
| `packages/skill-registry/tests/test_registry.py` | Expects 8 skills (4 lawfirm + 4 demo), `get_skill("lawfirm/case_qa")` | Remove lawfirm assertions; update count to 4 (demo only) or add skill-index data source |
| `packages/skill-registry/tests/test_discovery.py` | Expects 8 entries in discovery index | Update expected count; lawfirm skills removed |
| `packages/skill-registry/tests/test_api.py` | `handle_get("/skills/lawfirm/case_qa")` returns 200 | Remove lawfirm endpoint test or expect 404 |
| `packages/skill-registry/tests/test_mapper.py` | `manifest_skill_to_descriptor` with `case_qa` | Keep function test (backward compat); remove lawfirm-specific assertions |
| `packages/router-service/tests/test_hybrid_strategy.py` | Uses `lawfirm/compliance_review`, `lawfirm/case_qa` as inline fixtures | Update fixtures to use non-lawfirm skill IDs or skill-index IDs |
| `solutions/lawfirm/tests/test_lawfirm_solution.py` | `test_skills_use_neutral_descriptors` iterates `raw["skills"]` | Remove or skip this test when `skills` key is absent |
| `solutions/lawfirm/src/.../hermes_materializer.py` | `_render_skill_template` reads `metadata.get("skills")` | Already handles empty list; verify no crash on missing key |

### 13.2 Test Update Strategy

- **skill-registry tests:** Update to load from demo_non_legal manifest only (4 skills) for backward-compat tests. Add new tests for `index_to_descriptors()` function.
- **router-service tests:** Replace `lawfirm/compliance_review` fixtures with generic test IDs (e.g., `test/compliance_review`). These are inline fixtures, not manifest-loaded.
- **lawfirm solution tests:** Remove `test_skills_use_neutral_descriptors` or make it conditional on `skills` key existing.

---

## 14. Package Structure for packages/skill-materializer/

### 14.1 Source Modules

```
packages/skill-materializer/
├── pyproject.toml
├── src/
│   └── inkstatute_skill_materializer/
│       ├── __init__.py
│       ├── hermes_materializer.py        # Hermes profile layout (symlink-first, copy for scripts)
│       ├── acp_materializer.py           # ACP agent skills layout (Claude Code plugin format + rewriting)
│       ├── host_assumption_rewriter.py   # Pattern-based text transformation
│       ├── body_injector.py              # Skill body injection with context budget
│       ├── three_separation.py           # Metadata-only routing manifest producer
│       ├── cli.py                        # CLI: materialize --target hermes|acp --index <path> --output <path>
│       └── __main__.py                   # Module entry point
├── tests/
│   ├── test_hermes_materializer.py
│   ├── test_acp_materializer.py
│   ├── test_host_assumption_rewriter.py
│   ├── test_body_injector.py
│   ├── test_three_separation.py
│   ├── test_manifest_cleanup.py
│   ├── test_hermes_acp_integration.py    # Integration test with `hermes acp --check` (skip if unavailable)
│   └── fixtures/
│       └── minimal SKILL.md files for unit tests
```

### 14.2 Python API

```python
from inkstatute_skill_materializer import (
    materialize_hermes,      # Hermes profile layout materializer
    materialize_acp,         # ACP agent skills layout materializer
    SkillBodyInjector,       # Budget-constrained body injection
    HostAssumptionRewriter,  # Pattern-based text transformation
)
```

### 14.3 CLI

```bash
# Materialize to Hermes profile layout
python -m inkstatute_skill_materializer materialize --target hermes --index <path> --output <path>

# Materialize to ACP agent skills layout
python -m inkstatute_skill_materializer materialize --target acp --index <path> --output <path>

# Inject skill body with budget
python -m inkstatute_skill_materializer inject-body --skill-id <id> --index <path> --budget <tokens>
```

---

## 15. Key Files Reference

### New Package to Create
- `packages/skill-materializer/` — New Python package (see §14)

### Existing Files to Modify
- `solutions/lawfirm/manifest.json` — Remove `skills` array (SKILL-09)
- `packages/skill-registry/src/inkstatute_skill_registry/mapper.py` — Add `index_to_descriptors()` function
- `packages/skill-registry/tests/test_registry.py` — Update for manifest without skills array
- `packages/skill-registry/tests/test_discovery.py` — Update expected skill counts
- `packages/skill-registry/tests/test_api.py` — Remove lawfirm/case_qa endpoint test
- `packages/skill-registry/tests/test_mapper.py` — Update lawfirm-specific assertions
- `packages/router-service/tests/test_hybrid_strategy.py` — Update compliance_review fixture
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — Handle empty/missing skills array
- `solutions/lawfirm/tests/test_lawfirm_solution.py` — Update manifest validation
- `scripts/run_v2_gates.py` — Add skill-materializer gate (35 → 36)
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — Update gate count assertion (35 → 36)

### Existing Files to Reference (Read-Only)
- `packages/skill-index/src/inkstatute_skill_index/index_builder.py` — `SkillIndex`, `IndexRecord` (21 fields)
- `packages/skill-index/src/inkstatute_skill_index/metadata_extractor.py` — `_extract_host_assumptions()` (trigger patterns)
- `packages/platform-runtime/src/platform_runtime/context_assembler.py` — Budget enforcement pattern
- `lawfirm-profile/scripts/sync_legal_skills.py` — Existing materialization pattern
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — `ACPBackendConfig.hermes_home` (line 94, 487-488)
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — V2 solution-pack materializer

### Source Repos (Read-Only Materialization Targets)
- `/home/sorawatcher/workspace/ai-for-china-legal/` — 338 SKILL.md (excluding .qwen/), 13 plugins
- `/home/sorawatcher/workspace/legal-skills/` — 51 SKILL.md, flat structure, 35 with scripts/

---

## 16. Risk Assessment

### 16.1 Symlink Portability

Symlinks work on Linux/macOS but may not work on Windows or cross-filesystem. The materializer should:
- Try symlink first
- Fall back to copy if symlink fails (cross-filesystem, permissions)
- Log which strategy was used for each skill

### 16.2 Hermes ACP Integration Test Reliability

The integration test (`hermes acp --check`) requires Hermes to be installed. In CI without Hermes:
- Test should be skipped with a clear message
- Unit tests with fixture SKILL.md files provide coverage without Hermes

### 16.3 Host Assumption Rewriting Completeness

The regex-based rewriter is deterministic but may miss edge cases:
- `/plugin:skill` patterns inside code blocks (should they be rewritten?)
- `ask_user` in URLs or file paths (false positives)
- `CLAUDE.md` in non-practice-profile contexts

Mitigation: The rewrite report is auditable; false positives can be reviewed and the rules refined.

### 16.4 Manifest Cleanup Backward Compatibility

Removing the `skills` array from `manifest.json` may break:
- Any code that reads `manifest["skills"]` without checking for key existence
- The `LawfirmHermesMaterializer._render_skill_template()` already handles empty list
- The `load_skills_from_manifests()` already uses `data.get("skills", [])` (returns empty list)

**Verification:** All test updates must be done atomically with the manifest change to avoid transient failures.
