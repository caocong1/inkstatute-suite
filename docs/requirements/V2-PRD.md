# 墨律 InkStatute V2 需求规格说明书

版本：V2  
日期：2026-06-27  
仓库：`inkstatute-suite`  
中文名：墨律  
英文名：InkStatute  
前置文档：[V1-PRD.md](./V1-PRD.md)（已归档为草案，V2 取代其作为当前规格）

## 0. V1 → V2 变更摘要

V1 定位"全栈 Agent 平台 + 9 个子系统 + 律师助手行业包"，范围过大、未锁定后端、无法快速验证。

V2 基于 Sisyphus 与 Codex 五轮架构讨论达成的共识，做以下根本性收敛：

| 维度 | V1 | V2 |
|---|---|---|
| 平台形态 | 新建独立后端 + 9 子系统 | Hermes 就是后端，V2 只加薄契约层 |
| V1 范围 | 9 个子系统全部并列 | 保留 6 个模块，砍掉 11 个推到 M2–M4 |
| 会话存储 | 独立 Conversation API + 数据库 | 不建，从 Hermes sessions 映射只读视图 |
| 反馈通道 | 重新设计反馈闭环 | 沿用 Hermes 现有 hook/卡片/jsonl 链路，只标准化 |
| 长任务 | 未定义同步/异步 | 异步契约，WeCom 5s ACK + 完成后主动推送 |
| 自迭代 | 提及但未落地 | 契约层预留 `execution_trace` / `route_mismatch` / `skill_candidate`，V2 只记录不合成 |
| 可组合性 | 口头原则 | 硬验收，进 CI，合成非法律任务跑契约层 |
| 验收 | 文档完整性检查 | 律师 5 工作日 / 15 任务 / 契约覆盖率 95% / 长任务成功率 80% |
| 关键旅程 | 无 | 3 条抽样旅程，显式声明"仅验收抽样，非能力边界" |

V2 的核心判断：**平台化的第一步是契约和验收，不是重造 Hermes。** 先让律师能用、能用好用、能日常依赖，再深度迭代平台化。

## 1. 背景与目标

### 1.1 现状

Hermes `lawfirm` profile 已经是一套可运行的律师助手系统，且**当前正在被律师日常使用**：

- 人格：`SOUL.md` 定义"小律"身份、合规边界、工作底稿原则。
- 通道：gateway 运行中，企业微信 WeCom（id=155 私聊）、QQ Bot、微信三通道 connected。
- 模型：`custom:ollama-cloud`，glm-5.2，base_url `https://ollama.com/v1`。
- Skills：101 个顶层目录，通过 symlink/copy 同步约 312 个 skill，涵盖合同审查、判决书分析、法律检索、文书起草、法院短信、OPC 常法顾问等。
- Router：`scripts/router.py` 纯规则路由（正则匹配，无 LLM 调用），输出 `RouteDecision(primary_skill, supporting_skills, gate_before, gate_after, confidence, reason, matched_rule)`。
- MCP：`law-database`（flk.npc.gov.cn 法律法规检索）、`wenshu`（wenshu.court.gov.cn 裁判文书检索）。
- 闸门：`ask-user-enforcement`（强制 2-4 澄清问题）、`cn-law-research-gate`（法律检索约束）、`legal-de-ai-polish`（去 AI 化）。
- 反馈闭环已跑通：`response_filter` hook 生成 message_id + 保存 preview → `template_card_dispatcher` hook 通过 gateway WebSocket 发模板卡片 → `wecom_template_card_shim` hook 拦截按钮回调 → 写入 `feedback/feedback.jsonl`。
- 自迭代：`skillopt-runner` + down 反馈累计触发人工确认的 skill 优化流程。
- 合同审查：`contract_review_trackchanges.py` 已能产出带 Word track changes 的 docx。
- Hook 机制：`HOOK.yaml` 定义 name/description/events，`handler.py` 实现；现有事件 `agent:end`、`gateway:startup`；`agent:end` context 含 `response/platform/user_id/chat_id/session_id/active_skill_name`，hook 可回写 context。

### 1.2 V2 目标

把 Hermes 已跑通的律师助手**契约化、可观测、可组合验证**，让律师能持续日常使用，同时为未来平台化（多后端、多前端、多行业）锁定契约边界不锁实现。

V2 不做：

- 不重建后端。
- 不重造会话存储、路由、skill 执行、MCP 管理、模型网关、反馈通道。
- 不实现自动 Skill 合成。
- 不做 Web/Tauri/QQBot 完整闭环。

V2 要做：

- 定义平台标准契约（5 个 schema）。
- 在 Hermes 侧加 hook-based 薄契约层，把内部状态归一化成契约事件。
- 异步任务契约，解决长任务 + WeCom 超时。
- 契约测试 + 可组合性合成任务进 CI。
- 反馈标准化为 `FeedbackEvent`，沿用现有卡片链路。
- 只读会话视图，从契约日志构建。
- 律师 5 工作日真实试运行验收。

### 1.3 长期方向（不在 V2 实现）

InkStatute 长期是可复用全栈 Agent 平台，支持财税、医疗、工程、政务、教育等行业。V2 通过"契约不锁实现"为这条路留口：未来换非 Hermes 后端，只需新后端实现同一契约层；未来接新行业，只需换 profile/skills/MCP/输出约束配置。平台核心不依赖法律字段、不依赖 WeCom 字段、不依赖 Hermes 内部目录结构。

