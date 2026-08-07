# Phase 88: Unified Event Contract - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

平台有一套与 ACP v1 `session/update` 同构的统一事件词汇，能同时承载客户端 SSE 与后端 ACP 两条链路，且每类事件都定义了 bot 非流式降级行为；V2 的 5 个落库 schema 与 28 个 gate 完全不受影响。

这是 v3.0 的第一个 phase，无前置依赖。它交付的是 `packages/platform-contract`——整个里程碑的协议底座。后续 Phase 89（ACP client）、90（event bridge）、91（gateway）全部消费这里定义的事件词汇。

**Success Criteria（必须全部为真）：**
1. `packages/platform-contract` 导出 13 类统一事件（`session.started` / `message.delta` / `message.completed` / `thought.delta` / `tool_call.started|delta|completed` / `plan.updated` / `phase.changed` / `elicitation.requested` / `permission.requested` / `artifact.created` / `citation.recorded` / `run.state_changed` / `error`），每类都有 JSON Schema、Python 绑定、TypeScript 绑定，且 schema 校验测试全过
2. `RunEvent` 被重新规格化为统一事件的承载体，保留 `occurred_at` / `ingested_at` / `seq`；乱序回放测试与"按 `seq` 从任意断点续传不重复不丢失"测试通过
3. 澄清提问契约支持 2-4 题、单选 / 多选 / 自由文本，字段语义与 `ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md` 一致（含 `allow_multiple`），并能与 V2 `RunInterrupt` 的 `interrupt_id` / `resume_state_ref` 互转
4. 五相进度（research → intake → retrieval → draft → review）契约存在，且有到 thinking / tool / streaming / review 的映射表与测试
5. 每类事件的 bot 降级行为（缓冲 / 投递 / 丢弃 / 折叠为业务化提示）在代码中声明且可测——给定一串事件，聚合器产出确定的最终投递内容
6. 现有 28 个 gate 全绿，V2 的 5 个 schema 字段无一改动或删除

**Requirements:** EVT-01, EVT-02, EVT-03, EVT-04, EVT-05, EVT-06

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion

All implementation choices are at the agent's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`). Use ROADMAP phase goal, success criteria, AGENTS.md binding architecture decisions, and codebase conventions to guide decisions.

**Binding constraints from AGENTS.md that apply to this phase:**
- 事件词汇与 ACP `session/update` 同构（Binding Decision #2）——平台是 thin relay，不是翻译层
- `packages/platform-contract` 是实现优先级第一（Implementation Priorities #1）
- `packages/contract-test-suite` 紧随其后——schema validation、fixture replay、composability tests、CI gates（Implementation Priorities #2）
- 法律特定字段属于 `industry_context`；平台级 schema 必须保持行业中性（由 `solutions/demo_non_legal` composability 测试验证）
- Contract logs prefer references such as `raw_payload_ref`，默认不存敏感全文
- 输出边界在本 phase 就要在契约里埋好种子（Binding Decision: 输出边界在 ACP event bridge 和 Gateway 两处强制）
- 权限请求绝不在服务端自动批准——`permission.requested` 事件必须能承载"需用户审批卡片"的语义
- 每个 `packages/*/src` 目录必须被 gate 覆盖（`gate-coverage` meta-test 强制）
- 现有 28 个 gate 必须保持全绿

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Key areas to investigate:
- V2 的 5 个落库 schema（位置与字段）
- 现有 28 个 gate（`scripts/run_v2_gates.py`）
- `ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md`（澄清提问契约源）
- V2 `RunInterrupt` 的 `interrupt_id` / `resume_state_ref` 结构
- ACP v1 `session/update` 事件结构（Hermes Agent v0.19.0 已验证）
- 现有 `packages/` 目录结构（如有）

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
