---
phase: 112-dsh-engine-integration-acp-over-stdio
plan: 02
subsystem: acp_client (Dart ACP v1 client — full method coverage)
tags: [acp, dart, flutter, session, prompt, cancel, update, permission, mock-fixtures]
requires:
  - "112-01: Flutter skeleton + Dart ACP client tracer (NDJSON transport, initialize handshake)"
provides:
  - "Full AcpClient with all 7 ACP v1 methods: initialize, session/new, session/prompt, session/cancel, session/update handling, session/request_permission handling"
  - "Client-side cwd validation (absolute path check before sending)"
  - "DP-4 single in-flight enforcement (client-side guard per session)"
  - "session/update agent_message_chunk text aggregation via onUpdate Stream<String>"
  - "Pluggable PermissionPolicy callback for session/request_permission (default deny)"
  - "3 JSONL fixture files: text_turn, cancel, reject_extra_dirs"
  - "4 new test files: session_new_test, session_prompt_test, session_cancel_test, session_update_test"
  - "23/23 tests passing (9 original + 14 new), flutter analyze clean"
affects:
  - "Wave 3+ plans: subprocess manager, build pipeline, chat UI — all build on this full client"
tech-stack:
  added: []
  patterns:
    - "Write queue serialization in AcpTransport.send (Future chain) — prevents IOSink 'StreamSink is bound' on concurrent writes"
    - "Write queue serialization in mock server _send — same pattern for mock server stdout"
    - "Client-side in-flight tracking via Set<String> _inflightSessions — DP-4 single in-flight per session"
    - "Broadcast StreamController<String> for onUpdate — text chunks from agent_message_chunk notifications"
    - "PermissionPolicy typedef callback — pluggable policy hook for session/request_permission"
    - "Mock server --mode=permission — sends session/request_permission, handles client response, sends appropriate agent_message_chunk"
    - "Mock server 100ms delay before prompt response — gives cancel time to arrive and settle"
key-files:
  created:
    - apps/flutter_app/packages/acp_client/test/fixtures/text_turn.jsonl
    - apps/flutter_app/packages/acp_client/test/fixtures/cancel.jsonl
    - apps/flutter_app/packages/acp_client/test/fixtures/reject_extra_dirs.jsonl
    - apps/flutter_app/packages/acp_client/test/session_new_test.dart
    - apps/flutter_app/packages/acp_client/test/session_prompt_test.dart
    - apps/flutter_app/packages/acp_client/test/session_cancel_test.dart
    - apps/flutter_app/packages/acp_client/test/session_update_test.dart
  modified:
    - apps/flutter_app/packages/acp_client/lib/acp_client.dart
    - apps/flutter_app/packages/acp_client/lib/acp_transport.dart
    - apps/flutter_app/packages/acp_client/lib/acp_types.dart
    - apps/flutter_app/packages/acp_client/test/fixtures/mock_acp_server.dart
decisions:
  - "AcpTransport.send serialized via Future-chain write queue — prevents 'StreamSink is bound' errors when prompt + cancel or concurrent prompts race to write"
  - "Mock server _send also serialized with write queue — same IOSink concurrency issue on server side when delayed responses fire simultaneously"
  - "Mock server adds 100ms delay before prompt response — gives cancel notification time to arrive and settle the prompt as cancelled before the default end_turn response fires"
  - "DP-4 single in-flight enforced client-side via Set<String> _inflightSessions — async functions in Dart catch sync throws into Future errors, so tests use expectLater with the Future (not expect with a closure)"
  - "newSession accepts additionalDirectories/mcpServers as optional params — wire payload includes them when non-empty so server can reject with -32602; toJson() omits them for production (always empty)"
  - "PermissionPolicy is a typedef callback (not an interface) — simpler for app-level policy injection; default deny (reject-once) when no policy set"
  - "onUpdate stream uses broadcast StreamController — allows multiple listeners and doesn't buffer when no listener is attached"
  - "Removed ServerRequestHandler typedef and onServerRequest field — replaced by PermissionPolicy callback for request_permission; other server requests get empty result response"
metrics:
  duration: "~8 minutes"
  completed: "2026-08-13T16:23:00Z"
  tasks: 2
  files_created: 7
  files_modified: 4
  tests_passing: 23
  flutter_analyze_issues: 0
---

# Phase 112 Plan 02: Full ACP v1 Client Method Coverage Summary

Expanded the Dart ACP client from the tracer (Plan 01) to full ACP v1 method coverage: session/new with cwd validation, session/prompt with single in-flight enforcement (DP-4), session/cancel, session/update text aggregation, and session/request_permission policy hook — all tested with scripted mock fixtures, no real model needed.