## 2. 产品定位

InkStatute 是面向专业服务场景的全栈 Agent 平台。

V2 阶段产品形态：**基于 Hermes lawfirm profile 的律师助手 + 平台契约层**。

第一阶段服务对象：

- 律师、律师助理、律所管理者。
- 企业法务、合规人员。
- 有法律咨询、合同审查、案件材料整理需求的业务用户。

平台长期服务对象（V2 不交付）：

- 行业 Agent 开发者。
- 企业内部知识与流程自动化团队。
- 希望把已有 skill、MCP、模型供应商、机器人通道统一接入的平台运营者。

核心价值（V2 交付的部分）：

- 把 Hermes 已有能力契约化，使其对外可观测、可反馈、可回放、可替换。
- 用异步契约解决长任务 + 通道超时。
- 用可组合性 CI 防止平台核心偷偷绑定行业字段。
- 用 `execution_trace` / `route_mismatch` / `skill_candidate` 为未来自迭代留可审计入口。

## 3. 现有 lawfirm profile 能力盘点

### 3.1 人格与合规边界

`SOUL.md` 定义"小律"身份、语气、工作范围、保密原则、合规红线、工作底稿原则。V2 不动这部分，视为 lawfirm 行业包的内部配置。

### 3.2 Skill 体系

101 个顶层目录、约 312 个 skill。来源：`ai-for-china-legal`（symlink）、`legal-skills`（copy+同步脚本）、方法论 skill、平台 skill。V2 不建独立 Skill Registry，只通过 Hermes router 日志和 skill index 读取 skill 元数据，归一化进 `ExecutionTrace.active_skill_name`。

### 3.3 路由与编排

`scripts/router.py` 纯规则路由。V2 不建独立 Router Service，只把 router 决策归一化成 `RouteDecision` 契约事件。路由策略（强信号优先、低置信度澄清、错误反馈）保持 Hermes 现有行为不变。

### 3.4 闸门与质量控制

`ask-user-enforcement`、`cn-law-research-gate`、`legal-de-ai-polish`。V2 不动闸门逻辑，只在 `ExecutionTrace` 里记录闸门命中。

### 3.5 MCP 与外部工具

`law-database`、`wenshu`。V2 不建 MCP Connector Registry，只在 `ExecutionTrace.tool_calls` 里记录工具调用摘要。

### 3.6 模型供应商与 Agent 接入

Hermes 使用 `custom:ollama-cloud / glm-5.2`，预留 fallback。V2 不建 Model Provider Gateway，沿用 Hermes 配置。`ExecutionTrace.model_usage`（V2 尽量有）记录模型/token/耗时。

### 3.7 前端与通道

WeCom（id=155）、QQ Bot、微信。V2 主通道是 WeCom，QQ Bot/微信不作为 V2 验收通道但保持运行不破坏。V2 不建独立 Channel Adapter，Hermes gateway 继续直接收通道回调，契约层在 hook 内归一化。

### 3.8 反馈与自迭代

已跑通闭环：`response_filter` → `pending_previews.jsonl` → `template_card_dispatcher` → 模板卡片 → 用户点按钮 → `wecom_template_card_shim` 拦截 → `feedback.jsonl`。`skillopt-runner` 做 down 反馈累计 → 人工确认 → 修订。

V2 不重造这条链路，只做两件事：

1. 把 `feedback.jsonl` 标准化成 `FeedbackEvent` 契约事件。
2. 在 `FeedbackEvent` 和 `ExecutionTrace` 里预留 `route_mismatch` / `skill_candidate` 字段，为未来自迭代留可审计入口。

## 4. V2 功能范围

V2 保留 6 个模块。原 V1 的 9 个子系统中，4.1 统一会话 API / 4.2 多 Agent Runtime Adapter / 4.3 独立 Skill Registry / 4.4 独立 Router Service / 4.5 MCP Connector Registry / 4.6 Model Provider Gateway / 4.7 Document Pipeline / 4.9 Admin Console API 全部砍出 V2，推到 M2–M4（见第 11 节）。

### 4.0 关键用户旅程（验收抽样，非能力边界）

> **防路径依赖声明**：本节旅程仅作为验收抽样与回归测试样本，不作为系统能力边界。系统必须支持任意 skill / gate / MCP / 工具 / 输出约束的端到端执行，包括本节未枚举的组合。律师真实需求千变万化（如 PPT 套模板生成、合同 docx 带 Word 原生修订等长尾），系统不得因未枚举某旅程而拒绝或降级处理。

**旅程 1：合同审查（长任务 + 文档产出 + 反馈）**

律师在 WeCom 发送合同 docx + "审查这份合同" → Hermes 5s 内 ACK → 路由到 `commercial-contract-review` skill → `ask-user-enforcement` 闸门可能追问 → 律师补充 → `cn-law-research-gate` 检索 → 生成审查意见 → 若要求 track changes 则产出 `trackchanges_docx` Artifact → 通过 WeCom 推送文件 + 文本摘要 + 模板卡片 → 律师点卡片反馈 → 写入 `FeedbackEvent`。

**旅程 2：法律检索问答（短任务 + 引用）**

律师发"建设工程施工合同司法解释第几条说了什么" → 路由到法律检索 skill → 调 `law-database` MCP → 返回带引用的法条文本 → WeCom 推送文本 + 模板卡片 → 反馈。

