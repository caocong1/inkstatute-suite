# Phase 125: Frontend Wiring & Pruning - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** UIW-01..05
**Depends on:** Phase 124 GATE-12 绿灯

<domain>
## Phase Boundary

把已经正确到达前端的事件真正渲染出来：换传输层、裁 V3 耦合、裁 Arena、补设置面板与工作区外壳。

**本阶段的核心纪律：`packages/ui-core/src/event-reducer.ts` 与全部 ui-core 组件源码零改动。**
唯一允许改 ui-core 的是**删除** Arena 相关文件与 `src/index.ts` 的导出收敛。
</domain>

<decisions>
## 已定案

- 基座 = `apps/desktop`（Tauri 2 + SolidJS 外壳已存在，3,096 行 Rust + 4,128 行前端）
- UI 组件 = `packages/ui-core`（12,576 行，墨律三主题与 lawyer-desktop 逐字节相同）
- 传输 = Tauri `listen("inkstatute://run-event")`，替换 Gateway SSE

## 事实核对（调研已确认，不需再查）

| 项 | 事实 |
|---|---|
| 主题文件 | `molv-tokens.css` / `molv-base.css` 与 lawyer-desktop **逐字节相同** |
| 组件 CSS | 9 个组件规范化换行符后全部相同 |
| ChatPanel 解耦 | 文件头自述已剥离 dialog/webview/invoke，只认 `RenderState` + adapters |
| events.ts | `packages/platform-sdk-ts/src/events.ts` **零 import**，纯类型模块，可与 HTTP 客户端切割 |
| 缺口 | ui-core 没有 SettingsPanel 与 Workspace 分栏外壳（它们在 app 层） |

## 移植源（只读参照）

| 目标 | 源 | 行数 |
|---|---|---|
| SettingsPanel | `/Users/dongli/Workspace/lawyer-desktop/src/components/settings/SettingsPanel.tsx` | 963 → 砍到 ~600 |
| Workspace 分栏 | `/Users/dongli/Workspace/lawyer-desktop/src/components/workspace/Workspace.tsx` | 277 |
| App 路由 | `/Users/dongli/Workspace/lawyer-desktop/src/App.tsx` | 141 |
| 全局样式 | `/Users/dongli/Workspace/lawyer-desktop/src/index.css` | 111 |

**lawyer-desktop 是另一个仓库，只读参照，不得修改。**
CSS 移植时注意源文件是 CRLF，写入本仓时统一为 LF。

## 删除清单

**`apps/desktop/src/`：**
```
config/gateway.ts          config/arena.ts
contexts/AuthContext.tsx   contexts/ConnectionContext.tsx
pages/ArenaPage.tsx        lib/upload.ts            lib/runBuilder.ts
lib/offlineCache.ts        components/FTS5SearchPanel.tsx（改为接历史面重写）
```

**`apps/desktop/src-tauri/src/`：**
```
commands/offline_cache.rs   migrations/002_offline_cache.sql
```
`workspace/`（chunker/index_store/manager/parser/scanner，1,725 行）：
DSH 自带 fs 工具与沙箱，agent 可自行读用户文件；自建工作区 FTS5 索引不再需要。
**本阶段删除**，若 Phase 126 发现技能需要它再回滚。

**`packages/ui-core/src/`（唯一允许的 ui-core 改动）：**
```
components/ArenaWorkflowCreator.{tsx,css}  components/ParallelStreamPanel.{tsx,css}
components/ScoreCard.{tsx,css}             components/SynthesisViewer.{tsx,css}
components/ReviewSummary.{tsx,css}         components/SlotStreamView.tsx
reducers/arenaEventReducer.ts              stores/arenaStream.ts
types/arena.ts                             stores/sseUtils.ts   stores/eventStream.ts
tests/test_arena_*.{ts,tsx}  tests/test_score_card.tsx  tests/test_parallel_stream_panel.tsx
tests/test_review_summary.tsx  tests/test_synthesis_viewer.tsx
```
删除后收敛 `src/index.ts` 的导出。

**`packages/platform-sdk-ts/`：** 保留 `src/events.ts`，`src/index.ts`（HTTP 客户端）冻结不删但不再被引用。
</decisions>

<risks>
| # | 风险 | 缓解 |
|---|---|---|
| 1 | 删 Arena 时误删被主链路引用的文件 | 每删一批跑 `tsc --noEmit` + `vitest run`，红了立刻回退该批 |
| 2 | `event-reducer.ts` 被顺手"优化" | 门禁脚本里有 `git diff --quiet packages/ui-core/src/event-reducer.ts` 断言 |
| 3 | CRLF/LF 混入导致 diff 噪声 | 移植时统一 LF；`.gitattributes` 若无 `* text=auto` 则补 |
| 4 | 设置面板砍功能时砍掉护栏相关项 | 砍的是 sync/skillopt 页签；LLM/技能/文件/关于四项必须保留 |
| 5 | 删 `workspace/` 后技能需要它 | 本阶段留 git tag `pre-125-workspace-removal` 便于回滚 |
</risks>
