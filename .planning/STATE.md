---
gsd_state_version: 1.0
milestone: v5.0
milestone_name: Tauri Shell + DSH Three-Plane Integration
current_phase: 126
current_phase_name: guardrails-and-presets
status: ready
stopped_at: Phase 125 完成（V3 裁剪 + Tauri 事件传输 + 设置面板 + 工作区外壳 + 引擎启动）；Phase 126 可开始
last_updated: "2026-08-16T00:00:00.000Z"
last_activity: 2026-08-16
last_activity_desc: Phase 125 verification complete, all automated gates green
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 20
  completed_plans: 9
  percent: 65
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-15)

**Core value:** 一名零技术操作的律师在 Windows 桌面上双击即用：Tauri 2 + SolidJS app（装配 `packages/ui-core` 墨律三主题）经 ACP over stdio 驱动本地嵌入的 DSH 引擎，**工具调用与思考过程可见**，分域法律技能随内容包自动更新，四条法律护栏与人审标记不可绕过，引擎半自动更新且失败自动回滚。

**Current focus:** Phase 126 — guardrails-and-presets

## Current Position

Phase: 126 (guardrails-and-presets) — READY
Status: Phase 125 complete, ready for Phase 126
Last activity: 2026-08-16 — Phase 125 verification complete

Progress: [█████████████░] 65% (4/6 phases: 122, 123, 124, 125 complete)

## Milestone v5.0 Overview

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A 引擎底座换血 | 122 | npm lockfile 装配替代 zip 管线；ACP 配置缺陷修复；空目录能装出可启动引擎 |
| B 真实链路打通 | 123-124 | 引擎主管 + 三面接入 + 事件映射；真 key 跑通问答；fixture 门禁亮灯 |
| C 产品外壳 | 125-126 | ui-core 接线 + 裁剪 + 设置面板 + 护栏双层 + 技能能力层 |
| D 交付 | 127 | 单 exe 安装包 + 三层更新 + 回滚门禁 |
| E 增强（交付后） | 128 | 多模型交叉互评 + 对抗质询，分歧强制人审 |

**关键路径：** 122 → 123 → 124 → 125 → 126 → 127（严格串行）。**Phase 128 为交付后增强，不在关键路径上。**

**并行机会：** 无——刻意串行。每阶段验收门禁是下一阶段输入前提；执行方为自主 agent，串行显著降低返工。

## Previous Milestones

### v4.0 Flutter Native + DSH Engine（开发侧闭环 2026-08-15，产品层被 v5.0 推翻）

Phases 112-121。**引擎层与能力层成果继续有效并被 v5.0 沿用**：DSH 接入契约、分域预设、技能 dsh 物化管线、内容包更新机制。
产品层 `apps/flutter_app` 冻结保留（不删除），其 `lib/engine/`、`lib/content/`、`lib/guardrails/`、`lib/wizard/` 是 Rust 侧移植的行为参照。
APP-04（Word 原生修订导出）业主明确放弃。归档待 `/gsd-complete-milestone`。

### v3.1 Legal AI Arena (shipped 2026-08-09) / v3.0 Unified Legal Core (shipped 2026-08-08)

Phases 105-111 / 88-104。v3.x 平台整体冻结。**v3.0 交付的 `packages/ui-core` 与 `packages/platform-sdk-ts/src/events.ts` 在 v5.0 中复活为核心资产**（其余部分保持冻结）。

## Accumulated Context

### Roadmap Evolution

- v5.0 roadmap created 2026-08-15: Phases 122-127, 34 requirements 全部映射, 四阶段（引擎底座换血 → 真实链路打通 → 产品外壳 → 交付）
- v5.0 触发：Flutter UI 打磨成本过高、呈现简陋，不具备交付品相；调研发现 `packages/ui-core` 已是 lawyer-desktop 像素级 UI 的逐字节移植且已解耦在正确的事件缝上
- v4.0 开发侧闭环 2026-08-15 (Phases 112-121)
- v3.1 shipped 2026-08-09 / v3.0 shipped 2026-08-08 / v1.x-V2 共 87 phase 已归档

### Decisions

v5.0 关键决策（依据 `.planning/research/V5-SELECTION.md` 11 项本机实测）：

- **基座 = `apps/desktop` + `packages/ui-core`**，不是 lawyer-desktop（另一仓库），也不是新建项目
- **三面接入**：ACP stdio 做控制面（prompt / cancel / permission）、会话 JSONL 日志做观测面（tool / reasoning / streaming）、`session-query.db` 做历史面（列表 / 全文搜索）
- **会话模型**：一个 app 运行期一个引擎子进程；一个对话一个 ACP 会话；跨 app 重启用**回灌**续接（实测 `contextWindow: 1000000` 使其廉价）
- **否决 SDK JSON-RPC 缝**：无权限通道（"dead capability"）、无取消、无版本协商，违反护栏硬约束
- **否决引擎常驻**：破坏零孤儿进程保证（v4 DSH-02 硬要求）
- **否决自写 DSH 事件转发插件**：官方持久化插件已在写这些数据，读文件即可
- **引擎钉 npm 精确版本，禁用 dist-tag**（`latest` 指向旧版 `0.0.1-rc.1`）
- **引擎更新 = lockfile 装配 + 版本目录 + 冒烟闸 + 指针切换**；npm registry 即 CDN，业主只托管约 40KB 的 `engine-lock.json`
- **放弃 Word 原生修订导出**，连带移除 `docx-rs`、`pdf-extract`、便携 Python、track-changes 脚本

### v4 结论被实测推翻的三条

1. 「工具活动不可见为接受取舍」（V4 DP-2）→ **撤销**
2. 「引擎 170MB zip、禁自动升级」→ **改写为半自动**
3. 「不用 WebView」→ **失效**（该约束的前提是 Flutter 选型）

