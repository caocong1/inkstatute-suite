# V3 技术选型证据

日期：2026-08-06
用途：固化 V3 架构决策的可验证依据，避免后续 session 重复调研。
配套：`docs/requirements/V3-PRD.md`

---

## 1. 现状实测数据（本机验证，非推断）

### 1.1 inkstatute-suite 规模

```
总 Python LOC        118,556
测试文件             275
测试函数             3,173
CI gate              28（scripts/run_v2_gates.py，unittest 非 pytest）
```

逐包源码/测试行数（`find + wc -l`）：

| 目录 | src | test |
|---|---:|---:|
| packages/backends | 3,984 | 4,149 |
| packages/channel-core | 629 | 318 |
| packages/channels | 5,439 | 8,599 |
| packages/contract-test-suite | 33 | 6,284 |
| packages/mcp-registry | 511 | 740 |
| packages/model-gateway | 919 | 1,536 |
| packages/multi-agent-adapter | 955 | 962 |
| packages/operator-config | 1,386 | 1,885 |
| packages/platform-contract | 1,596 | 290 |
| packages/platform-runtime | 8,723 | 7,948 |
| packages/platform-sdk-ts | 297 | 137 |
| packages/rbac | 619 | 843 |
| packages/router-service | 950 | 1,484 |
| packages/skill-registry | 1,488 | 1,623 |
| packages/solution-loader | 867 | 322 |
| services/admin-console-api | 3,212 | 6,245 |
| services/admin-web-ui | 5,831 | 6,277 |
| services/conversation-read-view | 2,355 | 2,568 |
| services/feedback-service | 1,059 | 906 |
| services/hermes-contract-layer | 1,205 | 723 |
| services/lawyer-web-chat | 1,331 | 1,344 |
| services/qqbot-service | 1,156 | 2,236 |
| services/wecom-service | 3,271 | 2,997 |
| apps/platform_api | 1,099 | 411 |
| apps/web_chat | 0 (TS) | 375 |
| solutions/lawfirm | 314 | 190 |
| solutions/demo_non_legal | 211 | 154 |

### 1.2 关键否定性发现

```bash
# 全仓库搜索法律 skill 仓引用
$ grep -rln "ai-for-china-legal\|ai_for_china_legal" . | grep -v .git
./docs/requirements/V2-PRD.md
./.planning/milestones/v1.6-phases/37-skill-registry-read/37-RESEARCH.md
```

**零代码引用。** 平台从未接触过真实法律 skill。

```bash
# 是否有任何代码从磁盘读取 SKILL.md？
$ grep -rn "SKILL\.md" --include='*.py' . | grep -v test
solutions/lawfirm/src/.../hermes_materializer.py:97   # 写出 SKILL.md.template
solutions/demo_non_legal/src/.../hermes_materializer.py:84
packages/skill-registry/src/.../discovery.py:44        # URL 字符串，非读文件
```

唯一 skill 数据源是 `solutions/lawfirm/manifest.json` 手写的 4 条元数据。

### 1.3 冻结的 Protocol 接口

`packages/platform-runtime/src/platform_runtime/protocols.py`：

- `BackendAdapter`（9 方法）：`backend_id` / `capabilities` / `bootstrap_check` / `submit_run` / `get_run` / `stream_events` / `cancel_run` / `submit_approval` / `collect_artifacts`
- `ChannelAdapter`（6 方法）：`channel_id` / `capabilities` / `verify_and_ack` / `normalize_inbound` / `deliver` / `health`
- `SolutionLoader`（3 方法）：`validate` / `load` / `materialize_for`
- `RunRuntime`（6 方法）：`create_run` / `resume_interrupt` / `poll` / `stream` / `cancel` / `approve`

---

## 2. ACP 决定性验证

### 2.1 本机实测

