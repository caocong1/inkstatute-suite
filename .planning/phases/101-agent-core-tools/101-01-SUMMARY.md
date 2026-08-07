# Summary: Plan 101-01 — Tool Registry + EventEmitter Extensions + Clarification Tool

**Phase**: 101 (agent-core-tools)
**Plan**: 101-01
**Wave**: 1 (no dependencies)
**Requirements**: CORE-02 (partial — tool registry + clarification tool + EventEmitter extensions)
**Status**: COMPLETE
**Date**: 2026-08-11

## What Was Built

### 1. ToolRegistry + Dispatching ToolExecutor (Task 101-01-01)
- **`packages/agent-core/src/inkstatute_agent_core/tools/registry.py`** — `ToolRegistry` class mapping tool names to `ToolHandler` callables. Methods: `register()`, `register_definition()`, `get_handler()`, `get_tool_definitions()`, `has_tool()`. Stores OpenAI function-calling format definitions.
- **`packages/agent-core/src/inkstatute_agent_core/tools/executor.py`** — `create_dispatching_executor(registry)` factory that returns a `ToolExecutor` callable. Dispatches to registry handlers, catches unknown tools (returns `ToolResult` with `ErrorInfo`), catches handler exceptions as secondary safety net.
- **`packages/agent-core/src/inkstatute_agent_core/tools/__init__.py`** — Updated to re-export `ToolRegistry`, `ToolHandler`, `create_dispatching_executor`.
- **`packages/agent-core/tests/test_tool_registry.py`** — 17 tests covering registration, lookup, definitions, dispatching (success, unknown tool, handler exception).

### 2. EventEmitter Extensions (Task 101-01-02)
- **`emit_artifact_created(artifact, metadata)`** — Emits `artifact.created` event with `ArtifactCreatedPayload` containing the `Artifact` dataclass.
- **`emit_elicitation_requested(interrupt_id, intro, questions, ...)`** — Emits `elicitation.requested` event with `ElicitationRequestedPayload`.
- **Side-channel event buffer** — `drain_side_channel_events()` method allows the turn loop to yield events emitted by tool handlers (e.g. clarification tool emitting `elicitation.requested`). Both new emit methods add events to the side channel.
- **13 new tests** in `test_event_emitter.py` covering event structure, payload serialization, seq monotonicity, injectable clocks.

### 3. Clarification (ask_user) Tool (Task 101-01-03)
- **`packages/agent-core/src/inkstatute_agent_core/tools/clarification.py`** — `create_clarification_tool(emitter)` factory returning a `ToolHandler`. Parses `intro` + `questions`, validates 2-4 questions via `validate_question_count()`, auto-assigns `q1`/`q2` for empty IDs, auto-fills `value` from `label`, handles free-text questions (no options), generates `interrupt_id` (UUID), emits `elicitation.requested`, returns `ToolResult` with `metadata={"terminate_turn": True, "elicitation_id": ...}`.
- **`CLARIFICATION_TOOL_DEFINITION`** — OpenAI function-calling format dict with `name="ask_user"`, 2-4 question constraint.
- **24 tests** in `test_clarification_tool.py` covering valid/invalid question counts, auto-assigned IDs, auto-filled values, free-text questions, emit event verification, terminate_turn metadata.

### 4. Turn Loop terminate_turn Enhancement (Task 101-01-04)
- **`packages/agent-core/src/inkstatute_agent_core/turn_loop.py`** — After tool execution, checks `result.metadata.get("terminate_turn")`. When set, emits `run.state_changed` with `status="waiting_for_user"` and returns from the generator. Tool result still appended to `current_messages`, `tool_call.completed` emitted with `status="succeeded"`. Backward-compatible: no `terminate_turn` → behavior unchanged. Also drains side-channel events after tool execution.
- **6 new tests** in `test_turn_loop.py` covering terminate_turn=True stops loop, terminate_turn=False continues, multiple tools with one terminate, no tools unchanged, tool result appended, waiting_for_user as last event.

### 5. E2E Integration Test (Task 101-01-05)
- **`packages/agent-core/tests/test_e2e_tool_registry.py`** — 5 e2e tests wiring `ToolRegistry` + `create_dispatching_executor` + `create_clarification_tool` + `run_turn()` with `FixtureProvider`. Verifies: `elicitation.requested` emitted, `tool_call.completed` (succeeded), `run.state_changed` (waiting_for_user), generator stops, no external LLM calls, seq monotonicity, free-text questions.

