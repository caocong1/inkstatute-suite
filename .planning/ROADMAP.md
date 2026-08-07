# Roadmap: 墨律 InkStatute

## Milestones

- 🚧 **v3.0 Unified Legal Core** — Phases 88-104 (in progress, started 2026-08-06)
- ✅ **V2 PRD Foundation** — Phases 1-8 (2026-06-30; Phase 5/8 human gates carried)
- ✅ **v1.1 Platform Foundation** — Phases 09-13 (2026-06-30)
- ✅ **v1.2 Conversational Context and Memory Foundation** — Phases 14-19 (2026-07-02)
- ✅ **v1.3 Production Memory System and Evaluation Spikes** — Phases 20-25.1 (2026-07-02)
- ✅ **v1.4 Long-Term Memory Productization** — Phases 26-32 (2026-07-03)
- ✅ **v1.5 V2 Acceptance Closure** — Phases 33-35 (2026-07-03)
- ✅ **v1.6 M2 Multi-Backend & Platform Extensions** — Phases 36-44 (2026-07-04)
- ✅ **v1.7 M3 Platform Extensions** — Phases 45-57.1 (2026-07-06)
- ✅ **v1.8 QQBot Channel Production** — Phases 58-67 (2026-07-09)
- ✅ **v1.9 QQBot Host Composition** — Phases 68-72 (2026-07-10)
- ✅ **v1.10 Operator Config Console** — Phases 73-78.1 (2026-07-12)
- ✅ **v1.11 Product Console** — Phases 79-87 (2026-07-15)

<details>
<summary>✅ v1.x archives (Phases 1-87) — SHIPPED</summary>

All v1.x phase details, requirements, and audits are archived under `.planning/milestones/`.
See `.planning/MILESTONES.md` for the consolidated history.

Carried human gates from v1.x (NOT closed by v3.0):

- Phase 5 live WeCom UAT operator confirmation
- Phase 8 five-workday lawyer trial acceptance
- Operator `--live` QQ OpenAPI acceptance evidence

</details>

---

## 🚧 v3.0 Unified Legal Core (In Progress)

**Milestone Goal:** 一套法律能力核心，通过同一套事件词汇同时服务所有客户端（web / 桌面 / 移动浏览器 / WeCom / QQ）和所有 agent 后端（Hermes / Codex / Claude Code / 墨律自研），并让 396 个真实法律 skill 首次进入平台。

**Source:** `docs/requirements/V3-PRD.md` · **Evidence:** `.planning/research/V3-SELECTION.md`

**Stages:**

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 协议底座 | 88-90 | Hermes 可通过 ACP 被平台驱动 |
| B 通道统一 | 91-95 | **律师可在 web / 桌面 / WeCom / QQ 四处用同一套能力** |
| C 能力层 | 96-99 | **396 个真实法律 skill 首次进入平台** |
| D 自研核心 | 100-104 | 心脏换成自研，通道层零改动 |

**关键路径：** 88 → 89 → 90 → 91 → 92 → 93（走完即有可用 Web 产品）

## Phases

### 阶段 A — 协议底座

- [x] **Phase 88: Unified Event Contract** - ACP 同构的统一事件词汇 + Schema/绑定 + 降级规则 + V2 契约保持 (EVT-01..06)
- [x] **Phase 89: ACP Backend Client** - Python ACP client 驱动 hermes acp 与第二后端，子进程生命周期 (ACP-01, ACP-02, ACP-03, ACP-06)
- [x] **Phase 90: ACP Event Bridge & Output Boundary** - 双向映射 + 输出边界 + 权限安全默认 (ACP-04, ACP-05, ACP-07, SAFE-02, SAFE-03)

### 阶段 B — 通道统一

- [x] **Phase 91: Unified Gateway** - 多租户 HTTP+SSE 网关，取代 platform_api 与 lawyer-web-chat 的重叠 (GW-01..06)
- [x] **Phase 92: Shared UI Core** - 从 lawyer-desktop 抽取 @inkstatute/ui-core，chat UI 单一实现 (UI-01, UI-02, UI-03, UI-06) ✅
- [x] **Phase 93: Web Client** - 响应式 Web 客户端（桌面 + 移动浏览器） (UI-04) ✅
- [x] **Phase 94: Desktop Client** - Tauri 外壳复用，invoke() → Gateway，离线只读 (UI-05) ✅
- [x] **Phase 95: Bot Channel Degradation** - WeCom/QQ 改为 Gateway 消费者 + 非流式降级 (BOT-01, BOT-02, BOT-03) ✅ COMPLETE