```bash
$ which hermes
/home/sorawatcher/.local/bin/hermes

$ hermes --version
Hermes Agent v0.19.0 (2026.7.20) · upstream 0fa5e41c
Install directory: /home/sorawatcher/.hermes/hermes-agent
Python: 3.11.15

$ hermes --help | grep -o 'acp'
acp                                    # acp 在子命令列表中

$ hermes acp --version
0.19.0

$ hermes acp --check
Hermes ACP check OK                    # ← 决定性证据
```

本项目使用的 Hermes **就是** Nous Research 的 Hermes Agent，v0.19.0 原生支持 ACP。
文档：https://hermes-agent.nousresearch.com/docs/user-guide/features/acp

### 2.2 ACP 消歧（同名两协议）

| 名称 | 出处 | 状态（2026-08） | 定位 |
|---|---|---|---|
| **Agent Client Protocol** | Zed | **v1 稳定；v2 draft（2026-07-20，明确会变）** | 宿主↔本地 agent，JSON-RPC 2.0 / stdio |
| Agent Communication Protocol | IBM BeeAI | **2025-08-29 并入 A2A，repo 归档** | 已死 |
| A2A (Agent2Agent) | Google → Linux Foundation | v1.0 稳定 | 跨组织 agent↔agent，HTTP+JSON-RPC+SSE，AgentCard |
| MCP | Anthropic → Linux Foundation | 稳定 | agent↔工具，**正交** |
| AG-UI | CopilotKit | 新兴 | agent↔前端 UI，SSE 事件 |

来源：
- https://agentclientprotocol.com/protocol/v2/overview
- https://agentclientprotocol.com/announcements/acp-v2-draft
- https://research.ibm.com/projects/agent-communication-protocol（"ACP is now part of A2A"）
- https://a2a-protocol.org/latest/announcing-1.0/
- https://github.com/ag-ui-protocol/ag-ui

### 2.3 ACP 生态（后端层价值来源）

原生或经官方 adapter 支持 ACP 的 agent：
Hermes（`hermes acp`）、OpenAI Codex（`@agentclientprotocol/codex-acp`）、Claude Code（`@agentclientprotocol/claude-agent-acp`）、Gemini CLI（`--acp`）、GitHub Copilot CLI（`copilot --acp --stdio`）、OpenCode（`opencode acp`）、Cursor CLI（`cursor-agent acp`）、Cline、Aider（PR）、Qwen Code 等。
ACP Registry 收录 174+ agent：https://agentclientprotocol.com/get-started/registry

宿主：Zed（原生）、JetBrains（原生）、VS Code（ACP Client 扩展）、Neovim、Emacs；
非编辑器宿主：ACP UI（跨平台桌面/移动/web）、OpenACP（Telegram/Discord/Slack 桥）。

### 2.4 ACP 方法面（与产品需求的对应）

| ACP | 墨律需求 |
|---|---|
| `session/new` / `resume` / `list` / `close` / `cancel` | 多端会话续接、长任务取消 |
| `session/prompt` | 提交一轮 |
| `session/update`：`agent_message_chunk` / `agent_thought_chunk` / `tool_call_update` / `plan` / `usage_update` | 流式回复、推理、工具轮、五相进度、成本 |
| `session/request_permission` | 高风险法律动作人审 |
| `elicitation/create`（form 模式，JSON Schema，支持单选 enum / 多选 array） | `ASK-USER-PROTOCOL.md` 的 2-4 题 `allow_multiple` 澄清卡片 |
| Artifact content block（base64 + mimeType） | docx / trackchanges_docx 产物回传 |
| `_meta` + `_` 前缀自定义方法 | 法律专用扩展（industry_context） |

**编辑器味道是可选的**：`fs/read_text_file` / `fs/write_text_file` / `terminal/*` 是 client 侧**可选 capability**，v2 已移除。
来源：https://agentclientprotocol.com/rfds/v2/client-filesystem-terminal-capabilities

### 2.5 Python SDK

PyPI `agent-client-protocol` 0.11.0（2026-07-05），Python >=3.10,<3.15。
支持 client 与 agent 双侧，async 基类，`spawn_agent_process` 辅助，Pydantic 模型跟随每次 ACP 发布（`make gen-all`）。
示例含 `echo_agent.py`、`duet.py`（client+agent）、Gemini 桥。
来源：https://pypi.org/project/agent-client-protocol/ · https://github.com/agentclientprotocol/python-sdk

