---
phase: 109-arena-service
plan: 05
status: complete
requirements: [SVC-01, SVC-02, SVC-03, SVC-04, SVC-06, SVC-07, SVC-08]
---

# Plan 05: Engine Integration — Wire ArenaEngine to ArenaServiceApp - Summary

## Objective

Wire `ArenaEngine` to `ArenaServiceApp` via `ArenaEventEmitter` (implements the engine's `EventEmitter` protocol, forwards events to the SSE stream + event buffer). Integrate `ArenaOutputBoundary` into `ArenaSseStream`, `SubprocessController` for per-run timeout + cleanup, and `StaggeredStartupSemaphore` for initialize limiting. Implement the `stream()` method for SSE multiplexing with reconnection support. End-to-end tests verify the full create → stream → cancel → status flow.

## Tasks Completed

### Task 1: engine_integration.py — ArenaEventEmitter + wire all components together

**Files created/modified:**
- `services/arena-service/src/arena_service/engine_integration.py` (new)
- `services/arena-service/src/arena_service/app.py` (updated)
- `services/arena-service/src/arena_service/__init__.py` (updated)
- `services/arena-service/tests/test_engine_integration.py` (new)
- `services/arena-service/tests/test_endpoints.py` (updated MockEngine to async interface)

**Key changes:**
- `ArenaEventEmitter` — implements the `EventEmitter` protocol from `arena_engine.mode1`, forwards events to `ArenaEventBuffer` (for reconnection replay) and `asyncio.Queue` (for live SSE streaming) with monotonically increasing seq numbers per arena
- `ArenaServiceEngine` — integration wiring layer composing `ArenaEngine` + `ArenaEventBuffer` + `ArenaSseStream` + `ArenaOutputBoundary` + `SubprocessController` + `StaggeredStartupSemaphore`
- `_StaggeredAdapter` — wraps a `BackendAdapter` with staggered startup on `submit_run` via `__getattr__` delegation
- `ArenaServiceApp` handlers updated to delegate to `ArenaServiceEngine` async methods (`create_arena`, `cancel_arena`, `user_action`, `status_arena`) with `inspect.isawaitable` for backward compatibility
- `ArenaServiceApp.stream()` — async generator for SSE multiplexing with localhost + auth checks before yielding any frames, `Last-Event-ID` header parsing for reconnection
- `SubprocessController` cleanup callback wired to `engine.cancel()` — per-run timeout triggers arena cancellation (SVC-06)
- `StaggeredStartupSemaphore` wraps `adapter.submit_run()` via `_StaggeredAdapter` — limits concurrent initializations (SVC-08)
- `ArenaOutputBoundary` wired into `ArenaSseStream` — meta/gateway/system noise dropped from SSE (SVC-04)
- 16 behavior tests covering all 13 behaviors from the plan

### Task 2: End-to-end integration test — create → stream → cancel → status

**Files modified:**
- `services/arena-service/tests/test_engine_integration.py` (added 10 e2e tests)
- `services/arena-service/src/arena_service/engine_integration.py` (fixes for reconnection dedup + timeout enforcement)

**Key changes:**
- 10 e2e tests in `EngineE2ETests` class covering all SVC requirements:
  1. Full Mode 1 flow with 2 mock agents → stream → verify agent_slot tags
  2. Cancel flow → status 'cancelled' → stream ends gracefully
  3. User action (stop) → status changes to 'stopped'
  4. SSE reconnection with Last-Event-ID → no duplication, no loss
  5. Output boundary blocks 'meta: internal' content from SSE stream
  6. Subprocess timeout with hanging adapter → arena cancelled
  7. Staggered startup with 4 agents and max_concurrent=2
  8. Auth enforcement on all 4 endpoints + stream (401)
  9. Localhost enforcement (403 forbidden_remote)
  10. Multiple concurrent arenas isolated by arena_id in event buffer

- Fix `stream_arena` reconnection: skip queued events with `seq <= max_replayed_seq` to prevent duplication when reconnecting after run has buffered events
- Fix `run_arena_background`: call `engine._run_arena()` directly instead of `engine.run()` because the latter catches `CancelledError`, preventing `asyncio.wait_for` from enforcing the per-run timeout (SVC-06)
- `HangingAdapter` and `MetaContentAdapter` test helpers
- `V3MockAdapter` subclass that maps V2 event types to V3 (passes ACP output boundary allowlist)

## Verification

```
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH=services/arena-service/src:packages/acp-event-bridge/src:packages/acp-client/src:packages/arena-engine/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/arena-service/tests -p "test_engine_integration.py" -v
```

Result: **26 tests pass, 0 failures** (16 behavior tests + 10 e2e tests)

Full suite: **163 tests pass, 0 failures** (all existing tests + new tests)

## Artifacts Produced

- `arena_service.engine_integration.ArenaEventEmitter` — EventEmitter protocol implementation forwarding to buffer + SSE queue with seq numbers
- `arena_service.engine_integration.ArenaServiceEngine` — integration layer wiring all components together
- `arena_service.engine_integration._StaggeredAdapter` — wraps BackendAdapter with staggered startup on submit_run
- `arena_service.app.ArenaServiceApp` (updated) — full handler implementations + `stream()` method
- `tests/test_engine_integration.py` — 26 tests covering all 13 behaviors + 10 e2e flows

## Key Design Decisions

1. **`_run_arena` direct call**: `run_arena_background` calls `engine._run_arena()` directly instead of `engine.run()` because the latter catches `CancelledError`, which prevents `asyncio.wait_for` from enforcing the per-run timeout. This is documented in the method's docstring.

2. **Reconnection dedup**: `stream_arena` tracks `max_replayed_seq` and skips queued events with `seq <= max_replayed_seq` to prevent duplication when a client reconnects after the run has already buffered events.

3. **`inspect.isawaitable`**: App handlers use `inspect.isawaitable` to support both sync and async engine methods, ensuring backward compatibility with existing test mocks.

4. **`V3MockAdapter`**: Test helper that maps V2 event types (`message_delta`) to V3 (`message.delta`) so events pass the ACP output boundary allowlist during testing.

5. **Adapter factory pattern**: `ArenaServiceEngine` accepts an optional `adapter_factory` callable that creates adapters per slot, enabling automatic background run startup on arena creation.
