---
phase: 109
slug: arena-service
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-09
---

# Phase 109 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Test framework | unittest with IsolatedAsyncioTestCase |
| Test runner | `python -m unittest discover` |
| Gate runner | `python scripts/run_v2_gates.py` |
| HTTP testing | stdlib http.client or urllib |
| SSE testing | In-memory event capture |
| TDD mode | false |

## Requirement → Test Mapping

| Requirement | Test File | Test Class/Method | Gate |
|-------------|-----------|-------------------|------|
| SVC-01 | test_auth.py | LocalBindingAuthTests | arena-service |
| SVC-02 | test_endpoints.py | ArenaEndpointTests | arena-service |
| SVC-03 | test_sse_multiplexing.py | SSEMultiplexingTests | arena-service |
| SVC-04 | test_output_boundary.py | OutputBoundaryTests | arena-service |
| SVC-05 | test_permission_safety.py | PermissionSafetyTests | arena-permission-safety (GATE-05) |
| SVC-06 | test_subprocess_control.py | SubprocessControlTests | arena-service |
| SVC-07 | test_sse_reconnection.py | SSEReconnectionTests | arena-service |
| SVC-08 | test_staggered_startup.py | StaggeredStartupTests | arena-service |
| GATE-05 | test_permission_safety.py | PermissionSafetyGateTests | arena-permission-safety |
| GATE-06 | test_orphan_process.py | OrphanProcessGateTests | arena-orphan-process |

## Validation Waves

### Wave 0 (Pre-execution)
- [x] Research complete (109-RESEARCH.md)
- [x] Context complete (109-CONTEXT.md)
- [x] Validation strategy complete (109-VALIDATION.md)

### Wave 1 (Core service — no dependencies)
- [ ] config.py + auth.py + app.py scaffold + openapi.py — SVC-01, SVC-02
- [ ] sse.py + event_buffer.py — SVC-03, SVC-07

### Wave 2 (Security + control — depends on Wave 1)
- [ ] output_boundary.py — SVC-04
- [ ] subprocess_control.py + PID tracking — SVC-06
- [ ] staggered startup semaphore — SVC-08

### Wave 3 (Integration + gates — depends on Wave 1+2)
- [ ] Engine integration + end-to-end tests
- [ ] GATE-05 (permission safety) + GATE-06 (orphan process) + gate baseline update

## Acceptance Criteria

1. **Local binding**: 127.0.0.1:8001, non-localhost rejected, no-token rejected
2. **Endpoints**: create/stream/cancel/user-action/status + OpenAPI docs
3. **SSE multiplexing**: N agents on single SSE with agent_slot tagging
4. **Output boundary**: ACP output filter applied, no meta/gateway/system noise
5. **Permission security**: dangerous kinds rejected, no batch approve
6. **Subprocess control**: liveness + timeout + partial-result acceptance
7. **SSE reconnection**: buffer by arena_id, seq-based replay, no dup/loss
8. **Staggered startup**: semaphore prevents simultaneous initialize
9. **Gates**: GATE-05 + GATE-06 in CI, zero PID residue after cancel

## Nyquist Sampling

- Every task has automated verify
- No 3 consecutive tasks without automated verify
- Feedback latency: < 30s per test run
