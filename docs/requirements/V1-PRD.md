# 墨律 InkStatute V1 需求规格说明书

版本：V1 草案  
日期：2026-06-27  
仓库：`inkstatute-suite`  
中文名：墨律  
英文名：InkStatute

## 1. 背景与目标

当前 Hermes `lawfirm` profile 已经形成一套可运行的律师助手系统：有独立人格提示词、法律 skill 体系、路由层、MCP 法律检索工具、企业微信与 QQBot 通道、反馈采集、SkillOpt 风格的自迭代机制，以及 gateway/session/log/hook 等运行能力。

InkStatute V1 的目标不是把这些文件简单搬进一个后端项目，而是把这套能力抽象成一个可复用的全栈 Agent 平台。律师助手是第一个行业包，后续可以复用同一平台扩展财税、医疗、工程、政务、教育等其他行业 Agent。

V1 以需求规格和架构边界为主，先定义平台应具备的能力、模块、接口边界、数据对象和验收标准。具体后端技术栈暂不锁定。

## 2. 产品定位

InkStatute 是一个面向专业服务场景的全栈 Agent 平台。

第一阶段服务对象：

- 律师、律师助理、律所管理者
- 企业法务、合规人员
- 有法律咨询、合同审查、案件材料整理需求的业务用户

平台长期服务对象：

- 行业 Agent 开发者
- 企业内部知识与流程自动化团队
- 希望把已有 skill、MCP、模型供应商、机器人通道统一接入的平台运营者

核心价值：

- 把自然语言请求稳定路由到合适的 skill、工具、模型或 Agent。
- 统一接入 Hermes Agent、Codex、Claude Code、OpenCode 和自研 Agent。
- 统一接入企业微信 Bot、QQ Bot、Web、Tauri 桌面端等前端。
- 统一管理行业 skill、MCP 工具、模型供应商、反馈和迭代。
- 以律师助手为首个行业包，沉淀可迁移的平台能力。

## 3. 现有 lawfirm profile 能力盘点

### 3.1 人格与合规边界

`SOUL.md` 定义了“小律”作为律师助理的身份、语气、工作范围、保密原则、合规红线和工作底稿原则。平台化后，这部分应抽象为“行业人格与安全策略包”。

V1 需要支持：

- 行业身份配置，例如律师助手、财税助手、工程助手。
- 服务范围配置，例如法律检索、合同审查、文书起草、文档处理。
- 禁止事项配置，例如不伪造证据、不规避执行、不泄露隐私。
- 输出规范配置，例如法律输出必须包含引用依据与检索说明。
- 管理员内部标记与用户可见内容分离。

### 3.2 Skill 体系

当前 profile 顶层存在约 97 个 `SKILL.md`，维护手册记录实际接入约 312 个 skill，来源包括：

- `ai-for-china-legal`：13 个领域插件和大量子 skill，当前通过 symlink 同步。
- `legal-skills`：端到端法律工作流 skill，当前通过 copy 与同步脚本维护。
- 法律方法论 skill：演绎、归纳、类比、目的解释、体系解释等内部推理能力。
- 平台 skill：反馈收集、SkillOpt、自迭代、企业微信模板卡片、公众号文章提取等。

平台化后，skill 不能只是本地目录。V1 需要定义 Skill Registry，管理 skill 的来源、版本、能力描述、触发条件、依赖关系、行业归属、启用状态和风险等级。

### 3.3 路由与编排

当前已存在：

- `skills/lawfirm-router/SKILL.md`
- `scripts/router.py`
- `scripts/build_skill_index.py`
- `data/skill_index.json`
- `router_logs/`
- `data/router_errors.jsonl`

路由器负责把用户自然语言映射到主 skill、supporting skills、前置闸门、后置闸门和置信度。V1 需要把该能力抽象成 Router Service。

Router Service 应支持：

- 规则路由。
- 语义路由预留。
- skill 索引构建。
- 路由决策日志。
- 低置信度时触发澄清问题。
- 路由错误反馈记录。
- 行业包可替换的路由策略。

