---
phase: 42
slug: admin-console-api
status: planning
researcher: gsd-planner
created: 2026-07-04
---

# Phase 42 Research — Admin Console API

> Requirements: **ADMIN-01** — Operator can authenticate to a read-only Admin Console API via a static token from env, and query sessions, tasks, feedback, gates, and health views with filtering and pagination.
> **ADMIN-02** — Operator can verify that Admin Console API health/status views use a field allowlist that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values.
> **SC3 (Phase 42 success criterion 3)** — Operator can verify that `admin_api_enabled` defaults to `False` and that the Admin Console API runs `run_v2_gates.py --json-summary` via subprocess for gate status views without importing gate internals.

## 1. Summary

Phase 42 creates a **new service** `services/admin-console-api/` — a read-only Admin Console API that authenticates operators via a static token from env and exposes sessions, tasks, feedback, gates, and health views with filtering and pagination. The service **reuses** `ContractLogReadModel` and cursor pagination from `services/conversation-read-view/` — it does not duplicate the read model or pagination logic. It is strictly read-only: no mutations, no writes, no side effects beyond a subprocess call to `run_v2_gates.py --json-summary` for gate status views.

The work is **contract-safe**: no changes to `packages/platform-contract/` or `packages/platform-runtime/protocols.py` (SAFETY-02, SAFETY-06). The `admin_api_enabled` feature flag already exists in `RuntimeFeatureFlags` (`packages/platform-runtime/src/platform_runtime/feature_flags.py:22`) and defaults to `False` — Phase 42 wires it into the API handler as a gate, it does not modify the flag definition.

Key findings:

- The Admin Console API is a **new service** following the existing `services/conversation-read-view/` pattern: `src/{package}/`, `tests/`, `pyproject.toml` with `dependencies = []`, `README.md`. Pure Python, stdlib only, no server process.
- `ContractLogReadModel` (`services/conversation-read-view/src/conversation_read_view/read_model.py:28-288`) provides `get_conversation()`, `get_task()`, `get_task_by_trace_id()`, `get_trace_reconstruction()`, `list_conversations()`, `list_tasks()`. The Admin Console API imports and delegates to these methods — it does not subclass or duplicate.
- Cursor pagination (`services/conversation-read-view/src/conversation_read_view/pagination.py:1-133`) provides `resolve_max_result_limit()`, `clamp_limit()`, `encode_cursor()`, `decode_cursor()`, `slice_page()`. The Admin Console API reuses these directly.
- Privacy scrubbing (`services/conversation-read-view/src/conversation_read_view/privacy.py:51-62`) provides `scrub_contract_payload()` which raises `ValueError` on forbidden keys. The Admin Console API routes all data-view responses through this scrub.
- The `admin_api_enabled` flag is already defined in `RuntimeFeatureFlags` (`feature_flags.py:22`) with default `False`. The `require_enabled("admin_api_enabled")` method (`feature_flags.py:27-32`) raises `RuntimeFeatureDisabledError` when the flag is off. Phase 42 calls this before processing any request.
- `scripts/run_v2_gates.py` supports `--json-summary` (`run_v2_gates.py:25,40-46`) which outputs `{"passed": bool, "gates": [{"name": str, "exit_code": int}]}`. The Admin Console API runs this via `subprocess.run` — it does NOT import gate internals.
- Health/status views must use a **field allowlist** that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values. Only `secrets_configured: true/false` is exposed. This is a separate concern from the `ALL_FORBIDDEN_KEYS` privacy scrub — the allowlist is a positive filter (only expose known-safe fields), not a negative filter (block known-bad fields).

## 2. Existing Service Patterns

### 2.1 Service directory layout

**Reference:** `services/conversation-read-view/`, `services/wecom-service/`, `services/feedback-service/`

```
services/{name}/
  src/{package_name}/
    __init__.py     # public API surface
    api.py          # handle_get route dispatcher (pure GET)
    ...             # domain modules
  tests/
    test_*.py       # unittest test modules
  pyproject.toml    # name=inkstatute-{name}, dependencies=[]
  README.md
```

All services use `dependencies = []` in `pyproject.toml` — pure stdlib, no external runtime dependencies. Tests use `unittest` (not pytest). The `PYTHONPATH` for tests includes cross-package source roots (e.g., `packages/platform-contract/src`, `packages/platform-runtime/src`).

### 2.2 API handler pattern

**File:** `services/conversation-read-view/src/conversation_read_view/api.py:18-82`

The entry point is `handle_get(path, query, read_model, feedback_queue=None) -> tuple[int, dict]`. It:
1. Splits path and query via `_split_path_query`.
2. Routes by path prefix (`if route_path == "/conversations": ...`).
3. Applies `scrub_contract_payload` via `_with_contract_metadata` on every 200 response.
4. Returns `(status_code, response_dict)`.

