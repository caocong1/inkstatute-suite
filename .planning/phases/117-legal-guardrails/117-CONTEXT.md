---
phase: 117-legal-guardrails
created: 2026-08-14
status: planning
requirements: [GRD-01, GRD-02, GRD-03, GRD-04, GRD-05, GRD-06]
depends_on: [116]
---

# Phase 117: Legal Guardrails — Context

## Goal

六条护栏以"提示词段 + app 呈现/强制"双层落地，任一层缺失都算护栏绕过（回归测试锁定）；批准栈维持 terminal 默认拒绝；高风险结论恒带人审徽记且不可自动消除。

## Requirements

- **GRD-01**: research-gate — 未检索现行法规/司法解释不得下结论；app 侧无 verified 引用时结论区"待核实"标记
- **GRD-02**: citation audit — 引用必标 verified/retrieved/unverified；三类徽记渲染，unverified 视觉警示
- **GRD-03**: ask-user 强制 — 关键事实缺失不得起草；`[CLARIFY: …]` 解析（Phase 116 已建）与"未澄清任务锁定"状态机
- **GRD-04**: de-AI polish — 终稿过润色段；独立样式呈现；终稿前无 polish 标记的结论被 app 标记"未经润色"
- **GRD-05**: human review — 高风险结论恒带 `[HUMAN_REVIEW: …]`；徽记不可自动消除；批准栈无任何放行路径
- **GRD-06**: 保密 — 上传前脱敏提醒；DeepSeek API 传输告知；客户材料任务入口一次性确认；本地默认

## Success Criteria

1. research-gate 双层：预设人设已含（Phase 113）；app 侧无 verified 引用时结论区"待核实"标记，测试锁定
2. citation audit 双层：模型输出引用解析 → 徽记渲染（Phase 116 已建）；解析失败的引用落入 unverified，测试锁定
3. ask-user 双层：`[CLARIFY: …]` 解析（Phase 116 已建）与"未澄清任务锁定"状态机；锁定态下发送新任务被拦截
4. de-AI polish：终稿渲染样式独立；终稿前无 polish 标记的结论被 app 标记"未经润色"
5. human review：`[HUMAN_REVIEW: …]` 徽记渲染（Phase 116 已建）且无任何 UI/API 路径可自动消除；高风险任务类型清单在 app 配置层定义
6. confidentiality：涉及客户材料的任务入口弹一次性确认（DeepSeek API 传输告知 + 脱敏提醒）；确认记录落本地库
7. 护栏回归套件：6 条护栏各至少 1 个"绕过尝试"负向测试
8. 真实引擎实测：一条带护栏冲突的法律任务在真实 DSH 引擎上产出 `[CLARIFY: …]`（real-API 标注）

## Existing Infrastructure (from Phase 116)

- `lib/chat/text_parser.dart` — Already parses `[CLARIFY:]`, `[HUMAN_REVIEW:]`, `[CITE:type:source]`
- `lib/chat/chat_models.dart` — Citation (verified/retrieved/unverified), HumanReviewMarker, ClarifyRequest
- `lib/chat/citation_badge_widget.dart` — Three-state badges + human review badge
- `lib/chat/clarification_card_widget.dart` — Clarification card with input
- `lib/chat/chat_controller.dart` — Controller with single in-flight, approval handling
- `lib/chat/output_boundary.dart` — Output boundary filtering
- `lib/chat/session_database.dart` — Session store with approvals table
- `presets/legal-core/agent.cordis.yml` — Persona with 6 guardrail prompt segments

## What Phase 117 Adds

### App-side enforcement layer (the "second layer" of each guardrail)

1. **GRD-01 app layer**: `ResearchGateChecker` — Checks if assistant message has verified citations; if not, marks conclusion area with "待核实" tag
2. **GRD-02 app layer**: `CitationAuditEnforcer` — Ensures all citations fall into verified/retrieved/unverified; parse failures default to unverified with visual warning
3. **GRD-03 app layer**: `ClarifyLockStateMachine` — When `[CLARIFY:]` is present, session enters locked state; new prompts are blocked until user responds
4. **GRD-04 app layer**: `PolishChecker` — Detects if assistant text has polish marker `[POLISHED]`; if missing, marks conclusion as "未经润色"
5. **GRD-05 app layer**: `HumanReviewEnforcer` — Ensures `[HUMAN_REVIEW:]` markers cannot be removed by any UI/API path; high-risk task type list in app config
6. **GRD-06 app layer**: `ConfidentialityGate` — One-time confirmation dialog for tasks involving client materials; confirmation record persisted to local DB

### Negative regression test suite

6 bypass-attempt tests, one per guardrail, verifying that removing either layer causes test failure.

## Plan Structure

- **117-01**: Guardrail core models + research-gate + citation audit enforcer (GRD-01, GRD-02)
- **117-02**: Clarify lock state machine + polish checker + human review enforcer (GRD-03, GRD-04, GRD-05)
- **117-03**: Confidentiality gate + high-risk task config + negative regression suite (GRD-06 + all guardrails)
