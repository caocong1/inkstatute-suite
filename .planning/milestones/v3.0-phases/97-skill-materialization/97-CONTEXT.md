---
phase: 97
slug: skill-materialization
status: draft
created: 2026-08-09
skip_discuss: false
---

# Phase 97 — Skill Materialization

## Phase Goal

一份 skill 语料能被三种后端各自消费——平台建的是索引 + 物化器，而不是第四份 skill 拷贝

## Requirements

- **SKILL-05**: skill 物化器——把语料按每个后端期望的布局落地（Hermes profile / ACP agent skills / 自研 core），一份 skill 三处可用；宿主假设按目标后端改写
- **SKILL-06**: 元数据 / 正文 / 工具依赖三分离；正文按需注入且受上下文预算约束（实测正文 2K–20K token）
- **SKILL-09**: 废弃 `solutions/lawfirm/manifest.json` 的 4 条手写 skill 元数据作为 skill 源；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates

## Success Criteria

1. 物化器能把语料落到 Hermes profile 布局（symlink 优先、脚本类 copy），且 `hermes acp` 能加载物化产物中的 skill（实测验证，不是推断）
2. 物化器能把语料落到 ACP agent skills 布局，并按目标后端改写宿主假设（`/plugin:skill` → 自然语言触发、`ask_user` → `elicitation`）
3. 自研 core 路径不需物化——直接读索引 + 按需读正文
4. 元数据 / 正文 / 工具依赖三分离在代码中体现：路由只用索引，正文只在执行时按需注入，工具依赖由各后端各自满足
5. 正文注入受上下文预算约束——给定预算，注入器能在 2K–20K token 的 skill 正文中做出确定性取舍并记录被裁剪的部分
6. `solutions/lawfirm/manifest.json` 不再包含 4 条手写 skill 元数据；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates，且 `solution-loader` 与 `skill-registry` 的测试相应更新后全绿

## Codebase Scout Findings

### 1. Hermes Profile Layout (Production Reference)

**Location:** `/home/sorawatcher/.hermes/profiles/lawfirm/skills/`

**Current state:** 101 skill directories, mix of symlinks and copies:
- **68 symlinks** → `ai-for-china-legal/<plugin>/skills/<skill-name>/` (e.g., `commercial-contract-review` → `/home/sorawatcher/workspace/ai-for-china-legal/commercial-legal/skills/contract-review/`)
- **33 regular directories** (copies or local-only skills):
  - `legal-*` prefixed skills synced from `legal-skills` via `sync_legal_skills.py` (marked with `.sync_source = "legal-skills"`)
  - `lawfirm-local` skills (e.g., `ask-user-enforcement`, `wecom-template-card`) marked with `.sync_source = "lawfirm-local"`
  - Other local skills (e.g., `wechat-article-search`, `skillopt-runner`)

**Key pattern:** Hermes loads skills from `~/.hermes/profiles/<profile>/skills/<skill-name>/SKILL.md`. The production lawfirm profile uses **symlinks for ai-for-china-legal skills** (zero-copy, always current) and **copies for legal-skills** (with `.sync_source` marker and `LOCAL_CHANGELOG.md` for local modifications).

**Symlink naming convention:** `<plugin-prefix>-<skill-name>` (e.g., `commercial-contract-review`, `ai-governance-algorithm-filing`, `builder-hub-skill-discovery`). The plugin name is used as a prefix, with `legal-` for legal-skills entries.

**Hermes ACP integration:** `ACPBackendConfig.hermes_home` sets `HERMES_HOME` env var for the subprocess (adapter.py line 488). The `hermes acp` command picks up skills from `$HERMES_HOME/profiles/<profile>/skills/`.

### 2. ACP Agent Skills Layout

**ACP does not have a built-in "agent skills" directory concept in the same way Hermes does.** ACP agents receive their capabilities via `initialize` negotiation and `session/update` events. Skills are loaded by the agent itself (e.g., Hermes loads from its profile directory).

