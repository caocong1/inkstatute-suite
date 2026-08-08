---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Legal AI Arena
status: completed
stopped_at: v3.1 roadmap created — 6 phases (105-110), 45 requirements mapped, ready to plan Phase 105
last_updated: "2026-08-08T17:24:23.326Z"
last_activity: 2026-08-08 -- Phase 107 marked complete
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 13
  completed_plans: 13
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-06)

**Core value:** 律师可以在任意端（web / 桌面 / 手机浏览器 / 企业微信 / QQ）用到同一套法律能力，得到一致的流式体验、澄清卡片、带 Word 原生修订的文书产物与反馈回路；而平台可以在不动任何通道代码的前提下更换 agent 后端，在不复制 skill 语料的前提下让所有后端共享 396 个真实法律 skill。高风险法律结论始终人审。

**Current focus:** Phase 107 — Arena Engine — Modes 1+2

## Current Position

Phase: 107 — COMPLETE
Plan: 1 of 6
Status: Phase 107 complete
Last activity: 2026-08-08 -- Phase 107 marked complete

## Milestone v3.1 Overview

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 契约扩展 | 105 | Arena 生命周期事件 + 数据类 + Protocol 定义完成 |
| B fs 处理器 | 106 | ACP agent 可自主读取参考文件，路径沙箱不可逃逸 |
| C 竞技引擎 — 模式 1+2 | 107 | N agent 并行 + 自评迭代可用，护栏不可绕过 |
| D 竞技引擎 — 模式 3+4 | 108 | 交叉评审 + 对抗竞技 + 独立 session 综合最终版 |
| E 竞技服务 | 109 | 本地 HTTP+SSE 服务暴露全部竞技能力 |
| F 竞技 UI + 集成 | 110 | 桌面 app 内完整竞技体验，gate 更新，端到端全绿 |

**关键路径：** 105 → 106 → 107 → 108 → 109 → 110（Mode 1 在 107 完成时即为可用产品）

**并行机会：** 105 之后 106 可与 107 的 mock-agent 测试并行准备；109 依赖 107+108；110 依赖 109。

## Milestone v3.0 Overview (SHIPPED)

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 协议底座 | 88-90 | Hermes 可通过 ACP 被平台驱动 |
| B 通道统一 | 91-95 | 律师可在 web / 桌面 / WeCom / QQ 四处用同一套能力 |
| C 能力层 | 96-99 | 396 个真实法律 skill 首次进入平台 |
| D 自研核心 | 100-104 | 心脏换成自研 Python core，通道层零改动 |

**关键路径：** 88 → 89 → 90 → 91 → 92 → 93（走完即有可用 Web 产品）— ALL COMPLETE

## Accumulated Context

### Roadmap Evolution

- v3.1 roadmap created 2026-08-08: Phases 105–110, 45 requirements 全部映射, 六阶段（契约扩展 → fs 处理器 → 引擎模式 1+2 → 引擎模式 3+4 → 竞技服务 → 竞技 UI+集成）
- v3.0 roadmap created 2026-08-06: Phases 88–104, 61 requirements 全部映射, 四阶段（协议底座 → 通道统一 → 能力层 → 自研核心）— SHIPPED 2026-08-08
- V2 及 v1.1–v1.11 共 87 个 phase 已归档至 `.planning/milestones/`
- V3 重新定位的触发：V2 的四个范围前提全部失效（详见 PROJECT.md）

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. V3 的 15 条新决策全部记于 2026-08-06。
最影响后续执行的几条：

- 后端层对齐 ACP v1（`hermes acp --check` 已本机验证 OK）；锁 v1 不用 v2 draft
- 通道层不对齐外部协议，但事件词汇与 ACP `session/update` 同构
- 自研 agent core 用 **Python**（依据能力非成本：Word 原生修订 41K 字节 Python vs 74 行 Rust；skill 语料 140 个 .py）
- 先定协议后换心脏：A+B+C 用 `hermes acp` 即可交付可用产品
- skill 语料只读 vendoring，平台建索引 + 物化器，不复制不建执行 runtime
- 共享 UI 沿用 SolidJS，从 lawyer-desktop 抽取；chat UI 必须单一实现
- 移动原生 App 推 V4；SaaS 只留 `backend_process_mode` 契约口
- 工具轮必须流式（修复 lawyer-desktop 的非流式缺陷）

### Pending Todos

**V3-SELECTION.md §7 的 6 个待验证项已全部完成（2026-08-06）。** 结论见 `.planning/research/V3-SELECTION.md` §7。摘要：

