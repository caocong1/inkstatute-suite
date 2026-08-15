# 墨律 InkStatute

## What This Is

墨律 InkStatute 是一个单用户 Windows 桌面法律助手：**法律能力包 + 律师可用外壳，套在 DeepSeek Harness（DSH）引擎上**。

- **引擎层**：DSH（钉版本、随安装包分发、经 automation-only ACP server over stdio 驱动）。agent loop / 工具注册表 / 批准栈 / 技能系统 / 会话持久化 / 子代理 / 工作流全部继承 DSH，墨律不再自研执行核心。
- **能力层**：`ai-for-china-legal`（345 个 SKILL.md，唯一事实源，只读物化）经 `dsh` 物化管线进入分域预设；内容包独立版本化、启动时自动更新、失败回滚。`legal-skills` 并入推迟（DEFER-01）。
- **产品层**：Tauri 2 + SolidJS 桌面 app（`apps/desktop` + `packages/ui-core`）——会话 UI、**工具调用时间线与思考过程**、批准卡片、澄清卡片、引用/人审徽记、三层更新器、零操作安装。

v3.x 平台（Gateway / WeCom / QQ / Arena / 自研 Python core）整体冻结。
**例外：`packages/ui-core` 与 `packages/platform-sdk-ts/src/events.ts` 在 v5.0 中复活为核心资产。**
`apps/flutter_app`（v4.0 产品层）冻结保留，作为 Rust 侧移植的行为参照，不删除、不再投入。

## Core Value

一名零技术操作的律师在 Windows 桌面上双击即用：Tauri + SolidJS app 经 ACP over stdio 驱动本地嵌入的 DSH 引擎，工具调用与思考过程可见，分域法律技能随内容包自动更新，四条法律护栏（research-gate / citation audit / ask-user / de-AI polish）与人审标记不可绕过，引擎半自动更新且失败自动回滚。高风险法律结论始终人审。

## Current Milestone: v5.0 Tauri Shell + DSH Three-Plane Integration

**Started:** 2026-08-15
**Status:** Roadmap defined — Phases 122-127, 34 requirements mapped, Phase 122 planned
**Predecessor:** v4.0 Flutter Native + DSH Engine（开发侧闭环 2026-08-15；产品层被推翻）

**目标：** 一名零技术操作的律师在 Windows 桌面上双击即用：Tauri 2 + SolidJS app 经 ACP over stdio 驱动本地嵌入的 DSH 引擎；工具调用与思考过程可见；分域法律预设 + 技能内容包自动更新；四条法律护栏与人审标记不可绕过；引擎半自动更新且失败自动回滚。

**为什么做这个：** v4.0 的三层分工是对的，引擎层与能力层继续沿用；被推翻的只有产品层——Flutter 原生 UI 打磨成本过高、呈现简陋，不具备交付品相。调研发现 `packages/ui-core` 已是 lawyer-desktop 像素级打磨 UI 的完整移植（主题文件逐字节相同），且组件已解耦在 `event-reducer.ts` 之后，而这套事件词汇与 DSH 原生会话事件近乎 1:1。换引擎 = 换事件来源，reducer 与组件零改动。

**架构：**

```
apps/desktop (Tauri 2 + SolidJS, Windows)
    ├── packages/ui-core（墨律三主题 + 已解耦组件 + event-reducer 421 行，零改动）
    ├── 首启向导 │ 会话 UI │ 工具时间线 │ 批准卡 │ 澄清卡 │ 引用/人审徽记
    ↕ Tauri event channel（RunEventEnvelope）
Rust 引擎主管（apps/desktop/src-tauri）
    ├── 控制面 ACP stdio：prompt / cancel(通知) / request_permission
    ├── 观测面 session.jsonl 尾随：tool / reasoning / streaming
    ├── 历史面 session-query.db 只读：会话列表 + FTS5 全文搜索
    └── 进程生命周期 │ 凭据注入 │ 事件映射 │ lockfile 装配与更新
    ↕ 一个 app 运行期一个引擎子进程
DSH 引擎（钉 npm 精确版本，node.exe + lockfile 装配树，约 42MB）
    ├── engines/acp.cordis.yml（spine + JSONL 持久化 + 查询索引 + 批准栈
    │     + 沙箱 + fs/todo 工具 + 压缩 + 分域技能 + pi-ai 多供应商）
    └── DSH_HOME=%LOCALAPPDATA%\InkStatute\runtime\.dsh
```

**关键设计决策（依据 `.planning/research/V5-SELECTION.md` 11 项本机实测）：**

- 基座 = `apps/desktop` + `packages/ui-core`，不是 lawyer-desktop（另一仓库），也不是新建项目
- 三面接入：ACP 控制面 + 会话 JSONL 观测面 + SQLite 历史面。**撤销 v4 的「工具活动不可见」取舍（DP-2）**
- 会话模型：一个 app 运行期一个引擎进程、一个对话一个 ACP 会话；跨重启用回灌续接（实测 `contextWindow: 1000000`）
- `session/cancel` 必须作为**通知**发送（无 `id`）——按请求发返回 `Method not found` 而静默失败
- 否决 SDK JSON-RPC 缝（无权限通道 / 无取消 / 无版本协商）、否决引擎常驻（破坏零孤儿保证）、否决自写 DSH 转发插件
- 引擎钉 npm 精确版本，**禁用 dist-tag**（`latest` 指向旧版）；更新 = lockfile 装配 + 版本目录 + 冒烟闸 + 指针切换
- 放弃 Word 原生修订导出，连带移除 `docx-rs` / `pdf-extract` / 便携 Python / track-changes 脚本
- 修复 v4 遗留缺陷：`${DSH_HOME}` 不展开（会话历史落在引擎目录）、Google Fonts CDN 中国大陆不可达、依赖系统 Node

## Previous: v4.0 Flutter Native + DSH Engine — 产品层被 v5.0 推翻

**开发侧闭环:** 2026-08-15
**Status:** Phases 112-121 完成。**引擎层与能力层成果继续有效并被 v5.0 沿用**（DSH 接入契约、分域预设、技能 dsh 物化管线、内容包更新机制）。产品层 `apps/flutter_app` 冻结保留作 Rust 侧移植参照，不删除、不投入。APP-04（Word 原生修订导出）业主明确放弃。
**Archived:** `.planning/milestones/v4.0-REQUIREMENTS.md`

