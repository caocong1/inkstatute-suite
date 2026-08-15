# V5 选型研究：Tauri + SolidJS + DSH 三面接入

**Researched:** 2026-08-15
**Scope:** 为 V5（产品层从 Flutter 转 Tauri + SolidJS）提供选型证据。
**方法:** 全部结论来自本机实测，非文档转述。实测环境 macOS 25.5 · Node v22.21.1 · DSH 0.1.0-rc.6 · registry.npmmirror.com。
**Overall confidence:** HIGH（11 项实验均在本机跑通并留有可复现命令）

> **路径更正**：V4 文档中的 `/home/sorawatcher/...` 在当前开发机不存在。四个仓库实际位于
> `/Users/dongli/Workspace/{inkstatute-suite, lawyer-desktop, deepseek-harness, ai-for-china-legal}`。
> `scripts/build_dsh_release.sh` 里的 `DSH_REPO` 默认值仍是旧路径，需一并修正（该脚本本身在 V5 退役）。

## 0. 结论速览

1. **基座 = `apps/desktop` + `packages/ui-core`**，不是 lawyer-desktop（另一仓库），也不是新建项目。
2. **UI 复制成本已付清**：`packages/ui-core` 是 lawyer-desktop UI 的完整移植，主题文件逐字节相同。
3. **组件已解耦在正确的缝上**：只认 `RenderState`，由 `event-reducer.ts` 从 15 种统一事件推导，而这套词汇与 DSH 原生会话事件近乎 1:1。
4. **ACP 做控制面 + 会话日志做观测面**，撤销 V4 的「工具活动不可见」取舍（DP-2）。
5. **npm lockfile 装配替代 170MB zip 管线**，引擎更新从「禁自动」变为「半自动可行」。

## 1. 路线对比

| 路线 | 需删除 | 需重写 | 需新增 | 结论 |
|---|---|---|---|---|
| A. 改 lawyer-desktop | ~10,000 Rust（共 15,323） | ~2,300 TS（api.ts + conversation.ts） | ~2,050 Rust | ❌ 跨仓库；引擎/预设/技能/内容包都不在该仓 |
| B. 新建项目复用 UI | — | ~1,500 TS（外壳重搭） | ~2,050 Rust | ❌ 重复造 `apps/desktop` 已有的 3,096 行 Rust 外壳、适配器、迁移、能力声明与测试 |
| **A′. 改 `apps/desktop`** | ~1,100 TS + ~280 Rust | **0**（reducer 与组件原样） | ~2,050 Rust + ~700 TS | ✅ **V5** |

## 2. 实测证据

### E1 — `packages/ui-core` 是 lawyer-desktop UI 的逐字节移植

```
diff lawyer-desktop/src/themes/molv-tokens.css  ui-core/src/themes/molv-tokens.css  → 相同
diff lawyer-desktop/src/themes/molv-base.css    ui-core/src/themes/molv-base.css    → 相同
```

9 个组件 CSS（ChatPanel · DocPreview · ConversationDrawer · TitleBar · HomePage · MentionComposer ·
CitationPanel · AgentTracePanel · MessageFeedback）经 `tr -d '\r'` 规范化换行符后**全部相同**。
差异仅为 lawyer-desktop 侧是 CRLF。ui-core 另有 lawyer-desktop 没有的 `ClarificationCard`。

规模：ui-core 12,576 行（TS/TSX/CSS），lawyer-desktop 前端 14,496 行（含测试与 app 层）。

### E2 — 组件已与后端解耦

`ui-core/src/components/ChatPanel.tsx` 文件头自述：

> Stripped all platform-specific dependencies (dialog, webview, invoke).
> Receives state via props from the event reducer (RenderState). Uses adapter interfaces.

`event-reducer.ts`（421 行）是纯函数 `(state, RunEventEnvelope) → RenderState`，已有 fixtures 与测试。
统一事件 15 种：`session.started` · `message.delta` · `message.completed` · `thought.delta` ·
`tool_call.started` · `tool_call.delta` · `tool_call.completed` · `plan.updated` · `phase.changed` ·
`elicitation.requested` · `permission.requested` · `artifact.created` · `citation.recorded` ·
`run.state_changed` · `error`。

`packages/platform-sdk-ts/src/events.ts` **零 import**，是纯类型模块，可与 HTTP 客户端完全切割。

