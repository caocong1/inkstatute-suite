---
phase: 109-arena-service
plan: 03
status: complete
requirements: [SVC-04, SVC-05]
---

# Plan 03: Output Boundary Enforcement + Permission Security - Summary

## Objective

Wire the ACP output filter into the arena service as the second enforcement layer (SVC-04), ensuring meta/gateway/system noise never reaches the desktop client. Implement permission security verification (SVC-05) that confirms `_DANGEROUS_PERMISSION_KINDS` is preserved, dangerous kinds are immediately rejected, and no batch approve path exists in the arena service.

## Tasks Completed

### Task 1: output_boundary.py — Wire ACPOutputFilter as second enforcement layer (SVC-04)

**Files created:**
- `services/arena-service/src/arena_service/output_boundary.py` — `ArenaOutputBoundary` class
- `services/arena-service/tests/test_output_boundary.py` — 19 tests (all passing)

**Files modified:**
- `services/arena-service/src/arena_service/__init__.py` — re-exports `ArenaOutputBoundary`

**Key implementation details:**
- `ArenaOutputBoundary` wraps `ACPOutputFilter` (layer 1: ACP pre-filter) and `DefaultAssistantOutputBoundary` (layer 2: content-based checks)
- Two-layer enforcement: ACP pre-filter runs first; if BLOCK or REWRITE, short-circuits (second layer not called). If ALLOW, the `DefaultAssistantOutputBoundary` is applied.
- All 8 blocked content categories tested: meta, gateway, system, update, command, help, available_commands_update, terminal
- Unknown event types are default-denied (blocked) — only `ACP_ALLOWED_EVENT_TYPES` pass through
- `apply_to_sse_event` integrates with `ArenaSseStream` — blocked events return `None` from `encode_event`
- `should_send` helper returns `True` for non-BLOCK decisions

**Commit:** `feat(109-03): wire ACPOutputFilter as second enforcement layer (SVC-04)`

### Task 2: permission_safety.py — Verify dangerous kinds preserved + no batch approve (SVC-05)

**Files created:**
- `services/arena-service/src/arena_service/permission_safety.py` — 6 public functions
- `services/arena-service/tests/test_permission_safety.py` — 14 tests (all passing)

**Files modified:**
- `services/arena-service/src/arena_service/__init__.py` — re-exports permission safety functions

**Key implementation details:**
- `_DANGEROUS_PERMISSION_KINDS` is imported from `inkstatute_acp_client.adapter` — NOT redefined (single source of truth)
- `get_dangerous_kinds()` returns the canonical `frozenset({"terminal", "execute_code"})` — verified as the same object via `assertIs`
- `is_dangerous_kind()` correctly identifies `terminal` and `execute_code` as dangerous; `read_file` and `web_search` as safe
- `check_no_batch_approve(ArenaServiceApp)` inspects `OPERATIONS` tuple and class methods — no batch/bulk approve exists
- `check_no_auto_approve_dangerous(app_module)` scans arena_service source files for auto-approval patterns (`auto_approve`, `allow_once`, direct approval of dangerous kinds) — none found
- `check_permission_request_forwarding(app)` verifies no `auto_approve` method exists and the app delegates to an engine
- `simulate_approval(adapter, run_id, kind, decision)` exercises the adapter's `submit_approval()` — `terminal` kind is rejected (run → `WAITING_FOR_USER`), `read_file` kind is approved normally
- `_DANGEROUS_PERMISSION_KINDS` preserved as-is: `frozenset({"terminal", "execute_code"})`

**Commit:** `feat(109-03): verify dangerous kinds preserved + no batch approve (SVC-05)`

## Verification Results

### Task 1 verify (output boundary):
```
Ran 19 tests in 0.001s
OK
```

### Task 2 verify (permission safety + output boundary):
```
Ran 14 tests in 0.010s  (permission safety)
OK

Ran 19 tests in 0.001s  (output boundary)
OK
```

**Total: 33 tests, all passing.**

## Must-Haves Verification

### Truths
- ✅ `ArenaOutputBoundary` enforces the same ACP output filter as Gateway — meta/gateway/system/update/command/help/available_commands_update/terminal noise NEVER reaches the client
- ✅ Unknown event types are default-denied (blocked) — only `ACP_ALLOWED_EVENT_TYPES` pass through
- ✅ Two-layer enforcement: ACP pre-filter (first) + DefaultAssistantOutputBoundary (second)
- ✅ `_DANGEROUS_PERMISSION_KINDS` is imported from `inkstatute_acp_client.adapter` — NOT redefined, preserved as `frozenset({"terminal", "execute_code"})`
- ✅ No batch approve endpoint exists in the arena service — approvals are processed one at a time
- ✅ `terminal` and `execute_code` permissions are immediately rejected when `decision="approved"` — they cannot be auto-approved
- ✅ Non-dangerous permissions (read_file, web_search, etc.) are approved normally through `submit_approval()`

### Artifacts
- ✅ `arena_service.output_boundary.ArenaOutputBoundary`
- ✅ `arena_service.permission_safety.get_dangerous_kinds`
- ✅ `arena_service.permission_safety.is_dangerous_kind`
- ✅ `arena_service.permission_safety.check_no_batch_approve`
- ✅ `arena_service.permission_safety.check_no_auto_approve_dangerous`
- ✅ `arena_service.permission_safety.simulate_approval`
- ✅ `tests/test_output_boundary.py::OutputBoundaryTests`
- ✅ `tests/test_permission_safety.py::PermissionSafetyTests`

### Key Links
- `ArenaOutputBoundary` is ready to be injected into `ArenaSseStream` as the `output_filter` parameter (wired in Plan 05)
- `permission_safety` module imports `_DANGEROUS_PERMISSION_KINDS` from `inkstatute_acp_client.adapter` — single source of truth
- `check_no_batch_approve` and `check_no_auto_approve_dangerous` will be used in GATE-05 tests (Plan 06)
- `simulate_approval` test helper exercises the adapter's existing rejection logic (adapter.py lines 395-436)