### 阶段 C — 能力层

- [x] **Phase 96: Real Skill Index** - 真实索引 396 个 SKILL.md，双仓合并与冲突模型 (SKILL-01..04, SAFE-05) ✅
- [x] **Phase 97: Skill Materialization** - 按后端物化，三分离，废弃假 manifest skill 源 (SKILL-05, SKILL-06, SKILL-09) ✅ COMPLETE
- [x] **Phase 98: Real-Index Routing** - 路由换真实索引 + 移植强信号规则与三模式判定 (SKILL-07, SKILL-08) ✅ COMPLETE
- [x] **Phase 99: Practice Profile** - CLAUDE.md 执业配置多租户化 + 临时模式 + 冷启动访谈 (PROF-01, PROF-02, PROF-03) ✅ COMPLETE

### 阶段 D — 自研核心

- [ ] **Phase 100: Agent Core Skeleton** - Python async 流式 turn loop（工具轮也流式）+ 上下文预算 + 模型层 (CORE-01, CORE-04, CORE-09) — Plans 100-01, 100-02, 100-03 complete (scaffold + EventEmitter + config + model layer + context assembler + turn loop + messages)
- [ ] **Phase 101: Agent Core Tools** - 工具层 + Word 原生修订 docx (CORE-02, CORE-03)
- [ ] **Phase 102: Legal Guardrail Port** - prompt 装配 / tool_leak / citation 审计 / 四护栏移植 (CORE-05..08, SAFE-01, SAFE-04)
- [ ] **Phase 103: Dual Entry Points** - in-process BackendAdapter + inkstatute-agent acp (CORE-10)
- [ ] **Phase 104: Legacy Convergence** - 退役 ~5,465 行存量 + gate 体系更新 (CONV-01..05, SAFE-06)

---

## Phase Details

### Phase 88: Unified Event Contract

**Goal**: 平台有一套与 ACP v1 `session/update` 同构的统一事件词汇，能同时承载客户端 SSE 与后端 ACP 两条链路，且每类事件都定义了 bot 非流式降级行为；V2 的 5 个落库 schema 与 28 个 gate 完全不受影响
**Depends on**: Nothing (first v3.0 phase)
**Requirements**: EVT-01, EVT-02, EVT-03, EVT-04, EVT-05, EVT-06
**Success Criteria** (what must be TRUE):

  1. `packages/platform-contract` 导出 13 类统一事件（`session.started` / `message.delta` / `message.completed` / `thought.delta` / `tool_call.started|delta|completed` / `plan.updated` / `phase.changed` / `elicitation.requested` / `permission.requested` / `artifact.created` / `citation.recorded` / `run.state_changed` / `error`），每类都有 JSON Schema、Python 绑定、TypeScript 绑定，且 schema 校验测试全过
  2. ✅ `RunEvent` 被重新规格化为统一事件的承载体，保留 `occurred_at` / `ingested_at` / `seq`；乱序回放测试与"按 `seq` 从任意断点续传不重复不丢失"测试通过 (EVT-02 complete, Plan 88-02)
  3. ✅ 澄清提问契约支持 2-4 题、单选 / 多选 / 自由文本，字段语义与 `ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md` 一致（含 `allow_multiple`），并能与 V2 `RunInterrupt` 的 `interrupt_id` / `resume_state_ref` 互转 (EVT-03 complete, Plan 88-03)
  4. ✅ 五相进度（research → intake → retrieval → draft → review）契约存在，且有到 thinking / tool / streaming / review 的映射表与测试 (EVT-04 complete, Plan 88-04)
  5. ✅ 每类事件的 bot 降级行为（缓冲 / 投递 / 丢弃 / 折叠为业务化提示）在代码中声明且可测——给定一串事件，聚合器产出确定的最终投递内容 (EVT-05 complete, Plan 88-05)
  6. ✅ 现有 28 个 gate 全绿，V2 的 5 个 schema 字段无一改动或删除 (EVT-06 complete, Plan 88-06)

**Plans**: TBD (est. 3-4)
**UI hint**: no

### Phase 89: ACP Backend Client