For ACP-speaking agents that support skill loading (Claude Code, Codex):
- **Claude Code:** loads skills from `.claude/skills/` or plugin directories with `.claude-plugin/plugin.json`
- **Codex:** loads from configured skill paths
- **General ACP:** the agent's own skill loading mechanism is opaque to the ACP client

**Materialization for ACP:** The materializer needs to produce a directory layout that the target ACP agent can consume. For Claude Code format (which both source repos already use), this means:
- Plugin directories with `.claude-plugin/plugin.json`
- Skill directories with `SKILL.md` files
- The host assumption rewriting happens at the SKILL.md content level, not the directory structure

### 3. solutions/lawfirm/manifest.json (The 4 Fake Skills)

**Location:** `solutions/lawfirm/manifest.json` (64 lines)

**Current contents:**
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
    {"name": "case_qa", "description": "...", "intent": "factual_qa", "required_tools": ["law_search"], "risk_level": "medium"},
    {"name": "contract_draft", "description": "...", "intent": "drafting", "required_tools": ["docx_writer"], "risk_level": "high"},
    {"name": "litigation_summary", "description": "...", "intent": "analysis", "required_tools": ["law_search"], "risk_level": "high"},
    {"name": "compliance_review", "description": "...", "intent": "review", "required_tools": ["law_search"], "risk_level": "medium"}
  ],
  "mcp": [{"name": "law_search", "transport": "stdio", "secret_ref": "LAW_SEARCH_TOKEN"}],
  "output_policy": {"allow_legal_conclusions": true, "require_citation": true, "redact_pii": true, "block_meta_leak": true},
  "eval": ["fixtures/case_qa_eval.json"],
  "default_adapter_config": {"backend_id": "hermes", "run_invocation_mode": "oneshot"},
  "secret_templates": ["HERMES_API_KEY", "LAW_SEARCH_TOKEN", "LAW_PAYMENT_TOKEN"],
  "industry_context": {"legal_domain": {"jurisdiction_scope": "CN", "high_risk_topics": [...], "human_review_required_for": [...]}}
}
```

**After SKILL-09 removal, manifest retains:**
- `solution_id`, `version`, `manifest_ref`, `metadata`
- `persona_ref`
- `mcp` (MCP tool configurations)
- `output_policy` (output boundary rules)
- `eval` (evaluation fixtures)
- `default_adapter_config` (backend selection)
- `secret_templates` (secret references)
- `industry_context` (legal-specific fields)
- **`skills` array is REMOVED** (or emptied)

**Tests that reference the 4 fake skills and need updating:**
- `packages/skill-registry/tests/test_registry.py` — `get_skill("lawfirm/case_qa")`, search by intent/risk_level
- `packages/skill-registry/tests/test_discovery.py` — loads from both manifests, expects 8 total skills
- `packages/skill-registry/tests/test_api.py` — `handle_get("/skills/lawfirm/case_qa")`
- `packages/skill-registry/tests/test_mapper.py` — `manifest_skill_to_descriptor` with `case_qa`
- `packages/router-service/tests/test_hybrid_strategy.py` — `lawfirm/compliance_review` descriptor
- `solutions/lawfirm/tests/test_lawfirm_solution.py` — manifest validation
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — `_render_skill_template` reads `metadata.get("skills")`

### 4. packages/skill-registry (V2, manifest-based)

**Location:** `packages/skill-registry/src/inkstatute_skill_registry/`

**Current data flow:**
1. `mapper.py` → `load_skills_from_manifests([manifest_paths])` → reads `data["skills"]` from each manifest JSON → converts to `NeutralSkillDescriptor` list
2. `registry.py` → `SkillRegistry(skills)` → provides `list_skills()`, `get_skill()`, `search()`
3. `discovery.py` → builds `/.well-known/agent-skills/index.json` from descriptor list
4. `api.py` → HTTP-like handler for skill queries

**After Phase 97:** The skill-registry should be able to consume the real skill-index.json (from Phase 96) instead of manifest fake data. The `mapper.py` needs a new function like `index_to_descriptors(skill_index)` that converts `IndexRecord` → `NeutralSkillDescriptor`. The manifest-based `load_skills_from_manifests` remains for backward compatibility but is no longer the primary skill source.

### 5. packages/router-service

**Location:** `packages/router-service/src/inkstatute_router_service/`

**Current state:**
- `strategies.py` — `RouterStrategy` enum: `RULE`, `SKILL`, `HYBRID`
- `service.py` — `RouterService` with `decide()`, `_decide_rule()`, `_decide_skill()`, `_decide_hybrid()`
- `classifier.py` — `classify_intent()` keyword/regex intent classification
- `legal_risk.py` — `LegalRiskAssessment`, `LegalRiskClassifierPort`
- `model_classifier.py` — `ModelClassifierPort` for LLM-based classification
- `tool_resolver.py` — tool resolution

**Phase 97 scope:** Router-service is NOT directly modified in Phase 97 (that's Phase 98: SKILL-07, SKILL-08). However, the materializer must produce output that the router CAN consume. The three-separation principle (criterion 4) means the router only uses index metadata, never skill bodies.

### 6. lawfirm-profile/scripts/ (Materialization Reference)

**sync_legal_skills.py** (382 lines):
- Syncs `legal-skills` → `~/.hermes/profiles/lawfirm/skills/` with `legal-` prefix
- Uses `shutil.copytree` for copies, creates `.sync_source` marker files
- 4-state conflict classification (in-sync / upstream-changed / both-changed / local-missing)
- This is the **existing materialization pattern for legal-skills → Hermes**

**build_skill_index.py** (~200 lines):
- Scans SKILL.md files under a root directory
- Produces a structured index for `router.py`
- Entry shape: `name`, `description`, `argument_hint`, `category`, `triggers`, `source`, `user_facing`, `is_orchestrator`, `path`
- This is the **pre-Phase-96 index builder** that Phase 96 replaced with `packages/skill-index`

**router.py** (498 lines):
- 11 strong-signal rules (court_sms, judgment_or_transcript, new_case, docx_contract_review, qa_extraction, polish_draft, ip_infringement, ip_filing, labor_dispute, compliance_system, opc_counsel)
- Rule-first matching with confidence scoring
- `gate_before` = ask-user-enforcement, `gate_after` = legal-de-ai-polish
- Phase 98 will port these rules; Phase 97 just needs to ensure materialized skills are consumable by this router pattern

### 7. Context Budget Injection

**Existing budget logic:** `packages/platform-runtime/src/platform_runtime/context_assembler.py`
- `ContextAssemblyBudgetError` — raised when protected context exceeds budget
- `budget_tokens` (default 2048), `chars_per_token` (default 4)
- `trim_strategy = "protected_then_feedback_memory_recent_artifact"` — deterministic trim order
- Trims sections in order: feedback → memory → recent → artifact, until under budget
- Records `estimated_tokens` and trimmed sections

**Phase 97 adaptation:** The skill body injector needs similar budget logic:
- Given a token budget and a skill body (2K–20K tokens), produce a trimmed body
- Deterministic trimming: preserve frontmatter + gates + first N sections, trim tail
- Record which sections were trimmed in a `trim_report`

### 8. Existing Materializer Pattern (solutions/lawfirm/)

**`hermes_materializer.py`** (213 lines):
- `LawfirmHermesMaterializer` class with `materialize(solution, output_dir)` method
- Produces 4 files: `SKILL.md.template`, `SAMPLE_PERSONA.md`, `tools.json`, `SANITIZATION_REPORT.md`
- Reads skills from `manifest.metadata.get("skills")` — the 4 fake skills
- Pre-flight sanitization scan (refuses secrets, raw payloads, etc.)
- This is a **solution-pack-level materializer** (V2 pattern), NOT a skill-corpus materializer

**Phase 97 distinction:** The Phase 97 materializer is fundamentally different:
- V2 materializer: manifest → sanitized Hermes profile bundle (4 fake skills)
- Phase 97 materializer: skill-index.json → per-backend skill layouts (389 real skills)
- The V2 materializer remains for solution-pack concerns (persona, MCP, output_policy)
- The Phase 97 materializer handles skill corpus materialization

### 9. Host Assumption Patterns in skill-index

**Current extraction** (`metadata_extractor.py` line 127-147):
- `_TRIGGER_PATTERN = r"/[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+"` — extracts `/plugin:skill` trigger patterns
- Also extracts `argument-hint` from frontmatter
- `ask-user-enforcement` is recognized as a gate pattern (line 58)

**Host assumptions that need rewriting for ACP:**
1. `/plugin:skill` trigger patterns (319 SKILL.md files have these) → natural language triggers for ACP agents that don't support slash commands
2. `ask_user` references → `elicitation` (ACP protocol's `elicitation/create`)
3. `CLAUDE.md` practice profile references → platform-side multi-tenant config (Phase 99 concern, but materializer should flag)

### 10. Three-Separation Principle

**Current state:** Not yet enforced in code. The skill-index (Phase 96) already separates:
- **Metadata:** `IndexRecord` with 21 fields (skill_id, name, description, token_estimate, declared_gates, etc.)
- **Body:** SKILL.md files remain in source repos (read-only vendoring)
- **Tools:** `required_scripts` field in index; actual tool satisfaction is per-backend

**Phase 97 enforcement:**
- The materializer produces metadata-only manifests for routing (no bodies)
- Skill bodies are read on-demand at execution time, subject to budget
- Tool dependencies (scripts/, MCP connectors) are satisfied by each backend independently

## Key Decisions (Auto-Selected)

### 1. Package Location: New `packages/skill-materializer/`

[auto] Q: "Where should the skill materializer code live?" → Selected: "New package `packages/skill-materializer/`" (recommended default)

**Rationale:** Phase 96 created `packages/skill-index` for scanning/indexing. Phase 97 creates a separate `packages/skill-materializer` for the materialization logic. This follows the package-per-concern pattern. The materializer consumes the skill-index output and produces per-backend layouts. Keeping them separate allows the indexer to remain a build-time tool while the materializer can be invoked at deploy time or runtime.

### 2. Hermes Materialization: Symlink-first, copy for scripts

[auto] Q: "Symlink vs copy for Hermes profile materialization?" → Selected: "Symlink for SKILL.md directories, copy for skills with scripts/" (matches production pattern)

**Rationale:** The production lawfirm profile already uses this exact pattern:
- 68 symlinks for ai-for-china-legal skills (zero-copy, always current with upstream)
- Copies for legal-skills (with `.sync_source` marker) because they have `scripts/` directories with Python files that may need local modifications
- The materializer replicates this pattern: `symlink(target_dir, profile_skills_dir / skill_name)` for skills without scripts, `copytree` for skills with scripts
- Symlinks are preferred because they maintain the read-only vendoring principle (no fourth copy)

### 3. ACP Materialization: Claude Code plugin format with host assumption rewriting

[auto] Q: "What layout for ACP agent skills?" → Selected: "Claude Code plugin format (already used by both source repos) with content-level host assumption rewriting"

**Rationale:** Both source repos already use the Claude Code plugin format (`.claude-plugin/plugin.json`, `SKILL.md`). For ACP agents that support this format (Claude Code, Codex), the materializer:
1. Creates a target directory with plugin structure
2. Symlinks or copies SKILL.md files (same symlink-first strategy)
3. Rewrites host assumptions in SKILL.md content:
   - `/plugin:skill` trigger patterns → natural language description (e.g., "When the user asks about contract review...")
   - `ask_user` → `elicitation` (ACP protocol term)
   - `CLAUDE.md` references → flagged as `practice_profile_dependency` (resolved in Phase 99)
4. Produces a manifest of rewrites for auditability

### 4. Self-built Core Path: No materialization, direct index + on-demand body reading

[auto] Q: "Does the self-built core need materialization?" → Selected: "No — direct index read + on-demand body read" (per success criterion 3)

**Rationale:** The self-built Python agent core (Phase 100+) reads `skill-index.json` directly for routing decisions and reads SKILL.md bodies on-demand at execution time. No materialization step is needed. This is the simplest path and avoids any copy. The core uses the index for metadata (routing, token estimates, gates) and reads the body from the source repo path when a skill is activated.

### 5. Three-Separation Enforcement: Materializer produces metadata-only routing manifests; bodies read on-demand

[auto] Q: "How to enforce metadata/body/tools separation in code?" → Selected: "Materializer outputs metadata-only manifests for routing; bodies are never copied to routing artifacts; tools are resolved per-backend"

**Rationale:**
- **Metadata:** The materializer produces a routing manifest (JSON) containing only index-level fields (skill_id, name, description, token_estimate, declared_gates, etc.). This is what the router consumes.
- **Body:** SKILL.md bodies remain in source repos. They are read on-demand at execution time via the source path recorded in the index. The body injector (criterion 5) reads from source, applies budget, and injects into the agent's context.
- **Tools:** `required_scripts` and MCP tool dependencies are listed in the index but satisfied by each backend independently. The materializer does not copy scripts; it records tool requirements for the backend to resolve.

### 6. Context Budget Injection: Section-priority deterministic trim with trim report

[auto] Q: "How to deterministically trim 2K-20K token skill bodies within budget?" → Selected: "Section-priority deterministic trim with trim report" (extends existing context_assembler pattern)

**Rationale:** The existing `context_assembler.py` already has a budget enforcement pattern:
- `budget_tokens`, `chars_per_token`, `trim_strategy`
- Trims sections in deterministic order until under budget
- Records estimated tokens and trimmed sections

Phase 97 adapts this for skill body injection:
1. Parse SKILL.md into sections (markdown headers `##`)
2. Assign priorities: frontmatter + description = protected; gates (research-gate, ask-user) = high; core instructions = medium; examples/appendices = low
3. Trim from lowest priority until under budget
4. Produce a `SkillBodyInjectionResult` with: injected_text, original_token_estimate, injected_token_estimate, trimmed_sections list, budget_used
5. Deterministic: same input + same budget → same output

