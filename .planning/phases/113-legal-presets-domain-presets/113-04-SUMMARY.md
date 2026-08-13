---
phase: 113-legal-presets-domain-presets
plan: 04
type: summary
created: 2026-08-14
---

# Plan 113-04 Summary — engine smoke test (real DSH engine)

## What was accomplished

Executed a **real DSH engine smoke test** for the legal-core preset. The DSH engine was spawned with a mock LLM and the legal-core preset's skill composition, driven through the full ACP protocol (initialize → session/new → session/prompt), and the model request was captured to verify:

1. **Skill names discovered**: All 3 legal-core fixture skills (`citation-check`, `contract-review`, `legal-research`) appear in the `<available_skills>` block in the model request messages — confirming that the `skill-filesystem` plugin discovered the SKILL.md files from `customSkillDirs` and the `tool-skill` plugin rendered the catalog into the model prefix.
2. **`ask_user_question` excluded**: The tool catalog registered by the engine contains `create_goal`, `get_goal`, `job_kill`, `job_list`, `job_output`, `skill`, `update_goal` — and does NOT contain `ask_user_question` — confirming DP-1 (the `tool-ask-user` plugin row omission removes the tool from the engine's tool registry).

The structural fallback path was also implemented and remains available for environments where the DSH engine is not built or node is not available.

### Task 1: EnginePresetSmoke utility + test

- Created `apps/flutter_app/lib/presets/engine_preset_smoke.dart`:
  - `SmokePath` enum: `realEngine`, `structuralFallback`.
  - `SmokeResult` class: `pathTaken`, `skillsDiscovered`, `askUserQuestionPresent`, `details`.
  - `EnginePresetSmoke.run()`: attempts the real engine path first, falls back to structural verification.
  - **Real engine path**: Creates a temp directory with a mock LLM (`mock-llm.mjs`), a minimal `cordis.yml` using the legal-core skill composition (with `skill-filesystem` pointing to `presets/legal-core/skills`, `tool-skill`, and NO `tool-ask-user`), and `node_modules/` symlinks to all built DSH packages. Spawns the engine via `Process.start('node', [bin.js, --config, cordis.yml])`, drives the ACP protocol via raw NDJSON, reads the captured model request, and extracts skill names and tool names.
  - **Structural fallback path**: Parses the preset's `agent.cordis.yml` via `PresetReader.parseComposition()`, asserts no `tool-ask-user` plugin, asserts `customSkillDirs` is set, scans the `skills/` directory for SKILL.md files via `PresetReader.parseSkillFrontmatter()`, and collects skill names.
- Created `apps/flutter_app/test/presets/engine_preset_smoke_test.dart`:
  - Resolves the legal-core preset directory from the repo root.
  - Calls `EnginePresetSmoke.run()` with `preferRealEngine: true`.
  - Asserts `askUserQuestionPresent == false` (regardless of path taken).
  - Asserts `skillsDiscovered` is non-empty and contains at least one of `contract-review`, `legal-research`, `citation-check`.
  - Asserts `pathTaken` is a valid `SmokePath` enum value.
  - Prints the path taken and details for documentation.
  - 120-second timeout to accommodate the real engine path (node_modules setup + engine spawn + ACP session).
  - Additional tests for `SmokeResult` data class and `SmokePath` enum.

### Task 2: 113-ENGINE-SMOKE-RESULT.md

- Created `.planning/phases/113-legal-presets-domain-presets/113-ENGINE-SMOKE-RESULT.md` documenting:
  - **Path Taken**: Real DSH engine smoke test (`SmokePath.realEngine`).
  - **Rationale**: Built DSH engine available, node available, mock LLM approach used (no `DEEPSEEK_API_KEY` needed), package resolution via symlinks.
  - **Assertions Verified**: ask_user_question NOT in tool catalog, legal-core skill names in `<available_skills>` block, preset YAML valid, customSkillDirs set, ACP protocol handshake succeeded.
  - **V3 Verification Item Status**: Fully verified — skill directory enters model prefix, skills loadable by name.
  - **Test Output**: The actual smoke test result output.

## Files created/modified

### Created
- `apps/flutter_app/lib/presets/engine_preset_smoke.dart` (497 lines)
- `apps/flutter_app/test/presets/engine_preset_smoke_test.dart` (105 lines)
- `.planning/phases/113-legal-presets-domain-presets/113-ENGINE-SMOKE-RESULT.md`

### Modified
- None (no existing files changed, no frozen directories touched)

## Test results

- **Engine preset smoke tests**: 3 tests, all pass
  - `engine_preset_smoke_test.dart`: 3 tests (smoke test with real engine, SmokeResult data class, SmokePath enum)
- **Full flutter test suite**: 135 tests (134 pass + 1 skip), all pass
- **dart analyze**: No issues found

## V4 gate results

| Gate | Status | Message |
|------|--------|---------|
| dart-analyze | PASS | No issues found |
| flutter-test | PASS | All tests passed |
| engine-manifest | SKIP | Pin + cordis valid; engine-manifest.json not found (build engine first) |
| mock-e2e | PASS | All mock E2E tests passed |
| meta-test | PASS | All lib/ directories have test coverage |
| docx-golden | SKIP | SKIP: docx golden not active until Phase 118 |

**All V4 gates passed.**

## Smoke test path: Real DSH engine

The real DSH engine smoke test was used (not the structural fallback). Key evidence:

```
Path taken: realEngine
Skills discovered: [citation-check, contract-review, legal-research]
ask_user_question present: false
Tools: create_goal, get_goal, job_kill, job_list, job_output, skill, update_goal
Available skills block found: true
```

The mock LLM approach allowed a full engine boot, skill discovery, tool registration, and ACP protocol session without requiring `DEEPSEEK_API_KEY`. The `<available_skills>` block was found in the model request messages (injected by the `tool-skill` plugin as a user-role message), not in the system prompt.

## Deviations from the plan

1. **Mock LLM approach**: The plan suggested checking for `DSH_SNAPSHOT=replay` or a mock LLM mode. The DSH repo has a `DSH_SNAPSHOT=replay` mode, but it requires a pre-recorded fixture file and replays a fixed session — it cannot drive new prompts or discover new skills. Instead, a custom mock LLM (`LlmAdapter` plugin) was created that captures the model request and returns a canned response. This is more flexible and allows testing the actual skill discovery and tool registration pipeline.

2. **`<available_skills>` in messages, not system prompt**: The plan expected skill names to appear in the system prompt or the `initialize` response. The DSH `tool-skill` plugin injects the `<available_skills>` block as a durable user-role message in the conversation, not in the system prompt. The mock LLM captures `options.messages` (which contains the user-role message with the skill catalog) in addition to `options.system` and `options.tools`.

3. **Node_modules setup via shell script**: The plan suggested using `DshProcessManager` from Phase 112. However, `DshProcessManager` requires a `DshConfig` that points to a built engine directory with `lib/bin.js` and `acp.cordis.yml`. The smoke test creates its own temp directory with a custom `cordis.yml` and needs package resolution via symlinks. A shell script is used for the node_modules setup for speed (scanning ~200 packages is faster in bash than in Dart async I/O).

4. **Raw NDJSON instead of AcpClient**: The smoke test uses raw NDJSON over stdin/stdout instead of the `AcpClient` from Phase 112. This avoids coupling the smoke test to the `AcpClient`'s internal state management and allows direct control over the protocol flow. The `AcpClient` is still used by the structural fallback path's mock ACP server (if needed).

## Verification status

- [x] EnginePresetSmoke attempts the real DSH engine first, falls back to structural if not feasible
- [x] Real engine path: spawns DSH with mock LLM, drives initialize → session/new → session/prompt
- [x] Real engine path: captures model request (system prompt, tools, messages)
- [x] Real engine path: asserts skill names in `<available_skills>` block
- [x] Real engine path: asserts `ask_user_question` NOT in tool names
- [x] Structural fallback: parses preset YAML, asserts no tool-ask-user, asserts customSkillDirs, scans SKILL.md
- [x] Both paths assert no ask_user_question in the tool catalog
- [x] Both paths discover legal-core skill names
- [x] Test passes in the current environment (real engine path taken)
- [x] Path taken is recorded for documentation (SmokeResult.pathTaken)
- [x] 113-ENGINE-SMOKE-RESULT.md documents the path taken, rationale, and V3 status
- [x] V3 verification item fully verified (skill directory enters model prefix, skills loadable by name)
- [x] `flutter analyze` exits 0
- [x] `flutter test` exits 0
- [x] V4 gates all pass
- [x] No frozen directory modified
- [x] No modifications to presets/ files (owned by Plans 113-01 and 113-02)
- [x] No modifications to the DSH repo
- [x] No real API key required (mock LLM used)
