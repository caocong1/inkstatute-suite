---
phase: 116-chat-ui-output-boundary
status: complete
requirements_closed: [APP-01, APP-02, APP-03, APP-05]
plans_executed: [116-01, 116-02, 116-03, 116-04]
test_count: 316
v4_gates: all-pass
---

# Phase 116 Summary: Chat UI & Output Boundary

## Goal Achieved

律师看到的产品本体：单一 Flutter 会话 UI 完整渲染已提交文本流、批准卡片、澄清卡片、引用徽记、人审徽记与状态文案；本地会话库落成；输出边界把一切引擎噪声挡在用户视野外。

## Plans Executed

### 116-01: Chat models + output boundary + text parser

- `lib/chat/chat_models.dart` — Sealed ChatMessage hierarchy (UserMessage, AssistantMessage, ApprovalMessage, ClarifyMessage, SystemErrorMessage). Citation with three-state type (verified/retrieved/unverified). HumanReviewMarker, ClarifyRequest, ApprovalStatus, ErrorType, MessageStatus, ChatSession.
- `lib/chat/output_boundary.dart` — OutputBoundary filters ACP session updates; only `agent_message_chunk` with text content passes.
- `lib/chat/text_parser.dart` — TextParser extracts `[CLARIFY:]`, `[HUMAN_REVIEW:]`, and `[CITE:type:source]` markers.

### 116-02: Chat UI widgets

- `lib/chat/chat_message_widget.dart` — Renders all ChatMessage subtypes.
- `lib/chat/approval_card_widget.dart` — Interactive allow/reject card, no batch approval.
- `lib/chat/clarification_card_widget.dart` — Clarification card with text input and submit.
- `lib/chat/citation_badge_widget.dart` — Three-state colored badges + human review badge.
- `lib/chat/status_bar_widget.dart` — Processing indicator, cancel button, practice area.
- `lib/chat/chat_view.dart` — Main chat view with message list, input (disabled when processing), send button.

### 116-03: Local session store (drift/SQLite)

- `lib/chat/session_database.dart` — Drift NativeDatabase wrapper with raw SQL API.
- `lib/chat/session_repository.dart` — CRUD: createSession, getSession, listSessions, addMessage, updateApproval, deleteSession, exportSession, listPracticeAreas.
- Dependencies added: drift ^2.20.0, sqlite3_flutter_libs ^0.5.0, path_provider ^2.1.0.

### 116-04: App shell + error mapping + integration

- `lib/chat/chat_controller.dart` — ChangeNotifier bridging AcpClient to UI. Single in-flight enforcement, streaming text aggregation, error mapping, persistence.
- `lib/chat/error_mapper.dart` — ErrorMapper maps exceptions to user-readable Chinese messages (engineNotStarted, rateLimited, authFailed, timeout, unknown). Raw stack traces logged locally only.
- `lib/main.dart` — Full app shell replacing tracer. MaterialApp with light/dark themes, HomeScreen with drawer navigation and ChatView.

## Requirements Closed

- **APP-01**: Flutter app shell with single chat UI under `lib/chat/`. Light/dark themes.
- **APP-02**: Session UI with streaming rendering, approval cards, clarification cards, citation badges, human-review badges, status text, disabled input during processing, cancel button.
- **APP-03**: Local SQLite session database with sessions, messages, citations, approvals. CRUD, grouping by practice area, deletion, export.
- **APP-05**: Output boundary filters non-assistant noise. Error mapping for four scenarios. Raw stack traces to local logs only.

## Test Count

316 tests total (all pass):
- 13 chat_models tests
- 15 output_boundary tests
- 18 text_parser tests
- 5 chat_message_widget tests
- 6 approval_card_widget tests
- 4 clarification_card_widget tests
- 5 citation_badge_widget tests
- 10 chat_view tests
- 4 session_database tests
- 9 session_repository tests
- 9 chat_controller tests
- 8 error_mapper tests
- 2 widget (app shell) tests
- Plus all pre-existing Phase 112-115 tests

## V4 Gates

```
dart-analyze     PASS
flutter-test     PASS
engine-manifest  SKIP (build engine first)
mock-e2e         PASS
meta-test        PASS
docx-golden      SKIP (Phase 118)
```

## R2/R3 Status

- **R2 (澄清体验)**: Clarification card parsing and follow-up prompt implemented and tested. Full round-trip test in chat_controller_test verifies `[CLARIFY:]` extraction and user response submission as new prompt. No PRD RB1 activation needed.
- **R3 (可见性)**: Status text ("处理中..."), citation badges (verified/retrieved/unverified), and human-review badges are all rendered and tested. No PRD RB2 activation needed.

## Commits

- `bcc3cec` — phase context + 4 plans
- `e78ff78` — 116-01: chat models + output boundary + text parser
- `014ad60` — 116-02: chat UI widgets
- `a6d07bf` — 116-03: local session store with drift/SQLite
- (pending) — 116-04: app shell + error mapping + integration