## Previous: v3.1 Legal AI Arena — SHIPPED

**Shipped:** 2026-08-09
**Status:** COMPLETE — Phases 105-111（Arena 契约、ACP fs handler、竞技引擎四模式、竞技服务、桌面竞技 UI、Closure）
**Archived:** v3.1 文档随 `/gsd-complete-milestone` 归档（归档前 git 历史保留）

## Previous: v3.0 Unified Legal Core — SHIPPED

**Shipped:** 2026-08-08
**Status:** COMPLETE — 17 phases (88-104), 69 plans, 192 tasks, 937 tests, 34 gates green
**Source:** [V3-PRD.md](../docs/requirements/V3-PRD.md) | **Evidence:** [V3-SELECTION.md](research/V3-SELECTION.md)

**交付内容：** 13-category 统一事件词汇（ACP 同构）、Python ACP client、统一多租户 HTTP+SSE Gateway、@inkstatute/ui-core（23 组件 3 主题）、响应式 Web + Tauri 桌面 + WeCom/QQ Gateway 消费者、396 真实法律 skill 索引物化、自研 Python async streaming agent core（context budget + tool layer + Word 原生修订 docx + 4 法律护栏移植）、双入口（in-process + `inkstatute-agent acp` CLI）、存量收敛（~10,483 行退役）。

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) | [v3.0-phases](milestones/v3.0-phases/)

## Previous: v1.11 Product Console — SHIPPED

**Shipped:** 2026-07-15
**Status:** COMPLETE — 9 phases shipped (79–87), 27/27 requirements satisfied, 9/9 phases verified, 8/8 integration checks passed. Audit: tech_debt (no blockers; documentation hygiene + carried human gates). Product-grade operations control plane: runnable entry points, process orchestration, reports/logs/audit/health dashboards, session auth, product polish, and end-to-end smoke verification with gate-honesty stamping.

**Archive:** [v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md) | [v1.11-REQUIREMENTS.md](milestones/v1.11-REQUIREMENTS.md) | [v1.11-MILESTONE-AUDIT.md](milestones/v1.11-MILESTONE-AUDIT.md)

**Carried human gates (not closed):** Phase 5 live WeCom UAT; Phase 8 five-workday lawyer trial; operator `--live` QQ OpenAPI acceptance.

## Previous: v1.10 Operator Config Console — SHIPPED

**Shipped:** 2026-07-12
**Status:** COMPLETE — 7 phases shipped (73–78.1), 20/20 requirements satisfied, audit passed. InkStatute-owned operator config for channels, providers/catalog, and vision routing without editing Hermes.

**Archive:** [v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md) | [v1.10-REQUIREMENTS.md](milestones/v1.10-REQUIREMENTS.md) | [v1.10-MILESTONE-AUDIT.md](milestones/v1.10-MILESTONE-AUDIT.md)

## Previous: v1.9 QQBot Host Composition — SHIPPED

**Shipped:** 2026-07-10
**Status:** COMPLETE — 5/5 phases shipped (68-72), 11/11 requirements satisfied, audit passed. Closed v1.8 accepted host-composition gaps: thin `services/qqbot-service/` webhook host, dual-knob runtime registration, Protocol-path smoke dry-run, controlled live HUMAN GATE docs/honesty.

**Archive:** [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md)

## Previous: v1.8 QQBot Channel Production — SHIPPED

**Shipped:** 2026-07-09
**Status:** COMPLETE with accepted gaps closed by v1.9 — 10/10 phases shipped (58-67), 28/28 package-level requirements satisfied, 321 qqbot unit tests green. Host composition / Protocol-path smoke / controlled live path delivered in v1.9; live QQ OpenAPI acceptance remains a human gate.

**Archive:** [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)

## Previous: v1.6 M2 Multi-Backend & Platform Extensions — SHIPPED

**Shipped:** 2026-07-04
**Status:** COMPLETE — 9/9 phases shipped (36-44), 22/22 requirements satisfied, 19/19 V2 gates green (969 tests).

The v1.6 milestone extended the platform beyond Hermes-only by proving agent-backend-neutral contracts (Codex + provider_model prototypes), normalizing routing as an independent service, exposing skill metadata and operational read views, completing conversation-read-view, and adding a second channel (QQBot) to prove ChannelAdapter portability — while keeping all existing V2 gates green and V2 human-gate evidence stable.

**Key deliverables shipped:**
- Codex adapter prototype (`packages/backends/codex`) — proves BackendAdapter contract portability via `codex exec --json` subprocess.
- Provider model adapter prototype (`packages/backends/provider_model`) — direct LLM provider mode via `AsyncOpenAI` lazy SDK import.
- Independent Router Service (`packages/router-service`) — standalone router library with RULE and SKILL modes, injectable into hermes-contract-layer mapper.
- Skill Registry read (`packages/skill-registry`) — read-only registry exposing Hermes skill metadata as `NeutralSkillDescriptor` records with list/get/search + `/.well-known/agent-skills/index.json`.
- Conversation Read-View completion (`services/conversation-read-view`) — cursor-based pagination, time-range/dimension filters, trace reconstruction by `trace_id`, CSV/JSON export, read-time privacy scrubbing.
- Admin Console API (`services/admin-console-api`) — read-only admin API with static token auth, sessions/tasks/feedback/gates/health views, field allowlist excluding secrets.
- QQBot channel loop (`packages/channels/qqbot` + `packages/channel-core`) — channel-generic logic extracted into shared package, QQBot ChannelAdapter implements 6-method Protocol, fixture-driven loop proof.
- Gate coverage meta-test (`packages/contract-test-suite/tests/test_gate_coverage.py`) — enforces every `packages/*/src` and `services/*/src` directory is covered by a gate. 19 gates, 969 tests.

