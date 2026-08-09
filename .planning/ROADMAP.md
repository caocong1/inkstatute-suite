# Roadmap: 墨律 InkStatute

## Milestones

- 🔄 **v3.1 Legal AI Arena** — Phases 105-110 (started 2026-08-08)
- ✅ **v3.0 Unified Legal Core** — Phases 88-104 (shipped 2026-08-08)
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

Carried human gates from v1.x (NOT closed by v3.0 or v3.1):

- Phase 5 live WeCom UAT operator confirmation
- Phase 8 five-workday lawyer trial acceptance
- Operator `--live` QQ OpenAPI acceptance evidence

</details>

---

## 🔄 v3.1 Legal AI Arena (STARTED 2026-08-08)

**Milestone Goal:** 律师可在桌面 app 内创建法律任务，选择多个 ACP 后端 agent 并行处理，每个 agent 自评迭代到满意后交叉评审，最终由独立 session 综合评审意见产出最终版——全程流式可见、法律护栏不绕过。

**Source:** `.planning/REQUIREMENTS.md` · **Research:** `.planning/research/SUMMARY.md`

**Phases:**

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 契约扩展 | 105 | Arena 生命周期事件 + 数据类 + Protocol 定义完成，所有组件可发射/消费 arena 事件 |
| B fs 处理器 | 106 | ACP agent 可自主读取用户选定目录的参考文件，路径沙箱不可逃逸 |
| C 竞技引擎 — 模式 1+2 | 107 | N agent 并行 + 自评迭代可用，护栏不可绕过，编排器不产出内容 |
| D 竞技引擎 — 模式 3+4 | 108 | 交叉评审 + 对抗竞技 + 独立 session 综合最终版可用 |
| E 竞技服务 | 109 | 本地 HTTP+SSE 服务暴露全部竞技能力，多流复用 + 权限安全 + 子进程受控 |
| F 竞技 UI + 集成 | 110 | 桌面 app 内完整竞技体验，gate 体系更新，端到端集成测试全绿 |
| G v3.1 Closure | 111 | 桌面 arena UI 真正集成 + Word 导出端点 + FS handler 接线 + 测试回归修复 |

**关键路径：** 105 → 106 → 107 → 108 → 109 → 110 → 111（Mode 1 在 107 完成时即为可用产品；111 闭合 v3.1 audit tech debt）

**并行机会：** 105 之后 106 可与 107 的 mock-agent 测试并行准备；109 依赖 107+108；110 依赖 109；111 依赖 110。

## Phases

### 阶段 A — 契约扩展

- [ ] **Phase 105: Arena Contract Extension** - Arena 生命周期事件 + 数据类 + Protocol + Schema 校验 (CONTRACT-01..04)

### 阶段 B — fs 处理器

- [ ] **Phase 106: ACP fs Handler** - fs/read_text_file 入站路由 + 路径沙箱 + 参考文件注入消毒 + Gateway 向后兼容 (FS-01..04, SAFE-05, GATE-04)

### 阶段 C — 竞技引擎（模式 1+2）

- [ ] **Phase 107: Arena Engine — Modes 1+2** - 并行调度 + 自评迭代 + 编排器不产出内容 + 护栏不可绕过 + 产物持久化 + 故障恢复 + 用户停止 (ENGINE-01, ENGINE-02, ENGINE-05..09, SAFE-01..04, SAFE-07)

### 阶段 D — 竞技引擎（模式 3+4）

- [ ] **Phase 108: Arena Engine — Modes 3+4** - 交叉评审 + 对抗竞技 + 多轮综合 + 提前停止 + 跨族评审强制 (ENGINE-03, ENGINE-04, SAFE-06)

### 阶段 E — 竞技服务

- [ ] **Phase 109: Arena Service** - 本地 HTTP+SSE 服务 + 多流复用 + 输出边界 + 权限安全 + 子进程受控 + SSE 重连 + 错峰启动 (SVC-01..08, GATE-05, GATE-06)

### 阶段 F — 竞技 UI + 集成

