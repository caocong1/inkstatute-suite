# Phase 79 — Research Notes

**Phase:** 79 — Entry Points & Threading Foundation  
**Researched:** 2026-07-13  
**Domain:** Python stdlib `http.server` threaded entry points, signal handling, and shared-state thread safety for the v1.11 Product Console.  
**Confidence:** HIGH

## User Constraints

Copied from `79-CONTEXT.md` (auto-generated, no locked decisions):

- **Claude's Discretion:** All implementation choices are at Claude's discretion. Use the ROADMAP phase goal, success criteria, and codebase conventions.
- **Deferred Ideas:** None — discuss phase skipped.

### Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENTRY-01 | `admin-web-ui` runnable as `python -m admin_web_ui` with configurable host/port, graceful shutdown, and feature-flag gate. | `ThreadingHTTPServer` + `BaseHTTPRequestHandler` (`AdminWebUiServer`) already exists; only `__main__.py` and signal handling are missing. |
| ENTRY-02 | `admin-console-api` runnable as `python -m admin_console_api` with configurable host/port, graceful shutdown, and feature-flag gate. | Pure `handle_admin_get` / `handle_admin_put` handlers exist; need a `BaseHTTPRequestHandler` wrapper and `__main__.py`. |
| ENTRY-03 | `ThreadingHTTPServer` (not single-threaded) and thread-safety audit for `OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, process table. | `BaseHTTPRequestHandler` is not thread-safe; concurrent writes to `OperatorConfigStore` and mutable lists must be guarded. |

## Summary

Phase 79 is the foundation layer for the v1.11 Product Console. Both the admin web UI and the admin API are currently pure, testable handler cores (`handle_admin_web_ui_request`, `handle_admin_get`, `handle_admin_put`) with no runnable entry point. This phase adds a `__main__.py` to each service, binds them to a `ThreadingHTTPServer` with a configurable host/port and SIGINT/SIGTERM graceful shutdown, and gates startup with `RuntimeFeatureFlags`.

Because `ThreadingHTTPServer` spawns a new thread per request, the second half of the phase is a thread-safety audit of every shared mutable object that the request handlers touch: `OperatorConfigStore` (file-backed JSON), `feedback_queue` (pending-feedback list), `ContractLogReadModel` (immutable index), and the future process table (Phase 80). The audit is captured in `THREADING.md`.

**Primary recommendation:** Implement a `__main__.py` per service, add a small `ThreadingHTTPServer` adapter in `admin-console-api`, make `OperatorConfigStore` thread-safe with a `threading.Lock`, wrap the feedback queue with snapshot-under-lock semantics, and create a guarded `ProcessRegistry` stub for Phase 80.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP entry point / port binding | Backend / API | Frontend Server (SSR) | `__main__.py` is the OS process entry point; the handlers are thin wrappers over existing API/SSR cores. |
| Graceful shutdown / signal handling | Backend | — | SIGINT/SIGTERM handling belongs to the process lifecycle, not to request handlers. |
| Thread-safe shared state | API / Runtime | — | `OperatorConfigStore`, `feedback_queue`, and future process table are backend resources accessed by request threads. |
| Feature flag gating | API / Runtime | — | `RuntimeFeatureFlags` is already a core runtime concept; `from_env` extends it. |
| Threading model decision doc | Architecture | — | `THREADING.md` documents the audit and decisions for all phases that build on it. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `http.server.ThreadingHTTPServer` | Python stdlib (≥3.11) | Binds `BaseHTTPRequestHandler` subclasses to a host/port and dispatches each request on its own thread. | Ships with Python, avoids external web-framework dependencies; matches the existing stdlib-only handler pattern. [VERIFIED: `python -c "from http.server import ThreadingHTTPServer; print(ThreadingHTTPServer)"`] |
| `signal` | Python stdlib | SIGINT/SIGTERM handlers for graceful shutdown. | Required for clean `server.shutdown()` on Ctrl-C / `kill`. [CITED: docs.python.org/3/library/signal.html] |
| `threading` | Python stdlib | `Lock` for `OperatorConfigStore`, `ThreadSafeFeedbackQueue`, `ProcessRegistry`. | Standard concurrency primitive for in-process shared mutable state. |
| `argparse` | Python stdlib | Optional `--host`, `--port`, `--config-path` CLI overrides. | Operators expect CLI knobs without editing code. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `os` / `pathlib` | Python stdlib | Resolve env vars, default paths, and test file existence. | Always used for config path resolution. |
| `json` | Python stdlib | Parse PUT request bodies and serialize responses. | Only for `admin-console-api` JSON adapter; `admin-web-ui` uses HTML/SSR. |

### Package Legitimacy Audit

No external packages are introduced. All recommended stack items are Python stdlib.

## Architecture Patterns

### Entry point pattern

Each `__main__.py` is a thin adapter:

1. Resolve env and CLI args.
2. Build `RuntimeFeatureFlags.from_env()` and require the service-specific flag.
3. Build `read_model`, `feedback_queue`, `config_store`, `env`, `rbac_secret`.
4. Set the same `server.*` attributes that the test suite already injects.
5. Create `ThreadingHTTPServer((host, port), Handler)` and call `serve_forever()`.
6. Register a SIGINT/SIGTERM handler that calls `server.shutdown()` from a separate thread.

### Shared-state thread-safety pattern

- `OperatorConfigStore.load` / `save`: wrap in a `threading.Lock` per instance. Concurrent saves serialize on the same store object; `os.replace` is atomic but the temporary-file path is shared and the read-modify-write cycle is not.
- `feedback_queue`: wrap in a `ThreadSafeFeedbackQueue` class that holds a `list` and a `Lock`. Iteration returns a snapshot copy under the lock; appends/replacements take the lock.
- `ContractLogReadModel`: immutable after construction. The `read_model` reference is assigned once at startup; future reloads replace the reference under a `read_model_lock`.
- `ProcessRegistry`: a `dict` guarded by a `threading.Lock`. Phase 79 only adds/removes/gets records; Phase 80 will start/stop processes.

### Anti-Patterns to Avoid

- Do **not** call `server.shutdown()` from inside the signal handler on the same thread — this deadlocks `serve_forever()`. Use a short-lived daemon thread.
- Do **not** mutate `BaseHTTPRequestHandler` class variables; put shared state on the `server` instance.
- Do **not** pass a plain `list` for `feedback_queue` if it can be mutated by another thread; use the snapshot wrapper.
- Do **not** create a new `OperatorConfigStore` per request and rely on the file-system for atomicity; the process should use one shared `config_store` instance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent HTTP request dispatch | A thread pool on top of `HTTPServer` | `ThreadingHTTPServer` | Already part of stdlib; handles socket accept and thread lifecycle safely. |
| Process signal shutdown | Custom signal + polling loop | `signal.signal` + `server.shutdown()` from a daemon thread | Standard pattern avoids deadlock and cross-platform fork issues. |
| Shared mutable state guard | Manual `try/finally` locks everywhere | `threading.Lock` with `with` or a dedicated wrapper class | Reduces boilerplate and guarantees release on exceptions. |
| JSON body parsing | Ad-hoc byte splitting | `json.loads` with `Content-Length` cap | Prevents unbounded reads and malformed-body crashes. |

## Common Pitfalls

### Pitfall 1: Default single-threaded `HTTPServer` freezes the UI
- **What goes wrong:** Using `HTTPServer` instead of `ThreadingHTTPServer` means one request at a time. A blocking GET (e.g., a long report or log tail) locks the entire console.
- **How to avoid:** Bind `ThreadingHTTPServer` and document the choice in `THREADING.md`. Add a socket-level test that fires two concurrent requests and asserts both complete.

### Pitfall 2: `server.shutdown()` deadlock from a signal handler
- **What goes wrong:** Calling `httpd.shutdown()` inside the signal handler blocks the same thread that is running `serve_forever()`.
- **How to avoid:** `signal.signal` handler spawns `threading.Thread(target=httpd.shutdown, daemon=True).start()` and returns immediately.

### Pitfall 3: `OperatorConfigStore` read-modify-write races
- **What goes wrong:** Two concurrent `PUT /config/channels` requests load the same file, modify it, and write `.tmp` + `os.replace`. The last write wins, and the `.tmp` file path collides.
- **How to avoid:** Add a `threading.Lock` to `OperatorConfigStore` and wrap `load`/`save` with `with self._lock`. The `__main__.py` passes a single shared store instance to all handlers.

### Pitfall 4: `feedback_queue` mutation while being iterated
- **What goes wrong:** Another thread appends feedback while a request thread is iterating the list.
- **How to avoid:** Use `ThreadSafeFeedbackQueue` whose `__iter__` returns a snapshot under the lock.

### Pitfall 5: `ContractLogReadModel` assumed mutable
- **What goes wrong:** Code starts modifying `read_model` internal caches or replacing the reference without a lock.
- **How to avoid:** Treat it as immutable; if a future reload is needed, replace `server.read_model` under a `threading.Lock`.

### Pitfall 6: Feature flags not loaded from environment
- **What goes wrong:** `RuntimeFeatureFlags()` defaults to all OFF, so the service refuses to boot even when the operator set flags.
- **How to avoid:** Add `RuntimeFeatureFlags.from_env()` that reads `INKSTATUTE_<FIELD_NAME_UPPER>` style env vars (e.g., `INKSTATUTE_ADMIN_WEB_UI_ENABLED`).

## Code Examples

### Minimal `ThreadingHTTPServer` with signal shutdown

```python
import signal
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)