### E3 — DSH 已公开发布 npm

`@deepseek-ai/dsh` 0.1.0-rc.6 发布于 2026-08-13（晚于 V4 选型研究）。
`acp-demo` 及 13 个组合插件（`dsh-llm-deepseek` · `dsh-sandbox-local` · `dsh-sandbox-policy` ·
`dsh-subprocess-local` · `dsh-bash-sandbox` · `dsh-user-approval` · `dsh-token-meter` ·
`dsh-compaction-basic` · `dsh-session-projection` · `dsh-fs-sandbox` · `dsh-fs-observation-policy` ·
`dsh-tool-fs` · `dsh-tool-todo` · `dsh-repeat-tool-reminder`）全部在册。

### E4 — npm 装配可替代 zip 管线（决定性实验）

```bash
npm install @deepseek-ai/dsh-acp-demo@0.1.0-rc.6 <13 个插件同版本>
# → added 87 packages in 9s，85MB
cp engines/acp.cordis.yml .            # 未经任何修改
node node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js --config acp.cordis.yml
```

握手结果：

```
initialize  → {"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp","version":"0.0.1"},...}
session/new → {"sessionId":"..."}
```

对比 `scripts/build_dsh_release.sh`：整仓克隆 + pnpm install + pnpm build + `pnpm deploy --legacy`
+ 约 300 行符号链接手术（递归复制 pnpm store 条目、重写 workspace 相对软链、删残链），产出 170MB zip。

### E5 — 全链路可达真实模型

`session/prompt` 返回 `Authentication Fails, Your api key: ****-key is invalid`（用的是假 key）。
证明 agent loop → 适配器 → HTTP 传输 → DeepSeek 官方端点整条链路完整。

### E6 — ACP 面确实只有已提交文本

源码 `packages/acp/acp/src/index.ts` 约 152 行注释与实现：

> Emit only committed assistant text. Raw chunks, reasoning, tools, plans, titles,
> and retry markers are presentation or trace data and stay off the automation wire.

`ctx.on('session/event', ...)` 只在 `event.type === 'assistant/message'` 时发 `agent_message_chunk`。
README「Known Limitations」明列：**Fresh sessions only**（load/list/resume/delete/fork 全不支持）。

### E7 — 会话 JSONL 是完整的第二通道

配 `packChunks: false` + `persistenceCompression: none` 后写出明文 NDJSON。一次失败轮次即产出 14 行，
`seq` 从 0 连续：

```
session(头) · agent/inbox/spliced · turn/start · step/start · user/message ×3
· session/title · request/header · request/context · assistant/chunk · step/end · turn/end
```

`request/context` 实测 `{"provider":"deepseek-official","model":"deepseek-v4-pro","contextWindow":1000000}`
—— 1M 上下文是「回灌历史续接对话」可行的量化依据。

`assistant/chunk` 的 chunk 联合类型（源码 `packages/llm/llm/src/types.ts:291`）：
`block-start` · `text-delta` · `reasoning-delta` · `tool-call-delta` · `block-end` · `usage` · `finish`。

### E8 — 会话列表与全文搜索白送

引擎自动生成 `session-query.db`：

```sql
CREATE TABLE persisted_sessions (id TEXT PRIMARY KEY, version, created_at, cwd,
  parent_session, seed_length, delegation_depth, agent_preset, revision, generation) STRICT;
CREATE VIRTUAL TABLE persisted_docs USING fts5(text, session_id, seq, type, time,
  surface, codepoint_length, tokenize='unicode61');
```

### E9 — V4 配置的落盘缺陷

`persistenceRoot: '${DSH_HOME}/sessions'` 中的 `${DSH_HOME}` **不被 Cordis 展开**。
实测在引擎工作目录下建出了名为 `${DSH_HOME}` 的字面量目录，会话日志与 `session-query.db` 全落在里面
—— 引擎目录整体替换时连同历史一并抹掉。

修法已实测通过（配置本就使用 `!!js` 标签，见 `sandbox-policy.workspaceRoot`）：

```yaml
persistenceRoot: !!js process.env.DSH_HOME + '/sessions'
```

### E10 — 多会话与取消（架构承重点）

一条 ACP 连接创建 3 个会话成功；对其中 2 个并发 `session/prompt`，各自独立结算；
每个会话在 `<root>/--<规范化 cwd>--/<sessionId>/session.jsonl` 有独立日志目录。

