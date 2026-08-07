# 墨律 InkStatute V3 需求规格说明书

版本：V3
日期：2026-08-06
仓库：`inkstatute-suite`
中文名：墨律　英文名：InkStatute
前置文档：`docs/requirements/V2-PRD.md`（V2 已交付 11 个 milestone / 87 个 phase，本文件取代其作为当前规格）

---

## 0. 为什么要有 V3

### 0.1 一句话诊断

**墨律有一条世界级的"法律能力配送管道"、一批真正的"法律能力"、三个互不相认的"法律能力执行器"——而管道从未接上能力，三个执行器各自重复实现了 skill 加载、路由、MCP、ask_user。**

| 资产 | 位置 | 体量 | 现状 |
|---|---|---|---|
| 平台管道 | `inkstatute-suite` | 118,556 行 Python / 275 测试文件 / 3,173 测试 / 28 gate | **从未引用过任何真实法律 skill** |
| 法律能力 | `ai-for-china-legal` + `legal-skills` | 345 + 51 个 SKILL.md（含 140 个 Python 脚本） | 只被 Hermes profile 和桌面端消费 |
| 执行器 A | `lawfirm-profile`（Hermes） | 312 skill（297 symlink + 9 copy + 6 自建 gate）、router.py 498 行 | 生产在跑 |
| 执行器 B | `lawyer-desktop`（Tauri/Rust 自研） | agent loop 2000 行、router 627 行、classifier 691 行 | 可用，**与平台零集成** |
| 执行器 C | `lawyer-ai`（OpenCode） | ~55 文件 | 原型，搁置 |

证据：全仓库 grep `ai-for-china-legal` 只命中 `V2-PRD.md` 和一份 v1.6 研究笔记，**零代码引用**。平台唯一的 skill 数据源是 `solutions/lawfirm/manifest.json` 里手写的 4 条元数据，`hermes_materializer.py` 甚至会把它们**写出**一个 `SKILL.md.template` 存根。

### 0.2 V2 的前提已经失效

V2 的所有关键决策都建立在四个前提上，这四个前提现在全部不成立：

| V2 前提 | V3 现实 | 影响 |
|---|---|---|
| "不做完整多后端 runtime，Hermes 是唯一生产后端" | Hermes v0.19.0 原生支持 ACP；Codex / Claude Code / Gemini CLI / OpenCode / Cursor / Cline 也支持 | 多后端不再需要 N 个 adapter，只需 1 个 ACP client |
| "WeCom 是唯一通道，Web/桌面/移动不在范围" | 业主要 web + 桌面 App + 移动 + bot 全部端 | 通道层必须先于后端层被抽象 |
| "不做完整 Skill Registry，只读 Hermes skill index" | 396 个真实 skill 从未进入平台；每个执行器各自加载 | skill 必须升级为独立能力层 |
| "自研 agent 只是 north star，BackendAdapter 能表达即可" | `lawyer-desktop` 已是可运行的自研 agent；业主明确要自研核心 | 自研核心是本期交付项，不是留口 |

### 0.3 V3 的核心判断

**"统一执行核心"能办到，但它不是一段代码，是一个协议边界。**

平台不该自己"执行"法律任务，也不该为每个后端写胶水。平台该做的是：定义**一套事件词汇**，让它同时跑在两条链路上——对客户端说 HTTP+SSE，对后端说 ACP over stdio。两边同构，平台只做扇出、租户、持久化、输出边界和通道降级。

自研 agent core 因此不再是"要不要做"的架构决策，而是"第几个 ACP agent"的排期问题。

---

## 1. 目标架构

### 1.1 三层与两条链路

```
┌─────────────────────────────────────────────────────────────────────┐
│ 通道层 Clients                                                      │
│  Web(桌面/移动浏览器) │ 桌面 App(Tauri) │ 移动 App(V4) │ WeCom │ QQ  │
│  ── 共享 @inkstatute/ui-core (SolidJS)，chat UI 只有一份实现 ──      │
└───────────────────────────────┬─────────────────────────────────────┘
                     HTTP + SSE │ 统一事件词汇 + 租户鉴权
                                │ (bot 通道在此降级为非流式聚合)
┌───────────────────────────────▼─────────────────────────────────────┐
│ 平台层 InkStatute Gateway (Python)                                  │
│  会话/运行状态机 · 多端扇出 · 持久化 · 输出边界 · 契约事件 · 反馈    │
│  ┌───────────────────────── 能力层 Skill Layer ─────────────────┐   │
│  │ Skill 索引(396 个真实 SKILL.md) · 物化器 · 路由 · 执业配置   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                 ACP over stdio │ 同一套事件词汇
      ┌─────────────┬───────────┴────────┬──────────────────┐
┌─────▼──────┐ ┌────▼─────┐ ┌────────────▼───┐ ┌───────────▼────────┐
│ hermes acp │ │codex-acp │ │claude-code-acp │ │ 墨律自研 agent-core │
│  (现成)    │ │ (现成)   │ │   (现成)       │ │  (Python, 本期建)   │
└────────────┘ └──────────┘ └────────────────┘ └────────────────────┘
```

**唯一稳定耦合点**：统一事件词汇。客户端不知道后端是谁；后端不知道通道是谁；skill 对所有后端一视同仁。

### 1.2 五个架构问题的结论

#### 问题 1：三层边界与契约

- **通道层契约与后端层契约是同一套事件词汇，两种传输**。不是两个契约，也不是同一个传输。
  - 客户端 ⟷ 平台：HTTP + SSE（需要多租户、鉴权、断线续传、非流式降级）
  - 平台 ⟷ 后端：ACP over stdio（需要子进程生命周期、能力协商、权限请求）