**旅程 3：野生任务（未命中已注册 skill，自迭代预留）**

律师发"把这个法律 PPT 按另一个 PPT 模板套用生成新 PPT" → 路由零匹配或弱匹配 → Hermes 仍执行（用 LLM + 工具组合完成）→ `ExecutionTrace.matched_registered_skill=false` → 律师反馈"路由不对"或"应该有专门 skill" → `FeedbackEvent.route_mismatch=true` + `skill_candidate` 记录 → 进入待审候选队列（V2 不自动合成）。

这三条旅程覆盖短任务/长任务/野生任务、文本/文件/卡片输出、正向/负向反馈、路由命中/未命中。验收时全部跑通，但系统不得只优化这三条路径。

### 4.1 V2 最小闭环与模块边界

V2 的 6 个模块：

| 模块 | 物理位置 | 职责 | 不做的事 |
|---|---|---|---|
| `platform-contract` | `packages/platform-contract/` | 定义 5 个契约 schema + 异步任务状态机 + 错误码 | 无运行时逻辑，纯定义 |
| `contract-test-suite` | `packages/contract-test-suite/` | schema 校验 + 合成任务回放 + 可组合性测试 + CI job | 不测 Hermes 内部行为 |
| `hermes-contract-layer` | `services/hermes-contract-layer/` | Hermes hook 适配，把内部状态归一化成契约事件 | 不改 Hermes 核心，不接管 runtime |
| `conversation-read-view` | `services/conversation-read-view/` | 从契约日志构建会话/任务只读视图 | 不建独立会话存储，不直读 sessions.db 作为权威源 |
| `feedback-service` | `services/feedback-service/` | 读 `feedback.jsonl`，标准化为 `FeedbackEvent`，分类/去重/导出待审队列 | 不改反馈通道，不自动修订 skill |
| WeCom bot 日常测试闭环 | 部署在 Hermes lawfirm profile | 律师通过 WeCom 日常使用，契约层 shadow 记录 | 不改 WeCom 配置，不引入新进程 |

**唯一耦合点**：平台标准契约 `AgentTurn → AgentResult`（详见第 6 节）。WeCom 不知道 Hermes，Hermes 不知道 WeCom，二者只通过契约连接。

### 4.2 platform-contract

定义 5 个核心 schema（第 6 节）+ 异步任务状态机 + 错误码。

异步任务状态机：

```
queued → running → waiting_for_user | succeeded | failed | cancelled
```

错误码分三类：

- `contract_error`：schema 校验失败、字段缺失、枚举非法。
- `runtime_error`：Hermes 内部错误、hook 失败、模型超时。
- `channel_error`：WeCom 发送失败、回调丢失。

`platform-contract` 是纯定义包，无运行时逻辑。被 `hermes-contract-layer`、`conversation-read-view`、`feedback-service`、`contract-test-suite` 依赖。提供 JSON Schema + Python 类型 + TypeScript 类型三套绑定（V2 优先 JSON Schema + Python）。

### 4.3 contract-test-suite

测试三类：

1. **schema validation**：5 个 schema 的字段校验、枚举校验、required 校验。
2. **fixture replay**：黄金样例（真实律师任务的脱敏回放）校验 Hermes hook 输出能转成标准事件。
3. **合成任务可组合性**：用非法律合成 `AgentTurn`（财税、工程、教育）跑契约层，必须返回结构合法的 `AgentResult`，不能 schema 崩或要求法律字段。法律专用字段只能出现在 `industry_context` 扩展块。

CI 接入：PR 必跑，schema 不一致 / 字段缺失 / 关联断裂 / 法律字段泄漏到顶层 required 时 CI 失败。

### 4.4 hermes-contract-layer

物理形态：一组新 hook + mapper + 事件日志 writer，部署时 symlink 或 copy 进 `~/.hermes/profiles/lawfirm/hooks/`。不改 Hermes 核心代码。

新增 hook：

| hook | 挂载事件 | 职责 |
|---|---|---|
| `contract_result_recorder` | `agent:end`（在 `response_filter` 之后） | 把最终回复格式化为 `AgentResult`，写契约日志，不改出站文本 |
| `contract_feedback_normalizer` | 离线/定时（不是 hook） | 读 `feedback.jsonl` + `pending_previews.jsonl`，标准化为 `FeedbackEvent` |

**关键限制**：Hermes 当前只暴露 `agent:end` 和 `gateway:startup` 事件，没有 `agent:start`。V2 接受这个限制：

- `AgentTurn` 的用户原始输入字段，V2 通过 `agent:end` 时从 session 上下文反推（次优但可接受）。
- 真正的 inbound 拦截要等 Hermes 暴露更多事件（列进第 13 节遗留风险）。
- V2 的契约层是 **shadow contract**：Hermes 照常跑，平台侧形成标准事件日志，不接管流量。

**事件排序**：每个契约事件必须带 `occurred_at` + `ingested_at` + 单调序号。`contract-test-suite` 加乱序回放测试。

### 4.5 conversation-read-view

从契约日志构建只读视图，不建独立会话存储。

优先级：

1. 先读契约事件日志（V2 主路径）。
2. 不够再补 `sessions.db` adapter，明确标注为 Hermes-specific read model。
3. `conversation_id` 在契约里是稳定外部标识，映射到 Hermes 内部 session，不是新数据库 row。

对外只读接口（V2 最小集）：

