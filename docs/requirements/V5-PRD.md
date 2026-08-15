# 墨律 InkStatute V5 需求规格说明书

版本：V5
日期：2026-08-15
仓库：`inkstatute-suite`
中文名：墨律　英文名：InkStatute
前置文档：`docs/requirements/V4-PRD.md`（v4.0 开发侧技术闭环于 2026-08-15；产品层结论被 V5 推翻）
选型证据：`.planning/research/V5-SELECTION.md`（11 项本机实测）

---

## 0. 为什么要有 V5

### 0.1 一句话诊断

V4 的三层分工（DSH 引擎 / 法律能力包 / 产品外壳）是对的，**引擎层与能力层继续沿用**。
被推翻的只有产品层：Flutter 原生 UI 打磨成本过高、呈现简陋，不具备交付给律师的品相。

### 0.2 V4 前提已失效的部分

| V4 前提 | V5 现实 | 影响 |
|---|---|---|
| 产品层 = Flutter 原生，明确不用 WebView | Flutter UI 打磨成本不可接受 | 产品层改为 Tauri 2 + SolidJS |
| 「不用 WebView」是硬约束 | 该约束的前提是 Flutter 选型（原生 UI 才是选 Flutter 的意义）。换到 Tauri 后前端本就是 WebView | 约束失效，不再适用 |
| UI 需从零打磨或逐字复制 lawyer-desktop | `packages/ui-core` 已是 lawyer-desktop UI 的完整移植，主题文件逐字节相同 | UI 复制成本已付清 |
| ACP 只能拿到已提交文本，工具活动不可见为接受取舍（DP-2） | 会话 JSONL 日志含完整事件流，可配为明文 NDJSON | DP-2 撤销，工具时间线可见 |
| 引擎 = 170MB zip，禁自动升级 | DSH 已公开发布 npm，lockfile 装配 9 秒 / 42MB | 引擎可半自动升级 |
| Word 原生修订导出（APP-04）+ 便携 Python | 业主决定放弃，交给 agent 自身文档能力 | 移除 docx-rs / pdf-extract / 便携 Python |

### 0.3 V5 的核心判断

**墨律 = 法律能力包 + 律师可用外壳，套在 DSH 引擎上。** 三层分工不变，只换产品层实现：

- **引擎层 → DSH**（钉 npm 版本、嵌入、经 ACP over stdio 驱动）。不变。
- **能力层 → `ai-for-china-legal` 技能语料 + 分域预设**。不变。
- **产品层 → Tauri 2 + SolidJS 桌面 app**，装配 `packages/ui-core`（墨律三主题 + 已解耦组件 + 事件归约器）。

---

## 1. 目标与非目标

### 1.1 目标

- 交付一个 Windows 单文件安装包：安装 → 首启向导（供应商 + 密钥）→ 直接对话，全程无命令行。
- 引擎能力（工具调用、技能加载、审批、历史、压缩）由嵌入的 DSH 提供，墨律不重复实现。
- 律师能看见 agent 在干什么：流式正文、思考过程、工具调用时间线、工作流进度。
- 四条法律护栏（research-gate / citation audit / ask-user / de-AI polish）与高风险人审标记不可绕过。
- 引擎半自动更新（检查 → 提示 → 用户确认 → 自动替换 → 冒烟闸 → 失败回滚）；内容包全自动更新。
- LLM 自动判断法律领域，用户不选菜单、不配置任何东西。

### 1.2 非目标（V5 不做）

- **不做 Word 原生修订导出**：移除 `docx-rs`、`pdf-extract`、便携 Python、track-changes 脚本。文档能力交给 agent 自身（技能里已写产出格式要求）。
- 不做内嵌文档编辑：DocPreview 只读呈现。
- 不做 Gateway / WeCom / QQ / Arena / 管理台 / 多租户 / 远程引擎。
- 不做自研 agent loop 的任何投入。
- 不做移动端。
- 不复活 `apps/flutter_app`：冻结保留（其引擎生命周期、内容更新、护栏逻辑作为 Rust 侧移植参照），不删除、不再投入。

---

## 2. 目标用户与验收场景

**目标用户：一名电脑操作能力弱的执业律师，由业主远程代为安装与升级。**
原则：**用户不碰终端、不碰配置文件、不碰密钥、不碰升级。**

核心验收场景：

