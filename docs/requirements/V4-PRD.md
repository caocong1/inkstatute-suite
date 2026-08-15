# 墨律 InkStatute V4 需求规格说明书

版本：V4
日期：2026-08-13
仓库：`inkstatute-suite`
中文名：墨律　英文名：InkStatute
前置文档：`docs/requirements/V3-PRD.md`（v3.0 / v3.1 已交付；V4 吸收此前讨论中的「v5 内嵌 DSH」构想，Flutter 全量重构与 DSH 引擎接入合并为一个里程碑，不再单独立 v5）

---

## 0. 为什么要有 V4

### 0.1 一句话诊断

V3 验证了一条正确结论：**执行核心不该自研**。v3.0 交付的自研 Python core（turn_loop + 工具层 + 护栏移植）、v3.1 交付的竞技引擎，加在一起证明了"墨律的平台层可以换后端"，但也暴露了两件 V3 无法靠增量修复的事：

1. **执行核心是军备竞赛，不是差异化。** 自研 core 要持续追赶 DeepSeek Harness（以下简称 DSH）这类专职 harness 的工程投入——后者已具备 agent loop、工具注册表、批准栈、技能系统、子代理、工作流、目标、计划模式、压缩、会话持久化与 Web 运维面。墨律的差异化从来不在 loop，在**法律能力（396 个真实 SKILL.md）+ 法律护栏 + 律师可用性**。
2. **V3 的平台形态与真实交付对象错配。** 业主的目标用户是一个"连基础软件都装不了"的律师朋友，交付物是"双击即用"。V3 的 gateway / wecom / qq / arena / 管理台是为"律所规模 + 多通道"设计的，为一个人服务是负资产。

### 0.2 V3 前提已失效的部分

| V3 前提 | V4 现实 | 影响 |
|---|---|---|
| 自研 Python agent core 是默认后端 | DSH 的 agent loop 全面优于自研，且自带 ACP server | 自研 core 退役，DSH 成为唯一引擎 |
| 桌面端 = Tauri + SolidJS 薄壳 | 业主已选 Flutter 全量重构，且明确不用 WebView | 桌面端重写为 Flutter 原生 UI |
| 平台 = Gateway + 多通道 + 多后端 | 交付对象是单用户桌面 app，本地直连 DSH | 平台层冻结，通道层出 V4 范围 |
| 后端层 = 任意 ACP agent 的适配矩阵 | DSH 一个引擎覆盖，不需要 N 个后端 | acp-client(TS)/arena/agent-core 全部冻结 |

### 0.3 V4 的核心判断

**墨律 = 法律能力包 + 律师可用外壳，套在 DSH 引擎上。** 三层分工：

- **引擎层 → DSH（钉版本、嵌入、经 ACP over stdio 驱动）**。不再自研 loop，不再维护 agent 运行时。
- **能力层 → `ai-for-china-legal` 技能语料 + 分域预设**。语料仓仍是唯一事实源；墨律新增一条 `dsh` 物化管线；预设按执业方向切分以控制 token 成本；内容包独立版本化、独立自动更新。
- **产品层 → Flutter 原生桌面 app**。只做：会话 UI、批准卡片、法律护栏的呈现与执行、Word 原生修订导出、三层更新器、零操作安装。**不用 WebView**——Flutter 选型的意义就是原生 UI。

---

## 1. 目标与非目标

### 1.1 目标

- 交付一个 Windows 单文件安装包：安装 → 首启向导（执业方向 + 密钥）→ 直接对话。
- 引擎能力（工具调用、技能加载、审批、历史）由嵌入的 DSH 提供，墨律不重复实现。
- 396 个法律技能中的首批分域集合（core + commercial + litigation + family + employment）真正进入产品、可随内容包更新，且更新不需要律师做任何操作。
- 四条法律护栏（research-gate / citation audit / ask-user / de-AI polish）与高风险人审标记在 V4 产品中不可绕过。
- Word 原生修订 docx 导出保持 v3.0 质量（复用 41,185 字节 Python 实现，不重写）。

### 1.2 非目标（V4 不做）

- 不用 WebView、不嵌入 DSH Web GUI、不复刻 Tauri 版形态。
- 不做 Gateway / WeCom / QQ / Arena / 管理台：v3.x 平台组件冻结，不进 V4 交付物。
- 不把 396 个技能一次性全量挂载（token 预算约束，见 §6）。
- 不做多租户、多用户、远程引擎（单用户本地，DSH 子进程 per-session）。
- 不做移动端（沿用 V3 决定：移动推后）。
- 不做自研 agent loop 的任何后续投入（lawyer-desktop loop、packages/agent-core 全部冻结）。

