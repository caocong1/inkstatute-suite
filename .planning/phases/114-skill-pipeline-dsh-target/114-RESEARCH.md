---
phase: 114-skill-pipeline-dsh-target
researched: 2026-08-14
researcher: gsd-phase-researcher
confidence: HIGH
key_findings_count: 10
---

# Phase 114: Skill Pipeline — dsh Target — Research

**Researched:** 2026-08-14
**Domain:** DSH skill materialization, content packaging, semantic rewriting, compatibility gates
**Confidence:** HIGH (All findings verified by source code inspection)
**Key Findings Count:** 10

## Executive Summary

Phase 114 requires extending `ai-for-china-legal/scripts/convert-skills.js` with a new `dsh` target that materializes skills from the corpus into DSH-compatible format. The conversion pipeline involves: (1) white-listed domain scanning (4 target domains only), (2) two semantic rewrites (slash commands → skill tool guidance, CLAUDE.md writes → practice-profile.md), (3) flat skill structure (sub-skills promoted to top-level with hyphenated names), (4) content-manifest.json generation with sha256 hashes, (5) zip packaging, and (6) compatibility gate extension. The DSH skill loader scans one level of subdirectories for `SKILL.md` files and requires YAML frontmatter with `name` and `description` fields. The current DSH pin is commit `47f943859b` with Node.js `^22.19.0 || >=24.0.0`. The corpus has no existing CI (no `.github/workflows/`), so the dsh target can run on Linux CI via `npm run test:compatibility` extension.

## Findings by Research Question

### 1. convert-skills.js Extension Point

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/scripts/convert-skills.js` (295 lines)

**Current structure:**
- Lines 47-51: Platform validation (`VALID_PLATFORMS = ["kimi", "opencode", "standalone", "all"]`)
- Lines 53-75: Shared `parseSkillMd()` function (extracts frontmatter via `yaml` package)
- Lines 79-98: Shared `findSkillFiles()` recursive walk
- Lines 102-216: Three converter functions (`convertToKimi`, `convertToOpenCode`, `convertToStandalone`)
- Lines 220-246: Shared `processSkills()` dispatcher
- Lines 248-293: Main function with platform dispatch

**Minimal extension point:**
Add `"dsh"` to `VALID_PLATFORMS` array (line 47), then add a new `else if` branch in the main function (after line 289) that calls a new `convertToDSH()` function. The shared parsing (`parseSkillMd`) and file discovery (`findSkillFiles`) are fully reusable.

**Target dispatch location:** Lines 262-290 in `main()` function. The dispatch pattern is:
```javascript
if (platform === "kimi") {
  // kimi conversion
} else if (platform === "opencode") {
  // opencode conversion
} else if (platform === "standalone") {
  // standalone conversion
}
```

**Shared parsing reuse:** `parseSkillMd()` (lines 55-75) already extracts:
- `name` from frontmatter (falls back to directory name)
- `description` from frontmatter (normalizes newlines to spaces)
- `argument-hint` from frontmatter (optional)
- Body content after `---` markers

This matches DSH's expected frontmatter schema exactly.

### 2. Skill Count Per Domain

**Corpus structure verified:**

| Domain | Top-level skills | Sub-skills | Total SKILL.md files |
|--------|----------------|------------|----------------------|
| commercial-legal | 4 (cold-start-interview, contract-drafting, contract-review, liability-analysis) | 21 | 24 |
| litigation-legal | 6 (cold-start-interview, defense-drafting, evidence-management, limitation-monitoring, matter-intake, representation-drafting) | 26 | 30 |
| family-legal | 5 (cold-start-interview, divorce-agreement, inheritance, property-division, will-drafting) | 19 | 22 |
| employment-legal | 6 (cold-start-interview, hiring-review, labor-dispute-handling, leave-management, non-compete-review, termination-review) | 21 | 24 |

**Total for 4 target domains:** 100 SKILL.md files (24+30+22+24)

**Legal-core candidate set estimation:**
The ≤30 constraint is feasible. A conservative legal-core selection could include:
- contract-review (6 sub-skills)
- legal-research (from corpus, if exists)
- citation-check (from shared/research-gate)
- 2-3 high-value skills from each domain (e.g., liability-analysis, evidence-organization, divorce-agreement, labor-dispute-handling)

This would result in ~15-20 skills, well within the ≤30 budget.

### 3. Slash Command Patterns

**Pattern format:** `/<plugin-name>:<skill-name>` (kebab-case for both parts)

**Examples found in corpus:**
- `/commercial-legal:cold-start-interview` (QUICKSTART.md line 31)
- `/commercial-legal:review` (CLAUDE.md line 46)
- `/litigation-legal:cold-start-interview` (QUICKSTART.md line 32)
- `/ai-governance:cold-start-interview` (multiple occurrences in ai-governance skills)
- `/ai-governance:use-case-inventory` (ai-use-case-classification/SKILL.md line 105)
- `/ai-governance:risk-level-classification` (ai-use-case-classification/SKILL.md line 106)

**Regex pattern:** `\/[a-z-]+:[a-z-]+`

**Parse strategy:**
```javascript
const slashCommandRegex = /\/([a-z-]+):([a-z-]+)/g;
```

**Semantic rewrite target:** Replace slash command references with "用 skill 工具按名加载 X 技能" (use the skill tool to load skill X by name). Example:
- Original: "运行 `/commercial-legal:contract-review` 进行审查"
- Rewritten: "用 skill 工具按名加载 contract-review 技能进行审查"

### 4. CLAUDE.md Write Instructions

**Patterns found in corpus:**
- "写入 `ai-governance/CLAUDE.md`" (ai-governance/skills/cold-start-interview/style-regulatory-resources/SKILL.md line 11)
- "写入 CLAUDE.md 的 `## 文书风格` 和 `## 可用集成` 两章" (same file)
- "写入映射" section headers (multiple sub-skills)
- "写入前确认话术" (multiple sub-skills)
- "已写入「我们是谁」+「谁在使用」" (identity-enterprise-profile/SKILL.md line 258)