- `GET /conversations/{id}` — 会话基本信息 + 最近消息。
- `GET /tasks/{id}` — 任务状态 + 执行轨迹。
- `GET /feedback?status=pending` — 待处理反馈队列。

### 4.6 feedback-service

读 `feedback.jsonl`，标准化为 `FeedbackEvent`：

- 去重：按钮重复点击、网络重试、shim 多次写入时用幂等键。
- 分类：评分、纠错、事实缺失、引用错误、路由错误、格式问题、合规问题。
- 路由错误 → 标记 `route_mismatch=true` + 生成 `skill_candidate` 记录（V2 只记录不合成）。
- 导出待处理反馈队列，供 `skillopt-runner` 人工确认流程消费。

不改反馈通道，不重造卡片链路，不自动修订高风险 skill。

### 4.7 WeCom bot 日常测试闭环

V2 主验收通道。不需要新建代码，是 4.4 + 4.6 + Hermes 现有链路的端到端串通：

```
律师 WeCom 发消息
  → Hermes gateway 接收（5s 内 ACK）
  → Hermes lawfirm session 执行（router + skill + gate + MCP）
  → response_filter hook 处理出站
  → contract_result_recorder hook 记录 AgentResult（shadow）
  → Hermes 原通道发送 WeCom 消息 + 模板卡片
  → 律师点卡片按钮
  → wecom_template_card_shim 拦截 → feedback.jsonl
  → contract_feedback_normalizer 标准化为 FeedbackEvent
```

第 4.4 节的 `contract_result_recorder` hook 部署完成后，这条链路即可跑通，律师可以开始日常测试。`conversation-read-view` 和 `feedback-service` 可以在测试期间并行补强。

## 5. V2 非目标

V2 不做：

- 不重建后端，Hermes 就是 V2 后端。
- 不建独立会话存储。
- 不建独立 Router Service / Skill Registry / MCP Registry / Model Gateway。
- 不重造反馈通道，沿用 Hermes hook/卡片/jsonl 链路。
- 不实现完整 Web UI。
- 不实现 Tauri 桌面端。
- 不实现 QQBot 完整闭环（保持运行不破坏即可）。
- 不自动迁移 Hermes profile 中的密钥、数据库、日志、账号 token、用户文档。
- 不自动修改法律结论类 skill。
- 不自动合成新 skill（只在契约层记录 `skill_candidate`）。
- 不承诺完全替代律师判断。
- 不把律师行业写死进平台核心（由可组合性 CI 验证）。
- 不改 Hermes 核心代码，契约层只通过 hook 机制接入。

## 6. 数据对象与契约 Schema

V2 用 5 个契约事件 schema 取代 V1 的 7 个数据库表设计。这些是**事件**不是**表**——它们描述平台观察到的标准事件，不规定存储实现。

法律专用字段不得出现在任何 schema 的顶层 required，只能放 `industry_context` 扩展块。

### 6.1 AgentTurn

一次用户输入被平台识别为一次 agent 轮次的标准化事件。

| 字段 | type | required | 说明 |
|---|---|---|---|
| `turn_id` | string | ✅ | 轮次唯一 ID |
| `conversation_id` | string | ✅ | 会话 ID，映射 Hermes session |
| `channel` | string | ✅ | 来源通道：`wecom` / `qqbot` / `web` / `desktop` |
| `user_id` | string | ✅ | 平台用户 ID，映射 Hermes context.user_id |
| `message_type` | enum(text, file, image, voice, button_callback) | ✅ | 消息类型 |
| `content` | string | ❌ | 文本内容（message_type=text 时） |
| `attachments` | AttachmentRef[] | ❌ | 附件引用列表 |
| `output_constraints` | OutputConstraints | ❌ | 用户或上游对输出的约束 |
| `industry_context` | object | ❌ | 行业扩展字段容器，法律专用字段只能放这里 |
| `received_at` | string(datetime) | ✅ | 平台接收时间 |
| `metadata` | object | ❌ | 平台或实现侧附加信息 |

**OutputConstraints**（为长尾需求预留，直接回应"PPT 套模板"和"docx 带 track changes"两类真实需求）：

| 字段 | type | required | 说明 |
|---|---|---|---|
| `format` | enum(docx, pptx, xlsx, pdf, markdown, text, json, card, other) | ❌ | 期望输出格式 |
| `features` | string[] | ❌ | 输出必须启用的功能，如 `track_changes` / `ppt_template` / `citations` / `comments` |
| `template_ref` | string | ❌ | 模板引用（模板文件 ID / URL / 内置模板名） |
| `citation_style` | string | ❌ | 引用风格，如 `chinese_legal` |
| `language_register` | enum(formal, colloquial) | ❌ | 语言风格 |
| `must_cite` | string[] | ❌ | 必须引用的来源 |

### 6.2 AgentResult

一次 agent 轮次的标准化结果事件。异步产生，不假设同步返回。

