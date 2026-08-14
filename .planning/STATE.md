---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: Flutter Native + DSH Engine
status: Phase 116 complete — ready for Phase 117/118 (parallel)
stopped_at: Phase 116 verified and transitioned — Chat UI & Output Boundary (models + widgets + session store + controller + app shell)
last_updated: "2026-08-14T06:00:00Z"
last_activity: "2026-08-14 — Phase 116 complete: 4/4 plans executed, chat UI with output boundary + approval/clarification/citation cards + drift/SQLite session store + error mapping + app shell, 316 tests, V4 gates all pass"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 21
  completed_plans: 21
  percent: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-13)

**Core value:** 一名零技术操作的律师在 Windows 桌面上双击即用：Flutter 原生 app 经 ACP over stdio 驱动本地嵌入的 DSH 引擎，分域法律技能随内容包自动更新，四条法律护栏与人审标记不可绕过，Word 原生修订稿一键导出。

**Current focus:** Phase 117/118 — Legal Guardrails / Word Export (parallel after 116)

## Current Position

Phase: 117 of 120 (Legal Guardrails) — next in critical path
Status: Phase 116 complete — ready for Phase 117/118 (parallel per roadmap)
Last activity: 2026-08-14 — Phase 116 verified and transitioned: 4/4 plans executed, chat UI with output boundary + approval/clarification/citation cards + drift/SQLite session store + error mapping + app shell, 316 tests, V4 gates all pass

Progress: [▓▓▓▓▓░░░░░] 56%

## Milestone v4.0 Overview

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A DSH 引擎底座 | 112 | Flutter 骨架 + Dart ACP 客户端 + 子进程管理 + 引擎发布脚本，mock 全链路冒烟通过 |
| B 法律预设与能力层 | 113-115 | 分域预设 + dsh 物化管线 + 内容包自动更新可用，token 预算门禁生效 |
| C 客户端与护栏 | 116-118 | 会话 UI / 批准与澄清 / 护栏双层 / Word 导出端到端可用 |
| D 交付与收敛 | 119-120 | 单 exe 安装包 + 三层更新 + 律师试运行验收 + v3.x 冻结收敛 |

**关键路径：** 112 → 113 → 116 → 117 → 119 → 120

**并行机会：** 114/115（技能管线）在 113 后与 116/117 并行；118（docx）依赖 113，与 116/117 并行；119 依赖 115+116+117+118。

## Previous Milestones (SHIPPED)

### v3.1 Legal AI Arena (shipped 2026-08-09)

Phases 105-111：Arena 契约扩展、ACP fs handler、竞技引擎四模式、竞技服务、桌面竞技 UI、v3.1 Closure。归档待 `/gsd-complete-milestone`。

### v3.0 Unified Legal Core (shipped 2026-08-08)

Phases 88-104：统一事件词汇、Python ACP 客户端、多租户 Gateway、ui-core、396 技能索引/物化、自研 Python core、双入口、legacy 收敛。**V4 起自研 core 退役**（见 PROJECT.md Key Decisions）。

## Accumulated Context

### Roadmap Evolution

- v4.0 roadmap created 2026-08-13: Phases 112-120, 33 requirements 全部映射, 四阶段（DSH 引擎底座 → 法律预设与能力层 → 客户端与护栏 → 交付与收敛）
- v3.1 shipped 2026-08-09 (Phases 105-111)
- v3.0 shipped 2026-08-08 (Phases 88-104)
- V2 及 v1.1-v1.11 共 87 个 phase 已归档至 `.planning/milestones/`
- V4 触发：执行核心自研是军备竞赛（DSH 专职团队无法竞争）；V3 平台形态与"单用户双击即用"交付错配；业主选定 Flutter 全量重构并明确否决 WebView

### Decisions

V4 的 10 条新决策记于 PROJECT.md Key Decisions（2026-08-13）。最影响执行的：

- 引擎 = DSH，集成缝 = automation-only ACP server（JSON-RPC stdio）；无 WebView
- ACP 三个刻意限制由产品吸收：澄清走 `[CLARIFY:]` 约定文本 + 前置采集（DP-1）、工具活动不可见（DP-2）、批准卡唯一交互通道（DP-3）
- DSH pre-release → 钉 commit、禁自动升级引擎、升级前真机回归
- 技能语料唯一事实源 = ai-for-china-legal；新增 dsh 物化 target；内容包独立版本化自动更新
- 分域预设 + 核心集 ≤30 + 目录渲染预算门禁（≤8,000 字符默认）——禁全量挂载 345 技能
- docx 确定性变换在 app 侧（便携 Python 执行 41KB track-changes 脚本），模型不写 docx 字节
- v3.x 平台冻结（gateway/wecom/qq/arena/agent-core/ui-core(Tauri)/web/desktop），验收后退役