The Admin Console API follows the same pattern but adds an **auth gate** before routing: `handle_admin_get(path, query, headers, read_model, feedback_queue, feature_flags, env) -> tuple[int, dict]`. The auth gate checks (1) `admin_api_enabled` flag and (2) static token from env. If either fails, returns 403.

### 2.3 pyproject.toml pattern

**File:** `services/conversation-read-view/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-admin-console-api"
version = "0.1.0"
description = "Read-only Admin Console API for InkStatute V2 operator views."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
```

## 3. ContractLogReadModel Reuse Strategy

### 3.1 Import path

The Admin Console API imports `ContractLogReadModel` from `conversation_read_view.read_model`:

```python
from conversation_read_view.read_model import ContractLogReadModel, build_read_model, load_records_from_jsonl
from conversation_read_view.pagination import clamp_limit, resolve_max_result_limit, slice_page
from conversation_read_view.privacy import scrub_contract_payload
```

This works because the admin-console-api gate's PYTHONPATH includes `services/conversation-read-view/src` (same as the conversation-read-view gate does for `packages/platform-contract/src`).

### 3.2 Delegation, not duplication

The Admin Console API **delegates** to the read model methods — it does not subclass, wrap, or duplicate them:

| Admin Console View | Read Model Method | Notes |
|---------------------|-------------------|-------|
| `/sessions` (list) | `read_model.list_conversations()` | Sessions = conversations in the contract log model |
| `/sessions/{id}` | `read_model.get_conversation()` | Single conversation lookup |
| `/tasks` (list) | `read_model.list_tasks()` | Filtered, paginated task list |
| `/tasks/{id}` | `read_model.get_task()` / `get_task_by_trace_id()` | Single task lookup |
| `/feedback` | `feedback_queue` filtering | Same as conversation-read-view `/feedback` |
| `/gates` | subprocess `run_v2_gates.py --json-summary` | Gate status view |
| `/health` | field allowlist projection | Health/status view |

The Admin Console API adds its own **filter parsing** and **pagination wrapping** on top of the read model methods, but the core data retrieval is delegated.

### 3.3 Sessions vs conversations

The ROADMAP says "sessions, tasks, feedback" — in the contract log model, "sessions" maps to "conversations" (a conversation is a session in V2 contract terms). The Admin Console API exposes `/sessions` as an alias for the conversation list view, delegating to `list_conversations()`. This is a naming choice, not a data model change.

## 4. Static Token Auth from Env

### 4.1 Token resolution

The Admin Console API reads a static token from env var `ADMIN_API_TOKEN`. If the env var is not set or is empty, the API refuses all requests with 403. The token is compared using `hmac.compare_digest` (constant-time comparison) to prevent timing attacks.

**File to create:** `services/admin-console-api/src/admin_console_api/auth.py`

```python
import hmac
import os
from typing import Mapping

ADMIN_API_TOKEN_ENV = "ADMIN_API_TOKEN"

def resolve_admin_token(env: Mapping[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    token = source.get(ADMIN_API_TOKEN_ENV, "")
    return token if token else None

def check_auth_header(header_value: str, expected_token: str | None) -> bool:
    if expected_token is None:
        return False
    if not header_value.startswith("Bearer "):
        return False
    provided = header_value.removeprefix("Bearer ")
    return hmac.compare_digest(provided, expected_token)
```

### 4.2 Auth gate in the API handler

`handle_admin_get` checks auth before routing:

1. Resolve `admin_api_enabled` flag — if `False`, return 403 `{"error": {"code": "admin_api_disabled", ...}}`.
2. Resolve `ADMIN_API_TOKEN` from env — if not set, return 403 `{"error": {"code": "admin_api_not_configured", ...}}`.
3. Extract `Authorization` header from `headers` — if missing or invalid, return 401 `{"error": {"code": "unauthorized", ...}}`.
4. Route to the appropriate view handler.

### 4.3 Privacy constraint

The token value is never logged, never included in responses, and never appears in test fixtures. Tests use short placeholder tokens (e.g., `test-token`) — never real secret-like values. The privacy scanner scans `.planning/phases/**/*.md` for secret-like values, so plan files use `REDACTED` or short placeholders (< 12 chars).

## 5. Field Allowlist for Health/Status Views

### 5.1 Allowlist design

Health/status views expose a **positive allowlist** of fields — only fields explicitly in the allowlist are included in the response. This is different from the `ALL_FORBIDDEN_KEYS` negative filter (which blocks known-bad keys). The allowlist approach is safer because it prevents accidental exposure of new secret-like fields.

**File to create:** `services/admin-console-api/src/admin_console_api/health.py`

