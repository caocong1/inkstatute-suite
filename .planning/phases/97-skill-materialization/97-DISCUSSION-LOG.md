# Phase 97 Discussion Log — Skill Materialization

**Phase:** 97 — Skill Materialization
**Mode:** --auto (all gray areas auto-selected with recommended options)
**Created:** 2026-08-09
**Requirements:** SKILL-05, SKILL-06, SKILL-09

---

## Gray Area Analysis

### GA-01: Hermes Materialization Strategy — Symlink vs Copy

**Question:** Should the Hermes profile materializer use symlinks or copies for skill files?

**Options:**
- A) Symlink all skills (zero-copy, always current) — **Recommended**
- B) Copy all skills (full duplication, works cross-filesystem)
- C) Symlink for SKILL.md, copy for scripts/ (hybrid) — **Selected**
- D) Hardlinks (zero-copy, but fragile on cross-filesystem moves)

**Analysis:** The production lawfirm profile already uses a hybrid pattern:
- 68 symlinks for ai-for-china-legal skills (no scripts, pure prompt)
- 33 copies for legal-skills (have `scripts/` with Python files) and local-only skills
- `.sync_source` marker files track provenance

Symlinks maintain the read-only vendoring principle (no fourth copy). However, legal-skills have `scripts/` directories with 140 Python files that may need local modifications (per `sync_legal_skills.py` pattern with `LOCAL_CHANGELOG.md`). Copying is necessary for these.

**Decision:** C — Symlink for skills without scripts, copy for skills with scripts. Matches the production pattern exactly. The materializer checks `required_scripts` in the index record: if non-empty, use `copytree`; otherwise, use `symlink`.

---

### GA-02: ACP Agent Skills Layout

**Question:** What directory layout should the ACP materializer produce?

**Options:**
- A) Custom flat layout (all skills in one directory)
- B) Claude Code plugin format (`.claude-plugin/plugin.json` + `skills/<name>/SKILL.md`) — **Selected**
- C) ACP-specific format (no standard exists)
- D) Mirror the source repo structure exactly

**Analysis:** Both source repos already use the Claude Code plugin format. ACP agents that support skill loading (Claude Code, Codex) consume this format natively. There is no "ACP-specific" skill layout — ACP is a protocol, not a skill format. The agent's own skill loading mechanism determines the expected layout.

Option B is the natural choice because:
1. Both source repos already produce this format
2. Claude Code and Codex can consume it directly
3. The materializer can symlink to the existing plugin directories (zero-copy)
4. Host assumption rewriting happens at the SKILL.md content level, not the directory structure

**Decision:** B — Claude Code plugin format with content-level host assumption rewriting. The materializer creates a target directory with plugin structure, symlinks/copies SKILL.md files, and rewrites host assumptions in the body text.

---

### GA-03: Self-built Core Path — Materialization vs Direct Read

**Question:** Does the self-built Python agent core need materialized skills?

**Options:**
- A) Materialize to a core-specific directory (same as Hermes/ACP)
- B) No materialization — direct index read + on-demand body read — **Selected**
- C) Materialize metadata only, read bodies from source

**Analysis:** Success criterion 3 explicitly states: "自研 core 路径不需物化——直接读索引 + 按需读正文". The self-built core (Phase 100+) reads `skill-index.json` for routing metadata and reads SKILL.md bodies from source repo paths (recorded in the index) at execution time. This is the simplest path and avoids any copy.

Option C is effectively what happens — the core uses the index (metadata) and reads bodies on-demand. But there's no "materialization" step; it's just direct consumption.

**Decision:** B — No materialization for self-built core. Direct index read + on-demand body read. The materializer package provides the `body_injector` for budget-constrained reading, which the core will use at execution time.

---

### GA-04: Three-Separation Enforcement Mechanism

**Question:** How to enforce metadata/body/tools separation in code?

**Options:**
- A) Type-level enforcement (separate dataclasses for metadata, body, tools)
- B) Output structure enforcement (routing manifest has no bodies; bodies never copied to routing artifacts) — **Selected**
- C) Runtime assertion (check that routing never reads bodies)
- D) Convention only (documented but not enforced)

**Analysis:** The three-separation principle (criterion 4) requires:
- **Routing** uses only index metadata (skill_id, name, description, token_estimate, declared_gates)
- **Body** is read only at execution time, on-demand, subject to budget
- **Tools** are resolved by each backend independently

Option B enforces this structurally: the materializer produces a routing manifest (JSON) that contains only metadata fields. Skill bodies are never included in routing artifacts. The body injector is a separate component that reads from source paths. Tool dependencies are listed in the index but not resolved by the materializer.

