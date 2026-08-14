# V4 选型研究：DSH 引擎 + Flutter 原生 + ACP over stdio

**Researched:** 2026-08-13
**Scope:** 为 V4（Flutter 全量重构 + DSH 引擎嵌入）提供选型证据。所有 DSH 事实来自本机 `/home/sorawatcher/deepseek-harness` 源码审读，非二手资料。
**Overall confidence:** HIGH（DSH 侧契约已逐文件核实；Flutter 侧为既有选型，不重复论证）

## 0. 结论速览

1. **引擎 = DSH，不复活自研 core，不继续养 lawyer-desktop loop。** DSH 的 agent loop / 工具注册表 / 技能系统 / 批准栈 / 会话持久化 / 子代理 / 工作流 / 目标 / 计划模式 / 压缩为专职团队持续投入，自研无法竞争（军备竞赛结论）。
2. **集成缝 = DSH 的 automation-only ACP server（JSON-RPC stdio）**。这是 DSH 唯一面向外部产品进程的稳定缝；用户明确否决 WebView，因此不用 `dsh web` 的浏览器面。
3. **DSH 是 pre-release**：仓库 `AGENTS.md` 明言"首个 tagged release 前自由破坏兼容"，session 格式无兼容承诺。因此引擎必须**钉 commit、随 app 版本发布、禁自动升级**。
4. **技能管线可行**：DSH 技能格式（目录 + SKILL.md，YAML frontmatter name/description）与 `ai-for-china-legal` 现有格式同构；语料仓已有 `convert-skills.js --to kimi|opencode|standalone` 多端物化管线，加 `dsh` target 是低风险增量。
5. **ACP 面刻意最小**：只有文本 in / 已提交文本 out / 一次性批准卡。澄清与工具可见性必须移出对话协议（见 PRD DP-1/DP-2）。

## 1. 候选方案对比

| 方案 | 优 | 劣 | 结论 |
|---|---|---|---|
| A. DSH + ACP over stdio（选定） | 官方自动化缝；文本+批准卡足以撑起聊天产品；引擎能力完整；一份协议跨 DSH 版本稳定 | 无工具流、无 elicitation；DSH pre-release 需钉版 | ✅ V4 |
| B. DSH + WebView 嵌入 `dsh web` | 零协议工作量，UI 现成 | 用户明确否决（Flutter 选型意义即原生 UI）；协议面（Typert RPC+WS）更不稳定 | ❌ |
| C. 自研 Flutter loop（原 v4 方案） | 无外部依赖 | 重复 lawyer-desktop 的 2000 行 loop 教训；护栏/压缩/审批全要重做 | ❌ |
| D. 保留 V3 平台 + DSH 作为又一个后端 | 通道资产复用 | 为单用户保留 118K 行平台是负资产；Gateway 多一层进程 | ❌ 冻结 |

## 2. DSH ACP server 契约（逐条核实）

来源：`packages/acp/acp/README.md`。关键事实：

- `initialize` 只声明 baseline 提示词能力；不声明 session/editor/terminal/filesystem/MCP。
- `session/new` 要求绝对主 `cwd`；`additionalDirectories`/`mcpServers` 非空即拒。
- `session/prompt` 每会话单 in-flight；文本块拼接；空闲才算结算（`end_turn` / `cancelled`）。
- `session/update` 只发已提交 `assistant/message` 文本块；原始增量、工具活动、reasoning 不上线。
- `session/request_permission` 一次性 allow/reject（带 tool call id）。
- 断开时桥接层先拒新请求、结算挂起 prompt、再 dispose 本连接全部 agent——**零孤儿进程保证**。
- 运行形态：`node --import tsx packages/examples/acp-demo/src/bin.ts --config examples/acp-agent/cordis.yml`（源码态）；组合含 agent-spine-demo / session-persistence-jsonl / checkpoint-policy / session-query-sqlite / dsh-acp，叶层配置供给 LLM、执行器、沙箱、批准、fs、工具。`provider`/`model` 为必填配置。

对产品的推论（已定案为 PRD DP-1..DP-4）：澄清走约定文本块；工具活动不可见为接受取舍；批准卡为唯一交互通道；单 in-flight 对齐 UI。

## 3. 预设与技能（DSH 侧事实）

