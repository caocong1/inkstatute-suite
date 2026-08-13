# Phase 112: DSH Engine Integration (ACP over stdio) - Research

**Researched:** 2026-08-13
**Domain:** Flutter desktop app + Dart ACP v1 client + DSH subprocess management + engine release pipeline + v4 gates
**Confidence:** HIGH (V1-V5 all closed with live evidence; DSH contract verified by source code + running tests)

## Summary

Phase 112 is the technical risk gate for V4. Its primary deliverable is closing V4-SELECTION §7's V1-V5 verification items with real evidence from the DSH repo at `/home/sorawatcher/deepseek-harness`. **All five items are CLOSED** — no falsification, no rollback trigger.

V1 (real ACP full flow) was verified by driving the DSH ACP composition (`examples/acp-agent/cordis.yml`) through a Python script client against a mock LLM server, completing initialize → session/new → session/prompt → receiving committed text "Hello from mock LLM" → clean exit (code 0). Additionally, 85 keyless snapshot tests passed (`DSH_SNAPSHOT=replay vitest run`), covering the full protocol surface including text turns, tool calls, bash execution, skill loading, approval escalation, and cancellation.

V2 (approval escalation) was verified by the `escalation-approved` and `escalation-rejected` snapshot tests, which show `session/request_permission` being sent from server to client with `allow-once`/`reject-once` options, the client's decision being relayed to the model, and the model's subsequent behavior reflecting the decision.

V3 (skill directory into prefix) was verified by the `skill-load` snapshot test, which proves skills are discovered from filesystem directories, their name+description catalog is rendered into the model prefix as a `<system-reminder>` with `<available_skills>`, and the model loads skills by name via the `skill` tool. The `customSkillDirs` config field (rank 300 in `dsh-skill-filesystem`) uses the same mechanism for additional custom roots.

V4 (session log path) was verified by source code analysis and fixture inspection: JSONL logs at `<root>/--<normalized-cwd>--/<encoded-id>/session.jsonl.zstd` (or `.jsonl` with compression:none), `SESSION_FORMAT_VERSION = 0`, first line is `SessionHeader` with `{type:"session", version:0, id, createdAt, cwd, delegationDepth:0}`.

V5 (production startup form) was verified by running `pnpm run build` and confirming the built bin at `packages/examples/acp-demo/lib/bin.js` (executable Node.js script with shebang `#!/usr/bin/env node`), then successfully driving an `initialize` handshake through the built bin.

**Primary recommendation:** Proceed to implementation. The ACP contract is stable enough for a Dart v1 client. Use the snapshot fixtures as the mock ACP server script source. Pin DSH commit `47f943859b` (current HEAD). The built bin path is `packages/examples/acp-demo/lib/bin.js` (bin name `dsh-acp-demo`).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`). Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

**Binding constraints from AGENTS.md / V4-PRD that plan-phase MUST honor (non-negotiable):**

- 引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）。无 WebView。ACP 契约以 DSH `packages/acp/acp/README.md` 为准。
- DSH 钉版本 + 禁自动升级引擎：`engines/dsh-pin.txt` 钉 commit；升级 = 改 pin → `scripts/build_dsh_release.sh` 重建 → 真机回归 → 随 app 版本发布。
- ACP 三个刻意限制由产品吸收：澄清走 `[CLARIFY: …]` 约定文本 + 前置采集（DP-1，引擎组合移除 `ask_user_question`）；工具活动以状态文案呈现（DP-2）；批准卡为唯一交互通道（DP-3）；单 in-flight（DP-4）。
- 批准栈 terminal/execute_code 默认拒绝、上抛用户卡、无批量批准；未知 kind 一律拒绝。
- 单用户、单本地引擎、Windows 优先；无 Gateway、无远程引擎、无多租户。
- 安全：API 密钥只存 OS 凭据库；仓库/日志/遥测/安装包零明文密钥（grep 断言）；引擎日志 reference-first（原始 payload、客户全文不进 app 日志）。
- V4 产品代码 = `apps/flutter_app/`（Dart/Flutter）与 `presets/`、`engines/`、`scripts/build_dsh_release.sh`、`scripts/run_v4_gates.py`。冻结目录（LEG-01 清单：services/gateway、services/wecom-service、services/qqbot-service、services/arena-service、packages/agent-core、packages/arena-engine、packages/acp-client(TS)、packages/ui-core(SolidJS)、apps/web、apps/desktop）零新提交。
- 每个新 Dart `lib/` 目录必须有测试覆盖（v4 门禁 meta-test）。
- 不引入新依赖除非 V4 PRD 或当前 phase plan 要求（Flutter 生态例外：SQLite/drift 等已列入 PRD）。

**Phase 112 是技术风险闸口：** RESEARCH 必须先闭环 V4-SELECTION §7 的 V1-V5。任一证伪触发 PRD §12.1 回退评审（RB1 分步表单澄清 / RB2 尾随日志展示），不得在证据不足时进入 Phase 113。Plan-phase 必须把 V1-V5 实测作为 RESEARCH 工作包的首要交付，并在 PLAN 中显式标注"V1-V5 闭环前不得进入实现波次"。

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`).

### Deferred Ideas (OUT OF SCOPE)

None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DSH-01 | Dart ACP v1 客户端（`apps/flutter_app/packages/acp_client`）——JSON-RPC stdio 帧收发、`initialize` 握手（仅 baseline 能力）、`session/new`（绝对 cwd；`additionalDirectories`/`mcpServers` 非空即拒）、`session/prompt`（单 in-flight）、`session/cancel`、`session/update` 文本块聚合、`session/request_permission` 策略钩子；以脚本化 mock ACP server（fixtures）完整测试，无需真实模型 | ACP protocol fully documented from SDK source + DSH bridge source. Framing = newline-delimited JSON (NDJSON). All 7 methods verified. Snapshot fixtures provide mock server script source. See §ACP Protocol Contract and §V1-V5 Evidence. |
| DSH-02 | DSH 子进程管理器——从捆绑引擎目录 spawn ACP 组合；`DSH_HOME` 指向 `%LOCALAPPDATA%\InkStatute\runtime\.dsh`；API 密钥经环境注入（不落盘明文）；initialize 握手健康探针；app 退出优雅关停；零孤儿进程断言 | DSH bridge teardown verified in source: `quiesce()` cancels all sessions, drains continuable subagents, disposes agents in parallel, awaits all results. Built bin confirmed working. See §Subprocess Management and §V5 Evidence. |
| DSH-03 | 引擎发布产物管线（`scripts/build_dsh_release.sh` + `engines/dsh-pin.txt` + `engines/acp.cordis.yml`）——钉 commit 构建 → `engine-<version>.zip`（便携 Node + 构建产物 + ACP 组合 + 预设物化）→ `engine-manifest.json` {dsh_commit, node_version, sha256, built_at}；**引擎禁自动升级** | Build verified: `pnpm run build` produces `packages/examples/acp-demo/lib/bin.js`. Node version requirement: `^22.19.0 \|\| >=24.0.0`. DSH commit SHA: `47f943859b`. See §Engine Release Pipeline and §V5 Evidence. |
| DSH-04 | 批准安全——引擎批准栈 terminal/execute_code 默认拒绝并上抛 `session/request_permission`；app 策略：未知 kind 一律拒绝、已知 kind 渲染用户卡片、无批量批准入口；mock 权限事件测试全路径 | Approval escalation verified via snapshot tests. `session/request_permission` sends `allow-once`/`reject-once` options. Approval config keys documented. See §Approval Security and §V2 Evidence. |
| GATE-01 | v4 门禁 runner（`scripts/run_v4_gates.py`）——dart analyze + flutter test + 内容结构测试 + 引擎清单校验，接 CI | Flutter/Dart not yet installed (Wave 0 gap). Gate runner design documented. See §V4 Gates Runner. |
| GATE-02 | 覆盖门禁——每个新 Dart `lib/` 目录有测试覆盖；meta-test 在 v4 runner 内 | Meta-test design documented. See §V4 Gates Runner. |
</phase_requirements>

## V1-V5 Verification Evidence

> **This is the risk gate deliverable.** All five items were verified against the DSH repo at `/home/sorawatcher/deepseek-harness` (READ-ONLY — no modifications were made to that repo).

### Summary Table

| Item | Description | Status | Evidence Method | Key Evidence |
|------|-------------|--------|----------------|--------------|
| V1 | Real ACP full flow (initialize → session/new → session/prompt → committed text) | **CLOSED** | Python script client + mock LLM server + keyless snapshot tests | Full flow completed with mock:llm; 85 snapshot tests passed |
| V2 | Approval escalation (terminal default deny → session/request_permission) | **CLOSED** | Keyless snapshot tests (escalation-approved, escalation-rejected) | `session/request_permission` with allow-once/reject-once options observed in fixtures |
| V3 | Skill directory into prefix (customSkillDirs → model prefix → load by name) | **CLOSED** | Keyless snapshot test (skill-load) + source code analysis | Skill catalog rendered as `<available_skills>` in model prefix; `skill` tool loads by name |
| V4 | Session log path and structure (JSONL, SESSION_FORMAT_VERSION) | **CLOSED** | Source code analysis + fixture inspection | Path pattern, header structure, SESSION_FORMAT_VERSION=0 confirmed |
| V5 | Production startup form (built bin, not tsx source) | **CLOSED** | `pnpm run build` + built bin initialize test | `packages/examples/acp-demo/lib/bin.js` built and responding to initialize |

### V1 — Real ACP Full Flow: CLOSED