### 7. manifest.json Cleanup: Remove `skills` array, keep all other fields

[auto] Q: "What exactly to remove from manifest.json?" → Selected: "Remove the `skills` array entirely; keep all other fields unchanged"

**Rationale:** Per SKILL-09 and PROJECT.md decision: "废弃 `solutions/lawfirm/manifest.json` 的 4 条手写 skill 元数据作为 skill 源；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates". The `skills` array is removed. The `eval` field references `fixtures/case_qa_eval.json` which may need updating or removal. The `default_adapter_config` remains. The `metadata.materialize_targets` remains.

**Test updates required:**
- `packages/skill-registry/tests/test_registry.py` — remove `case_qa` assertions, update to use skill-index data
- `packages/skill-registry/tests/test_discovery.py` — update expected skill count (8 → only demo_non_legal skills)
- `packages/skill-registry/tests/test_api.py` — remove `lawfirm/case_qa` endpoint test
- `packages/skill-registry/tests/test_mapper.py` — keep `manifest_skill_to_descriptor` tests (function still exists for backward compat) but remove lawfirm-specific assertions
- `packages/router-service/tests/test_hybrid_strategy.py` — update `compliance_review` fixture
- `solutions/lawfirm/tests/test_lawfirm_solution.py` — update manifest validation (no `skills` key)
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — `_render_skill_template` handles empty/missing skills array