**取消的调用形式是陷阱**：

```
session/cancel 作为请求（带 id） → {"code":-32601,"message":"Method not found"}   ❌ 静默失败
session/cancel 作为通知（无 id） → in-flight prompt 立即结算 {"stopReason":"cancelled"}  ✅
```

（ACP SDK `acp.d.ts:442`：「This is a notification sent by the client to cancel an ongoing prompt turn.」）

### E11 — lockfile 可驱动 Rust 侧装配

`package-lock.json` v3：**104 条**，**零嵌套 `node_modules`**（树全平），
100% 带 `resolved` URL 与 sha512 `integrity`。

体积分布：85MB 中 58MB 是 `node-pty/prebuilds`（darwin-arm64 · darwin-x64 · win32-arm64 · win32-x64
四平台预编译）。只留 `win32-x64` 后引擎树约 42MB。

**dist-tag 陷阱**：`@deepseek-ai/dsh-*` 的 `latest` 指向 `0.0.1-rc.1`（旧），`next` 才是 `0.1.0-rc.6`。
裸装会静默拿到旧版 → 必须钉精确版本号。

## 3. 被否决的方案

### 3.1 SDK JSON-RPC 缝（`@deepseek-ai/dsh-sdk-jsonrpc-server`）

它「streams every durable fact as `session.event`」，正是 ACP 丢掉的那些。否决理由（均出自其官方 README）：

- **无权限通道**：「Server→client requests are dead capability — the server never sends one」→ 批准卡片无法实现，违反「法律护栏不可绕过」硬约束。
- **无取消、无会话关闭**：「a client abandons a turn by closing the runtime process」→ 律师中止只能杀进程。
- **无版本协商**：`serverInfo.version` 是未校验的 `0.0.1`，且明示「pre-release stance, no compatibility promise」。

两条缝都要独占 stdout，不可并存。

### 3.2 自写 DSH 事件转发插件

技术可行（`ctx.on('session/event')` 是公开缝），但会引入需随 DSH 版本维护的 TypeScript 资产。
官方持久化插件已经在写这些数据，读文件即可 —— 选更无聊的方案。

### 3.3 引擎常驻（跨 app 关闭存活）

可完美解决会话续接，但破坏零孤儿进程保证（V4 DSH-02 硬要求），且引擎升级时进程冲突难处理。
改用回灌方案，1M 上下文使其成本可接受。

## 4. 顺带发现的缺陷

| # | 缺陷 | 位置 | 修法 |
|---|---|---|---|
| D1 | `${DSH_HOME}` 不展开，会话历史落在引擎目录 | `engines/acp.cordis.yml` | `!!js process.env.DSH_HOME + '/sessions'`（已验证） |
| D2 | Google Fonts CDN 在中国大陆不可达，字体静默回退 | `ui-core/src/themes/molv-tokens.css:7` `@import url('https://fonts.googleapis.com/...')` | 字体本地化，移除 `@import` |
| D3 | 依赖系统 Node，与零配置冲突 | Flutter 版 `DshConfig.forEngine` 写死 `executable: 'node'` | 随包带 `node.exe`，用绝对路径 |
| D4 | `DSH_REPO` 默认值指向不存在的路径 | `scripts/build_dsh_release.sh` | 脚本在 V5 退役 |

## 5. 复现命令

```bash
# E4/E5：引擎装配 + 启动
mkdir engine-probe && cd engine-probe && npm init -y
V=0.1.0-rc.6
for p in dsh-acp-demo dsh-llm-deepseek dsh-sandbox-local dsh-sandbox-policy \
         dsh-subprocess-local dsh-bash-sandbox dsh-user-approval dsh-token-meter \
         dsh-compaction-basic dsh-session-projection dsh-fs-sandbox \
         dsh-fs-observation-policy dsh-tool-fs dsh-tool-todo dsh-repeat-tool-reminder; do
  set -- "$@" "@deepseek-ai/$p@$V"; done
npm install "$@"

# E11：lockfile 结构
python3 -c "import json;d=json.load(open('package-lock.json'));p=d['packages'];\
print(len(p), sum(1 for k in p if k.count('node_modules')>1), \
sum(1 for k,v in p.items() if k and not v.get('resolved')))"
# → 104 0 0
```