**Goal**: 平台能以 Python ACP client 驱动任意 ACP agent 作为后端，`hermes acp` 生产可用，并有第二个 ACP 后端跑通同一契约以证明可替换性；子进程生命周期受控
**Depends on**: Phase 88
**Requirements**: ACP-01, ACP-02, ACP-03, ACP-06
**Success Criteria** (what must be TRUE):

  1. `packages/acp-client` 实现 `BackendAdapter` 的 9 方法 Protocol，基于 PyPI `agent-client-protocol`，锁定协议 v1 并在 `initialize` 做版本与能力协商；不满足所需能力的 agent 被明确拒绝而非静默降级
  2. `backend_id="hermes"` 通过 `hermes acp` 可用：能创建会话、发送 prompt、收到流式 `session/update`、取消、关闭；含 Hermes 版本兼容矩阵与 `bootstrap_check`
  3. 第二个 ACP 后端（`codex-acp` 或 `claude-agent-acp`）跑通同一条测试路径，证明换 `backend_id` 不需要改任何调用方代码
  4. 子进程生命周期受控：会话结束回收、超时回收、崩溃可重启且不泄漏进程；有测试断言无孤儿进程
  5. 契约暴露 `backend_process_mode`（`per_session` / `pooled` / `remote`），当前实现 `per_session`，其余枚举值存在但未实现且被显式标记
  6. 无网络/无外部 agent 的 CI 环境下，用 fixture ACP agent（本仓自带的 echo agent）跑通全部测试

**Plans**: TBD (est. 3-4)
**UI hint**: no

### Phase 90: ACP Event Bridge & Output Boundary

**Goal**: ACP 事件与统一事件之间双向无损映射，且输出边界与权限安全默认在这个桥上强制执行——后端噪声与危险权限请求不可能穿过
**Depends on**: Phase 89
**Requirements**: ACP-04, ACP-05, ACP-07, SAFE-02, SAFE-03
**Success Criteria** (what must be TRUE):

  1. ACP `session/update` 的每个变体（`agent_message_chunk` / `agent_thought_chunk` / `tool_call_update` / `plan` / `usage_update` 等）与统一事件双向映射，往返测试语义无损
  2. ACP `elicitation/create` 与 `session/request_permission` 正确映射为 `elicitation.requested` / `permission.requested`，用户答复能正确回注到 ACP 侧
  3. 输出边界在桥上强制执行：给定一组后端 meta / gateway / system / update / command / help / `available_commands_update` / `terminal` 类内容的 fixture，全部被阻断或改写为 InkStatute 业务化提示，无一到达普通用户事件流
  4. 权限安全默认：`terminal` / `execute_code` 类权限请求被显式拒绝或上抛为用户审批，**服务端不得默认 allow**；有测试断言不存在自动 `allow_once` 路径
  5. secrets 不出现在任何契约事件、日志或落库记录中；ACP 子进程凭据仅经环境注入；有隐私扫描测试
  6. 契约日志保持 reference-first（`raw_payload_ref`），不存敏感全文

**Plans**: TBD (est. 3)
**UI hint**: no

### Phase 91: Unified Gateway ✅ COMPLETE

**Goal**: 全项目只有一个面向客户端的入口——多租户 HTTP + SSE Gateway，`apps/platform_api` 与 `services/lawyer-web-chat` 的职责重叠被消除
**Depends on**: Phase 90
**Requirements**: GW-01, GW-02, GW-03, GW-04, GW-05, GW-06 (all complete)
**Success Criteria** (what must be TRUE):

  1. ✅ `services/gateway`（由 `apps/platform_api` 升级而来）提供全部端点：`/v1/sessions`、`/v1/sessions/{id}`、`/v1/sessions/{id}/runs`、`/v1/runs/{id}`、`/v1/runs/{id}/events`(SSE)、`/v1/runs/{id}/elicitation`、`/v1/runs/{id}/approvals`、`/v1/artifacts/{id}`、`/v1/uploads`、`/v1/feedback`、`/v1/skills`，且有 OpenAPI 文档 (GW-01 complete, Plan 91-05)
  2. ✅ SSE 流式传输统一事件；客户端带 `Last-Event-ID` 重连后从正确 `seq` 续传，集成测试断言不重复不丢失 (GW-02 complete, Plan 91-02)
  3. ✅ 鉴权可用：RBAC + 会话 cookie（web/桌面）与 Bearer token（bot/程序化）；租户校验生效；自用形态可用单租户默认值但契约字段不省略 (GW-03 complete, Plan 91-05)
  4. ✅ 附件上传返回 `attachment_ref`、产物下载经 `artifact_id`，均 reference-first 且需鉴权 + 租户校验；跨租户访问被拒 (GW-04 complete, Plan 91-03)
  5. ✅ `services/lawyer-web-chat` 的能力（SSE 编码、会话鉴权、多设备会话列表、上传、反馈）已在 Gateway 中等价可用，旧服务标记 deprecated (GW-05 complete, Plan 91-04)
  6. ✅ `ChannelAdapter.verify_and_ack` 已降级为可选 capability，不实现它的通道适配器仍能通过 Protocol 校验与 gate (GW-06 complete, Plan 91-04)