### 8. Materialization API: Python API + CLI

[auto] Q: "What's the interface for the materializer?" → Selected: "Python API + CLI subcommand" (follows skill-index pattern)

**Rationale:** Following the Phase 96 pattern (`packages/skill-index` with `cli.py` and `__main__.py`):
- Python API: `from inkstatute_skill_materializer import materialize_hermes, materialize_acp, SkillBodyInjector`
- CLI: `python -m inkstatute_skill_materializer materialize --target hermes --index <path> --output <path>`
- CLI: `python -m inkstatute_skill_materializer inject-body --skill-id <id> --index <path> --budget <tokens>`

### 9. Host Assumption Rewriting: Pattern-based text transformation with audit log

[auto] Q: "How to rewrite host assumptions for ACP?" → Selected: "Pattern-based text transformation with audit log" (deterministic, testable)

**Rationale:** The rewriter applies deterministic regex-based transformations to SKILL.md body text:
1. `/plugin:skill` → natural language trigger (extract skill name from pattern, generate "When the user asks about <skill>...")
2. `ask_user` / `ask-user` → `elicitation` (ACP protocol term)
3. `CLAUDE.md` references → flagged but not rewritten (Phase 99 handles practice profiles)
4. Each rewrite is logged in a `rewrite_report` with: original_text, rewritten_text, rule_applied, location