**Method:** Two independent evidence paths:

#### Path A: Live mock-LLM full flow (primary evidence)

A Python script client drove the DSH ACP composition through the complete protocol flow against a mock LLM server.

**Commands run:**
```bash
# Terminal 1: Start mock LLM server
cd /home/sorawatcher/deepseek-harness
node --import tsx packages/test-support/llm-mock-server/src/bin.ts \
  --sequence success --success-text "Hello from mock LLM" --repeat-last --port 18003 --api-key mock-key

# Terminal 2: Drive ACP server via Python script client
cd /home/sorawatcher/deepseek-harness
DEEPSEEK_API_KEY=mock-key DEEPSEEK_BASE_URL=http://127.0.0.1:18003/v1 DSH_PERMISSION_MODE=workspace-write \
  python3 <script>  # sends initialize, session/new, session/prompt via stdin to:
  node --import tsx packages/examples/acp-demo/src/bin.ts --config examples/acp-agent/cordis.yml
```

**Observed output (verbatim):**
```
INIT: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp","version":"0.0.1"},"agentCapabilities":{"promptCapabilities":{"image":false,"audio":false,"embeddedContext":false}},"authMethods":[]}}
NEW: {"jsonrpc":"2.0","id":2,"result":{"sessionId":"78d56a12-3b3a-4f4d-a212-84d6b7a55f2c"}}
UPDATE: {"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"78d56a12-3b3a-4f4d-a212-84d6b7a55f2c","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"Hello from mock LLM"}}}}
PROMPT RESULT: {"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}
EXIT CODE: 0
```

**Mock LLM server output:**
```
{"type":"ready","baseURL":"http://127.0.0.1:18003/v1","randomSeed":1404701565}
{"type":"request","attempt":1,"scriptBehavior":"success","behavior":"success","path":"/v1/chat/completions"}
{"type":"result","attempt":1,"scriptBehavior":"success","behavior":"completed","chunksSent":5}
```

**Recorded facts:**
- Startup time: ~3s (tsx source launch; built bin is faster)
- Env vars required: `DEEPSEEK_API_KEY` (presence required at boot, validity only on model call), `DEEPSEEK_BASE_URL` (to point at mock), `DSH_PERMISSION_MODE` (sandbox policy)
- Exit code: 0 (clean exit on stdin close)
- Protocol version: 1
- Committed text received: "Hello from mock LLM" via `session/update` `agent_message_chunk`

[VERIFIED: live mock-LLM run, 2026-08-13]

#### Path B: Keyless snapshot tests (corroborating evidence)

**Command run:**
```bash
cd /home/sorawatcher/deepseek-harness
DSH_SNAPSHOT=replay npx vitest run --config vitest.snapshot.config.ts examples/acp-agent/tests/acp.snapshot.ts
```

**Observed output:**
```
 Test Files  1 passed (1)
      Tests  85 passed | 1 skipped (86)
   Duration  29.99s
```

Key passing scenarios:
- `snapshot: handshake matches the expected outputs` — initialize + session/new
- `snapshot: text-turn matches the expected outputs` — full prompt → committed text "PONG"
- `snapshot: tool-call-turn matches the expected outputs` — tool calls through ACP
- `snapshot: bash-tool-turn matches the expected outputs` — bash execution
- `snapshot: cancel matches the expected outputs` — session/cancel
- `snapshot: multi-turn matches the expected outputs` — multi-turn conversation
- `snapshot: skill-load matches the expected outputs` — skill loading (V3)
- `snapshot: escalation-approved matches the expected outputs` — approval approved (V2)
- `snapshot: escalation-rejected matches the expected outputs` — approval rejected (V2)

The `text-turn` fixture's `stdout.expected.jsonl` shows the complete protocol flow:
```jsonl
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp","version":"0.0.1"},"agentCapabilities":{"promptCapabilities":{"image":false,"audio":false,"embeddedContext":false}},"authMethods":[]}}
{"jsonrpc":"2.0","id":2,"result":{"sessionId":"{{sessionId}}"}}
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"{{sessionId}}","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"PONG"}}}}
{"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}
```

[VERIFIED: `DSH_SNAPSHOT=replay vitest run`, 2026-08-13]

### V2 — Approval Escalation: CLOSED

**Method:** Keyless snapshot tests + source code analysis.

**Commands run:**
```bash
cd /home/sorawatcher/deepseek-harness
DSH_SNAPSHOT=replay npx vitest run --config vitest.snapshot.config.ts examples/acp-agent/tests/acp.snapshot.ts
# Tests: snapshot: escalation-approved, snapshot: escalation-rejected — both PASSED
```

**Observed `session/request_permission` event (from `escalation-rejected/stdout.expected.jsonl`):**
```jsonl
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,...,"authMethods":[]}}
{"jsonrpc":"2.0","id":2,"result":{"sessionId":"{{sessionId}}"}}
{"jsonrpc":"2.0","id":1,"method":"session/request_permission","params":{"sessionId":"{{sessionId}}","toolCall":{"toolCallId":"call_00_WB1vnPomi8yr6MlcFKTj7912"},"options":[{"optionId":"allow-once","name":"Allow once","kind":"allow_once"},{"optionId":"reject-once","name":"Reject","kind":"reject_once"}]}}
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"{{sessionId}}","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"The user rejected the permission escalation, so this command cannot be run."}}}}
{"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}
```

**Approval config snippet (from `examples/acp-agent/cordis.yml`):**
```yaml
- id: approval
  name: '@deepseek-ai/dsh-user-approval'
  config:
    policy: !!js "(process.env.DSH_PERMISSION_MODE ?? (process.env.DSH_SNAPSHOT === undefined ? 'workspace-write' : 'danger-full-access')) === 'danger-full-access' ? 'never' : 'ask'"
```

**Sandbox policy config (from `cordis.yml`):**
```yaml
- id: sandbox-policy
  name: '@deepseek-ai/dsh-sandbox-policy'
  config:
    mode: !!js "process.env.DSH_PERMISSION_MODE ?? (process.env.DSH_SNAPSHOT === undefined ? 'workspace-write' : 'danger-full-access')"
    workspaceRoot: !!js process.cwd()
```

**How the escalation flow works** [VERIFIED: `packages/acp/acp/src/index.ts` lines 191-206, `packages/interaction/user-approval/README.md`]:
1. Sandbox starts in `read-only` or `workspace-write` mode
2. Model attempts a bash write that exceeds sandbox permissions
3. Sandbox denies the request
4. Model retries with `sandbox_permissions` + `justification`
5. The approval/request waterfall listener in the ACP bridge fires
6. Bridge sends `session/request_permission` to the client with `allow-once`/`reject-once` options
7. Client responds → outcome relayed to model via tool-result path
8. If rejected, model receives rejection and reports it; if approved, retried write lands on disk

**For V4 `engines/acp.cordis.yml` "terminal default deny" config:**
- Set `sandbox-policy.mode: 'read-only'` (or `workspace-write` for file writes within workspace)
- Set `approval.policy: 'ask'` (so terminal/execute_code requests escalate to client)
- The ACP bridge's `approval/request` listener sends `session/request_permission` with `allow-once`/`reject-once` — no batch approval path exists [VERIFIED: `packages/acp/acp/src/index.ts` lines 191-206]

[VERIFIED: snapshot tests + source code, 2026-08-13]

### V3 — Skill Directory into Prefix: CLOSED

**Method:** Keyless snapshot test + source code analysis.

**Commands run:**
```bash
cd /home/sorawatcher/deepseek-harness
DSH_SNAPSHOT=replay npx vitest run --config vitest.snapshot.config.ts examples/acp-agent/tests/acp.snapshot.ts
# Test: snapshot: skill-load — PASSED
```

**Skill fixture structure (from `examples/acp-agent/tests/snapshots/skill-load/workspace/.dsh/skills/`):**
```
snapshot-skill/SKILL.md    — name: snapshot-skill, description: Exercise project skill discovery...
model-only-skill/SKILL.md  — name: model-only-skill, user-invocable: false
user-only-skill/SKILL.md
```

**Snapshot skill content (`snapshot-skill/SKILL.md`):**
```yaml
---
name: snapshot-skill
description: Exercise project skill discovery and loading in snapshot tests.
---

Follow these snapshot-only instructions.
Resolve referenced resources relative to this skill directory.
```

**Input script (`skill-load/input.json`):**
```json
{
  "steps": [
    { "op": "initialize" },
    { "op": "newSession" },
    { "op": "prompt", "text": "Load the snapshot-skill skill with the skill tool, then reply DONE." }
  ]
}
```

**Observed output (`skill-load/stdout.expected.jsonl`):**
```jsonl
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,...}}
{"jsonrpc":"2.0","id":2,"result":{"sessionId":"{{sessionId}}"}}
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"{{sessionId}}","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"DONE"}}}}
{"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}
```

**How skills enter the model prefix** [VERIFIED: `packages/skill/tool-skill/README.md`, `packages/skill/skill-filesystem/README.md`]:
1. `dsh-skill-filesystem` scans configured roots (rank 100: `<projectRoot>/.dsh/skills`, rank 200: `<projectRoot>/.agents/skills`, rank 300: `customSkillDirs`, rank 400: `<dshHome>/skills`, rank 500: `<agentsHome>/skills`)
2. Each `<name>/SKILL.md` or `<name>.md` is parsed for frontmatter (`name`, `description`)
3. `dsh-tool-skill` renders the catalog as a `<system-reminder>` with `<available_skills>` block into the model prefix at `agent/pre-step`
4. Model calls `skill` tool with exact name → `renderSkillContent(skill)` returns canonical `<skill_content>` block
5. Skill watcher (`watch: true` default) invalidates catalog on filesystem changes → hot-refresh without restart

