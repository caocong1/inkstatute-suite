---
phase: 116-chat-ui-output-boundary
created: 2026-08-14
status: planning
requirements: [APP-01, APP-02, APP-03, APP-05]
depends_on: [112, 113]
---

# Phase 116: Chat UI & Output Boundary — Context

## Goal

律师看到的产品本体：单一 Flutter 会话 UI 完整渲染已提交文本流、批准卡片、澄清卡片、引用徽记、人审徽记与状态文案；本地会话库落成；输出边界把一切引擎噪声挡在用户视野外。

## Requirements

- **APP-01**: Flutter 工程骨架（`apps/flutter_app/`，Windows 桌面优先）——单一 chat UI 实现；墨律三主题以 lawyer-desktop 23 组件为设计参照（不逐字复制）
- **APP-02**: 会话 UI——已提交文本流式渲染、批准卡片、澄清卡片（解析 `[CLARIFY:]`）、引用徽记（verified/retrieved/unverified）、人审徽记（`[HUMAN_REVIEW:]`）、状态文案；单 in-flight 时输入禁用
- **APP-03**: 本地会话库（SQLite/drift）——会话/消息/引用/审批记录；按执业方向分组；删除与导出
- **APP-05**: 输出边界——只渲染已提交 assistant 文本；DSH meta/system 噪声永不出现；错误映射用户可读（引擎未启动/限流/鉴权/超时）；原始堆栈只进本地日志

## Success Criteria

1. `apps/flutter_app/lib/chat/` 为唯一 chat UI 实现；墨律三主题可用；`flutter test` 全绿
2. 流式渲染：agent_message_chunk 增量渲染已提交文本；单 in-flight 时输入禁用并显示"处理中"；取消路径有 UI 与测试
3. 批准卡片：session/request_permission 渲染为 allow/reject 卡片；未知 kind 拒绝策略生效；无批量批准控件
4. 澄清卡片：模型输出含 `[CLARIFY: …]` 时渲染澄清卡片，用户补充后作为新 prompt 继续
5. 引用/人审渲染：verified/retrieved/unverified 三态徽记与 `[HUMAN_REVIEW: …]` 徽记视觉可辨
6. 输出边界：非 assistant 已提交文本一律不渲染；错误映射用户可读（四类场景测试）；原始堆栈只进本地日志
7. 本地会话库（SQLite/drift）：CRUD、按执业方向分组、删除与导出
8. 可见性实测（R3）：状态文案与引用审计联动可用

## Existing Infrastructure

- ACP client: `packages/acp_client/` — AcpClient with onUpdate stream, permission policy, session/prompt/cancel
- ACP types: SessionUpdate, RequestPermissionParams, PermissionOption, PermissionOutcome, ApprovalDecision
- Engine: `lib/engine/dsh_config.dart` — DshPaths, DshConfig for subprocess management
- Presets: `lib/presets/` — domain presets
- Content: `lib/content/` — content updater (Phase 115)
- Settings: `lib/settings/content_settings_page.dart` — content settings (Phase 115)
- main.dart: tracer skeleton, needs full app shell

## Key Architecture Decisions

1. **Single chat UI** — `lib/chat/` is the only chat implementation; no duplication
2. **Output boundary** — Only `agent_message_chunk` with `content.type == 'text'` reaches UI; all other notifications are filtered
3. **Approval cards** — `session/request_permission` renders as allow/reject card; unknown kinds auto-denied; no batch approval
4. **Clarification** — `[CLARIFY: …]` text convention parsed from assistant output; user response becomes new prompt
5. **Citation badges** — verified/retrieved/unverified three-state; `[HUMAN_REVIEW: …]` badge
6. **Local session store** — SQLite via drift; sessions/messages/citations/approvals; grouped by practice area
7. **Error mapping** — Four error types: engine-not-started, rate-limited, auth-failed, timeout; raw stack to local log only
8. **Status text** — "正在检索/起草/复核" status text linked to citation audit

## Dependencies to Add

- `drift: ^2.20.0` — SQLite ORM for local session store
- `sqlite3_flutter_libs: ^0.5.0` — SQLite native libraries
- `path_provider: ^2.1.0` — For database file path (may already be transitively available)

## Plan Structure

- **116-01**: Chat models + output boundary + text parser (CLARIFY/HUMAN_REVIEW/citation badges)
- **116-02**: Chat UI widgets (message list, approval card, clarification card, citation badge, status bar)
- **116-03**: Local session store (drift/SQLite: sessions, messages, citations, approvals)
- **116-04**: App shell + error mapping + integration + phase summary