The rewriter is:
- Deterministic (same input → same output)
- Auditable (every rewrite is logged)
- Reversible (the report allows reconstructing the original)
- Testable (fixture SKILL.md files with known patterns)

### 10. Test Strategy: Fixture-based + hermes acp --check verification

[auto] Q: "How to verify hermes acp can load materialized skills?" → Selected: "Fixture-based unit tests + integration test with `hermes acp --check`"

**Rationale:**
- Unit tests: fixture SKILL.md files → materialize → assert output structure, symlinks, rewrites
- Integration test: materialize to a temp profile directory → set `HERMES_HOME` → run `hermes acp --check` → assert OK
- The integration test requires Hermes to be installed (same as Phase 89's verification)
- If Hermes is not available in CI, the integration test is skipped with a clear message
- The `hermes acp --check` command verifies the profile is loadable, not that individual skills work

### 11. Gate Registration: New gate for skill-materializer

[auto] Q: "How to register the skill-materializer gate?" → Selected: "Add Gate() entry + add to gate-coverage paths" (follows Phase 96 pattern)

**Rationale:** Following the established pattern (STATE.md V6, Phase 96):
1. Add `skill_materializer_src` path variable
2. Add `Gate("skill-materializer", (py, "-m", "unittest", "discover", "-s", "packages/skill-materializer/tests"), (skill_materializer_src, ...))` 
3. Add `"packages/skill-materializer/src"` to the gate-coverage meta-test's path list
4. Add to compileall
5. Update gate count assertion (35 → 36)

## Key Files

### New Package to Create
- `packages/skill-materializer/` — New Python package
  - `src/inkstatute_skill_materializer/` — Main source
    - `__init__.py`
    - `hermes_materializer.py` — Hermes profile layout materializer (symlink-first, copy for scripts)
    - `acp_materializer.py` — ACP agent skills layout materializer (Claude Code plugin format + host assumption rewriting)
    - `host_assumption_rewriter.py` — Pattern-based text transformation (trigger patterns → natural language, ask_user → elicitation)
    - `body_injector.py` — Skill body injection with context budget (section-priority deterministic trim)
    - `three_separation.py` — Enforcement of metadata/body/tools separation (routing manifest producer)
    - `cli.py` — CLI entry point: `python -m inkstatute_skill_materializer materialize --target hermes|acp --index <path> --output <path>`
    - `__main__.py` — Module entry point
  - `tests/` — Test suite
    - `test_hermes_materializer.py` — Symlink creation, copy for scripts, profile layout
    - `test_acp_materializer.py` — Plugin format output, host assumption rewriting
    - `test_host_assumption_rewriter.py` — Pattern transformation rules + audit log
    - `test_body_injector.py` — Budget enforcement, section-priority trim, trim report
    - `test_three_separation.py` — Metadata-only manifest, no bodies in routing artifacts
    - `test_manifest_cleanup.py` — manifest.json skills array removal, test updates
    - `test_hermes_acp_integration.py` — Integration test with `hermes acp --check` (skip if Hermes unavailable)
    - `fixtures/` — Minimal fixture SKILL.md files for unit tests
  - `pyproject.toml` — Package configuration

### Existing Files to Modify
- `solutions/lawfirm/manifest.json` — Remove `skills` array (SKILL-09)
- `packages/skill-registry/src/inkstatute_skill_registry/mapper.py` — Add `index_to_descriptors()` function for skill-index consumption
- `packages/skill-registry/tests/test_registry.py` — Update tests for manifest without skills array
- `packages/skill-registry/tests/test_discovery.py` — Update expected skill counts
- `packages/skill-registry/tests/test_api.py` — Remove lawfirm/case_qa endpoint test
- `packages/skill-registry/tests/test_mapper.py` — Update lawfirm-specific assertions
- `packages/router-service/tests/test_hybrid_strategy.py` — Update compliance_review fixture
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — Handle empty/missing skills array
- `solutions/lawfirm/tests/test_lawfirm_solution.py` — Update manifest validation
- `scripts/run_v2_gates.py` — Add skill-materializer gate (35 → 36)
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — Update gate count assertion (35 → 36)

### Existing Files to Reference
- `packages/skill-index/src/inkstatute_skill_index/index_builder.py` — `SkillIndex`, `IndexRecord` (21 fields) — the input to the materializer
- `packages/skill-index/src/inkstatute_skill_index/metadata_extractor.py` — `_extract_host_assumptions()` (trigger patterns, argument-hint)
- `packages/platform-runtime/src/platform_runtime/context_assembler.py` — Budget enforcement pattern (lines 17, 84-85, 206-269)
- `lawfirm-profile/scripts/sync_legal_skills.py` — Existing materialization pattern for legal-skills → Hermes
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — `ACPBackendConfig.hermes_home` (line 94, 488) — how HERMES_HOME is set
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — V2 solution-pack materializer (reference, not directly reused)

### Source Repos (read-only materialization targets)
- `/home/sorawatcher/workspace/ai-for-china-legal/` — 338 SKILL.md (excluding .qwen/), 13 plugins
- `/home/sorawatcher/workspace/legal-skills/` — 51 SKILL.md, flat structure, 35 with scripts/

## Patterns Established

### Pattern 1: Materializer consumes skill-index, not source repos directly
The materializer reads `skill-index.json` (produced by Phase 96) to know what skills exist, their paths, token estimates, and host assumptions. It then reads source repo files (via paths in the index) to produce materialized output. This ensures the materializer and router share the same index as source of truth.

### Pattern 2: Symlink-first materialization
For Hermes and ACP targets, symlinks are preferred over copies to maintain the read-only vendoring principle. Copies are only used when the skill has `scripts/` directories (which may need local modifications) or when symlinks are not possible (cross-filesystem).

### Pattern 3: Host assumption rewriting is deterministic and auditable
Every rewrite is logged with original text, rewritten text, rule applied, and location. The rewrite report is produced alongside the materialized output for review.

### Pattern 4: Budget-constrained body injection
Skill bodies are injected on-demand with a token budget. The injector parses SKILL.md into sections, assigns priorities, and trims from lowest priority. The result includes a trim report for observability.

### Pattern 5: Three-separation enforced by output structure
- Routing manifest (JSON): metadata only, no bodies
- Skill bodies: remain in source repos, read on-demand
- Tool dependencies: listed in index, resolved per-backend
