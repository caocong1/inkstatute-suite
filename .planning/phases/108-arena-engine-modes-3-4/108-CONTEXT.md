---
phase: 108
slug: arena-engine-modes-3-4
status: complete
created: 2026-08-09
---

# Phase 108 — Context

> **Discuss phase was skipped.** All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

## Phase Goal

竞技评审（Mode 3）与对抗竞技（Mode 4）在 Mode 1+2 基础上叠加交叉评审、独立 session 综合、对抗式审查与提前停止——核心差异化能力

## Requirements

- **ENGINE-03**: Mode 3 Arena review — self-score iteration + multi-agent cross-review + independent session synthesis
- **ENGINE-04**: Mode 4 Adversarial — arena review + adversarial weakness-finding + multi-round synthesis + early stopping
- **SAFE-06**: Cross-family review enforcement (`backend_family(A) != backend_family(B)`)

## Success Criteria

1. Mode 3：自评迭代 + 多 agent 交叉评审（每个 agent 的产出被其他 agent 评审）+ 独立 session 拿最高分结果与所有评审意见产出最终版
2. Mode 4：在 Mode 3 基础上增加对抗式 weakness-finding + 多轮综合 + 提前停止（硬轮次上限 + ≥8/10 + 零高严重性发现时停止）
3. 跨族评审强制：交叉评审配对时 `backend_family(A) != backend_family(B)`，综合 session 的 backend_family 与所有被综合的 agent 不同；仅有同族 agent 时有明确降级行为（标记并警告，不静默放行）
4. 综合最终版由独立 agent session 产出（fresh context），编排器自身不产出内容
5. 评审输出结构化：findings + confidence（categorical: Certain/Likely/Possible）+ confirmed/disproved 标记

## Key Decisions

All decisions at agent's discretion. Follow AGENTS.md binding architecture decisions, especially:
- **Orchestrator never produces content** — synthesis is done by an independent agent session, not the engine
- **Fresh context per round** — each cross-review and synthesis uses a new session
- **Legal guardrails are non-bypassable** — post-hoc guardrails apply to all external agent outputs including synthesis
- **Cross-family review enforcement** — `backend_family(A) != backend_family(B)` for review pairs
- **Categorical confidence** — Certain/Likely/Possible, NOT numeric percentages (per research anti-patterns)
- **Early stopping** — hard round cap + ≥8/10 score + zero high-severity findings

## Dependencies

- **Phase 107** (Arena Engine — Modes 1+2) — completed (Mode 1, Mode 2, ArenaEngine, SlotRunner, ArtifactStore, GuardrailBoundary, ProvenanceLogger, MockACPBackendAdapter)
