# Requirements: 墨律 InkStatute — v3.0 Unified Legal Core

**Defined:** 2026-08-06
**Source:** `docs/requirements/V3-PRD.md`
**Evidence:** `.planning/research/V3-SELECTION.md`
**Core Value:** 一套法律能力核心，通过同一套事件词汇同时服务所有客户端（web / 桌面 / 移动浏览器 / WeCom / QQ）和所有 agent 后端（Hermes / Codex / Claude Code / 墨律自研）——客户端不知道后端是谁，后端不知道通道是谁，396 个真实法律 skill 对所有后端一视同仁。

---

## v3.0 Requirements

### EVT — 统一事件契约

- [x] **EVT-01**: 定义与 ACP v1 `session/update` 同构的统一事件词汇（`session.started` / `message.delta` / `message.completed` / `thought.delta` / `tool_call.*` / `plan.updated` / `phase.changed` / `elicitation.requested` / `permission.requested` / `artifact.created` / `citation.recorded` / `run.state_changed` / `error`），产出 JSON Schema + Python 绑定 + TypeScript 绑定
- [x] **EVT-02**: `RunEvent` 重新规格化为统一事件词汇的承载体，保留 `occurred_at` / `ingested_at` / `seq` 语义，支持乱序回放与按 `seq` 断线续传
- [x] **EVT-03**: 澄清提问契约（2-4 题、单选 / 多选 / 自由文本），与 `ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md` 语义一致，并与 V2 `RunInterrupt` 对齐
- [ ] **EVT-04**: 五相进度契约（research → intake → retrieval → draft → review）及其与 thinking / tool / streaming / review 的映射
- [ ] **EVT-05**: 每类事件定义 bot 非流式降级行为（缓冲 / 投递 / 丢弃 / 折叠为业务化提示），降级规则可测
- [ ] **EVT-06**: V2 的 5 个 schema（AgentTurn / AgentResult / ExecutionTrace / FeedbackEvent / RouteDecision）保留不变作为落库契约，由事件流投影生成；现有 28 个 gate 保持绿

### ACP — 后端层

- [ ] **ACP-01**: Python ACP client（stdio，锁定协议 v1，`initialize` 版本与能力协商），实现 `BackendAdapter` 9 方法 Protocol
- [ ] **ACP-02**: `hermes acp` 后端可用，含能力探测与 Hermes 版本兼容矩阵；替代 `packages/backends/hermes` 的自定义 HTTP runs API
- [ ] **ACP-03**: 至少一个额外 ACP 后端（`codex-acp` 或 `claude-agent-acp`）跑通同一契约，证明后端可替换性
- [ ] **ACP-04**: ACP `session/update` ⟷ 统一事件双向映射（含 `tool_call_update` / `plan` / `elicitation` / `request_permission`），往返语义无损
- [ ] **ACP-05**: 输出边界在事件桥上强制执行——后端 meta / gateway / system / update / command / help / `available_commands_update` / `terminal` 类内容不得到达普通用户
- [ ] **ACP-06**: ACP 会话与子进程生命周期管理（new / resume / cancel / close、超时回收、崩溃重启），契约预留 `backend_process_mode`（`per_session` / `pooled` / `remote`）
- [ ] **ACP-07**: 权限请求安全默认——`terminal` / `execute_code` 类权限请求必须显式拒绝或上抛用户审批，服务端不得默认 allow

### GW — 统一网关与通道层

- [ ] **GW-01**: 统一 Gateway HTTP API（`/v1/sessions`、`/v1/runs`、`/v1/runs/{id}/events` SSE、`/v1/runs/{id}/elicitation`、`/v1/runs/{id}/approvals`、`/v1/artifacts/{id}`、`/v1/uploads`、`/v1/feedback`、`/v1/skills`）
- [ ] **GW-02**: SSE 流式传输统一事件，支持 `Last-Event-ID` 按 `seq` 断线续传，不重复不丢失
- [ ] **GW-03**: 多租户鉴权与会话（延续 RBAC + 会话 cookie + Bearer token）；自用形态可用单租户默认值，但契约字段不省略
- [ ] **GW-04**: 附件上传与产物下载 reference-first（返回 `attachment_ref` / `artifact_id`，不落敏感全文），下载需鉴权 + 租户校验
- [ ] **GW-05**: 取代 `apps/platform_api` 与 `services/lawyer-web-chat` 的职责重叠，全项目单一网关
- [ ] **GW-06**: `ChannelAdapter.verify_and_ack` 降级为可选 capability，web / 桌面通道不实现亦合法

