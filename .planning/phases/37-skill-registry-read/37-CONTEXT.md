---
phase: 37
slug: skill-registry-read
status: planning
discuss_skipped: true
created: 2026-07-04
---

# Phase 37 Context — Skill Registry Read

> Discuss phase skipped (`workflow.skip_discuss=true`). Minimal context generated from ROADMAP.md and REQUIREMENTS.md.

## Phase Boundary

**Goal:** Operator can query a read-only Skill Registry that exposes Hermes skill metadata as `NeutralSkillDescriptor` records with list, get, search, and well-known discovery endpoint operations.

**Depends on:** Phase 36 (COMPLETE — safety baselines in place)

**Requirements:** SKILL-01, SKILL-02

## Success Criteria (from ROADMAP.md)

1. Operator can query the Skill Registry with `list_skills`, `get_skill`, and `search` operations (filter by tag, category, name substring) and receive `NeutralSkillDescriptor` records derived from Hermes skill metadata.
2. Operator can fetch `/.well-known/agent-skills/index.json` from the Skill Registry and receive skill name, description, and URL for discovery per the Cloudflare agent-skills-discovery convention.
3. Operator can verify the Skill Registry is read-only (no write, update, or delete operations) and that the `skill_registry_enabled` feature flag defaults to `False`.

## Decisions

No user decisions gathered (discuss skipped). Planner has discretion per RESEARCH.md findings.

## Code Context

- `skill_registry_enabled` feature flag already added in Phase 36 (defaults to `False`)
- Hermes skill metadata source needs to be identified during research
- `NeutralSkillDescriptor` schema may need to be defined or may already exist in platform-contract
- Cloudflare agent-skills-discovery convention: `/.well-known/agent-skills/index.json`