### 2.6 ACP 风险（已登记进 PRD §11）

1. v2 draft，破坏性变更已知：移除 `fs/*`、`terminal/*`、`session/load`、`tool_call`（改为首个 `tool_call_update` 创建）、`current_mode_update`。→ 锁 v1。
2. 稳定传输仅 stdio；Streamable HTTP / WebSocket 是 draft RFD。→ 自用同机足够。
3. 每会话一子进程（~200ms 启动，无跨会话缓存共享）。→ 自用可行；SaaS 需 daemon 模型。
4. 无多租户模型。→ 平台层已有 RBAC + TenantGuard。
5. **安全教训**：Buzz 的 ACP 桥自动以 `allow_once` 应答 Hermes 的权限请求，导致 agent 无提示执行 shell（官方文档自述 `rm -rf` 被直接执行）。→ 墨律 ACP client **必须显式拒绝** `terminal` / `execute_code` 类权限或上抛用户审批。
   来源：https://hermes-agent.nousresearch.com/docs/user-guide/features/acp （"Keep Buzz agents owner-only" 节）

---

## 3. 核心语言选型证据

评判原则（业主指定）：**不考虑开发难度和成本，追求能力强 + 前端客户端体验流畅。**

| 判据 | Python | Rust（lawyer-desktop 现状） | 结论 |
|---|---|---|---|
| Word 原生修订 docx | `lawfirm-profile/scripts/contract_review_trackchanges.py` = **41,185 字节，已建成** | `src-tauri/src/documents/docx_gen.rs` = **74 行**，仅 markdown→docx | Python 压倒性 |
| skill 语料可执行体 | legal-skills `scripts/`：**140 .py** / 31 .sh / 6 .js | 需 shell 出去调 Python | Python |
| 平台契约/可观测/RBAC/输出边界 | 118,556 行，3,173 测试，28 gate | 跨语言边界 → ExecutionTrace 与输出策略重复或降级 | Python |
| 嵌入桌面端离线 / 单二进制 | 弱 | 强 | **业主已定"在线为主，离线只读"，该优势失效** |
| 客户端体验流畅 | 由"首字节即流 + 工具轮流式"决定，非语言决定 | lawyer-desktop 当前工具轮**非流式**（先整轮拿 tool_calls，仅最终 content 流） | 平手，且现状是要修的缺陷 |

**定案：Python。**

### 3.1 lawyer-desktop 耦合度实测

```
#[tauri::command]   57 处
AppHandle           35 处
emit()              61 处（chat.rs 独占 43）
tauri::             100+ 处
```

模块分类：

| 类别 | 约 LOC | 模块 |
|---|---:|---|
| PURE（可移植逻辑） | ~4,000 | `skills/router.rs` 627、`skills/agent_classifier.rs` 691、`skills/loader.rs` 269、`llm/tool_leak.rs` 392、`llm/types.rs` 102、`citations/` 55、`law_library/` ~800 |
| IO-BOUND（接口可抽象） | ~6,000 | `llm/openai_compat.rs` 120、`mcp/` 349、`db/queries.rs` 1,276、`workspace/` ~2,000、`documents/docx_gen.rs` 74 |
| TAURI-BOUND（必重写） | ~10,000 | `commands/*` 全部、`lib.rs`、`security/*`、`sync/worker.rs` |

**需移植进 Python 的是 PURE + 部分 IO-BOUND，约 4,000 行**，其中"硬"的部分（承载产品知识）约 1,800 行。

### 3.2 lawyer-desktop 前端可复用性

- 23 个 `.tsx` 组件，21 个 CSS（`molv-tokens.css` / `molv-base.css`，`data-theme="a|b|c"` 墨律三主题）
- SolidJS 1.9.13 / TypeScript 6.0.3 / Vite 8.0.16
- **全部后端调用集中在 `src/services/api.ts`**：57 个 `invoke()` + 6 个 `listen()` 事件订阅
- Tauri 专属依赖仅 3 个 import（`api/core`、`api/app`、`api/event`）+ 插件（dialog / updater / webview 拖放）