### UI — 客户端

- [ ] **UI-01**: `packages/ui-core` 共享 SolidJS 组件包，从 `lawyer-desktop` 的 23 个组件与 21 个 CSS（`molv-tokens.css` / `molv-base.css`，墨律三主题）抽取
- [ ] **UI-02**: 统一事件流客户端（SSE consumer + 渲染状态机），一份实现供所有客户端复用
- [ ] **UI-03**: 流式对话 + ask_user 澄清卡片 + 文书预览 + 引用面板 + 五相进度，全部在 `ui-core` 内实现
- [ ] **UI-04**: Web 客户端交付，响应式，桌面浏览器与移动浏览器均可用
- [ ] **UI-05**: 桌面客户端交付——复用 `lawyer-desktop` 的 Tauri 外壳，57 个 `invoke()` 改指 Gateway HTTP/SSE，保留本地工作区索引，离线只读历史与已生成文书
- [ ] **UI-06**: 全项目 chat 消息列表 / 流式渲染 / ask_user 卡片 / 文书预览 / 引用面板**只有一份实现**（消除 lawyer-desktop 与 lawyer-ai 之间约 80% 的重复）

### BOT — 社交通道

- [ ] **BOT-01**: WeCom 与 QQ 通道复用同一事件流，实现非流式降级（事件聚合 + "仍在处理"业务化推送 + 最终投递）
- [ ] **BOT-02**: `services/wecom-service` 与 `services/qqbot-service` 改为 Gateway 事件流消费者，不再各自持有 agent 调用
- [ ] **BOT-03**: 现有生产行为不回退——WeCom 5 秒 ACK / AES-CBC 验签解密 / 模板卡片、QQ ED25519 验签 / 回调校验、双方幂等与重试

### SKILL — 能力层

- [ ] **SKILL-01**: 真实扫描并索引 `ai-for-china-legal`（345 个 SKILL.md）与 `legal-skills`（51 个 SKILL.md），产出机器可读 `skill-index.json`
- [ ] **SKILL-02**: 索引在**不修改任一 skill 仓**的前提下生成；正确区分约 60 个编排入口与约 285 个叶子子技能；正确解析 frontmatter、父子关系、`plugin.json`
- [ ] **SKILL-03**: 索引记录 `token_estimate`、`declared_gates`、`referenced_resources`、`practice_profile_dependency`、`host_assumptions`、`required_scripts`，供路由、可观测与上下文预算使用
- [ ] **SKILL-04**: 双仓合并与冲突模型——命名空间隔离、`legal-` 前缀、四态冲突分类（`in-sync` / `upstream-changed` / `both-changed` / `local-missing`），继承 `lawfirm-profile/scripts/sync_legal_skills.py` 语义
- [ ] **SKILL-05**: skill 物化器——把语料按每个后端期望的布局落地（Hermes profile / ACP agent skills / 自研 core），一份 skill 三处可用；宿主假设按目标后端改写
- [ ] **SKILL-06**: 元数据 / 正文 / 工具依赖三分离；正文按需注入且受上下文预算约束（实测正文 2K–20K token）
- [ ] **SKILL-07**: `packages/router-service` 数据源从 4 条手写元数据换成真实索引；移植 `lawfirm-profile/scripts/router.py` 的 12 条强信号正则与 0.4 软匹配阈值，行为不回退
- [ ] **SKILL-08**: 移植 `lawyer-desktop/src-tauri/src/skills/agent_classifier.rs` 的 Chat / Draft / Evidence 三模式判定与 continue / switch / aside 动作
- [ ] **SKILL-09**: 废弃 `solutions/lawfirm/manifest.json` 的 4 条手写 skill 元数据作为 skill 源；manifest 只保留 persona / output_policy / MCP / industry_context / secret_templates