def _shutdown(signum, frame):
    threading.Thread(target=httpd.shutdown, daemon=True).start()

signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

with httpd:
    httpd.serve_forever()
```

Source: [CITED: docs.python.org/3/library/http.server.html]

### Thread-safe `OperatorConfigStore` sketch

```python
import threading

class OperatorConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_operator_config_path()
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            # existing load logic

    def save(self, document, *, feature_flags):
        with self._lock:
            # existing save logic
```

This is a code sketch, not the implementation; the implementation belongs in `OperatorConfigStore`.

## Validation Architecture

> Included because `workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) |
| Config file | none — `pytest` may be used by CI but `python -m unittest` is the baseline |
| Quick run command | `PYTHONPATH=... python -m unittest services.admin-console-api.tests.test_threading -q` |
| Full suite command | `PYTHONPATH=... python -m unittest discover -s . -p 'test_*.py' -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENTRY-01 | `python -m admin_web_ui` boots on configured host/port and shuts down on SIGINT | integration | `python -m unittest services.admin-web-ui.tests.test_main -q` | ❌ Wave 0 |
| ENTRY-02 | `python -m admin_console_api` boots on configured host/port and shuts down on SIGINT | integration | `python -m unittest services.admin-console-api.tests.test_server -q` | ❌ Wave 0 |
| ENTRY-03 | `ThreadingHTTPServer` handles concurrent requests and shared state is guarded | unit + concurrency | `python -m unittest services.admin-console-api.tests.test_threading services.admin-web-ui.tests.test_threading -q` | ❌ Wave 0 |

### Wave 0 Gaps

- `services/admin-console-api/tests/test_threading.py` — shared-state thread-safety tests.
- `services/admin-console-api/tests/test_server.py` — HTTP entry-point tests.
- `services/admin-web-ui/tests/test_main.py` — HTTP entry-point and SSR tests.
- `.env.example` — add `INKSTATUTE_ADMIN_WEB_UI_ENABLED`, `INKSTATUTE_ADMIN_API_ENABLED`, `INKSTATUTE_OPERATOR_CONFIG_ENABLED`, `INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_FEEDBACK_QUEUE_PATH`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | `ThreadingHTTPServer` bound to `127.0.0.1` by default; no reverse-proxy/TLS assumed in this phase. |
| V2 Authentication | yes | Existing `rbac` HMAC token and `ADMIN_API_TOKEN` Bearer auth; no new auth added. |
| V3 Session Management | no | No session/cookie state; current token-based model continues. |
| V4 Access Control | yes | `RbacGuard` + `RuntimeFeatureFlags` service gating. |
| V5 Input Validation | yes | `json.loads` body parsing, `urllib.parse` path handling, `Content-Length` cap. |
| V6 Cryptography | no | No new cryptography; reuse `rbac` HMAC. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Binding admin services to public interfaces | Information Disclosure / Elevation | Default host `127.0.0.1`; operators may override via env. |
| Unbounded PUT body | Denial of Service | Read only `Content-Length` bytes and cap at a sensible max (e.g., 1 MiB). |
| Concurrent config writes | Tampering | `threading.Lock` in `OperatorConfigStore` load/save. |
| Feature-flag bypass | Elevation | `RuntimeFeatureFlags.from_env` + `require_enabled` in `__main__.py`. |

## Sources

### Primary (HIGH confidence)

- Python stdlib `http.server` — `ThreadingHTTPServer` documentation: [CITED: https://docs.python.org/3/library/http.server.html]
- Python stdlib `signal` — signal handlers: [CITED: https://docs.python.org/3/library/signal.html]
- Codebase `services/admin-console-api/src/admin_console_api/api.py` — `handle_admin_get` / `handle_admin_put` signatures.
- Codebase `services/admin-web-ui/src/admin_web_ui/server.py` — `handle_admin_web_ui_request` and `AdminWebUiServer`.
- Codebase `packages/operator-config/src/inkstatute_operator_config/store.py` — `OperatorConfigStore` atomic write implementation.
- Codebase `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags` frozen dataclass.

### Secondary (MEDIUM confidence)

- `.planning/research/STACK.md` — v1.11 Product Console stack research.
- `.planning/research/PITFALLS.md` — entry-point, signal, and orchestration pitfalls.
- `.planning/research/ARCHITECTURE.md` — service entry-point architecture.

### Tertiary (LOW confidence)

- None — all claims are either verified by codebase inspection or cited from official Python docs.

## Assumptions / Low-Confidence Items

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | Env var naming convention for feature flags is `INKSTATUTE_<FIELD_NAME_UPPER>` (e.g., `INKSTATUTE_ADMIN_WEB_UI_ENABLED`). | If different env vars are used, `__main__.py` can fail to boot. Mitigation: also support the exact field name. |
| A2 | The default contract-log path is read from `INKSTATUTE_CONTRACT_LOG_PATH` and the default feedback queue path is `INKSTATUTE_FEEDBACK_QUEUE_PATH` (new). | If the project uses a different convention, `__main__.py` will need adjustment. |
| A3 | `ThreadingHTTPServer` is sufficient for the v1.11 Product Console; no WebSocket/SSE is required in this phase. | If later phases require streaming, the entry-point adapter may need extension. |
| A4 | `OperatorConfigStore` can be made thread-safe by adding a per-instance `threading.Lock` without changing the public API. | If a future process reads/writes from multiple processes, an OS-level lock may be needed. |

## Out of Scope

- Process lifecycle start/stop/inspect (Phase 80: ORCHESTRATION).
- Log viewing / tail-follow (Phase 82).
- Reports / audit / health dashboards (Phases 81, 83, 84).
- RBAC token management / login-session (Phases 85, 86).
- UI polish (Phase 87).
- TLS, reverse-proxy, production deployment tooling.

## Metadata

- **Confidence breakdown:** Standard stack HIGH, Architecture HIGH, Pitfalls HIGH.
- **Research date:** 2026-07-13
- **Valid until:** 30 days (stdlib is stable)
