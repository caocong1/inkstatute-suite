# 墨律 InkStatute

## What This Is

墨律 InkStatute 是一个统一的法律助手平台：**一套法律能力核心，通过同一套事件词汇同时服务所有客户端和所有 agent 后端**。

- **通道层**：Web（桌面/移动浏览器）、桌面 App（Windows/macOS）、WeCom bot、QQ bot；移动原生 App 规划中。全部共享一份 UI 核心，chat UI 只有一份实现。
- **后端层**：任何说 ACP（Zed Agent Client Protocol）的 agent —— Hermes、Codex、Claude Code、Gemini CLI —— 加上墨律自研的 Python agent core。换后端不需要改任何通道代码。
- **能力层**：`ai-for-china-legal`（345 个 SKILL.md）+ `legal-skills`（51 个）共 396 个真实中国法律 skill，以只读 vendoring 引用，平台提供索引与按后端物化，一份 skill 三处可用。

平台自己不执行法律任务，也不为每个后端写胶水。它做的是：定义一套事件词汇，让它同时跑在两条链路上——对客户端说 HTTP+SSE，对后端说 ACP over stdio——并负责扇出、租户、持久化、输出边界与通道降级。

## Core Value

律师可以在任意端（web / 桌面 / 手机浏览器 / 企业微信 / QQ）用到同一套法律能力，得到一致的流式体验、澄清卡片、带 Word 原生修订的文书产物与反馈回路；而平台可以在不动任何通道代码的前提下更换 agent 后端，在不复制 skill 语料的前提下让所有后端共享 396 个真实法律 skill。高风险法律结论始终人审。

## Current Milestone: v3.0 Unified Legal Core — IN PROGRESS

**Started:** 2026-08-06
**Status:** Phases 88-104（17 phases，61 requirements，四阶段）
**Source:** [V3-PRD.md](../docs/requirements/V3-PRD.md) | **Evidence:** [V3-SELECTION.md](research/V3-SELECTION.md)

**为什么重新定位：** V2 交付了 118,556 行 Python、3,173 个测试、28 个 CI gate 的高质量平台管道，但全仓库 grep `ai-for-china-legal` 只命中 PRD 和一份研究笔记——**管道从未接上真实法律能力**。同时存在三个互不相认的执行器（Hermes profile、lawyer-desktop 自研 Rust、lawyer-ai/OpenCode），各自重复实现了 skill 加载、路由、MCP、ask_user。V2 的四个范围前提（单通道、单后端、无真实 skill、自研只留口）已全部失效。

**四个阶段：**

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 协议底座 | 88-90 | Hermes 可通过 ACP 被平台驱动 |
| B 通道统一 | 91-95 | 律师可在 web / 桌面 / WeCom / QQ 四处用同一套能力 |
| C 能力层 | 96-99 | 396 个真实法律 skill 首次进入平台 |
| D 自研核心 | 100-104 | 心脏换成自研 Python core，通道层零改动 |

**关键路径：** 88 → 89 → 90 → 91 → 92 → 93（走完即有可用 Web 产品）

**决定性发现：** `hermes acp --check` → `Hermes ACP check OK`（Hermes Agent v0.19.0）。本项目使用的 Hermes 原生支持 ACP；Codex / Claude Code / Gemini CLI / OpenCode / Cursor / Cline 亦然（ACP Registry 174+ agent）。现有 `packages/backends/{hermes,codex}` 共 3,875 行自定义 adapter 可归并为一个 ACP client。

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

### Active

**v3.0 Unified Legal Core — 61 requirements across 10 categories. See [REQUIREMENTS.md](REQUIREMENTS.md) for the full list and traceability matrix.**

- [ ] EVT-01..06: 统一事件契约（ACP 同构词汇 + Schema/绑定 + 降级规则 + V2 契约保持） — Phase 88
- [ ] ACP-01..07: ACP 后端层（Python client + hermes acp + 第二后端 + 事件桥 + 输出边界 + 权限安全默认） — Phases 89-90
- [ ] GW-01..06: 统一多租户 HTTP+SSE Gateway — Phase 91
- [ ] UI-01..06: 共享 UI 核心 + Web 客户端 + 桌面客户端（chat UI 单一实现） — Phases 92-94
- [ ] BOT-01..03: WeCom/QQ 改为 Gateway 消费者 + 非流式降级，现有生产行为不回退 — Phase 95
- [ ] SKILL-01..09: 396 个真实 SKILL.md 索引 / 物化 / 路由 — Phases 96-98
- [ ] PROF-01..03: 执业配置（CLAUDE.md 机制）多租户化 — Phase 99
- [ ] CORE-01..10: 自研 Python agent core（流式 turn loop / 工具层 / 法律护栏移植 / 双入口） — Phases 100-103
- [ ] CONV-01..05: 存量收敛，约 5,465 行退役 + gate 体系更新 — Phase 104
- [ ] SAFE-01..06: 安全与法律安全（贯穿）

**Human gates（不得由自动化声称通过）：**

- [ ] HG-1 法律质量：移植后的 prompt 装配与法律护栏须由律师抽样确认 — Phase 102
- [ ] HG-4 修订稿质量：Word 原生修订 docx 须由律师确认可用于对外谈判 — Phase 101
- [ ] HG-2 / Phase 5 live WeCom UAT operator confirmation. (carried from V2)
- [ ] HG-3 / 五工作日律师试运行验收. (carried from V2)
- [ ] Operator `--live` QQ OpenAPI acceptance evidence. (carried from v1.9; not auto-claimed)
- [ ] Future host/ops candidates from v1.9 archive: HOST-F01 durable wakeup stores; HOST-F02 async ACK queue; HOST-F03 health endpoints (deferred unless promoted)
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

