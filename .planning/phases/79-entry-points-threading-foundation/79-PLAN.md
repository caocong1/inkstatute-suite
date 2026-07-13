---
phase: 79-entry-points-threading-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/platform-runtime/src/platform_runtime/feature_flags.py
  - packages/operator-config/src/inkstatute_operator_config/store.py
  - services/admin-console-api/src/admin_console_api/feedback.py
  - services/admin-console-api/src/admin_console_api/process_registry.py
  - services/admin-console-api/src/admin_console_api/server.py
  - services/admin-console-api/src/admin_console_api/__main__.py
  - services/admin-console-api/tests/test_threading.py
  - services/admin-console-api/tests/test_server.py
  - services/admin-web-ui/src/admin_web_ui/__main__.py
  - services/admin-web-ui/tests/test_main.py
  - .planning/phases/79-entry-points-threading-foundation/THREADING.md
  - .env.example
autonomous: true
requirements:
  - ENTRY-01
  - ENTRY-02
  - ENTRY-03

must_haves:
  truths:
    - "Both `admin-web-ui` and `admin-console-api` have a `__main__.py` that boots a `ThreadingHTTPServer` on configurable host/port with SIGINT/SIGTERM graceful shutdown"
    - "`RuntimeFeatureFlags.from_env()` reads service flags from environment and `__main__.py` refuses to boot when the service flag is OFF"
    - "`OperatorConfigStore` is thread-safe: a `threading.Lock` guards `load` and `save` on the shared instance"
    - "`feedback_queue` is wrapped by `ThreadSafeFeedbackQueue` and iteration returns a snapshot under a `threading.Lock`"
    - "A guarded `ProcessRegistry` exists with `add`/`remove`/`get`/`list` protected by a `threading.Lock`"
    - "`THREADING.md` documents the `ThreadingHTTPServer` choice and the thread-safety decision for `OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, and process table"
    - "A socket-level integration test boots each service on port 0 and asserts concurrent requests do not serialize"
  artifacts:
    - path: "packages/platform-runtime/src/platform_runtime/feature_flags.py"
      provides: "`RuntimeFeatureFlags.from_env()` classmethod for env-based feature flag construction"
      contains: "from_env"
    - path: "packages/operator-config/src/inkstatute_operator_config/store.py"
      provides: "Thread-safe `OperatorConfigStore` with `threading.Lock` guarding `load`/`save`"
      contains: "_lock"
    - path: "services/admin-console-api/src/admin_console_api/feedback.py"
      provides: "`ThreadSafeFeedbackQueue` wrapper for concurrent iteration and mutation"
      contains: "ThreadSafeFeedbackQueue"
    - path: "services/admin-console-api/src/admin_console_api/process_registry.py"
      provides: "Guarded `ProcessRegistry` stub for Phase 80 orchestration"
      contains: "ProcessRegistry"
    - path: "services/admin-console-api/src/admin_console_api/server.py"
      provides: "`AdminConsoleApiServer` `BaseHTTPRequestHandler` that dispatches GET/PUT to `handle_admin_get`/`handle_admin_put`"
      contains: "AdminConsoleApiServer"
    - path: "services/admin-console-api/src/admin_console_api/__main__.py"
      provides: "Entry point for `python -m admin_console_api` with env resolution, flag gating, and signal shutdown"
      contains: "main"
    - path: "services/admin-web-ui/src/admin_web_ui/__main__.py"
      provides: "Entry point for `python -m admin_web_ui` with env resolution, flag gating, and signal shutdown"
      contains: "main"
    - path: ".planning/phases/79-entry-points-threading-foundation/THREADING.md"
      provides: "Threading model decision and thread-safety audit artifact"
      contains: "ThreadingHTTPServer"
  key_links:
    - from: "services/admin-console-api/src/admin_console_api/__main__.py"
      to: "services/admin-console-api/src/admin_console_api/server.py"
      via: "creates `ThreadingHTTPServer` with `AdminConsoleApiServer`"
      pattern: "ThreadingHTTPServer"
    - from: "services/admin-web-ui/src/admin_web_ui/__main__.py"
      to: "services/admin-console-api/src/admin_console_api/api.py"
      via: "sets `server.handle_admin_get` and `server.handle_admin_put` to the API handlers"
      pattern: "handle_admin_get"
    - from: "services/admin-web-ui/src/admin_web_ui/__main__.py"
      to: "services/admin-console-api/src/admin_console_api/probe.py"
      via: "sets `server.handle_config_probe` for provider probe POSTs"
      pattern: "handle_config_probe"
    - from: "services/admin-console-api/src/admin_console_api/server.py"
      to: "packages/operator-config/src/inkstatute_operator_config/store.py"
      via: "passes `server.config_store` (a thread-safe `OperatorConfigStore`) to handlers"
      pattern: "config_store"
    - from: ".planning/phases/79-entry-points-threading-foundation/THREADING.md"
      to: "packages/operator-config/src/inkstatute_operator_config/store.py"
      via: "documents the locking strategy for shared mutable state"
      pattern: "OperatorConfigStore"