- [ ] **Phase 110: Arena UI + Integration** - 桌面竞技 UI + 多流解复用 + 评分/评审/综合展示 + 状态持久化 + gate 更新 + 端到端集成 (UI-01..07, GATE-01..03)

### 阶段 G — v3.1 Closure

- [ ] **Phase 111: v3.1 Closure — Desktop Arena Integration + Export + Wiring + Test Fix** - 桌面 arena UI 真正集成 + Word 导出端点 + FS handler 接线 + BackendAdapter 测试回归修复 (UI-01..07, GATE-01 closure)

---

## Phase Details

### Phase 105: Arena Contract Extension

**Goal**: 平台有一套与现有 13 类事件同构的 Arena 生命周期事件词汇，所有竞技组件在写代码之前就能引用统一的契约——数据类、Protocol、Schema 校验、可组合性测试全部就位
**Depends on**: Nothing (first v3.1 phase; builds on v3.0 platform-contract)
**Requirements**: CONTRACT-01, CONTRACT-02, CONTRACT-03, CONTRACT-04
**Success Criteria** (what must be TRUE):

  1. `packages/platform-contract` 导出 Arena 生命周期事件（`arena.workflow_started` / `arena.workflow_completed` / `arena.score_recorded` / `arena.review_completed` / `arena.synthesis_started` / `arena.synthesis_completed` / `arena.adversarial_challenge_completed` / `arena.early_stop_triggered`），每类都有 JSON Schema、Python dataclass、TypeScript interface，且 schema 校验测试全过
  2. `ArenaWorkflowConfig` / `ArenaHandle` / `ArenaStatus` / `ArenaUserAction` 四个数据类在 Python 与 TypeScript 双侧定义，round-trip 序列化测试通过（Python → JSON → TypeScript → JSON → Python 无损）
  3. `ArenaWorkflow` Protocol 在 `platform-runtime` 中定义，包含启动/取消/用户动作/状态查询方法；一个 mock 实现能通过 Protocol 校验
  4. Arena 事件通过 fixture replay 测试（给定一组事件序列，回放结果确定且不重复不丢失）与可组合性测试（`solutions/demo_non_legal` 不因 arena 事件引入法律专用字段到顶层 required）

**Plans**: TBD (est. 3-4)
**UI hint**: no

### Phase 106: ACP fs Handler