- **Source of truth: `docs/requirements/V3-PRD.md`.** 选型证据：`.planning/research/V3-SELECTION.md`。V1/V2-PRD 保留为历史文档，不再是活跃需求源。
- **相关仓库**（本仓之外，皆为 workspace 同级目录）：
  - `ai-for-china-legal` — 345 个 SKILL.md，13 plugin，Claude-Code-plugin 格式，纯 prompt；含 `shared/inkstatute-integration/`（为墨律写的 ask_user 协议与 UX 待办）
  - `legal-skills` — 51 个 SKILL.md，37/51 带 `scripts/`（140 个 .py），MIT + CC-BY-NC 双许可
  - `lawyer-desktop` — 本项目前身，Tauri 2.11 + SolidJS；其 UI（23 组件 + 墨律三主题）与 agent 核心逻辑（router 627 / classifier 691 / tool_leak 392）是 V3 的迁入源
  - `lawfirm-profile` — 生产中的 Hermes profile，312 skill；`scripts/router.py`（498 行强信号路由）与 `scripts/contract_review_trackchanges.py`（41,185 字节 Word 原生修订）是必须保住的能力
  - `lawyer-ai` — OpenCode 原型，已搁置，不迁入
- **Target runtime**: Python 为平台与 agent core 语言；TypeScript 为客户端与共享 UI；JSON Schema 为跨语言契约格式。
- **Workflow**: 高自主 GSD，人工闸门保留给法律质量、真机通道与律师试运行。
- **开发顺序具约束力**：协议底座（88-90）→ 通道统一（91-95）→ 能力层（96-99）→ 自研核心（100-104）。阶段 A+B+C 完成即可交付可用产品（后端用 `hermes acp`），阶段 D 换心脏。

- **Architecture**: 一套事件词汇，两条链路——对客户端 HTTP+SSE，对后端 ACP over stdio。平台只做扇出、租户、持久化、输出边界与通道降级，不执行法律任务也不为每个后端写胶水。
- **Backend seam**: 对齐 Zed 的 Agent Client Protocol（v1）。已本机验证 `hermes acp --check` OK。一个 ACP client 取代 N 个自定义 adapter。
- **Channel seam**: 不对齐外部协议（客户端全为第一方，零互操作收益），但事件词汇与 ACP `session/update` 同构，使平台退化为薄中继。
- **Skill layer**: 只读 vendoring + 索引 + 按后端物化。平台不建 skill 执行 runtime，不复制语料。
- **Self-built core**: 默认后端，但架构上无特权——与 hermes/codex 走同一 BackendAdapter 与同一事件词汇。一份实现两个入口（in-process + `inkstatute-agent acp`）。
- **Privacy**: 契约日志 reference-first（`raw_payload_ref`），不存敏感全文。
- **User-facing output**: 输出边界在 ACP 事件桥与 Gateway 双重执行；后端 meta/gateway/system/update/command 噪声不得到达普通律师用户。
- **Permission safety**: ACP `session/request_permission` 服务端不得默认 allow；`terminal`/`execute_code` 类必须显式拒绝或上抛审批（参考 Buzz 的 auto-allow 事故）。
- **Legal safety**: 高风险法律结论人审；research-gate 与 citation 审计不可绕过；不自动合成或修改法律结论类 skill。
- **Composability**: 平台 schema 与 CI 保持行业中立，法律专用字段只进 `industry_context`；由 `solutions/demo_non_legal` 验证。

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **V3 PRD 取代 V2 成为活跃规格** | V2 的四个范围前提（单通道、单后端、无真实 skill、自研只留口）全部失效；且平台从未接上 396 个真实法律 skill | Decided 2026-08-06 |
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

- **Last shipped:** v1.11 Product Console (Phases 79–87) — product-grade operations control plane with process orchestration, observability dashboards, session auth, and end-to-end smoke verification.
- **Active milestone:** v3.0 Unified Legal Core (Phases 88–104) — Stage D 自研核心 in progress.
- **Phase 102 complete:** Legal Guardrail Port — 5 plans, 235 new tests (785 total), 6/6 requirements satisfied (CORE-05..08, SAFE-01, SAFE-04). All four legal guardrails (research-gate, ask-user, citation audit, de-AI polish) enforced at code level. 36 Rust golden fixtures replicated. C-1 code review finding (SAFE-01 bypass) fixed. HG-1 (法律质量) remains human gate.
- **v1.8 accepted gaps:** closed by v1.9 (host composition, Protocol-path smoke, controlled live path docs/honesty).
- **Carried human gates:** Phase 5 live WeCom UAT; Phase 8 five-workday lawyer trial; operator `--live` QQ OpenAPI acceptance.
- **Tech debt (v1.11):** Missing SUMMARY.md for phases 82-85; unchecked REQUIREMENTS.md checkboxes for OBS-04..10; incomplete Nyquist validation for 7/9 phases. All non-blocking.


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
*Last updated: 2026-08-08 — Phase 102 (Legal Guardrail Port) complete, milestone v3.0 in progress*