---

<objective>
Create runnable `python -m` entry points for `admin-web-ui` and `admin-console-api` on a `ThreadingHTTPServer` with configurable host/port, SIGINT/SIGTERM graceful shutdown, and feature-flag gating. Decide and document the threading model, then guard every shared mutable store (`OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, process table) before any later phase adds orchestration or log/report features.

Purpose: ENTRY-01 and ENTRY-02 make the admin console services product-grade runnable processes. ENTRY-03 ensures the services are multi-threaded and that shared mutable state is safe, so later phases (log viewing, reports, process orchestration) cannot introduce unguarded read-modify-write cycles.

Output: Two `__main__.py` files, two `BaseHTTPRequestHandler` adapters, a thread-safe `OperatorConfigStore`, a `ThreadSafeFeedbackQueue`, a guarded `ProcessRegistry`, `RuntimeFeatureFlags.from_env()`, the `THREADING.md` audit artifact, and green tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/79-entry-points-threading-foundation/79-CONTEXT.md
@.planning/phases/79-entry-points-threading-foundation/79-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/research/ARCHITECTURE.md
@packages/platform-runtime/src/platform_runtime/feature_flags.py
@packages/operator-config/src/inkstatute_operator_config/store.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/config_api.py
@services/admin-console-api/src/admin_console_api/probe.py
@services/admin-console-api/src/admin_console_api/views.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/__init__.py
@services/conversation-read-view/src/conversation_read_view/read_model.py
@services/feedback-service/src/feedback_service/queue.py
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: Threading foundation and shared-state thread-safety wrappers</name>
  <files>
    packages/platform-runtime/src/platform_runtime/feature_flags.py
    packages/operator-config/src/inkstatute_operator_config/store.py
    services/admin-console-api/src/admin_console_api/feedback.py
    services/admin-console-api/src/admin_console_api/process_registry.py
    services/admin-console-api/tests/test_threading.py
    services/admin-web-ui/tests/test_threading.py
    .planning/phases/79-entry-points-threading-foundation/THREADING.md
    .env.example
  </files>
  <read_first>
    packages/platform-runtime/src/platform_runtime/feature_flags.py
    packages/operator-config/src/inkstatute_operator_config/store.py
    services/feedback-service/src/feedback_service/queue.py
    .planning/research/PITFALLS.md
  </read_first>
  <action>
    Add a `RuntimeFeatureFlags.from_env()` classmethod to `feature_flags.py` that reads boolean values from `INKSTATUTE_<FIELD_NAME_UPPER>` env vars (e.g., `INKSTATUTE_ADMIN_WEB_UI_ENABLED`), falling back to `False` for any missing field. Keep the frozen dataclass shape and the existing `require_enabled` method.

    Add a `threading.Lock` to `OperatorConfigStore` and wrap the `load` and `save` methods with `with self._lock`. The lock must cover the entire read-modify-write cycle: `load` reads the JSON file and `save` reads the current document, mutates, writes `.tmp`, and calls `os.replace`. Do not change the public method signatures.

    Create `services/admin-console-api/src/admin_console_api/feedback.py` with a `ThreadSafeFeedbackQueue` class. It stores a list of `dict` items and a `threading.Lock`. `__iter__` returns `iter(list(self._items))` under the lock. `__bool__` is true when the snapshot is non-empty. Provide `append(item)` and `replace(items)` methods that take the lock. This object must be accepted anywhere `feedback_queue` is currently iterated with `for item in (feedback_queue or [])`.

    Create `services/admin-console-api/src/admin_console_api/process_registry.py` with a `ProcessRegistry` class. It holds a `dict[str, ProcessRecord]` and a `threading.Lock`. Provide `add(name, record)`, `remove(name)`, `get(name)`, `list()`, and `replace(name, record)`, all guarded by the lock. Phase 80 will start/stop processes through this registry; Phase 79 only creates the guarded table.

    Create `services/admin-console-api/tests/test_threading.py` with unit tests: concurrent `OperatorConfigStore.save` calls produce a valid JSON file and no `OSError` from `.tmp` collisions; `ThreadSafeFeedbackQueue` concurrent appends and iterations do not lose items or raise; `ProcessRegistry` concurrent add/remove/list is consistent.

    Create `services/admin-web-ui/tests/test_threading.py` with a small test that `ThreadSafeFeedbackQueue` is iterable and truthy like a list.

    Create `.planning/phases/79-entry-points-threading-foundation/THREADING.md` with: the decision to use `ThreadingHTTPServer`; a table mapping each shared mutable store (`OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, `ProcessRegistry`) to its guard and rationale; and the rule that `RuntimeFeatureFlags` and `server` handler references are immutable after startup.

    Update `.env.example` to add `INKSTATUTE_ADMIN_WEB_UI_ENABLED`, `INKSTATUTE_ADMIN_API_ENABLED`, `INKSTATUTE_OPERATOR_CONFIG_ENABLED`, `INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_FEEDBACK_QUEUE_PATH`, `ADMIN_WEB_UI_HOST`, `ADMIN_WEB_UI_PORT`, `ADMIN_CONSOLE_API_HOST`, `ADMIN_CONSOLE_API_PORT`, and `RBAC_TOKEN_SECRET` placeholders.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/operator-config/src:services/admin-console-api/src:services/admin-web-ui/src:services/conversation-read-view/src:services/feedback-service/src:packages/rbac/src:packages/platform-contract/src python -m unittest services.admin-console-api.tests.test_threading services.admin-web-ui.tests.test_threading -q</automated>
  </verify>
  <done>`RuntimeFeatureFlags.from_env()` exists; `OperatorConfigStore.load`/`save` are guarded; `ThreadSafeFeedbackQueue` and `ProcessRegistry` are thread-safe; `THREADING.md` audit is written; tests pass.</done>