**`customSkillDirs` config** [VERIFIED: `packages/skill/skill-filesystem/README.md` Config table]:
```yaml
# In cordis.yml, via acp-agent config → skills.filesystem.customSkillDirs:
- id: acp-agent
  name: '@deepseek-ai/dsh-acp-demo'
  config:
    skills:
      filesystem:
        customSkillDirs:
          - /path/to/skills/domain-a
          - /path/to/skills/domain-b
```

The `customSkillDirs` entries are scanned at rank 300, after project roots and before user roots. The same discovery → catalog → prefix → load-by-name mechanism applies. The snapshot test uses project-level skills (rank 100: `.dsh/skills`), but the mechanism is identical for `customSkillDirs`.

[VERIFIED: snapshot test + source code, 2026-08-13]

### V4 — Session Log Path: CLOSED

**Method:** Source code analysis + fixture inspection.

**SESSION_FORMAT_VERSION** [VERIFIED: `packages/core/session/src/types.ts:56`]:
```typescript
export const SESSION_FORMAT_VERSION = 0
```

**Path pattern** [VERIFIED: `packages/session/session-persistence-jsonl/README.md` "On-disk layout"]:
```
<root>/--<normalized-cwd>--/<encoded-id>/session.jsonl.zstd    (default, zstd compression)
<root>/--<normalized-cwd>--/<encoded-id>/session.jsonl         (compression: 'none')
```

- `<root>` = `persistenceRoot` config value (from `cordis.yml` `acp-agent.config.persistenceRoot`)
- `--<normalized-cwd>--` = readable project directory (cwd with path separators replaced, bounded for filesystem limits; `_no-cwd/` when no cwd)
- `<encoded-id>` = session UUID, injectively escaped to one safe path segment (no traversal, no collision)

**Persistence root config** [VERIFIED: `examples/acp-agent/cordis.yml` line 56]:
```yaml
persistenceRoot: !!js process.env.DSH_SNAPSHOT_SESSIONS_ROOT ?? './.sessions'
persistenceCompression: !!js "process.env.DSH_SNAPSHOT === undefined ? 'zstd' : 'none'"
```

For V4 product: set `persistenceRoot` to `${DSH_HOME}/sessions` (i.e., `%LOCALAPPDATA%\InkStatute\runtime\.dsh\sessions`).

**Sample session header (first JSONL line)** [VERIFIED: `examples/acp-agent/tests/snapshots/text-turn/session.jsonl`]:
```json
{"type":"session","version":0,"id":"539aa64c-7f37-40ff-abd8-ed45b717be1b","createdAt":1783600629539,"cwd":"{{cwd}}","delegationDepth":0}
```

**Sample event structure (subsequent lines):**
```json
{"type":"agent/inbox/spliced","seq":0,"time":1785498761270,"data":{"target":"next-turn","start":0,"inserted":[...]}}
{"type":"turn/start","seq":1,"time":1785821359466,"data":{"turn":1}}
{"type":"step/start","seq":3,"time":1783600629542,"data":{"turn":1,"step":1}}
```

- `seq` is contiguous across the decoded log (`events[i].seq === i`)
- `type` tags include: `session`, `agent/inbox/spliced`, `turn/start`, `turn/end`, `step/start`, `step/end`, `assistant/message`, `assistant/chunk`, `tool/call`, `tool/result`, `approval/asked`, `approval/decided`, etc.
- `assistant/chunk` events are never dropped; eligible runs of ≥3 consecutive same-block chunks may be packed as `text-chunks`/`reasoning-chunks`/`tool-call-chunks` rows
- Compression: default `zstd` (checksummed frames); `none` for raw JSONL (snapshot mode)

**RB2 dependency:** The session log is the tail-follow source for RB2 (read-only progress display). The JSONL structure is stable within a pinned DSH commit; `SESSION_FORMAT_VERSION = 0` with no compatibility promise (pre-release stance). The app must NOT parse the JSONL as protocol — only extract status text from `turn/start`, `step/start`, `tool/call`, `assistant/message` events for display.

[VERIFIED: source code + fixture inspection, 2026-08-13]

### V5 — Production Startup Form: CLOSED

**Method:** `pnpm run build` + built bin initialize test.

**Command run:**
```bash
cd /home/sorawatcher/deepseek-harness
pnpm run build  # produces lib/ outputs across all packages
```

**Built bin location** [VERIFIED: `packages/examples/acp-demo/package.json` "bin" field + `ls packages/examples/acp-demo/lib/`]:
```
packages/examples/acp-demo/lib/bin.js    # 1439 bytes, executable, #!/usr/bin/env node
```

**Bin name:** `dsh-acp-demo` (from `package.json` `"bin": {"dsh-acp-demo": "lib/bin.js"}`)

**Built bin test:**
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}' | \
  DEEPSEEK_API_KEY=sk-dummy DSH_PERMISSION_MODE=workspace-write \
  node packages/examples/acp-demo/lib/bin.js --config examples/acp-agent/cordis.yml 2>/dev/null
```

**Observed output:**
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp","version":"0.0.1"},"agentCapabilities":{"promptCapabilities":{"image":false,"audio":false,"embeddedContext":false}},"authMethods":[]}}
```

**Node version requirement** [VERIFIED: `package.json` "engines" field]:
```
"node": "^22.19.0 || >=24.0.0"
```

**Build command:** `pnpm run build` (= `npm run build:lib && npm run build:web`; `build:lib` = `tsc -b tsconfig.host.json && tsdown --env.DSH_BUILD_FACE host` + client variant)

**Packaging implication for `build_dsh_release.sh`:**
1. Checkout pinned commit from `engines/dsh-pin.txt`
2. Run `pnpm install`
3. Run `pnpm run build`
4. Copy `packages/examples/acp-demo/lib/` (bin.js + index.js + invariant.js + types/)
5. Copy all workspace dependency `lib/` directories (the built bin imports `@deepseek-ai/dsh-app-boot` etc.)
6. Bundle portable Node (Windows, matching `^22.19.0 || >=24.0.0`)
7. Copy `engines/acp.cordis.yml` (the product composition config)
8. Zip as `engine-<version>.zip`
9. Generate `engine-manifest.json` with sha256

**Important:** The built bin is a Node.js ESM script (`import` statements), not a standalone executable. It requires Node.js runtime + all workspace dependency `lib/` directories. The packaging script must include the entire `node_modules` tree of built workspace packages (or use `tsdown` bundling to produce a single-file bundle — needs investigation in implementation).

[VERIFIED: `pnpm run build` + built bin test, 2026-08-13]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ACP JSON-RPC stdio client | Dart package (`packages/acp_client`) | — | Pure Dart package; no Flutter dependency; testable in isolation |
| DSH subprocess lifecycle | Flutter app (`apps/flutter_app`) | Dart `dart:io` | App owns process spawn/kill; `dart:io` Process API is the mechanism |
| Engine release packaging | Shell script (`scripts/`) | CI | Build-time artifact; not runtime code |
| V4 gate runner | Python script (`scripts/`) | CI | Meta-test + test orchestration; Python is the existing script language |
| Approval policy | App-side Dart | Engine-side config | App decides allow/reject; engine config sets default-deny + escalation |
| Session log persistence | Engine (DSH) | — | Engine owns JSONL logs; app reads for RB2 display only |
| Mock ACP server fixtures | Dart test fixtures | — | Scripted mock in Dart for client testing; no real model needed |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flutter | stable (install needed) | Windows desktop app framework | User-selected; native UI, no WebView [CITED: PRD §0.3] |
| Dart | bundled with Flutter | Language for ACP client + app | Flutter's language; `dart:io` for subprocess management |
| `@agentclientprotocol/sdk` | 0.25.1 | ACP protocol reference (TypeScript) | DSH's ACP SDK; Dart client re-implements the same wire protocol [VERIFIED: `node_modules/@agentclientprotocol/sdk/package.json`] |
| DSH (`deepseek-harness`) | commit `47f943859b` | V4 engine | User-selected; pinned commit [VERIFIED: `git rev-parse HEAD`] |
| Node.js | `^22.19.0 \|\| >=24.0.0` | DSH runtime | DSH engines requirement [VERIFIED: `package.json` engines field] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| drift | latest stable | SQLite ORM for Dart | Local session library (APP-03, Phase 116) — listed in PRD |
| sqlite3 | bundled with drift | Local database | Session/message/reference storage |
| test (Dart) | bundled with Flutter | Unit testing | ACP client tests, mock fixtures |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Flutter desktop | Tauri (Rust) | User explicitly chose Flutter; Tauri is the frozen v3.x approach |
| Custom Dart ACP client | Generate from ACP OpenAPI spec | ACP SDK is TypeScript-only; Dart client must be hand-written from the protocol spec (only 7 methods, low complexity) |
| `dart:io` Process | `process_run` package | `dart:io` is stdlib, sufficient for subprocess management; no extra dependency needed |

**Installation:**
```bash
# Flutter (Wave 0 — not yet installed)
# Download from https://docs.flutter.dev/get-started/install/windows
# Or via snap/apt on Linux for development
flutter create --platforms=windows apps/flutter_app

# DSH is already pnpm install-ed at /home/sorawatcher/deepseek-harness
# No additional npm packages needed in inkstatute-suite for Phase 112
```