**结论：前端清晰解耦，`invoke()` → `fetch()/EventSource` 即可 web 化**，是本项目最容易复用的资产。

### 3.3 三份重复的 chat UI（要消除的对象）

| 功能 | lawyer-desktop | lawyer-ai | inkstatute-suite |
|---|---|---|---|
| 消息列表 | `ChatPanel.tsx` | `MessageList.tsx` | 无（仅渲染器） |
| 消息渲染 | SolidMarkdown + 自定义 | `MessageItem.tsx` | `renderRunEvents()` |
| 流式协议 | Tauri 事件 `chat-stream` | WebSocket 自定义 | SSE `RunEvent` |
| 文件上传 | Tauri fs 插件 | HTTP multipart | 仅 payload_ref |
| 鉴权 | 无（本地） | JWT | RBAC + cookie |

**三个协议、三份 UI、零共享。** chat UI 约 80% 重复。

---

## 4. 法律 skill 语料实测

### 4.1 规模与结构

| | ai-for-china-legal | legal-skills |
|---|---|---|
| SKILL.md 数 | **345** | **51** |
| 组织 | 13 plugin × `skills/<name>/SKILL.md`（+ 嵌套子技能） | 扁平自包含 |
| 层级 | ~60 编排入口 + ~285 叶子 | 无嵌套 |
| 形态 | 纯 prompt/procedure | 37/51 带 `scripts/`；42 带 `references/`；26 带 `config/`；11 带 `assets/` |
| frontmatter | `name` 100%、`description` 100%、`argument-hint`（编排入口） | + `version` 96%、`license` 100%、`author` 96%、`homepage` 94% |
| 体积 | 编排入口 4-6KB，深叶 8-12KB | 3KB–40KB |
| 宿主假设占比 | ~25% | ~75% |
| license | 未声明（plugin.json 层） | MIT 30 / CC-BY-NC 13 / 完整条款 8 |

按 plugin 的 SKILL.md 数：ai-governance 25、commercial-legal 23、construction-legal 25、criminal-compliance 25、data-compliance 25、employment-legal 31、family-legal 25、ip-legal 25、law-student 25、legal-aid 25、legal-builder-hub 25、litigation-legal 32、regulatory-legal 25、shared 2。

### 4.2 横切机制（必须被平台承接）

| 机制 | 说明 | 依赖量 |
|---|---|---|
| `shared/research-gate/` | 强制前置检索（五步：清点材料→构建搜索词→按序检索→动态网页处理→输出研究底稿），既是 skill 又是 policy，标注 **MUST RUN** | 全部法律文书生成 |
| per-plugin `CLAUDE.md` 执业配置 | 审查立场（甲方/乙方）、升级矩阵（金额阈值+审批层级）、文书风格、管辖识别、交易破坏者；未配置降级"临时模式"并标记 | **~50 个 skill** |
| `shared/inkstatute-integration/ASK-USER-PROTOCOL.md` | 为墨律写的 ask_user 规范：2-4 题、`allow_multiple` 单/多选、答复以隐藏消息 `以下是补充信息…` 回注 | 平台必须实现 |
| `shared/inkstatute-integration/AGENT-UX-OPTIMIZATION.md` | 为墨律写的 UX 待办：P0 起草前反问闸门 / 完成后 `suggested_prompts[]` / 五相 phase 对齐；P1 风险预警前置、事实-证据对照表、多稿 diff 摘要 | 平台需求输入，全部 `open` |
| `shared/cross-platform/` | qwen-code / opencode / kimi-code / standalone-agent 四套格式规范 + `scripts/convert-skills.js`（**存在且可用**） | 物化器可参考 |
| `managed-agent-cookbooks/*.yaml` | 4 个定时监控 agent（案例/工商变更/期限/法规），schema 含 `schedule`(cron) / `input_prompt` / `data_sources` / `integration` / `output_template` / `escalation_rules` | V4 候选 |