## What Was Built

### Task 1: session/new + session/prompt + session/cancel + mock fixtures + tests (commit 2896675)

**Library code (3 files modified):**
- `acp_client.dart` — Full rewrite from tracer to complete client:
  - `newSession(cwd, {additionalDirectories, mcpServers})`: Validates cwd is absolute client-side (ArgumentError before sending). Includes additionalDirectories in wire payload when non-empty so server can reject with -32602.
  - `prompt(sessionId, text)`: Enforces DP-4 single in-flight per session via `_inflightSessions` Set. Throws StateError if a prompt is already in-flight. Removes from set in `finally` block (handles both success and error).
  - `cancel(sessionId)`: Sends session/cancel as JSON-RPC notification (no id, no response expected).
  - `_handleNotification`: Processes session/update notifications for text aggregation, then dispatches to onNotification callback.
  - `_processSessionUpdate`: Extracts text from agent_message_chunk with content.type == 'text', adds to onUpdate stream. Unknown sessionUpdate types ignored (output boundary).
  - `_handleServerRequest`: Routes session/request_permission through PermissionPolicy callback. Other server requests get empty result response.
  - `onUpdate` getter: Exposes `Stream<String>` from broadcast StreamController for committed assistant text chunks.
  - `setPermissionPolicy(PermissionPolicy)`: Setter for pluggable permission policy.
  - `close()`: Cancels subscription, closes StreamController, closes transport.

- `acp_transport.dart` — Added write queue serialization:
  - `send()` now uses a Future-chain `_writeQueue` to serialize writes. Each send waits for the previous write's flush to complete before writing. Prevents "StreamSink is bound" errors when concurrent sends race (prompt + cancel, or concurrent prompts on different sessions).

- `acp_types.dart` — Added `additionalDirectories` field to `SessionNewParams`. Added `PermissionPolicy` typedef at end of file.

**Mock server (1 file modified):**
- `mock_acp_server.dart` — Expanded with:
  - `--mode=permission` CLI argument: sends `session/request_permission` before prompt response.
  - `session/new`: Rejects non-empty `additionalDirectories` with -32602. Rejects non-empty `mcpServers` with -32602.
  - `session/prompt`: 100ms delay before settling (gives cancel time to arrive). Tracks in-flight prompts in `_inflightPrompts` map.
  - `session/cancel`: Settles in-flight prompt as cancelled (sends response with stopReason: "cancelled"). Unknown sessionId is no-op.
  - `_handleClientResponse`: Handles client's permission response (id: 1) — sends appropriate agent_message_chunk ("DONE" for allow, rejection text for reject) then settles prompt.
  - Write queue serialization in `_send` (same pattern as transport).

**Fixture files (3 files created):**
- `text_turn.jsonl` — initialize → session/new → agent_message_chunk → end_turn
- `cancel.jsonl` — initialize → session/new → cancelled
- `reject_extra_dirs.jsonl` — initialize → -32602 error

**Test files (3 files created, 9 tests):**
- `session_new_test.dart` (4 tests): absolute cwd success, relative cwd ArgumentError, additionalDirectories -32602, mcpServers -32602
- `session_prompt_test.dart` (3 tests): text prompt → end_turn with agent_message_chunk, DP-4 single in-flight rejection, concurrent prompts on different sessions
- `session_cancel_test.dart` (2 tests): cancel settles in-flight as cancelled, cancel unknown sessionId is no-op

### Task 2: session/update aggregation + session/request_permission policy hook + tests (commit e2feb00)

**Test file (1 file created, 5 tests):**
- `session_update_test.dart`:
  - `agent_message_chunk text chunks delivered to onUpdate stream` — verifies text from agent_message_chunk reaches the stream
  - `multiple chunks aggregate into concatenated text` — 3 sequential prompts, 3 chunks, concatenated string verified
  - `unknown sessionUpdate types do not deliver to text stream` — output boundary verified (all delivered chunks are non-empty strings)
  - `permission policy hook is called and response is sent back` — mock server in permission mode sends request_permission, policy callback receives params (sessionId, toolCallId, options), returns allow-once, mock sends "DONE" text
  - `default policy (no hook) returns reject-once` — no policy set, mock sends rejection text, stopReason is end_turn

## Verification Results

