---
phase: 107
slug: arena-engine-modes-1-2
status: complete
created: 2026-08-09
---

# Phase 107 — Context

> **Discuss phase was skipped.** All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

## Phase Goal

纯 Python 编排库实现 Mode 1（标准并行）与 Mode 2（自评迭代），用 mock ACP client 即可完整测试；编排器永远不产出内容，法律护栏在引擎边界不可绕过

## Requirements

- **ENGINE-01**: Mode 1 Standard — N agents process in parallel via `asyncio.TaskGroup`, user selects result
- **ENGINE-02**: Mode 2 Self-score iteration — agent self-scores with 10-point framework, self-optimizes, user manually stops
- **ENGINE-05**: Orchestrator never produces content (gate test: no LLM provider imports in arena-engine)
- **ENGINE-06**: Fresh context per round for cross-review/synthesis (gate test: no `session/resume` calls)
- **ENGINE-07**: Artifact persistence — structured output per agent per round, reference-first logging
- **ENGINE-08**: Agent failure recovery — timeout, retry, partial results, asyncio exception isolation
- **ENGINE-09**: User stop/pause/cancel with graceful partial result handling
- **SAFE-01**: Legal guardrails non-bypassable in all 4 modes (research-gate, citation audit, ask-user, de-AI polish)
- **SAFE-02**: Post-hoc citation audit for external ACP agents (v3.0 guardrails live in `turn_loop.py`)
- **SAFE-03**: Post-hoc de-AI polish for external ACP agents
- **SAFE-04**: High-risk legal conclusions retain `requires_human_review=true`
- **SAFE-07**: Provenance logging per claim (agent → reviewer → source)

## Success Criteria

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

## Key Decisions

All decisions at agent's discretion. Follow AGENTS.md binding architecture decisions, especially:
- **The self-built agent core is Python** — the arena engine is a pure Python orchestration library
- **Orchestrator never produces content** — it only coordinates agents, never calls LLM providers directly
- **Legal guardrails are non-bypassable** — research-gate, citation audit, ask-user, de-AI polish
- **Tool rounds must stream** — non-streaming tool rounds are a defect
- **Contract logs prefer references** — `raw_payload_ref` not sensitive full text
- **High-risk legal conclusions stay human-reviewed** — `requires_human_review=true` always

## Dependencies

- **Phase 105** (Arena Contract Extension) — completed (Arena events, dataclasses, Protocol)
- **Phase 106** (ACP fs Handler) — completed (fs handler, sandbox, sanitizer)
