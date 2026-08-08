---
phase: 109
slug: arena-service
status: complete
created: 2026-08-09
---

# Phase 109 — Technical Research

## 1. Service Structure

**Findings:**
- Gateway is **stdlib-only** (no aiohttp/FastAPI) — `services/gateway/pyproject.toml` line 15: `dependencies = []`
- `GatewayApp` in `services/gateway/src/gateway/app.py` (lines 122-201)
- Framework-free routing via `_parse_route()` (lines 202-294)
- SSE via `GatewaySseStream` in `services/gateway/src/gateway/sse.py` (lines 72-122)

**Implementation approach:**
- Create `services/arena-service/` mirroring Gateway structure
- Framework-free, stdlib-only HTTP server
- Modules: `app.py`, `auth.py`, `sse.py`, `config.py`, `event_buffer.py`, `openapi.py`
- `ArenaServiceApp` class following `GatewayApp` pattern

## 2. Local Binding + Token Auth (SVC-01)

**Findings:**
- Gateway binding via `GatewayConfig` (config.py lines 18-33)
- `GatewayAuth` in auth.py (lines 49-140) — Bearer token or session cookie
- No localhost check in Gateway — NEW for arena-service

**Implementation approach:**
- `ArenaServiceConfig` with `bind_host: str = "127.0.0.1"`, `bind_port: int = 8001`
- Bind explicitly to 127.0.0.1:8001
- Reject non-localhost: check `client_address[0]` starts with "127." or "::1"
- Token auth: `secrets.token_urlsafe(32)` for local token generation
- `ArenaServiceAuth` class with `require_auth()` method
- All requests require `Authorization: Bearer <token>` header

## 3. Endpoints (SVC-02)

**Findings:**
- Gateway endpoints in app.py (lines 56-95): create_session, create_run, stream_run, etc.
- Routing via `_parse_route()` mapping method+path to operation constants
- OpenAPI in `services/gateway/src/gateway/openapi.py`

**Implementation approach:**
- Arena endpoints:
  - `POST /arena` — create arena
  - `GET /arena/{arena_id}/stream` — SSE stream
  - `POST /arena/{arena_id}/cancel` — cancel arena
  - `POST /arena/{arena_id}/action` — user action (select/stop/pause/resume)
  - `GET /arena/{arena_id}/status` — status query
- Operation constants: `OPERATION_CREATE_ARENA`, `OPERATION_STREAM_ARENA`, etc.
- `_parse_route()` for arena paths
- OpenAPI spec generation following Gateway's `openapi.py` pattern

## 4. SSE Multiplexing (SVC-03)

**Findings:**
- Gateway SSE: single run per connection (`GET /v1/runs/{run_id}/events`)
- Mode 1 already tags events with `agent_slot` (mode1.py lines 162-173)
- EventEmitter protocol (mode1.py lines 50-64) — callback for emitting events

**Implementation approach:**
- SSE endpoint accepts `arena_id` (not run_id)
- `ArenaEventEmitter` implements EventEmitter protocol, forwards to SSE stream
- All arena events already have `metadata.agent_slot` from engine
- Client demultiplexes by filtering on `metadata.agent_slot`
- Reuse `GatewaySseStream.encode_event()` for SSE frame encoding

## 5. Output Boundary (SVC-04)

**Findings:**
- `ACPOutputFilter` in `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/output_filter.py` (lines 206-444)
- Blocks 8 categories: meta:, gateway:, system:, update:, command:, help:, available_commands_update:, terminal:
- Default-deny for unknown event types (lines 110-126)
- Returns `FilterDecision` with action/visible_content/audit_metadata
- Gateway applies `DefaultAssistantOutputBoundary` in sse.py (lines 83-104)

**Implementation approach:**
- Import `ACPOutputFilter` from `inkstatute_acp_event_bridge.output_filter`
- In SSE encoding, call `filter.filter_event()` before `encode_sse_event()`
- Filtered events are dropped (not sent to client)
- Two-layer enforcement: ACP bridge (first) + arena service (second)

## 6. Permission Security (SVC-05)

**Findings:**
- `_DANGEROUS_PERMISSION_KINDS` in `packages/acp-client/src/inkstatute_acp_client/adapter.py` line 115:
  `frozenset({"terminal", "execute_code"})`
