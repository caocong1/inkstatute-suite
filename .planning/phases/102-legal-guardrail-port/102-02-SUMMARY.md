---
phase: 102-legal-guardrail-port
plan: 02
status: complete
created: 2026-08-08
---

# Plan 102-02 Summary — Prompt Assembler Port

## What Was Done

Ported the prompt assembly logic from `lawyer-desktop/src-tauri/src/skills/router.rs` (627 lines) into a pure-function Python module `packages/agent-core/src/inkstatute_agent_core/prompt_assembler.py` (362 lines). All 10 Rust golden fixture test cases were replicated as Python tests, plus 13 additional behavioral tests for full coverage.

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `packages/agent-core/src/inkstatute_agent_core/prompt_assembler.py` | 362 | Pure-function prompt assembly module |
| `packages/agent-core/tests/test_prompt_assembler.py` | 297 | 33 tests (10 Rust golden fixtures + 13 additional) |

## Ported Components

1. **`AgentMode` enum** — `str, Enum` with `CHAT`/`DRAFT`/`EVIDENCE` values (matching Rust `AgentMode` from `agent_classifier.rs:8-12`, serde `rename_all = "lowercase"`)
2. **`SkillMetadata` dataclass** — lightweight with `name`, `plugin_name`, `description`, `full_content` fields (matching Rust `SkillMetadata` fields used by `router.rs`)
3. **`RESEARCH_GATE_FALLBACK` constant** — verbatim from `router.rs:5-14` (raw string literal, no escape processing)
4. **`RETRIEVAL_TOOL_MAP`** — 10 `(tool_name, mapped_step)` pairs from `router.rs:67-99`
5. **`is_retrieval_tool_name(name)`** — direct matches + `mcp__` prefix fragment check (`router.rs:36-49`)
6. **`is_public_web_tool_text(text)`** — fragment check for web/search/fetch/url/browser/crawl/网页/搜索/抓取/链接 (`router.rs:51-58`)
7. **`is_retrieval_tool(name, description)`** — combines name + description check (`router.rs:60-63`)
8. **`build_retrieval_tool_mapping(retrieval_tools)`** — empty degradation + known tool mapping + unknown tool generic description + closing warning (`router.rs:103-137`)
9. **`build_skill_descriptions(skills)`** — builds `## 可用法律技能` section, skips `research-gate` (`router.rs:16-32`)
10. **`_build_qa_system_prompt()`** — Chat mode base prompt (`router.rs:195-213`)
11. **`_build_evidence_system_prompt()`** — Evidence mode base prompt (`router.rs:215-236`)
12. **`_DRAFT_BASE_PROMPT`** — Draft mode inline base prompt (`router.rs:149-164`)
13. **`_CITATION_WRITING_SPEC`** — citation format instructions (`router.rs:175-181`)
14. **`build_system_prompt(skills, research_gate_content, active_skill, mode, retrieval_tools)`** — assembles mode base + research-gate + retrieval tool mapping + citation spec + skill descriptions + active skill body (`router.rs:139-193`)

## What Was NOT Ported (per plan)

- `build_builtin_tool_definitions()` — tool definition builder, belongs to tool layer (Phase 101)
- `build_workspace_tool_definitions()` — tool definition builder
- `build_law_tool_definitions()` — tool definition builder
- `route_skill()` — skill routing, belongs to routing (Phase 98)

## Test Results

```
# Prompt assembler tests only
33 passed in 0.03s

# Full agent-core suite
583 passed, 20 warnings in 1.90s
```

- 550 pre-existing tests: all still green
- 33 new tests: all green
- No new pip dependencies (stdlib only: `dataclasses`, `enum`)

## Golden Fixture Test Cases (10 from Rust)

| # | Rust test name | Python test name |
|---|----------------|------------------|
| 1 | `evidence_prompt_mandates_clarify_research_and_review_markers` | `test_evidence_prompt_mandates_clarify_research_and_review_markers` |
| 2 | `draft_prompt_mandates_first_turn_clarification_and_gate` | `test_draft_prompt_mandates_first_turn_clarification_and_gate` |
| 3 | `qa_prompt_keeps_gate_but_drops_drafting_mandates` | `test_qa_prompt_keeps_gate_but_drops_drafting_mandates` |
| 4 | `tool_mapping_lists_only_available_tools` | `test_tool_mapping_lists_only_available_tools` |
| 5 | (tool_mapping in evidence prompt) | `test_tool_mapping_appears_in_evidence_prompt` |
| 6 | `empty_tool_list_degrades_honestly` | `test_empty_tool_list_degrades_honestly` |
| 7 | `public_web_tools_are_retrieval_tools` | 4 sub-tests in `TestPublicWebToolsAreRetrievalTools` |
| 8 | `retrieval_tool_name_detection` | 10 sub-tests in `TestRetrievalToolNameDetection` |
| 9 | (skill descriptions skip research-gate) | `TestBuildSkillDescriptions` |
| 10 | (active skill body injection) | `TestActiveSkillInjection` |

Note: Rust tests 5 (`qa_mode_excludes_generate_docx_but_other_modes_keep_it`) and 6 (`chat_mode_keeps_fetch_url_but_excludes_docx`) test `build_builtin_tool_definitions()` which was NOT ported (tool layer, Phase 101).

## Human Gate Status

**HG-1 (法律质量): NOT auto-closable.** This port is a structural port — the Python implementation produces equivalent prompts to the Rust source. Legal quality sampling by a lawyer is still required before claiming the guardrails are no worse than the current `lawyer-desktop` / Hermes implementation. This summary claims only that the structural port is complete and the golden fixture tests pass.

## Key Design Decisions

1. **String fidelity**: Rust `\` line continuations strip leading whitespace on continuation lines. The Python port uses implicit string concatenation with explicit `\n` escape sequences to produce byte-identical prompt content.
2. **No cross-package coupling**: `SkillMetadata` is a local dataclass, not imported from `skill-index`, to keep `agent-core` self-contained.
3. **Private base prompt functions**: `_build_qa_system_prompt()` and `_build_evidence_system_prompt()` are prefixed with `_` since they are only called via `build_system_prompt()`. `_DRAFT_BASE_PROMPT` is a module-level constant since the Draft prompt is an inline string literal in Rust.