- **现有 5 个 V2 schema 保留但降级为持久化契约**，不再是唯一契约。`AgentTurn/AgentResult/ExecutionTrace/FeedbackEvent/RouteDecision` 继续作为审计/回放/反馈的落库事件；新增的统一事件词汇是**传输契约**，`RunEvent` 被重新规格化为它的承载体。理由：V2 的 5 schema 是"一轮结束后的总结"，无法表达流式增量、工具轮、澄清中断、权限请求——这些正是所有端体验的核心。
- **`packages/channel-core` 的通道无关逻辑（幂等、投递守卫、输出策略、notice 过滤）全部保留**，它本来就不含 webhook 假设。`ChannelAdapter` 的 6 方法 Protocol 里 `verify_and_ack` 是 IM webhook 特有的；web/桌面/移动通道走 Gateway HTTP，不实现该方法（capability 声明为不需要）。

#### 问题 2：法律 skill 的形态与归属

**实测形态**（不是猜测）：

| 维度 | ai-for-china-legal | legal-skills |
|---|---|---|
| 数量 | 345 个 SKILL.md，13 plugin | 51 个 SKILL.md，扁平 |
| 结构 | 两层：~60 编排入口 + ~285 叶子子技能 | 单层自包含 |
| 形态 | **纯 prompt/procedure**，无执行体 | **混合**：37/51 带 `scripts/`（140 py / 31 sh / 6 js） |
| frontmatter | `name`/`description`（100%）、`argument-hint`（编排入口） | 另有 `version` 96% / `license` 100% / `author` 96% / `homepage` 94% |
| 体积 | 编排入口 4-6KB，深叶 8-12KB | 3KB–40KB |
| 宿主假设 | ~25% 含（文件路径、`ask_user` 工具、`/plugin:skill` 语法） | ~75% 含（脚本执行、config 路径） |
| 配置依赖 | ~50 个 skill 读 per-plugin `CLAUDE.md` 执业配置，未配置时降级"临时模式" | `config/*.example.json` |

**归属结论**：

1. **skill 留在自己的仓库**，平台通过 vendoring（git submodule / 只读挂载）引用，**不进 solution-pack、不复制进平台仓**。理由：两个 skill 仓有各自的版本、license（legal-skills 是 MIT + CC-BY-NC 双许可）、作者和演进节奏；复制进来立刻产生第四份分叉。
2. **平台不建 skill 执行 runtime**。所有候选后端（Hermes 的 `~/.hermes/skills/`、Claude Code、Codex、自研 core）都原生加载 SKILL.md。平台建的是**索引 + 物化器**：
   - **索引**：扫描 396 个 SKILL.md，产出机器可读索引（编排入口/叶子、token 预算、gate 声明、宿主假设标记、双仓冲突）。**可在不修改任一 skill 仓的前提下生成**。
   - **物化器**：把语料按每个后端期望的布局落地（Hermes profile 目录 / ACP agent skills 目录 / 自研 core 的加载路径）。一份 skill，三处可用。
3. **三分离**：元数据（索引，用于路由/可观测）· 正文（按需注入 prompt，受上下文预算约束）· 工具依赖（MCP / 脚本，声明在索引，由各后端各自满足）。
4. **不同后端消费方式不同，但平台只维护一份索引 + N 个物化器**，而不是 N 份 skill 拷贝。
5. `solutions/lawfirm/manifest.json` 那 4 条手写元数据与真实 396 个 skill **完全无关**——它是 V2 为了跑通 SolutionLoader 造的假数据。V3 废弃它作为 skill 源，`manifest.json` 只保留 persona / output_policy / MCP / industry_context 等真正的 solution 级配置。

#### 问题 3：自研 agent core 的定位

**结论：主后端，但通过与其他后端完全相同的协议接入。**

这不是"方向 A 平级"也不是"方向 B 主后端"的二选一，因为提问预设了一个错误的对立：把"是不是主力"和"是不是特殊"绑定在了一起。正确答案是**默认后端 = 自研，但它在架构上没有任何特权**。

- 自研 core 是 `backend_id="inkstatute"`，与 `hermes`/`codex`/`claude-code` 走同一 BackendAdapter 与同一事件词汇。
- 它同时提供**两个入口**（一份实现）：
  - **in-process**：平台直接调用的 Python 库（快路径，完整可观测，无 IPC）
  - **`inkstatute-agent acp`**：标准 ACP agent 入口，可被 Zed / VS Code / Buzz 等外部宿主使用，也为未来桌面端嵌入留口
- 排期上它在最后一个阶段建成。**在它建成之前，`hermes acp` 就能让全部通道跑通**——这是本 PRD 最重要的排期决策：先拿到可用产品，再换心脏，换的时候不动任何通道代码。

**语言定案：Python。** 依据是能力，不是成本：

| 判据 | 证据 |
|---|---|
| 最难的法律产出（Word 原生修订 docx） | `lawfirm-profile/scripts/contract_review_trackchanges.py` = **41,185 字节 Python，已建成**；`lawyer-desktop/src-tauri/src/documents/docx_gen.rs` = **74 行**，只能 markdown→docx。用 Rust 是能力**退化** |
| skill 语料的可执行一半 | legal-skills 的 `scripts/` 有 **140 个 .py** / 31 .sh / 6 .js。Rust 核心必须 shell 出去调 Python，等于仍需 Python |
| 平台契约/可观测/RBAC/输出边界 | 118,556 行 Python、3,173 测试、28 gate。跨语言边界会让 ExecutionTrace 与输出策略要么重复要么降级 |
| Rust 的真实优势（嵌入桌面端离线、单二进制） | **业主已定"在线为主、离线只读"，该优势失效** |
| 客户端体验流畅 | 不由核心语言决定，由**首字节即流 + 工具轮也流式**决定。`lawyer-desktop` 当前工具轮是**非流式**的（先整轮 LLM 调用拿到 tool_calls，只有最终 content 才流），这是要修的缺陷而非要移植的资产 |