**Safety preserved:**
- Contract freeze maintained (`packages/platform-contract/` unchanged during M2).
- All 6 M2 feature flags default to `False`.
- BackendAdapter Protocol (9 methods) and ChannelAdapter Protocol (6 methods) frozen.
- Output boundary enforced for all new backends.
- V2 human gate evidence stable.

**Archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

</details>

## Requirements

### Validated

- ✓ ADM-01: Admin/operator GET/PUT `/config/*`; lawyer/viewer denied mutate — Phase 74
- ✓ ADM-03: Operational admin views stay read-only; config writes only on explicit `/config/*` — Phase 74
- ✓ v1.9 HOST-*: Thin QQBot production webhook host composing verify_and_ack → ingress/session/feedback → deliver (default-OFF) — v1.9 (Phases 68-70)
- ✓ v1.9 REG-*: Runtime registration of QQBotChannelAdapter into DefaultRunRuntime.channels / flag→config dual-knob mapping — v1.9 (Phase 69)
- ✓ v1.9 SMOKE-*: Smoke dry-run exercises full adapter/session Protocol path via host helpers — v1.9 (Phase 71)
- ✓ v1.9 LIVE-*: Controlled QQ live path with fail-closed env + runbook; acceptance remains HUMAN GATE — v1.9 (Phase 72)
- ✓ v1.9 SAFE-*: ADAPTER-04 host isolation + secret refs at process edge — v1.9 (Phase 68)
- Existing Hermes `lawfirm` profile is already running as the lawyer assistant backend.
- Hermes source inspection confirms `agent:end` response filtering is insufficient as a complete user-output boundary because gateway/update/restart/delivery/status paths can send directly through platform adapters.
- Existing Hermes WeCom, QQ Bot, and WeChat gateway connections exist as runtime evidence and migration inputs, with WeCom as the V2 acceptance channel. Target V2 WeCom ingress/egress is owned by InkStatute, not Hermes gateway.
- Existing Hermes feedback path is already present: `response_filter` preview, template card dispatch, callback shim, and `feedback.jsonl`.
- Existing Hermes router, skills, gates, MCP tools, model gateway, and session storage remain the operational baseline.
- Phase 3 Hermes integration spike is complete: hook ordering is source-confirmed, AgentTurn strategy is documented, identifier/state/privacy/safety rules are defined, and non-happy-path fixtures validate through the contract-test-suite.
- Phase 4 Hermes shadow event layer is complete: repo-owned hook artifact, mapper, JSONL writer, and event-stream replay fixtures validate without live Hermes mutation.
- v1.2 conversational context and memory foundation is complete: ordinary WeCom continuation/start flows reach runtime run creation, pending clarification resumes remain interrupt-based, bounded context/memory metadata is reference-first, and external memory providers remain optional sanitized-spike candidates.
- [WECOM-01] Build InkStatute-owned WeCom service for receive/send, ACK, message normalization, text/file/card delivery, feedback callbacks, idempotency, retry, and output policy. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [ADAPTER-01] Define and implement the agent backend adapter contract and runtime selector, with Hermes as the first supported mode and Codex/provider-model modes preserved as contract-compatible future modes. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [HERMES-01] Build a reproducible Hermes agent adapter bootstrap path from a sanitized lawfirm profile bundle, version/capability matrix, external secrets/env, and health checks. — Phase 55 (v1.0); audited Phase 33; verified Phase 34.
- [OUTPUT-01] Add an assistant output boundary so ordinary WeCom users see only InkStatute lawyer-assistant output, not Hermes gateway/update/command/meta notices. — Phase 55 (v1.0); audited Phase 33; verified Phase 34.
- [LOOP-01] Preserve and validate the WeCom task-to-agent-to-reply-to-card-to-feedback loop through InkStatute WeCom service. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [FEEDBACK-01] Normalize Hermes feedback into FeedbackEvent records with dedupe, classification, and human-reviewed skill candidates. — Phase 6 (v1.0); audited Phase 33; verified Phase 34.
- [READVIEW-01] Build read-only conversation/task/feedback APIs from contract logs. — Phase 7 (v1.0); audited Phase 33; verified Phase 34.
- [OBSERVE-01] Enforce observability, replay, privacy, and legal safety baselines. — Phase 7 (v1.0); audited Phase 33; verified Phase 34.
- [COMPOSE-01] Enforce composability and industry-neutral contract behavior in CI. — Phase 8 (v1.0); audited Phase 33; verified Phase 34.
- ✓ M3 adapter productization (streaming, artifacts, session memory, multi-provider) — v1.7 (Phases 46-49)
- ✓ M3 platform extensions (MCP registry, model gateway, multi-agent, skill write, hybrid routing) — v1.7 (Phases 50-55)
- ✓ M3 operator & UX layer (Admin Web UI, Lawyer Web Chat) — v1.7 (Phase 57)
- ✓ M3 security & compliance (RBAC, multi-tenant isolation) — v1.7 (Phases 51, 56, 57.1)
- ✓ M3 safety (9 feature flags default False, frozen Protocols preserved, 24 V2 gates green) — v1.7 (Phase 45)
- ✓ CORE-05: 移植 router.rs Chinese legal prompt assembly — Phase 102
- ✓ CORE-06: 移植 tool_leak.rs 工具调用泄漏检测与解析 — Phase 102
- ✓ CORE-07: 移植 citation 审计（提取 + 验证） — Phase 102
- ✓ CORE-08: 四条法律护栏代码级强制（research-gate / ask-user / citation audit / de-AI polish） — Phase 102
- ✓ SAFE-01: skill_candidate.requires_human_review 恒为 true，高风险法律结论人审 — Phase 102
- ✓ SAFE-04: research-gate 与 citation 审计不可绕过 — Phase 102
- ✓ CORE-10: 双入口（in-process BackendAdapter + inkstatute-agent acp） — Phase 103
- ✓ CONV-01: 退役 packages/backends/hermes 与 packages/backends/codex — Phase 104
- ✓ CONV-02: 退役 packages/channels/web_sse — Phase 104
- ✓ CONV-03: 归并 services/lawyer-web-chat 进 Gateway；退役 services/hermes-contract-layer — Phase 104
- ✓ CONV-04: 冻结 packages/multi-agent-adapter (experimental) — Phase 104
- ✓ CONV-05: gate 体系更新（34 gates, gate-coverage meta-test 全覆盖） — Phase 104
- ✓ SAFE-06: 可组合性保持 + WeCom/QQ 回归测试全绿 — Phase 104
- ✓ SKL-11: 分域预设挂载（materialize_presets + INKSTATUTE_SKILL_DIRS 运行时注入） — Phase 126
- ✓ SKL-12: 内容包自动更新（semver 预发布兼容 + sha256 + 原子切换 + 回滚） — Phase 126
- ✓ SKL-13: token 预算门禁（目录渲染 ≤ 8,000 字符，超预算拒绝发货） — Phase 126
- ✓ GRD-11: research-gate 可核验化（工具时间线 research_performed + 无 verified 引用时「待核实」标记） — Phase 126
- ✓ GRD-12: citation audit（verified/retrieved/unverified 三级徽记 + citation.recorded 事件） — Phase 126
- ✓ GRD-13: ask-user（[CLARIFY:] 块状解析 + ClarificationCard + 未澄清任务锁定） — Phase 126
- ✓ GRD-14: de-AI polish + human review（[HUMAN_REVIEW:] 恒人审 + 徽记不可消除） — Phase 126
- ✓ GRD-15: 批准卡片（allow-once/reject-once，无批量批准路径，60s 超时自动拒绝） — Phase 126
- ✓ GRD-16: 输出边界 + 保密（只渲染已提交文本 + 首次上传一次性保密确认） — Phase 126