- `submit_approval()` (lines 395-436) rejects auto-approval for dangerous kinds
- No batch approve path exists — adapter processes one approval at a time
- Test coverage: `packages/acp-event-bridge/tests/test_permission_safety.py` (15 tests)

**Implementation approach:**
- Arena service does NOT provide batch approval endpoint
- Import `_DANGEROUS_PERMISSION_KINDS` to verify it's preserved
- Permission requests forwarded to adapter's `submit_approval()`
- No code path allows auto-approval of terminal/execute_code
- Test: verify `_DANGEROUS_PERMISSION_KINDS` is unchanged, verify no batch endpoint exists

## 7. Subprocess Control (SVC-06)

**Findings:**
- `ACPBackendAdapter.submit_run()` spawns subprocess (adapter.py lines 260-324)
- Session tracking: `_sessions: dict[str, ACPClient]` (line 150)
- `shutdown()` closes all sessions (lines 452-466)
- `ArenaEngine.cancel()` calls `adapter.cancel_run()` + `adapter.shutdown()` (engine.py lines 133-175)
- `SlotRunner.run_agent_slot()` uses `asyncio.wait_for()` with timeout (slot_runner.py lines 112-121)
- SlotResult with `status="timeout"` or `status="failed"` returns partial content (lines 132-145)

**Implementation approach:**
- Wrap ArenaEngine calls with per-run timeout at service layer
- Liveness check: periodic health check on adapter sessions
- On timeout/crash: call `ArenaEngine.cancel()` to trigger cleanup
- Accept partial results via SlotResult's partial flag
- Track PIDs via adapter session tracking

## 8. SSE Reconnection (SVC-07)

**Findings:**
- `RunEventBuffer` in `services/gateway/src/gateway/event_buffer.py` (lines 47-166)
  - Per-run in-memory buffer with seq-based replay
  - `append()` stores events with `BufferedEvent(event, buffered_at)` (lines 73-88)
  - `replay(run_id, last_seq)` returns events with `seq > last_seq` (lines 90-102)
  - FIFO eviction at `max_events_per_run` (default 1000)
  - Terminal state retention for 300 seconds (lines 117-135)
- `parse_last_event_id()` in sse.py (lines 124-137)
- Gateway `stream()` method (app.py lines 295-343): replay buffered → live stream

**Implementation approach:**
- `ArenaEventBuffer` similar to `RunEventBuffer` but keyed by `arena_id`
- Buffer events with seq tracking
- On reconnection with `Last-Event-ID` header, replay from breakpoint
- Seq-based filtering ensures no dup/loss
- FIFO eviction + terminal state retention

## 9. Staggered Startup (SVC-08)

**Findings:**
- No existing semaphore in Gateway — NEW for arena-service
- Asyncio `Semaphore` pattern for limiting concurrent initializations

**Implementation approach:**
- `asyncio.Semaphore(2)` in ArenaServiceConfig (default 2 concurrent initializations)
- Wrap adapter `submit_run()` calls with semaphore:
  ```python
  async with self._initialize_semaphore:
      await adapter.submit_run(run_request)
  ```
- Prevents N agents calling `initialize()` simultaneously
- Default limit: 2 (configurable)

## 10. Gate Tests (GATE-05, GATE-06)

**Findings:**
- Gate structure: `Gate(name, command, pythonpath)` in `scripts/run_v2_gates.py`
- Current baseline: 36 gates (test_gate_coverage.py line 60)
- Gate coverage meta-test checks all `packages/*/src` and `services/*/src` are covered

**Implementation approach:**
- **GATE-05 (permission safety)**: New gate `"arena-permission-safety"`
  - Command: `python -m unittest discover -s services/arena-service/tests -p "test_permission_safety.py"`
  - Tests: verify `_DANGEROUS_PERMISSION_KINDS` preserved, no batch approve, terminal/execute_code rejected
- **GATE-06 (orphan process)**: New gate `"arena-orphan-process"`
  - Command: `python -m unittest discover -s services/arena-service/tests -p "test_orphan_process.py"`
  - Tests: cancel arena → assert zero PID residue
- Update gate count baseline from 36 to 38 in test_gate_coverage.py
- Add `services/arena-service/src` to compileall gate

## 11. Integration with ArenaEngine