</task>

<task type="auto">
  <name>Task 2: Admin Console API `__main__.py` and `server.py`</name>
  <files>
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/__main__.py
    services/admin-console-api/tests/test_server.py
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/config_api.py
    services/admin-console-api/src/admin_console_api/views.py
    services/conversation-read-view/src/conversation_read_view/read_model.py
    services/feedback-service/src/feedback_service/queue.py
  </read_first>
  <action>
    Create `services/admin-console-api/src/admin_console_api/server.py` with `AdminConsoleApiServer(BaseHTTPRequestHandler)`. Implement `do_GET` and `do_PUT`. Use `urllib.parse.urlparse` to split `self.path` into path and query. For `do_GET`, call `handle_admin_get(path, query_dict, headers, self.server.read_model, self.server.feedback_queue, self.server.feature_flags, self.server.env, self.server.rbac_secret, config_store=self.server.config_store)` and return the JSON response with `Content-Type: application/json; charset=utf-8`. For `do_PUT`, read `Content-Length` bytes (capped at 1 MiB), parse with `json.loads`, call `handle_admin_put(path, body, headers, self.server.feature_flags, self.server.env, config_store=self.server.config_store, rbac_secret=self.server.rbac_secret)`, and return JSON. On JSON parse errors return `400`; on unexpected handler exceptions return `500` and log the traceback to `stderr`. Send `405` for methods other than GET/PUT.

    Create `services/admin-console-api/src/admin_console_api/__main__.py` with a `main()` function. Resolve `ADMIN_CONSOLE_API_HOST` (default `127.0.0.1`) and `ADMIN_CONSOLE_API_PORT` (default `8081`) from env. Build `RuntimeFeatureFlags.from_env()` and call `feature_flags.require_enabled("admin_api_enabled")`; if disabled, print a clear error and exit `1`. Set `RBAC_TOKEN_SECRET` from env, `env` from `os.environ`, `read_model` from `INKSTATUTE_CONTRACT_LOG_PATH` (build with `build_read_model(load_records_from_jsonl(path))` if the file exists, otherwise `build_read_model([])`), `feedback_queue` from `INKSTATUTE_FEEDBACK_QUEUE_PATH` (build with `build_pending_feedback_queue` if the file exists, otherwise `ThreadSafeFeedbackQueue()`), and `config_store` as a shared `OperatorConfigStore()`. Set `server.feature_flags`, `server.env`, `server.rbac_secret`, `server.read_model`, `server.feedback_queue`, `server.config_store` on the `ThreadingHTTPServer` instance. Register SIGINT/SIGTERM handlers that call `httpd.shutdown()` from a daemon thread. Run `httpd.serve_forever()` inside a `with httpd:` context so the socket closes cleanly. If the package cannot be imported, add the repo's `packages/*/src` and `services/*/src` directories to `sys.path` before importing, but only do this inside `__main__.py`.

    Create `services/admin-console-api/tests/test_server.py` with integration tests: start the server on `127.0.0.1:0`, read the bound port, issue two concurrent `GET /health` requests using `urllib.request` and `threading`, assert both return `200` and `OK` body; test `GET /sessions` with a valid `Bearer` token returns `200` JSON; test `PUT /config/channels` updates the config and returns `200`; test that `admin_api_enabled=False` causes `main()` to raise `SystemExit` or print a clear message and exit. Use a temporary directory for `INKSTATUTE_CONTRACT_LOG_PATH` and `INKSTATUTE_OPERATOR_CONFIG_PATH`.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/operator-config/src:services/admin-console-api/src:services/admin-web-ui/src:services/conversation-read-view/src:services/feedback-service/src:packages/rbac/src:packages/platform-contract/src:packages/contract-test-suite/src:services/hermes-contract-layer/src python -m unittest services.admin-console-api.tests.test_server -q</automated>
  </verify>
  <done>`python -m admin_console_api` boots a `ThreadingHTTPServer` on the configured host/port, handles GET/PUT, returns JSON, and integration tests pass including concurrent requests.</done>