### Active

**v4.0 Flutter Native + DSH Engine — 33 requirements（5 DSH + 7 SKL + 6 APP + 6 GRD + 4 PKG + 2 LEG + 3 GATE），全部映射到 Phases 112-120（100%）。权威列表见 [REQUIREMENTS.md](REQUIREMENTS.md)，规格真源 [V4-PRD.md](../docs/requirements/V4-PRD.md)。**

**Human gates（不得由自动化声称通过）：**

- [ ] HG-1 法律质量：V4 基线（DSH + 分域预设）须由律师抽样确认不低于 lawyer-desktop/Hermes 基线 — Phase 120
- [ ] HG-4 修订稿质量：Word 原生修订 docx 须由律师确认可用于对外谈判 — Phase 118
- [ ] HG-3 五工作日 / 15 真实任务律师试运行验收 — Phase 120
- [ ] HG-2 / Phase 5 live WeCom UAT operator confirmation — DEFERRED（通道随 v3.x 平台冻结）
- [ ] Operator `--live` QQ OpenAPI acceptance evidence — DEFERRED（通道随 v3.x 平台冻结）

### Historical (superseded by v4.0)

v3.0（61 条）与 v3.1（45 条）需求已随各自里程碑交付；v3.0 归档见 [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md)。以下为 v1.x-v2 遗留条目，仅存档：

- [x] Define the V2 platform contract package with five event schemas, async task states, error categories, JSON Schema, Python bindings, and fixtures.
- [x] Model AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision as platform events with traceable relationships.
- [x] Build a contract test suite before production Hermes hook work.
- [x] Resolve Hermes integration risks before production hook implementation.
- [x] Add a thin hook-based Hermes shadow contract layer that does not alter legal/business outbound behavior.
- [x] M2-01: Codex adapter prototype proving agent-backend-neutral contract beyond Hermes. — Phase 39 (v1.6)
- [x] M2-02: Direct provider_model adapter prototype proving contract-compatible direct LLM provider mode. — Phase 40 (v1.6)
- [x] M2-03: Independent Router Service normalizing routing decisions as a standalone service. — Phase 38 (v1.6)
- [x] M2-04: Skill Registry read exposing Hermes skill metadata as a read-only registry. — Phase 37 (v1.6)
- [x] M2-05: conversation-read-view completion with full PRD-spec read-only views, pagination, and filtering. — Phase 41 (v1.6)
- [x] M2-06: Admin Console API (read-only) exposing operational views for operators. — Phase 42 (v1.6)
- [x] M2-07: QQBot complete loop as second channel proving ChannelAdapter portability. — Phase 43 (v1.6)
- [x] M2-08: Gate coverage meta-test enforcing every packages/*/src and services/*/src directory is covered by a V2 gate. — Phase 44 (v1.6)

### Out of Scope (v3.0)

- **移动原生 App 出包上架**（Android / iOS）— 推 V4。Tauri 2 移动端较嫩，中国 Android 无 Play Store、iOS 需 App Store 中国区 + ICP 备案（2-4 周）。本期移动浏览器顶着，共享 UI 按可打包成 App 的方式设计但不出包。
- **SaaS 多租户规模化**（agent 进程池 / 远程 ACP 传输 / 水平扩容）— 契约留 `backend_process_mode` 口，实现不做。业主已定"先自用"。
- **桌面端完全离线的本地 agent runtime** — 业主已定"在线为主，离线只读"。
- **重建 Hermes core** — Hermes 是 ACP 后端之一。
- **复制 skill 语料进平台仓** — 只读 vendoring 引用。两个 skill 仓有各自 license（含 CC-BY-NC）、作者与演进节奏，复制立刻产生第四份分叉。
- **平台自建 skill 执行 runtime** — 所有候选后端都原生加载 SKILL.md；平台建索引 + 物化器。
- **通道层对齐 AG-UI / Vercel AI SDK** — 所有客户端均为第一方，零互操作收益。保留映射文档。
- **后端层对齐 A2A** — A2A 是跨组织 agent↔agent，层次不对。
- **ACP v2 特性** — v2 为 draft 且已知破坏性变更；锁 v1。
- **新通道**（WeChat 小程序 / WhatsApp / Slack）。
- **向量检索 / embedding RAG** — 沿用 SQLite FTS5。
- **自动合成或自动修改高风险法律结论 skill** — 继承 V2 约束，只记 `skill_candidate`，人审。
- **契约日志默认存客户法律原文** — reference-first。
- Retired product V1 and V2 as active requirement sources — V3 PRD replaces them（V2-PRD 保留为历史文档）。

## Context