**lawyer-desktop 各归其位**（不是丢弃，是拆解）：

| lawyer-desktop 资产 | V3 去向 |
|---|---|
| `src/` 23 个 SolidJS 组件 + 21 个 CSS（墨律三主题） | → `packages/ui-core`（共享 UI 核心，三端复用） |
| `src-tauri/` Tauri 外壳 + 更新器 + 文件对话框 | → `apps/desktop`（桌面客户端外壳，`invoke()` 改指 Gateway HTTP/SSE） |
| `skills/router.rs` 627 行（中文法律 prompt 装配、research-gate 注入、检索工具映射、引用规范） | → 移植进 `packages/agent-core`（Python）——**最高价值 IP** |
| `skills/agent_classifier.rs` 691 行（Chat/Draft/Evidence 三模式 + continue/switch/aside） | → 移植进 `packages/agent-core` |
| `llm/tool_leak.rs` 392 行（DSML/XML 泄漏工具调用解析、全角字符归一、重试） | → 移植进 `packages/agent-core`——生产硬化过，非平凡 |
| `citations/`（引用抽取与核验） | → 移植进 `packages/agent-core` |
| `skills/loader.rs` 269 行 | → 归入 `packages/skill-index`（Python，且能力更强：要处理双仓 + 宿主假设标记） |
| `mcp/` JSON-RPC stdio client | → 用 Python MCP SDK 替代，或归入 agent-core |
| `workspace/` FTS5 索引、`law_library/` | → 移植进 Python（服务端也需要，`sqlite3` 支持 FTS5） |
| `db/queries.rs` 1276 行 SQLite CRUD | → 不移植，平台已有持久化 |

#### 问题 4：存量代码逐包去向

见 §6 完整表格。

#### 问题 5：ACP 对齐

**结论：后端层对齐 ACP；通道层不对齐任何外部协议，但采用与 ACP 同构的事件词汇。**

**"ACP" 是同名两协议，必须先消歧：**

| 名称 | 出处 | 状态 | 定位 |
|---|---|---|---|
| **Agent Client Protocol** | Zed，`agentclientprotocol.com` | **v1 稳定，v2 draft（2026-07-20 发布，明确会变）** | 宿主 ⟷ 本地 agent，JSON-RPC 2.0 over stdio |
| Agent Communication Protocol | IBM BeeAI | **2025-08-29 并入 A2A，repo 归档，已死** | — |
| A2A (Agent2Agent) | Google → Linux Foundation | v1.0 稳定 | 跨组织 agent ⟷ agent，HTTP+JSON-RPC+SSE |
| MCP | Anthropic → Linux Foundation | 稳定 | agent ⟷ 工具，**正交，继续用** |
| AG-UI | CopilotKit | 新兴 | agent ⟷ 前端 UI，SSE 事件 |

业主说的"支持 ACP 协议的 agent"= **Zed 的 Agent Client Protocol**。

**为什么后端层对齐 ACP：**

1. **已在本机验证可用**：`hermes acp --check` → `Hermes ACP check OK`（Hermes Agent v0.19.0）。业主现用的 Hermes 就是 Nous Research 的 Hermes Agent，原生 `hermes acp` 子命令。
2. **一个 adapter 换 N 个**：Codex（`codex-acp`）、Claude Code（`claude-agent-acp`）、Gemini CLI（`--acp`）、OpenCode（`opencode acp`）、Cursor、Cline、Copilot CLI 全部支持；ACP Registry 有 174+ agent。现有 `packages/backends/{hermes,codex}` 共 3,875 行自定义 adapter 可归并为一个 ACP client。
3. **协议形状与产品需求一一对应**，不是勉强适配：
   - `session/update` 的 `agent_message_chunk`/`agent_thought_chunk`/`tool_call_update`/`plan` → 正好是 lawyer-desktop 的 thinking/tool/streaming/review 四相 UI
   - `elicitation/create`（支持单选 enum / 多选 array）→ 正好是 `ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md` 定义的 2-4 题、`allow_multiple` 澄清卡片
   - `session/request_permission` → 正好是高风险法律动作的人审闸门
   - `session/new`/`resume`/`cancel`/`close` → 正好是长任务与多端续接
4. **编辑器味道是可选的，且正在被移除**：`fs/*` 和 `terminal/*` 是 client 侧**可选 capability**，v2 直接删除。法律 chat 客户端不声明即可。
5. **Python SDK 成熟**：PyPI `agent-client-protocol` 0.11.0（2026-07-05），支持 client 与 agent 双侧，async，Pydantic 模型跟随每次 ACP 发布。

**为什么通道层不对齐 AG-UI / Vercel AI SDK：**

- **所有客户端都是第一方**（我们自己的 web/桌面/移动/bot）。标准协议的价值在于与**外部**互操作；后端层有真外部（Hermes/Codex/Claude Code），通道层没有。为零互操作收益引入一个第二事件词汇 + 一个外部依赖，是净负债。
- 但**事件词汇采用与 ACP `session/update` 同构的设计**，好处是平台退化成薄中继：进来什么形状，出去什么形状，只加租户/持久化/降级。同时在文档中保留到 AG-UI 的映射表，未来若需要第三方 UI 接入，是一层薄适配而非重构。

**必须诚实记录的 ACP 风险：**