**Plans**: 5 (91-01 Gateway Tracer + 91-02 SSE Replay + 91-03 Upload/Artifact/Feedback + 91-04 Skills/verify_and_ack/Deprecation + 91-05 OpenAPI/Integration/Verification)
**UI hint**: no

### Phase 92: Shared UI Core

**Goal**: 存在一个共享 SolidJS 组件包，chat 相关 UI 在全项目只有一份实现，且它消费统一事件流而不是任何平台专属 IPC
**Depends on**: Phase 91
**Requirements**: UI-01, UI-02, UI-03, UI-06
**Success Criteria** (what must be TRUE):

  1. `packages/ui-core` 存在，包含从 `lawyer-desktop` 迁入的组件与墨律三主题（`molv-tokens.css` / `molv-base.css`，`data-theme="a|b|c"`），且不依赖任何 `@tauri-apps/*` 包
  2. 统一事件流客户端（SSE consumer + 渲染状态机）在 `ui-core` 内实现一次，能消费 Phase 88 定义的全部 13 类事件；有 fixture 事件流驱动的渲染测试
  3. 流式对话、ask_user 澄清卡片（单选/多选/自由文本）、文书预览、引用面板、五相进度全部在 `ui-core` 内实现并可独立测试
  4. `packages/platform-sdk-ts` 生成统一事件词汇的 TS 绑定，`ui-core` 使用它而非手写类型
  5. 全项目 grep 不到第二份 chat 消息列表 / 流式渲染 / ask_user 卡片实现；`apps/web_chat` 原型渲染器被标记 deprecated
  6. `ui-core` 有构建产物与类型声明，可被 `apps/web` 与 `apps/desktop` 同时依赖

**Plans**: 4 (92-01 Tracer: scaffold+theme+reducer+ChatPanel+fixtures ✅ | 92-02 Chat interaction components ✅ | 92-03 Document preview + citations ✅ | 92-04 Full integration ✅)
**UI hint**: yes

### Phase 93: Web Client

**Goal**: 律师可以打开浏览器（桌面或手机）登录墨律，完成一轮完整的法律任务，看到流式回复、澄清卡片、文书产物与引用
**Depends on**: Phase 92
**Requirements**: UI-04
**Success Criteria** (what must be TRUE):

  1. `apps/web` 存在并可构建运行，使用 `packages/ui-core`，通过 Gateway HTTP/SSE 与平台通信，零自有 chat UI 代码
  2. 桌面浏览器下可完成：登录 → 新建会话 → 发送任务（含附件上传）→ 看到流式回复与五相进度 → 回答澄清卡片 → 下载产物 → 提交反馈
  3. 移动浏览器下同一流程可用，布局响应式（无横向滚动、触摸目标可点、澄清卡片可用）
  4. 断线重连后事件流从正确位置续传，界面不重复渲染已收到的内容
  5. 会话在多设备间可见（同一租户/用户在另一浏览器登录能看到会话列表与历史）
  6. 端到端测试覆盖上述主流程（可用 fixture 后端，不依赖真实 LLM）

**Plans**: 4 (93-01 Tracer + 93-02 Workspace SSE + 93-03 Gateway stubs + 93-04 Mobile/E2E)
**UI hint**: yes

### Phase 94: Desktop Client

**Goal**: 桌面 App 复用同一份 UI 与同一个 Gateway，不再持有自己的 agent 逻辑；离线时可只读历史与已生成文书
**Depends on**: Phase 92
**Requirements**: UI-05
**Success Criteria** (what must be TRUE):

  1. `apps/desktop` 存在，由 `lawyer-desktop` 的 Tauri 外壳迁入，使用 `packages/ui-core`，Windows 与 macOS 可构建
  2. 原 57 个 `invoke()` 调用点中，凡属于 agent / 会话 / 消息 / 技能 / 文档生成的，全部改为 Gateway HTTP/SSE；仅保留桌面专属能力（文件对话框、拖放、自动更新、本地工作区索引）为 Tauri 命令
  3. 桌面端不再包含 agent loop、LLM provider 调用、skill 加载或 MCP client——这些能力全部来自平台
  4. 离线状态下应用可启动，能查看历史会话与已下载的产物文件，发起新任务时给出明确的"需要联网"提示而非静默失败
  5. 本地工作区 FTS5 索引作为桌面专属增强保留，其检索结果可作为附件引用提交给平台
  6. 桌面端与 Web 端在同一任务上表现一致（同样的事件、同样的澄清卡片、同样的产物）