### PROF — 执业配置

- [ ] **PROF-01**: per-plugin `CLAUDE.md` 执业配置机制升级为平台侧多租户配置（审查立场、升级矩阵、文书风格、管辖识别、交易破坏者），覆盖约 50 个依赖它的 skill
- [ ] **PROF-02**: 未配置时降级"临时模式"，并在每个输出上标记
- [ ] **PROF-03**: 冷启动访谈可通过统一事件词汇的 `elicitation.requested` 完成配置采集

### CORE — 自研 agent 核心（Python）

- [ ] **CORE-01**: `packages/agent-core` async 流式 turn loop——首字节即流，**工具轮也流式**，不得整轮缓冲（修复 lawyer-desktop 现状缺陷）
- [ ] **CORE-02**: 工具层——澄清提问、法规检索、文件读取、文档生成、MCP client；工具结果回注与多轮工具编排
- [ ] **CORE-03**: Word 原生修订 docx 产出能力，直接复用 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节）的能力，不重写
- [ ] **CORE-04**: 上下文预算与裁剪策略，处理 skill 正文 2K–20K token 的注入成本
- [ ] **CORE-05**: 移植 `lawyer-desktop/src-tauri/src/skills/router.rs`（627 行）的中文法律 prompt 装配、research-gate 注入、检索工具映射、引用书写规范
- [ ] **CORE-06**: 移植 `lawyer-desktop/src-tauri/src/llm/tool_leak.rs`（392 行）的工具调用泄漏检测与解析（DSML / XML 变体、全角字符归一、重试），用 Rust 侧现有测试用例作为对拍集
- [ ] **CORE-07**: 移植 citation 审计（引用抽取 + 核验 + verified / retrieved / unverified 标注）
- [ ] **CORE-08**: 四条法律护栏在核心中代码级强制——research-gate 前置、ask-user-enforcement 阻断、citation 审计、de-AI polish
- [ ] **CORE-09**: 多 provider 模型层（OpenAI 兼容 / Anthropic / Ollama），由 `packages/backends/provider_model` 归并而来，复用 `packages/model-gateway` 的熔断 / 限流 / 成本追踪
- [ ] **CORE-10**: 双入口一份实现——in-process `BackendAdapter`（`backend_id="inkstatute"`）+ `inkstatute-agent acp` 标准 ACP agent 入口，`--check` 可通过

### CONV — 存量收敛

- [ ] **CONV-01**: `packages/backends/hermes`（1,843 行）与 `packages/backends/codex`（2,032 行）退役，能力归并进 ACP adapter；兼容矩阵与 bootstrap 检查逻辑迁移不丢失
- [ ] **CONV-02**: `packages/channels/web_sse`（fixture-only）与 `apps/web_chat`（原型渲染器）退役
- [ ] **CONV-03**: `services/lawyer-web-chat`（1,331 行）归并进统一 Gateway；`services/hermes-contract-layer`（1,205 行）缩减为 Hermes 专属配置
- [ ] **CONV-04**: `packages/multi-agent-adapter` 标记 experimental 冻结（不删不扩）
- [ ] **CONV-05**: gate 体系更新——为新增包补 gate，移除已退役包的 gate，`gate-coverage` meta-test 保持"每个 `packages/*/src` 与 `services/*/src` 都被覆盖"且全绿

### SAFE — 安全与法律安全

- [ ] **SAFE-01**: 高风险法律结论保持人审——不自动合成 skill、不自动修改法律结论类 skill、`skill_candidate.requires_human_review` 恒为 true
- [ ] **SAFE-02**: 契约日志 reference-first（`raw_payload_ref`），不存敏感全文；secrets 不入仓 / 不入日志 / 不入契约事件；ACP 子进程凭据经环境注入
- [ ] **SAFE-03**: 输出边界贯穿事件桥与 Gateway 两处，后端 meta / gateway / system 噪声不得到达普通律师用户
- [ ] **SAFE-04**: research-gate 与 citation 审计不可绕过——法律结论必须有依据来源标注
- [ ] **SAFE-05**: skill 语料以只读 vendoring 引用，平台不写回 skill 仓
- [ ] **SAFE-06**: 可组合性保持——非法律合成任务（`solutions/demo_non_legal`）必须跑通契约层，法律专用字段只在 `industry_context`