**Goal**: ACP agent 可自主读取用户选定目录内的参考文件，且路径沙箱从第一天起就不可逃逸——遍历、符号链接、绝对路径、非法扩展名、超大文件全部被拒；Gateway 路径不受影响
**Depends on**: Phase 105
**Requirements**: FS-01, FS-02, FS-03, FS-04, SAFE-05, GATE-04
**Success Criteria** (what must be TRUE):

  1. `packages/acp-client` 在 `initialize` 时声明 `clientCapabilities.fs.readTextFile: true`，且入站 `fs/read_text_file` 请求被路由到已注册的 handler（未注册时返回明确错误而非崩溃）
  2. 路径沙箱五重防护全部生效：resolve 规范化 + prefix-check 根目录约束 + symlink rejection + 扩展名 allowlist + size cap；有测试覆盖 path traversal（`../`）、symlink escape、绝对路径越界、非 allowlist 扩展名、超大文件五种攻击向量
  3. Gateway 路径向后兼容：不传 `client_capabilities` 时 `acp-client` 不声明 fs 能力，Gateway 行为零变化，现有 34 gate 全绿
  4. 参考文件在交付给 agent 前经过 prompt injection 消毒（分隔符包裹 + 模式检测 + 检测日志），消毒后的内容可安全注入 agent 上下文
  5. fs/* 沙箱逃逸测试套件（GATE-04）在 CI 中运行且全绿

**Plans**: TBD (est. 3)
**UI hint**: no

### Phase 107: Arena Engine — Modes 1+2

**Goal**: 纯 Python 编排库实现 Mode 1（标准并行）与 Mode 2（自评迭代），用 mock ACP client 即可完整测试；编排器永远不产出内容，法律护栏在引擎边界不可绕过
**Depends on**: Phase 105, Phase 106
**Requirements**: ENGINE-01, ENGINE-02, ENGINE-05, ENGINE-06, ENGINE-07, ENGINE-08, ENGINE-09, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-07
**Success Criteria** (what must be TRUE):

  1. Mode 1：N 个 agent 通过 `asyncio.TaskGroup` 并行处理同一任务，每个 agent 的流式事件带 `metadata.agent_slot` 标记，用户可从 N 个结果中选择一个
  2. Mode 2：每个 agent 用 10 分框架自评 + 自优化迭代，用户可手动停止迭代；停止后保留当前最佳结果
  3. 编排器不产出内容——gate test 断言 `packages/arena-engine` 不导入任何 LLM provider（无 `openai` / `anthropic` / `ollama` import）
  4. 每轮交叉评审/综合使用 fresh context——gate test 断言 `arena-engine` 不调用 `session/resume`（每轮新建 session）
  5. 产物持久化：每个 agent 每轮的 structured output 被持久化，reference-first logging（`raw_payload_ref` 不存敏感全文）
  6. Agent 故障恢复：timeout / crash / retry 被隔离在单个 agent slot 内，`asyncio` 异常不传播到其他 slot，partial results 被保留并标记
  7. 用户 stop/pause/cancel 可随时触发，cancel 后零孤儿进程（PID 断言测试）
  8. 法律护栏在所有 4 种模式中不可绕过：research-gate / citation audit / ask-user / de-AI polish 对自研 agent 在 `turn_loop.py` 内执行，对外部 ACP agent 在引擎边界执行 post-hoc citation audit + de-AI polish
  9. 高风险法律结论的 `requires_human_review` 恒为 true，有测试断言
  10. Provenance 日志：每个 claim 记录 agent → reviewer → source 链路，可追溯

**Plans**: TBD (est. 5-6)
**UI hint**: no

### Phase 108: Arena Engine — Modes 3+4

**Goal**: 竞技评审（Mode 3）与对抗竞技（Mode 4）在 Mode 1+2 基础上叠加交叉评审、独立 session 综合、对抗式审查与提前停止——核心差异化能力
**Depends on**: Phase 107
**Requirements**: ENGINE-03, ENGINE-04, SAFE-06
**Success Criteria** (what must be TRUE):

  1. Mode 3：自评迭代 + 多 agent 交叉评审（每个 agent 的产出被其他 agent 评审）+ 独立 session 拿最高分结果与所有评审意见产出最终版
  2. Mode 4：在 Mode 3 基础上增加对抗式 weakness-finding + 多轮综合 + 提前停止（硬轮次上限 + ≥8/10 + 零高严重性发现时停止）
  3. 跨族评审强制：交叉评审配对时 `backend_family(A) != backend_family(B)`，综合 session 的 backend_family 与所有被综合的 agent 不同；仅有同族 agent 时有明确降级行为（标记并警告，不静默放行）
  4. 综合最终版由独立 agent session 产出（fresh context），编排器自身不产出内容
  5. 评审输出结构化：findings + confidence（categorical: Certain/Likely/Possible）+ confirmed/disproved 标记

**Plans**: TBD (est. 4-5)
**UI hint**: no

### Phase 109: Arena Service

**Goal**: 本地 HTTP+SSE 服务将引擎、acp-client、契约组装为可被桌面 app 消费的单元——绑定 127.0.0.1:8001，多流复用，输出边界与权限安全双重生效，子进程受控
**Depends on**: Phase 108, Phase 106
**Requirements**: SVC-01, SVC-02, SVC-03, SVC-04, SVC-05, SVC-06, SVC-07, SVC-08, GATE-05, GATE-06
**Success Criteria** (what must be TRUE):

  1. `services/arena-service` 绑定 `127.0.0.1:8001`，本地 token auth 生效；非 localhost 连接被拒，无 token 请求被拒
  2. 端点齐全：create arena / stream arena / cancel arena / user action / status arena，且有 OpenAPI 文档
  3. N 个 agent 的流式事件在单条 SSE 连接上复用，每个事件带 `metadata.agent_slot`；客户端可按 slot 解复用
  4. 输出边界在服务层强制执行——与 Gateway 相同的 ACP 输出过滤器，后端 meta/gateway/system 噪声不可到达客户端
  5. 权限安全：dangerous kinds（`terminal` / `execute_code`）被立即拒绝，不存在 batch approve 路径；`_DANGEROUS_PERMISSION_KINDS` 原样保留
  6. 子进程受控：liveness check + per-run timeout + partial-result acceptance；agent 崩溃/超时后 run 不卡死，partial results 被接受并标记
  7. SSE 重连：客户端带 run ID 重连后从断点续传，事件不重复不丢失（buffer by run ID）
  8. 错峰启动 semaphore 防止 N 个 agent 同时 `initialize` 导致竞争
  9. 权限安全测试（GATE-05）与孤儿进程测试（GATE-06）在 CI 中运行且全绿——cancel 后零 PID 残留

**Plans**: TBD (est. 4-5)
**UI hint**: no

### Phase 110: Arena UI + Integration

**Goal**: 律师在桌面 app 内完成完整的竞技体验——创建任务、选 agent、看并行流、看评分、看评审、看综合最终版并导出 Word 修订稿；gate 体系更新，端到端集成测试全绿
**Depends on**: Phase 109
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, GATE-01, GATE-02, GATE-03
**Success Criteria** (what must be TRUE):

  1. Arena workflow creator 可用：律师可选择模式（1-4）、选择 N 个 ACP 后端 agent、输入任务指令、选择参考文件目录
  2. Parallel stream panel 显示 N 个解复用后的实时 agent 流，每个 slot 独立渲染流式回复、thought、tool call
  3. Score card 显示每个 agent 每轮的自评分（10 分框架）；Review summary 显示 findings、confidence、confirmed/disproved
  4. Synthesis viewer 显示综合最终版并支持 Word 原生修订 track-changes 导出
  5. `ArenaEventReducer` 通过组合现有 `reduce()` per slot 实现解复用——不重写单流 reducer 逻辑
  6. 刷新保留状态：run state 持久化 + SSE 重连后界面不重复渲染已收到的内容
  7. Gate-coverage meta-test 更新至 36+ gates，`arena-engine` 与 `arena-service` 的 `src` 目录均被覆盖且全绿
  8. 端到端集成测试覆盖全部 4 种模式（Mode 1-4），用 fixture agent 跑通 create → stream → score → review → synthesis → export 全流程
  9. `solutions/demo_non_legal` arena 变体可组合性测试通过——arena 事件不含法律专用字段在顶层 required

**Plans**: TBD (est. 5-6)
**UI hint**: yes

---

## ✅ v3.0 Unified Legal Core (SHIPPED 2026-08-08)

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

<details>
<summary>v3.0 Phase Details (88-104) — SHIPPED</summary>

### Phase 88: Unified Event Contract ✅

- **Requirements**: EVT-01..06 — 13-category unified event vocabulary, ACP-isomorphic, JSON Schema + Python + TypeScript bindings, bot degradation rules, V2 contract preserved.

### Phase 89: ACP Backend Client ✅

- **Requirements**: ACP-01, ACP-02, ACP-03, ACP-06 — Python ACP client driving hermes acp, second backend proof, subprocess lifecycle.

### Phase 90: ACP Event Bridge & Output Boundary ✅

- **Requirements**: ACP-04, ACP-05, ACP-07, SAFE-02, SAFE-03 — Bidirectional ACP↔unified event mapping, output boundary enforced, permission safety defaults.

### Phase 91: Unified Gateway ✅ COMPLETE

- **Requirements**: GW-01..06 — Single multi-tenant HTTP+SSE Gateway replacing platform_api + lawyer-web-chat.

### Phase 92: Shared UI Core ✅ COMPLETE

- **Requirements**: UI-01, UI-02, UI-03, UI-06 — @inkstatute/ui-core extracted from lawyer-desktop, 23 components, 3 themes, single chat UI implementation.

### Phase 93: Web Client ✅ COMPLETE

- **Requirements**: UI-04 — Responsive web client (desktop + mobile browser), full task flow via Gateway.

### Phase 94: Desktop Client ✅ COMPLETE

- **Requirements**: UI-05 — Tauri desktop shell reusing ui-core, invoke()→Gateway, offline read-only.

### Phase 95: Bot Channel Degradation ✅ COMPLETE

- **Requirements**: BOT-01, BOT-02, BOT-03 — WeCom/QQ as Gateway consumers with non-streaming degradation.

### Phase 96: Real Skill Index ✅ COMPLETE

- **Requirements**: SKILL-01..04, SAFE-05 — 396 real legal SKILL.md indexed, read-only, dual-repo merge.

### Phase 97: Skill Materialization ✅ COMPLETE

- **Requirements**: SKILL-05, SKILL-06, SKILL-09 — Per-backend materialization, three-way separation, manifest cleanup.

### Phase 98: Real-Index Routing ✅ COMPLETE

- **Requirements**: SKILL-07, SKILL-08 — Routing on real skill index, strong-signal rules ported, three-mode detection.

### Phase 99: Practice Profile ✅ COMPLETE

- **Requirements**: PROF-01, PROF-02, PROF-03 — CLAUDE.md practice profile multi-tenantized, cold-start interview.

### Phase 100: Agent Core Skeleton ✅ COMPLETE

- **Requirements**: CORE-01, CORE-04, CORE-09 — Python async streaming turn loop, context budget, model layer.

### Phase 101: Agent Core Tools ✅ COMPLETE

- **Requirements**: CORE-02, CORE-03 — Tool layer + Word-native track-changes docx (41,185 bytes ported).

### Phase 102: Legal Guardrail Port ✅ COMPLETE

- **Requirements**: CORE-05..08, SAFE-01, SAFE-04 — Prompt assembly, tool_leak, citation audit, 4 guardrails ported from Rust.
- **Human gate**: HG-1 法律质量

### Phase 103: Dual Entry Points ✅ COMPLETE

- **Requirements**: CORE-10 — in-process BackendAdapter + `inkstatute-agent acp` CLI.

### Phase 104: Legacy Convergence ✅ COMPLETE

- **Requirements**: CONV-01..05, SAFE-06 — ~10,483 lines retired, gate system updated (34 gates), composability preserved.

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) | [v3.0-phases](milestones/v3.0-phases/)

</details>

### Phase 111: v3.1 Closure — Desktop Arena Integration + Export + Wiring + Test Fix

**Goal**: Wire arena UI components into the desktop app so lawyers can actually use the arena workflow end-to-end (create → stream → score → review → synthesis → export), add the missing Word export endpoint to arena-service, wire Phase 106 FS handler into arena-engine for reference_dir reading, and fix the BackendAdapter method count test regression introduced by SAFE-06's `backend_family()` addition
**Depends on**: Phase 110
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, GATE-01 (closure of partial items from v3.1 audit)
**Success Criteria** (what must be TRUE):

  1. `apps/desktop/src/` imports and renders arena UI components (ArenaWorkflowCreator, ParallelStreamPanel, ScoreCard, ReviewSummary, SynthesisViewer) from `@inkstatute/ui-core` — an arena page or route exists in the desktop app
  2. ArenaWorkflowCreator → `POST /v1/arena` on arena-service is wired end-to-end in the desktop app (lawyer can create an arena workflow from the UI)
  3. `arenaStream.ts` store is wired into the desktop app's arena page — SSE events from arena-service are consumed and demultiplexed via ArenaEventReducer
  4. `POST /v1/arena/{arena_id}/export` endpoint exists in arena-service, calling agent-core's track-changes generation to produce Word-native docx
  5. SynthesisViewer's `onExport` callback calls the new export endpoint and triggers docx download via desktopFileAdapter
  6. arena-engine uses Phase 106 FS handler (FSSandbox.read_text_file) when `ArenaWorkflowConfig.reference_dir` is set — reference files are read, sanitized, and injected into agent context
  7. `test_backend_adapter_has_exactly_9_methods` updated to expect 10 methods (reflecting `backend_family()` addition for SAFE-06) — qqbot-channel gate returns to green (excluding pre-existing recall test)
  8. E2E integration test covers the export flow (create → stream → synthesis → export docx) — GATE-01 closure
  9. All 41 gates green (qqbot-channel recall test pre-existing failure accepted as carry)

**Plans**: 6 plans
Plans:
**Wave 1**

- [x] 111-01-PLAN.md — ui-core export gap (add createArenaStream, ArenaStreamStore, arenaEventReducer, arenaMetaReducer to barrel)
- [x] 111-02-PLAN.md — BackendAdapter test-fix (update 4 count/hash assertions across 3 gates)
- [x] 111-04-PLAN.md — arena-service export endpoint (POST /v1/arena/{id}/export delegating to agent-core track-changes)
- [x] 111-05-PLAN.md — arena-engine reference_dir wiring (FSSandbox + ReferenceSanitizer into _build_run_request)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 111-03-PLAN.md — Desktop arena page + arena client (wire 5 ui-core arena components + createArenaStream store)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 111-06-PLAN.md — E2E export flow test + SynthesisViewer onExport wiring + final 41-gate run

**UI hint**: yes

---

## Progress

### v3.1 Legal AI Arena

**Execution Order:** 105 → 106 → 107 → 108 → 109 → 110 → 111

**Parallelization opportunities** (for wave-based execution):

- After 105: Phase 106 can proceed; mock-agent test scaffolding for 107 can begin
- After 107: Phase 108 depends on 107 (Modes 3+4 build on Modes 1+2)
- After 108 + 106: Phase 109 wires engine + fs handler into service
- After 109: Phase 110 builds UI against running arena-service
- After 110: Phase 111 closes tech debt (desktop integration + export + wiring + test fix)

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 105. Arena Contract Extension | A | 4/4 | Complete   | 2026-08-08 |
| 106. ACP fs Handler | B | 3/3 | Complete   | 2026-08-08 |
| 107. Arena Engine — Modes 1+2 | C | 6/6 | Complete   | 2026-08-08 |
| 108. Arena Engine — Modes 3+4 | D | 4/4 | Complete   | 2026-08-08 |
| 109. Arena Service | E | 6/6 | Complete   | 2026-08-08 |
| 110. Arena UI + Integration | F | 5/5 | Complete   | 2026-08-09 |
| 111. v3.1 Closure | G | 5/6 | In Progress|  |

### v3.0 Unified Legal Core — COMPLETE

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 88. Unified Event Contract | A | 6/6 | Complete | 2026-08-07 |
| 89. ACP Backend Client | A | 3/3 | Complete | 2026-08-07 |
| 90. ACP Event Bridge & Output Boundary | A | 4/4 | Complete | 2026-08-07 |
| 91. Unified Gateway | B | 5/5 | Complete | 2026-08-08 |
| 92. Shared UI Core | B | 4/4 | Complete | 2026-08-08 |
| 93. Web Client | B | 4/4 | Complete | 2026-08-08 |
| 94. Desktop Client | B | 4/4 | Complete | 2026-08-09 |
| 95. Bot Channel Degradation | B | 4/4 | Complete | 2026-08-09 |
| 96. Real Skill Index | C | 4/4 | Complete | 2026-08-09 |
| 97. Skill Materialization | C | 4/4 | Complete | 2026-08-10 |
| 98. Real-Index Routing | C | 3/3 | Complete | 2026-08-10 |
| 99. Practice Profile | C | 3/3 | Complete | 2026-08-10 |
| 100. Agent Core Skeleton | D | 4/4 | Complete | 2026-08-11 |
| 101. Agent Core Tools | D | 4/4 | Complete | 2026-08-11 |
| 102. Legal Guardrail Port | D | 5/5 | Complete | 2026-08-08 |
| 103. Dual Entry Points | D | 3/3 | Complete | 2026-08-08 |
| 104. Legacy Convergence | D | 4/4 | Complete | 2026-08-08 |
