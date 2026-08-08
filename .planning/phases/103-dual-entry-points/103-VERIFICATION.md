---
phase: 103-dual-entry-points
verified: 2026-08-08T14:30:00.000Z
status: passed
score: 14/14 must-haves verified
behavior_unverified: 0
---

# Phase 103: Dual Entry Points Verification Report

**Phase Goal:** 自研核心以一份实现提供两个入口，并在架构上与其他后端完全平等——换 `backend_id` 不需要改任何通道层或 UI 代码
**Verified:** 2026-08-08T14:30:00.000Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | InProcessAgentCoreAdapter implements all 9 BackendAdapter methods | ✓ VERIFIED | test_backend_adapter.py: 23 tests covering all 9 methods |
| 2 | backend_id() returns "inkstatute" | ✓ VERIFIED | test_backend_id_returns_inkstatute |
| 3 | capabilities() declares streaming/cancel/approval but NOT fs/* or terminal/* | ✓ VERIFIED | test_capabilities_declares_streaming_cancel_approval, test_capabilities_does_not_declare_fs_or_terminal |
| 4 | submit_run() starts run_turn() as background task and returns RunHandle | ✓ VERIFIED | test_submit_run_returns_handle_with_running_status |
| 5 | stream_events() yields RunEvent objects in seq order until terminal state | ✓ VERIFIED | test_stream_events_yields_message_delta, test_stream_events_completes_with_terminal_state |
| 6 | cancel_run() cancels background task and emits run.state_changed | ✓ VERIFIED | test_cancel_run_emits_state_changed (W-1 fix applied) |
| 7 | submit_approval() rejects terminal and execute_code permissions | ✓ VERIFIED | test_submit_approval_rejects_terminal, test_submit_approval_rejects_execute_code |
| 8 | ACP server responds to initialize with protocolVersion 1 | ✓ VERIFIED | test_initialize_responds_with_protocol_version_1 |
| 9 | ACP server does NOT declare fs/* or terminal/* capabilities | ✓ VERIFIED | test_initialize_does_not_declare_fs, test_initialize_does_not_declare_terminal |
| 10 | inkstatute-agent acp --check works | ✓ VERIFIED | test_check_flag_exits_zero_when_ok, test_check_flag_exits_nonzero_when_provider_unavailable |
| 11 | Both entry points share same run_turn() implementation — no duplicate logic | ✓ VERIFIED | test_both_entry_points_share_run_turn (static import check) |
| 12 | Both entry points produce same event type sequence for same input | ✓ VERIFIED | test_event_type_sequence_matches_between_entry_points |
| 13 | Backend selection is configurable via operator-config | ✓ VERIFIED | test_default_backend_id_is_inkstatute, test_tenant_override_takes_precedence |
| 14 | Backend interchangeability: same task via hermes and inkstatute, same event shape | ✓ VERIFIED | test_backend_interchangeability_hermes_vs_inkstatute |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| packages/agent-core/src/inkstatute_agent_core/backend_adapter.py | InProcessAgentCoreAdapter | ✓ EXISTS + SUBSTANTIVE | 549 lines, all 9 BackendAdapter methods |
| packages/agent-core/src/inkstatute_agent_core/backend_config.py | AgentCoreBackendConfig | ✓ EXISTS + SUBSTANTIVE | Config dataclass with provider_factory |
| packages/agent-core/src/inkstatute_agent_core/acp_server.py | ACP server protocol handler | ✓ EXISTS + SUBSTANTIVE | 591 lines, JSON-RPC handler + reverse event mapping |
| packages/agent-core/src/inkstatute_agent_core/__main__.py | CLI entry point | ✓ EXISTS + SUBSTANTIVE | argparse with acp subcommand + --check |
| packages/agent-core/pyproject.toml (modified) | Entry point script | ✓ EXISTS + SUBSTANTIVE | [project.scripts] added |
| packages/operator-config/src/inkstatute_operator_config/backend_selection.py | Backend selection resolver | ✓ EXISTS + SUBSTANTIVE | BackendSelectionDoc + resolve_backend_id() |

**Artifacts:** 6/6 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| backend_adapter.py | turn_loop.py | run_turn() import | ✓ WIRED | Background task calls run_turn() |
| backend_adapter.py | prompt_assembler.py | build_system_prompt() import | ✓ WIRED | System prompt uses Phase 102 assembler (W-7 fix) |
| acp_server.py | turn_loop.py | run_turn() import | ✓ WIRED | ACP server calls run_turn() |
| acp_server.py | prompt_assembler.py | build_system_prompt() import | ✓ WIRED | System prompt assembled |
| __main__.py | acp_server.py | ACPServer import | ✓ WIRED | CLI dispatches to ACPServer |
| backend_selection.py | store.py | ConfigStore import | ✓ WIRED | Load backend selection from store |

**Wiring:** 6/6 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| CORE-10: 双入口（in-process BackendAdapter + inkstatute-agent acp） | ✓ SATISFIED | - |

**Coverage:** 1/1 requirements satisfied

## Success Criteria Coverage

| SC | Description | Status | Evidence |
|----|-------------|--------|----------|
| SC-1 | in-process 入口实现 BackendAdapter 9 方法 | ✓ VERIFIED | InProcessAgentCoreAdapter + 23 tests |
| SC-2 | ACP 入口可启动，--check 通过，可被 ACP client 驱动 | ✓ VERIFIED | ACPServer + 35 tests + ACPClient integration |
| SC-3 | 两个入口共享同一份核心实现，无重复逻辑 | ✓ VERIFIED | Both import run_turn from turn_loop.py |
| SC-4 | 后端可替换性验收通过 | ✓ VERIFIED | test_backend_interchangeability_hermes_vs_inkstatute |
| SC-5 | ACP 入口正确声明能力，不声明 fs/terminal | ✓ VERIFIED | test_initialize_does_not_declare_fs/terminal |
| SC-6 | 后端选择可经 operator-config 配置 | ✓ VERIFIED | BackendSelectionDoc + resolve_backend_id() |

**SC Coverage:** 6/6 verified

## Code Review Results

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | - |
| Warning | 8 | 2 fixed (W-1 sentinel race, W-7 system prompt parity), 6 acknowledged (non-blocking) |
| Info | 6 | Acknowledged |

## Test Summary

| Metric | Value |
|--------|-------|
| Existing tests (pre-phase) | 785 |
| New tests (Phase 103) | 94 (23 + 35 + 36) |
| Total tests | 879 passed, 5 skipped |
| Pass rate | 100% (0 failed) |
| Subtests | 27 passed |
| V2 gates | All green |
| New pip dependencies | 0 |

## Conclusion

Phase 103 is complete. The self-built Python agent core now has dual entry points — in-process `InProcessAgentCoreAdapter` and `inkstatute-agent acp` CLI — both sharing the same `run_turn()` implementation with no duplicate logic. Backend selection is configurable via operator-config. The two code review fixes (sentinel race and system prompt parity) ensure correctness and architectural equality. All 6 success criteria verified.