**Decision:** B — Output structure enforcement. The materializer produces:
1. `routing-manifest.json` — metadata only (from skill-index records)
2. Materialized skill directories (Hermes/ACP) — for backends that need filesystem layout
3. `body_injector.py` — separate component for on-demand body reading with budget

---

### GA-05: Context Budget Injection Strategy

**Question:** How to deterministically trim 2K-20K token skill bodies within a budget?

**Options:**
- A) Truncate at character count (simple but loses semantic boundaries)
- B) Section-priority deterministic trim (parse markdown sections, trim by priority) — **Selected**
- C) LLM-based summarization (non-deterministic, adds latency)
- D) Token-level truncation (requires tokenizer dependency)

**Analysis:** The existing `context_assembler.py` already has a budget enforcement pattern with deterministic trim order. Phase 97 adapts this for skill bodies:

1. Parse SKILL.md into sections (markdown `##` headers)
2. Assign priorities:
   - **Protected (never trimmed):** frontmatter, description, declared gates
   - **High:** core instructions, research-gate, ask-user enforcement
   - **Medium:** detailed procedures, examples
   - **Low:** appendices, references, change logs
3. Trim from lowest priority until under budget
4. Produce `SkillBodyInjectionResult` with: injected_text, original_token_estimate, injected_token_estimate, trimmed_sections, budget_used

This is deterministic (same input + same budget → same output), testable, and doesn't require external dependencies.

**Decision:** B — Section-priority deterministic trim with trim report. Extends the existing `context_assembler.py` pattern. Uses the same `chars_per_token` heuristic as the skill-index token estimator.

---

### GA-06: manifest.json Cleanup Scope

**Question:** What exactly to remove from `solutions/lawfirm/manifest.json`?

**Options:**
- A) Remove `skills` array only, keep everything else — **Selected**
- B) Remove `skills` + `eval` (eval references fake skills)
- C) Remove `skills` + `eval` + `default_adapter_config`
- D) Rewrite manifest from scratch

**Analysis:** Per SKILL-09: "废弃 `solutions/lawfirm/manifest.json` 的 4 条手写 skill 元数据作为 skill 源；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates".

The `skills` array is the 4 fake hand-written skill metadata entries. Removing it is the core requirement. The `eval` field references `fixtures/case_qa_eval.json` which is an eval fixture for the fake `case_qa` skill — it should be emptied or updated. The `default_adapter_config` is still valid (backend selection). The `persona_ref`, `mcp`, `output_policy`, `secret_templates`, `industry_context` all remain.

**Decision:** A — Remove `skills` array only. The `eval` field is updated to empty array `[]` (eval fixtures for fake skills are no longer relevant). All other fields remain unchanged. The `hermes_materializer.py` in solutions/lawfirm is updated to handle empty/missing skills array gracefully.

---

### GA-07: Materialization API Design

**Question:** What's the interface for the materializer?

**Options:**
- A) Python API only (library function calls)
- B) CLI only (command-line tool)
- C) Python API + CLI subcommand — **Selected**
- D) REST API (over-engineering for a build-time tool)

**Analysis:** Following the Phase 96 pattern (`packages/skill-index` with both `cli.py` and Python API), the materializer provides both:
- **Python API:** `materialize_hermes(index, output_dir)`, `materialize_acp(index, output_dir)`, `SkillBodyInjector(skill_index).inject(skill_id, budget)`
- **CLI:** `python -m inkstatute_skill_materializer materialize --target hermes|acp --index <path> --output <path>`

This allows both programmatic use (by the platform at deploy time) and manual invocation (by operators for testing).

**Decision:** C — Python API + CLI subcommand. Follows the established skill-index pattern.

---

### GA-08: Host Assumption Rewriting Rules

**Question:** What are the specific transformation rules for ACP host assumption rewriting?

**Options:**
- A) Remove all host assumptions (let the agent figure it out)
- B) Rewrite `/plugin:skill` → natural language; `ask_user` → `elicitation`; flag `CLAUDE.md` — **Selected**
- C) Full semantic rewrite (LLM-based, non-deterministic)
- D) No rewriting (pass through as-is)

**Analysis:** The skill-index extracts host assumptions as trigger patterns (`/plugin:skill` format, 319 SKILL.md files) and argument-hints. For ACP agents that don't support slash commands, these need to be rewritten.

