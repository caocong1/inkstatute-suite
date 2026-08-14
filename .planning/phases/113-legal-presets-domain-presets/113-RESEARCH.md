# Phase 113: Legal Presets & Domain Presets — Research

**Researched:** 2026-08-14
**Domain:** DSH preset format, legal domain presets, guardrail prompt segments, token budget enforcement, preset materialization
**Confidence:** HIGH (DSH preset architecture verified by source code inspection)

## Summary

Phase 113 creates the V4 capability layer shape: 5 legal domain presets (`legal-core` + 4 domains) under `presets/`, each with a `preset.yml` metadata file and an `agent.cordis.yml` composition that uses DSH's `standard` preset as a base, embeds the 6 guardrail prompt segments in the persona, removes `ask_user_question` (DP-1), and points `customSkillDirs` at the content package domain directories. A token budget gate enforces ≤8,000 characters for the core skill catalog rendering. A materialization script installs presets to `~/.agent-presets/<domain>/`.

## DSH Preset Format Reference

### Preset = directory with one `agent.cordis.yml`

A DSH agent preset is a directory containing a single `agent.cordis.yml` file. DSH ships 4 presets at `apps/cli/config/agent-presets/`:
- `standard` — full coding agent (persona + tools + skills + plan mode)
- `code` — PTC mode (code-focused)
- `cordis` — creative mode (self-modifying toolset)
- `minimal` — minimal agent

### Standard preset structure (`apps/cli/config/agent-presets/standard/agent.cordis.yml`)

The standard preset (251 lines) contains these plugin rows:
- `persona` (`@deepseek-ai/dsh-persona`) — agent identity text
- `agent-instructions` (`@deepseek-ai/dsh-agent-instructions`) — instruction injection point
- `tool-bash` / `tool-pwsh` — shell tools (platform-conditional)
- `tool-fs` / `tool-fs-search` — filesystem tools
- `skill-filesystem` (`@deepseek-ai/dsh-skill-filesystem`) — skill discovery from filesystem
- `tool-skill` (`@deepseek-ai/dsh-tool-skill`) — skill catalog + loader tool
- `tool-goal` — goal tool
- `planning` (group) — plan mode
- `tool-ralph` — subagent tool
- `tool-ask-user` (`@deepseek-ai/dsh-tool-ask-user`) — **MUST BE REMOVED for V4 (DP-1)**
- `tool-todo` — todo tool
- `tool-web` — web search tool

### Persona plugin (`packages/preset/persona/src/index.ts`)

The `@deepseek-ai/dsh-persona` plugin accepts a `text` config field:
```yaml
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: >-
      You are a coding agent powered by the {{model}} model. Your working directory is {{cwd}}.
```
`{{model}}` and `{{cwd}}` are resolved from the agent's route and workspace. V4 presets will embed the 6 guardrail segments in this text field.

### Preset metadata (`packages/preset/agent-presets/src/metadata.ts`)

Presets have metadata (name, description) separate from the composition. The `preset.yml` file carries this:
```yaml
name: legal-core
description: 精选核心法律技能集（≤30 技能）
```

### Preset discovery (`packages/preset/agent-presets/src/discovery.ts`)

DSH discovers presets from filesystem directories. The discovery scans trusted and user-authored roots. The `~/.agent-presets/` directory is the user root. V4 materialization installs presets there.

## customSkillDirs Configuration

### Skill filesystem plugin (`packages/skill/skill-filesystem/src/index.ts`)

The `@deepseek-ai/dsh-skill-filesystem` plugin accepts a `customSkillDirs` config field:
```typescript
customSkillDirs?: string[]
```
Default: `[]`. Each entry is resolved to an absolute path and scanned for SKILL.md files. Custom dirs get rank 300 (after project roots at rank 200, before user roots at rank 400).

V4 preset composition:
```yaml
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - ~/.agent-presets/legal-core/skills
      # Or per-domain: ~/.agent-presets/legal-commercial/skills
```

### Skill discovery

Each `customSkillDirs` entry is scanned for `SKILL.md` files with frontmatter:
```yaml
---
name: skill-name
description: One-line description
---
```
The catalog (name + description) is rendered into the model prefix as `<available_skills>`.

## ask_user_question Tool Removal (DP-1)

### Tool plugin (`packages/interaction/tool-ask-user/src/index.ts`)

The `@deepseek-ai/dsh-tool-ask-user` plugin registers the `ask_user_question` tool. In the standard preset it appears at line 237-238:
```yaml
- id: tool-ask-user
  name: '@deepseek-ai/dsh-tool-ask-user'
```

### V4 removal approach

V4 preset compositions **omit** the `tool-ask-user` row entirely. This removes the `ask_user_question` tool from the ACP session tool set. Clarification then goes through the `[CLARIFY: …]` convention text in the persona (DP-1).

### Test assertion

A test must assert that the `ask_user_question` tool does NOT appear in the ACP session tool set. This can be verified by:
1. Parsing the preset's `agent.cordis.yml` and asserting no `tool-ask-user` row
2. (Future) Driving a real ACP session and inspecting the tool catalog

## Token Budget Enforcement (SKL-07)

### DSH catalog rendering

The `@deepseek-ai/dsh-tool-skill` plugin renders the skill catalog into the model prefix. Each skill contributes its `name` + `description` to an `<available_skills>` block. DSH has a per-description cap (`catalogDescriptionMaxLength`, default 500 chars) but **no global catalog budget**.

### V4 budget gate (app-side)