1. 双击安装包 → 向导选供应商 + 填密钥 → 打开即用，全程无命令行。
2. 输入「审查这份合同」并拖入文件 → 看到流式回答、思考过程、工具调用时间线、引用标记（verified/retrieved/unverified）、必要时看到澄清卡片与「需人工复核」徽记。
3. 审批：agent 要跑 shell / 写文件时弹出批准卡片，点允许或拒绝；不存在批量批准入口。
4. 中止：生成跑偏时点停止，当前轮立即结算。
5. 引擎更新：业主发新版 → app 提示「有新引擎版本」→ 用户点确认 → 后台下载校验冒烟 → 下次启动生效；失败用户无感。
6. 技能更新：业主发新内容包 → app 启动自动拉取 → 用户无感生效，失败自动回滚。
7. 断网：app 可打开、可看历史；提示「联网后才能进行新任务」。

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ apps/desktop（Tauri 2 + SolidJS，Windows 桌面）                │
│  packages/ui-core：墨律三主题 + 已解耦组件 + event-reducer     │
│  首启向导 │ 会话 UI │ 批准卡 │ 澄清卡 │ 引用/人审徽记          │
│  工具时间线 │ 工作流进度 │ 设置面板                            │
├──────────────────────────────────────────────────────────────┤
│ Tauri event channel（RunEventEnvelope，唯一新增传输层）        │
├──────────────────────────────────────────────────────────────┤
│ Rust 引擎主管（apps/desktop/src-tauri）                        │
│  ┌────────────┬─────────────────┬───────────────────────┐    │
│  │ 控制面      │ 观测面           │ 历史面                 │    │
│  │ ACP stdio  │ session.jsonl   │ session-query.db       │    │
│  │ prompt     │ 明文 NDJSON 尾随 │ SQLite FTS5 只读       │    │
│  │ cancel     │ tool/reasoning  │ 会话列表 + 全文搜索     │    │
│  │ permission │ /streaming      │                        │    │
│  └────────────┴─────────────────┴───────────────────────┘    │
│  进程生命周期 │ 凭据注入 │ 事件映射 │ 引擎更新器              │
├──────────────────────────────────────────────────────────────┤
│ DSH 引擎（钉 npm 版本，随安装包分发）                          │
│  node.exe + lockfile 装配的依赖树（Windows 侧约 42MB）        │
│  engines/acp.cordis.yml：agent-spine + JSONL 持久化 +         │
│    SQLite 查询索引 + 批准栈 + 沙箱 + fs/todo 工具 + 压缩 +     │
│    分域技能目录 + pi-ai 多供应商适配器                         │
│  DSH_HOME=%LOCALAPPDATA%\InkStatute\runtime\.dsh             │
├──────────────────────────────────────────────────────────────┤
│ 云端（业主维护）：模型 API │ engine-lock.json │ 内容包 release  │
└──────────────────────────────────────────────────────────────┘
```

数据布局（Windows）：

```
%LOCALAPPDATA%\InkStatute\
  app\                 # Tauri 应用（安装器管理）
  node\node.exe        # 便携 Node 运行时
  engine\<version>\    # lockfile 装配的引擎树 + acp.cordis.yml
  engine\current       # 指针文件（单行版本号）
  runtime\.dsh\        # DSH_HOME：预设、设置、会话日志、查询索引
  skills\<release>\    # 内容包版本目录 + current 指针