| 字段 | type | required | 说明 |
|---|---|---|---|
| `result_id` | string | ✅ | 结果唯一 ID |
| `turn_id` | string | ✅ | 关联 AgentTurn.turn_id |
| `status` | enum(success, partial, failed, blocked, needs_clarification) | ✅ | 完成状态 |
| `reply_type` | enum(text, markdown, file, card, status_update) | ✅ | 回复类型 |
| `content` | string | ❌ | 回复文本（或摘要） |
| `artifacts` | Artifact[] | ❌ | 产物列表 |
| `clarifying_questions` | string[] | ❌ | 需要用户澄清的问题 |
| `execution_trace` | ExecutionTrace | ❌ | 执行轨迹 |
| `feedback_target` | string | ❌ | 本结果对应的反馈目标 ID（供 FeedbackEvent 关联） |
| `route_mismatch` | boolean | ❌ | 标记本轮实际任务与路由/skill 是否不匹配 |
| `skill_candidate` | SkillCandidate | ❌ | route_mismatch=true 或存在更优 skill 时记录候选 |
| `error` | ErrorInfo | ❌ | 失败信息 |
| `metadata` | object | ❌ | 平台或实现侧附加信息 |

**Artifact**：

| 字段 | type | required | 说明 |
|---|---|---|---|
| `artifact_id` | string | ✅ | 产物唯一 ID |
| `kind` | enum(docx, pptx, trackchanges_docx, xlsx, pdf, markdown, json, other) | ✅ | 产物类型，必须能区分普通 docx 和带 Word 修订的 docx |
| `name` | string | ✅ | 面向用户展示的文件名 |
| `uri` | string | ✅ | 下载/读取位置 |
| `mime_type` | string | ❌ | MIME 类型 |
| `template_ref` | string | ❌ | 使用的模板引用 |
| `features` | string[] | ❌ | 实际启用的功能，如 `track_changes` / `ppt_template` |
| `source_refs` | string[] | ❌ | 生成依据的输入文件/知识库引用 |
| `metadata` | object | ❌ | 产物级扩展（页数、字数、slide 数等） |

**SkillCandidate**（自迭代预留）：

| 字段 | type | required | 说明 |
|---|---|---|---|
| `detected` | boolean | ✅ | 是否检测到候选 |
| `source` | enum(route_mismatch, repeated_feedback, unknown_task) | ✅ | 候选来源 |
| `proposed_name` | string | ❌ | 建议 skill 名 |
| `risk_level` | enum(low, medium, high) | ❌ | 风险等级 |
| `requires_human_review` | boolean | ❌ | 是否需要人工确认（V2 始终 true） |
| `evidence` | string[] | ❌ | 证据（关联的 feedback_id / turn_id） |

### 6.3 FeedbackEvent

从 Hermes `feedback.jsonl` 标准化生成。

| 字段 | type | required | 说明 |
|---|---|---|---|
| `feedback_id` | string | ✅ | 反馈唯一 ID |
| `turn_id` | string | ✅ | 关联 AgentTurn.turn_id |
| `result_id` | string | ❌ | 关联 AgentResult.result_id |
| `conversation_id` | string | ✅ | 会话 ID |
| `user_id` | string | ✅ | 用户 ID |
| `source` | enum(card_button, text_command, web_form, admin_annotation) | ✅ | 反馈来源 |
| `event_type` | enum(rating, correction, fact_missing, citation_error, route_mismatch, format_issue, compliance_issue, skill_candidate) | ✅ | 反馈类型 |
| `rating` | number | ❌ | 评分 |
| `action` | enum(up, down, needs_fix, route_wrong) | ❌ | 卡片按钮动作 |
| `message` | string | ❌ | 自然语言反馈 |
| `route_mismatch` | boolean | ❌ | 是否路由错误反馈 |
| `skill_candidate` | SkillCandidate | ❌ | 路由错误时附带的 skill 候选 |
| `labels` | string[] | ❌ | 聚合标签 |
| `related_skill` | string | ❌ | 关联 skill |
| `related_route_decision` | string | ❌ | 关联路由决策 ID |
| `status` | enum(pending, triaged, resolved, dismissed) | ✅ | 处理状态 |
| `created_at` | string(datetime) | ✅ | 反馈产生时间 |
| `raw_payload_ref` | string | ❌ | 原始 payload 引用（不存全文，避免泄露敏感） |

### 6.4 ExecutionTrace

记录一次任务的实际执行路径，分三档：

**V2 必须有**：

| 字段 | type | 说明 |
|---|---|---|
| `trace_id` | string | 执行链路唯一 ID |
| `turn_id` | string | 关联 AgentTurn.turn_id |
| `started_at` | string(datetime) | 开始时间（无 agent:start 时由接入层生成） |
| `ended_at` | string(datetime) | agent:end 时间 |
| `active_skill_name` | string \| null | 实际执行的 skill |
| `matched_registered_skill` | boolean | 是否命中已注册 skill（false = 野生任务） |
| `occurred_at` | string(datetime) | 事件发生时间 |
| `ingested_at` | string(datetime) | 事件入库时间 |
| `seq` | integer | 单调序号（用于乱序回放） |

**V2 尽量有**：

| 字段 | type | 说明 |
|---|---|---|
| `steps` | object[] | 关键执行步骤摘要 |
| `tool_calls` | object[] | 外部工具调用摘要 |
| `artifacts_written` | string[] | 写入的 Artifact ID 列表 |
| `route_decision` | object \| null | 路由选择依据、候选 skill、置信度 |
| `gates` | object[] | 闸门命中记录 |
| `errors` | object[] | 执行错误、降级、阻塞 |

**V2 不强制**：

| 字段 | type | 说明 |
|---|---|---|
| `model_usage` | object \| null | 模型/token/耗时/成本 |
| `debug_payload` | object \| null | 内部调试信息（非稳定结构） |