</task>

<task type="auto">
  <name>Task 3: Admin Web UI `__main__.py` and integration tests</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/tests/test_main.py
    .env.example
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/probe.py
  </read_first>
  <action>
    Create `services/admin-web-ui/src/admin_web_ui/__main__.py` with a `main()` function. Resolve `ADMIN_WEB_UI_HOST` (default `127.0.0.1`) and `ADMIN_WEB_UI_PORT` (default `8080`) from env. Build `RuntimeFeatureFlags.from_env()` and call `feature_flags.require_enabled("admin_web_ui_enabled")`; if disabled, exit `1`. Build the same `read_model`, `feedback_queue`, `config_store`, `env`, and `rbac_secret` as the admin-console-api entry point. Set `server.feature_flags`, `server.env`, `server.rbac_secret`, `server.read_model`, `server.feedback_queue`, `server.config_store`, `server.handle_admin_get = admin_console_api.api.handle_admin_get`, `server.handle_admin_put = admin_console_api.api.handle_admin_put`, and `server.handle_config_probe = admin_console_api.probe.handle_config_probe`. Create `ThreadingHTTPServer((host, port), AdminWebUiServer)`, register SIGINT/SIGTERM daemon-thread shutdown, and call `serve_forever()` inside a `with` context. If sibling packages are not importable, add the repo `packages/*/src` and `services/*/src` directories to `sys.path` before importing.

    Create `services/admin-web-ui/tests/test_main.py` with integration tests: start the server on `127.0.0.1:0`, read the bound port, issue two concurrent `GET /` requests with `Authorization: Bearer <token>` and assert both return `200` and `text/html`; issue a `POST /config/channels` with a valid CSRF token (obtained by first rendering the form) and assert the response is `200` and contains expected HTML; test that `admin_web_ui_enabled=False` causes `main()` to raise `SystemExit` or print and exit. Use a temporary directory for the operator config and contract log paths and set `RBAC_TOKEN_SECRET` for the test.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/operator-config/src:services/admin-console-api/src:services/admin-web-ui/src:services/conversation-read-view/src:services/feedback-service/src:packages/rbac/src:packages/platform-contract/src:packages/contract-test-suite/src:services/hermes-contract-layer/src python -m unittest services.admin-web-ui.tests.test_main -q</automated>
  </verify>
  <done>`python -m admin_web_ui` boots a `ThreadingHTTPServer` on the configured host/port, serves the SSR admin UI, handles POSTs with CSRF, and integration tests pass including concurrent requests.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator browser → `admin-web-ui` | SSR HTML over HTTP; no secrets or resolved values rendered in the UI. |
