---
phase: 79-entry-points-threading-foundation
plan: 01
subsystem: api

tags:
  - ThreadingHTTPServer
  - BaseHTTPRequestHandler
  - threading.Lock
  - RuntimeFeatureFlags

requires:
  - phase: 78.1-operator-config-polish
    provides: OperatorConfigStore and admin console handlers

provides:
  - Runnable `python -m admin_console_api` entry point
  - Runnable `python -m admin_web_ui` entry point
  - Thread-safe `OperatorConfigStore`
  - `ThreadSafeFeedbackQueue` wrapper
  - Guarded `ProcessRegistry` for Phase 80 orchestration
  - Threading model decision artifact `THREADING.md`

affects:
  - 80-wecom-host-process-orchestration
  - 81-reports-dashboard
  - 82-log-viewing
  - 83-contract-event-audit
  - 84-health-gate-dashboard

tech-stack:
  added: []
  patterns:
    - ThreadingHTTPServer per-request thread model
    - Snapshot-under-lock for shared mutable lists
    - Single shared store instance on the server

key-files:
  created:
    - services/admin-console-api/src/admin_console_api/server.py
    - services/admin-console-api/src/admin_console_api/__main__.py
    - services/admin-web-ui/src/admin_web_ui/__main__.py
    - services/admin-console-api/src/admin_console_api/feedback.py
    - services/admin-console-api/src/admin_console_api/process_registry.py
    - services/admin-console-api/tests/test_threading.py
    - services/admin-web-ui/tests/test_threading.py
    - services/admin-console-api/tests/test_server.py
    - services/admin-web-ui/tests/test_main.py
    - .planning/phases/79-entry-points-threading-foundation/THREADING.md
  modified:
    - packages/platform-runtime/src/platform_runtime/feature_flags.py
    - packages/operator-config/src/inkstatute_operator_config/store.py
    - services/admin-console-api/src/admin_console_api/api.py
    - services/admin-console-api/src/admin_console_api/views.py
    - .env.example

key-decisions:
  - "Use http.server.ThreadingHTTPServer for both services to keep blocking work from freezing the UI."
  - "Guard OperatorConfigStore.load/save with a per-instance threading.Lock to serialize writers."
  - "Wrap the feedback queue in ThreadSafeFeedbackQueue so iteration returns a snapshot under the lock."
  - "Create ProcessRegistry now as a guarded table for Phase 80 orchestration."

patterns-established:
  - "Entry point: __main__.py resolves env, builds shared deps, creates ThreadingHTTPServer, and registers SIGINT/SIGTERM shutdown from a daemon thread."
  - "Server adapter: BaseHTTPRequestHandler subclasses read from self.server.* attributes and call the existing pure-function handlers."
  - "Shared state: every mutable store is either immutable (read model) or guarded by a threading.Lock (OperatorConfigStore, feedback queue, process table)."

requirements-completed:
  - ENTRY-01
  - ENTRY-02
  - ENTRY-03

completed: 2026-07-13
---

# Phase 79: Entry Points & Threading Foundation Summary

**Runnable `python -m` entry points for `admin-web-ui` and `admin-console-api` on `ThreadingHTTPServer`, with a thread-safety audit and guarded shared mutable state.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-07-13T00:00:00Z
- **Completed:** 2026-07-13T00:00:00Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments

- Added `RuntimeFeatureFlags.from_env()` so service flags are read from `INKSTATUTE_*` env vars.
- Made `OperatorConfigStore` thread-safe by wrapping `load` and `save` with a `threading.Lock`.
- Created `ThreadSafeFeedbackQueue` for concurrent append/iteration and `ProcessRegistry` for Phase 80 orchestration.
- Built `AdminConsoleApiServer` and `admin-console-api/__main__.py` with `create_server()`, `main()`, and graceful SIGINT/SIGTERM shutdown.
- Built `admin-web-ui/__main__.py` with `create_server()` and `main()` that wires `AdminWebUiServer` to the admin API handlers.
- Added socket-level integration tests for both services: concurrent requests, auth, and config POST/PUT.
- Documented the threading model and thread-safety audit in `THREADING.md`.

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags.from_env()` classmethod.
- `packages/operator-config/src/inkstatute_operator_config/store.py` — per-instance `threading.Lock` guarding `load`/`save`.
- `services/admin-console-api/src/admin_console_api/feedback.py` — `ThreadSafeFeedbackQueue`.
- `services/admin-console-api/src/admin_console_api/process_registry.py` — `ProcessRegistry` and `ProcessRecord`.
- `services/admin-console-api/src/admin_console_api/server.py` — `AdminConsoleApiServer` and `create_server()`.
- `services/admin-console-api/src/admin_console_api/__main__.py` — `python -m admin_console_api` entry point.
- `services/admin-web-ui/src/admin_web_ui/__main__.py` — `python -m admin_web_ui` entry point.
- `services/admin-console-api/tests/test_threading.py` — concurrency tests for store, queue, registry.
- `services/admin-web-ui/tests/test_threading.py` — queue compatibility tests.
- `services/admin-console-api/tests/test_server.py` — integration tests for the admin API server.
- `services/admin-web-ui/tests/test_main.py` — integration tests for the admin web UI server.
- `.planning/phases/79-entry-points-threading-foundation/THREADING.md` — threading model and audit.
- `.env.example` — added new host/port/flag/path placeholders.
- `services/admin-console-api/src/admin_console_api/api.py` and `views.py` — updated type hints to accept `ThreadSafeFeedbackQueue`.

## Decisions Made

- `ThreadingHTTPServer` chosen over a single-threaded `HTTPServer` to keep blocking report/log/process work from freezing the UI.
- Shared mutable state is guarded by `threading.Lock` per instance rather than a global lock, because each server holds a single shared instance.
- `ContractLogReadModel` remains immutable after construction; future reloads replace the reference on the server.

## Deviations from Plan

None — plan executed as written. Test auth used `INKSTATUTE_RBAC_ENABLED=true` and RBAC tokens to match the existing auth pipeline.

## Issues Encountered

- Initial integration tests used `urllib.request.Request` with `data` but no explicit `method="PUT"`, causing POST requests and 405 responses. Fixed by adding `method="PUT"`.
- `GET /health` and `GET /sessions` require authentication, so tests were updated to provide a valid `Authorization` header.

## Verification

- `services.admin-console-api.tests.test_threading` — passed
- `services.admin-web-ui.tests.test_threading` — passed
- `services.admin-console-api.tests.test_server` — passed
- `services.admin-web-ui.tests.test_main` — passed
- `python -m admin_console_api --host 127.0.0.1 --port 0` booted and exited cleanly on SIGINT.
- `python -m admin_web_ui --host 127.0.0.1 --port 0` booted and exited cleanly on SIGINT.

## Next Phase Readiness

- Phase 80 (WeCom HTTP Host + Process Orchestration) can start; a guarded `ProcessRegistry` is in place.
- The threading model decision is documented, so later phases can rely on `ThreadingHTTPServer` and snapshot-under-lock patterns.

---
*Phase: 79-entry-points-threading-foundation*
*Completed: 2026-07-13*