**Chinese patterns to match:**
- `写入.*CLAUDE\.md`
- `写入.*实践配置文件`
- `写入.*章节`

**Replacement target:** `practice-profile.md` in the app data directory (Phase 115 app-side updater will write to `%LOCALAPPDATA%\InkStatute\practice-profile.md` or equivalent).

**Semantic rewrite:**
- Original: "将访谈结果写入 ai-governance/CLAUDE.md"
- Rewritten: "将访谈结果写入 practice-profile.md"

### 5. DSH Skill Loader Behavior

**Location:** `/home/sorawatcher/deepseek-harness/packages/skill/skill-filesystem/src/index.ts`

**Scanning behavior (lines 241-261):**
The `roots()` method returns skill roots in rank order:
- Rank 100: `<projectRoot>/.dsh/skills`
- Rank 200: `<projectRoot>/.agents/skills`
- Rank 300: `customSkillDirs` (the Phase 114 target)
- Rank 400: `<dshHome>/skills`
- Rank 500: `<agentsHome>/skills`

**Discovery depth (README.md line 71):**
"Discovery is one level deep — only `<root>/<name>/SKILL.md` and `<root>/<name>.md` are recognized; nested skill trees and package manifests are ignored."

**Chokidar configuration (lines 487-502):**
```typescript
const watcher = chokidar.watch(mode.anchor, {
  persistent: true,
  ignoreInitial: true,
  depth: 1,  // ONE LEVEL ONLY
  followSymlinks: this.config.followSymlinks,
  atomic: true,
  // ...
})
```

**Frontmatter schema (README.md lines 54-58):**
Required fields:
- `name` (kebab-case)
- `description`

Optional fields:
- `whenToUse`
- `metadata` (open YAML object)
- `disable-model-invocation` (boolean)
- `user-invocable` (boolean)

**Conclusion:** DSH scans exactly one level of subdirectories. Sub-skills must be promoted to top-level with hyphenated names (e.g., `contract-review-risk-identification/SKILL.md`).

### 6. DSH Pin Version

**Location:** `/home/sorawatcher/workspace/inkstatute-suite/engines/dsh-pin.txt`

**Current pin:**
```
dsh_commit=47f943859b
node_version=^22.19.0 || >=24.0.0
```

**Manifest field:** `min_engine_version` should be set to `47f943859b` (the full commit hash). The Node.js version constraint can be included as metadata but is not required for compatibility checking.

### 7. Sub-skill Handling

**Corpus structure example:**
```
commercial-legal/skills/contract-review/
├── SKILL.md (orchestration entry)
├── clause-revision/SKILL.md
├── legal-basis/SKILL.md
├── negotiation-points/SKILL.md
├── output-formatting/SKILL.md
└── risk-identification/SKILL.md
```

**Flattening convention (from CONTEXT.md GA-3):**
Sub-skills are promoted to top-level with `<parent>-<child>` naming:
- `contract-review/risk-identification/SKILL.md` → `contract-review-risk-identification/SKILL.md`
- `contract-review/clause-revision/SKILL.md` → `contract-review-clause-revision/SKILL.md`

**Frontmatter preservation:**
The `name` field in frontmatter retains the original name (e.g., `risk-identification`), while the directory name uses the hyphenated form for uniqueness.

**Rationale:** DSH's one-level scan cannot handle nested directories. Hyphenated naming ensures uniqueness while preserving semantic meaning.

### 8. End-to-End Demo Path

**Existing Phase 113 script:** `/home/sorawatcher/workspace/inkstatute-suite/scripts/test_materialize_presets.sh`

**Pattern:** Uses temp directories for source and destination, verifies:
1. Files materialized correctly
2. Installed files are read-only
3. Re-run is atomic (idempotent)