---

## v4 Requirements（本期不做，已登记）

### MOBILE — 移动原生 App

- **MOBILE-01**: Android APK / 厂商商店分发
- **MOBILE-02**: iOS App Store 中国区上架（需 ICP 备案）
- **MOBILE-03**: Tauri 2 mobile 或 Capacitor 打包路径选型与验证

### SCALE — SaaS 规模化

- **SCALE-01**: ACP agent 进程池 / daemon 模型（替代每会话一子进程）
- **SCALE-02**: 远程 ACP 传输（等 v2 Streamable HTTP / WebSocket 稳定）
- **SCALE-03**: 水平扩容与租户级资源隔离

### OFFLINE — 桌面端完全离线

- **OFFLINE-01**: 桌面端嵌入本地 agent runtime
- **OFFLINE-02**: 本地模型推理与本地 skill 执行

### FUTURE — 其他候选

- **FUTURE-01**: `managed-agent-cookbooks` 定时监控 agent（案例 / 工商变更 / 期限 / 法规监控）
- **FUTURE-02**: WeChat 小程序通道
- **FUTURE-03**: 向量检索 / embedding RAG（当前沿用 SQLite FTS5）
- **FUTURE-04**: A2A 协议对齐（跨组织 agent 互操作）
- **FUTURE-05**: AG-UI 适配层（第三方 UI 接入）
- **FUTURE-06**: `packages/multi-agent-adapter` 产品化

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| 重建 Hermes core | Hermes 是 ACP 后端之一，不是被替代对象 |
| 复制 skill 语料进平台仓 | 立刻产生第四份分叉；两仓有各自 license（含 CC-BY-NC）、作者与演进节奏 |
| 平台自建 skill 执行 runtime | 所有候选后端都原生加载 SKILL.md；平台建索引 + 物化器即可 |
| 通道层对齐 AG-UI / Vercel AI SDK | 所有客户端均为第一方，零互操作收益，净增依赖 |
| 后端层对齐 A2A | A2A 是跨组织 agent↔agent，层次不对 |
| ACP v2 特性 | v2 为 draft 且已知破坏性变更；锁 v1，v2 特性开关关闭 |
| 自研核心用 Rust / TypeScript | Word 原生修订能力退化 + skill 语料 140 个 .py 仍需 Python；离线优势因"在线为主"失效 |
| `services/admin-web-ui` 并入 `ui-core` | 运维控制台与律师端 UI 无关，强行统一是过度抽象 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVT-01 | Phase 88 | Complete |
| EVT-02 | Phase 88 | Complete |
| EVT-03 | Phase 88 | Complete |
| EVT-04 | Phase 88 | Pending |
| EVT-05 | Phase 88 | Pending |
| EVT-06 | Phase 88 | Pending |
| ACP-01 | Phase 89 | Pending |
| ACP-02 | Phase 89 | Pending |
| ACP-03 | Phase 89 | Pending |
| ACP-06 | Phase 89 | Pending |
| ACP-04 | Phase 90 | Pending |
| ACP-05 | Phase 90 | Pending |
| ACP-07 | Phase 90 | Pending |
| GW-01 | Phase 91 | Pending |
| GW-02 | Phase 91 | Pending |
| GW-03 | Phase 91 | Pending |
| GW-04 | Phase 91 | Pending |
| GW-05 | Phase 91 | Pending |
| GW-06 | Phase 91 | Pending |
| UI-01 | Phase 92 | Pending |
| UI-02 | Phase 92 | Pending |
| UI-03 | Phase 92 | Pending |
| UI-06 | Phase 92 | Pending |
| UI-04 | Phase 93 | Pending |
| UI-05 | Phase 94 | Pending |
| BOT-01 | Phase 95 | Pending |
| BOT-02 | Phase 95 | Pending |
| BOT-03 | Phase 95 | Pending |
| SKILL-01 | Phase 96 | Pending |
| SKILL-02 | Phase 96 | Pending |
| SKILL-03 | Phase 96 | Pending |
| SKILL-04 | Phase 96 | Pending |
| SKILL-05 | Phase 97 | Pending |
| SKILL-06 | Phase 97 | Pending |
| SKILL-09 | Phase 97 | Pending |
| SKILL-07 | Phase 98 | Pending |
| SKILL-08 | Phase 98 | Pending |
| PROF-01 | Phase 99 | Pending |
| PROF-02 | Phase 99 | Pending |
| PROF-03 | Phase 99 | Pending |
| CORE-01 | Phase 100 | Pending |
| CORE-04 | Phase 100 | Pending |
| CORE-09 | Phase 100 | Pending |
| CORE-02 | Phase 101 | Pending |
| CORE-03 | Phase 101 | Pending |
| CORE-05 | Phase 102 | Pending |
| CORE-06 | Phase 102 | Pending |
| CORE-07 | Phase 102 | Pending |
| CORE-08 | Phase 102 | Pending |
| CORE-10 | Phase 103 | Pending |
| CONV-01 | Phase 104 | Pending |
| CONV-02 | Phase 104 | Pending |
| CONV-03 | Phase 104 | Pending |
| CONV-04 | Phase 104 | Pending |
| CONV-05 | Phase 104 | Pending |
| SAFE-01 | Phase 102 | Pending |
| SAFE-02 | Phase 90 | Pending |
| SAFE-03 | Phase 90 | Pending |
| SAFE-04 | Phase 102 | Pending |
| SAFE-05 | Phase 96 | Pending |
| SAFE-06 | Phase 104 | Pending |