InkStatute must enforce the total catalog budget app-side. The gate:
1. Scan the `customSkillDirs` for SKILL.md files
2. Parse frontmatter `name` + `description` for each
3. Sum the rendered length (name + separator + description + newline per skill)
4. Assert total ≤ budget (default 8,000 chars, configurable)
5. If over budget → red light, refuse to ship

### Implementation

A Dart utility in `apps/flutter_app/lib/presets/` (or a Python script in `scripts/`) that:
- Takes a preset directory and budget limit as input
- Scans `customSkillDirs` for SKILL.md files
- Parses YAML frontmatter
- Computes total rendered catalog length
- Returns pass/fail

A test in `apps/flutter_app/test/presets/` verifies:
- legal-core catalog ≤ 8,000 chars → green
- A synthetic 345-skill catalog → red (explicitly forbidden)
- Budget is configurable

### 345-skill full mount prohibition

The test suite must include an explicit assertion that mounting all 345 skills is forbidden. This is a negative regression test: if someone accidentally points `customSkillDirs` at the full corpus, the budget gate catches it.

## Guardrail Prompt Segments (PRD §7)

The 6 guardrail segments to embed in every preset's persona text:

| # | Guardrail | Prompt segment |
|---|-----------|----------------|
| 1 | research-gate | 结论前必须检索现行法规/司法解释，未检索不得结论。任何法律结论必须基于已检索的现行有效法律依据。 |
| 2 | citation audit | 输出引用必须标注来源状态：[verified]（已核实原文）、[retrieved]（已检索但未核实原文）、[unverified]（未检索）。未标注引用视为 unverified。 |
| 3 | ask-user | 关键事实缺失时不得起草，必须输出 `[CLARIFY: 缺失事实描述]` 块等待用户澄清。未澄清前任务锁定。 |
| 4 | de-AI polish | 终稿必须经过去 AI 腔润色：去除"综上所述""值得注意的是"等模板化表述，保持法律文书的专业简洁。 |
| 5 | human review | 高风险法律结论（定性建议、诉讼策略、合同实质条款）必须标注 `[HUMAN_REVIEW: 原因]`，该标记不可由模型自行移除。 |
| 6 | confidentiality | 涉及客户材料时必须提醒：上传内容将经 DeepSeek API 传输，请确认已脱敏。每次涉及客户材料的任务前输出一次性提醒。 |

Additional persona directive: "先经 skill 工具加载对应技能再动手" (load the relevant skill via the skill tool before acting).

## Materialization Script Design

### `scripts/materialize_presets.sh`

Purpose: Install `presets/<domain>/` to `~/.agent-presets/<domain>/` (read-only).

Design:
```bash
#!/usr/bin/env bash
set -euo pipefail
# Materialize presets/ to ~/.agent-presets/ (read-only, install-time only).
# The installed directory is read-only — all customization goes through
# the presets/ source in the repo, never by editing installed files.
# Upgrade = re-run this script (overwrites installed content atomically).

PRESETS_SRC="${PRESETS_SRC:-presets}"
DEST="${DEST:-$HOME/.agent-presets}"

for domain_dir in "$PRESETS_SRC"/*/; do
  domain=$(basename "$domain_dir")
  target="$DEST/$domain"
  # Atomic copy: stage to temp, then rename.
  staging=$(mktemp -d)
  cp -r "$domain_dir." "$staging/"
  chmod -R a-w "$staging"  # read-only discipline
  mkdir -p "$DEST"
  rm -rf "$target"
  mv "$staging" "$target"
done
```

### Read-only discipline

Installed preset files are marked read-only (`chmod -R a-w`). The script comment explicitly states:
- Installed files are read-only
- All customization goes through `presets/` source
- Upgrade = re-run the script (atomic overwrite)
- Never edit installed files directly

## Real Engine Smoke Test (Success Criterion #4)

### Reusing Phase 112 engine base

- `apps/flutter_app/packages/acp_client` — Dart ACP client for driving the session
- `apps/flutter_app/lib/engine/dsh_process.dart` — subprocess manager for spawning DSH
- `engines/dsh-pin.txt` — pinned DSH commit
- `engines/acp.cordis.yml` — ACP composition (may need a V4 preset variant)

### Smoke test approach

1. Create 2-3 minimal SKILL.md fixtures in a test skill directory
2. Create a test preset that points `customSkillDirs` at the test skill directory
3. Spawn DSH with the test preset
4. Drive `initialize` → `session/new` → `session/prompt` ("list available skills")
5. Assert the response contains the skill names from the fixtures
6. Assert `ask_user_question` is NOT in the tool catalog

### Limitation

This requires a real DSH build (or `tsx` source launch) and a mock LLM. Since Phase 112 only dry-ran the build script, this smoke test may need to use `tsx` source launch against the DSH repo at `/home/sorawatcher/deepseek-harness`. If the real engine smoke test is not feasible in the current environment, a structural test (parse preset YAML, assert fields) + mock ACP server test can substitute, with the real engine smoke deferred to Phase 119 Windows packaging.

## Risks

1. **Real engine smoke test feasibility** — Driving a real DSH session requires either a built engine or `tsx` source launch + mock LLM. If neither is available in the current environment, the smoke test falls back to structural + mock ACP verification, with real engine smoke deferred.
2. **Token budget measurement accuracy** — The app-side budget gate measures the catalog rendering length by parsing SKILL.md frontmatter. This is an approximation of what DSH actually renders (DSH may add formatting). The gate should be conservative (measure slightly larger than DSH's actual render).
3. **Preset format evolution** — DSH is pre-release; the preset format may change. Pinning the DSH commit (`engines/dsh-pin.txt`) mitigates this.