| 风险 | 影响 | V3 对策 |
|---|---|---|
| v2 是 draft，会有破坏性变更（已删 `fs/*`、`terminal/*`、`session/load`、`tool_call`） | 升级成本 | 目标 **v1**，`initialize` 走版本协商；v2 就绪但特性开关关闭 |
| 稳定传输只有 stdio；HTTP/WebSocket 是 draft RFD | 无法直接做远程 agent | 自用形态下 agent 与平台同机，stdio 足够；SaaS 时走 daemon 模型或等 v2 远程传输 |
| 每会话一子进程（~200ms 启动，无跨会话缓存共享） | SaaS 规模是死路 | **业主已定"先自用"**：单律所 ≤50 人完全可行。契约里预留 `backend_process_mode`（`per_session` / `pooled` / `remote`），SaaS 时换实现不换契约 |
| 无多租户模型 | 租户隔离必须自建 | 本来就在平台层做（已有 RBAC + TenantGuard） |
| `elicitation/create` 是 draft，尚无客户端渲染 | 澄清卡片不能靠外部宿主 | 我们自己既是宿主又是客户端，自己渲染；对外部宿主降级为纯文本提问 |

---

## 2. 交付范围

### 2.1 V3 要做

1. **统一事件契约**：ACP 同构的事件词汇 + JSON Schema + Python/TS 绑定 + 冻结测试。
2. **ACP 后端适配**：Python ACP client，驱动 `hermes acp` 及至少一个额外 ACP agent；能力探测与版本兼容矩阵；事件双向映射；输出边界在桥上强制执行。
3. **统一 Gateway**：多租户 HTTP + SSE API，取代 `apps/platform_api` 与 `services/lawyer-web-chat` 的重叠；断线按 `seq` 续传；附件/产物 reference-first。
4. **共享 UI 核心**：从 `lawyer-desktop` 抽取 `packages/ui-core`（SolidJS + 墨律三主题 + 流式对话 + ask_user 卡片 + 文书预览 + 引用面板 + 五相进度），**chat UI 全项目只有一份实现**。
5. **Web 端**：响应式，桌面浏览器 + 移动浏览器可用。
6. **桌面端**：复用 `lawyer-desktop` 的 Tauri 外壳，`invoke()` 改指 Gateway HTTP/SSE，离线只读历史。
7. **Bot 通道降级**：WeCom / QQ 复用同一事件流，非流式聚合 + "仍在处理"业务化推送；现有 5s ACK / ED25519 / 模板卡片 / 幂等行为不回退。
8. **Skill 能力层**：真实索引 396 个 SKILL.md；双仓合并与冲突模型；按后端物化；用真实索引重做路由；执业配置（practice profile）多租户化。
9. **自研 agent core**（Python）：async 流式 turn loop（工具轮也流式）、工具层、Word 原生修订 docx、上下文预算、法律护栏移植（research-gate / citation 审计 / tool_leak 防泄漏 / de-AI polish）、in-process + ACP 双入口。
10. **存量收敛**：逐包保留/重构/废弃执行到位，gate 体系更新且 gate-coverage meta-test 保持绿。

### 2.2 V3 不做

- **不做移动原生 App 出包上架**（Android / iOS）。本期移动浏览器顶着；共享 UI 按可打包成 App 的方式设计，但不出包。理由：Tauri 2 移动端比桌面端嫩，中国 Android 无 Play Store、iOS 需 App Store 中国区 + ICP 备案（2-4 周），风险后置且不返工。
- **不做多租户 SaaS 规模化**（agent 进程池 / 远程 ACP 传输 / 水平扩容）。契约留口，实现不做。
- **不做桌面端完全离线的本地 agent runtime**。离线只读历史与已生成文书。
- **不重建 Hermes core**。Hermes 是 ACP 后端之一。
- **不自动合成或自动修改高风险法律结论 skill**。继承 V2 约束，只记录 `skill_candidate`，人审。
- **不复制 skill 语料进平台仓**。vendoring 引用。
- **不对齐 A2A / AG-UI**。保留映射文档。
- **不做 WeChat 小程序 / WhatsApp / Slack 等新通道**。
- **不做向量检索 / embedding RAG**。沿用 SQLite FTS5 全文检索路线（lawyer-desktop 已验证）。

---

## 3. 统一事件词汇（V3 传输契约）

### 3.1 设计原则

- 与 ACP v1 `session/update` **同构**：同名概念用同名字段，ACP 有的不另造。
- 增量优先：一切可流的都流，客户端可只订阅摘要。
- 可降级：每个事件都能被聚合成一条最终消息，供 WeCom/QQ 这类非流式通道使用。
- 可重放：`occurred_at` + `ingested_at` + `seq` 保留 V2 语义，支持乱序回放与断线续传。
- 行业中立：法律专用字段只进 `industry_context`。

### 3.2 事件类型

| 事件 | ACP 对应 | 说明 | bot 降级行为 |
|---|---|---|---|
| `session.started` | `session/new` 响应 | 会话建立，携带 backend_id / capabilities | 静默 |
| `message.delta` | `agent_message_chunk` | 助手回复增量 | 缓冲 |
| `message.completed` | `agent_message`（v2） | 助手回复整条落定 | **投递** |
| `thought.delta` | `agent_thought_chunk` | 推理增量 | 丢弃 |
| `tool_call.started` / `.delta` / `.completed` | `tool_call_update` | 工具调用生命周期 | 折叠为"正在检索法规…"业务化提示 |
| `plan.updated` | `plan` / `plan_update` | 执行计划（映射五相进度） | 首次投递一条"仍在处理"，后续静默 |
| `phase.changed` | `_meta` 扩展 | 五相：research→intake→retrieval→draft→review | 同 plan |
| `elicitation.requested` | `elicitation/create` | 澄清提问（2-4 题，单选/多选/自由文本） | **投递为模板卡片** |
| `permission.requested` | `session/request_permission` | 高风险动作人审 | **投递为审批卡片** |
| `artifact.created` | Artifact content block | 产物（docx / trackchanges_docx / pptx / pdf） | **投递为文件** |
| `citation.recorded` | `_meta` 扩展 | 引用与核验状态（verified/retrieved/unverified） | 附在最终消息 |
| `run.state_changed` | 状态 update | `queued/running/waiting_for_user/succeeded/failed/cancelled` | 失败时投递业务化提示 |
| `error` | JSON-RPC error | 三类错误码（contract/runtime/channel），继承 V2 | 投递业务化提示 |