- Agent preset = 一个目录（preset.yml + agent.cordis.yml），挂在单个会话 scope 下；随附预设目录归部署所有、升级覆盖；用户自创预设放 `${DSH_HOME}/.agent-presets/<id>/`。
- 随附预设：standard / code（"PTC 模式"，Code Mode 呈现）/ minimal / cordis（"创造模式"，自修改工具集）。V4 自创分域预设以 standard 为底、presentation 保持 native。
- 技能：`skill-filesystem` 支持 `customSkillDirs`；发现 = 目录内 SKILL.md（frontmatter name/description）；模型经 `skill` 工具按名加载；**目录清单（name+description）渲染进模型前缀** → 全量 345 挂载不可行（token 预算，SKL-07）。
- `cordis` 预设自身的 skill 挂载写法（`customSkillDirs` 指向预设目录内 `skills/`）即 V4 分域预设挂载内容包的模板。

## 4. 语料仓事实

- `ai-for-china-legal`：345 SKILL.md、13 plugin、`package.json` 含 `convert`/`publish:all` 脚本（`--to kimi|opencode|standalone`）。
- 抽样：frontmatter 为 `name`/`description`/`argument-hint`；正文含斜杠命令（`/commercial-legal:cold-start-interview`）与"写 CLAUDE.md"类指令 → `dsh` target 只做两类语义改写（PRD §5.1）。
- 仓库含 `.qwen/skills/` 等自动产物目录，转换器必须**白名单目录**（按域），不得全树扫描（SKL-01 的实现约束）。
- `legal-skills`（51 个、37 个带 .py、CC-BY-NC）不进 V4（DEFER-01）。

## 5. Word 修订稿复用证据

- `lawfirm-profile/scripts/contract_review_trackchanges.py`：41,185 字节 Python、Word 原生 track-changes，v3.0 已将其移植进 `packages/agent-core`（Phase 101）。
- V4 结论：模型产 JSON 变更清单，app 侧用便携 Python 执行该脚本做确定性变换。理由：docx 生成是确定性变换，放模型外可审计、可测试、可版本控制；放模型内（让 agent 自己写 docx）引入不可控格式风险。金标准 fixtures 取 lawfirm-profile 既有测试。

## 6. 风险登记（研究侧）

| # | 风险 | 缓解 | 验证点 |
|---|---|---|---|
| R1 | DSH pre-release 升级破坏组合/预设 | 钉 commit；升级前真机回归；禁自动升级 | Phase 112 DSH-03；每次升级流程 |
| R2 | ACP 无 elicitation，澄清体验受损 | DP-1 约定文本 + 前置采集；RB1 分步表单兜底 | Phase 116 实测 |
| R3 | ACP 无工具流，律师看不到 agent 在干什么 | DP-2 状态文案 + 引用审计；RB2 尾随日志只读展示 | Phase 116 实测 |
| R4 | 345 技能目录 token 爆炸 | 分域预设 + 核心集预算（SKL-07） | Phase 113 门禁测试 |
| R5 | dsh target 语义改写损失技能原意 | 转换断言（SKL-03）+ HG-1 律师抽样 | Phase 114 / 120 |
| R6 | `skill` 工具按名加载依赖模型自觉 | 预设人设强制"先加载对应技能再动手"+ 核心集常驻目录 | Phase 113 / 120 |

## 7. 待验证项（进入执行前必须闭环，全部落在 Phase 112 RESEARCH）

- V1：本机真实启动 DSH ACP 组合（`examples/acp-agent/cordis.yml`），用脚本客户端完成 initialize → session/new → session/prompt → 收 committed text 全流程，记录启动时间、环境变量集、退出码。
- V2：审批链路实测——配置批准栈为"terminal 默认拒绝"后，确认 bash 工具请求经 `session/request_permission` 上抛（mock 客户端拒绝后模型收到拒绝结果）。
- V3：`skill` 工具在 ACP 会话中的行为实测——挂一个 2-skill 的 `customSkillDirs`，确认目录进入模型前缀、按名加载可用。
- V4：DSH 会话日志（JSONL）路径与结构确认（RB2 依赖）。
- V5：`dsh-acp` 生产启动形态确认（构建后 bin，非 tsx），供 `build_dsh_release.sh` 打包。
