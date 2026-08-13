---
phase: 112-dsh-engine-integration-acp-over-stdio
plan: 03
subsystem: acp_client (Dart ACP approval security three-state policy)
tags: [acp, dart, flutter, approval, security, permission, three-state, no-batch]
requires:
  - "112-01: Flutter skeleton + Dart ACP client tracer (NDJSON transport, initialize handshake)"
  - "112-02: Full ACP v1 client method coverage (session/new, prompt, cancel, update, permission hook)"
provides:
  - "ApprovalPolicy class with three-state logic: unknown kind → AutoDeny, terminal/execute_code → RenderCard, no batch path"
  - "PermissionKind enum (terminal, executeCode, unknown) with safe-default parsing"
  - "ApprovalDecision sealed class (AutoDeny, RenderCard) — deliberately no AutoAllow subtype"
  - "RequestPermissionParams extended with optional toolName for tool kind inference"
  - "ApprovalPolicy.resolveCard / resolveCardDismissed for one-shot user card resolution"
  - "ApprovalPolicy.defaultPolicy — denies all when no UI connected (safe default)"
  - "ApprovalPolicy.assertValidOptionId — enforces only allow-once/reject-once are valid"
  - "Mock server --escalation modes: approved, rejected, unknown-kind"
  - "3 JSONL fixture files: escalation_approved, escalation_rejected, unknown_kind"
  - "15 new tests covering all three states + no-batch negative grep + end-to-end flows"
  - "38/38 tests passing (23 original + 15 new), flutter analyze clean"
affects:
  - "Phase 116 (chat UI): approval card rendering will use ApprovalPolicy.evaluate + resolveCard"
  - "Wave 3+ plans: subprocess manager and chat UI build on this security boundary"
tech-stack:
  added: []
  patterns:
    - "Sealed class for ApprovalDecision — exhaustiveness checking ensures no AutoAllow can be added accidentally"
    - "PermissionKind.fromString returns unknown for null/unrecognized — safe default, never throws"
    - "toolKind parameter on evaluate() — ACP protocol carries only allow-once/reject-once options; tool kind is inferred from approval request context (RESEARCH.md nuance)"
    - "Mock server --escalation modes include toolName in toolCall object — simulates tool kind metadata for testing"
    - "Negative grep test reads source file and asserts forbidden patterns (allow-always, allow_all, remember, batch) are absent"
    - "assertValidOptionId runtime assertion — only allow-once and reject-once are valid option ids"
key-files:
  created:
    - apps/flutter_app/packages/acp_client/lib/approval_policy.dart
    - apps/flutter_app/packages/acp_client/test/approval_policy_test.dart
    - apps/flutter_app/packages/acp_client/test/fixtures/escalation_approved.jsonl
    - apps/flutter_app/packages/acp_client/test/fixtures/escalation_rejected.jsonl
    - apps/flutter_app/packages/acp_client/test/fixtures/unknown_kind.jsonl
  modified:
    - apps/flutter_app/packages/acp_client/lib/acp_types.dart
    - apps/flutter_app/packages/acp_client/lib/acp_client.dart
    - apps/flutter_app/packages/acp_client/test/fixtures/mock_acp_server.dart
decisions:
  - "ApprovalDecision is a sealed class with exactly two subtypes (AutoDeny, RenderCard) — Dart exhaustiveness checking ensures no AutoAllow can be added without updating all switch statements"
  - "PermissionKind.fromString returns PermissionKind.unknown for null or unrecognized values — safe default, never throws, always denies"
  - "ApprovalPolicy.evaluate takes a separate toolKind String parameter (not from RequestPermissionParams) — the ACP protocol does not carry tool kind in session/request_permission options; the app infers it from approval request context (RESEARCH.md §Approval Security Three-State nuance)"
  - "RequestPermissionParams extended with optional toolName field — the mock server includes this for testing; production code infers kind from tool call metadata or session context"
  - "defaultPolicy is a static final instance with no onUserCard callback — denies all kinds including terminal/execute_code (safe when no UI connected)"
  - "Mock server --escalation argument is separate from --mode — escalation modes include toolName in toolCall object; mode=permission (from Plan 02) remains unchanged for backward compatibility"
  - "Negative grep test reads the source file at test time and asserts forbidden patterns are absent — catches regressions if someone adds allow-always/remember/batch strings"
  - "assertValidOptionId throws AssertionError for any optionId other than allow-once/reject-once — runtime enforcement of the no-durable-grant invariant"
  - "Forbidden strings (allow-always, allow-all, remember, batch) were removed from all comments and error messages in approval_policy.dart — the negative grep test checks the raw source file including comments"