**Version verification:**
- Flutter: NOT installed (Wave 0 gap — plan must include install step)
- Dart: NOT installed (bundled with Flutter)
- Node.js: v24.16.0 [VERIFIED: `node --version`]
- pnpm: 11.21.0 [VERIFIED: `pnpm --version`]
- Python: 3.14.6 [VERIFIED: `python3 --version`]
- `@agentclientprotocol/sdk`: 0.25.1 [VERIFIED: `node_modules/@agentclientprotocol/sdk/package.json`]

## Package Legitimacy Audit

> Phase 112 installs Flutter/Dart ecosystem packages (drift, sqlite3) and uses DSH's existing npm workspace. No new npm packages are introduced in the inkstatute-suite repo. Flutter packages are listed in PRD as exceptions to the "no new dependencies" rule.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| drift | pub.dev | — | — | github.com/simolus3/drift | N/A (pub.dev) | Approved (PRD-listed) |
| sqlite3 | pub.dev | — | — | github.com/simolus3/sqlite3.dart | N/A (pub.dev) | Approved (PRD-listed) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Flutter/pub.dev packages are not checked by slopcheck (npm-only). Both are PRD-listed exceptions to the no-new-dependency rule. The planner should verify pub.dev versions at install time.*

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ apps/flutter_app (Flutter Windows desktop)                   │
│                                                              │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────┐  │
│  │ packages/    │   │ DSH Subprocess   │   │ Session UI  │  │
│  │ acp_client   │←──│ Manager          │   │ (Phase 116) │  │
│  │ (Dart)       │   │ (dart:io Process)│   └─────────────┘  │
│  │              │   │                  │                     │
│  │ NDJSON       │   │ spawn bin.js     │   ┌─────────────┐  │
│  │ stdin/stdout │   │ DSH_HOME=...     │   │ Approval    │  │
│  │              │   │ DEEPSEEK_API_KEY │   │ Card UI     │  │
│  └──────┬───────┘   └────────┬─────────┘   │ (Phase 116) │  │
│         │                    │              └─────────────┘  │
│         │  JSON-RPC          │  process                       │
│         │  over stdio        │  stdin/stdout                  │
├─────────┼────────────────────┼───────────────────────────────┤
│         ▼                    ▼                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ DSH Engine (pinned commit, built bin)                    │ │
│  │  dsh-acp-demo bin.js                                     │ │
│  │  ├── ACP bridge (session/update, request_permission)     │ │
│  │  ├── Agent spine (loop, tools, skills, approval)         │ │
│  │  ├── JSONL session persistence                           │ │
│  │  └── engines/acp.cordis.yml (composition config)         │ │
│  └─────────────────────────────────────────────────────────┘ │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ DeepSeek API (or mock:llm for testing)                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Build/CI Layer                                               │
│  scripts/build_dsh_release.sh → engine-<version>.zip         │
│  engines/dsh-pin.txt → pinned commit SHA                     │
│  engines/acp.cordis.yml → product composition config         │
│  scripts/run_v4_gates.py → dart analyze + flutter test +     │
│    engine manifest validation + mock E2E + meta-test         │
└─────────────────────────────────────────────────────────────┘
```

Data flow for a user prompt:
1. User types in Flutter app → app constructs `session/prompt` JSON-RPC request
2. `acp_client` serializes to NDJSON, writes to DSH subprocess stdin
3. DSH engine processes prompt → calls DeepSeek API → receives model response
4. DSH engine sends `session/update` notifications (committed text chunks) via stdout
5. `acp_client` reads NDJSON from stdout → parses → delivers to app
6. If model requests bash/file access → DSH sends `session/request_permission` → app shows approval card → user decides → `acp_client` sends response back
7. Prompt completes → DSH sends `session/prompt` response with `stopReason`
8. App exits → subprocess manager kills DSH process → zero orphans

### Recommended Project Structure

```
apps/flutter_app/
├── pubspec.yaml              # Flutter app, path-dep on packages/acp_client
├── lib/
│   ├── main.dart             # App entry point
│   ├── engine/               # DSH subprocess manager
│   │   ├── dsh_process.dart  # Process.start, lifecycle, health probe
│   │   └── dsh_config.dart   # DSH_HOME, engine path resolution
│   └── ...
├── test/
│   ├── engine/
│   │   └── dsh_process_test.dart
│   └── ...
└── windows/                  # Windows platform files

apps/flutter_app/packages/
└── acp_client/               # Internal Dart package (path dependency)
    ├── pubspec.yaml           # No Flutter dependency; pure Dart
    ├── lib/
    │   ├── acp_client.dart    # Main client class
    │   ├── acp_transport.dart  # NDJSON stdio framing
    │   ├── acp_protocol.dart   # JSON-RPC types (request/response/notification)
    │   └── acp_types.dart      # ACP method types (initialize, session/new, etc.)
    └── test/
        ├── acp_client_test.dart
        ├── acp_transport_test.dart
        ├── acp_protocol_test.dart
        └── fixtures/
            ├── mock_acp_server.dart  # Scripted mock ACP server
            ├── handshake.jsonl       # initialize → session/new
            ├── text_turn.jsonl       # prompt → committed text
            ├── escalation.jsonl      # request_permission flow
            └── cancel.jsonl          # session/cancel flow

engines/
├── dsh-pin.txt               # pinned DSH commit SHA
└── acp.cordis.yml            # product ACP composition config

scripts/
├── build_dsh_release.sh      # checkout pin → install → build → zip → manifest
└── run_v4_gates.py           # dart analyze + flutter test + manifest + meta-test
```

### Pattern 1: NDJSON JSON-RPC over stdio
**What:** ACP uses newline-delimited JSON (NDJSON) framing — each JSON-RPC message is one line terminated by `\n`. No Content-Length headers.
**When to use:** All ACP communication over stdio.
**Example:**
```dart
// Source: @agentclientprotocol/sdk dist/stream.js (verified)
// Each message = JSON.stringify(message) + "\n"
// Reading: split on "\n", parse each non-empty line as JSON

class AcpTransport {
  final Stream<List<int>> stdin;   // process.stdin
  final IOSink stdout;              // process.stdout

  void send(Map<String, dynamic> message) {
    stdout.writeln(jsonEncode(message));  // adds \n
  }

  Stream<Map<String, dynamic>> get messages {
    return stdin
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .where((line) => line.trim().isNotEmpty)
        .map((line) => jsonDecode(line) as Map<String, dynamic>);
  }
}
```
[VERIFIED: `node_modules/@agentclientprotocol/sdk/dist/stream.js` — `ndJsonStream` function]

### Pattern 2: Request/Response with ID correlation
**What:** JSON-RPC 2.0: requests have `id` + `method` + `params`; responses have `id` + `result` (or `error`); notifications have `method` + `params` (no `id`).
**When to use:** All ACP methods.
**Example:**
```dart
// Client→server request (has id):
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}

// Server→client response (has id, no method):
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,...}}

// Server→client notification (has method, no id):
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"...","update":{...}}}

// Server→client request (has id + method — needs response):
{"jsonrpc":"2.0","id":1,"method":"session/request_permission","params":{...}}
```
[VERIFIED: `node_modules/@agentclientprotocol/sdk/dist/schema/index.js` — AGENT_METHODS + CLIENT_METHODS]

### Pattern 3: Single in-flight prompt per session
**What:** `session/prompt` rejects with `invalidParams` if a prompt is already in flight for that session. The bridge tracks `inflight` state per session record.
**When to use:** App must disable input while a prompt is in flight (DP-4).
**Example:**
```dart
// From DSH bridge source (packages/acp/acp/src/index.ts line 274):
// if (record.inflight !== undefined) {
//   throw invalidParams('a prompt is already in flight for this session')
// }
```
[VERIFIED: `packages/acp/acp/src/index.ts` lines 274-276]

### Pattern 4: Subprocess lifecycle with zero orphans
**What:** On app exit: (1) close stdin to signal EOF, (2) DSH bridge `quiesce()` runs: cancels all sessions, settles pending prompts as `cancelled`, drains continuable subagents, disposes all agents in parallel, awaits all results. (3) Process exits with code 0.
**When to use:** App shutdown / window close.
**Example:**
```dart
// Dart subprocess management:
final process = await Process.start(
  'node',
  ['<engine>/lib/bin.js', '--config', '<engine>/acp.cordis.yml'],
  workingDirectory: '<engine>',
  environment: {
    'DSH_HOME': dshHomePath,
    'DEEPSEEK_API_KEY': apiKey,  // from OS credential store, never to disk
    'DSH_PERMISSION_MODE': 'workspace-write',
  },
);