### 6. All 38 Gates Green (Task 101-01-06)
- `python scripts/run_v2_gates.py` exits 0, `"passed": true`
- agent-core gate: 405 tests (340 original + 65 new)
- No regressions in any pre-existing gate

## Commits

| Hash | Description |
|------|-------------|
| `9ce46ca` | feat(101-01): ToolRegistry + dispatching ToolExecutor |
| `877b386` | feat(101-01): EventEmitter extensions — emit_artifact_created + emit_elicitation_requested |
| `9f57679` | feat(101-01): clarification (ask_user) tool — emits elicitation.requested, terminates turn |
| `234e121` | feat(101-01): turn loop terminate_turn check — emit waiting_for_user on signal |
| `5c844ff` | feat(101-01): e2e integration test + side-channel event buffer |
| `109476d` | test(101-01): all 38 gates green — agent-core 405 tests pass |

## Files Created
- `packages/agent-core/src/inkstatute_agent_core/tools/registry.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/executor.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/clarification.py`
- `packages/agent-core/tests/test_tool_registry.py`
- `packages/agent-core/tests/test_clarification_tool.py`
- `packages/agent-core/tests/test_e2e_tool_registry.py`

## Files Modified
- `packages/agent-core/src/inkstatute_agent_core/tools/__init__.py` (re-exports)
- `packages/agent-core/src/inkstatute_agent_core/event_emitter.py` (additive: 2 new emit methods + side-channel buffer)
- `packages/agent-core/src/inkstatute_agent_core/turn_loop.py` (additive: terminate_turn check + side-channel drain)
- `packages/agent-core/tests/test_event_emitter.py` (additive: 13 new tests)
- `packages/agent-core/tests/test_turn_loop.py` (additive: 6 new tests)

## Test Counts
- test_tool_registry.py: 17 tests
- test_clarification_tool.py: 24 tests
- test_e2e_tool_registry.py: 5 tests
- test_event_emitter.py: 56 tests (43 original + 13 new)
- test_turn_loop.py: 23 tests (17 original + 6 new)
- **Total new tests: 65**
- **Total agent-core tests: 405**

## Design Decisions

### Side-Channel Event Buffer
The clarification tool handler emits `elicitation.requested` via `emitter.emit_elicitation_requested()`, but the turn loop is an async generator that only yields events it directly creates. To bridge this gap, the EventEmitter maintains a `_side_channel_events` list. `emit_elicitation_requested()` and `emit_artifact_created()` add events to this list. The turn loop calls `emitter.drain_side_channel_events()` after tool execution (before `tool_call.completed`) and yields any buffered events. This maintains seq order because the side-channel event is created during tool execution (seq assigned at that point) and yielded before the turn loop emits `tool_call.delta` and `tool_call.completed`.

### Factory Pattern for Clarification Tool
The `ToolHandler` signature is `Callable[[dict], Awaitable[ToolResult]]` — no emitter access. The clarification tool needs an EventEmitter to emit `elicitation.requested`. Solution: `create_clarification_tool(emitter)` is a factory function that captures the emitter in a closure and returns a `ToolHandler`.

### terminate_turn Metadata
The clarification tool returns `ToolResult` with `metadata={"terminate_turn": True, "elicitation_id": ...}`. The turn loop checks this after each tool execution. When set, it emits `run.state_changed(waiting_for_user)` and returns. This is backward-compatible — when no tool uses `terminate_turn`, the loop behavior is unchanged.

## Self-Check: PASSED

- [x] All tasks executed and committed (6/6)
- [x] All acceptance_criteria PASS
- [x] ToolRegistry created (registry.py)
- [x] create_dispatching_executor() created (executor.py)
- [x] emit_artifact_created() added to EventEmitter
- [x] emit_elicitation_requested() added to EventEmitter
- [x] Clarification tool created (ask_user — clarification.py)
- [x] Turn loop enhanced (terminate_turn check)
- [x] All 38 gates green
- [x] SUMMARY.md with Self-Check: PASSED
