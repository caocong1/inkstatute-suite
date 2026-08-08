---
phase: 109-arena-service
plan: 02
status: complete
requirements: [SVC-03, SVC-07]
---

# Plan 02: SSE Multiplexing + Event Buffer for Reconnection - Summary

## Objective

Created `ArenaSseStream` (SSE encoding with N-agent multiplexing on a single connection, each event tagged with `metadata.agent_slot`) and `ArenaEventBuffer` (in-memory per-arena event buffer with seq-based replay for SSE reconnection). The multiplexing reuses the Gateway's `encode_sse_event` pattern but adds arena-specific event framing. The buffer mirrors `RunEventBuffer` but is keyed by `arena_id` instead of `run_id`.

## Tasks Completed

### Task 1: sse.py — ArenaSseStream with multiplexing + agent_slot tagging

**Files created:**
- `services/arena-service/src/arena_service/sse.py` — `ArenaSseStream`, `encode_arena_sse_event`, `parse_last_event_id`
- `services/arena-service/tests/test_sse_multiplexing.py` — `SSEMultiplexingTests` (14 tests)

**Key implementation details:**
- `encode_arena_sse_event(event)` serializes the full event dict (including `metadata` with `agent_slot`) as JSON with `ensure_ascii=False, sort_keys=True, separators=(",", ":")` and produces an SSE frame `id: {event_id}\nevent: {event_type}\ndata: {json}\n\n`.
- `ArenaSseStream` accepts an optional output filter (wired in Plan 03 to `ACPOutputFilter`). When provided, `encode_event` calls `filter.filter_event()` before encoding — BLOCK returns `None`, REWRITE replaces content.
- `parse_last_event_id(headers)` performs case-insensitive lookup for `Last-Event-ID` and parses as int, returning `None` on failure.
- Multiplexing is implicit: each event already carries `metadata.agent_slot` (set by the arena engine's `EventEmitter`), so the tag flows through JSON serialization unchanged — no slot-specific logic needed.
- Dependency-free: reimplemented locally (no import from `gateway`).

**Commit:** `feat(109-02): ArenaSseStream with N-agent multiplexing and agent_slot tagging`

### Task 2: event_buffer.py — ArenaEventBuffer with seq-based replay by arena_id

**Files created:**
- `services/arena-service/src/arena_service/event_buffer.py` — `ArenaEventBuffer`, `BufferedArenaEvent`
- `services/arena-service/tests/test_sse_reconnection.py` — `SSEReconnectionTests` (18 tests)

**Key implementation details:**
- `ArenaEventBuffer` is keyed by `arena_id` (not `run_id`) — supports arena-level reconnection.
- `replay(arena_id, last_seq)` returns events with `seq > last_seq` sorted by seq ascending — guarantees NO duplication, NO loss.
- `replay` returns shallow copies (`dict(be.event)`) so callers cannot mutate the buffer's internal state.
- FIFO eviction at `max_events_per_arena` (default 1000) prevents unbounded memory.
- Terminal state detection for `arena.workflow_completed`, `arena.workflow_cancelled`, `arena.workflow_failed` — terminal arenas retained for `terminal_retention_seconds` (default 300s) then cleaned up.
- Thread-safe via `threading.Lock` — verified with concurrent access test (5 threads × 100 events).
- `cleanup_expired(now)` removes terminal arenas past retention period; non-terminal arenas are never cleaned up by expiry.
- `clear_arena(arena_id)` removes a specific arena's buffer.

**Commit:** `feat(109-02): ArenaEventBuffer with seq-based replay by arena_id for SSE reconnection`

## Verification

All 32 tests pass:
```
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH=services/arena-service/src:packages/platform-contract/src:packages/platform-runtime/src:packages/arena-engine/src python -m unittest discover -s services/arena-service/tests -p "test_sse_*.py" -v
```

- `test_sse_multiplexing.py::SSEMultiplexingTests` — 14 tests (SVC-03)
- `test_sse_reconnection.py::SSEReconnectionTests` — 18 tests (SVC-07)

## Artifacts Produced

- `arena_service.sse.ArenaSseStream` — SSE encoder with agent_slot multiplexing and optional output filter
- `arena_service.sse.encode_arena_sse_event` — standalone SSE frame encoder
- `arena_service.sse.parse_last_event_id` — Last-Event-ID header parser for reconnection
- `arena_service.event_buffer.ArenaEventBuffer` — per-arena in-memory event buffer with seq-based replay
- `arena_service.event_buffer.BufferedArenaEvent` — dataclass wrapping buffered events with timestamp
- `tests/test_sse_multiplexing.py::SSEMultiplexingTests` — SVC-03 multiplexing and agent_slot tagging tests
- `tests/test_sse_reconnection.py::SSEReconnectionTests` — SVC-07 reconnection and seq-based replay tests

## Key Links

- `ArenaSseStream` will be used by `ArenaServiceApp.stream()` (Plan 05) to encode SSE frames for the multiplexed stream
- `ArenaEventBuffer` will be used by `ArenaServiceApp.stream()` (Plan 05) to buffer events and replay on reconnection
- `ArenaSseStream`'s optional output filter will be wired to `ACPOutputFilter` in Plan 03
- Events arrive from `ArenaEngine`'s `EventEmitter` protocol (mode1.py, mode2.py) already tagged with `metadata.agent_slot`

## Notes

- Plan 109-01 ran in parallel and created the package scaffold (pyproject.toml, __init__.py, config.py, auth.py, app.py, openapi.py). The `__init__.py` was updated to add re-exports for `sse` and `event_buffer` modules without removing Plan 01's existing re-exports.
- The `replay` method returns shallow copies of event dicts to prevent callers from mutating the buffer's internal state — this was caught and fixed during testing.
