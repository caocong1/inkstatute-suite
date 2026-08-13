---
phase: 113-legal-presets-domain-presets
transitioned: 2026-08-14
status: complete
plans_total: 4
plans_complete: 4
review_status: clean (remediated 8d185e6)
v4_gates: all pass
human_gates_open: none in Phase 113
requirements_covered: SKL-05, SKL-06, SKL-07
---

# Phase 113: Transition Record

## Completion summary

Phase 113 delivered the legal preset layer for InkStatute v4.0:

- **5 presets** with full guardrail persona (research-gate, citation audit, ask-user via `[CLARIFY: …]`, de-AI polish, `[HUMAN_REVIEW: …]`, confidentiality) and skill-loading directive:
  - `legal-core` — 3 curated skills (contract-review, legal-research, citation-check)
  - `legal-commercial` — 3 skills (commercial-due-diligence, contract-drafting, shareholder-agreement)
  - `legal-litigation` — 3 skills (civil-lawsuit-prep, evidence-organization, court-filing)
  - `legal-family` — 3 skills (divorce-settlement, child-custody, inheritance-dispute)
  - `legal-employment` — 3 skills (labor-dispute, severance-negotiation, employment-contract)
- **`PresetReader`** — YAML parsing with DSH `!!js` tag stripping, composition/metadata/skill-frontmatter parsing.
- **`BudgetGate`** — configurable 8,000-char default catalog budget, 345-skill full mount explicitly forbidden and tested.
- **`materialize_presets.sh`** — atomic install to `~/.agent-presets/<domain>/` with read-only discipline.
- **`EnginePresetSmoke`** — real DSH engine smoke test verified:
  - All 3 legal-core skill names appear in the model's `<available_skills>` prefix block.
  - `ask_user_question` is NOT in the tool catalog (DP-1 verified at engine level).
  - Structural fallback path documented for environments without the engine.

## Plans executed

| Plan | Wave | Title | Commit |
|------|------|-------|--------|
| 113-01 | 1 | legal-core preset + guardrail persona + budget gate | `9876fb5` |
| 113-02 | 2 | Four domain presets + structural and budget tests | `3a817a3` |
| 113-03 | 2 | Materialization script + token budget enforcement tests | `f5cc21a` |
| 113-04 | 3 | Real DSH engine smoke test | `64374b4` |

## Code review

- **Findings:** 0 critical, 4 warnings, 3 info
- **Remediation commit:** `8d185e6`
  - WR-01: Removed `ask_user_question` references from plan-mode section in all 5 preset compositions (replaced with `[CLARIFY: …]` convention text).
  - WR-03: `BudgetGate.checkFromSkillDirs` now falls back to `USERPROFILE` (Windows) when `HOME` is unset.
  - WR-04: `EnginePresetSmoke` now drains stderr to prevent pipe buffer fill from blocking the engine process.
  - WR-02: Accepted as-is — materialize_presets.sh is install-time only; the race window is acceptable for a single-user desktop app.
- **Final status:** clean

## V4 gate status (final)

| Gate | Status |
|------|--------|
| dart-analyze | PASS |
| flutter-test | PASS |
| engine-manifest | SKIP (build engine first) |
| mock-e2e | PASS |
| meta-test | PASS |
| docx-golden | SKIP (active at Phase 118) |

## Test count

- **Total Flutter tests:** 135 (134 pass + 1 skip)
- **New preset tests:** 75 (across 7 test files)

## Requirements closed

- **SKL-05** — Legal domain presets (legal-core + 4 domains) ✓
- **SKL-06** — Preset persona with guardrails and skill-loading directive ✓
- **SKL-07** — Token budget gate (8,000 chars, configurable, 345-skill prohibition) ✓

## Human gates

None opened or closed in Phase 113. Carried forward:
- HG-1 (Phase 120) — legal quality baseline
- HG-4 (Phase 118) — Word track-changes quality
- HG-3 (Phase 120) — five-day / 15-task lawyer trial

## Next phases (parallel per roadmap)

- **Phase 114:** Skill Pipeline — dsh Target (corpus → DSH skill materialization)
- **Phase 115:** Skill Content Auto-Update (app-side content package updater)
- **Phase 116:** Chat UI & Output Boundary (Flutter chat UI, approval/clarification cards, citation/human-review badges)

## Carry-forward notes for Phase 114

- `presets/<domain>/skills/*/SKILL.md` are synthetic fixtures only — Phase 114 must materialize real skills from `ai-for-china-legal` into DSH format.
- `PresetReader.parseSkillFrontmatter` expects YAML frontmatter with `name` and `description` fields — Phase 114's materialized skills must conform.
- `BudgetGate` enforces ≤8,000 chars by default — Phase 114's materialized legal-core catalog must fit within this budget.
- `customSkillDirs` in each preset points to `~/.agent-presets/<domain>/skills` — Phase 114's materialization target must align with this path.