**Plans**: 4 (94-01 Tracer + 94-02 SSE/Offline/FTS5 + 94-03 invoke migration/Settings/Update + 94-04 Menus/E2E/Completion) ✅
**UI hint**: yes

### Phase 95: Bot Channel Degradation ✅ COMPLETE

**Goal**: WeCom 与 QQ 通道复用同一事件流并正确降级为非流式，现有生产行为一步不退
**Depends on**: Phase 91
**Requirements**: BOT-01, BOT-02, BOT-03 (all complete)
**Success Criteria** (what must be TRUE):

  1. ✅ 事件降级层存在：给定一串统一事件，产出 (a) 一条最终投递消息、(b) 若干"仍在处理"业务化中间推送、(c) 产物文件投递、(d) 澄清与审批的模板卡片；降级规则来自 Phase 88 的声明且有测试
  2. ✅ `services/wecom-service` 与 `services/qqbot-service` 改为 Gateway 事件流消费者，源码中不再存在直接的 agent/backend 调用
  3. ✅ WeCom 现有行为不回退：5 秒 ACK、AES-CBC 验签解密、模板卡片、媒体上传下载、幂等与重试——现有测试全绿
  4. ✅ QQ 现有行为不回退：ED25519 验签、回调校验 op=13、webhook 端口约束、幂等——现有 28 个 qqbot 测试文件全绿
  5. ✅ 同一条任务从 WeCom 发起，律师收到的内容与 Web 端最终结果语义一致（答复 + 产物 + 澄清 + 反馈卡片）
  6. ✅ 后端 meta / gateway / system 噪声在 bot 通道同样不可见（输出边界在 Gateway 与降级层双重生效）

**Plans**: 4 (95-01 Tracer ✅ + 95-02 WeCom Migration ✅ + 95-03 QQ Migration ✅ + 95-04 Cross-Channel/Completion ✅) ✅
**UI hint**: no

### Phase 96: Real Skill Index

**Goal**: 396 个真实法律 SKILL.md 首次进入平台视野——平台能在不修改任一 skill 仓的前提下生成机器可读索引
**Depends on**: Phase 90
**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04, SAFE-05
**Success Criteria** (what must be TRUE):

  1. `packages/skill-index` 能扫描 vendored 的 `ai-for-china-legal`（345 个 SKILL.md）与 `legal-skills`（51 个 SKILL.md），产出 `skill-index.json`，总数与实测一致
  2. 索引过程**只读**——有测试断言扫描前后 skill 仓文件的 mtime 与内容哈希不变
  3. 索引正确区分约 60 个编排入口与约 285 个叶子子技能，父子关系正确（从目录结构 + `plugin.json` + 编排入口正文三方交叉验证）
  4. 每条索引记录含 `token_estimate`、`declared_gates`、`referenced_resources`、`practice_profile_dependency`、`host_assumptions`、`required_scripts`、`source_repo`、`license`
  5. 双仓合并生效：命名空间隔离、上游 skill 加 `legal-` 前缀、四态冲突分类（`in-sync` / `upstream-changed` / `both-changed` / `local-missing`）可产出报告
  6. 索引器对上游目录结构变化容错——缺失 frontmatter、缺失 `plugin.json`、非常规嵌套都不导致崩溃，而是产出带警告的记录

**Plans**: 4 (96-01 scanner core ✅ | 96-02 classification+metadata ✅ | 96-03 conflict model ✅ | 96-04 gate registration + index builder + CLI + e2e ✅) ✅ COMPLETE
**UI hint**: no

### Phase 97: Skill Materialization