- **Source of truth: `docs/requirements/V4-PRD.md`.** 选型证据：`.planning/research/V4-SELECTION.md`。V1/V2/V3-PRD 保留为历史文档，不再是活跃需求源。
- **相关仓库**（本仓之外，皆为 workspace 同级目录）：
  - `ai-for-china-legal` — 345 个 SKILL.md，Claude-Code-plugin 格式，纯 prompt；V4 技能语料唯一事实源（业主 Windows 路径 `C:\Users\sorawatcher\workspace\ai-for-china-legal`）；`convert-skills.js` 加 `dsh` target
  - `deepseek-harness` — V4 引擎源（`/home/sorawatcher/deepseek-harness`）；钉 commit 构建；ACP server 契约见 `packages/acp/acp/README.md`
  - `legal-skills` — 51 个 SKILL.md（37 带 .py，CC-BY-NC）；DEFER-01 许可评估后再议
  - `lawfirm-profile` — `scripts/contract_review_trackchanges.py`（41,185 字节 Word 原生修订）是 V4 docx 导出的复用资产
  - `lawyer-desktop` — Tauri 2.11 + SolidJS；V4 只取设计参照（23 组件 + 墨律三主题），agent 逻辑（router/classifier/tool_leak）不迁入、退役
  - `lawyer-ai` — OpenCode 原型，已搁置，不迁入
- **Target runtime**: Flutter/Dart 为产品层；DSH（Node）为引擎层；便携 Python 只服务 docx 确定性变换；JSON 为变更清单契约格式。
- **Workflow**: 高自主 GSD，人工闸门保留给法律质量（HG-1）、修订稿质量（HG-4）与律师试运行（HG-3）。
- **开发顺序具约束力**：DSH 引擎底座（112）→ 法律预设与能力层（113-115）→ 客户端与护栏（116-118）→ 交付与收敛（119-120）。Phase 112 RESEARCH 必须先闭环 V4-SELECTION §7 的 V1-V5，任一证伪触发 PRD §12.1 回退评审。