### 3.3 与 V2 契约的关系

- `RunEvent` 重新规格化为上述事件的承载体（`event_type` 取上表值，`payload` 按类型定义）。
- `AgentTurn` / `AgentResult` / `ExecutionTrace` / `FeedbackEvent` / `RouteDecision` **保留不变**，作为落库/审计/回放/反馈契约，由事件流投影生成。V2 的 28 个 gate 必须保持绿。
- `elicitation.requested` 与 V2 的 `RunInterrupt` 对齐（`interrupt_id` / `resume_state_ref` / `expected_response_schema_ref`）。
- `permission.requested` 与 V2 的 `Approval` 对齐。

---

## 4. 通道层规格

### 4.1 Gateway API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/v1/sessions` | POST / GET | 创建 / 列出会话（多端续接） |
| `/v1/sessions/{id}` | GET / DELETE | 会话详情 / 关闭 |
| `/v1/sessions/{id}/runs` | POST | 提交一轮（文本 + 附件引用 + output_constraints） |
| `/v1/runs/{id}` | GET / DELETE | 轮次状态 / 取消 |
| `/v1/runs/{id}/events` | GET (SSE) | 统一事件流；`Last-Event-ID` 按 `seq` 续传 |
| `/v1/runs/{id}/elicitation` | POST | 提交澄清答案 |
| `/v1/runs/{id}/approvals` | POST | 提交审批决定 |
| `/v1/artifacts/{id}` | GET | 产物下载（鉴权 + 租户校验） |
| `/v1/uploads` | POST | 附件上传，返回 `attachment_ref`（reference-first） |
| `/v1/feedback` | POST | 反馈 → `FeedbackEvent` |
| `/v1/skills` | GET | Skill 索引只读查询（供客户端展示技能选择器） |

鉴权：延续 RBAC + 会话 cookie（web/桌面）与 Bearer token（bot / 程序化）。自用形态下租户配置可极简（单租户默认值），但**契约字段不省略**。

### 4.2 客户端矩阵

| 客户端 | 本期状态 | 技术 | 共享程度 |
|---|---|---|---|
| Web（桌面浏览器） | **交付** | SolidJS + Vite，消费 Gateway SSE | 100% `ui-core` |
| Web（移动浏览器） | **交付** | 同上，响应式布局 | 100% `ui-core` + 移动布局适配 |
| 桌面 App（Win/macOS） | **交付** | 复用 `lawyer-desktop` Tauri 外壳；`invoke()`→HTTP/SSE；保留本地 FTS5 工作区索引与离线只读缓存 | `ui-core` + 桌面专属外壳 |
| 移动 App（Android/iOS） | **V4** | 设计上可 Tauri 2 mobile 或 Capacitor 打包，本期不出包 | — |
| WeCom bot | **改造** | 现有 `services/wecom-service` 改为 Gateway 消费者 | 事件降级层 |
| QQ bot | **改造** | 现有 `services/qqbot-service` 改为 Gateway 消费者 | 事件降级层 |

**硬性要求**：chat 消息列表、流式渲染、ask_user 卡片、文书预览、引用面板在全项目**只有一份实现**。现状是 lawyer-desktop 与 lawyer-ai 各写一遍（约 80% 重复），V3 必须消除。

---

## 5. 能力层规格

### 5.1 Skill 索引

扫描 vendored 的两个 skill 仓，产出 `skill-index.json`：

```json
{
  "skill_id": "commercial-legal/contract-review/risk-identification",
  "source_repo": "ai-for-china-legal",
  "name": "risk-identification",
  "description": "...",
  "argument_hint": "[合同文件路径或内容] [可选：--party 甲方|乙方]",
  "plugin": "commercial-legal",
  "kind": "leaf",
  "parent": "commercial-legal/contract-review",
  "children": [],
  "path": "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
  "size_bytes": 13284,
  "token_estimate": 4400,
  "declared_gates": {"before": ["cn-law-research-gate"], "after": ["legal-de-ai-polish"]},
  "referenced_resources": ["shared/references/subject-qualification-traps.md"],
  "practice_profile_dependency": "commercial-legal/CLAUDE.md",
  "host_assumptions": ["ask_user_tool", "slash_command"],
  "required_scripts": [],
  "risk_level": "medium",
  "license": null
}
```

要求：
- **不修改 skill 仓即可生成**（只读扫描 + frontmatter 解析 + 目录关系推断 + `plugin.json` 校验）。
- 双仓合并：命名空间隔离（`ai-for-china-legal/*` vs `legal-skills/*`），沿用 `lawfirm-profile/scripts/sync_legal_skills.py` 的 `legal-` 前缀与冲突分类（`in-sync` / `upstream-changed` / `both-changed` / `local-missing`）。
- 标记宿主假设，供物化器决定是否改写（Repo A ~25%、Repo B ~75% 含宿主假设）。
- `token_estimate` 供上下文预算使用（实测正文 2K–20K token）。

### 5.2 物化器

| 目标后端 | 物化产物 |
|---|---|
| Hermes | `~/.hermes/profiles/<profile>/skills/` 布局（symlink 优先，脚本类 copy），沿用现有 312 skill 的接法 |
| ACP agent（Codex/Claude Code） | 各自的 skills 目录布局；宿主假设改写（`/plugin:skill` → 自然语言触发，`ask_user` → `elicitation`） |
| 自研 agent-core | 直接读索引 + 按需读正文，无需物化 |

### 5.3 路由