**Goal**: 一份 skill 语料能被三种后端各自消费——平台建的是索引 + 物化器，而不是第四份 skill 拷贝
**Depends on**: Phase 96
**Requirements**: SKILL-05, SKILL-06, SKILL-09
**Success Criteria** (what must be TRUE):

  1. 物化器能把语料落到 Hermes profile 布局（symlink 优先、脚本类 copy），且 `hermes acp` 能加载物化产物中的 skill（实测验证，不是推断）
  2. 物化器能把语料落到 ACP agent skills 布局，并按目标后端改写宿主假设（`/plugin:skill` → 自然语言触发、`ask_user` → `elicitation`）
  3. 自研 core 路径不需物化——直接读索引 + 按需读正文
  4. 元数据 / 正文 / 工具依赖三分离在代码中体现：路由只用索引，正文只在执行时按需注入，工具依赖由各后端各自满足
  5. 正文注入受上下文预算约束——给定预算，注入器能在 2K–20K token 的 skill 正文中做出确定性取舍并记录被裁剪的部分
  6. `solutions/lawfirm/manifest.json` 不再包含 4 条手写 skill 元数据；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates，且 `solution-loader` 与 `skill-registry` 的测试相应更新后全绿

**Plans**: 4 (97-01 materializer core ✅ | 97-02 context budget injector ✅ | 97-03 skill-registry migration + manifest cleanup ✅ | 97-04 CLI + e2e + phase completion ✅) ✅ COMPLETE
**UI hint**: no

### Phase 98: Real-Index Routing

**Goal**: 路由基于 396 个真实 skill 而非 4 条假元数据，且继承两处已在生产验证过的路由产品知识
**Depends on**: Phase 97
**Requirements**: SKILL-07, SKILL-08
**Success Criteria** (what must be TRUE):

  1. `packages/router-service` 的数据源换成真实 skill 索引；RULE / SKILL / HYBRID 三策略与法律风险分级保留且测试全绿
  2. `lawfirm-profile/scripts/router.py` 的 12 条强信号确定性正则（法院短信、判决书、新案件、docx 合同等）已移植，且用原 router 的输入输出作为对拍集验证行为不回退
  3. 触发短语软匹配阈值 0.4、置信度 <0.6 标歧义、`gate_before` = ask-user-enforcement、`gate_after` = legal-de-ai-polish 的语义保留
  4. `lawyer-desktop` 的 Chat / Draft / Evidence 三模式判定与 continue / switch / aside 动作已移植，含 LLM 分类失败时的规则兜底
  5. 路由决策产出 `RouteDecision` 契约事件并写决策日志，可用于后续 `route_mismatch` 反馈关联
  6. 给定一组真实律师任务样本，路由能命中具体的叶子子技能（而不是只能命中 4 个假 skill 名）

**Plans**: 3 (98-01 strong-signal + soft matcher + golden tests ✅ | 98-02 three-mode detection + LLM fallback ✅ | 98-03 decision logging + phase completion ✅) ✅ COMPLETE
**UI hint**: no

### Phase 99: Practice Profile

**Goal**: 约 50 个依赖 `CLAUDE.md` 执业配置的 skill 能在平台上正确工作，配置成为平台侧的多租户数据而非文件系统里的模板
**Depends on**: Phase 98
**Requirements**: PROF-01, PROF-02, PROF-03
**Success Criteria** (what must be TRUE):

  1. 执业配置在平台侧建模并按租户存储：审查立场（甲方/乙方各自的责任限制、违约金、知识产权、数据保护、期限终止、管辖、交易破坏者）、升级矩阵（金额阈值 + 审批层级 + 自动升级触发）、文书风格、管辖识别
  2. 执行时执业配置被注入 skill 上下文，覆盖索引中标记了 `practice_profile_dependency` 的全部 skill
  3. 未配置时降级"临时模式"：使用通用默认值，且每个输出被标记 `[临时模式]`，有测试断言标记不会遗漏
  4. 冷启动访谈可通过 `elicitation.requested` 完成——多轮 2-4 题采集，答案写回租户执业配置
  5. 执业配置的读写经 RBAC 授权，跨租户访问被拒
  6. 执业配置不含 secrets，且不进入契约事件日志

**Plans**: 3 (99-01 ✅ complete, 99-02 ✅ complete, 99-03 ✅ complete) ✅ COMPLETE
**UI hint**: no

### Phase 100: Agent Core Skeleton