```python
HEALTH_ALLOWED_FIELDS = frozenset({
    "service",
    "status",
    "version",
    "secrets_configured",   # boolean only — true/false
    "uptime_seconds",
    "gate_count",
    "gates_passed",
    "gates_failed",
})
```

### 5.2 Excluded fields

The following fields are **excluded** from health/status views by the allowlist:

| Excluded Field | Reason |
|----------------|--------|
| `secret_refs_configured` (map) | Exposes which secrets are set — an attack surface |
| `api_base_url` | Exposes internal endpoint URLs |
| Config paths (e.g., `config_path`, `config_file`) | Exposes filesystem layout |
| Secret reference names (e.g., `wecom_token_ref`, `aes_key_ref`) | Exposes which secrets exist |
| Any field not in `HEALTH_ALLOWED_FIELDS` | Allowlist approach — default deny |

Only `secrets_configured: true/false` (a boolean) is exposed to indicate whether secrets are configured, without revealing which ones.

### 5.3 Allowlist application

The health view collects raw status data from the runtime (feature flags, gate results, etc.) and projects it through the allowlist:

```python
def project_health(raw_status: dict) -> dict:
    return {k: v for k, v in raw_status.items() if k in HEALTH_ALLOWED_FIELDS}
```

This ensures that even if the raw status dict contains `secret_refs_configured` or `api_base_url`, those fields are never exposed.

## 6. Gate Status via Subprocess

### 6.1 Subprocess approach

The Admin Console API runs `run_v2_gates.py --json-summary` via `subprocess.run` — it does NOT import gate internals. This ensures:
- No coupling between admin-console-api and gate implementation modules.
- Gate execution runs in a clean subprocess (same as CI).
- The admin-console-api package does not need gate modules on its PYTHONPATH.

**File to create:** `services/admin-console-api/src/admin_console_api/gates.py`

```python
import json
import subprocess
from pathlib import Path

def run_gate_summary(repo_root: str | Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[4]
    script = root / "scripts" / "run_v2_gates.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--json-summary"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(root),
    )
    return json.loads(completed.stdout)
```

### 6.2 Gate status view

The `/gates` endpoint returns the gate summary:

```json
{
  "passed": true,
  "gate_count": 13,
  "gates_passed": 13,
  "gates_failed": 0,
  "gates": [
    {"name": "platform-contract", "exit_code": 0},
    ...
  ],
  "metadata": {
    "source": "subprocess:run_v2_gates.py",
    "read_only": true
  }
}
```

### 6.3 Subprocess safety

- `timeout=300` (5 minutes) prevents hangs.
- `capture_output=True` captures stdout/stderr without leaking to the API response.
- The subprocess runs with `cwd=repo_root` so gate paths resolve correctly.
- Only the parsed JSON summary is returned — raw stdout/stderr is never exposed.
- Gate internals are not imported — the admin-console-api package has no dependency on gate modules.

## 7. Feature Flag `admin_api_enabled` (defaults False)

### 7.1 Existing flag

**File:** `packages/platform-runtime/src/platform_runtime/feature_flags.py:22`

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    ...
    admin_api_enabled: bool = False
    ...
```

The flag already exists and defaults to `False`. Phase 42 does NOT modify this file (contract freeze). It wires the flag into the API handler.

### 7.2 Flag gate in the API handler

`handle_admin_get` calls `feature_flags.require_enabled("admin_api_enabled")` before processing any request. If the flag is `False`, `RuntimeFeatureDisabledError` is raised, and the handler returns 403:

```python
try:
    feature_flags.require_enabled("admin_api_enabled")
except RuntimeFeatureDisabledError:
    return 403, {"error": {"code": "admin_api_disabled", "message": "admin_api_enabled flag is False"}}
```

### 7.3 Default-off behavior

When `admin_api_enabled` is `False` (the default), the API refuses all requests — even with a valid token. This is tested by:
1. Creating a `RuntimeFeatureFlags()` with default values (all `False`).
2. Calling `handle_admin_get` with a valid token and valid path.
3. Asserting the response is 403 with `error.code == "admin_api_disabled"`.

## 8. Cursor Pagination Reuse from Phase 41

### 8.1 Direct import

The Admin Console API imports pagination utilities directly from `conversation_read_view.pagination`:

```python
from conversation_read_view.pagination import (
    clamp_limit,
    resolve_max_result_limit,
    slice_page,
    encode_cursor,
    decode_cursor,
)
```

### 8.2 Max result limit

The Admin Console API uses its own env var `ADMIN_API_MAX_LIMIT` (default 100, clamped to `[10, 1000]`) — separate from `CONVERSATION_READ_VIEW_MAX_LIMIT`. This is implemented as a thin wrapper around the same clamping logic:

```python
ADMIN_API_MAX_LIMIT_ENV = "ADMIN_API_MAX_LIMIT"