- **Architecture**: 单用户本地架构——Flutter app 直接 ACP 驱动本地 DSH 子进程；无 Gateway、无 WebView、无远程引擎。三层更新：app（安装器）/ 引擎（禁自动）/ 内容包（唯一自动层）。
- **Engine seam**: DSH 的 automation-only ACP server（JSON-RPC stdio）——文本 prompt 进、已提交文本出、一次性批准卡。澄清与工具可见性按 DP-1/DP-2 产品化吸收。
- **Skill layer**: 语料仓只读物化（`dsh` target）+ 分域预设挂载 + 内容包原子更新；禁全量挂载；token 预算门禁。
- **Guardrails**: 双层（预设提示词段 + app 呈现/强制）；批准栈 terminal 默认拒绝；高风险结论恒人审。
- **Privacy**: 契约日志 reference-first（`raw_payload_ref`），不存敏感全文。
- **User-facing output**: 输出边界在 ACP 事件桥与 Gateway 双重执行；后端 meta/gateway/system/update/command 噪声不得到达普通律师用户。
- **Permission safety**: ACP `session/request_permission` 服务端不得默认 allow；`terminal`/`execute_code` 类必须显式拒绝或上抛审批（参考 Buzz 的 auto-allow 事故）。
- **Legal safety**: 高风险法律结论人审；research-gate 与 citation 审计不可绕过；不自动合成或修改法律结论类 skill。
- **Composability**: 平台 schema 与 CI 保持行业中立，法律专用字段只进 `industry_context`；由 `solutions/demo_non_legal` 验证。

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **V4 PRD 取代 V3 成为活跃规格** | 执行核心自研是军备竞赛（DSH 专职团队无法追赶）；V3 平台形态与"单用户双击即用"交付错配；业主选定 Flutter 全量重构 | Decided 2026-08-13 |
| **引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）** | 唯一面向外部产品进程的稳定缝；业主明确否决 WebView（Flutter 选型意义即原生 UI）；`dsh web` 的 Typert/WS 协议面不稳定 | Decided 2026-08-13 |
| **ACP 三个刻意限制由产品吸收** | ACP 无 elicitation/工具流/transcript：澄清走 `[CLARIFY:]` 约定文本 + 前置采集（DP-1）；工具活动以状态文案呈现（DP-2）；批准卡为唯一交互通道（DP-3）；不达标启用 RB1/RB2 | Decided 2026-08-13 |
| **DSH 钉版本 + 禁自动升级引擎** | DSH pre-release（首个 tagged release 前自由破坏兼容）；升级必须真机回归后随 app 版本发布 | Decided 2026-08-13 |
| **技能语料唯一事实源 = ai-for-china-legal；`dsh` 物化 target** | 语料仓已有 `--to kimi|opencode|standalone` 多端管线；DSH 技能格式同构；只做两类语义改写（斜杠命令/CLAUDE.md 写入） | Decided 2026-08-13 |
| **内容包 = 唯一自动更新层** | 技能迭代最频繁（业主不定期优化）；manifest + sha256 + 原子切换 + 回滚；DSH skill watcher 使更新零重启 | Decided 2026-08-13 |
| **分域预设 + token 预算门禁，禁全量挂载** | DSH 把技能目录（name+description）渲染进模型前缀；345 全挂 = 每请求背整本目录。core ≤30 + 四域；目录渲染 ≤8,000 字符默认 | Decided 2026-08-13 |
| **护栏双层（提示词段 + app 呈现/强制）** | ACP 无工具流，v3.0 的代码级强制（turn_loop.py）在引擎内不可移植；双层任一缺失即算绕过（回归锁定） | Decided 2026-08-13 |
| **docx 确定性变换在 app 侧** | 41,185 字节 Python 脚本是既有资产；docx 生成可审计可测试；模型永不直接写 docx 字节 | Decided 2026-08-13 |
| **v3.x 平台冻结，验收后退役** | gateway/wecom/qq/arena/agent-core/acp-client(TS)/ui-core(SolidJS)/apps/web/apps/desktop 不进 V4 交付物；单用户产品不需要 118K 行平台 | Decided 2026-08-13 |
| **自研 agent core（Python）退役** | V3 决策"自研 core 是默认后端"被 V4 推翻：DSH 全面接管；`packages/agent-core` 冻结，不再投入 | Superseded 2026-08-13 |
| **Tauri/SolidJS 桌面端退役** | 业主 Flutter 全量重构进行中；lawyer-desktop 只取设计参照 | Superseded 2026-08-13 |
| V3 PRD 取代 V2 成为活跃规格 | V2 的四个范围前提（单通道、单后端、无真实 skill、自研只留口）全部失效；且平台从未接上 396 个真实法律 skill | Superseded by V4 on 2026-08-13 |
| **后端层对齐 ACP（Zed Agent Client Protocol v1）** | 本机 `hermes acp --check` 已验证 OK；Codex/Claude Code/Gemini/OpenCode/Cursor/Cline 全支持，Registry 174+ agent；一个 client 取代 3,875 行自定义 adapter；`session/update`+`elicitation`+`request_permission` 与产品需求一一对应 | Decided 2026-08-06 |
| **锁 ACP v1，不用 v2** | v2 为 draft，已知破坏性变更（移除 `fs/*`/`terminal/*`/`session/load`/`tool_call`）；`initialize` 做版本协商，v2 特性开关关闭 | Decided 2026-08-06 |
| **通道层不对齐 AG-UI / Vercel AI SDK / A2A** | 所有客户端均为第一方，标准协议的互操作价值为零；引入第二套事件词汇 + 外部依赖是净负债。但事件词汇与 ACP 同构，保留 AG-UI 映射文档 | Decided 2026-08-06 |
| **自研 agent core 用 Python** | 依据能力非成本：最难的法律产出（Word 原生修订 docx）已有 41,185 字节 Python 实现，Rust 侧只有 74 行基础 docx；skill 语料含 140 个 .py；平台 118K 行 Python + 28 gate。Rust 的离线嵌入优势因业主选定"在线为主"而失效 | Decided 2026-08-06 |
| **自研 core 是默认后端但架构无特权** | 换 `backend_id` 不得需要改任何通道层或 UI 代码；一份实现两个入口（in-process BackendAdapter + `inkstatute-agent acp`） | Decided 2026-08-06 |
| **先定协议、后换心脏**：阶段 A+B+C 用 `hermes acp` 即可交付可用产品，阶段 D 再换自研核心 | 先拿到可用产品，换心脏时不动任何通道代码；也避免把"移植 4,000 行 Rust"放在关键路径上 | Decided 2026-08-06 |
| **skill 语料只读 vendoring，平台建索引 + 物化器** | 所有候选后端都原生加载 SKILL.md；复制进平台仓会立刻产生第四份分叉；两仓有各自 license（含 CC-BY-NC）与演进节奏 | Decided 2026-08-06 |
| **废弃 `solutions/lawfirm/manifest.json` 的 4 条手写 skill 元数据作为 skill 源** | 它与 396 个真实 skill 完全无关，是 V2 为跑通 SolutionLoader 造的假数据 | Decided 2026-08-06 |
| **共享 UI 沿用 SolidJS，从 lawyer-desktop 抽取 `ui-core`** | 团队已有两处 SolidJS 投入；墨律三主题与 23 个已打磨组件是设计资产；换框架收益不足以抵消丢弃代价。chat UI 必须收敛为单一实现（现状约 80% 重复） | Decided 2026-08-06 |
| **移动原生 App 推迟到 V4，本期移动浏览器** | Tauri 2 移动端比桌面端嫩；中国 Android 无 Play Store、iOS 需 App Store 中国区 + ICP 备案 2-4 周。推迟不返工 | Decided 2026-08-06 |
| **先自用（≤50 律师），SaaS 只留契约口** | ACP 每会话一子进程（~200ms 启动）在单律所完全可行，在 SaaS 是死路。契约留 `backend_process_mode`（per_session/pooled/remote），换实现不换契约 | Decided 2026-08-06 |
| **桌面端在线为主、离线只读** | 消除了自研核心必须可嵌入桌面端的约束，从而消除了 Rust 的主要优势论据 | Decided 2026-08-06 |
| **lawyer-desktop 拆解而非整体迁入** | UI → `packages/ui-core`；Tauri 外壳 → `apps/desktop`；agent 逻辑（~4,000 行 PURE/IO 代码）→ 移植进 Python `packages/agent-core`；SQLite CRUD 不迁（平台已有持久化） | Decided 2026-08-06 |
| **工具轮必须流式** | lawyer-desktop 现状是工具轮非流式（先整轮拿 tool_calls，仅最终 content 流），这是要修的缺陷而非要移植的资产 | Decided 2026-08-06 |
| V2 PRD is the active product specification | V1 scope was retired and too broad for the current validation goal | Superseded by V3 on 2026-08-06 |
| Build WeCom receive/send in InkStatute, not Hermes gateway | The user-facing lawyer bot is this product's channel service; Hermes should only provide agent logic | Decided 2026-06-28 |
| Treat Hermes lawfirm as the first agent backend adapter, not the platform or channel boundary | The product must support future Codex/provider-model modes without rewriting platform contracts | Decided 2026-06-28 |
| JSON Schema and Python bindings come before TypeScript | Current runtime priority is Python packages/services with schema as the cross-language contract | - Pending |
| Contract test suite precedes production Hermes hook implementation | Hook output should be validated against stable schemas and fixtures from the start | - Pending |
| Add an explicit Hermes integration spike before production hook work | PRD risks around hook order, message IDs, feedback targets, and redaction can block implementation | Completed in Phase 3 verification on 2026-06-28 |
| Add assistant output boundary before live WeCom acceptance | Hermes gateway/update/restart/command paths can bypass `agent:end`; user-facing WeCom must be owned by InkStatute and remain a pure lawyer assistant bot | Decided 2026-06-28 |
| Use sanitized lawfirm profile bundle plus external secrets for Hermes deployment | Copying the live profile directly risks committing secrets, logs, DBs, feedback, customer documents, and machine-specific paths | Decided 2026-06-28 |
| Lawyer trial acceptance remains a manual human gate | Five-workday legal trial metrics require real usage and legal/safety judgment | - Pending |
| Start a new milestone "Platform Foundation" (v1.1, Phase 09–13) as a deliberate refactor toward a reusable agent platform | User intent is a long-term general agent platform where the lawyer assistant is one solution; V2's additive `services/` shape is not the target | Decided 2026-06-29 |
| Design to four neutral interface contracts: ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime | Channels, agent backends, and solutions must be independently swappable; Hermes/WeCom/lawyer are the first of each, not the platform definition | Decided 2026-06-29 |
| Tech stack: JSON Schema contracts + Python 3.11 async core + TypeScript client SDK/chat component; Rust/Go deferred | Fastest delivery with richest agent ecosystem; first backend (Hermes) and lawyer solution are Python; clients are web/TS; embeddability kept via injectable runtime, not a Rust rewrite | Decided 2026-06-29 |
| Solutions are backend-portable (neutral manifest + per-backend materialization); Hermes profile is the first materialization target | The lawyer pack must later run on Codex/Claude Code/OpenCode/self-built backends without rewriting platform plumbing | Decided 2026-06-29 |
| Clients default to remote/thin; runtime kept embeddable; no local runtime this milestone | Web/desktop/mobile are all consumers of one platform API; desktop local runtime is a north-star option, not now | Decided 2026-06-29 |
| Self-built agent is north star only; this milestone just guarantees BackendAdapter can express it | Avoid over-scoping; ownership of the LLM loop is a future BackendAdapter implementation | Decided 2026-06-29 |
| Autonomy split: Phase 09–13 are code+test+fixtures (autonomous); live cutover and Phase 8 trial are human gates off the autonomous path | Enables hands-free `$gsd-autonomous` while preserving live-safety and legal human review | Decided 2026-06-29 |
| Keep Phase 10 `DefaultRunRuntime` embeddable, default-off, ref-first, and output-boundary-enforced for every yielded run event | The reusable platform core must be injectable and privacy-preserving before Hermes parity work starts | Verified in Phase 10 on 2026-06-29 |
| Keep Hermes one-shot as the default backend lane after Phase 11 | The `/v1/runs` parity spike is implemented but intentionally reports route mismatch evidence; API runs remain default-off behind `INKSTATUTE_HERMES_API_RUNS_ENABLED` until parity and later human gates approve | Verified in Phase 11 on 2026-06-29 |
| Phase 12 channel/client surface is default-off, remote/thin, and not live acceptance across WeCom wrapper, Web/SSE, platform API, SDK, and web chat | The platform channel lane is an embeddable building block, not a production UI; live cutover remains a separate human gate | Verified in Phase 12 on 2026-06-29 |
| Web chat renderer emits DOM-free RenderRecord objects, not HTML strings; host view layer maps records to framework primitives | Eliminates XSS-via-string-concatenation class; forces hosts to use React/Preact/lit-html/raw DOM/server template primitives | Decided 2026-06-29 |
| Start milestone v1.2 "Conversational Context and Memory Foundation" before live promotion | Ordinary users must be able to talk continuously without agent commands, while skill clarification, feedback, and memory stay bounded and privacy-safe | Decided 2026-06-30 |
| Make session continuation automatic rather than user-command-driven | Target users do not understand agent sessions; WeCom should infer whether to continue, resume, or start a new task | Decided 2026-06-30 |
| Build platform-native memory first and evaluate Mem0/Zep as optional adapters | Legal privacy, tenant isolation, deletion/export, and raw-payload rules must be proven before external memory services enter production | Decided 2026-06-30 |
| Treat memory indexes and summaries as derived/cacheable state, not the authority | Contract logs and reference stores remain the audit source; memory is context assembly support | Decided 2026-06-30 |
| Model skill clarification as runtime interrupts | The one-shot conversation path loses ask-user flows; pausing and resuming runs preserves skill questions across user replies | Decided 2026-06-30 |
| Keep platform-native memory as the lawyer-assistant default and route Zep/Hindsight, OpenViking/ReMe, and Mem0 through future sanitized spikes | The component study favors different providers for graph/audit, file-auditable, and PoC use cases, but live legal memory still needs privacy, deletion/export, residency, security, review, benchmark, and license gates | Decided 2026-07-02 |
| Build v1.3 as native production memory first, with external providers as measured adapter spikes | A legal-memory system needs deletion/export, tenant isolation, human review, traceability, and raw-payload controls before provider convenience; external tools must beat or complement the native baseline through sanitized evidence | Decided 2026-07-02 |
| Start M2 (v1.6) before formal V2 acceptance, accepting the PRD §11 dependency violation as risk | V2 code closure is READY (9/9 code reqs, 479 tests, 0 gaps); the only remaining V2 gates are human (Phase 5 live WeCom UAT + Phase 8 lawyer trial) which run in parallel. Blocking all M2 code work on human gates would waste autonomous capacity. Risk accepted: M2 features are contract-compatible extensions, not V2-acceptance-critical paths. | Decided 2026-07-03 |
| Start v1.9 QQBot Host Composition to close v1.8 host-level gaps | v1.8 delivered package-level QQBot production loop with audit `gaps_found`; next value is a thin production webhook host + smoke Protocol-path hardening + controlled live integration, without claiming live acceptance | ✓ Good — shipped 2026-07-10 |
| Host is composition-only (`services/qqbot-service/`); package owns crypto/normalize/send | Avoid duplicating channel logic; keep ADAPTER-04 freeze and empty host deps | ✓ Good — v1.9 |
| Dual default-OFF knobs + explicit `channels=(QQBotChannelAdapter,)` injection | Accidental live IO prevention; no platform-runtime auto-discovery | ✓ Good — v1.9 |
| Smoke dry-run must exercise host Protocol path (not leaf helpers only) | CI honesty: leaf-only evidence cannot claim host-complete | ✓ Good — v1.9 |
| `--live` remains HUMAN GATE; CI never auto-claims live acceptance | Live needs secrets, fresh msg_id, human judgment | ✓ Good — v1.9 |
| Start milestone v1.10 Operator Config Console | Operators need InkStatute-owned UI to configure QQ/WeCom channels, providers (vendor+custom), models, and vision routing without editing Hermes | Decided 2026-07-10 |
| Config secrets stay as refs; values resolve at process edge only | Matches QQ host SAFE-02 and AGENTS.md — never commit tokens or plant raw secrets in config objects | Decided 2026-07-10 |
| Vision routing: dedicated vision model when main model lacks image understanding | GLM-class text models need separate vision path; multimodal mains can consume images directly | Decided 2026-07-10 |