metrics:
  duration: "~6 minutes"
  completed: "2026-08-13T17:30:00Z"
  tasks: 1
  files_created: 5
  files_modified: 3
  tests_passing: 38
  flutter_analyze_issues: 0
---

# Phase 112 Plan 03: Approval Security Three-State Policy Summary

Implemented and tested the DSH-04 approval security three-state policy: unknown permission kinds are always denied (never shown to user), terminal/execute_code kinds render as user-facing approval cards (deferred decision for UI), and no batch/durable grant path exists anywhere in the code. This locks down the approval security boundary before any UI is built (Phase 116).

## What Was Built

### Task 1: ApprovalPolicy three-state logic + tests + mock fixtures (commit d8c4201)

**Library code (3 files modified, 1 created):**

- `approval_policy.dart` (new) — Three-state approval policy:
  - `ApprovalPolicy` class with `evaluate(RequestPermissionParams, String? toolKind)` → `ApprovalDecision`
  - Unknown kind → `AutoDeny` (reject-once immediately, never shown to user)
  - terminal/execute_code with UI → `RenderCard` (deferred decision, invokes `onUserCard` callback)
  - terminal/execute_code without UI → `AutoDeny` (safe default when no UI connected)
  - `resolveCard(RenderCard, String userChoice)` → `PermissionOutcome.selected('allow-once')` or `PermissionOutcome.selected('reject-once')` — one-shot only
  - `resolveCardDismissed(RenderCard)` → `PermissionOutcome.cancelled()`
  - `decisionToOutcome(ApprovalDecision)` — static helper: AutoDeny → reject-once, RenderCard → StateError (must be resolved)
  - `defaultPolicy` static instance — denies all kinds (no UI connected)
  - `assertValidOptionId(String)` — throws AssertionError for any optionId other than 'allow-once'/'reject-once'
  - No method or field produces 'allow-always', 'allow-all', 'remember', 'batch', or any durable grant