用真实索引重做路由，继承两处已验证的产品知识：
- `lawfirm-profile/scripts/router.py`（498 行）：12 条强信号确定性正则（法院短信、判决书、新案件、docx 合同…）、触发短语软匹配 0.4 阈值、`gate_before`/`gate_after`、0.6 以下标歧义、JSONL 决策日志。
- `lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`（691 行）：Chat/Draft/Evidence 三模式判定 + continue/switch/aside 动作、LLM 分类 + 规则兜底。

现有 `packages/router-service` 的三策略（RULE/SKILL/HYBRID）与法律风险分级保留，把数据源从 4 条假元数据换成真实索引。

### 5.4 执业配置（Practice Profile）

`CLAUDE.md` 机制（~50 个 skill 依赖）升级为平台侧多租户配置：审查立场（甲方/乙方）、升级矩阵（金额阈值 + 审批层级）、文书风格、管辖识别、交易破坏者。未配置时降级"临时模式"并在每个输出上标记。冷启动访谈可通过 `elicitation` 完成。

---

## 6. 存量代码逐包去向

### 6.1 packages/

| 包 | 源码行 | 决议 | 理由与方向 |
|---|---|---|---|
| `platform-contract` | 1,596 | **重构（扩展）** | 5 个 V2 schema 保留为落库契约；新增统一事件词汇；`RunEvent` 重新规格化。不删任何现有类型，28 gate 保持绿 |
| `platform-runtime` | 8,723 | **保留 + 重构** | `BackendAdapter`/`ChannelAdapter`/`SolutionLoader`/`RunRuntime` 四 Protocol 是资产，保留。`ChannelAdapter.verify_and_ack` 改为可选 capability（web/桌面不实现）。Memory/ContextAssembler 保留供 agent-core 复用 |
| `channel-core` | 629 | **保留** | 幂等/投递守卫/输出策略/notice 过滤本就通道无关，无 webhook 假设，直接复用 |
| `channels/wecom` | 254 | **保留** | WeCom 特有协议封装 |
| `channels/qqbot` | ~3,500 | **保留** | 28 个测试文件，签名/令牌/富媒体已生产硬化 |
| `channels/web_sse` | 259 | **废弃** | fixture-only、无网络 IO。被真实 Gateway SSE 取代 |
| `backends/hermes` | 1,843 | **废弃（归并）** | 自定义 HTTP runs API 被 `hermes acp` 取代。兼容矩阵/bootstrap 检查逻辑迁入 ACP adapter |
| `backends/codex` | 2,032 | **废弃（归并）** | `codex exec --json` subprocess 原型被 `codex-acp` 取代 |
| `backends/provider_model` | 3,467 | **重构（归并进 agent-core）** | 直连 LLM provider 的 runner（OpenAI/Anthropic/Ollama）正是自研 core 需要的模型层，迁入 `agent-core` 而非独立 backend |
| `contract-test-suite` | 6,284 测试 | **保留 + 扩展** | 28 gate + gate-coverage meta-test 是本仓最大的质量资产。新增事件契约、ACP 映射、skill 索引的 gate |
| `skill-registry` | 1,488 | **重构** | 接口（`list/get/search` + `/.well-known/agent-skills/`）保留，数据源从 4 条 manifest 换成真实 396 skill 索引 |
| `solution-loader` | 867 | **保留 + 重构** | 物化器（Materializer）概念正确，只是从未指向真实 skill。改造为 skill 物化器宿主 |
| `router-service` | 950 | **重构** | 三策略骨架保留，注入真实索引 + 移植 `router.py` 强信号规则 + `agent_classifier` 三模式 |
| `mcp-registry` | 511 | **保留** | agent-core 与 ACP 后端都需要 MCP 服务器注册 |
| `model-gateway` | 919 | **保留** | 熔断/限流/成本追踪，agent-core 直接复用 |
| `operator-config` | 1,386 | **保留** | 通道/provider/模型目录/视觉路由配置，V3 增加 backend 与 skill 源配置节 |
| `rbac` | 619 | **保留** | Gateway 鉴权直接复用 |
| `multi-agent-adapter` | 955 | **冻结** | 原型，无消费者。不删不扩，标记 experimental，V4 再议 |
| `platform-sdk-ts` | 297 | **重构** | 从 OpenAPI 自动生成保留，改为生成统一事件词汇的 TS 绑定，供 `ui-core` 使用 |
| **新增** `agent-core` | — | **新建** | 自研 Python agent 核心 |
| **新增** `skill-index` | — | **新建** | 真实 skill 扫描/索引/合并/冲突 |
| **新增** `acp-client` | — | **新建** | Python ACP client + 事件双向映射 |
| **新增** `ui-core` | — | **新建** | 共享 SolidJS 组件（TS） |

### 6.2 services/

| 服务 | 源码行 | 决议 | 理由与方向 |
|---|---|---|---|
| `wecom-service` | 3,271 | **重构** | 保留全部 WeCom 协议实现（验签/解密/ACK/模板卡/媒体/幂等）。移除自持 agent 调用，改为 Gateway 事件流消费者 + 非流式降级 |
| `qqbot-service` | 1,156 | **重构** | 同上 |
| `lawyer-web-chat` | 1,331 | **废弃（归并）** | 与 `apps/platform_api` 职责重叠。SSE 编码、会话鉴权、多设备会话列表、上传、反馈的实现迁入统一 Gateway |
| `hermes-contract-layer` | 1,205 | **重构（大幅缩减）** | hook 影子录制不再需要（ACP 直接给结构化事件）。保留 `lawfirm` profile bootstrap 与兼容矩阵，迁入 ACP adapter 的 Hermes 专属配置 |
| `feedback-service` | 1,059 | **保留** | 反馈归一/分类/去重/待审队列，接 Gateway `/v1/feedback` |
| `conversation-read-view` | 2,355 | **保留** | 只读视图/分页/导出/隐私擦洗，数据源改为统一事件流投影 |
| `admin-console-api` | 3,212 | **保留 + 扩展** | 运维控制面。新增 backend 进程管理、skill 索引状态、ACP 能力矩阵视图 |
| `admin-web-ui` | 5,831 | **保留** | stdlib SSR 运维控制台，与律师端 UI 无关，不并入 `ui-core` |
| **新增** `gateway` | — | **新建** | 统一多租户 HTTP + SSE 网关 |