def resolve_admin_max_limit(env: Mapping[str, str] | None = None) -> int:
    source = env if env is not None else os.environ
    raw = source.get(ADMIN_API_MAX_LIMIT_ENV)
    if raw is None:
        return DEFAULT_MAX_RESULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULT_LIMIT
    return max(MIN_MAX_RESULT_LIMIT, min(value, MAX_MAX_RESULT_LIMIT))
```

The `slice_page` and cursor encode/decode functions are reused as-is — they are generic and work with any `(sort_key, occurred_at, item)` tuple list.

## 9. V2 Gate Integration Approach

### 9.1 New gate for admin-console-api

Phase 42 adds a new gate entry to `scripts/run_v2_gates.py` for the admin-console-api service. This is done in Wave 3 (42-03) after the service is created and tested.

**Gate definition (to add to `_gates()` in `run_v2_gates.py`):**

```python
Gate(
    "admin-console-api",
    (py, "-m", "unittest", "discover", "-s", "services/admin-console-api/tests"),
    (admin_api_src, read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src),
),
```

The PYTHONPATH includes:
- `admin_api_src` — the admin-console-api package itself.
- `read_view_src` — for `ContractLogReadModel` and pagination imports.
- `feedback_src` — for feedback queue imports.
- `contract_src` — for contract event schema validation.
- `platform_src` — for platform contract types.
- `platform_runtime_src` — for `RuntimeFeatureFlags` and `privacy_keys`.

### 9.2 compileall gate update

The `compileall` gate (`run_v2_gates.py:133-155`) must also include `services/admin-console-api/src` in its file list.

### 9.3 Gate count

After Phase 42, the gate count increases from 13 to 14 (adding `admin-console-api`). Phase 44 (M2 Gate Integration) will add the remaining gates and the meta-test.

### 9.4 Contract freeze verification

Phase 42 verifies that:
- `packages/platform-contract/` is not modified (SAFETY-02, SAFETY-06).
- `packages/platform-runtime/protocols.py` is not modified (SAFETY-02).
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` is not modified (the `admin_api_enabled` flag already exists from Phase 36).
- The `test_contract_count_freeze.py` tests remain green.

## 10. Privacy Considerations

### 10.1 Privacy scrub on data views

All data views (sessions, tasks, feedback) route responses through `scrub_contract_payload` from `conversation_read_view.privacy`. This raises `ValueError` if any `ALL_FORBIDDEN_KEYS` key is present in the response — same behavior as the conversation-read-view API.

### 10.2 Field allowlist on health/status views

Health/status views use a **positive allowlist** (`HEALTH_ALLOWED_FIELDS`) — only explicitly allowed fields are exposed. This prevents accidental leakage of:
- Secret reference names
- Config paths
- `secret_refs_configured` maps
- `api_base_url` values

### 10.3 Token handling

The `ADMIN_API_TOKEN` env var is read at request time (not cached) and never logged. Auth comparison uses `hmac.compare_digest` (constant-time). Tests use short placeholder tokens (< 12 chars) — never real secret-like values.

### 10.4 Plan file privacy

The privacy scanner scans `.planning/phases/**/*.md` for secret-like values. All plan files use `REDACTED` or short placeholders (< 12 chars) for any token-like values. No literal secrets appear in plan files.

## 11. Read-Only Constraint

The Admin Console API is **strictly read-only**:
- All endpoints are GET-only (the handler is `handle_admin_get`, not `handle_admin_post`/`put`/`delete`).
- No mutations to contract logs, read models, feedback queues, or any state.
- The only side effect is a subprocess call to `run_v2_gates.py --json-summary` for gate status — which itself is read-only (it runs test suites and reports results).
- No write, update, or delete operations are exposed.

## 12. Dependencies and PYTHONPATH

### 12.1 Runtime dependencies

The admin-console-api package has `dependencies = []` — pure stdlib. It imports from:
- `conversation_read_view` (read model, pagination, privacy) — via PYTHONPATH
- `platform_runtime` (feature flags, privacy keys) — via PYTHONPATH
- `feedback_service` (feedback queue) — via PYTHONPATH
- `contract_test_suite` (event stream replay, for loading records) — via PYTHONPATH

### 12.2 Test PYTHONPATH

```
PYTHONPATH=services/admin-console-api/src:services/conversation-read-view/src:packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src
```

## 13. Wave Structure

| Wave | Plan | Focus | Depends On |
|------|------|-------|------------|
| 1 | 42-01 | Service structure + static token auth + sessions/tasks/feedback views with filtering and pagination | — |
| 2 | 42-02 | Health/status views with field allowlist (exclude secrets) + gate status via subprocess | 42-01 |
| 3 | 42-03 | admin_api_enabled feature flag (defaults False) + V2 gate integration + contract freeze verification | 42-01, 42-02 |