// On app exit:
process.stdin.close();  // signal EOF → DSH quiesce → clean exit
final exitCode = await process.exitCode;  // should be 0
// If timeout: process.kill(pid, ProcessSignal.sigterm);
```
[VERIFIED: `packages/acp/acp/src/index.ts` lines 357-410 — `quiesce()` function]

### Anti-Patterns to Avoid

- **Parsing DSH session logs as protocol:** The JSONL session log is for RB2 display only (status text extraction). It is NOT a protocol stream — its format has no compatibility promise (`SESSION_FORMAT_VERSION = 0`, pre-release).
- **Using `dsh web` or WebView:** User explicitly vetoed WebView. The ACP stdio seam is the only integration surface.
- **Batch approval:** The ACP bridge offers only `allow-once`/`reject-once` — no `allow-always`, no batch path. App must never synthesize one.
- **Auto-upgrading the engine:** DSH is pre-release with no compatibility promise. Upgrades require pin change → rebuild → real-machine regression → app version release.
- **Logging raw payloads to app logs:** Engine logs are reference-first. App logs must not contain customer document text or raw model payloads.

## ACP Protocol Contract (from DSH source + ACP SDK)

### Framing

- **Transport:** newline-delimited JSON (NDJSON) over stdio [VERIFIED: `node_modules/@agentclientprotocol/sdk/dist/stream.js`]
- **Each frame:** `JSON.stringify(message) + "\n"` — one compact JSON object per line
- **Stdout:** reserved for protocol frames only (no logger output) [VERIFIED: `examples/acp-agent/README.md`]
- **Stderr:** diagnostics only (logger output, warnings)
- **Protocol version:** 1 [VERIFIED: `node_modules/@agentclientprotocol/sdk/dist/schema/index.js` — `PROTOCOL_VERSION = 1`]

### Methods (client → server, AGENT_METHODS)

| Method | Params | Result | Behavior |
|--------|--------|--------|----------|
| `initialize` | `{protocolVersion: 1, clientCapabilities: {}}` | `{protocolVersion: 1, agentInfo: {name, version}, agentCapabilities: {promptCapabilities: {image: false, audio: false, embeddedContext: false}}, authMethods: []}` | Negotiates version; advertises baseline-only prompts. No session/editor/terminal/filesystem/MCP capability. |
| `authenticate` | — | void (no-op) | Server advertises no auth methods. |
| `session/new` | `{cwd: string (absolute), mcpServers: []}` | `{sessionId: string}` | Creates fresh agent. Rejects: non-absolute cwd, non-empty `additionalDirectories`, non-empty `mcpServers`. |
| `session/prompt` | `{sessionId: string, prompt: [{type: "text", text: string} \| {type: "resource_link", name, uri}]}` | `{stopReason: "end_turn" \| "cancelled" \| "max_tokens"}` | Concatenates text blocks; one in-flight per session; waits for whole-agent idle. Rejects: empty prompt, unsupported content (image/audio/embedded). |
| `session/cancel` | `{sessionId: string}` | void (notification, no response) | Cancels addressed agent; settles pending prompt as `cancelled`. Unknown ids are no-ops. |

### Methods (server → client, CLIENT_METHODS)

| Method | Params | Response | Behavior |
|--------|--------|----------|----------|
| `session/update` | `{sessionId, update: {sessionUpdate: "agent_message_chunk", content: {type: "text", text: string}}}` | — (notification) | One per non-empty text block in committed `assistant/message`. Raw deltas, tools, reasoning omitted. |
| `session/request_permission` | `{sessionId, toolCall: {toolCallId: string}, options: [{optionId: "allow-once", name: "Allow once", kind: "allow_once"}, {optionId: "reject-once", name: "Reject", kind: "reject_once"}]}` | `{outcome: {outcome: "selected", optionId: "allow-once" \| "reject-once"} \| {outcome: "cancelled"}}` | One-shot allow/reject for bridge-owned approval requests. Client may answer automatically. |

### Lifecycle guarantees

- One connection may own several sessions [VERIFIED: `packages/acp/acp/README.md`]
- Disconnect teardown: (1) reject new sessions/prompts, (2) settle pending prompts as `cancelled`, (3) drain continuable subagents child-first, (4) dispose all owned agents in parallel, (5) await all results. **Zero orphan processes.** [VERIFIED: `packages/acp/acp/src/index.ts` `quiesce()` function]
- `session/close` per-session is NOT implemented — one connection releases all sessions [VERIFIED: `packages/acp/acp/README.md` "Known Limitations"]
- Fresh sessions only — load, list, resume, delete, fork are unsupported [VERIFIED: same]

### Error handling

- Invalid params: `{code: -32602, message: "..."}` (e.g., "cwd must be an absolute path", "additionalDirectories is not supported", "mcpServers is not supported", "a prompt is already in flight for this session", "only text and resource_link prompt content is supported", "empty prompt")
- Internal error: `{code: -32603, message: "..."}` (e.g., "the ACP bridge has been disposed", "connection closed during session/new")
- Method not found: `{code: -32601, message: "..."}` [VERIFIED: `packages/sdk/protocol/README.md`]

## Subprocess Management in Dart

### `dart:io` Process API

```dart
// Start process
final process = await Process.start(
  executable,
  arguments,
  workingDirectory: workingDir,
  environment: env,
  runInShell: false,
);

// stdin: IOSink — write NDJSON frames
process.stdin.writeln(jsonEncode(request));

// stdout: Stream<List<int>> — read NDJSON frames
process.stdout
    .transform(utf8.decoder)
    .transform(const LineSplitter())
    .listen((line) => handleFrame(jsonDecode(line)));

// stderr: Stream<List<int>> — diagnostics
process.stderr
    .transform(utf8.decoder)
    .listen((line) => log.warning('DSH stderr: $line'));

// Exit code
final exitCode = await process.exitCode;

// Kill
process.kill(ProcessSignal.sigterm);  // graceful
// On Windows: ProcessSignal.sigterm maps to TerminateProcess
```

[ASSUMED — based on Dart `dart:io` documentation; Flutter not yet installed to verify]

### Windows-specific considerations

- **Process killing:** `Process.kill()` on Windows uses `TerminateProcess`. For graceful shutdown, close stdin first (EOF triggers DSH `quiesce()`), then wait for exit with a timeout, then `kill()` if needed.
- **Job objects:** Windows Job Objects can ensure child processes are killed when the parent dies. Dart's `dart:io` does NOT expose Job Objects directly. Options:
  1. Close stdin → wait for exit (preferred — DSH's `quiesce()` handles cleanup)
  2. Use `taskkill /PID <pid> /T /F` as fallback (kills process tree)
  3. P/Invoke Windows API for Job Objects (complex, probably unnecessary given DSH's clean teardown)
- **Environment variables:** `Process.start(environment: {...})` replaces the entire environment. Must include `PATH`, `SYSTEMROOT`, etc. from the parent environment plus DSH-specific vars.
- **Paths:** Use Windows-style paths (`%LOCALAPPDATA%\InkStatute\runtime\.dsh`). Dart's `Platform` provides `Platform.environment['LOCALAPPDATA']`.

[ASSUMED — Windows-specific Dart behavior; verify on Windows during implementation]

### Zero orphans assertion

The test strategy for DSH-02:
1. Spawn DSH process via `Process.start`
2. Send `initialize` → verify response (health probe)
3. Close stdin
4. Await `process.exitCode` with timeout (e.g., 10s)
5. Assert exit code == 0
6. Assert process is no longer in the process table
7. On timeout: `process.kill()` + fail test

For Windows: additionally assert no child `node.exe` processes remain (via `tasklist` or `wmic process where "ParentProcessId=<pid>"`).

## Mock ACP Server Fixtures

### Design

The mock ACP server is a Dart script that:
1. Reads NDJSON from stdin
2. Responds with scripted NDJSON on stdout
3. Implements the 7 ACP methods with deterministic responses
4. Can simulate `session/request_permission` for approval testing

### Fixture scenarios (from DSH snapshot tests)

| Fixture | Flow | Source |
|---------|------|--------|
| `handshake` | initialize → session/new | `examples/acp-agent/tests/snapshots/handshake/stdout.expected.jsonl` |
| `text_turn` | initialize → session/new → session/prompt → agent_message_chunk → end_turn | `examples/acp-agent/tests/snapshots/text-turn/stdout.expected.jsonl` |
| `escalation_approved` | initialize → session/new → session/prompt → request_permission → allow → agent_message_chunk → end_turn | `examples/acp-agent/tests/snapshots/escalation-approved/stdout.expected.jsonl` |
| `escalation_rejected` | initialize → session/new → session/prompt → request_permission → reject → agent_message_chunk → end_turn | `examples/acp-agent/tests/snapshots/escalation-rejected/stdout.expected.jsonl` |
| `cancel` | initialize → session/new → session/prompt → session/cancel → cancelled | `examples/acp-agent/tests/snapshots/cancel/stdout.expected.jsonl` |
| `reject_extra_dirs` | initialize → session/new with additionalDirectories → error | `examples/acp-agent/tests/snapshots/reject-extra-dirs/stdout.expected.jsonl` |

### Mock server pattern

```dart
// Scripted mock ACP server for testing acp_client
class MockAcpServer {
  final List<Map<String, dynamic>> _scriptedResponses = [];

