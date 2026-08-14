---
phase: 114-skill-pipeline-dsh-target
plan: 114-01
wave: 1
status: complete
commit: 0a29ca8
tests: 13
requirements: [SKL-01]
---

# Plan 114-01: Summary

## What was done

Extended `ai-for-china-legal/scripts/convert-skills.js` with a new `dsh` target that materializes skills from the corpus into DSH-compatible flat format.

### Files modified
- `scripts/convert-skills.js` — Added `dsh` to VALID_PLATFORMS, DOMAIN_MAP whitelist, convertToDSH(), processDSH(), rewriteSlashCommands(), rewriteClaudeMdWrites(), dshFlatSkillName(), dshSourceDomain()
- `package.json` — Added `test:dsh-convert` script

### Files created
- `test/fixtures/dsh-synthetic/` — Synthetic fixture corpus (5 SKILL.md files across 3 domains, 2 whitelisted + 1 non-whitelisted)
- `test/dsh-convert.test.js` — 13 tests covering all conversion behaviors

## Key decisions

1. **Domain detection:** Two modes — single-domain (inputBase ends with `/skills`, domain = parent dir name) and multi-domain (inputBase contains domain subdirectories, domain = first path segment).
2. **Sub-skill promotion:** `<parent>/<child>/SKILL.md` → `<parent>-<child>/SKILL.md`. Frontmatter `name` retains original name.
3. **Slash command regex:** `/\/([a-z][a-z-]*):([^\s`)]+)/g` — matches `/plugin:skill` patterns including placeholder names like `<子技能名>`.
4. **CLAUDE.md rewrite:** All `CLAUDE.md` references replaced with `practice-profile.md`, except those in `> **迁移说明**` migration blockquote lines.
5. **Description field:** Semantic rewrites applied to both frontmatter description and body text.
6. **`dsh` excluded from `all`:** The `all` platform expansion remains `["kimi", "opencode", "standalone"]` — dsh is a separate target.

## Test results

- 13 tests, all pass
- Domain whitelist: 3 tests ✓
- Flat structure: 1 test ✓
- Sub-skill promotion: 2 tests ✓
- Slash command rewrite: 2 tests ✓
- CLAUDE.md rewrite: 2 tests ✓
- Frontmatter preservation: 2 tests ✓
- Existing target compatibility: 1 test ✓

## Verification

- `node scripts/convert-skills.js --to dsh --input ./commercial-legal/skills --output ./dist/dsh-test` produces 23 flat skills in `legal-commercial/`
- Zero slash command residue in output
- Zero CLAUDE.md residue outside migration blockquotes
- Existing kimi target unaffected