### 3.4 闸门与质量控制

当前关键闸门包括：

- `ask-user-enforcement`：正式法律任务前强制提出 2 到 4 个澄清问题。
- `cn-law-research-gate`：生成法律文书前进行中国大陆法律检索约束。
- `legal-de-ai-polish`：法律文书初稿完成后去除 AI 化表述。

平台化后，闸门应成为可编排的 Task Gate：

- 前置闸门：事实收集、权限校验、冲突检查、检索要求。
- 执行中闸门：工具失败重试、证据缺口提示、敏感内容处理。
- 后置闸门：格式检查、引用检查、去 AI 化、交付前质量检查。

### 3.5 MCP 与外部工具

当前 `config.yaml` 中已配置：

- `law-database` MCP：法律法规检索、法条详情、按法律检索案例。
- `wenshu` MCP：裁判文书检索、详情、统计。

V1 需要 MCP Connector Registry：

- 管理 MCP server 的名称、命令、参数、环境变量、启用状态、健康状态。
- 暴露标准工具发现接口。
- 记录工具调用日志、失败原因、耗时和费用。
- 支持按行业包声明必需 MCP 和可选 MCP。

### 3.6 模型供应商与 Agent 接入

当前 Hermes profile 使用 `custom:ollama-cloud`，并预留 OpenRouter、OpenAI Codex、Nous、ZAI、Kimi、MiniMax、Bedrock 等 fallback 配置思路。

V1 后端需要同时支持两条路径：

- 直接接入外部 Agent Runtime：Hermes Agent、Codex、Claude Code、OpenCode。
- 自研 Agent 直接接入模型供应商：OpenAI、Anthropic、OpenRouter、Ollama Cloud、Bedrock、其他 OpenAI-compatible endpoint。

平台需要把模型供应商、Agent Runtime 和业务 skill 解耦。业务层只表达任务目标、上下文、工具约束和输出要求，不直接绑定某个供应商。

### 3.7 前端与通道

当前已接入：

- 企业微信 WeCom 私聊通道。
- QQBot 私聊通道。
- 企业微信模板卡片反馈 hook。

V1 需要支持以下前端形态：

- 企业微信 Bot。
- QQ Bot。
- Web 端。
- Tauri 桌面端。

后续预留：

- 飞书、钉钉、Slack、Telegram、Teams。
- HTTP Webhook。
- 内部 API 调用。

### 3.8 反馈与自迭代

当前已存在：

- `/feedback` 文本反馈。
- 企业微信模板卡片按钮反馈。
- `feedback/feedback.jsonl`。
- `feedback/pending_previews.jsonl`。
- `feedback_storage.py`。
- `skillopt-runner`。
- down 反馈累计后触发人工确认的 skill 优化流程。

V1 需要将反馈能力产品化：

- 每次 Agent 回复生成可追踪 message_id。
- 用户反馈自动关联到会话、消息、skill、路由决策、模型和工具调用。
- 反馈分为评分、纠错、事实缺失、引用错误、路由错误、格式问题、合规问题。
- 自动生成待处理反馈队列。
- 高风险 skill 只能生成修改建议，不得自动落盘。
- 低风险文案、触发词、路由规则可进入人工确认后的自动修订流程。

## 4. V1 功能范围

### 4.1 统一会话 API

后端应提供统一会话入口，屏蔽不同前端通道差异。

标准输入应包含：

- channel：`wecom`、`qqbot`、`web`、`desktop` 等。
- conversation_id。
- user_id。
- message_id。
- message_type：文本、文件、图片、语音、按钮回调。
- content。
- attachments。
- metadata。

标准输出应包含：

- reply_type：文本、markdown、文件、卡片、状态更新。
- content。
- attachments。
- trace_id。
- task_id。
- feedback_target。

### 4.2 Agent Runtime Adapter

V1 需要定义统一 Agent Runtime Adapter，至少覆盖：

- Hermes Agent adapter。
- Codex adapter。
- Claude Code adapter。
- OpenCode adapter。
- Self-hosted Agent adapter。