  void handleRequest(Map<String, dynamic> request) {
    final method = request['method'] as String?;
    final id = request['id'];

    switch (method) {
      case 'initialize':
        _send({
          'jsonrpc': '2.0', 'id': id,
          'result': {
            'protocolVersion': 1,
            'agentInfo': {'name': 'mock-acp', 'version': '0.0.1'},
            'agentCapabilities': {
              'promptCapabilities': {'image': false, 'audio': false, 'embeddedContext': false}
            },
            'authMethods': [],
          }
        });
        break;
      case 'session/new':
        _send({'jsonrpc': '2.0', 'id': id, 'result': {'sessionId': 'mock-session-001'}});
        break;
      case 'session/prompt':
        // Send update notification, then prompt response
        _notify({'jsonrpc': '2.0', 'method': 'session/update', 'params': {
          'sessionId': request['params']['sessionId'],
          'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Mock response'}},
        }});
        _send({'jsonrpc': '2.0', 'id': id, 'result': {'stopReason': 'end_turn'}});
        break;
      // ... session/cancel, session/request_permission, etc.
    }
  }
}
```

[VERIFIED: fixture content from `examples/acp-agent/tests/snapshots/*/stdout.expected.jsonl`]

## Engine Release Pipeline

### `engines/dsh-pin.txt` format

```
# DSH pinned commit for InkStatute V4 engine
# Upgrade = change this file → rebuild → real-machine regression → app version release
47f943859bef60e4160492346772ded9b24f765a
```

[ASSUMED format — no existing file; design based on PRD §4.2]

### `scripts/build_dsh_release.sh` design

```bash
#!/usr/bin/env bash
set -euo pipefail

# Inputs
DSH_REPO="${DSH_REPO:-/path/to/deepseek-harness}"
PIN_FILE="engines/dsh-pin.txt"
VERSION="${1:?engine version required}"

# Read pinned commit
COMMIT=$(grep -v '^#' "$PIN_FILE" | head -1 | tr -d '[:space:]')
echo "Building DSH engine $VERSION from commit $COMMIT"

# Workspace
WORKDIR=$(mktemp -d)
git clone "$DSH_REPO" "$WORKDIR"
cd "$WORKDIR"
git checkout "$COMMIT"

# Build
pnpm install --frozen-lockfile
pnpm run build

# Assemble engine directory
ENGINE_DIR="engine-$VERSION"
mkdir -p "$ENGINE_DIR/lib"
cp packages/examples/acp-demo/lib/bin.js "$ENGINE_DIR/lib/"
cp packages/examples/acp-demo/lib/index.js "$ENGINE_DIR/lib/"
cp packages/examples/acp-demo/lib/invariant.js "$ENGINE_DIR/lib/"
# Copy all workspace dependency lib/ directories
# (This is the complex part — needs node_modules resolution)
cp -r node_modules/@deepseek-ai "$ENGINE_DIR/node_modules/"
cp -r node_modules/@agentclientprotocol "$ENGINE_DIR/node_modules/"
# ... other dependencies

# Copy product composition config
cp "$ORIGINAL_DIR/engines/acp.cordis.yml" "$ENGINE_DIR/"

# Zip
zip -r "engine-$VERSION.zip" "$ENGINE_DIR"

# Generate manifest
SHA256=$(sha256sum "engine-$VERSION.zip" | cut -d' ' -f1)
NODE_VERSION=$(node --version)
cat > "engine-manifest.json" << EOF
{
  "engine_version": "$VERSION",
  "dsh_commit": "$COMMIT",
  "node_version": "$NODE_VERSION",
  "sha256": "$SHA256",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Built engine-$VERSION.zip (sha256: $SHA256)"
```

[ASSUMED design — no existing script; based on PRD §4.2 and V5 findings]

**Key challenge:** The built bin is a Node.js ESM script that imports workspace packages. The packaging script must either:
1. Copy the entire `node_modules` tree of built workspace packages (large but simple)
2. Use `tsdown` bundling to produce a self-contained bundle (needs investigation)
3. Use `npm pack` / `pnpm pack` for each dependency and assemble (complex)

Option 1 is recommended for Phase 112 (simplest, most reliable). Optimization can come later.

### `engines/acp.cordis.yml` design

Based on `examples/acp-agent/cordis.yml` but configured for the V4 product:

```yaml
# InkStatute V4 engine ACP composition
# Approval stack: terminal/execute_code default deny → escalate to user card

- id: llm-deepseek
  name: '@deepseek-ai/dsh-llm-deepseek'
  config:
    thinking: enabled
    reasoningEffort: max
    models:
      - id: deepseek-v4-flash
      - id: deepseek-v4-pro

# Sandbox: workspace-write (allow file writes within session cwd)
- id: sandbox
  name: '@deepseek-ai/dsh-sandbox-local'

- id: sandbox-policy
  name: '@deepseek-ai/dsh-sandbox-policy'
  config:
    mode: workspace-write
    workspaceRoot: !!js process.cwd()

- id: subprocess
  name: '@deepseek-ai/dsh-subprocess-local'

- id: bash
  name: '@deepseek-ai/dsh-bash-sandbox'
  config:
    timeoutMs: 60000

# Approval: ASK → escalate to session/request_permission
# (terminal/execute_code requests surface as approval cards)
- id: approval
  name: '@deepseek-ai/dsh-user-approval'
  config:
    policy: ask

# ACP automation server
- id: acp-agent
  name: '@deepseek-ai/dsh-acp-demo'
  config:
    provider: deepseek-official
    model: deepseek-v4-pro
    persistenceRoot: '${DSH_HOME}/sessions'
    persistenceCompression: zstd
    persona: |
      You are a legal assistant powered by the {{model}} model.
      Your working directory is {{cwd}}.
      # ... legal guardrails persona (Phase 113)
    workspaceContext:
      maxBytes: 65536

# ... (skill-filesystem, fs-sandbox, tools, etc. — subset of cordis.yml)
```

[ASSUMED design — based on `examples/acp-agent/cordis.yml` with product-specific modifications]

## V4 Gates Runner

### `scripts/run_v4_gates.py` design

```python
#!/usr/bin/env python3
"""V4 gate runner: dart analyze + flutter test + engine manifest + mock E2E + meta-test."""

import subprocess, sys, json, os
from pathlib import Path

def run(cmd, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"FAIL: {' '.join(cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result

# 1. dart analyze
run(["dart", "analyze", "apps/flutter_app"])

# 2. flutter test
run(["flutter", "test", "apps/flutter_app"])

# 3. Engine manifest validation
manifest = json.loads(Path("engine-manifest.json").read_text())
required = {"engine_version", "dsh_commit", "node_version", "sha256", "built_at"}
assert required.issubset(manifest.keys()), f"Missing manifest fields: {required - manifest.keys()}"

# 4. Mock E2E (acp_client tests with mock fixtures)
run(["flutter", "test", "apps/flutter_app/packages/acp_client"])

# 5. Meta-test: every new Dart lib/ dir has tests
lib_dirs = []
for p in Path("apps/flutter_app/lib").rglob("*"):
    if p.is_dir() and (p / "lib").exists():
        lib_dirs.append(p)
for lib_dir in lib_dirs:
    test_dir = lib_dir.parent / "test"
    if not test_dir.exists():
        print(f"FAIL: {lib_dir} has no test/ directory")
        sys.exit(1)

print("All V4 gates passed.")
```

[ASSUMED design — no existing script; based on GATE-01/GATE-02 requirements]

### Meta-test for test coverage (GATE-02)

The meta-test walks `apps/flutter_app/lib/` and `apps/flutter_app/packages/*/lib/` directories and asserts each has a corresponding `test/` directory with at least one `_test.dart` file.

## Approval Security Three-State

### The three states

| State | Condition | App Action |
|-------|-----------|------------|
| **Deny** | Unknown permission kind | Auto-reject; never show to user |
| **Render card** | terminal / execute_code kind | Show approval card with tool name + reason; user selects allow-once or reject-once |
| **No batch** | Any kind | No "allow all" / "remember" / "always" option exists in the protocol |

### How this maps to ACP `session/request_permission`

The ACP bridge sends `session/request_permission` with:
```json
{
  "options": [
    {"optionId": "allow-once", "name": "Allow once", "kind": "allow_once"},
    {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"}
  ]
}
```

There is no `allow-always` option. The bridge never infers a durable grant from an unknown client response. [VERIFIED: `packages/acp/acp/src/index.ts` lines 191-206, `packages/interaction/user-approval/README.md`]

### App-side policy implementation

```dart
// App-side approval policy
PermissionOutcome handlePermissionRequest(RequestPermissionRequest request) {
  // The ACP bridge only sends allow-once/reject-once options.
  // The "kind" field on options is always "allow_once" or "reject_once".
  // There is no "terminal" or "execute_code" kind in the ACP permission options.
  //
  // The app's three-state policy applies to the TOOL CALL that triggered the
  // permission request, not to the permission options themselves:
  // 1. If the tool call is for an unknown kind → auto-reject (return reject-once)
  // 2. If the tool call is terminal/execute_code → render user card
  // 3. Never offer batch approval (the protocol doesn't support it)

  // For Phase 112 mock testing: the mock client always returns a scripted answer.
  // For Phase 116+: the app UI renders the card.
  return PermissionOutcome.selected('reject-once');  // default deny
}
```

**Important nuance:** The ACP `session/request_permission` options are always `allow-once`/`reject-once` — they do not carry tool-kind information. The tool kind is implicit in the approval request that triggered the escalation (the bridge's `approval/request` listener fires for sandbox escalation retries). The app's three-state policy (unknown → deny, terminal → card, no batch) is an app-level decision based on what triggered the permission, not on the ACP options themselves.

[VERIFIED: `packages/acp/acp/src/index.ts` lines 191-206, `packages/interaction/user-approval/README.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-RPC framing | Custom frame parser | NDJSON (newline-delimited JSON) | ACP uses NDJSON, not Content-Length; trivial to implement in Dart with `LineSplitter` |
| Agent loop | Custom turn/step/tool loop | DSH engine (inherited) | Agent loop is a solved problem in DSH; self-rolling is the v3.x mistake |
| Session persistence | Custom JSONL writer | DSH JSONL persistence (inherited) | Engine owns session logs; app only reads for RB2 display |
| Skill discovery | Custom skill scanner | DSH skill-filesystem (inherited) | Engine owns skill discovery, catalog rendering, and hot-refresh |
| Approval stack | Custom approval UI logic | DSH approval seam + ACP request_permission | Engine owns the approval waterfall; app only renders the card |
| SQLite access | Raw SQL queries | drift ORM | PRD-listed; type-safe, migration-safe |
| Process management | Custom process tracker | `dart:io` Process API | stdlib; sufficient for spawn/kill/exit |

**Key insight:** Phase 112 builds only two things: (1) a Dart ACP client that speaks the wire protocol, and (2) a subprocess manager that spawns/kills the DSH engine. Everything else is inherited from DSH.

## Common Pitfalls

### Pitfall 1: Content-Length framing assumption
**What goes wrong:** Implementing LSP-style Content-Length headers instead of NDJSON.
**Why it happens:** LSP is the most common JSON-RPC over stdio protocol; developers assume ACP follows the same framing.
**How to avoid:** ACP uses NDJSON (newline-delimited JSON). Each message is one line. Use `LineSplitter` in Dart. [VERIFIED: `node_modules/@agentclientprotocol/sdk/dist/stream.js`]
**Warning signs:** Process hangs after sending initialize — the server is waiting for a `\n` that never comes, or parsing Content-Length headers that don't exist.

### Pitfall 2: Stdout contamination
**What goes wrong:** The DSH engine sends non-JSON output on stdout, breaking the protocol stream.
**Why it happens:** A plugin or logger writes to stdout instead of stderr.
**How to avoid:** The ACP bridge installs no stdout logger; leaf additions must use stderr. The `acp.e2e.ts` test verifies stdout purity (every line must parse as JSON). [VERIFIED: `examples/acp-agent/tests/acp.e2e.ts` "emits only framed JSON-RPC on stdout"]
**Warning signs:** JSON parse errors in the client; `session/update` notifications with garbled content.

### Pitfall 3: Orphan processes on Windows
**What goes wrong:** App exits but DSH child processes (subprocess, bash) remain running.
**Why it happens:** `Process.kill()` on Windows kills only the immediate process, not the process tree. DSH may spawn child processes (bash, subprocess groups).
**How to avoid:** Close stdin first → DSH `quiesce()` drains all descendants → clean exit. Only use `kill()` as fallback after timeout. On Windows, consider `taskkill /PID <pid> /T /F` for tree kill. [VERIFIED: `packages/acp/acp/src/index.ts` `quiesce()` function]
**Warning signs:** `node.exe` processes in Task Manager after app close; port conflicts on restart.

### Pitfall 4: Non-absolute cwd in session/new
**What goes wrong:** `session/new` rejects with "cwd must be an absolute path".
**Why it happens:** Passing a relative path as cwd.
**How to avoid:** Always resolve to absolute path before sending. On Windows: `File(path).absolute.path`. [VERIFIED: `packages/acp/acp/src/index.ts` `validateSessionParams` function]
**Warning signs:** Error code -32602 with message "cwd must be an absolute path".

### Pitfall 5: Engine packaging missing workspace dependencies
**What goes wrong:** Built bin fails to start with `ERR_MODULE_NOT_FOUND` for `@deepseek-ai/dsh-app-boot`.
**Why it happens:** The built bin imports workspace packages by name; the packaging script didn't include their built `lib/` directories.
**How to avoid:** Include the entire `node_modules/@deepseek-ai/` and `node_modules/@agentclientprotocol/` trees in the engine zip. Or investigate `tsdown` bundling for a self-contained bundle. [VERIFIED: built bin imports `@deepseek-ai/dsh-app-boot` — `packages/examples/acp-demo/lib/bin.js` line 2]
**Warning signs:** `Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@deepseek-ai/dsh-app-boot'`

### Pitfall 6: Snapshot test filter mismatch
**What goes wrong:** Running `pnpm run test:snapshot -t "acp"` skips all tests.
**Why it happens:** The `-t` filter matches test names across all files, but the snapshot suite uses `describe.concurrent` which may interact differently with the filter. Running the specific file works.
**How to avoid:** Run snapshot tests by file path: `DSH_SNAPSHOT=replay npx vitest run --config vitest.snapshot.config.ts examples/acp-agent/tests/acp.snapshot.ts`. [VERIFIED: observed during V1 verification]
**Warning signs:** All tests show as "skipped" with 0ms duration.

## Code Examples

### Complete ACP client handshake (Dart)

```dart
// Source: ACP protocol verified from @agentclientprotocol/sdk + DSH bridge source

import 'dart:convert';
import 'dart:io';

class AcpClient {
  final Process _process;
  int _nextId = 1;
  final Map<int, Completer<Map<String, dynamic>>> _pending = {};

  AcpClient(this._process) {
    _process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .where((line) => line.trim().isNotEmpty)
        .listen(_handleMessage);
  }

  void _handleMessage(String line) {
    final msg = jsonDecode(line) as Map<String, dynamic>;
    final id = msg['id'];

    if (id != null && msg['method'] != null) {
      // Server→client request (e.g., session/request_permission)
      _handleServerRequest(msg);
    } else if (id != null) {
      // Response to our request
      final completer = _pending.remove(id);
      completer?.complete(msg);
    } else if (msg['method'] != null) {
      // Notification (e.g., session/update)
      _handleNotification(msg);
    }
  }

  Future<Map<String, dynamic>> _call(String method, Map<String, dynamic> params) {
    final id = _nextId++;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _process.stdin.writeln(jsonEncode({
      'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params,
    }));
    return completer.future;
  }

  Future<Map<String, dynamic>> initialize() =>
      _call('initialize', {'protocolVersion': 1, 'clientCapabilities': {}});

  Future<String> newSession(String cwd) async {
    final resp = await _call('session/new', {'cwd': cwd, 'mcpServers': []});
    return resp['result']['sessionId'] as String;
  }

  Future<String> prompt(String sessionId, String text) async {
    final resp = await _call('session/prompt', {
      'sessionId': sessionId,
      'prompt': [{'type': 'text', 'text': text}],
    });
    return resp['result']['stopReason'] as String;
  }

  void cancel(String sessionId) {
    _process.stdin.writeln(jsonEncode({
      'jsonrpc': '2.0', 'method': 'session/cancel',
      'params': {'sessionId': sessionId},
    }));
  }

  void _handleNotification(Map<String, dynamic> msg) {
    if (msg['method'] == 'session/update') {
      final params = msg['params'];
      final update = params['update'];
      if (update['sessionUpdate'] == 'agent_message_chunk') {
        final text = update['content']['text'];
        // Deliver committed text to app
      }
    }
  }

  void _handleServerRequest(Map<String, dynamic> msg) {
    if (msg['method'] == 'session/request_permission') {
      // App policy: default deny, render card for terminal/execute_code
      _process.stdin.writeln(jsonEncode({
        'jsonrpc': '2.0', 'id': msg['id'],
        'result': {'outcome': {'outcome': 'selected', 'optionId': 'reject-once'}},
      }));
    }
  }

  Future<void> close() async {
    _process.stdin.close();
    await _process.exitCode.timeout(Duration(seconds: 10),
        onTimeout: () => _process.kill());
  }
}
```

[VERIFIED: protocol shapes from `@agentclientprotocol/sdk` + DSH bridge source + snapshot fixtures]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tauri + SolidJS desktop | Flutter native desktop | V4 decision (2026-08-13) | No WebView; native UI; Dart instead of TypeScript |
| Self-built agent core (Python) | DSH engine (TypeScript/Node) | V4 decision (2026-08-13) | No loop maintenance; inherit all engine capabilities |
| ACP client in TypeScript | ACP client in Dart | V4 decision (2026-08-13) | New implementation from protocol spec; only 7 methods |
| Content-Length framing (LSP) | NDJSON framing (ACP) | ACP spec v1 | Simpler framing; no header parsing |

**Deprecated/outdated:**
- `packages/acp-client` (TypeScript): frozen (LEG-01), not used in V4
- `packages/agent-core` (Python): frozen (LEG-01), not used in V4
- `apps/desktop` (Tauri/SolidJS): frozen (LEG-01), not used in V4

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Flutter | DSH-01, DSH-02, GATE-01, GATE-02 | ✗ | — | Install in Wave 0 |
| Dart | DSH-01, DSH-02 | ✗ | — | Bundled with Flutter |
| Node.js | DSH-03 (engine build) | ✓ | v24.16.0 | — |
| pnpm | DSH-03 (engine build) | ✓ | 11.21.0 | — |
| Python 3 | GATE-01 (gate runner) | ✓ | 3.14.6 | — |
| DSH repo | V1-V5 verification, DSH-03 | ✓ | commit 47f943859b | — |
| `@agentclientprotocol/sdk` | Protocol reference | ✓ | 0.25.1 | — |
| DEEPSEEK_API_KEY | Real model calls | ✗ | — | Use mock:llm for testing; snapshot tests are keyless |

**Missing dependencies with no fallback:**
- Flutter/Dart SDK: Must be installed before implementation can begin. This is a Wave 0 blocking gap.

**Missing dependencies with fallback:**
- DEEPSEEK_API_KEY: Not needed for Phase 112 (mock ACP server fixtures + keyless snapshot tests cover all protocol testing). Real API key is needed for Phase 118+ (GATE-03 real-API E2E).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Flutter/Dart `test` (bundled with Flutter) |
| Config file | `apps/flutter_app/pubspec.yaml` (flutter_test dependency) — none yet (Wave 0) |
| Quick run command | `flutter test apps/flutter_app/packages/acp_client` |
| Full suite command | `flutter test apps/flutter_app` + `dart analyze apps/flutter_app` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DSH-01 | ACP initialize handshake | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/new with absolute cwd | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/new rejects non-absolute cwd | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/new rejects non-empty additionalDirectories | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/new rejects non-empty mcpServers | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/prompt single in-flight rejection | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/prompt text block concatenation | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/cancel | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/update text block aggregation | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-01 | session/request_permission policy hook | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ Wave 0 |
| DSH-02 | DSH subprocess spawn + health probe | integration | `flutter test apps/flutter_app/test/engine/dsh_process_test.dart` | ❌ Wave 0 |
| DSH-02 | Zero orphan process on exit | integration | `flutter test apps/flutter_app/test/engine/dsh_process_test.dart` | ❌ Wave 0 |
| DSH-02 | DSH_HOME environment injection | integration | `flutter test apps/flutter_app/test/engine/dsh_process_test.dart` | ❌ Wave 0 |
| DSH-03 | Engine manifest validation | unit | `python3 scripts/run_v4_gates.py` | ❌ Wave 0 |
| DSH-03 | Engine build produces zip + manifest | smoke | `bash scripts/build_dsh_release.sh <version>` | ❌ Wave 0 |
| DSH-04 | Unknown kind → deny | unit | `flutter test packages/acp_client/test/approval_test.dart` | ❌ Wave 0 |
| DSH-04 | terminal/execute_code → render card | unit | `flutter test packages/acp_client/test/approval_test.dart` | ❌ Wave 0 |
| DSH-04 | No batch approval path | unit | `flutter test packages/acp_client/test/approval_test.dart` | ❌ Wave 0 |
| GATE-01 | dart analyze passes | gate | `dart analyze apps/flutter_app` | ❌ Wave 0 |
| GATE-01 | flutter test passes | gate | `flutter test apps/flutter_app` | ❌ Wave 0 |
| GATE-01 | Engine manifest validation | gate | `python3 scripts/run_v4_gates.py` | ❌ Wave 0 |
| GATE-02 | Meta-test: every lib/ dir has tests | meta | `python3 scripts/run_v4_gates.py` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `flutter test apps/flutter_app/packages/acp_client` (quick — ACP client unit tests only)
- **Per wave merge:** `flutter test apps/flutter_app` + `dart analyze apps/flutter_app` + `python3 scripts/run_v4_gates.py` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] Flutter SDK install — blocking; all Dart/Flutter work depends on it
- [ ] `apps/flutter_app/` — Flutter project does not exist; `flutter create --platforms=windows` needed
- [ ] `apps/flutter_app/packages/acp_client/` — Dart package does not exist
- [ ] `apps/flutter_app/packages/acp_client/test/` — test directory + fixtures
- [ ] `apps/flutter_app/test/engine/` — DSH subprocess manager tests
- [ ] `engines/dsh-pin.txt` — pin file does not exist
- [ ] `engines/acp.cordis.yml` — product composition config does not exist
- [ ] `scripts/build_dsh_release.sh` — build script does not exist
- [ ] `scripts/run_v4_gates.py` — gate runner does not exist
- [ ] `pubspec.yaml` — no Flutter project config exists

