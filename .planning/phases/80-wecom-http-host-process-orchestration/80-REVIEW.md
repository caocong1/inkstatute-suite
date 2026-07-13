# Phase 80 — WeCom HTTP Host + Process Orchestration — Code Review

## Summary

- **Phase**: 80-wecom-http-host-process-orchestration
- **Commits reviewed**: `e67f8ec` (implementation), `543a89e` (docs)
- **Review focus**: Security, concurrency, correctness
- **Status**: `findings` (small safe issues were fixed and retested)

## Scope

Reviewed the Phase 80 implementation files, excluding planning docs, `.env.example`, and tests.

- `packages/rbac/src/rbac/matrix.py`
- `services/admin-console-api/src/admin_console_api/api.py`
- `services/admin-console-api/src/admin_console_api/config_api.py`
- `services/admin-console-api/src/admin_console_api/process_registry.py`
- `services/admin-console-api/src/admin_console_api/process_supervisor.py`
- `services/admin-console-api/src/admin_console_api/processes_api.py`
- `services/admin-console-api/src/admin_console_api/server.py`
- `services/admin-web-ui/src/admin_web_ui/__main__.py`
- `services/admin-web-ui/src/admin_web_ui/api_client.py`
- `services/admin-web-ui/src/admin_web_ui/dashboard.py`
- `services/admin-web-ui/src/admin_web_ui/processes.py`
- `services/admin-web-ui/src/admin_web_ui/server.py`
- `services/qqbot-service/src/qqbot_service/__main__.py`
- `services/qqbot-service/src/qqbot_service/http_server.py`
- `services/wecom-service/src/wecom_service/__main__.py`
- `services/wecom-service/src/wecom_service/http_server.py`
- `services/wecom-service/src/wecom_service/webhook.py`

## Findings and fixes

### 1. `process_supervisor.py` — `PYTHONPATH` fallback was conditional and used wrong repo root

**Problem**: `ProcessSupervisor.start` only computed the fallback source-root `PYTHONPATH` when `self._env` had no `PYTHONPATH` at all, and it used `Path(__file__).resolve().parents[3]` which resolves to the `services/` directory, not the repo root. Because the fallback paths were appended to `services/`, the child WeCom/QQBot hosts would fail with `ModuleNotFoundError` for `inkstatute_channels_wecom` when the parent `PYTHONPATH` was missing the channel source roots.

**Fix**: Added `ProcessSupervisor._default_pythonpath()` and `_pythonpath_for_child()`:

- Uses the correct repo root (`parents[4]`).
- Always prepends the canonical source roots (`services/.../src`, `packages/.../src`, including `channels/wecom` and `channels/qqbot`) to any inherited `PYTHONPATH`, deduplicating entries.
- Sets `child_env["PYTHONPATH"]` unconditionally.

### 2. `process_supervisor.py` — `self._procs` was not thread-safe

**Problem**: `ProcessSupervisor` is used by `ThreadingHTTPServer` and admin endpoints. Reads and writes to `self._procs` and `self._registry` were unprotected, and `status()` performed a blocking HTTP probe while touching shared state, creating a race window.

**Fix**: Added `self._lock = threading.Lock()` in `__init__` and protected:

- `start()` — full start/kill/Popen/register critical section.
- `stop()` — full terminate/wait/unregister critical section.
- `status()` — brief snapshot/update with the HTTP probe done outside the lock, using a `current.pid == record.pid` guard when writing back the health result.
- `_persist()` — file write is locked.

### 3. `process_supervisor.py` — `log_file` file descriptor leak

**Problem**: `start()` opened `log_file = open(log_path, "ab")` and passed it to `subprocess.Popen`, but the parent process never closed the file object, leaking the descriptor.

**Fix**: Wrapped `Popen` in `try/finally: log_file.close()`. The child inherits a dup of the underlying fd, so this is safe.

### 4. `wecom_service/webhook.py` — `handle_wecom_webhook_request` could crash on non-JSON or non-UTF-8 bodies

**Problem**: `payload = json.loads(body_bytes.decode("utf-8"))` was unguarded. A malformed body caused a `JSONDecodeError`/`UnicodeDecodeError` to propagate and become a 500 response.

**Fix**: Added a `try/except (UnicodeDecodeError, json.JSONDecodeError)` block that returns a 400 response with `{"error":"invalid_json"}` before any further processing.

### 5. `wecom_service/__main__.py` and `qqbot_service/__main__.py` — repo-root path off-by-one

**Problem**: The `sys.path` insertion in both `__main__.py` files used `Path(__file__).resolve().parents[3]` and `parents[2]`, which resolve to `services/` and `services/<service>/` rather than the repo root and `services/<service>/src`. The resulting fallback paths did not point to the package source roots.

**Fix**: Changed to `parents[4]` for the repo root and `parents[2] / "src"` for the service source root so the fallback `sys.path` entries are correct.

## Notes / warnings

- The `__main__.py` `sys.path` fallback is correct, but because `__init__.py` at the top of the `wecom_service` and `qqbot_service` packages also imports `inkstatute_channels_*` and `inkstatute_operator_config` at import time, `__main__.py` is reached only after `__init__.py` already needs those packages. Running `python -m wecom_service` without `PYTHONPATH` exported still fails unless `__init__.py` also gets the source roots. In production/ProcessSupervisor paths, `PYTHONPATH` is set explicitly, so runtime is unaffected. Consider adding the same source-root `sys.path` insertion to `__init__.py` if standalone `python -m` execution without a prepared `PYTHONPATH` is required.
- `process_supervisor.py` `start()` still holds `self._lock` during the up-to-5-second termination wait of a stale PID. This is acceptable for admin operations but means concurrent `status()` calls may block briefly during a restart.

## Tests run

After the fixes, the relevant test suites were run with the canonical source roots on `PYTHONPATH`:

- `services/admin-console-api/tests` — 280 passed, 1 skipped
- `services/wecom-service/tests` — 90 passed
- `services/qqbot-service/tests` — 83 passed
- `services/admin-web-ui/tests` — 161 passed
- `packages/rbac/tests` — 61 passed
- `packages/platform-runtime/tests` — 406 passed, 3 skipped

## Status

`status: findings`

All identified issues were small, safe, and fixed inline. No large refactors or new dependencies were introduced.