### 6.3 apps/ 与 solutions/

| 目录 | 决议 | 理由 |
|---|---|---|
| `apps/platform_api` (1,099) | **重构（升级为 gateway 基座）** | SSE 帧编码、OpenAPI、create/poll/cancel/approve/stream 的骨架正确，扩展为完整 Gateway |
| `apps/web_chat` (TS 原型) | **废弃** | DOM-free fixture 渲染器，被真实 `ui-core` 取代 |
| **新增** `apps/web` | **新建** | Web 客户端 |
| **新增** `apps/desktop` | **新建** | 从 `lawyer-desktop` 迁入的 Tauri 外壳 |
| `solutions/lawfirm` | **重构** | 移除 4 条假 skill 元数据；保留 persona / output_policy / MCP / industry_context / secret_templates；skill 改为指向真实索引的选择器 |
| `solutions/demo_non_legal` | **保留** | 可组合性 CI 需要非法律合成任务，防止平台核心绑定法律字段 |

### 6.4 收敛量化

- 废弃/归并：`backends/hermes` 1,843 + `backends/codex` 2,032 + `channels/web_sse` 259 + `lawyer-web-chat` 1,331 + `apps/web_chat` ≈ **5,465 行退役**
- 归并再用：`backends/provider_model` 3,467 → `agent-core`
- 大幅缩减：`hermes-contract-layer` 1,205 → 约 300 行 Hermes 专属配置
- 新增：`agent-core` / `skill-index` / `acp-client` / `gateway` / `ui-core` / `apps/web` / `apps/desktop`

---

## 7. 安全、合规与法律安全

继承 V2 全部底线，新增 V3 特有条款：

- **法律护栏不可绕过**：`research-gate` 强制前置（先检索后作答）、citation 审计（标注 verified / retrieved / unverified）、`ask-user-enforcement`（关键事实缺失时阻断起草）、`legal-de-ai-polish`。这四条在自研 core 中是**代码级强制**，在 ACP 后端中通过 skill 物化 + 输出校验实施。
- **高风险法律结论必须人审**：不自动合成 skill、不自动修改法律结论类 skill、`skill_candidate.requires_human_review` 恒为 true。
- **输出边界**：后端 meta / gateway / system / update / command / help 噪声不得到达普通律师用户。ACP 事件桥是新的执行点（`session/update` 里的 available_commands / terminal / config_option 类更新必须被拦截）。
- **权限请求不得自动批准**：ACP `session/request_permission` 在服务端不得默认 allow。参考 Buzz 的教训——其 ACP 桥自动 `allow_once` 导致 agent 无提示执行 shell。墨律的 ACP client **必须显式拒绝** `terminal`/`execute_code` 类权限，或上抛为用户审批卡片。
- **secrets**：ACP agent 子进程的凭据通过环境注入，不入仓、不入日志、不入契约事件。
- **契约日志 reference-first**：`raw_payload_ref`，不存敏感全文。
- **skill 语料 vendoring 只读**：平台不写回 skill 仓。

---

## 8. 非功能需求

- **可观测性**：每轮产出完整事件流 + 投影出的 `ExecutionTrace`；契约日志覆盖率 ≥ 95%（继承 V2）。
- **可组合性（硬性）**：非法律合成任务必须跑通契约层，法律字段只在 `industry_context`。由 `solutions/demo_non_legal` + 可组合性 CI 验证（继承 V2）。
- **后端可替换性**：切换 `backend_id` 不需要改任何通道层或 UI 代码。由"同一 UI 分别对 hermes / inkstatute 两个后端跑通同一测试"验证。
- **通道可替换性**：新增一个通道不需要改后端层或能力层。
- **客户端无重复**：chat UI 单一实现（见 §4.2）。
- **流式体验**：首字节延迟以事件流第一条 `message.delta` / `thought.delta` 计；**工具轮必须流式**，不得整轮缓冲。
- **断线续传**：SSE 按 `seq` 续传，不重复不丢失。
- **零破坏**：现有 28 个 gate 保持绿；WeCom / QQ 现有生产行为不回退；Hermes 非 lawfirm profile 行为不受影响。

---

## 9. 验收标准

### 9.1 契约与 CI

- 新增 gate 全绿，现有 28 gate 保持绿，`gate-coverage` meta-test 保持"每个 `packages/*/src` 与 `services/*/src` 都被 gate 覆盖"。
- 统一事件词汇的 JSON Schema 校验、乱序回放、断线续传、bot 降级聚合全部有测试。
- ACP 映射双向往返测试（ACP `session/update` → 统一事件 → ACP，语义无损）。
- 可组合性：非法律合成任务不因 V3 改造而失败。

### 9.2 后端可替换性（关键验收）

**同一条律师任务，分别用 `backend_id=hermes`（ACP）与 `backend_id=inkstatute`（自研）跑通，通道层与 UI 代码零改动，事件流形状一致。**

### 9.3 通道一致性（关键验收）

**同一条律师任务，在 Web、桌面 App、WeCom bot 三处发起，都能得到：正确的最终答复、正确的产物文件、正确的澄清卡片、正确的反馈回路。**其中 Web 与桌面看到流式与五相进度，WeCom 看到聚合结果与"仍在处理"提示。