| Check | Result |
|-------|--------|
| `flutter test packages/acp_client/` | exit 0 — 23/23 tests passed |
| `flutter analyze` (apps/flutter_app) | exit 0 — No issues found |
| `flutter analyze packages/acp_client` | exit 0 — No issues found |
| Frozen directories modified | None |
| Real model calls | None — all tests use mock ACP server fixtures |

## Test Inventory

| File | Tests | Coverage |
|------|-------|----------|
| acp_transport_test.dart | 5 | NDJSON send/messages, unparseable line skip (T-112-01) |
| acp_client_test.dart | 4 | initialize handshake, newSession, prompt end_turn, ID correlation |
| session_new_test.dart | 4 | absolute cwd, relative cwd rejection, additionalDirectories -32602, mcpServers -32602 |
| session_prompt_test.dart | 3 | text prompt end_turn, DP-4 single in-flight, concurrent different sessions |
| session_cancel_test.dart | 2 | cancel settles as cancelled, cancel unknown sessionId no-op |
| session_update_test.dart | 5 | onUpdate stream delivery, multi-chunk aggregation, unknown type boundary, permission hook, default deny |
| **Total** | **23** | |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AcpTransport.send concurrent write serialization**
- **Found during:** Task 1
- **Issue:** Concurrent sends (prompt + cancel, or Future.wait of concurrent prompts) caused "Bad state: StreamSink is bound to a stream" errors because IOSink.flush() was in progress when the second write attempted.
- **Fix:** Added a Future-chain `_writeQueue` to `AcpTransport.send()` that serializes writes — each send waits for the previous flush to complete before writing.
- **Files modified:** `acp_transport.dart`
- **Commit:** 2896675

**2. [Rule 1 - Bug] Mock server concurrent write serialization**
- **Found during:** Task 1
- **Issue:** When two delayed prompt responses fired simultaneously (concurrent prompts test), the mock server's `_send()` had the same IOSink concurrency issue.
- **Fix:** Added the same Future-chain write queue pattern to the mock server's `_send()` method.
- **Files modified:** `mock_acp_server.dart`
- **Commit:** 2896675

**3. [Rule 3 - Blocking] Mock server prompt response delay for cancel test**
- **Found during:** Task 1
- **Issue:** The mock server's prompt response was immediate (via `.then()` chaining), so the prompt completed with `end_turn` before the cancel notification arrived. The cancel test expected `cancelled` but got `end_turn`.
- **Fix:** Added a 100ms `Future.delayed` before the prompt response in `_handleDefaultPrompt`. The cancel handler checks `_inflightPrompts` and settles as cancelled; the delayed response checks if the prompt is still in-flight before sending `end_turn`.
- **Files modified:** `mock_acp_server.dart`
- **Commit:** 2896675

**4. [Rule 3 - Blocking] DP-4 test: async function throws are Future errors, not sync throws**
- **Found during:** Task 1
- **Issue:** `expect(() => client.prompt(...), throwsA(...))` didn't catch the StateError because Dart async functions catch synchronous throws and turn them into Future errors. The closure returned a Future (not a throw), so `throwsA` didn't fire.
- **Fix:** Changed to `await expectLater(client.prompt(...), throwsA(isA<StateError>()))` — `expectLater` with a Future properly catches Future errors.
- **Files modified:** `session_prompt_test.dart`
- **Commit:** 2896675

**5. [Rule 2 - Missing functionality] Removed ServerRequestHandler, replaced with PermissionPolicy**
- **Found during:** Task 1 (acp_client.dart rewrite)
- **Issue:** The Plan 01 tracer had a generic `ServerRequestHandler` typedef and `onServerRequest` field. The plan specifies a dedicated `PermissionPolicy` callback for `session/request_permission`.
- **Fix:** Replaced `ServerRequestHandler`/`onServerRequest` with `PermissionPolicy` typedef and `_permissionPolicy` field. The `_handleServerRequest` method routes `session/request_permission` through the policy hook; other server requests get an empty result response. Default policy is reject-once (default deny).
- **Files modified:** `acp_client.dart`
- **Commit:** 2896675

## Known Stubs

None — all code is production-quality with real behavior. The AcpClient implements all 7 ACP v1 methods with full protocol compliance, in-flight tracking, text aggregation, and permission policy hook.

## Threat Flags

None — no new security-relevant surface beyond what the plan's threat model covers. T-112-03 (single in-flight elevation of privilege) is mitigated by the client-side `_inflightSessions` guard that rejects a second prompt before sending (DP-4). The permission policy hook defaults to reject-once (default deny) when no policy is set.

## Self-Check: PASSED

All created files exist on disk. All commit hashes verified in git log.