- `acp_types.dart` (modified) — Expanded with approval-specific types:
  - `PermissionKind` enum: `terminal`, `executeCode`, `unknown` — with `fromString(String?)` that returns `unknown` for null/unrecognized (safe default)
  - `ApprovalDecision` sealed class: `AutoDeny` (deny immediately), `RenderCard` (defer to user UI) — deliberately NO `AutoAllow` subtype
  - `RequestPermissionParams` extended with optional `toolName` field — parsed from `toolCall.toolName` if present (mock server includes it for testing; ACP protocol itself doesn't carry tool kind)

- `acp_client.dart` (modified) — Added `export 'approval_policy.dart'` to the library entry point

**Mock server (1 file modified):**
- `mock_acp_server.dart` — Expanded with `--escalation` argument:
  - `--escalation=approved`: Sends `session/request_permission` with `toolName: 'terminal'`, waits for client response. If allow-once → "DONE" agent_message_chunk → end_turn.
  - `--escalation=rejected`: Same but expects reject-once → rejection message → end_turn.
  - `--escalation=unknown-kind`: Sends `session/request_permission` with `toolName: 'mystery_tool'` (unrecognized kind) → expects auto-deny (reject-once) → rejection message → end_turn.
  - `--escalation` is separate from `--mode` — existing `--mode=permission` (Plan 02) remains unchanged for backward compatibility.

**Fixture files (3 files created):**
- `escalation_approved.jsonl` — Derived from DSH `escalation-approved/stdout.expected.jsonl`: initialize → session/new → request_permission (terminal) → allow-once → "DONE" → end_turn
- `escalation_rejected.jsonl` — Derived from DSH `escalation-rejected/stdout.expected.jsonl`: initialize → session/new → request_permission (terminal) → reject-once → rejection message → end_turn
- `unknown_kind.jsonl` — Synthetic fixture: initialize → session/new → request_permission (mystery_tool) → auto-deny → rejection message → end_turn

**Test file (1 file created, 15 tests):**
- `approval_policy_test.dart`:
  - Test 1: Unknown kind → AutoDeny → PermissionOutcome.selected('reject-once') (never renders card)
  - Test 2 (extra): null toolKind → AutoDeny
  - Test 3 (extra): Unknown kind never invokes user card callback
  - Test 4: terminal kind → RenderCard (deferred, not auto-deny), callback invoked
  - Test 5: execute_code kind → RenderCard (deferred), callback invoked
  - Test 6: User selects allow → PermissionOutcome.selected('allow-once') (one-shot)
  - Test 7: User selects reject → PermissionOutcome.selected('reject-once') (one-shot)
  - Test 8: User dismisses card → PermissionOutcome.cancelled()
  - Test 9: Default policy denies all kinds (terminal, execute_code, unknown, null — no UI → safe)
  - Test 10 (extra): Default policy with no callback denies terminal kind
  - Test 11: No-batch negative grep — reads approval_policy.dart source, asserts 'allow-always', 'allow_all', 'allow-all', 'remember', 'batch' are absent
  - Test 12 (extra): assertValidOptionId rejects durable grant option ids (allow-always, allow-all, remember, batch-approve)
  - Test 13: End-to-end escalation approved flow (permission → allow-once → DONE → end_turn)
  - Test 14: End-to-end escalation rejected flow (permission → reject-once → rejection → end_turn)
  - Test 15 (extra): End-to-end unknown-kind escalation flow (permission with mystery_tool → auto-deny → rejection)

## Verification Results

| Check | Result |
|-------|--------|
| `flutter test packages/acp_client/test/approval_policy_test.dart` | exit 0 — 15/15 tests passed |
| `flutter test packages/acp_client/` | exit 0 — 38/38 tests passed (23 original + 15 new) |
| `flutter analyze` (apps/flutter_app) | exit 0 — No issues found |
| `grep -r "allow-always\|allow_all\|batch_approve\|always_allow" lib/` | 0 matches (no batch approval path) |
| `grep -rE "auto.*allow\|autoAllow\|auto_approve" approval_policy.dart` | 0 matches (no auto-approve) |
| `grep -rEi "allow-always\|allow_all\|remember\|batch" approval_policy.dart` | 0 matches (no durable grants) |
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
| approval_policy_test.dart | 15 | unknown→deny (3), terminal/execute_code→card (2), card resolution (3), default policy (2), no-batch grep (2), E2E escalation (3) |
| **Total** | **38** | |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Duplicate constructor in RequestPermissionParams**
- **Found during:** Task 1 (test compilation)
- **Issue:** The edit to add `toolName` to `RequestPermissionParams` created a second constructor instead of modifying the existing one, causing a "already declared in this scope" compilation error.
- **Fix:** Merged the two constructors into a single one with `this.toolName` as an optional named parameter.
- **Files modified:** `acp_types.dart`
- **Commit:** d8c4201

**2. [Rule 1 - Bug] Forbidden strings in doc comments and error messages**
- **Found during:** Task 1 (negative grep test failure)
- **Issue:** The `approval_policy.dart` doc comments and `assertValidOptionId` error message contained the forbidden strings ('allow-always', 'allow-all', 'remember', 'batch') that the negative grep test checks for. The test correctly caught this — the source file must not contain these strings anywhere, including comments.
- **Fix:** Rewrote all doc comments and error messages to use alternative wording ('durable grant', 'multi-use grant', 'multi-grant path') instead of the forbidden strings.
- **Files modified:** `approval_policy.dart`
- **Commit:** d8c4201

### Extra Tests (beyond plan's 10)

The plan specified 10 tests. I implemented 15 tests, adding 5 extra edge-case tests:
- null toolKind → AutoDeny (edge case for the unknown kind state)
- Unknown kind never invokes user card callback (security boundary verification)
- Default policy with no callback denies terminal kind (specific safe-default check)
- assertValidOptionId rejects durable grant option ids (runtime assertion verification)
- End-to-end unknown-kind escalation flow (E2E for the auto-deny path)

These extras strengthen the security boundary testing without deviating from the plan's intent.

## Known Stubs

None — all code is production-quality. The `ApprovalPolicy` class implements the complete three-state approval security boundary with no placeholders or TODOs.

## Threat Flags

All four threats from the plan's threat model are mitigated:

- **T-112-07 (Elevation of Privilege — Unknown kind auto-deny):** MITIGATED — `PermissionKind.fromString` returns `unknown` for null/unrecognized values; `ApprovalPolicy.evaluate` returns `AutoDeny` for unknown kinds; the user card callback is never invoked for unknown kinds (verified by test).
- **T-112-08 (Elevation of Privilege — Batch approval path):** MITIGATED — No method or field produces durable/multi-use grants; `assertValidOptionId` throws for invalid option ids; negative grep test confirms no forbidden strings in source; `ApprovalDecision` sealed class has no `AutoAllow` subtype.
- **T-112-09 (Elevation of Privilege — Default policy when no UI):** MITIGATED — `defaultPolicy` static instance denies all kinds; `ApprovalPolicy` with null `onUserCard` returns `AutoDeny` for all kinds including terminal/execute_code (verified by test).
- **T-112-10 (Tampering — Tool kind inference):** MITIGATED — `PermissionKind.fromString` validates kind against known set (terminal, execute_code); unrecognized values default to `unknown` → `AutoDeny`; the kind is not trusted from untrusted model output directly but inferred from approval request context.

## Self-Check: PASSED

All created files exist on disk. All commit hashes verified in git log. All verification checks pass.