### 6.5 RouteDecision

从 Hermes router 决策归一化。

| 字段 | type | required | 说明 |
|---|---|---|---|
| `route_decision_id` | string | ✅ | 决策唯一 ID |
| `turn_id` | string | ✅ | 关联 AgentTurn.turn_id |
| `primary_skill` | string \| null | ✅ | 主 skill（null = 简单问答不走 skill） |
| `supporting_skills` | string[] | ❌ | 辅助 skill 链 |
| `gates_before` | string[] | ❌ | 前置闸门 |
| `gates_after` | string[] | ❌ | 后置闸门 |
| `required_tools` | string[] | ❌ | 所需工具 |
| `confidence` | number | ✅ | 置信度 0-1 |
| `matched_rule` | string | ❌ | 命中规则名 |
| `reason` | string | ❌ | 决策理由 |
| `mode` | enum(matched, simple_qa, skipped, zero_match) | ✅ | 路由模式（zero_match = 野生任务） |
| `route_mismatch` | boolean | ❌ | 反馈后标注是否路由错 |
| `created_at` | string(datetime) | ✅ | 决策时间 |

### 6.6 对象关系

```
AgentTurn ──┬──→ RouteDecision
            │
            └──→ ExecutionTrace ──→ AgentResult ──→ Artifact[]
                                                │
                                                └──→ FeedbackEvent[]
```

所有事件通过 `turn_id` 关联。`conversation_id` 是会话级外键。`feedback_target` 连接 `AgentResult` 和 `FeedbackEvent`。

## 7. 安全、合规与隐私

V2 不做完整安全体系（推到 M3），但必须遵守底线：

- 客户材料、案件事实、合同内容默认保密。
- 默认不把用户原文、文档、日志发送到未授权第三方。
- 密钥只通过环境变量或密钥管理系统引用，V2 沿用 Hermes 现有密钥管理，不新增明文密钥存储。
- 契约日志只引用原始 payload（`raw_payload_ref`），不存敏感全文。日志中避免记录完整身份证号、手机号、银行账号、住址。
- 管理员内部标记不能暴露给普通用户（沿用 Hermes `response_filter` 的 `ADMIN_NOTICE` 剥离机制）。
- 法律文书、检索结论、案件评估必须体现"供律师审核的工作底稿"原则。
- 高风险反馈不得自动修改法律结论、法条引用、案由判断、管辖判断、责任承担等内容。V2 始终 `skill_candidate.requires_human_review=true`。

V2 不覆盖但 M3 必须补：数据落地与跨境、at-rest/in-transit 加密、多租户隔离、RBAC、留存与销毁、审计日志完整性（WORM）、密钥轮换、工作底稿留痕。

## 8. 非功能需求

- **可观测性**：每条 AgentResult 带 `execution_trace`，能关联消息、任务、路由、工具调用、闸门、反馈。契约日志覆盖率 ≥ 95%。
- **可组合性（硬性）**：任意 skill / gate / MCP / 工具 / 输出约束的组合，只要各自 enabled 且依赖满足，必须能端到端执行，无需平台核心代码变更。由可组合性 CI 验证（见 10.3）。
- **可恢复性**：长任务失败后能查看失败阶段（`ExecutionTrace.errors` + `AgentResult.status=failed`）。
- **可扩展性**：新增行业包不需要改平台核心（由合成任务 CI 验证）。
- **可替换性**：未来换非 Hermes 后端，只需新后端实现同一契约层。V2 不验证多后端，但契约设计为此留口。
- **可审计性**：契约事件带 `occurred_at` + `ingested_at` + `seq`，可乱序回放。
- **可部署性**：V2 是 Hermes 侧 hook + 仓库内契约包，本地开发即可，不需要独立服务器。
- **零破坏**：Hermes 非 lawfirm profile 行为不受影响；Hermes lawfirm profile 现有 WeCom 模板卡反馈链路不回退。

## 9. 首个行业包：lawfirm

lawfirm 行业包 V2 就是 Hermes lawfirm profile 本身，加上契约层 hook：

- 小律人格与合规策略（`SOUL.md`）。
- 法律文书工作底稿输出规范。
- 合同审查、案件初始化、判决书分析、法院短信、OPC 常法顾问等主工作流。
- 法律检索和裁判文书检索 MCP。
- 强制问询、法律检索、去 AI 化等闸门。
- WeCom 模板卡片反馈链路。
- `skillopt-runner` 自迭代流程。

平台核心（`platform-contract` + `contract-test-suite`）不得依赖"小律"或法律专用字段。法律能力作为 Hermes lawfirm profile 挂载，契约层只归一化记录。

## 10. 验收标准

### 10.1 仓库与文档验收（基础）

- `README.md` 说明 V2 定位、仓库结构、V2 文档入口。
- `docs/requirements/V2-PRD.md` 覆盖目标、现状、功能范围、非目标、契约 schema、安全合规、验收。
- `.gitignore` 排除密钥、日志、数据库、缓存、运行状态、客户文档、构建产物。
- 仓库是 git repository。

### 10.2 契约 CI 验收

- `contract-test-suite` 在 CI 主分支保持通过。
- schema validation：5 个 schema 字段校验、枚举校验、required 校验全过。
- fixture replay：黄金样例能从 Hermes hook 输出转成标准事件。
- 关联完整性：`message → task → route → response → feedback` 链路不断裂，断裂率 ≤ 5%。
- 契约日志覆盖率 ≥ 95%：真实任务必须同时具备 `AgentTurn` 和 `AgentResult`。

