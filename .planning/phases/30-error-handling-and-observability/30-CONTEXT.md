# Phase 30 Context: Error Handling and Observability

**Date:** 2026-07-03
**Phase goal:** Add retry, graceful degradation, and contract events for memory operations so failures are handled internally and never surprise the user.

---

## Current State

- Phase 29 wired memory into the WeCom session runtime.
- `memory_integration.py` has `fail_open` / `fail_closed` / `log_only` failure modes.
- Memory operations are async and network-bound (Hindsight).
- No structured retry, no failure classification, and no contract events for memory operations yet.

## What Needs to Change

1. Retain/recall operations need exponential backoff retry.
2. Failures must be classified (transient vs permanent vs timeout).
3. On critical memory failure, the bot still responds gracefully without exposing the failure.
4. Contract events must be emitted for retain, recall, and failures.
5. No silent fallback to a different memory UX (e.g., switching to SQLite without explicit config).

## Key Decisions Already Made

- `MemoryIntegrationPolicy.failure_mode` controls whether failures are fatal.
- `fail_open` is the default for WeCom runtime.
- Hindsight is the primary backend; SQLite is no longer the default.

---

## Open Questions

1. Should retry live in the `Memory` adapter or in a wrapper?
2. Should contract events be emitted by the wrapper or by the caller?
3. What is the exact event schema? Can we reuse existing `MemoryUse` or need a new `MemoryOperationEvent`?

---

## Suggested Minimal Shippable Scope

- Implement a `RetryableMemory` wrapper that adds exponential backoff retry around any `Memory` implementation.
- Add `MemoryFailureCategory` enum: `transient`, `timeout`, `permanent`, `auth`.
- Add `MemoryOperationEvent` dataclass for retain/recall/reflect/failure events.
- Add a `MemoryObserver` Protocol so callers can record events to a contract log.
- Update `memory_integration.py` to use `RetryableMemory` and emit events.
- Add tests for retry, failure classification, and event emission.
- Keep V2 gates green.