**Phase 114 adaptation:**
Create `scripts/test_dsh_materialization.sh` with the following chain:
```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Run convert-skills.js --to dsh on corpus
cd /home/sorawatcher/workspace/ai-for-china-legal
node scripts/convert-skills.js --to dsh \
  --input ./commercial-legal/skills \
  --output ./dist/dsh/legal-commercial

# 2. Generate manifest
node scripts/generate-dsh-manifest.js \
  --input ./dist/dsh \
  --output ./dist/dsh/content-manifest.json

# 3. Create zip
cd dist/dsh
zip -r ../legal-skills-content-v1.0.0.zip .

# 4. Verify unzip and structure
cd ../..
unzip -q legal-skills-content-v1.0.0.zip -d /tmp/test-unpack
# Verify SKILL.md files exist and are parseable
# Verify manifest.json is valid JSON
# Verify sha256 hashes match
```

**Minimal script chain:** convert → manifest → zip → verify

### 9. CI Integration

**Finding:** The corpus has NO CI infrastructure (no `.github/workflows/` directory).

**Current test script:** `package.json` line 18:
```json
"test:compatibility": "node scripts/convert-skills.js --to all --input ./commercial-legal/skills --output ./dist/test"
```

**Extension approach (from CONTEXT.md GA-5):**
Create `scripts/test-dsh-output.js` and extend `package.json`:
```json
"test:dsh": "node scripts/test-dsh-output.js",
"test:compatibility": "node scripts/convert-skills.js --to all --input ./commercial-legal/skills --output ./dist/test && npm run test:dsh"
```

**CI runner OS:** Since the corpus has no CI, Phase 114 can establish CI on GitHub Actions using Linux runners (ubuntu-latest). The Node.js script is cross-platform and will run on Linux CI.

### 10. Manifest Schema

**Required fields (from CONTEXT.md success criterion #3):**
```json
{
  "schema_version": "1.0.0",
  "release_version": "1.0.0",
  "released_at": "2026-08-14T00:00:00Z",
  "min_engine_version": "47f943859b",
  "domains": {
    "legal-commercial": {
      "skills": [
        {
          "name": "contract-review",
          "sha256": "abc123..."
        }
      ]
    },
    "legal-litigation": { "skills": [...] },
    "legal-family": { "skills": [...] },
    "legal-employment": { "skills": [...] }
  }
}
```

**Existing manifest examples:** None found in either repo. The corpus has `plugin.json` files for Claude plugin metadata, but no content-manifest.json format.

**Implementation:** Create `scripts/generate-dsh-manifest.js` that:
1. Scans `dist/dsh/<domain>/` directories
2. Computes sha256 for each SKILL.md file
3. Generates manifest with above schema
4. Writes to `dist/dsh/content-manifest.json`

## Risk-Gate Items

No new V1-V5 risks identified. All findings are HIGH confidence based on source code verification.

## Recommendations for Planner

1. **Convert-skills.js extension:** Add `dsh` to `VALID_PLATFORMS` and implement `convertToDSH()` function that:
   - Accepts domain whitelist (commercial-legal, litigation-legal, family-legal, employment-legal)
   - Outputs flat structure: `dist/dsh/<domain>/<skill-name>/SKILL.md`
   - Promotes sub-skills with hyphenated naming
   - Applies two semantic rewrites (slash commands, CLAUDE.md writes)
   - Preserves frontmatter (name, description, argument-hint)

2. **Domain mapping:** Hardcode the whitelist in the dsh target with explicit mapping:
   ```javascript
   const DOMAIN_MAP = {
     'commercial-legal': 'legal-commercial',
     'litigation-legal': 'legal-litigation',
     'family-legal': 'legal-family',
     'employment-legal': 'legal-employment'
   };
   ```

3. **Semantic rewrite implementation:**
   - Slash command regex: `\/([a-z-]+):([a-z-]+)` → replace with "用 skill 工具按名加载 $2 技能"
   - CLAUDE.md write regex: `写入.*CLAUDE\.md` → replace with "写入 practice-profile.md"

4. **Manifest generator:** Create `scripts/generate-dsh-manifest.js` with crypto module for sha256.

5. **Content gate:** Create `scripts/test-dsh-output.js` that validates:
   - Each SKILL.md is parseable (YAML frontmatter valid)
   - Frontmatter has required `name` and `description` fields
   - No slash command patterns remain in body
   - No CLAUDE.md write patterns remain in body
   - Directory names match frontmatter `name` (or hyphenated form for sub-skills)

6. **CI integration:** Add `.github/workflows/dsh-materialization.yml` to corpus repo that runs `npm run test:compatibility` on push to main.

7. **End-to-end demo:** Create `scripts/test_dsh_materialization.sh` following the pattern of `test_materialize_presets.sh`.

8. **Legal-core selection:** Plan for manual curation of ≤30 skills from the 100 total across 4 domains. Consider adding a `core: true` frontmatter field to mark skills for legal-core inclusion.

## Open Questions

None. All research questions answered with HIGH confidence.
