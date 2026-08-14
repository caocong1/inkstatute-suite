---
phase: 118-word-track-changes-export
created: 2026-08-14
status: planning
requirements: [APP-04, GATE-03]
depends_on: [113]
human_gate: HG-4
---

# Phase 118: Word Track-Changes Export — Context

## Goal

律师一键拿到带 Word 原生修订的 docx：模型产结构化变更清单，app 侧便携 Python 执行 41,185 字节 track-changes 脚本做确定性变换；E2E 与金标准齐备，人工闸门 HG-4 就位。

## Requirements

- **APP-04**: Word 原生修订导出 — 模型产结构化变更清单 JSON（schema 本阶段定义）；app 侧便携 Python 执行 `contract_review_trackchanges.py` 确定性变换；输出 docx 到用户路径；金标准 fixtures 取 lawfirm-profile；模型永不直接写 docx 字节
- **GATE-03**: E2E — mock ACP 全流程 + 真实引擎路径 + docx 导出金标准

## Success Criteria

1. 变更清单 JSON schema 定义：条款定位、原文、修订文、修订理由、风险等级；schema 校验测试
2. 便携 Python + track-changes 脚本打包进 app；模型永不直接写 docx 字节（代码断言）
3. 金标准 fixtures：输出 docx 的 track-changes 结构与 fixture 一致
4. 导出 UX：会话内一键导出 → 用户指定路径 → 成功/失败状态明确；失败不污染会话
5. GATE-03 E2E：mock ACP 全流程 + 真实引擎路径 + docx 金标准
6. RESEARCH 结论：embeddable Python 体积与 lxml 依赖兼容性定案
7. **HG-4**：docx 须经律师确认 — 自动化只记录"待确认"状态

## Existing Infrastructure

- `lawfirm-profile/scripts/contract_review_trackchanges.py` — 41,185 bytes, the V4 asset to reuse
  - Uses `lxml` for OOXML manipulation
  - `TrackChangesBuilder` class with `process()` and `save()` methods
  - Currently uses hardcoded `REVIEW_ITEMS` — needs refactoring to accept JSON input
  - Produces Word native track-changes (insertions, deletions, comments)
- V4 gates already include `docx-golden` (currently SKIP, activated this phase)

## Architecture

### V4 Flow

1. Model produces structured change list JSON (in assistant text, parsed by app)
2. App extracts JSON from assistant message
3. App invokes portable Python with `contract_review_trackchanges.py` + JSON + input docx path
4. Python script produces output docx with Word native track-changes
5. App presents output path to user

### Key Constraint

**Model never directly writes docx bytes.** The model only produces the JSON change list. The deterministic transformation is done by the Python script on the app side. This is enforced by:
- The JSON schema being the only model output format for exports
- The Python script being the only docx writer
- Code assertion: no model text reaches the docx writer directly

## Plan Structure

- **118-01**: Change list JSON schema + Dart models + parser
- **118-02**: Python script refactor + portable Python integration + docx golden test infrastructure
- **118-03**: Export UX + GATE-03 E2E + HG-4 status + phase summary