## Shipped Milestones

### v1.11 Product Console (Shipped: 2026-07-15)

Product-grade operations control plane across 9 phases (79–87): runnable `python -m` entry points with ThreadingHTTPServer, WeCom/QQBot process orchestration via admin console, reports/logs/audit/health dashboards reading from existing data sources (no new DB), HMAC-signed session auth coexisting with Bearer tokens, product polish (error pages, responsive nav, one-click startup), and end-to-end smoke test with gate-honesty stamping. Stdlib-only constraint maintained throughout. Audit: tech_debt (27/27 requirements, 9/9 phases, 8/8 integration; no blockers).

**Archive:** [v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md) | [v1.11-REQUIREMENTS.md](milestones/v1.11-REQUIREMENTS.md) | [v1.11-MILESTONE-AUDIT.md](milestones/v1.11-MILESTONE-AUDIT.md)

### v1.10 Operator Config Console (Shipped: 2026-07-12)

InkStatute-owned operator config for channels, providers/catalog, and vision routing without editing Hermes. Refs-only store with Hermes filesystem ban, dual-knob channel enablement, SSRF-safe provider probe, vision routing runtime, CSRF-protected SSR config pages, gate-honesty banners. 7 phases (73–78.1), 20/20 requirements, audit passed.

**Archive:** [v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md) | [v1.10-REQUIREMENTS.md](milestones/v1.10-REQUIREMENTS.md) | [v1.10-MILESTONE-AUDIT.md](milestones/v1.10-MILESTONE-AUDIT.md)