### 10.3 可组合性合成任务验收

合成任务集（非法律 + 法律混合）：

- 简单法律问答（短任务）。
- 合同审查（长任务 + skill + gate + Artifact）。
- 法律检索（MCP tool trace）。
- 路由错误模拟（人工标 `route_mismatch`）。
- WeCom 反馈（模板卡片 → FeedbackEvent）。
- 长任务失败（`AsyncTask.status=failed` + read view 可读）。
- **非法律合成任务**（财税、工程、教育）：契约层必须返回结构合法的 `AgentResult`，不能 schema 崩或要求法律字段。法律字段只能出现在 `industry_context`。

通过标准：全部任务 schema 合法、关联完整、无法律字段泄漏到顶层 required。

### 10.4 律师试运行验收

- 至少 1 名律师连续 5 个工作日用 WeCom bot 做日常测试。
- 完成至少 15 个真实任务，其中至少 12 个有明确业务产出。
- 覆盖至少 3 类任务（合同审查、法律检索问答、文书起草、判决书/案例分析中任选三类）。
- 长任务（端到端 > 60s）成功率 ≥ 80%。
- 普通任务端到端成功率 ≥ 85%。
- 用户反馈采集率 ≥ 60%（至少 60% 任务有模板卡片反馈或人工标注）。
- 正向反馈占比 ≥ 60%；若低于 60%，必须有分类和修复计划。
- 负面反馈 48 小时内有响应动作记录。
- `route_mismatch` 不超过 3 条；每条必须生成结构化 `skill_candidate` 或 `routing_rule_candidate`。
- Hermes lawfirm profile 现有 WeCom 模板卡反馈链路不回退。
- Hermes 非 lawfirm profile 行为不受影响。

## 11. 后续里程碑建议

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| **V2（本文档）** | 契约层 + Hermes hook 适配 + WeCom 闭环 + 律师试运行 | 无 |
| M2 | 独立 Router Service 归一化升级 / Skill Registry 读取 / conversation-read-view 完整化 / Admin Console API 只读 / QQBot 完整闭环 | V2 验收通过 |
| M3 | 多 Agent Runtime Adapter（Codex/Claude/OpenCode）/ MCP Connector Registry / Model Provider Gateway / Web 端 / 安全合规体系（数据落地、加密、多租户、RBAC、留存销毁） | M2 |
| M4 | Document Pipeline（完整 Office 编辑、模板继承、样式迁移）/ Tauri 桌面端 / 自动 Skill 合成 | M3 |

## 12. V2 开发顺序与依赖图

### 12.1 开发顺序

| 步骤 | 模块 | 交付物 | 验收方式 | 粗估 |
|---:|---|---|---|---:|
| 1 | `platform-contract` | 5 个契约 schema + 异步状态机 + 错误码 + JSON Schema/Python 类型 + fixture | schema lint + fixture 校验通过 | 2-3 人天 |
| 2 | `contract-test-suite` | 测试框架 + 黄金样例 + 合成任务 runner + CI job | 本地 + CI 能验证 schema、样例、可组合性 | 2-3 人天 |
| 3 | `hermes-contract-layer` 最小版 | `contract_result_recorder` hook + mapper + 事件日志 writer | 跑 3-5 个真实律师任务后能产出标准事件 | 3-5 人天 |
| 4 | **WeCom 可用闭环加固** | 部署 hook + 确认模板卡片链路 + `feedback.jsonl` 标准化 | WeCom 端到端：发任务 → 回复 → 卡片 → 反馈 → FeedbackEvent | 1-2 人天 |
| 5 | `conversation-read-view` | 契约日志只读视图 + 最小 API | 按 conversation_id/task_id/trace_id 查询 | 2-4 人天 |
| 6 | `feedback-service` | feedback.jsonl 标准化 + 去重 + 分类 + skill_candidate 生成 | 真实反馈变 FeedbackEvent 并关联 message/task/skill/route | 2-3 人天 |
| 7 | 契约 CI + 可组合性验收 | 合成任务集 + 回放测试 + 覆盖率统计 + PR 阻断 | CI 契约测试必跑 + 可组合性验证 | 1-2 人天 |
| 8 | 律师 5 工作日试运行 | 试运行脚本 + 问题记录模板 + 指标统计 | 15 真实任务，达 10.4 指标 | 5 工作日观察期 |

**第 4 步完成后 WeCom bot 可用，律师可开始日常测试。** 第 5/6/7 步在测试期间并行补强。

### 12.2 依赖图

```
platform-contract (1)
  ├─→ contract-test-suite (2)
  └─→ hermes-contract-layer (3)
        ├─→ WeCom 闭环 (4) ← 律师可开始测试
        ├─→ conversation-read-view (5) ┐
        └─→ feedback-service (6)       ├─→ 律师试运行指标统计 (8)
                                        │
        contract-test-suite (2) ───────┴─→ 契约 CI 验收 (7)
```

可并行：

- 步骤 2 可在步骤 1 schema 初稿稳定后并行。
- 步骤 5 和 6 可在步骤 3 事件格式稳定后并行。
- 律师开始测试后，步骤 5/6/7 可继续并行补强。
- 合成任务 fixture 可和 `hermes-contract-layer` 同步积累。