Adapter 需要提供一致能力：

- 创建任务。
- 追加用户输入。
- 流式或非流式读取回复。
- 传入工具和 MCP 权限。
- 传入 skill 或 workflow 指令。
- 中止任务。
- 查询任务状态。
- 收集日志与 trace。

### 4.3 Skill Registry

Skill Registry 管理行业能力包。

核心字段：

- skill_id。
- display_name。
- industry。
- source_type：local、git、symlink、copy、marketplace。
- source_uri。
- version。
- description。
- triggers。
- dependencies。
- gates_before。
- gates_after。
- risk_level。
- user_facing。
- enabled。

V1 至少需要支持 lawfirm 行业包导入现有 skill index。

### 4.4 Router Service

Router Service 根据用户请求和上下文生成执行计划。

执行计划包含：

- primary_skill。
- supporting_skills。
- selected_agent_runtime。
- required_mcp_tools。
- gates_before。
- gates_after。
- clarification_questions。
- confidence。
- reason。

路由策略要求：

- 强信号规则优先。
- 简单问答可以不进入复杂 skill。
- 低置信度必须澄清或交由人工配置策略。
- 每次路由必须记录日志。
- 用户反馈可反向标注路由错误。

### 4.5 MCP Connector Registry

V1 应支持注册、启用、禁用和健康检查 MCP server。

连接器字段：

- connector_id。
- name。
- protocol：mcp、http、local-script。
- command 或 endpoint。
- env_refs。
- tools。
- industry。
- enabled。
- health_status。
- last_checked_at。

法律行业 V1 默认连接器：

- 法律法规检索。
- 裁判文书检索。
- 文档处理。

### 4.6 Model Provider Gateway

Model Provider Gateway 负责统一模型供应商配置和调用。

V1 需要定义：

- provider。
- model。
- base_url。
- api_key_ref。
- context_length。
- cost_policy。
- fallback_policy。
- timeout_policy。
- retry_policy。
- audit_policy。

业务模块不得直接读取明文 API key。所有密钥由部署环境或密钥管理系统提供。

### 4.7 Document Pipeline

法律助手必须处理文档。

V1 需要定义文档流水线能力：

- 上传文件。
- 文件类型识别。
- 文本抽取。
- 结构化解析。
- 任务绑定。
- 生成 docx、xlsx、pptx、pdf 等交付物。
- 文件权限与过期策略。
- 敏感信息脱敏预留。

第一版只定义接口和存储边界，不要求实现完整 Office 编辑。

### 4.8 Feedback Loop

V1 需要支持：

- 每条回复关联 feedback_target。
- 机器人端按钮反馈。
- Web/桌面端评分和文字反馈。
- 管理端反馈列表。
- 路由错误与 skill 错误分离。
- 反馈导出给优化流程。
- 人工确认后才允许修改 skill、路由规则或提示词。

### 4.9 Admin Console API

V1 后端需要预留管理接口：

- 查看 gateway/channel 状态。
- 查看会话和任务。
- 查看路由决策。
- 查看 MCP 健康状态。
- 查看模型供应商状态。
- 查看反馈队列。
- 管理 skill 启用状态。
- 导出审计日志。

## 5. V1 非目标

V1 不做以下事项：

- 不实现完整 Web UI。
- 不实现完整 Tauri 桌面端。
- 不自动迁移 Hermes profile 中的密钥、数据库、日志、账号 token、用户文档。
- 不自动修改法律结论类 skill。
- 不承诺完全替代律师判断。
- 不锁定后端技术栈。
- 不把律师行业写死进平台核心。

## 6. 数据对象草案

### 6.1 Conversation

- id。
- channel。
- external_conversation_id。
- user_id。
- industry。
- active_agent_runtime。
- created_at。
- updated_at。

### 6.2 Message

- id。
- conversation_id。
- role。
- message_type。
- content。
- attachments。
- trace_id。
- created_at。

### 6.3 Task

- id。
- conversation_id。
- user_message_id。
- status。
- route_decision_id。
- agent_runtime。
- primary_skill。
- started_at。
- finished_at。
- error。