注：`ai-for-china-legal/connectors/` 目录存在（law-database / wenshu / gsxt / patent / trademark / wechat-notify，含 `connector.json` + Node.js 实现与 `_lib/rpc.js`），但子代理复核时未在其扫描范围内确认，物化阶段需再次核对其是否为标准 MCP 还是自定义 RPC。

### 4.3 lawfirm-profile 的既有接法（参考实现）

- 312 skill = 297 symlink（ai-for-china-legal）+ 9 copy（legal-skills）+ ~6 自建 gate skill
- `scripts/sync_legal_skills.py`（382 行）：比对 frontmatter version，四态分类 `in-sync` / `upstream-changed` / `both-changed` / `local-missing`；自动同步 upstream-changed；`both-changed` 标记人工；`.sync_source` 标记；上游 skill 加 `legal-` 前缀
- `scripts/router.py`（498 行）：**规则优先，router 内无 LLM 调用**；12 条强信号正则（法院短信、判决书、新案件、docx 合同…）；触发短语软匹配阈值 0.4；`gate_before`=ask-user-enforcement、`gate_after`=legal-de-ai-polish；置信度 <0.6 标歧义；决策写 JSONL
- MCP：`law-database`（flk.npc.gov.cn）、`wenshu`（Playwright 兜底）

### 4.4 双仓冲突

无直接命名冲突（Repo A 层级命名，Repo B 扁平命名）。功能重叠：`contract-copilot`（B）vs `contract-review`+`contract-drafting`（A）。

---

## 5. 客户端选型证据

### 5.1 Tauri 2 移动端（2026-08 状态）

- 桌面（Win/macOS/Linux）：**生产就绪**，2.11.5（2026-07-01）
- 移动（iOS/Android）：**可上架但比桌面嫩**——WebView 渲染差异、移动插件少于 Capacitor、iOS 需 Apple Developer $99/年 + 真机签名
- 中国分发：Android 无 Play Store（APK/厂商商店）；iOS 需 App Store 中国区 + **ICP 备案（需中国公司主体 + 中国域名，2-4 周）**

来源：https://v2.tauri.app/ · https://v2.tauri.app/distribute/sign/ios/

**决策：移动原生 App 推迟到 V4。** 本期移动浏览器，风险后置且不返工。

### 5.2 SolidJS 长期可行性

- 性能与体积优势明确（7.6KB gzip vs React+ReactDOM 45KB）
- 生态约为 React 的 ~5%，但 `shadcn-solid`（57 组件）与 SolidStart v1.0 已可用
- 团队已有两处 SolidJS 投入（lawyer-desktop 23 组件、lawyer-ai 18 组件）
- Capacitor 与 Tauri 路径均支持；React Native 路径不支持

**决策：沿用 SolidJS。** 换框架的收益不足以抵消丢弃墨律三主题与 23 个已打磨组件的代价。

### 5.3 通道层协议：为何不用 AG-UI / Vercel AI SDK

- AG-UI（CopilotKit 背书，SSE 事件，~16 种事件类型）与 Vercel AI SDK data stream protocol 都是成熟方案，且事件空间与我们需要的高度重合
- **但所有客户端都是第一方**。标准协议的价值在于与外部互操作：后端层有真外部（Hermes/Codex/Claude Code），通道层没有
- 引入第二套事件词汇 + 外部依赖，换来零互操作收益 = 净负债

**决策：自有事件词汇，但与 ACP `session/update` 同构**，使平台退化为薄中继；文档保留到 AG-UI 的映射表，未来第三方 UI 接入是薄适配而非重构。

### 5.4 中国 bot 通道约束（塑造降级设计）

- **WeCom**：5 秒内必须 ACK 否则重试；无流式；无输入中状态；模板卡片支持结构化输出；AES-CBC 加解密；被动回调 + 主动推送两段式
- **QQ**：ED25519 签名（`X-Signature-Ed25519` / `X-Signature-Timestamp`）；webhook 仅限 80/443/8080/8443；回调校验 op=13 需对 `event_ts + plain_token` 签名；webhook 与 WebSocket 互斥