### 12.3 关键路径

步骤 1 → 3 → 4 是关键路径（6-10 人天），完成后律师可开始测试。其余在测试期间并行完成。

## 13. 遗留风险与未决问题

V2 实现期必须解决，不阻塞 PRD 定稿但阻塞开发：

1. **hook 事件内排序**：同一任务的 message/task/route/response/feedback 可能乱序。已要求 `occurred_at` + `ingested_at` + `seq` + 乱序回放测试，但实现期要确认 Hermes hook 执行顺序机制（`contract_result_recorder` 是否稳定在 `response_filter` 之后跑）。
2. **inbound 事件缺失**：Hermes 只有 `agent:end`，没有 `agent:start`。V2 接受"在 agent:end 反推 turn 输入"的次优方案，但要确认是否能在 Hermes 找到隐藏的 inbound hook 点（需读 Hermes 源码），否则 `AgentTurn.content` 只能靠 session 上下文反推，可能不完整。
3. **`message_id` 稳定性**：Hermes、WeCom、反馈卡片之间的 message/feedback target 映射必须固定。现有 `response_filter` 已生成 `message_id` 并写回 context，但要确认这个 ID 在卡片回调时能稳定回传。
4. **长任务状态来源**：Hermes 哪些日志能稳定表达 `queued/running/waiting_for_user/failed/succeeded`？V2 异步状态机需要 Hermes 侧有对应信号。
5. **response_filter 与 template card 的关联**：要确认每条回复只生成一个可追踪 `feedback_target`，避免一条回复多张卡片导致反馈关联混乱。
6. **feedback 去重**：按钮重复点击、网络重试、shim 多次写入时需要幂等键。`feedback-service` 必须定义幂等规则。
7. **raw payload 存储**：契约日志只引用原始 payload（`raw_payload_ref`），不存敏感全文。但 raw payload 存哪、保留多久、脱敏规则要在实现期定。
8. **敏感信息脱敏**：契约日志覆盖率（≥95%）和隐私最小化之间需要明确规则——不能为了覆盖率把敏感全文写进日志。
9. **路由日志缺口**：简单问答不走 router 时，`RouteDecision.mode=simple_qa`，但要确认 Hermes 在这种情况下是否有日志可归一化，还是契约层要自己生成"skipped"记录。
10. **CI fixture 代表性**：合成任务不能只测 happy path，必须包含路由错、长任务失败、反馈重复点击、非法律任务。
11. **Skill 合成边界**：V2 只记录 `skill_candidate`，不得自动修改高风险法律 skill。实现期要确保 `feedback-service` 不会误触发 `skillopt-runner` 的自动修订。
12. **律师试运行样本偏小**：5 工作日 / 15 任务足够做 V2 闭环验收，但不代表法律质量长期指标。M2 要规划持续评测。
13. **多 hook 同事件执行顺序**：`agent:end` 上已有 `admin_notice` 和 `response_filter` 两个 hook，再加 `contract_result_recorder` 是第三个。Hermes hook 的事件内排序机制需确认，否则可能记录到未过滤的 response。退路是把记录逻辑合并进 `response_filter`（增加耦合但保证顺序）。

## 14. V1 原章节去向对照

| V1 章节 | V2 处理 |
|---|---|
| 1. 背景与目标 | 改写（1.1 现状 + 1.2 V2 目标 + 1.3 长期方向） |
| 2. 产品定位 | 改写（收敛到 V2 形态） |
| 3. 现有 lawfirm profile 能力盘点 | 保留 + 补充反馈 hook 已跑通事实 |
| 4. V1 功能范围（9 子系统） | 重写为 6 模块（4.1-4.7） |
| 4.1 统一会话 API | 降级为 `AgentTurn` 契约 schema（6.1） |
| 4.2 Agent Runtime Adapter | 砍出 V2，推 M3 |
| 4.3 Skill Registry | 降级为读取 Hermes skill index（3.2） |
| 4.4 Router Service | 降级为 `RouteDecision` 标准化（6.5） |
| 4.5 MCP Connector Registry | 降级为 `ExecutionTrace.tool_calls`（6.4） |
| 4.6 Model Provider Gateway | 砍出 V2，推 M3 |
| 4.7 Document Pipeline | 砍出 V2，推 M4 |
| 4.8 Feedback Loop | 保留为 `feedback-service`（4.6）+ `FeedbackEvent`（6.3） |
| 4.9 Admin Console API | 降级为只读 view，推 M2 |
| 5. V1 非目标 | 改写（增加不重建后端、不重造反馈通道等） |
| 6. 数据对象草案（7 表） | 重写为 5 个契约事件 schema |
| 7. 安全、合规与隐私 | 收敛为 V2 底线 + M3 待补清单 |
| 8. 非功能需求 | 增加 可组合性（硬性）+ 契约覆盖率 + 零破坏 |
| 9. 首个行业包：lawfirm | 改写为"Hermes lawfirm profile + 契约层 hook" |
| 10. 验收标准 | 重写为 10.1-10.4（文档 + 契约 CI + 可组合性 + 律师试运行） |
| 11. 后续里程碑建议 | 重排 M2-M4 |
| — | 新增 4.0 关键用户旅程（防路径依赖） |
| — | 新增 12. V2 开发顺序与依赖图 |
| — | 新增 13. 遗留风险与未决问题 |
| — | 新增 14. V1 原章节去向对照 |