### Known Defects Carried Into v5.0

| # | 缺陷 | 位置 | 修法 | 归属 |
|---|---|---|---|---|
| D1 | `${DSH_HOME}` 不被 Cordis 展开，会话历史落在引擎目录（更新时被抹） | `engines/acp.cordis.yml` | `!!js process.env.DSH_HOME + '/sessions'`（已修复，冒烟通过） | ENG-04 / Phase 122 ✅ |
| D2 | Google Fonts CDN 中国大陆不可达，字体静默回退 | `packages/ui-core/src/themes/molv-tokens.css:7` | 移除 `@import`，字体本地化 | PKG-12 / Phase 127 |
| D3 | 依赖系统 Node，与零配置冲突 | Flutter 版 `DshConfig` 写死 `executable: 'node'` | 随包带 `node.exe`，绝对路径 spawn | PKG-11 / Phase 127 |
| D4 | `DSH_REPO` 默认值指向不存在的 `/home/sorawatcher/...` | `scripts/build_dsh_release.sh` | 脚本在 Phase 122 退役 | ENG-01 / Phase 122 ✅ |

### 仓库路径更正

V4 文档中的 `/home/sorawatcher/...` 在当前开发机不存在。实际路径：

```
/Users/dongli/Workspace/inkstatute-suite     # 本仓
/Users/dongli/Workspace/lawyer-desktop       # UI 移植源（只读参照）
/Users/dongli/Workspace/deepseek-harness     # DSH 源码（只读参照；构建改走 npm）
/Users/dongli/Workspace/ai-for-china-legal   # 语料仓（348 SKILL.md）
```

### Blockers/Concerns

- **Phase 123 是方案风险闸口**：RTM-07（对话续接回灌）必须用**真实 API key** 实测。若回灌体验不可接受，触发架构回退评审（备选：引擎常驻方案）。不得在证据不足时直接进入 124。
- **DSH 是 pre-release**：每次引擎升级必须过冒烟闸；`engine\current` 指针在冒烟通过前一次都不动。
- **明文 NDJSON 日志体积**：为打开观测面关闭了 zstd 与 packChunks，需在 Phase 124 观测单会话日志量级并定保留期策略。
- **日志尾随延迟**：`writeBatchMaxDelayMs` 默认 200ms，可配置下调；已提交文本经 ACP 与日志双通道到达可交叉校验。
- 语料仓转换器执行环境与内容源在中国大陆的可用性，沿用 v4.0 结论。

## Deferred Items

### Carried Human Gates（v5.0 不得自动关闭 — 延后至交付律师阶段）

| Category | Item | Status |
|----------|------|--------|
| Human gate | HG-1 法律质量：经律师抽样确认不低于 lawyer-desktop/Hermes 基线 | DEFERRED |
| Human gate | HG-3 律师试运行：五工作日 / 15 真实任务 | DEFERRED |
| Human gate | HG-2 真机通道（WeCom live UAT）/ Operator `--live` QQ | DEFERRED — 通道随 v3.x 冻结 |

> HG-4（修订稿质量）随 APP-04 放弃而**关闭**，不再是待办闸门。

### Deferred to post-v5.0

| Category | Item |
|----------|------|
| DEFER-01 | legal-skills 语料并入（51 个，CC-BY-NC 许可评估后） |
| FUTURE-07 | ACP 原生 elicitation（若上游实现，可替代 `[CLARIFY:]` 约定文本） |
| FUTURE-08 | ACP 会话恢复（若上游实现 load/resume，可替代回灌方案） |
| FUTURE-04..06 | 多用户远程引擎 / v3.x 平台复活评估 / Code Mode 预设 |
| MOBILE | 移动端 |

## Session Continuity

Last session: 2026-08-16
Stopped at: v5.0 Phase 124 完成，GATE-12 通过，准备进入 Phase 125
Product spec: docs/requirements/V5-PRD.md (Tauri Shell + DSH Three-Plane Integration)
Research: .planning/research/V5-SELECTION.md (11 项本机实测, HIGH confidence)
Requirements: .planning/REQUIREMENTS.md (34/34 mapped to phases 122-127, 100% coverage)
Execution plan: .planning/ROADMAP.md (Phases 122-127)
v4.0 archive: .planning/milestones/v4.0-REQUIREMENTS.md · v1.x/v3.0 archives: .planning/milestones/

## Operator Next Steps

- **Phase 125 已完成**：V3 平台耦合裁剪、Tauri 事件传输（`inkstatute://run-event`）、设置面板（4 标签）、工作区外壳（可拖拽分屏 + 键盘可达）、引擎启动流（失败显示中文错误 + 重试）全部完成。36 个 desktop 测试通过；85 个 Rust 测试通过；V5 门禁 2/2 绿；`packages/ui-core` 与 `event-reducer.ts` 未改动。
- 执行顺序严格串行：122 → 123 → 124 → 125 → 126 → 127。Phase 125 验收门禁已亮灯，可进入 126。
- **Phase 126 是护栏双层 + 分域预设**：冻结 schema 与提示词段；UI 呈现/强制层；分域预设物化结构；token 预算门禁。
- **Task 5 手动 UI 检查**（6 项真机验证）延后到 Phase 127 集成测试时执行——需要真实引擎装配 + API key。
- 律师人工闸门（HG-1 / HG-3）保持 DEFERRED — 不得自动关闭。
- `apps/flutter_app` 冻结：可读作参照，**不得修改、不得删除**。
- `#[ignore]` 真实引擎测试（`query_real_engine_history` 等）需在网络 + 真实 API key 环境中手动运行。