→ 统一事件词汇必须**从第一天就为聚合降级设计**，不能建立在"客户端一定能流式"的假设上。

---

## 6. 被否决的备选方案（记录理由，防止重复讨论）

| 备选 | 否决理由 |
|---|---|
| 为每个后端各写一个 BackendAdapter（V2 路线延续） | Hermes/Codex/Claude Code/Gemini/OpenCode 全部已支持 ACP；一个 client 换 N 个 adapter，3,875 行可退役 |
| 后端层用 A2A | A2A 是跨组织 agent↔agent（远程、AgentCard 发现），不是宿主↔本地 agent。层次不对 |
| 通道层用 AG-UI | 客户端全为第一方，零互操作收益（§5.3） |
| 自研核心用 Rust（保 lawyer-desktop 现状） | Word 原生修订能力退化（41K 字节 Python vs 74 行 Rust）；skill 语料 140 个 .py 仍需 Python；离线优势因"在线为主"失效（§3） |
| 自研核心用 TypeScript（统一前后端语言） | 同样失去 python-docx 修订能力与 skill 脚本；且要放弃 118K 行 Python 平台 |
| 把 skill 语料复制进平台仓 | 立刻产生第四份分叉；两仓有各自 license（含 CC-BY-NC）、作者与演进节奏 |
| 平台自建 skill 执行 runtime | 所有候选后端都原生加载 SKILL.md；平台该建的是索引 + 物化器 |
| 本期就做移动原生 App | Tauri 2 移动端较嫩 + ICP 备案 2-4 周；推迟不返工（§5.1） |
| 本期就做 SaaS 多租户规模化 | 业主已定"先自用，架构留口"；为想象中的规模付税 |
| 保留 `apps/platform_api` 与 `services/lawyer-web-chat` 两套 HTTP/SSE | 职责重叠（都做 SSE + 会话 + 鉴权），合并为单一 Gateway |

---

## 7. 待验证项 — 已验证（2026-08-06）