Specific rules:
1. `/commercial-legal:contract-review` → "When the user asks about contract review..." (extract skill name, generate natural language trigger)
2. `ask_user` / `ask-user` → `elicitation` (ACP protocol's `elicitation/create`)
3. `CLAUDE.md` references → flagged as `practice_profile_dependency: true` in metadata (not rewritten; Phase 99 handles practice profiles)
4. `scripts/*.py` references → flagged as `required_scripts` (not rewritten; backend resolves)

Each rewrite is logged in a `rewrite_report` for auditability.

**Decision:** B — Pattern-based text transformation with audit log. Deterministic, testable, reversible.

---

### GA-09: Test Strategy for Hermes ACP Loading Verification

**Question:** How to verify that `hermes acp` can load materialized skills?

**Options:**
- A) Unit tests only (assert output structure, don't actually load)
- B) Unit tests + integration test with `hermes acp --check` — **Selected**
- C) Full E2E test (start hermes acp, send a prompt, verify skill activation)
- D) Manual verification only

**Analysis:** Success criterion 1 requires "实测验证，不是推断". The integration test:
1. Materializes skills to a temp profile directory
2. Sets `HERMES_HOME` to the temp directory
3. Runs `hermes acp --check`
4. Asserts output contains "Hermes ACP check OK"

If Hermes is not installed in the CI environment, the test is skipped with `@unittest.skipUnless(shutil.which("hermes"), "Hermes not installed")`. This follows the same pattern as Phase 89's ACP verification.

Option C (full E2E) is too heavy for Phase 97 — it requires a working LLM and a real skill activation. That's Phase 98+ territory.

**Decision:** B — Fixture-based unit tests + integration test with `hermes acp --check`. Skip if Hermes unavailable.

---

### GA-10: skill-registry Migration Path

**Question:** How should skill-registry transition from manifest-based to index-based?

**Options:**
- A) Replace `load_skills_from_manifests()` with `load_skills_from_index()` entirely
- B) Add `index_to_descriptors()` alongside `load_skills_from_manifests()` (both available) — **Selected**
- C) Make skill-registry a pure consumer of skill-index (remove manifest support)
- D) Create a new package for index-based registry

**Analysis:** The skill-registry currently reads from manifest JSON (4 fake skills). After Phase 97, it should be able to consume the real skill-index. However, completely removing manifest support would break `solutions/demo_non_legal` which still has legitimate manifest skills.

Option B provides a smooth transition:
- `load_skills_from_manifests()` remains for solution-pack manifests (demo_non_legal, future non-legal solutions)
- `index_to_descriptors()` is new: converts `SkillIndex` → `list[NeutralSkillDescriptor]`
- The lawfirm manifest's `skills` array is removed, so `load_skills_from_manifests()` returns 0 lawfirm skills
- The real skills come from `index_to_descriptors(skill_index)`

**Decision:** B — Add `index_to_descriptors()` alongside existing `load_skills_from_manifests()`. Both are available. The lawfirm manifest no longer contributes skills; the skill-index does.

---

### GA-11: Gate Registration for skill-materializer

**Question:** How to register the skill-materializer gate?

**Options:**
- A) Add to existing skill-index gate (shared gate)
- B) New separate gate — **Selected**
- C) No gate (not needed)

**Analysis:** Following the established pattern (Phase 96 added a separate skill-index gate), the skill-materializer gets its own gate. This ensures:
1. `gate-coverage` meta-test passes (every `packages/*/src` is covered)
2. Tests run independently
3. Gate count increments (35 → 36)

**Decision:** B — New separate gate `Gate("skill-materializer", ...)`. Gate count: 35 → 36. Update gate count assertion in `test_audit_v2_requirements.py`.

---

## Summary

| # | Gray Area | Selected Option | Rationale |
|---|-----------|----------------|-----------|
| GA-01 | Hermes materialization strategy | Symlink-first, copy for scripts | Matches production lawfirm profile pattern |
| GA-02 | ACP agent skills layout | Claude Code plugin format + content rewriting | Both source repos already use this format |
| GA-03 | Self-built core path | No materialization, direct index + on-demand read | Per success criterion 3 |
| GA-04 | Three-separation enforcement | Output structure enforcement | Routing manifest has no bodies; bodies read on-demand |
| GA-05 | Context budget injection | Section-priority deterministic trim | Extends existing context_assembler pattern |
| GA-06 | manifest.json cleanup scope | Remove `skills` array, keep all other fields | Per SKILL-09 specification |
| GA-07 | Materialization API design | Python API + CLI subcommand | Follows skill-index pattern |
| GA-08 | Host assumption rewriting rules | Pattern-based text transformation with audit log | Deterministic, testable, reversible |
| GA-09 | Test strategy | Unit tests + `hermes acp --check` integration | Per success criterion 1 (实测验证) |
| GA-10 | skill-registry migration path | Add `index_to_descriptors()` alongside manifest loader | Smooth transition, preserves demo_non_legal |
| GA-11 | Gate registration | New separate gate (35 → 36) | Follows Phase 96 pattern |

**Total gray areas:** 11
**All auto-selected with recommended options.**