**Coverage:**

- v3.0 requirements: 61 total
- Mapped to phases: 61
- Unmapped: 0 ✓

---

## Definition of Done

v3.0 完成的判定条件（全部满足）：

1. **契约与 CI**：新增 gate 全绿；现有 28 gate 保持绿；`gate-coverage` meta-test 绿；ACP 映射双向往返测试通过；可组合性合成任务不因 V3 改造失败。
2. **后端可替换性**：同一条律师任务，分别用 `backend_id=hermes`（ACP）与 `backend_id=inkstatute`（自研）跑通，通道层与 UI 代码零改动，事件流形状一致。
3. **通道一致性**：同一条律师任务，在 Web、桌面 App、WeCom bot 三处发起，都得到正确的最终答复、产物文件、澄清卡片与反馈回路；Web 与桌面看到流式与五相进度，WeCom 看到聚合结果与"仍在处理"提示。
4. **能力层**：skill 索引覆盖 396 个真实 SKILL.md 且生成过程不修改任一 skill 仓；物化产物可被 `hermes acp` 加载；`router.py` 的 12 条强信号规则行为不回退。
5. **自研核心**：工具轮流式（工具执行期间无整轮静默）；Word 原生修订 docx 产出成功；四条法律护栏有测试覆盖；`inkstatute-agent acp --check` 通过。
6. **存量收敛**：约 5,465 行退役代码已移除且无回归；逐包去向表全部执行到位。

## Human Gates（不得由自动化声称通过）

| Gate | 内容 | 状态 |
|---|---|---|
| **HG-1 法律质量** | 移植后的 prompt 装配与法律护栏，须由律师抽样确认输出质量不低于现有 lawyer-desktop / Hermes | 未开始 |
| **HG-2 真机通道** | WeCom 与 QQ 的 live 收发验收 | 继承 V2，未关闭 |
| **HG-3 律师试运行** | 5 工作日 / 15 真实任务 | 继承 V2，未关闭 |
| **HG-4 修订稿质量** | Word 原生修订 docx 须由律师确认可直接用于对外谈判 | 未开始 |

---

*Requirements defined: 2026-08-06*
*Last updated: 2026-08-06 after V3 architecture re-scoping*