| Admin API client → `admin-console-api` | JSON API; authenticated via `RBAC_TOKEN_SECRET` or `ADMIN_API_TOKEN` Bearer header. |
| Request thread → shared mutable state | `OperatorConfigStore`, `feedback_queue`, `ProcessRegistry` are guarded by `threading.Lock`. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-79-01 | Denial of Service | `AdminConsoleApiServer` PUT body | mitigate | Read only `Content-Length` bytes and cap at 1 MiB; parse JSON inside `try/except` and return `400` on failure. |
| T-79-02 | Elevation | Service boot without flag | mitigate | `__main__.py` calls `feature_flags.require_enabled("admin_*_enabled")` and exits `1` when the flag is OFF. |
| T-79-03 | Information Disclosure | Binding to all interfaces | mitigate | Default host is `127.0.0.1`; operators may override via `ADMIN_*_HOST` env. |
| T-79-04 | Tampering | Concurrent config writes | mitigate | `OperatorConfigStore.load`/`save` are guarded by a `threading.Lock`. |
| T-79-05 | Denial of Service | `ThreadingHTTPServer` thread explosion | accept | stdlib per-request thread model; single-machine ops with modest concurrency. Document in `THREADING.md` that this is acceptable for the product console. |
| T-79-06 | Denial of Service | Unbounded `feedback_queue` list | mitigate | `ThreadSafeFeedbackQueue` returns snapshots; future phases must cap queue size. |
</threat_model>

<verification>
`test_threading.py` (admin-console-api and admin-web-ui) passes, `test_server.py` (admin-console-api) passes, `test_main.py` (admin-web-ui) passes, `python -m admin_console_api --host 127.0.0.1 --port 0` boots and exits cleanly on SIGINT, and `python -m admin_web_ui --host 127.0.0.1 --port 0` boots and exits cleanly on SIGINT.
</verification>

<success_criteria>
1. Operator can start `admin-web-ui` and `admin-console-api` as standalone HTTP servers via `python -m <pkg>` (or entry script) with configurable host/port, SIGINT/SIGTERM graceful shutdown, and a feature-flag gate that refuses to boot when the service flag is OFF.
2. Both services bind `ThreadingHTTPServer` (not single-threaded `HTTPServer`) so blocking operations (log reads, report aggregation, subprocess waits) do not freeze the UI; a socket-level integration test boots each service on an ephemeral port and asserts concurrent requests do not serialize.
3. A threading-model decision artifact documents the `ThreadingHTTPServer` choice, and a thread-safety audit guards every shared mutable store (`OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, process table) with per-store `threading.Lock` or copy-on-rebuild semantics — no unguarded read-modify-write cycle remains.
</success_criteria>

<output>
Create `.planning/phases/79-entry-points-threading-foundation/79-SUMMARY.md` when done.
</output>
