---
phase: 110
slug: arena-ui-integration
status: complete
created: 2026-08-09
---

# Phase 110 — Context

> **Discuss phase was skipped.** All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

## Phase Goal

律师在桌面 app 内完成完整的竞技体验——创建任务、选 agent、看并行流、看评分、看评审、看综合最终版并导出 Word 修订稿；gate 体系更新，端到端集成测试全绿

## Requirements

- **UI-01**: Arena workflow creator — mode selection (1-4), N agent selection, task input, reference file directory
- **UI-02**: Parallel stream panel — N demultiplexed real-time agent streams, per-slot rendering
- **UI-03**: Score card + Review summary — self-score (10-point), findings, confidence, confirmed/disproved
- **UI-04**: Synthesis viewer — final version display + Word native track-changes export
- **UI-05**: ArenaEventReducer — demultiplexing via existing reduce() per slot, no rewrite
- **UI-06**: State persistence — run state + SSE reconnection without re-rendering
- **UI-07**: Gate-coverage meta-test update — 36+ gates, arena-engine + arena-service covered
- **GATE-01**: End-to-end integration tests — all 4 modes, fixture agents, full flow
- **GATE-02**: demo_non_legal arena composability test — no legal-specific fields in top-level required
- **GATE-03**: Gate-coverage meta-test — arena-engine + arena-service src covered and green

## Success Criteria

1. Arena workflow creator 可用：律师可选择模式（1-4）、选择 N 个 ACP 后端 agent、输入任务指令、选择参考文件目录
2. Parallel stream panel 显示 N 个解复用后的实时 agent 流，每个 slot 独立渲染流式回复、thought、tool call
3. Score card 显示每个 agent 每轮的自评分（10 分框架）；Review summary 显示 findings、confidence、confirmed/disproved
4. Synthesis viewer 显示综合最终版并支持 Word 原生修订 track-changes 导出
5. `ArenaEventReducer` 通过组合现有 `reduce()` per slot 实现解复用——不重写单流 reducer 逻辑
6. 刷新保留状态：run state 持久化 + SSE 重连后界面不重复渲染已收到的内容
7. Gate-coverage meta-test 更新至 36+ gates，`arena-engine` 与 `arena-service` 的 `src` 目录均被覆盖且全绿
8. 端到端集成测试覆盖全部 4 种模式（Mode 1-4），用 fixture agent 跑通 create → stream → score → review → synthesis → export 全流程
9. `solutions/demo_non_legal` arena 变体可组合性测试通过——arena 事件不含法律专用字段在顶层 required

## Key Decisions

All decisions at agent's discretion. Follow AGENTS.md binding architecture decisions, especially:
- **Single UI core** — chat UI has exactly one implementation, arena UI extends it
- **ArenaEventReducer composes existing reduce()** — no rewrite of single-stream reducer
- **Word native track-changes** — use existing `lawfirm-profile/scripts/contract_review_trackchanges.py` pattern
- **State persistence** — run state + SSE reconnection without re-rendering
- **Gate coverage** — arena-engine + arena-service src must be covered

## Dependencies

- **Phase 109** (Arena Service) — completed (HTTP+SSE service, all endpoints, gates)
- **Phase 108** (Arena Engine — Modes 3+4) — completed (Mode 3/4, cross-family, adversarial)
- **Phase 107** (Arena Engine — Modes 1+2) — completed (Mode 1/2, ArenaEngine, SlotRunner)