```

**关键：会话历史落在 `runtime\.dsh\` 而非 `engine\`，引擎目录整体替换不影响历史。**

---

## 4. 引擎集成契约（已实测）

### 4.1 会话模型（DP-1，V5 定案）

- **一个 app 运行期 = 一个 DSH 引擎子进程。** 不是 per-session 进程。已实测：一条 ACP 连接可拥有多个会话，各自独立的 prompt 槽、工作区、取消路径与日志目录。
- **一个对话 = 一个 ACP 会话**，首次发消息时惰性创建，在 app 运行期内保持打开。
- **跨 app 重启的对话续接 = 回灌**。ACP 明确「Fresh sessions only」，重开旧对话时创建新 ACP 会话，由 app 把此前成稿的往来作为首轮提示的上下文前缀回灌。
  - 依据：实测 `request/context` 事件显示 `contextWindow: 1000000`，法律对话转录仅占数个百分点。
  - 溢出由 `dsh-compaction-basic`（thresholdRatio 0.8）自动处理。
  - 回灌轮数上限可配（默认 20 轮），超出则从最近往前截断并在前缀注明「更早内容已省略」。
- **否决常驻引擎方案**：引擎进程跨 app 关闭存活会破坏零孤儿进程保证（V4 DSH-02 硬要求），且带来升级期进程冲突。

### 4.2 控制面：ACP over stdio（逐条实测）

| 方法 | 形式 | 契约 |
|---|---|---|
| `initialize` | 请求 | `protocolVersion: 1`；返回 `agentInfo.name = "deepseek-harness-acp"` |
| `session/new` | 请求 | `cwd` 必须绝对路径；`mcpServers: []`（非空即拒）；返回 `sessionId` |
| `session/prompt` | 请求 | 每会话单 in-flight；`prompt: [{type:'text', text}]`；返回 `{stopReason}` |
| `session/cancel` | **通知（无 id）** | **按请求发送会返回 `Method not found` 而静默失败**。实测通知形式令 in-flight prompt 立即结算为 `{"stopReason":"cancelled"}` |
| `session/request_permission` | 服务端→客户端请求 | 携带 tool call id；一次性 allow-once / reject-once |

**输出边界**：`session/update` 只发 `agent_message_chunk`（已提交 assistant 文本）。工具、推理、计划、标题全部不上 ACP 线——由观测面补齐。

### 4.3 观测面：会话 JSONL 日志（V5 新增，撤销 V4 DP-2）

- 配置 `packChunks: false` + `persistenceCompression: none` → 明文 NDJSON，`seq` 连续（`events[i].seq === i`）。
- 路径：`<persistenceRoot>/--<规范化 cwd>--/<sessionId>/session.jsonl`
- 事件词汇（实测）：`session` 头 · `turn/start` · `turn/end` · `step/start` · `step/end` · `user/message` · `assistant/message` · `assistant/chunk` · `tool/call` · `tool/result` · `session/title` · `request/header` · `request/context` · `agent/inbox/spliced`
- `assistant/chunk` 的 chunk 类型：`block-start` · `text-delta` · `reasoning-delta` · `tool-call-delta` · `block-end` · `usage` · `finish`

### 4.4 历史面：会话查询索引

- `<persistenceRoot>/session-query.db`（SQLite，引擎自动维护，app 侧**只读**）
- `persisted_sessions` 表：id / created_at / cwd / agent_preset / revision
- `persisted_docs` FTS5 虚拟表（unicode61 分词）：会话全文搜索

### 4.5 持久化根路径（V4 缺陷修正）

V4 的 `persistenceRoot: '${DSH_HOME}/sessions'` **不被 Cordis 展开**，会在引擎目录下建出名为 `${DSH_HOME}` 的字面量目录——引擎更新替换目录时连同会话历史一并抹掉。

V5 修正（已实测）：

```yaml
persistenceRoot: !!js process.env.DSH_HOME + '/sessions'
```

### 4.6 多供应商

用 `@deepseek-ai/dsh-llm-pi-ai`。配置里 `apiKeyEnv` 是**凭据引用**而非凭据本身（官方文档：no secret enters this file）。app 侧职责仅两项：设置界面的供应商选项数据；启动引擎时按当前供应商注入对应环境变量。适配器、协议、模型目录全部由 DSH 提供。

---

## 5. 事件映射（产品层核心契约）

`packages/ui-core` 的组件只认 `RenderState`，由 `event-reducer.ts`（421 行，不改）从统一事件推导。Rust 侧负责把 DSH 事件翻成 `RunEventEnvelope`。

| DSH 来源 | 统一 `event_type` | 驱动的 UI |
|---|---|---|
| `session` 头 | `session.started` | 会话建立 |
| `assistant/chunk` · `text-delta` | `message.delta` | ChatPanel 流式正文 |
| `assistant/message` | `message.completed` | 消息定稿 |
| `assistant/chunk` · `reasoning-delta` | `thought.delta` | 思考过程 |
| `tool/call` | `tool_call.started` | AgentTracePanel |
| `assistant/chunk` · `tool-call-delta` | `tool_call.delta` | 工具参数流式 |
| `tool/result` | `tool_call.completed` | 工具结果 / 技能激活 |
| `step/start` · `step/end` | `plan.updated` | WorkflowProgressSteps |
| `turn/start` · `turn/end` | `run.state_changed` | 运行状态、停止按钮 |
| `turn/end` reason.kind=error | `error` | 错误态 |
| ACP `session/request_permission` | `permission.requested` | **批准卡片** |
| `[CLARIFY:]` 约定文本块 | `elicitation.requested` | **澄清卡片** |
| fs 工具结果派生 | `artifact.created` | DocPreview |
| 正文扫描派生（citationAudit） | `citation.recorded` | **引用徽记** |
| `session/title` | 元数据 | ConversationDrawer 标题 |

---

## 6. 更新机制

### 6.1 三层

| 层 | 节奏 | 机制 |
|---|---|---|
| App | 静默检查 + 提示 | `tauri-plugin-updater`（lawyer-desktop 已接好，换真签名公钥） |
| 引擎 | 检查 → 提示 → 用户确认 → 自动替换 | lockfile 装配 + 版本目录 + 冒烟闸 + 指针切换（§6.2） |
| 内容包 | 全自动，用户无感 | 沿用 V4 `content-manifest.json` + sha256 + 原子切换 + 回滚 |

### 6.2 引擎更新七步

1. **取版本** — 拉 `engine-lock.json`（业主托管，约 40KB），比对 `engine\current`
2. **兼容闸** — 检查 app 版本 ∈ `lock.compatible_app_range`，否则只提示升 app
3. **下载** — 按 lockfile 逐包下载 tarball，逐包校验 sha512 `integrity`
4. **铺树** — 按 lockfile `packages` 路径展开到 `engine\<新版本>\`，写入 `acp.cordis.yml`
5. **冒烟** — 启动新引擎跑 `initialize` → `session/new` → 退出；任一步失败即删除新目录，`current` 不动
6. **切换** — 冒烟通过后原子写 `current`，下次启动生效
7. **回滚** — `current` 写回旧版本号；旧目录保留一代

**不变式：新版本在冒烟通过之前，`current` 指针一次都不会动。**

### 6.3 引擎装配（替换 V4 的 zip 管线）

- 分发源：npm 官方源，国内走 `registry.npmmirror.com`（实测均可达）。业主只需托管 `engine-lock.json`。
- **必须钉精确版本号，禁用 dist-tag**：`latest` 指向 `0.0.1-rc.1`（旧），`next` 才是当前版。
- lockfile v3 实测 104 条、**零嵌套 `node_modules`**、100% 带 `resolved` + sha512 `integrity` → Rust 侧照着铺平即可，运行时不需要 npm。
- 体积：装出 85MB，裁掉 `node-pty` 的非 Windows 预编译后约 42MB。
- `engines/dsh-pin.txt` 从钉 git commit 改为钉 npm 版本号。
- 退役 `scripts/build_dsh_release.sh` 的 pnpm-deploy 符号链接手术。

### 6.4 Node 运行时

随安装包带 `node.exe`（官方 win-x64 zip 约 37MB，v24 LTS）。因更新走 Rust 侧 lockfile 装配，**不需要带 npm**。
禁止依赖系统 Node（V4 `DshConfig` 直接写 `executable: 'node'`，与零配置冲突）。

---

## 7. 法律护栏（沿用 V4 GRD-01..06，呈现层重做）

双层不变：预设人设提示词段（模型侧）+ app 呈现/强制（渲染侧），任一层缺失即视为绕过。

V5 变化：工具活动可见后，research-gate 的「是否真的检索了」从推断变为**可核验**——`tool/call` 时间线直接显示检索工具是否被调用。

---

## 8. 冻结与移除

| 对象 | 处置 |
|---|---|
| `apps/flutter_app` | **冻结**，不删除。其 `lib/engine/`、`lib/content/`、`lib/guardrails/`、`lib/wizard/` 是 Rust 侧移植的行为参照 |
| `apps/web`、`apps/web_chat`、`apps/platform_api` | 冻结（V4 已冻结，不变） |
| `packages/ui-core` 的 Arena 组件 | 裁剪：`ArenaWorkflowCreator` · `ParallelStreamPanel` · `ScoreCard` · `SynthesisViewer` · `ReviewSummary` · `arenaEventReducer.ts` · `stores/arenaStream.ts` · `types/arena.ts` |
| `apps/desktop` 的 Gateway 耦合 | 移除：`config/gateway.ts` · `config/arena.ts` · `contexts/AuthContext.tsx` · `contexts/ConnectionContext.tsx` · `pages/ArenaPage.tsx` · `lib/upload.ts` · `lib/runBuilder.ts` · `commands/offline_cache.rs` |
| `docx-rs` · `pdf-extract` | 从 `apps/desktop/src-tauri/Cargo.toml` 移除 |
| 便携 Python · track-changes 脚本 | 不进 V5 |
| `packages/platform-sdk-ts` | 只保留 `src/events.ts`（零 import 的纯类型模块）；`src/index.ts` 的 HTTP 客户端冻结 |

---

## 9. 已知风险

| # | 风险 | 缓解 | 验证点 |
|---|---|---|---|
| R1 | ACP 无会话恢复，重开对话模型无上下文 | 回灌（§4.1），1M 上下文使其廉价 | Phase 123 真 key 实测 |
| R2 | DSH pre-release 破坏组合/事件格式 | 钉精确 npm 版本；冒烟闸；失败不动指针 | 每次引擎升级 |
| R3 | 日志尾随有延迟（`writeBatchMaxDelayMs` 默认 200ms） | 可配置下调；已提交文本经 ACP 双通道到达可交叉校验 | Phase 123 |
| R4 | 345 技能目录 token 爆炸 | 分域预设 + 核心集预算门禁（沿用 SKL-07） | Phase 126 |
| R5 | Google Fonts CDN 在中国大陆不可达，字体静默回退 | 字体本地化，移除 `@import` | Phase 125 |
| R6 | 明文 NDJSON 日志体积增长（关闭了 zstd 与 packChunks） | 会话目录按保留期清理；单会话日志量级可接受 | Phase 123 |