| # | 结论 | 关键行动项 |
|---|---|---|
| V1 | 标准 MCP（JSON-RPC 2.0，protocolVersion 2024-11-05） | Phase 101 无需协议适配；2/6 connector 已实现 |
| V2 | codex-acp v1.1.13 + claude-agent-acp v0.65.0 均安装+initialize 通过 | Phase 89 健康检查用 `initialize` 握手而非 `--check` |
| V3 | elicitation 可用但 UNSTABLE；`_meta` fallback 可行 | Phase 90 必须 `use_unstable_protocol=True`；0.12.0 已发布需 re-verify |
| V4 | skill 加载 OK，但必须显式设 `HERMES_HOME`（issue #18594） | Phase 89 subprocess spawner 必须传 `HERMES_HOME`；实际 369 skill 非原记 312 |
| V5 | 纯 Python + lxml，可移植，无平台特定代码 | 文件在 `lawfirm-profile/scripts/`（非 ai-for-china-legal） |
| V6 | 手动注册：新包需加 path 变量 + Gate() 条目 + compileall | 每个引入新包的 phase plan 须含 gate 注册检查项 |

### Blockers/Concerns

- **v3.1 研究标记 Phase 107 (Arena Engine) 需要更深入研究** — 4-mode 工作流逻辑、交叉评审配对矩阵、提前停止收敛阈值是最复杂的算法部分；自评偏差意识、交叉质询/证伪、对抗式弱点查找的 prompt 设计是新颖的，可能需要针对真实法律任务迭代调优。
- **v3.1 研究标记 Phase 109 (Arena Service) 需要更深入研究** — N 路交错流的 SSE 复用与背压处理、子进程存活检测、多路复用流的重连语义是现有 Gateway 不处理的模式（它只处理单 run）；错峰启动 semaphore 与 per-run timeout 值需经验调优。
- **HG-1（Phase 102 法律质量）不得由自动化声称通过。** v3.0 遗留 human gate，律师抽样确认输出质量。
- **HG-4（Phase 101 修订稿质量）不得由自动化声称通过。** v3.0 遗留 human gate，Word 原生修订 docx 须由律师确认。
- Mode 3/4 的 prompt 设计（自评偏差意识、交叉质询、对抗式弱点查找）可能需要律师评审 gate（类似 HG-1）才能 ship。
- ACP 生态变化较快，进入 Phase 105 前应重新核对协议版本状态。

## Deferred Items

### Carried Human Gates（v1.x / v3.0 遗留，v3.1 不得自动关闭）

| Category | Item | Status |
|----------|------|--------|
| Human gate | Phase 5 live WeCom UAT operator confirmation | HUMAN_NEEDED (carried from V2) |
| Human gate | Phase 8 five-workday lawyer trial acceptance | HUMAN_NEEDED (carried from V2) |
| Human gate | Operator `--live` QQ OpenAPI acceptance evidence | HUMAN GATE (carried from v1.9) |

### Deferred to V4

| Category | Item |
|----------|------|
| MOBILE-01..03 | 移动原生 App（Android APK / iOS App Store 中国区 + ICP 备案 / Tauri-mobile vs Capacitor 选型） |
| SCALE-01..03 | SaaS 规模化（ACP agent 进程池 / 远程 ACP 传输 / 水平扩容） |
| OFFLINE-01..02 | 桌面端完全离线的本地 agent runtime |
| FUTURE-01..06 | 定时监控 agent / WeChat 小程序 / 向量 RAG / A2A / AG-UI 适配 / multi-agent-adapter 产品化 |
| v3.1 FUTURE-01..06 | 可靠性加权评分聚合 / skill-index prompt enrichment / 质量成本展示 / arena 状态持久化格式 / 跨族分类法 / arena 与远程 Gateway 组合 |

## Session Continuity

Last session: 2026-08-08
Stopped at: v3.1 roadmap created — 6 phases (105-110), 45 requirements mapped, ready to plan Phase 105
Product spec: .planning/PROJECT.md (v3.1 Legal AI Arena)
Research: .planning/research/SUMMARY.md (Legal AI Arena, HIGH confidence)
Requirements: .planning/REQUIREMENTS.md (45/45 mapped to phases 105-110, 100% coverage)
Execution plan: .planning/ROADMAP.md (Phases 105-110, none started)
Carried human gates (do not auto-complete): HG-1 (法律质量 — Phase 102), HG-4 (修订稿质量 — Phase 101), HG-2 (真机通道 — carried from V2), HG-3 (律师试运行 — carried from V2), QQ --live acceptance (carried from v1.9)
v1.x archives: .planning/milestones/

## Operator Next Steps

- Begin Phase 105 (Arena Contract Extension) with /gsd-plan 105