---

## 2. 目标用户与验收场景

**目标用户：一名电脑操作能力弱的执业律师（业主的朋友），由业主远程代为安装与升级。** 原则：**用户不碰终端、不碰配置文件、不碰密钥、不碰升级**。

核心验收场景：

1. 双击安装包 → 向导选执业方向（点一张卡片）→ 打开即用，全程无命令行。
2. 输入"审查这份合同"并选择文件 → 看到流式回答、引用标记（verified/retrieved/unverified）、必要时看到"缺关键事实"澄清卡片与"需人工复核"徽记。
3. 审批：agent 要跑 shell/写文件时弹出批准卡片，用户点允许/拒绝；不存在批量批准入口。
4. 导出 Word 修订稿：一键生成带 track-changes 的 docx 到用户指定路径。
5. 技能更新：业主在语料仓发新版 → app 启动时自动拉取内容包 → 用户无感生效，失败自动回滚上一版。
6. 断网：app 可打开、可看历史；提示"联网后才能进行新任务"。

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ apps/flutter_app（Flutter 原生，Windows 桌面）                 │
│  首启向导 │ 会话 UI │ 批准卡片 │ 澄清卡片 │ 引用渲染 │ 人审徽记 │
│  三层更新器 │ 本地会话库(SQLite) │ Word 导出 │ 崩溃/健康遥测    │
├──────────────────────────┬───────────────────────────────────┤
│ packages/acp_client(Dart)│ 便携 Python（docx 确定性变换）      │
│ ACP v1 JSON-RPC stdio    │ contract_review_trackchanges.py   │
├──────────────────────────┴───────────────────────────────────┤
│ DSH 引擎（钉版本，随安装包分发）                               │
│  engines/acp.cordis.yml：agent-spine + persistence + 查询     │
│  + 批准栈(默认拒绝终端) + fs + 技能(分域) + dsh-acp(stdio)    │
│  DSH_HOME=%LOCALAPPDATA%\InkStatute\runtime\.dsh             │
│  .agent-presets/<domain>/  ← 分域预设（presets/ 物化而来）     │
│  skills/<release>/         ← 内容包（原子切换 + 回滚）         │
├──────────────────────────────────────────────────────────────┤
│ 云端（业主维护）：模型 API（DeepSeek）│ 内容包 release 源      │
└──────────────────────────────────────────────────────────────┘
```

数据布局（Windows）：

```
%LOCALAPPDATA%\InkStatute\
  app\                 # Flutter 应用（安装器管理）
  engine\<version>\    # 钉版 DSH 构建 + 便携 Node
  runtime\.dsh\        # DSH_HOME：预设、设置、会话、凭据
  skills\<release>\    # 内容包版本目录 + current 指针
  python\              # 便携 Python（docx 专用）