**Goal**: 存在一个 Python 自研 agent 核心骨架，其流式表现优于被移植的 Rust 原版——工具轮期间客户端不会经历整轮静默
**Depends on**: Phase 97
**Requirements**: CORE-01, CORE-04, CORE-09
**Success Criteria** (what must be TRUE):

  1. `packages/agent-core` 存在，实现 async 流式 turn loop，产出 Phase 88 的统一事件；有多轮工具编排与轮次上限
  2. **工具轮流式**：工具调用期间持续产出 `thought.delta` 与 `tool_call.started|delta|completed`，测试断言从提交到最终回复之间不存在超过阈值的事件静默期（这是对 `lawyer-desktop` 现状缺陷的修复）
  3. 上下文预算与裁剪策略生效：给定 token 预算与一组 skill 正文（2K–20K token）+ 历史，装配器产出确定性的上下文并记录被裁剪内容
  4. 模型层由 `packages/backends/provider_model` 归并而来，支持 OpenAI 兼容 / Anthropic / Ollama，流式与工具调用在各 provider 间归一
  5. 模型层复用 `packages/model-gateway` 的熔断 / 限流 / 成本追踪，`usage` 数据进入事件流
  6. 全部测试可在无外部 LLM 的情况下用 fixture provider 运行

**Plans**: TBD (est. 4)
**UI hint**: no

### Phase 101: Agent Core Tools

**Goal**: 自研核心具备完成真实法律任务所需的工具，包括墨律最难也最值钱的产出——带 Word 原生修订的合同审查稿
**Depends on**: Phase 100
**Requirements**: CORE-02, CORE-03
**Success Criteria** (what must be TRUE):

  1. 工具层实现并可被 turn loop 调用：澄清提问（映射 `elicitation.requested`）、法规检索、文件读取、文档生成、MCP client（复用 `packages/mcp-registry`）
  2. 工具结果正确回注 turn loop，多轮工具编排可用；工具失败不导致整轮崩溃而是产出 `error` 事件并可恢复
  3. Word 原生修订 docx 产出成功：直接复用 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节）的能力，**不重写**；产出的 docx 在 Word 中显示为原生修订标记
  4. 产物以 `artifact.created` 事件发出，`kind` 正确区分 `docx` 与 `trackchanges_docx`，并可经 Gateway `/v1/artifacts/{id}` 下载
  5. MCP 工具（`law-database`、`wenshu`）可被发现与调用，调用摘要进入 `tool_call.*` 事件与 `ExecutionTrace.tool_calls`
  6. 工具权限遵守 Phase 90 的安全默认——不存在未经审批的 shell / 代码执行路径

**Plans**: TBD (est. 4)
**UI hint**: no

### Phase 102: Legal Guardrail Port

**Goal**: `lawyer-desktop` 里最有价值的法律产品知识被完整移植进 Python 核心，且四条法律护栏在代码级不可绕过
**Depends on**: Phase 101, Phase 99
**Requirements**: CORE-05, CORE-06, CORE-07, CORE-08, SAFE-01, SAFE-04
**Success Criteria** (what must be TRUE):

  1. `skills/router.rs`（627 行）的中文法律 prompt 装配已移植：三模式基础 prompt、research-gate 注入、检索工具映射（只承诺实际可用的工具）、引用书写规范、skill 描述清单与激活 skill 正文注入
  2. `llm/tool_leak.rs`（392 行）的工具调用泄漏检测与解析已移植：DSML / XML 变体识别、全角字符（`｜`、`▁`）归一、泄漏重试；**用 Rust 侧现有测试用例作为 Python 侧对拍集，逐条通过**
  3. citation 审计已移植：引用抽取、对照本地法规库与检索证据核验、标注 verified / retrieved / unverified，产出 `citation.recorded` 事件
  4. 四条法律护栏代码级强制且有测试：research-gate 前置（未检索不得给法律结论）、ask-user-enforcement（关键事实缺失时阻断起草）、citation 审计、de-AI polish
  5. 高风险法律安全保持：不自动合成 skill、不自动修改法律结论类 skill、`skill_candidate.requires_human_review` 恒为 true，有测试断言
  6. 建立 golden fixture 对拍集——同一输入在移植前后的 prompt 装配结果可比对，差异需被显式解释

**Plans**: TBD (est. 4-5)
**UI hint**: no
**Human gate**: HG-1 法律质量（律师抽样确认输出质量不低于现有 lawyer-desktop / Hermes）—— 不得由自动化声称通过

### Phase 103: Dual Entry Points

