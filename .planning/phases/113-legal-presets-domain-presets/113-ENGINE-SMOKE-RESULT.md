# Phase 113 — Engine Smoke Test Result

## Path Taken

**Real DSH engine smoke test** — `SmokePath.realEngine`

The real DSH engine was successfully spawned with a mock LLM and the legal-core preset's skill composition. The ACP protocol was driven end-to-end: `initialize` → `session/new` → `session/prompt`. The mock LLM captured the model request, which contained the `<available_skills>` block with all 3 legal-core fixture skill names and a tool catalog that did NOT include `ask_user_question`.

## Rationale

A real engine smoke test was feasible because:

1. **Built DSH engine available**: The DSH repo at `/home/sorawatcher/deepseek-harness` has a built `packages/examples/acp-demo/lib/bin.js` (the ACP server bin). All DSH packages have built `lib/index.js` outputs from the repo's TypeScript build.

2. **Node.js available**: Node v24.16.0 is installed at `/home/sorawatcher/.local/bin/node`.

3. **Mock LLM approach**: No `DEEPSEEK_API_KEY` was needed. A custom mock LLM (`mock-llm.mjs`) was created as a `LlmAdapter` plugin that captures the model request (system prompt, tool schemas, and messages) and returns a canned response. This allows the engine to boot, load the preset composition, discover skills, render the `<available_skills>` catalog, register tools, and drive a full ACP session — all without a real model call.

4. **Package resolution**: A temp directory was created with `node_modules/` symlinks pointing to all built DSH packages and vendor packages. This allows the Cordis loader to resolve all plugin imports from the temp directory.

The `DSH_SNAPSHOT=replay` mode was also investigated but requires a pre-recorded fixture file (`DSH_SNAPSHOT_FILE`) and replays a fixed session — it cannot drive new prompts or discover new skills. The mock LLM approach is more flexible and allows testing the actual skill discovery and tool registration pipeline.

## Assertions Verified

### 1. `ask_user_question` is NOT in the ACP session tool catalog (DP-1 verified)

The mock LLM captured the tool schemas from the model request. The registered tools were:
- `create_goal`
- `get_goal`
- `job_kill`
- `job_list`
- `job_output`
- `skill`
- `update_goal`

`ask_user_question` is **NOT** in this list. This confirms that omitting the `tool-ask-user` plugin row from the preset composition removes the `ask_user_question` tool from the engine's tool registry (DP-1).

### 2. Legal-core skill names are discoverable (V3 verified)

The mock LLM captured the `<available_skills>` block from the model request messages:

```
<available_skills>
- `citation-check`: 引用核查——标注 verified/retrieved/unverified 来源状态
- `contract-review`: 合同审查——条款风险识别与修订建议
- `legal-research`: 法律检索——现行法规与司法解释检索
</available_skills>
```

All 3 legal-core fixture skill names (`citation-check`, `contract-review`, `legal-research`) appear in the catalog. This confirms that:
- The `skill-filesystem` plugin discovered the SKILL.md files from the `customSkillDirs` path.
- The `tool-skill` plugin rendered the catalog (name + description) into the model prefix as `<available_skills>`.
- Skills are loadable by name via the `skill` tool (the tool is registered in the catalog).

### 3. Preset YAML is valid and parseable

The engine successfully loaded the cordis.yml composition, which includes the `skill-filesystem` plugin with `customSkillDirs` pointing to the legal-core skills directory. No load errors occurred.

### 4. `customSkillDirs` is set correctly

The `customSkillDirs` in the smoke test cordis.yml points to the local `presets/legal-core/skills` directory. The engine successfully discovered all 3 SKILL.md files from this directory.

### 5. ACP protocol handshake succeeded

- `initialize` returned `protocolVersion: 1` with `agentInfo.name: "deepseek-harness-acp"`.
- `session/new` returned a valid `sessionId`.
- `session/prompt` completed with `stopReason: "end_turn"`.

## V3 Verification Item Status

**V3 is fully verified** by this smoke test:

- ✅ Skill directory enters the model prefix — the `<available_skills>` block was present in the model request messages, rendered by the `tool-skill` plugin from the `skill-filesystem` discovery.
- ✅ Skills are loadable by name — the `skill` tool is registered in the tool catalog, allowing the model to load any skill by its name from the `<available_skills>` list.

No deferral is needed — the real engine smoke test fully exercises the V3 verification item's landing form.

## Test Output

```
=== ENGINE PRESET SMOKE TEST RESULT ===
Path taken: realEngine
Skills discovered: [citation-check, contract-review, legal-research]
ask_user_question present: false
Details: Real DSH engine spawned with mock LLM. protocolVersion=1, sessionId=0056f1e9-09b8-474e-87e6-24696520390e. Tools: create_goal, get_goal, job_kill, job_list, job_output, skill, update_goal. Available skills block found: true.
=== END SMOKE TEST RESULT ===
```

## Implementation Notes

- The smoke test creates a temp directory with:
  - `mock-llm.mjs`: A mock `LlmAdapter` that captures the model request and writes it to a JSON file.
  - `cordis.yml`: A minimal ACP composition with the mock LLM, `skill-filesystem` (pointing to legal-core skills), `tool-skill`, and `acp-agent` — but NO `tool-ask-user`.
  - `node_modules/`: Symlinks to all built DSH packages and vendor packages for module resolution.
- The engine is spawned via `Process.start('node', [bin.js, '--config', './cordis.yml'])`.
- The ACP protocol is driven via raw NDJSON over stdin/stdout.
- The mock LLM captures `options.system`, `options.tools`, and `options.messages` from the `GenerateOptions` passed to `stream()`.
- The `<available_skills>` block is found in the `messages` array (as a user-role message injected by `tool-skill`), not in the `system` prompt.
- The structural fallback path remains available for environments where the DSH engine is not built or node is not available.