### 6.4 RouteDecision

- id。
- task_id。
- primary_skill。
- supporting_skills。
- gates_before。
- gates_after。
- required_tools。
- confidence。
- matched_rule。
- reason。
- created_at。

### 6.5 Skill

- id。
- name。
- industry。
- source_type。
- source_uri。
- version。
- description。
- triggers。
- risk_level。
- enabled。

### 6.6 Connector

- id。
- name。
- type。
- config_ref。
- tools。
- enabled。
- health_status。

### 6.7 Feedback

- id。
- message_id。
- task_id。
- conversation_id。
- user_id。
- rating。
- category。
- comment。
- related_skill。
- related_route_decision。
- status。
- created_at。

## 7. 安全、合规与隐私

V1 必须遵守：

- 客户材料、案件事实、合同内容默认视为保密信息。
- 默认不把用户原文、文档和日志发送到未授权第三方。
- 密钥只通过环境变量或密钥管理系统引用。
- 日志中避免记录完整身份证号、手机号、银行账号、住址等敏感信息。
- 管理员内部标记不能暴露给普通用户。
- 法律文书、检索结论和案件评估必须体现“供律师审核的工作底稿”原则。
- 高风险反馈不得自动修改法律结论、法条引用、案由判断、管辖判断、责任承担等内容。

## 8. 非功能需求

- 可观测性：每次请求有 trace_id，能关联消息、任务、路由、工具调用、模型调用和反馈。
- 可恢复性：任务失败后能查看失败阶段，必要时重新执行。
- 可扩展性：新增行业包不需要改平台核心。
- 可替换性：Agent Runtime、模型供应商、MCP connector 可替换。
- 可审计性：关键配置变更、skill 变更和反馈处理有记录。
- 可部署性：支持本地开发，后续支持服务器部署和私有化部署。

## 9. 首个行业包：lawfirm

lawfirm 行业包 V1 默认包含：

- 小律人格与合规策略。
- 法律文书工作底稿输出规范。
- 合同审查、案件初始化、判决书分析、法院短信、OPC 常法顾问等主工作流。
- 法律检索和裁判文书检索 MCP。
- 强制问询、法律检索、去 AI 化等闸门。
- WeCom 与 QQBot 通道适配。
- 反馈和 skill 优化流程。

平台核心不得依赖“小律”或法律专用字段。法律能力应作为行业包挂载。

## 10. 验收标准

文档和仓库骨架验收：

- `README.md` 能说明项目定位、名称、仓库结构和 V1 文档入口。
- `docs/requirements/V1-PRD.md` 覆盖目标、现状盘点、功能范围、非目标、数据对象、安全合规、验收标准。
- `.gitignore` 排除密钥、日志、数据库、缓存、运行状态、客户文档和构建产物。
- 仓库初始化为 git repository。

需求内容验收：

- 明确“墨律 InkStatute”是全栈 Agent 平台，不是单一后端服务。
- 明确律师助手是第一个行业包，不是唯一行业。
- 明确支持 Hermes Agent、Codex、Claude Code、OpenCode 和自研 Agent。
- 明确支持企业微信 Bot、QQ Bot、Web 和 Tauri 桌面端。
- 明确包括 skill、MCP、router、feedback、自迭代、模型供应商和文档处理。
- 明确不复制当前 Hermes profile 的密钥、日志、用户数据和运行数据库。

## 11. 后续里程碑建议

M1：技术选型与架构设计  
输出后端技术栈、数据库、消息队列、认证、部署方式和 monorepo 工具链方案。

M2：后端最小闭环  
实现统一会话 API、Hermes adapter、Router Service 和 lawfirm skill index 导入。

M3：机器人通道闭环  
接入企业微信和 QQBot，支持文本消息、任务执行、反馈按钮或反馈命令。

M4：Web 管理端  
实现任务、路由、反馈、connector、skill 状态查看。

M5：桌面端与文档流水线  
实现 Tauri 桌面端、文件上传、文档抽取、文档交付物管理。