### Pending Todos

**V4-SELECTION.md §7 的 5 个待验证项全部落在 Phase 112 RESEARCH：**

| # | 验证项 | 关键动作 |
|---|---|---|
| V1 | 真实启动 DSH ACP 组合全流程 | initialize → session/new → prompt → committed text；记录启动时间/env/退出码 |
| V2 | 审批上抛 | 批准栈 terminal 默认拒绝 → `session/request_permission` 上抛实测 |
| V3 | skill 目录进前缀 | `customSkillDirs` 挂 2-3 技能，目录进模型前缀、按名加载可用 |
| V4 | 会话日志路径 | JSONL 路径与结构确认（RB2 依赖） |
| V5 | 生产启动形态 | 构建后 bin（非 tsx）确认，供 `build_dsh_release.sh` 打包 |

### Blockers/Concerns

- **Phase 112 是技术风险闸口**：V1-V5 任一证伪即触发 PRD §12.1 回退评审（RB1 分步表单 / RB2 尾随日志展示），不得在证据不足时直接进入 113。
- **DSH 是 pre-release**：每次升级必须真机回归（Phase 118 GATE-03 真机路径 + 一轮真实法律任务），禁自动升级引擎。
- **HG-1 / HG-4 / HG-3 不得由自动化声称通过。** HG-4 挂 Phase 118，HG-1 与 HG-3 挂 Phase 120，签字权在律师。
- 语料仓在 Windows 路径（`C:\Users\sorawatcher\workspace\ai-for-china-legal`），转换器执行环境（Windows CI 或 WSL 桥接）在 Phase 114 RESEARCH 定案。
- GitHub Release 作为内容源在中国大陆网络环境的可用性在 Phase 115 RESEARCH 定案。

## Deferred Items

### Carried Human Gates（v4.0 不得自动关闭）

| Category | Item | Status |
|----------|------|--------|
| Human gate | HG-1 法律质量：V4 基线（DSH+分域预设）经律师抽样确认不低于 lawyer-desktop/Hermes 基线 | HUMAN_NEEDED (Phase 120) |
| Human gate | HG-4 修订稿质量：Word 原生修订 docx 经律师确认可用于对外谈判 | HUMAN_NEEDED (Phase 118) |
| Human gate | HG-3 律师试运行：五工作日 / 15 真实任务 | HUMAN_NEEDED (Phase 120) |
| Human gate | HG-2 真机通道（WeCom live UAT）| DEFERRED — 通道随 v3.x 平台冻结 |
| Human gate | Operator `--live` QQ OpenAPI acceptance | DEFERRED — 通道随 v3.x 平台冻结 |

### Deferred to post-v4.0

| Category | Item |
|----------|------|
| DEFER-01 | legal-skills 语料并入（51 个，CC-BY-NC 许可评估后） |
| FUTURE-02..06 | 流式工具事件 / ACP elicitation 澄清卡 / 多用户远程引擎 / v3.x 平台复活评估 / Code Mode 预设 |
| MOBILE | 移动端（沿用 V3 决定推后） |

## Session Continuity

Last session: 2026-08-14
Stopped at: Phase 116 complete and verified — ready for Phase 117/118 (parallel)
Product spec: docs/requirements/V4-PRD.md (Flutter Native + DSH Engine)
Research: .planning/research/SUMMARY.md (v4.0, HIGH confidence) + .planning/research/V4-SELECTION.md (选型证据)
Requirements: .planning/REQUIREMENTS.md (33/33 mapped to phases 112-120, 100% coverage)
Execution plan: .planning/ROADMAP.md (Phases 112-120, Phases 112-116 complete)
Carried human gates (do not auto-complete): HG-1 (Phase 120), HG-4 (Phase 118), HG-3 (Phase 120)
v1.x/v3.0 archives: .planning/milestones/

## Operator Next Steps

- Phase 117: Legal Guardrails (parallel with 118)
- Phase 118: Word Track-Changes Export (parallel with 117)
- Phase 112 V1-V5 risk gate is CLOSED; no rollback trigger
- 引擎升级（DSH commit 变更）必须先真机回归再发布，任何阶段不得绕过
- Carried human gates（HG-1, HG-4, HG-3）保持 HUMAN_NEEDED — do not auto-close
