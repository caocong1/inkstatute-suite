# Phase 79 — Threading Model Decision & Thread-Safety Audit

**Date:** 2026-07-13
**Scope:** `admin-web-ui` and `admin-console-api` entry points, shared mutable state.

## Decision

Both `admin-web-ui` and `admin-console-api` use `http.server.ThreadingHTTPServer` (Python stdlib). A `ThreadingHTTPServer` spawns a new thread for each incoming request so that blocking operations (log reads, report aggregation, subprocess waits in later phases) do not serialize the console.

Rationale:
- stdlib-only, no external web framework or thread-pool dependency.
- Matches the existing `BaseHTTPRequestHandler` adapter pattern used by `admin-web-ui` and `qqbot-service`.
- Single-machine ops with modest concurrency; per-request thread explosion is acceptable for the product console.

Graceful shutdown is implemented in each `__main__.py`:
- `signal.signal` for `SIGINT` and `SIGTERM`.
- The handler spawns a short-lived daemon thread that calls `server.shutdown()`.
- This avoids deadlocking `server.serve_forever()` because `shutdown()` is not called on the signal handler thread.

## Thread-Safety Audit

| Shared mutable state | Guard | Rationale |
|----------------------|-------|-----------|
| `OperatorConfigStore` | `threading.Lock` on `load()` and `save()` | The read-parse-validate and read-mutate-write cycles are not atomic. Concurrent saves could collide on the shared `.tmp` sibling file and produce a corrupted store. Locking the full load/save cycle serializes writers on the same store instance. |
| `feedback_queue` | `ThreadSafeFeedbackQueue` (snapshot under `threading.Lock`) | Iteration (`for item in feedback_queue`) must not see a partially mutated list. `__iter__` returns a snapshot copy under the lock; `append`/`replace` take the lock. |
| `ProcessRegistry` (process table) | `threading.Lock` on `add`/`remove`/`get`/`list`/`replace` | Phase 80 will start/stop processes through this registry. All public operations are guarded so the table is consistent when read by the UI and mutated by orchestration threads. |
| `ContractLogReadModel` | Immutable after construction | The read model is rebuilt from the JSONL contract log and never mutated. `__main__.py` stores a single reference on the server. Future reloads replace the reference, not the object. |
| `RuntimeFeatureFlags` and `server` handler references | Immutable after startup | `RuntimeFeatureFlags` is a frozen dataclass. `server.handle_admin_get`, `server.handle_admin_put`, `server.handle_config_probe`, `server.feature_flags`, `server.env`, `server.rbac_secret`, `server.read_model`, `server.feedback_queue`, and `server.config_store` are assigned once before `serve_forever()` and never reassigned after requests begin. |

## Consequences for later phases

- Phase 80 (process orchestration) must use the guarded `ProcessRegistry` and never replace the `ProcessRegistry` reference on the server after startup.
- Phase 81+ (reports, logs, audit) must read `read_model`/`feedback_queue` through the same wrappers and replace the `read_model` reference (not mutate it) when config changes require a reload.
- No unguarded `read_model` mutation, direct `.append` on `feedback_queue`, or direct `OperatorConfigStore` access outside the locked wrappers may be introduced.
