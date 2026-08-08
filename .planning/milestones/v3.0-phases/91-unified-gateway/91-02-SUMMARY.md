---
phase: 91-unified-gateway
plan: 02
subsystem: gateway
tags: [sse, last-event-id, reconnection, seq-replay, event-buffer]
requires:
  - phase: 91-01
    provides: Gateway scaffold + SSE encoding (GatewayApp, GatewaySseStream, parse_last_event_id)
provides:
  - gateway.event_buffer.RunEventBuffer (in-memory per-run event buffer with seq-based replay)
  - gateway.event_buffer.BufferedEvent (RunEvent wrapper with buffer metadata)
  - Last-Event-ID reconnection in GatewayApp.stream (replay + continue streaming)
  - Event buffer integration with output boundary (replayed events go through boundary)
  - Terminal state detection (run.state_changed with succeeded/failed/cancelled)
  - Buffer cleanup (FIFO eviction, terminal retention, clear_run)
affects: [91-03, 91-04, 91-05]
key-files:
  - services/gateway/src/gateway/event_buffer.py
  - services/gateway/src/gateway/app.py
  - services/gateway/tests/test_event_buffer.py
  - services/gateway/tests/test_sse_replay.py
  - services/gateway/tests/fixtures/replay_events.json
key-decisions:
  - "In-memory event buffer per run_id (no persistent storage) — sufficient for single-firm scale ≤50 lawyers"
  - "Seq-based replay: events with seq > last_seq are replayed in seq order, no duplicates, no loss"
  - "Buffer size capped at 1000 events per run with FIFO eviction"
  - "Terminal-state runs retain buffer for 5 minutes (300s) before cleanup"
  - "event_buffer parameter is optional in GatewayApp.__init__ — when None, stream behaves identically to Plan 91-01"
  - "Replayed events go through the same output boundary as live events (second enforcement point)"
  - "OnceRuntime test pattern: yields events only on first stream() call to simulate real reconnection behavior"
patterns-established:
  - "Seq-based reconnection: Last-Event-ID header → replay events with seq > last_seq → continue streaming"
  - "Thread-safe in-memory buffering with threading.Lock for concurrent SSE connections"
  - "Terminal state detection via event_type + payload status check"
  - "FIFO eviction for bounded event buffers"
  - "Optional dependency injection: event_buffer=None preserves backward compatibility"
requirements-completed: [GW-02]
coverage: 74 tests (46 existing + 14 event_buffer + 14 sse_replay)
duration: ~1.5h
completed: 2026-08-07
status: complete
---

# Plan 91-02 Summary — SSE Last-Event-ID Replay

## What Was Done

Implemented SSE Last-Event-ID reconnection for the Gateway: when a client disconnects from a `GET /v1/runs/{id}/events` SSE stream and reconnects with a `Last-Event-ID` header, the Gateway replays all events with `seq > last_event_id` from an in-memory per-run event buffer, then continues streaming new events. This satisfies GW-02: "SSE 流式传输统一事件，支持 Last-Event-ID 按 seq 断线续传，不重复不丢失".

### Tasks Completed (4/4)

| Task | Description | Commit |
|------|-------------|--------|
| 91-02-01 | Create event_buffer.py — in-memory per-run event buffer with seq-based replay | `e67e02f` |
| 91-02-02 | Integrate event buffer into app.py stream handler — Last-Event-ID replay on reconnection | `e2cf9d5` |
| 91-02-03 | Create test_event_buffer.py — 14 unit tests for RunEventBuffer | `90cbb72` |
| 91-02-04 | Create test_sse_replay.py and replay fixtures — 14 integration tests for Last-Event-ID reconnection | `adc9675` |

### Key Decisions

1. **In-memory event buffer per run_id**: No persistent storage, no external dependencies. Sufficient for single-firm scale (≤50 lawyers) per Key Decision #4 in the Phase 91 context. The buffer stores events per `run_id` with their `seq` numbers.

2. **Seq-based replay**: On reconnection with `Last-Event-ID`, the Gateway calls `replay(run_id, last_seq)` which returns events with `seq > last_seq`, ordered by `seq` ascending. No duplicates (no event with `seq <= last_seq` is replayed), no loss (all events with `seq > last_seq` are present).

3. **Optional event_buffer parameter**: `GatewayApp.__init__` accepts `event_buffer: RunEventBuffer | None = None`. When `None`, the stream method behaves identically to Plan 91-01 (no replay, no buffering). This preserves backward compatibility — all 46 existing tests pass without modification.

4. **Output boundary on replay**: Replayed events go through `GatewaySseStream.encode_event()` with the output boundary applied, just like live events. Events blocked by the boundary are skipped during replay (verified by `test_replay_applies_output_boundary`).

5. **Buffer lifecycle**: Buffer size capped at 1000 events per run with FIFO eviction. Terminal-state runs (detected via `run.state_changed` with status `succeeded`/`failed`/`cancelled`) retain their buffer for 5 minutes (300 seconds) before cleanup. `clear_run()` provides explicit cleanup for cancelled runs.

6. **OnceRuntime test pattern**: The `OnceRuntime` fake yields events only on the first `stream()` call, simulating real behavior where a runtime only produces new events after the initial stream is consumed. This lets integration tests verify that reconnection gets replayed events from the buffer (not re-yielded from the runtime).

### Test Coverage

- **test_event_buffer.py**: 14 tests (append/replay, seq ordering, last_seq filtering, empty buffer, FIFO eviction, terminal detection, non-terminal, cleanup expired, cleanup not expired, clear_run, multiple runs isolation, thread safety, no duplicates, get_buffered_events)
- **test_sse_replay.py**: 14 tests (stream without Last-Event-ID, reconnect with Last-Event-ID, Last-Event-ID:0, beyond buffer, no duplicates, no loss, seq order, output boundary, replay then continue, terminal retention, format match, event ID match, no regression tracer, buffer cleanup on cancel)
- **Total**: 74 tests (46 existing + 28 new), all passing

### Gate Status

- 31 gates total (30 existing + 1 gateway gate from Plan 91-01)
- All gates green
- Gateway gate runs `python -m unittest discover -s services/gateway/tests` — 74 tests pass

### Requirements Progress

- **GW-02** (complete): SSE Last-Event-ID reconnection with seq-based replay, no duplicates, no loss. In-memory event buffer per run_id. Integration tests verify reconnection scenarios.

## Self-Check: PASSED

- [x] All tasks executed and committed (4/4)
- [x] All acceptance_criteria PASS
- [x] In-memory event buffer per run_id (RunEventBuffer in event_buffer.py)
- [x] Last-Event-ID header parsing (parse_last_event_id in sse.py, used in app.py stream)
- [x] Seq-based replay (no duplicates, no loss — verified by 14 integration tests)
- [x] Integration test for reconnection scenario (test_sse_replay.py with 14 tests)
- [x] All tests pass (74 tests: 46 existing + 28 new)
- [x] 31 gates green
- [x] SUMMARY.md with Self-Check: PASSED
- [x] GW-02 marked complete in REQUIREMENTS.md