**Goal**: 自研核心以一份实现提供两个入口，并在架构上与其他后端完全平等——换 `backend_id` 不需要改任何通道层或 UI 代码
**Depends on**: Phase 102
**Requirements**: CORE-10
**Success Criteria** (what must be TRUE):

  1. in-process 入口：`backend_id="inkstatute"` 实现 `BackendAdapter` 9 方法，被 Gateway 直接调用，无 IPC 开销，完整可观测
  2. ACP 入口：`inkstatute-agent acp` 可启动，`inkstatute-agent acp --check` 通过，能被标准 ACP 宿主（用本仓的 fixture ACP client 验证）连接并完成一轮对话
  3. 两个入口共享同一份核心实现，无重复逻辑；有测试断言两条路径在同一输入下产生等价事件流
  4. **后端可替换性验收通过**：同一条律师任务分别用 `backend_id=hermes`（ACP）与 `backend_id=inkstatute`（in-process）跑通，通道层与 UI 代码零改动，事件流形状一致
  5. ACP 入口正确声明能力（不声明 `fs/*` / `terminal/*`），并正确实现 `elicitation` 与 `request_permission` 的 agent 侧
  6. 后端选择可经 `packages/operator-config` 配置，默认值可切换

**Plans**: TBD (est. 3)
**UI hint**: no

### Phase 104: Legacy Convergence

**Goal**: V3 承诺的存量收敛全部执行到位，仓库不再携带被取代的重复实现，且质量体系完整覆盖新结构
**Depends on**: Phase 103, Phase 95
**Requirements**: CONV-01, CONV-02, CONV-03, CONV-04, CONV-05, SAFE-06
**Success Criteria** (what must be TRUE):

  1. `packages/backends/hermes`（1,843 行）与 `packages/backends/codex`（2,032 行）已退役；其兼容矩阵与 `bootstrap_check` 逻辑已确认存在于 ACP adapter 中，无能力丢失
  2. `packages/channels/web_sse`（259 行）与 `apps/web_chat` 已退役
  3. `services/lawyer-web-chat`（1,331 行）已归并进 Gateway 并移除；`services/hermes-contract-layer`（1,205 行）已缩减为 Hermes 专属配置
  4. `packages/multi-agent-adapter` 标记 experimental 冻结（保留代码与测试，文档标注无生产消费者）
  5. gate 体系更新：新增包（`acp-client` / `skill-index` / `agent-core` / `ui-core` / `gateway`）都有 gate；已退役包的 gate 已移除；`gate-coverage` meta-test 断言每个 `packages/*/src` 与 `services/*/src` 都被覆盖且全绿
  6. 可组合性保持：`solutions/demo_non_legal` 的非法律合成任务跑通契约层，无法律专用字段泄漏到顶层 required
  7. 全量 gate 运行通过（`python scripts/run_v2_gates.py`），且 WeCom / QQ 现有生产行为回归测试全绿

**Plans**: TBD (est. 4)
**UI hint**: no

---

## Progress

**Execution Order:** 88 → 89 → 90 → 91 → 92 → 93 → 94 → 95 → 96 → 97 → 98 → 99 → 100 → 101 → 102 → 103 → 104

**Parallelization opportunities** (for wave-based execution):

- After 92: Phases 93 and 94 can run in parallel
- After 91: Phase 95 can run in parallel with 92/93/94
- After 90: Phase 96 can start in parallel with the 91-95 branch
- 100 depends on 97 (skill index/materialization), not on the B-stage channel work

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 88. Unified Event Contract | A | 6/6 | Complete    | 2026-08-07 |
| 89. ACP Backend Client | A | 3/4 | In Progress|  |
| 90. ACP Event Bridge & Output Boundary | A | 4/4 | Complete | 2026-08-07 |
| 91. Unified Gateway | B | 3/5 | In Progress|  |
| 92. Shared UI Core | B | 4/4 | Complete | 2026-08-08 |
| 93. Web Client | B | 4/4 | Complete | 2026-08-08 |
| 94. Desktop Client | B | 4/4 | Complete | 2026-08-09 |
| 95. Bot Channel Degradation | B | 4/4 | Complete | 2026-08-09 |
| 96. Real Skill Index | C | 3/4 | In Progress | - |
| 97. Skill Materialization | C | 0/TBD | Not started | - |
| 98. Real-Index Routing | C | 0/TBD | Not started | - |
| 99. Practice Profile | C | 0/TBD | Not started | - |
| 100. Agent Core Skeleton | D | 0/TBD | Not started | - |
| 101. Agent Core Tools | D | 0/TBD | Not started | - |
| 102. Legal Guardrail Port | D | 0/TBD | Not started | - |
| 103. Dual Entry Points | D | 0/TBD | Not started | - |
| 104. Legacy Convergence | D | 0/TBD | Not started | - |