| # | 待验证 | 影响 Phase | 结论 | 关键发现 |
|---|---|---|---|---|
| V1 | `ai-for-china-legal/connectors/` 协议类型 | 97, 101 | **标准 MCP** | JSON-RPC 2.0 over stdio，`protocolVersion:"2024-11-05"`，方法 `initialize`/`notifications/initialized`/`tools/list`/`tools/call`。6 个 connector 中 2 个已实现（`law-database`、`wenshu`），4 个仅 `connector.json` 配置无 `index.js`（`gsxt`/`wechat-notify`/`trademark`/`patent`）。标准 MCP client 可直连，无需适配。 |
| V2 | `codex-acp` / `claude-agent-acp` 本机可用性 | 89 | **已验证** | `npm install -g @agentclientprotocol/codex-acp`（v1.1.13，wraps Codex App Server v0.146.1）+ `@agentclientprotocol/claude-agent-acp`（v0.65.0）均安装成功。二者无 `--check` 子命令——`initialize` 握手即功能等价物，均返回 `protocolVersion:1` 成功。Auth 延迟到 session 时（codex 需 `CODEX_API_KEY`/`OPENAI_API_KEY`；claude `authMethods:[]`）。Phase 89 健康检查应用 `initialize` 握手而非 `--check`。 |
| V3 | ACP `elicitation/create` 在 Python SDK 0.11.0 可用性 | 88, 90 | **可用但 UNSTABLE** | `agent-client-protocol` 0.11.0 中 `elicitation/create`/`elicitation/complete` 完整实现：类型可 import（`CreateFormRequestElicitationRequest` 等），SDK 路由已接通。但 schema 标注 `**UNSTABLE**`（"not part of the spec yet"），SDK 默认 `use_unstable_protocol=False` 会发警告。**必须 `use_unstable_protocol=True` 构造 client。** `_meta` fallback 可行：`SessionNotification.field_meta`（alias `_meta`）是稳定 `Dict[str,Any]` 扩展点。**注意：0.12.0 已发布，Phase 90 前需重新核对。** |
| V4 | Hermes ACP 模式下 `lawfirm` profile skill 加载 | 89, 97 | **部分验证** | `hermes acp` 无 `--profile` flag——profile 由 `HERMES_HOME` 环境变量决定。**`active_profile` sticky file 不被 ACP 子进程尊重（Hermes issue #18594）**，必须显式设 `HERMES_HOME=/path/to/profiles/lawfirm`。设好后：`.env` 加载、MCP servers（wenshu + law-database，6 tools）注册、`hermes-acp` toolset 含 `skills_list`/`skill_view`/`skill_manage`、`.skills_prompt_snapshot.json` 含 **369 个 skill**（非原记 312）。`hermes acp --check` 通过。完整 `session/prompt` 因 provider 慢未跑完。**Phase 89 的 subprocess spawner 必须显式传 `HERMES_HOME`。** |
| V5 | `contract_review_trackchanges.py` 依赖与可移植性 | 101 | **可移植** | 文件位于 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41185 字节，非 ai-for-china-legal 仓）。依赖仅 `lxml`（+ stdlib `zipfile`/`shutil`/`os`/`re`/`copy`/`datetime`/`io`）。无 subprocess/COM/Word.exe/平台特定代码。`TrackChangesBuilder(input_path)` 类接受路径参数，可 Linux 直接运行。`main()` 中硬编码路径仅为 demo 入口。第二份 17098 字节版本在 `skills/legal-contract-copilot/scripts/`。 |
| V6 | `gate-coverage` meta-test 扩展方式 | 88, 104 | **手动注册** | meta-test（`test_gate_coverage.py`）通过 `Path.glob("*/src")` 自动发现 `packages/*/src` 与 `services/*/src`，但断言每个目录必须被某个 gate 覆盖。gate 注册表硬编码在 `scripts/run_v2_gates.py` `_gates()` 函数（28 个 `Gate()` 实例）。**新增包必须：① 加 path 变量 ② 加 `Gate()` 条目 ③ 加到 `compileall` gate 参数。** 无 manifest/自动注册。回归基线 `assertGreaterEqual(len(_gates()), 19)`。Phase 104 退役包时需同步移除 gate 并调整基线。 |

### 验证发现的 3 处文档偏差（需同步修正）

1. **V4 skill 数量**：V3-SELECTION §4.3 记 "312 skills"，实际 `.skills_prompt_snapshot.json` 含 **369 个 SKILL.md**（101 个顶层目录）。`hermes profile show lawfirm` 报 "Skills: 31" 是顶层分类数。Phase 96 skill-index 应以 SKILL.md 文件数为准。
2. **V5 文件位置**：V3-SELECTION §7 原文暗示文件在 `ai-for-china-legal`，实际在 `lawfirm-profile/scripts/`。`ai-for-china-legal` 仓是纯 Node.js，无 Python 文件。
3. **V3 SDK 版本**：V3-SELECTION §2.5 记 0.11.0（2026-07-05），PyPI 最新已到 **0.12.0**。Phase 90 前需 re-verify。

### 进入 Phase 88 的硬性前置条件（已满足）

- ✅ 三后端 ACP `initialize` 均通过（Hermes / codex-acp / claude-agent-acp）
- ✅ elicitation 有明确实现路径（`use_unstable_protocol=True` + `_meta` fallback）
- ✅ skill 语料可被 ACP 后端加载（`HERMES_HOME` 显式传递）
- ✅ trackchanges 脚本可移植（纯 Python + lxml）
- ✅ gate 注册机制明确（手动，每个新包三步）
- ✅ connectors 是标准 MCP（Phase 101 无需协议适配）

---

*验证完成日期：2026-08-06。验证方式：4 个并行 subagent 实际安装/运行/读源码。ACP 生态变化较快，Phase 90 前应重新核对 §2.2 + SDK 版本。*
