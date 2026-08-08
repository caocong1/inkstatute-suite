# Summary: Plan 100-03 — Context Assembler + Turn Loop

**Plan**: 100-03
**Phase**: 100 — Agent Core Skeleton
**Wave**: 2 (depends on 100-01; runs in parallel with 100-02)
**Status**: COMPLETE
**Date**: 2026-08-11

## What Was Done

Plan 100-03 created the context assembler and async turn loop for the InkStatute self-built Python agent core — the core fix for the "整轮静默" (whole-round silence) defect.

1. **AgentContextAssembler** (`context.py`) — combines conversation history trimming (from `context_assembler.py` pattern) with skill body injection (from `body_injector.py` pattern) under a total token budget:
   - `AgentContextPolicy` (frozen dataclass): `budget_tokens=32768`, `chars_per_token=4`, `skill_body_budget_fraction=0.6`, `history_budget_fraction=0.3`, `max_history_turns=20`
   - `AgentContextResult` (frozen dataclass): `messages`, `estimated_tokens`, `dropped_sections`, `trimmed_skill_sections`, `protected_sections`
   - `ContextAssemblyBudgetError`: raised when protected sections alone exceed budget
   - CJK-aware token estimation: CJK chars = 1 token, non-CJK = chars // 4
   - Section-priority trim for skill bodies: Protected (frontmatter + description + first section) → High (research-gate, ask-user) → Medium → Low (example, appendix, reference)
   - History trim: truncate to `max_history_turns`, then drop oldest-first when over budget
   - Deterministic: same input + same budget → same output

2. **Async turn loop** (`turn_loop.py`) — the heart of Phase 100:
   - `run_turn()` async generator yielding `RunEvent` objects
   - **Always streams** — uses `provider.chat_stream()` for every round, even during tool rounds (fixes the Rust original's `stream: false` defect)
   - Emits `phase.changed` at start of each round, `thought.delta` pre-LLM thought
   - `ContentDelta` → `message.delta` events
   - `ReasoningDelta` → `thought.delta` events
   - `ToolCallDelta` → accumulated, then `tool_call.started` before execution, `tool_call.delta` during, `tool_call.completed` after
   - `UsageDelta` → accumulated via `UsageAccumulator` from 100-02
   - `FinishDelta` → notes finish reason
   - **Heartbeat**: `emitter.maybe_heartbeat()` called before LLM call and during tool execution
   - **Turn limit**: `max_turns=10` (configurable); when exceeded, emits `error` with `turn_limit_exceeded` + `run.state_changed` to `failed`
   - **Error recovery**: tool execution exceptions caught → `tool_call.completed` with `status="error"` + `ErrorInfo` → error appended as tool result → loop continues
   - **Provider errors**: `provider.chat_stream()` exceptions → `error` event + `run.state_changed` to `failed`
   - `ToolResult` frozen dataclass: `content`, `error`, `metadata`
   - Uses `LlmProvider` Protocol, `StreamDelta` types, and `FixtureProvider` from 100-02

3. **Message building helpers** (`messages.py`):
   - `build_tool_result_message()`: builds `{"role": "tool", "tool_call_id": ..., "content": ...}`; error results prefixed with `"Error: "`
   - `build_assistant_message()`: builds `{"role": "assistant", "content": ..., "tool_calls": [...]}`; omits `tool_calls` key when None/empty; empty content becomes None
   - `append_tool_results()`: returns a new list (does not mutate input)
   - `extract_tool_calls_from_deltas()`: converts `ToolCallDelta` objects to OpenAI-format tool call dicts

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 100-03-01 | AgentContextAssembler (history trim + skill body injection) | `06f6db9` | PASS |
| 100-03-02 | Async turn loop (always-streaming, tool-call events, heartbeat, error recovery) | `1dcf9bb` | PASS |
| 100-03-03 | Message building helpers (tool results, assistant messages, delta extraction) | `689198e` | PASS |
| 100-03-04 | Verify all gates green + integration | (verification only) | PASS |

## Files Created

- `packages/agent-core/src/inkstatute_agent_core/context.py` — AgentContextAssembler, AgentContextPolicy, AgentContextResult, ContextAssemblyBudgetError
- `packages/agent-core/src/inkstatute_agent_core/turn_loop.py` — run_turn() async generator, ToolResult, ToolExecutor type alias
- `packages/agent-core/src/inkstatute_agent_core/messages.py` — build_tool_result_message, build_assistant_message, append_tool_results, extract_tool_calls_from_deltas
- `packages/agent-core/tests/test_context.py` — 20 tests
- `packages/agent-core/tests/test_turn_loop.py` — 17 tests
- `packages/agent-core/tests/test_messages.py` — 21 tests

## Files Modified

None. All 100-01 files (config.py, event_emitter.py) and 100-02 files (model/provider.py, fixtures.py) were read but not modified, per binding constraints.

## Test Results

- **agent-core gate**: 260 tests, all PASS
  - `test_config.py`: 18 tests (from 100-01)
  - `test_event_emitter.py`: 43 tests (from 100-01)
  - `test_model_provider.py`: ~98 tests (from 100-02)
  - `test_fixture_provider.py`: ~23 tests (from 100-02)
  - `test_context.py`: 20 tests (100-03: no trim, history trim, skill body trim, both trimmed, CJK, protected exceeds budget, determinism, policy override, empty inputs)
  - `test_turn_loop.py`: 17 tests (100-03: single-turn, multi-turn tools, tool failure recovery, turn limit, provider error, heartbeat, usage accumulation, seq monotonicity, always streaming)
  - `test_messages.py`: 21 tests (100-03: tool result, error tool result, assistant with/without tool calls, append, delta extraction, integration)
- **Full gate suite**: 38 gates, all green, exit code 0
- **No regressions**: all 37 pre-existing gates remain green
- **No external dependencies**: `packages/agent-core/pyproject.toml` still has `dependencies = []`

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] AgentContextAssembler created (history trim + skill body injection)
- [x] Async turn loop created (async generator)
- [x] Tool call streaming works (started|delta|completed + heartbeats)
- [x] Error recovery works (tool failures don't crash)
- [x] Turn limit enforced (max_turns=10)
- [x] All 38 gates green
- [x] SUMMARY.md with Self-Check: PASSED

## Deviations

None. All tasks completed as specified in the plan with no deviations.

## Notes for Subsequent Plans

- The turn loop uses `LlmProvider` Protocol, `StreamDelta` types, `UsageAccumulator`, and `FixtureProvider` from 100-02 (which was complete when 100-03 ran)
- The turn loop's internal `_build_tool_result_message()` and `_build_assistant_message_with_tool_calls()` helpers are duplicated from `messages.py` for self-containment; `messages.py` provides the public API for external callers
- The `tool_executor` parameter in `run_turn()` accepts a `Callable[[str, str, dict], Awaitable[ToolResult]]` — Phase 101 will provide real tool implementations
- The `phase` parameter in `run_turn()` defaults to `"research"` but can be set to `"draft"`, `"intake"`, etc. for Phase 102's five-phase progression
- Context assembler's `skill_bodies` parameter expects dicts with `"body"` (SKILL.md text) and optional `"skill_id"` keys — Phase 102 will wire this to the skill index