**Findings:**
- `ArenaEngine` in engine.py (lines 52-561)
  - `start()`, `cancel()`, `submit_user_action()`, `query_status()`, `run()`
  - `register_adapters()`, `register_synthesis_adapter()`, `register_adversarial_adapter()`
- EventEmitter protocol (mode1.py lines 50-64)
- Mode dispatch: mode1/mode2/mode3/mode4 based on `config.mode` (engine.py lines 298-403)

**Implementation approach:**
- Arena service instantiates `ArenaEngine` with `storage_dir` for artifacts
- Service-specific `ArenaEventEmitter` forwards to SSE buffer
- Per arena request:
  1. `engine.start(config)` → ArenaHandle
  2. Register adapters per slot
  3. For Mode 3/4: register synthesis/adversarial adapters
  4. `engine.run(arena_id, adapters, event_emitter)` as background task
- User actions → `engine.submit_user_action()`
- Cancel → `engine.cancel()`

## 12. Real Subprocess PID Tracking

**Findings:**
- Phase 107 deferred real PID assertion to Phase 109
- MockACPBackendAdapter has `_sessions: set[str]` (mock_acp.py line 106) — no real PIDs
- ACPBackendAdapter tracks `_sessions: dict[str, ACPClient]` (adapter.py line 150)
- Real PIDs are in `StdioACPTransport` (not exposed to adapter layer)

**Implementation approach:**
- Expose PID tracking from `StdioACPTransport` to `ACPBackendAdapter`
- Add `get_active_pids() -> set[int]` method to ACPBackendAdapter
- Test approach:
  1. Create arena with real ACP adapters (or mock with PID simulation)
  2. Start arena (spawns subprocesses)
  3. Record PIDs before cancel
  4. Call `engine.cancel()`
  5. Assert all recorded PIDs are gone (zero orphans)
- For testing without real subprocesses: mock PID tracking with fake PIDs

## Key Files to Create/Modify

**New files (services/arena-service/):**
1. `pyproject.toml` — package config (dependencies = [])
2. `src/arena_service/__init__.py` — re-exports
3. `src/arena_service/app.py` — ArenaServiceApp (HTTP server + routing)
4. `src/arena_service/auth.py` — ArenaServiceAuth (local token + localhost check)
5. `src/arena_service/config.py` — ArenaServiceConfig
6. `src/arena_service/sse.py` — ArenaSseStream (SSE encoding + multiplexing)
7. `src/arena_service/event_buffer.py` — ArenaEventBuffer (reconnection support)
8. `src/arena_service/openapi.py` — OpenAPI spec generation
9. `src/arena_service/output_boundary.py` — Output boundary enforcement (wraps ACPOutputFilter)
10. `src/arena_service/subprocess_control.py` — Liveness + timeout + PID tracking
11. `tests/test_auth.py` — SVC-01 tests
12. `tests/test_endpoints.py` — SVC-02 tests
13. `tests/test_sse_multiplexing.py` — SVC-03 tests
14. `tests/test_output_boundary.py` — SVC-04 tests
15. `tests/test_permission_safety.py` — SVC-05 + GATE-05 tests
16. `tests/test_subprocess_control.py` — SVC-06 tests
17. `tests/test_sse_reconnection.py` — SVC-07 tests
18. `tests/test_staggered_startup.py` — SVC-08 tests
19. `tests/test_orphan_process.py` — GATE-06 tests

**Modified files:**
20. `scripts/run_v2_gates.py` — Add arena-service gate + GATE-05 + GATE-06
21. `packages/contract-test-suite/tests/test_gate_coverage.py` — Update baseline to 38
22. `packages/acp-client/src/inkstatute_acp_client/adapter.py` — Add `get_active_pids()` method

## Anti-Patterns to Avoid

1. Non-localhost binding (must bind 127.0.0.1 only)
2. No token auth (all requests must have valid token)
3. Batch approval endpoint (must not exist)
4. Auto-approval of dangerous permissions (terminal/execute_code)
5. Output boundary bypass (meta/gateway/system noise reaching client)
6. Session reuse for SSE (must use fresh context)
7. N agents initializing simultaneously (semaphore required)
8. Orphaned processes after cancel (zero PID residue required)
9. SSE event loss/duplication on reconnection (seq-based replay required)
10. Framework dependency (must be stdlib-only like Gateway)