*(Everything is a Wave 0 gap — this is the first V4 phase with no existing Flutter/Dart infrastructure.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth (single-user desktop app); API key is the only credential |
| V3 Session Management | yes | ACP session lifecycle (session/new, session/cancel); DSH owns session state |
| V4 Access Control | yes | Approval three-state policy (deny unknown, card for terminal, no batch) |
| V5 Input Validation | yes | ACP protocol validation (absolute cwd, empty mcpServers, text-only prompts) |
| V6 Cryptography | yes | sha256 for engine manifest + content packages (Phase 115); OS credential store for API key |

### Known Threat Patterns for Flutter desktop + DSH subprocess

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage to logs/telemetry | Information Disclosure | OS credential store; env injection; grep assertion for zero plaintext keys |
| Orphan processes after app exit | Denial of Service | stdin close → DSH quiesce → clean exit; PID assertion test |
| Malicious engine zip (tampered) | Tampering | sha256 verification in manifest; no auto-upgrade |
| Unsanitized model output in UI | XSS equivalent | Flutter native rendering (no HTML/DOM); output boundary: only committed assistant text |
| Unauthorized tool execution | Elevation of Privilege | Approval three-state; terminal default deny; no batch approval |
| Session log data leakage | Information Disclosure | Reference-first logging; raw payloads not in app logs; JSONL stays in DSH_HOME |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Flutter `dart:io` Process API supports stdin/stdout streaming on Windows | Subprocess Management | Would need platform channel or alternative; LOW risk (standard Dart API) |
| A2 | `Process.kill()` on Windows kills only immediate process, not tree | Subprocess Management | May need `taskkill /T` or Job Objects; MEDIUM risk |
| A3 | `engines/dsh-pin.txt` format is a single commit SHA with comments | Engine Release Pipeline | Format may need adjustment; LOW risk (we define the format) |
| A4 | `build_dsh_release.sh` can copy `node_modules/@deepseek-ai/` for all workspace deps | Engine Release Pipeline | May need more complex dependency resolution; MEDIUM risk |
| A5 | drift/sqlite3 are the right choices for local SQLite in Flutter | Standard Stack | PRD-listed; LOW risk |
| A6 | `scripts/run_v4_gates.py` in Python is the right choice for gate runner | V4 Gates Runner | Could be Dart instead; LOW risk (Python already used for v3 gates) |
| A7 | Windows Job Objects are not needed for zero-orpharn guarantee | Subprocess Management | DSH quiesce() handles cleanup; MEDIUM risk (verify on Windows) |

**If this table is empty:** N/A — 7 assumptions identified, all LOW-MEDIUM risk.

## Open Questions

1. **Engine packaging: bundle vs. copy node_modules**
   - What we know: Built bin imports workspace packages by name; `node_modules/@deepseek-ai/` tree is needed
   - What's unclear: Whether `tsdown` can produce a self-contained bundle, or if we must copy the entire dependency tree
   - Recommendation: Start with copying `node_modules/@deepseek-ai/` + `node_modules/@agentclientprotocol/` (simplest); investigate bundling optimization later

2. **Windows process tree kill**
   - What we know: DSH `quiesce()` handles clean teardown on stdin close; `Process.kill()` on Windows uses `TerminateProcess`
   - What's unclear: Whether DSH child processes (bash, subprocess groups) are reliably killed by `quiesce()` on Windows
   - Recommendation: Implement stdin-close-first approach; add `taskkill /T` fallback; test on Windows in Phase 118

3. **Flutter installation method**
   - What we know: Flutter is not installed; needed for all Phase 112 work
   - What's unclear: Whether to install via `snap` (Linux dev), `apt`, or manual download; Windows dev environment setup
   - Recommendation: Install via official Flutter SDK; add as Wave 0 task

## Sources

### Primary (HIGH confidence)
- `@agentclientprotocol/sdk@0.25.1` source code (`node_modules/@agentclientprotocol/sdk/dist/`) — protocol schema, framing, methods
- `packages/acp/acp/README.md` — ACP contract (source of truth per AGENTS.md)
- `packages/acp/acp/src/index.ts` — bridge implementation (initialize, session/new, session/prompt, session/cancel, session/update, request_permission, quiesce)
- `packages/acp/acp/src/codec.ts` — turn-end mapping, prompt flattening
- `packages/session/session-persistence-jsonl/README.md` — JSONL log format, path pattern, crash semantics
- `packages/core/session/src/types.ts` — `SESSION_FORMAT_VERSION = 0`
- `packages/skill/skill-filesystem/README.md` — skill discovery roots, customSkillDirs, watcher
- `packages/skill/tool-skill/README.md` — skill catalog rendering into model prefix
- `packages/interaction/user-approval/README.md` — approval seam, policy, one-shot grants
- `examples/acp-agent/cordis.yml` — ACP composition config (approval, sandbox, persistence)
- `examples/acp-agent/README.md` — ACP example docs, session workspaces, permissions
- `examples/acp-agent/tests/snapshots/*/stdout.expected.jsonl` — verified protocol fixtures
- `packages/examples/acp-demo/package.json` — bin name, exports, dependencies
- `packages/examples/acp-demo/src/bin.ts` — bin entry point
- Live mock-LLM ACP flow test (2026-08-13) — full protocol verified
- `DSH_SNAPSHOT=replay vitest run` (2026-08-13) — 85 snapshot tests passed
- `pnpm run build` (2026-08-13) — built bin confirmed
- Built bin initialize test (2026-08-13) — built bin responds to initialize

### Secondary (MEDIUM confidence)
- `docs/requirements/V4-PRD.md` — product specification (source of truth)
- `.planning/research/V4-SELECTION.md` §7 — V1-V5 verification items
- `AGENTS.md` (inkstatute-suite) — binding architecture decisions
- `AGENTS.md` (deepseek-harness) — DSH conventions, pre-release stance

### Tertiary (LOW confidence)
- Dart `dart:io` Process API behavior on Windows — [ASSUMED] based on documentation, not verified (Flutter not installed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Flutter is user-selected; DSH verified by source + tests
- Architecture: HIGH — ACP protocol fully documented from SDK + bridge source; V1-V5 all closed
- Pitfalls: HIGH — identified from real test runs and source code analysis
- Subprocess management: MEDIUM — Dart API is standard but Windows behavior not yet verified
- Engine packaging: MEDIUM — build verified but packaging script is designed, not tested

**Research date:** 2026-08-13
**Valid until:** 2026-09-13 (30 days — DSH is pre-release, but pinned commit is stable)
