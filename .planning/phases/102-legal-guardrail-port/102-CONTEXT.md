---
phase: 102
slug: legal-guardrail-port
status: draft
created: 2026-08-08
skip_discuss: true
---

# Phase 102: Legal Guardrail Port - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

`lawyer-desktop` 里最有价值的法律产品知识被完整移植进 Python 核心，且四条法律护栏在代码级不可绕过。

Depends on: Phase 101 (Agent Core Tools — COMPLETE), Phase 99 (Practice Profile — COMPLETE)

Requirements: CORE-05, CORE-06, CORE-07, CORE-08, SAFE-01, SAFE-04

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`). Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from STATE.md / AGENTS.md that MUST be honored:
- **HG-1（Phase 102 法律质量）不得由自动化声称通过。** Rust→Python 移植法律 prompt 逻辑存在失真风险；须先建 golden fixture 对拍集，再由律师抽样确认。
- `tool_leak.rs` 392 行的防泄漏正则移植若有遗漏，会导致工具调用泄漏进用户可见文本。必须用 Rust 侧现有测试用例作为 Python 侧对拍集。
- 高风险法律安全保持：不自动合成 skill、不自动修改法律结论类 skill、`skill_candidate.requires_human_review` 恒为 true。
- 自研 agent core 用 Python；移植是 import/ported-logic，不是重写产品知识。

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

Primary source files to port (per ROADMAP success criteria):
- `lawyer-desktop` Rust: `skills/router.rs` (627 lines) — 中文法律 prompt 装配
- `lawyer-desktop` Rust: `llm/tool_leak.rs` (392 lines) — 工具调用泄漏检测与解析
- citation 审计逻辑（位置待 research 确认）
- 四条法律护栏：research-gate、ask-user-enforcement、citation 审计、de-AI polish

Target: `packages/agent-core/` Python 自研核心（Phase 100/101 已建骨架与工具层）

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

Success Criteria (must be TRUE):
1. `skills/router.rs`（627 行）的中文法律 prompt 装配已移植：三模式基础 prompt、research-gate 注入、检索工具映射（只承诺实际可用的工具）、引用书写规范、skill 描述清单与激活 skill 正文注入
2. `llm/tool_leak.rs`（392 行）的工具调用泄漏检测与解析已移植：DSML / XML 变体识别、全角字符（`｜`、`▁`）归一、泄漏重试；**用 Rust 侧现有测试用例作为 Python 侧对拍集，逐条通过**
3. citation 审计已移植：引用抽取、对照本地法规库与检索证据核验、标注 verified / retrieved / unverified，产出 `citation.recorded` 事件
4. 四条法律护栏代码级强制且有测试：research-gate 前置（未检索不得给法律结论）、ask-user-enforcement（关键事实缺失时阻断起草）、citation 审计、de-AI polish
5. 高风险法律安全保持：不自动合成 skill、不自动修改法律结论类 skill、`skill_candidate.requires_human_review` 恒为 true，有测试断言
6. 建立 golden fixture 对拍集——同一输入在移植前后的 prompt 装配结果可比对，差异需被显式解释

Human Gate: HG-1 法律质量（律师抽样确认输出质量不低于现有 lawyer-desktop / Hermes）—— 不得由自动化声称通过

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