```

---

## 4. 引擎集成契约（ACP over stdio）

DSH 的 ACP server（`@deepseek-ai/dsh-acp`）是 automation-only 的 JSON-RPC stdio 传输，是 V4 唯一使用的集成缝。其契约事实（来自 DSH 仓库 `packages/acp/acp/README.md`，Phase 112 须逐条实测固化）：

| 方法 | 行为 |
|---|---|
| `initialize` | 协商版本；仅声明 baseline 提示词能力，**不声明** session/editor/terminal/filesystem/MCP 能力 |
| `authenticate` | no-op（服务端不声明认证方式） |
| `session/new` | 用绝对主 `cwd` 创建新 agent；`additionalDirectories` / `mcpServers` 非空即拒 |
| `session/prompt` | 拼接 text blocks 为一条用户消息；每会话同时只允许一个 in-flight 请求；等待 agent 完全空闲；正常结束报 `end_turn`，取消报 `cancelled` |
| `session/cancel` | 只取消指定 agent，结算其挂起 prompt 为 `cancelled`；未知 id 为 no-op |
| `session/update` | 只发**已提交**的 `assistant/message` 文本块（`agent_message_chunk`）；原始增量、工具活动、reasoning 一律不上线 |
| `session/request_permission` | 桥接方拥有的审批请求（带 tool call id），客户端可一次性 allow/reject |

一条连接可持有多个会话；断开时框架保证：先拒新请求、结算挂起 prompt、再并行 dispose 本连接拥有的 agent，**不产生孤儿进程**。

### 4.1 由此得出的产品决策（绑定）

- **DP-1 澄清走约定文本，不走工具。** ACP 不暴露 elicitation/ask-user，DSH 的 `ask_user_question` 工具在 ACP 会话中无交互面。V4 引擎组合**移除**该工具；澄清由两部分承担：(a) 首启向导与任务入口的结构化采集（当事人、事实、期限、材料）；(b) 预设人设要求模型在关键事实缺失时**不得起草**，输出带标记的"缺事实"块（如 `[CLARIFY: …]`），app 解析渲染为澄清卡片，用户补充后以新 prompt 继续。
- **DP-2 工具活动不可见是接受的取舍。** `session/update` 不带工具流。app 只显示已提交文本 + 状态文案（"正在检索…"由 app 侧基于 phase 提示与引用审计推断）；工具细节只留在 DSH 会话日志（本地文件），供业主排障。若未来 DSH 提供流式工具事件，再升级接入，不在 V4 造轮子。
- **DP-3 批准卡片是 ACP 唯一交互通道。** 引擎组合的批准栈配置为：terminal / execute_code 类请求默认拒绝，并作为 `session/request_permission` 上抛；app 策略 = 未知 kind 一律拒绝、已知 kind 渲染用户卡片、**无批量批准**。
- **DP-4 每会话一个 in-flight prompt。** app 会话模型对齐：一条用户消息未结算前禁用输入（或排队并显示"处理中"）。

### 4.2 引擎分发（钉版）

- `engines/dsh-pin.txt` 记录 DSH commit；`scripts/build_dsh_release.sh` 在该 commit 上构建，产出 `engine-<version>.zip`：便携 Node（Windows）+ 构建产物 + `engines/acp.cordis.yml` + 预设物化目录；清单 `engine-manifest.json`：{dsh_commit, node_version, sha256, built_at}。
- **升级纪律**：DSH 为 pre-release（首个 tagged release 前自由破坏兼容）。任何 DSH 升级必须在业主机器上以全量回归（Phase 118 的 GATE-03 真机路径 + 一轮真实法律任务）验证通过后，才随 app 版本一起发布；**禁止自动升级引擎**。
- 引擎启动：app spawn `node <engine>/dsh-acp-bin --config engines/acp.cordis.yml`，`DSH_HOME` 指向 `runtime\.dsh`，`DEEPSEEK_API_KEY` 从 OS 凭据库读取后经环境注入（不落明文到磁盘日志）。

---

## 5. 能力层：技能管线与分域预设

### 5.1 语料源与物化

- 唯一事实源：`ai-for-china-legal`（业主 Windows 路径 `C:\Users\sorawatcher\workspace\ai-for-china-legal`；345 个 SKILL.md，Claude-Code-plugin 格式，纯 prompt）。墨律**永不复制语料进本仓**，只加一条 `dsh` 物化 target。
- `scripts/convert-skills.js` 新增 `--to dsh`：frontmatter（name/description）直通；语义改写仅两类：(a) 斜杠命令调用（如 `/commercial-legal:cold-start-interview`）改为"用 skill 工具按名加载 X 技能"；(b) 写 CLAUDE.md 的指令改为写 app 数据目录下的 `practice-profile.md`（每会话技能配置事实源）。输出结构：`dist/dsh/<domain>/<skill-name>/SKILL.md`。
- `legal-skills`（51 个，37 个带 .py、CC-BY-NC 许可）**V4 不并入**，单独评估许可后再议（记 DEFER-01）。

### 5.2 内容包与自动更新

- 内容包 = `dsh-content-<release>.zip` + `content-manifest.json` {schema_version, release_version, released_at, min_engine_version, domains:{<domain>:{skills:[{name,sha256}]}}}。
- 发布源 = GitHub Release（默认）或业主自有服务器（配置化）。发布 = convert → manifest → zip → release，纯脚本。
- app 端更新（SKL-04）：启动时（+手动检查）拉 manifest → 版本比对 → 原子下载解压到 `skills\<release>\` → 切换 current 指针 → 校验 sha256，失败回滚 last-good → 离线用 last-good。**DSH 技能按名加载 + skill-filesystem 自带 watcher，内容更新无需重启 app 与引擎。**

### 5.3 分域预设与 token 预算

- 预设源：本仓 `presets/<domain>/`（preset.yml + agent.cordis.yml），安装时物化到引擎的 `~/.agent-presets/<domain>/`。随附安装目录不可改（升级覆盖），一切定制走 `presets/` 源。
- 首批分域：`legal-core`（精选核心集 ≤30 个）、`legal-commercial`、`legal-litigation`、`legal-family`、`legal-employment`。其余域按需追加。
- **token 预算（SKL-07）**：DSH 把技能目录（name+description）渲染进模型前缀。**禁止全量挂载 345 个技能**。默认会话只挂载所选分域目录；核心集目录渲染长度设预算（默认 ≤ 8,000 字符，可配置），超预算拒绝发货（回归测试）。
- 预设人设统一包含：护栏提示词段（§7）、澄清约定（DP-1）、保密提示、`requires_human_review` 输出约定。

---

## 6. 产品层（Flutter）

### 6.1 会话 UI（APP-02 / APP-05）

- 单一实现：`apps/flutter_app/lib/chat/`；墨律三主题从 lawyer-desktop 的 23 组件取设计参照（不逐字复制 SolidJS 代码）。
- 渲染：已提交文本流（agent_message_chunk）、批准卡片、澄清卡片、引用标记（verified/retrieved/unverified）、人审徽记、状态文案。
- 输出边界：只渲染已提交 assistant 文本；DSH 的 meta/system 噪声永不出现；错误映射为用户可读（引擎未启动/限流/鉴权失败/超时），原始堆栈只进本地日志。

### 6.2 会话持久化（APP-03）

- 本地 SQLite（drift）：会话、消息、引用、审批记录；按执业方向分组；支持删除与导出（隐私）。
- DSH 会话日志（JSONL）与 app 会话库并存：前者是引擎事实源与排障源，后者是产品 UI 的事实源；两者不互相改写。

### 6.3 Word 原生修订导出（APP-04）

- 模型产出：修订意见 + 结构化变更清单（JSON，schema 由 Phase 118 定义）。
- **确定性变换在 app 侧**：便携 Python（Windows embeddable）执行 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节资产复用，不重写），输入变更清单，输出 track-changes docx 到用户路径。模型永远不直接写 docx 字节。
- 金标准 fixtures：lawfirm-profile 既有测试用例。

### 6.4 首启向导与零操作原则（APP-06 / DSH-05）

- 向导三步：执业方向（预设）→ API 密钥（预填/一次性粘贴，写入 OS 凭据库）→ 模型默认确认（DeepSeek 官方路由）。之后永不要求终端/配置。
- 业主分发密钥：统一由业主管理账单；app 支持密钥轮换入口（仅业主模式，如设置页隐藏入口 + 快捷键）。

### 6.5 打包与更新（PKG-01..04）

- 安装包：单 exe（Flutter build + 引擎 zip + 便携 Python + 初始内容包 + 预设），装到 `%LOCALAPPDATA%\InkStatute`，建开始菜单/桌面快捷方式。
- 三层更新：app（安装器）/ 引擎（zip 原子替换，禁自动）/ 内容包（§5.2，唯一自动层）。manifest 启动即查；产物签名校验。
- 健康/崩溃遥测：opt-in、脱敏后上传；引擎健康探针（initialize 握手）内嵌。
- 离线：last-good 引擎+内容包可启动、可看历史；新任务需联网（对齐"在线为主、离线只读"）。

---

## 7. 法律护栏（GRD-01..06）

护栏 = 预设提示词段 + app 呈现/强制 双层，任何一层缺失都算护栏绕过（回归测试）：

| 护栏 | 提示词段 | app 侧 |
|---|---|---|
| research-gate | 结论前必须检索现行法规/司法解释，未检索不得结论 | 引用审计结果联动：无 verified 引用时结论区显示"待核实" |
| citation audit | 输出引用必须标注 verified / retrieved / unverified | 三类徽记渲染，unverified 视觉警示 |
| ask-user | 关键事实缺失不得起草，输出 `[CLARIFY: …]` 块 | 解析为澄清卡片，未澄清前任务锁定 |
| de-AI polish | 终稿过一道去 AI 腔润色段 | 终稿独立样式呈现 |
| human review | 高风险结论恒带 `[HUMAN_REVIEW: …]` | 徽记 + 无法自动消除 |
| confidentiality | 上传前脱敏提醒、DeepSeek API 传输告知 | 每次涉及客户材料的任务入口弹一次性确认 |

**红线继承自 V3（不减级）**：批准请求永不服务端默认放行；引用审计不可绕过；高风险结论永不自动定稿；敏感全文不进日志（reference-first）。

---

## 8. 里程碑划分（Phase 112–120）

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A DSH 引擎底座 | 112 | Flutter 骨架 + Dart ACP 客户端 + 子进程管理 + 引擎发布脚本，全链路 mock 冒烟通过 |
| B 法律预设与能力层 | 113-115 | 分域预设 + dsh 物化管线 + 内容包自动更新可用 |
| C 客户端与护栏 | 116-118 | 会话 UI / 批准与澄清 / 护栏双层 / Word 导出端到端可用 |
| D 交付与收敛 | 119-120 | 单 exe 安装包 + 三层更新 + 律师试运行验收 + v3.x 冻结收敛 |

**关键路径**：112 → 113 → 116 → 117 → 119 → 120。
**并行**：114/115（技能管线）与 118（docx）在 113 之后即可与 116/117 并行。

人工闸门（不得由自动化声称通过）：HG-1 法律质量（V4 基线抽样对比，Phase 120）、HG-4 修订稿质量（Phase 118）、HG-3 五工作日/15 真实任务律师试运行（Phase 120）。HG-2（WeCom）与 QQ `--live` 随通道冻结转入 DEFER。

---

## 9. 安全与隐私

- 密钥：OS 凭据库 + 启动时环境注入；绝不进仓库/日志/安装包。
- 会话数据：`runtime\.dsh` 与 app SQLite 全部本地；日志 reference-first；崩溃遥测脱敏。
- 客户材料：经 DeepSeek API 传输前有用户确认与脱敏提醒（GRD-06）。
- 引擎面：DSH 沙箱（文件策略/批准栈）按产品组合收紧；终端默认拒绝（DP-3）。
- 更新面：manifest 与产物签名校验，防篡改/防降级。

## 10. 风险

| 风险 | 应对 |
|---|---|
| DSH pre-release 破坏兼容 | 钉 commit + 升级前真机回归 + 禁自动升级引擎（DP/§4.2） |
| ACP 面过窄（无工具流/无 elicitation） | DP-1/DP-2 已定案；Phase 116 实测确认澄清与状态文案够用，不够则回退方案见 §12-RB1 |
| 技能语义改写损失 | convert 测试断言（SKL-03）+ 律师抽样（HG-1）双保险 |
| 345 技能 token 爆炸 | SKL-07 预算门禁 |
| docx 质量回退 | 复用 41KB Python + 金标准 fixtures + HG-4 |
| 白痴用户遇到未知错误 | 输出边界 + 错误映射 + opt-in 遥测 + 业主远程日志路径 |

## 11. 验收标准（Definition of Done）

1. 33 条 V4 需求全部满足（`.planning/REQUIREMENTS.md` 追踪表 100%）。
2. v4 gate 全绿：dart analyze / flutter test / 内容结构测试 / 引擎清单校验 / mock ACP E2E / docx 金标准。
3. 真实引擎路径（DeepSeek API）跑通 §2 六个验收场景。
4. HG-1、HG-4、HG-3 三项人工闸门由律师确认签字（自动化永不声称通过）。
5. v3.x 平台组件冻结并归档（LEG-01/02），本仓主线只含 V4 产品代码路径。

## 12. 明确不做（Out of Scope）

- WebView / DSH Web GUI 嵌入；Gateway / WeCom / QQ / Arena / 管理台（冻结，见 LEG-01）。
- 自研 loop 后续投入；`packages/agent-core` 与 lawyer-desktop agent 逻辑退役。
- legal-skills 语料并入（DEFER-01，许可评估后另议）。
- 全量挂载 396 技能；多用户/远程引擎；移动端；ACP v2 特性。

### 12.1 回退方案（若 Phase 116 实测发现 ACP 面不满足产品底线）

- RB1（澄清）：改用"结构化采集前置 + 分步任务流"——把澄清彻底移出对话，做成向导式分步表单；模型只处理事实已齐的步骤。
- RB2（可见性）：app 只读尾随 `runtime\.dsh` 会话日志做进度展示（不解析协议、仅状态文案）。
- RB3（最终兜底，业主明确否决 WebView 前不用）：暂不记录，保持 ACP。

---
*V4 PRD 定稿：2026-08-13。对应 GSD 里程碑 v4.0（Phase 112–120）。*