### 9.4 能力层验收

- Skill 索引覆盖 396 个真实 SKILL.md（`ai-for-china-legal` 345 + `legal-skills` 51），生成过程不修改任一 skill 仓。
- 索引正确区分 ~60 编排入口与 ~285 叶子，正确标记宿主假设与 gate 声明。
- 物化器能把语料落到 Hermes profile 布局，且 `hermes acp` 能加载。
- 路由用真实索引，`lawfirm-profile/router.py` 的 12 条强信号规则行为不回退。

### 9.5 自研核心验收

- 工具轮流式：工具调用期间客户端持续收到 `tool_call.*` 与 `thought.delta`，不出现整轮静默。
- Word 原生修订 docx 产出成功（合同审查场景），能力不低于现有 `contract_review_trackchanges.py`。
- 四条法律护栏（research-gate / citation 审计 / tool_leak 防泄漏 / de-AI polish）有测试覆盖。
- `inkstatute-agent acp --check` 通过，可被外部 ACP 宿主连接。

### 9.6 人工闸门（不得由自动化声称通过）

| 闸门 | 内容 |
|---|---|
| **HG-1 法律质量** | 移植后的 prompt 装配与法律护栏，须由律师抽样确认输出质量不低于现有 lawyer-desktop / Hermes |
| **HG-2 真机通道** | WeCom 与 QQ 的 live 收发验收（继承 V2 未关闭的人工闸门） |
| **HG-3 律师试运行** | 5 工作日 / 15 真实任务（继承 V2 未关闭的人工闸门） |
| **HG-4 修订稿质量** | Word 原生修订 docx 须由律师确认可直接用于对外谈判 |

---

## 10. 开发顺序与依赖

分四个阶段，**阶段 A+B+C 完成即可交付可用产品**（后端用 `hermes acp`），阶段 D 换心脏。

```
阶段 A 协议底座        Phase 88 → 89 → 90
                              │
阶段 B 通道统一        Phase 91 ─┬─ 92 → 93
                                 │      └─ 94
                                 └─ 95
                              │
阶段 C 能力层          Phase 96 → 97 → 98 → 99
                              │
阶段 D 自研核心        Phase 100 → 101 → 102 → 103 → 104
```

| 阶段 | Phase | 交付 | 完成后的状态 |
|---|---|---|---|
| **A 协议底座** | 88-90 | 统一事件契约、ACP client、事件桥 | Hermes 可通过 ACP 被平台驱动 |
| **B 通道统一** | 91-95 | Gateway、ui-core、Web、桌面、bot 降级 | **律师可在 web/桌面/WeCom/QQ 四处用同一套能力** |
| **C 能力层** | 96-99 | Skill 索引、物化、路由、执业配置 | **396 个真实法律 skill 首次进入平台** |
| **D 自研核心** | 100-104 | agent-core、工具层、护栏移植、双入口、存量收敛 | 心脏换成自研，通道层零改动 |

**关键路径**：88 → 89 → 90 → 91 → 92 → 93。走完即有可用 Web 产品。

**并行机会**：92/93/94 与 95 可并行；96-99 可与 B 阶段后半并行；100-103 内部串行。

---

## 11. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | ACP v2 破坏性变更 | 升级返工 | 锁 v1，`initialize` 版本协商，v2 特性开关关闭 |
| R2 | ACP stdio-only，无远程传输 | 未来 SaaS 受限 | 契约留 `backend_process_mode`；自用形态 stdio 足够 |
| R3 | 每会话一子进程的资源模型 | SaaS 死路 | 已定"先自用"；SaaS 时换 daemon 实现不换契约 |
| R4 | Rust→Python 移植法律 prompt 逻辑失真 | **法律质量下降** | HG-1 律师抽样闸门；移植前先建 golden fixture 对拍 |
| R5 | `tool_leak.rs` 392 行的防泄漏正则移植遗漏 | 工具调用泄漏进用户可见文本 | 用 Rust 侧现有测试用例作为 Python 侧的对拍集 |
| R6 | Word 原生修订能力在新核心中退化 | **核心法律产出不可用** | 直接复用 `contract_review_trackchanges.py`，不重写；HG-4 闸门 |
| R7 | 一次性废弃 5,465 行存量代码引入回归 | 现有生产行为回退 | 分阶段废弃，每步保持 28 gate 绿；WeCom/QQ 行为有回归测试 |
| R8 | 共享 UI 抽取过度，压平平台差异 | 桌面/移动/web 体验都不好 | `ui-core` 只收敛业务组件，布局与交互模式允许平台特化 |
| R9 | Skill 索引依赖外部仓的目录约定 | 上游改结构即崩 | 索引器容错 + 索引生成有测试 + 上游 vendoring 锁版本 |
| R10 | 自主执行（gsd-autonomous）在法律领域逻辑上判断失误 | 隐蔽的质量问题 | 阶段 D 的 Phase 102 强制 HG-1；所有法律护栏改动需 golden fixture 对拍 |

---

## 12. 与 V2 的关系

- V2 的**契约方法论**（事件化、行业中立、reference-first、可组合性 CI、gate 体系）全部继承，是本项目最宝贵的工程资产。
- V2 的**范围假设**（单通道、单后端、无真实 skill、自研只留口）全部作废。
- V2 未关闭的人工闸门（Phase 5 live WeCom UAT、Phase 8 律师试运行、QQ live 验收）**继续携带**，不因 V3 开启而自动关闭。
- `docs/requirements/V2-PRD.md` 保留为历史文档，不再是活跃需求源。

---

*本文件为 V3 活跃产品规格。GSD 工件见 `.planning/REQUIREMENTS.md` 与 `.planning/ROADMAP.md`；选型证据见 `.planning/research/V3-SELECTION.md`。*
