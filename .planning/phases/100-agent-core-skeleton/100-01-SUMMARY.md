# Summary: Plan 100-01 — Agent Core Scaffold + EventEmitter + Config + Gate

**Plan**: 100-01
**Phase**: 100 — Agent Core Skeleton
**Wave**: 1 (no dependencies)
**Status**: COMPLETE
**Date**: 2026-08-11

## What Was Done

Plan 100-01 created the foundation for the InkStatute self-built Python agent core:

1. **Package scaffold** (`packages/agent-core/`) — pyproject.toml with `name="inkstatute-agent-core"`, `dependencies=[]`, src/inkstatute_agent_core/ with `__init__.py`, `model/` and `tools/` sub-packages (empty stubs for Phase 101), and `tests/` with `fixtures/`.

2. **AgentCoreConfig** (`config.py`) — frozen dataclass with all configurable parameters:
   - `max_turns=10` (matching Rust `MAX_TOOL_ROUNDS`)
   - `silence_threshold_seconds=5.0` (new in Python port — fixes "整轮静默" defect)
   - `response_max_tokens=8192` (matching Rust `RESPONSE_MAX_TOKENS`)
   - `temperature=0.3` (matching Rust default)
   - `context_budget_tokens=32768`, `chars_per_token=4`, `heartbeat_metadata_key="heartbeat"`
   - `__post_init__` validates `max_turns >= 1` and `silence_threshold_seconds > 0`

3. **EventEmitter** (`event_emitter.py`) — core event infrastructure:
   - Monotonic `seq` numbering starting from 0 (for SSE replay / Last-Event-ID)
   - Silence threshold tracking with injectable `monotonic_clock`
   - `maybe_heartbeat()` emits `thought.delta` with `metadata={"heartbeat": true}` when silence exceeds threshold
   - Injectable `clock` (ISO timestamps) and `monotonic_clock` for deterministic testing
   - Convenience methods: `emit_message_delta`, `emit_message_completed`, `emit_thought_delta`, `emit_tool_call_started/delta/completed`, `emit_phase_changed`, `emit_run_state_changed`, `emit_error`
   - Builds `RunEvent` objects with UUID `event_id`, serialized payloads via `serialize_payload()`

4. **Gate registration** (37 → 38 gates):
   - Added `agent_core_src` path variable in `scripts/run_v2_gates.py`
   - Added `Gate("agent-core", ...)` with PYTHONPATH: `agent_core_src`, `platform_src`, `platform_runtime_src`, `model_gateway_src`
   - Added `packages/agent-core/src` to compileall paths
   - Updated `test_audit_v2_requirements.py`: gate count 37 → 38, added `agent-core` assertion
   - Renamed `test_gate_count_is_37` → `test_gate_count_is_38` in `test_integration.py`

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 100-01-01 | Package scaffold (pyproject.toml, src, tests, __init__) | `7491e91` | PASS |
| 100-01-02 | AgentCoreConfig frozen dataclass | `74b9f66` | PASS |
| 100-01-03 | EventEmitter with monotonic seq + silence threshold + heartbeat | `40c92c0` | PASS |
| 100-01-04 | Gate registration (37 → 38) | `4156cdc` | PASS |
| 100-01-05 | Verify all 38 gates green + gate-coverage meta-test | (verification only) | PASS |

## Files Created

- `packages/agent-core/pyproject.toml`
- `packages/agent-core/src/inkstatute_agent_core/__init__.py`
- `packages/agent-core/src/inkstatute_agent_core/config.py`
- `packages/agent-core/src/inkstatute_agent_core/event_emitter.py`
- `packages/agent-core/src/inkstatute_agent_core/model/__init__.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/__init__.py`
- `packages/agent-core/tests/__init__.py`
- `packages/agent-core/tests/fixtures/__init__.py`
- `packages/agent-core/tests/test_config.py`
- `packages/agent-core/tests/test_event_emitter.py`

## Files Modified

- `scripts/run_v2_gates.py` — added `agent_core_src` path, `Gate("agent-core", ...)` entry, compileall path
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — gate count 37 → 38, added `agent-core` assertion
- `services/gateway/tests/test_integration.py` — renamed `test_gate_count_is_37` → `test_gate_count_is_38`, assertion 37 → 38

## Test Results

- **agent-core gate**: 61 tests, all PASS
  - `test_config.py`: 18 tests (defaults, custom values, validation, frozen)
  - `test_event_emitter.py`: 43 tests (seq monotonicity, all convenience methods, heartbeat, injectable clocks, event ordering)
- **Full gate suite**: 38 gates, all green, `"passed": true`
- **gate-coverage-meta-test**: PASS (auto-discovers `packages/agent-core/src`)
- **No regressions**: all 37 pre-existing gates remain green

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] packages/agent-core/ scaffolded
- [x] EventEmitter created (monotonic seq, silence threshold, heartbeat)
- [x] AgentCoreConfig created (max_turns=10, response_max_tokens=8192, temperature=0.3, silence_threshold=5s)
- [x] Gate registered (38 gates green)
- [x] SUMMARY.md with Self-Check: PASSED

## Deviations

None. All tasks completed as specified in the plan with no deviations.

## Notes for Subsequent Plans

- EventEmitter is the foundation — Plans 100-02, 100-03, and 100-04 all import from it
- The `agent-core` gate PYTHONPATH includes `platform_src`, `platform_runtime_src`, and `model_gateway_src` — ready for 100-02 (model layer) and 100-03 (context + turn loop)
- The `model/` and `tools/` sub-packages are empty stubs, ready for population in 100-02 and Phase 101 respectively
- `tests/fixtures/` is ready for turn scripts in 100-04