### v1.9 QQBot Host Composition (Shipped: 2026-07-10)

Thin `services/qqbot-service/` webhook host composing package Protocol methods, dual-knob runtime registration, Protocol-path smoke dry-run, and controlled live HUMAN GATE honesty/runbook. Audit passed 11/11. Closed v1.8 accepted host-composition gaps.

**Archive:** [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md)

### v1.7 M3 Platform Extensions (Shipped: 2026-07-06)

Promoted adapter prototypes to production-grade (streaming, artifacts, multi-provider, session memory), extended platform surface (MCP registry, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Gap closure phase 57.1 wired TenantGuard into Web UI data access paths. All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green (1,547+ tests). Audit passed 38/38.

**Archive:** [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)

### v1.6 M2 Multi-Backend & Platform Extensions (Shipped: 2026-07-04)

Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate coverage meta-test. Audit passed 22/22, 19/19 gates green, 969 tests.

**Archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

### v1.4 Long-Term Memory Productization (Shipped: 2026-07-03)

Replaced the evaluation-only memory approach with a single, productized long-term memory layer (Hindsight backend). Unified `Memory` interface, Hindsight adapter, focus/retention policies, WeCom runtime integration, retry/observability, singleton wiring, and contract event observability. Audit passed 20/20.

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

### v1.3 Production Memory System and Evaluation Spikes (Shipped: 2026-07-02)



### v1.2 Conversational Context and Memory Foundation (Shipped: 2026-07-02)

Automatic WeCom session continuity, interrupt resume, bounded short-term context, platform-native memory, feedback-informed context/candidate behavior, external-memory adapter evaluation, and Phase 19 E2E session-runtime closure. Audit status: `tech_debt` accepted.

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

### v1.1 Platform Foundation (Shipped: 2026-06-30)

Four-contract North Star platform architecture (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime) with embeddable runtime, Hermes backend adapter, multi-channel interface, and backend-portable solution loader — all default-OFF. 5 phases, 20 plans, 99 commits, 195 files, 25,368 lines. Audit: passed.

**Archive:** [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) | [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) | [v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

## Current State

- **Active milestone:** v5.0 Tauri Shell + DSH Three-Plane Integration — Phases 122-127. Phase 126 complete; Phase 127 (packaging + three-layer updates) is next.
- **Last shipped:** v3.1 Legal AI Arena (2026-08-09) / v3.0 Unified Legal Core (2026-08-08). v4.0 superseded by v5.0.
- **v5.0 deliverable:** Tauri 2 + SolidJS 桌面 app（装配 ui-core 墨律三主题）经 ACP over stdio 驱动本地嵌入 DeepSeek Harness（DSH）引擎，Windows 桌面双击即用。分域预设 + 内容包自动更新 + 六条护栏双层 + token 预算门禁 + 单 exe 安装包 + 三层更新。
- **Phase 126 complete:** 护栏双层落地（GRD-11..16）+ 分域预设挂载 + 内容包更新 + token 预算门禁（SKL-11..13）。四门全绿、无批量批准路径、event-reducer.ts 未改。
- **Frozen (LEG-01):** gateway / wecom / qq / arena / agent-core / acp-client(TS) / apps/web / apps/flutter_app。`packages/ui-core`(SolidJS) 与 `apps/desktop` 在 v5.0 复活为核心资产。
- **Carried human gates:** HG-1 法律质量（Phase 127）、HG-3 律师试运行（Phase 127）；HG-4 随 APP-04 放弃关闭；HG-2 / QQ `--live` 随通道冻结 DEFERRED。


## Evolution

This document evolves at each phase transition and milestone completion.

**After each phase transition** (via `$gsd-execute-phase` → `$gsd-verify-work`):
1. Requirements invalidated? Move to Out of Scope with rationale.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerge? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. "What This Is" still accurate? Update if drifted.

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of "What This Is" accuracy.
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state.
5. All shipped requirements moved to Validated.
6. Key Decisions table updated with milestone outcomes.

---
*Last updated: 2026-08-16 — Phase 126 (Guardrails & Capability Layer) complete: 9/9 requirements verified, 4 V5 gates green, 6 guardrails dual-layer, no batch approval path. Next: Phase 127 (Packaging + Three-Layer Updates).*