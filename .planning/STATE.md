---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Unified Legal Core
status: verifying
stopped_at: Phase 96 context gathered
last_updated: "2026-08-07T18:59:07.750Z"
last_activity: 2026-08-09 -- Phase 95 complete (Gateway client + event consumer + WeCom migration + QQ migration + cross-channel consistency + output boundary verification, BOT-01/02/03 complete, 34 gates green)
progress:
  total_phases: 17
  completed_phases: 8
  total_plans: 35
  completed_plans: 35
  percent: 47
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-06)

**Core value:** 律师可以在任意端（web / 桌面 / 手机浏览器 / 企业微信 / QQ）用到同一套法律能力，得到一致的流式体验、澄清卡片、带 Word 原生修订的文书产物与反馈回路；而平台可以在不动任何通道代码的前提下更换 agent 后端，在不复制 skill 语料的前提下让所有后端共享 396 个真实法律 skill。高风险法律结论始终人审。

**Current focus:** Phase 96 — Real Skill Index (Phase 95 complete)

## Current Position

Phase: 95 (bot-channel-degradation) — COMPLETE ✅
Plan: 95-04 complete (3 commits: WeCom cross-channel consistency tests + QQ cross-channel consistency tests + output boundary tests + GSD artifact updates)
Status: Phase 95 complete — Cross-channel consistency verified (WeCom and QQ produce same semantic result as Web), output boundary double-enforced (no backend noise in bot channels), all 6 success criteria verified, 34 gates green, BOT-01/BOT-02/BOT-03 marked complete
Last activity: 2026-08-09 -- Phase 95 complete (Gateway client + event consumer + WeCom migration + QQ migration + cross-channel consistency + output boundary verification, BOT-01/02/03 complete, 34 gates green)

**Next command:** `/gsd-execute-plan 96` for Phase 96 (Real Skill Index) （或 `/gsd-autonomous` 自动推进）

## Milestone v3.0 Overview

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 协议底座 | 88-90 | Hermes 可通过 ACP 被平台驱动 |
| B 通道统一 | 91-95 | 律师可在 web / 桌面 / WeCom / QQ 四处用同一套能力 |
| C 能力层 | 96-99 | 396 个真实法律 skill 首次进入平台 |
| D 自研核心 | 100-104 | 心脏换成自研 Python core，通道层零改动 |

**关键路径：** 88 → 89 → 90 → 91 → 92 → 93（走完即有可用 Web 产品）

**并行机会：** 92 之后 93/94 可并行；91 之后 95 可与 92/93/94 并行；90 之后 96 可与 B 阶段并行；100 依赖 97 而非 B 阶段。

## Accumulated Context

### Roadmap Evolution

- v3.0 roadmap created 2026-08-06: Phases 88–104，61 requirements 全部映射，四阶段（协议底座 → 通道统一 → 能力层 → 自研核心）
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

- **HG-1（Phase 102 法律质量）不得由自动化声称通过。** Rust→Python 移植法律 prompt 逻辑存在失真风险；须先建 golden fixture 对拍集，再由律师抽样确认。
- **HG-4（Phase 101 修订稿质量）不得由自动化声称通过。** Word 原生修订 docx 须由律师确认可直接用于对外谈判。
- `tool_leak.rs` 392 行的防泄漏正则移植若有遗漏，会导致工具调用泄漏进用户可见文本。必须用 Rust 侧现有测试用例作为 Python 侧对拍集。
- Phase 104 一次性退役约 5,465 行存量代码有回归风险，须分步进行且每步保持 28 gate 绿。
- ACP 生态变化较快，进入阶段 A 前应重新核对 `.planning/research/V3-SELECTION.md` §2.2 的协议版本状态。

## Deferred Items

### Carried Human Gates（v1.x 遗留，v3.0 不得自动关闭）

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

## Session Continuity

Last session: 2026-08-07T18:59:07.744Z
Stopped at: Phase 96 context gathered
Product spec: docs/requirements/V3-PRD.md
Selection evidence: .planning/research/V3-SELECTION.md (§7 verified)
Requirements: .planning/REQUIREMENTS.md (61/61 mapped, EVT-01..06 + ACP-01..07 + SAFE-02..03 + GW-01..06 + UI-04..05 + BOT-01..03 complete)
Execution plan: .planning/ROADMAP.md (Phases 88-104, Phase 88-95 complete, ready for Phase 96)
Carried human gates (do not auto-complete): .planning/phases/08-lawyer-trial-acceptance/
v1.x archives: .planning/milestones/

## Operator Next Steps

- `/gsd-execute-plan 96` — 开始 Phase 96 (Real Skill Index)
- 或 `/gsd-autonomous` 自动推进 Phases 96-104
- 或 `/gsd-autonomous --to 96` 只跑到"能力层"这个里程碑点
