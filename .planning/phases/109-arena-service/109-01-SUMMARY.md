---
phase: 109-arena-service
plan: 01
status: complete
requirements: [SVC-01, SVC-02]
---

# Plan 01: Service Scaffold — Config, Auth, App, OpenAPI - Summary

## Objective

Create the `services/arena-service/` package with the foundational service scaffold: `ArenaServiceConfig` (127.0.0.1:8001 binding), `ArenaServiceAuth` (local token + localhost-only check), `ArenaServiceApp` (framework-free HTTP routing with 5 arena endpoints), and OpenAPI document generation. This mirrors the Gateway's stdlib-only pattern (`GatewayApp`, `GatewayConfig`, `GatewayAuth`) but adds the NEW localhost-binding enforcement and token auth that Gateway does not have.

## Tasks Completed

### Task 1: config.py + auth.py — ArenaServiceConfig + ArenaServiceAuth

**Files created:**
- `services/arena-service/pyproject.toml` — Package config (stdlib-only, `dependencies = []`, `package-dir = { "" = "src" }`)
- `services/arena-service/src/arena_service/__init__.py` — Re-exports for `ArenaServiceConfig`, `ArenaServiceAuth`, `ArenaServiceApp`, `ArenaServiceAuthError`, `AuthContext`, `build_openapi_document`, `render_openapi_json`
- `services/arena-service/src/arena_service/config.py` — `ArenaServiceConfig` frozen slotted dataclass with 127.0.0.1:8001 defaults, `from_env` classmethod, `generate_token` staticmethod
- `services/arena-service/src/arena_service/auth.py` — `ArenaServiceAuth` (constant-time token compare via `secrets.compare_digest`), `ArenaServiceAuthError`, `AuthContext` frozen slotted dataclass, `check_localhost`/`require_localhost` methods
- `services/arena-service/tests/__init__.py` — Empty test package init
- `services/arena-service/tests/test_auth.py` — 10 tests covering all config + auth behaviors

**Verification:** `python -m unittest discover -s services/arena-service/tests -p "test_auth.py"` → 10 tests, OK (exit 0)

**Commit:** `feat(109-01): config.py + auth.py — ArenaServiceConfig + ArenaServiceAuth`

### Task 2: app.py + openapi.py — ArenaServiceApp routing + OpenAPI docs

**Files created:**
- `services/arena-service/src/arena_service/app.py` — `ArenaServiceApp` with 6 operation constants, `_parse_route` for 5 arena endpoints + OpenAPI, `dispatch` method (localhost → auth → routing order), handler stubs delegating to injected engine, `ArenaServiceError`
- `services/arena-service/src/arena_service/openapi.py` — `build_openapi_document` (OpenAPI 3.1 with all 5 endpoints + OpenAPI endpoint, BearerAuth security scheme), `render_openapi_json` (deterministic JSON), component schemas (CreateArenaRequest, ArenaHandle, ArenaStatus, UserActionRequest, ArenaEventFrame, OpenApiDocument, Error)
- `services/arena-service/tests/test_endpoints.py` — 19 tests covering all 13 behaviors (operation constants, _parse_route, auth-before-routing, engine delegation, OpenAPI structure/security)

**Verification:** `python -m unittest discover -s services/arena-service/tests -p "test_endpoints.py"` → 19 tests, OK (exit 0)

**Commit:** `feat(109-01): app.py + openapi.py — ArenaServiceApp routing + OpenAPI docs`

## Requirements Met

### SVC-01: Local Binding + Token Auth
- `ArenaServiceConfig` defaults to `bind_host="127.0.0.1"`, `bind_port=8001` — NEVER binds to 0.0.0.0
- `ArenaServiceAuth.require_localhost` rejects non-localhost connections with `403 forbidden_remote` BEFORE auth check
- `ArenaServiceAuth.require_auth` rejects missing/wrong token with `401 unauthorized` using constant-time comparison (`secrets.compare_digest`)
- `ArenaServiceApp.dispatch` applies localhost check → auth → routing in that order — NO endpoint bypasses auth

### SVC-02: Endpoints
- `POST /v1/arena` — create arena (delegates to `engine.create_arena`)
- `GET /v1/arena/{arena_id}/stream` — SSE stream (handled by `stream()` method in Plan 02)
- `POST /v1/arena/{arena_id}/cancel` — cancel arena (delegates to `engine.cancel_arena`)
- `POST /v1/arena/{arena_id}/action` — user action (delegates to `engine.submit_user_action`)
- `GET /v1/arena/{arena_id}/status` — status query (delegates to `engine.query_status`)
- `GET /v1/openapi` — OpenAPI 3.1 document (requires auth)
- OpenAPI 3.1 document covers all 5 endpoints with BearerAuth security scheme

## Artifacts Produced

- `arena_service.config.ArenaServiceConfig` — frozen config with 127.0.0.1:8001 binding defaults
- `arena_service.config.ArenaServiceConfig.from_env` — environment-based config construction
- `arena_service.config.ArenaServiceConfig.generate_token` — URL-safe token generation (43 chars)
- `arena_service.auth.ArenaServiceAuth` — local token + localhost-only enforcement
- `arena_service.auth.ArenaServiceAuthError` — auth error with status/code/message
- `arena_service.auth.AuthContext` — frozen slotted auth context dataclass
- `arena_service.app.ArenaServiceApp` — framework-free HTTP routing with 5 arena endpoints
- `arena_service.app.OPERATION_CREATE_ARENA` / `OPERATION_STREAM_ARENA` / `OPERATION_CANCEL_ARENA` / `OPERATION_USER_ACTION` / `OPERATION_STATUS_ARENA` / `OPERATION_GET_OPENAPI` — operation constants
- `arena_service.openapi.build_openapi_document` — OpenAPI 3.1 spec for all arena endpoints
- `arena_service.openapi.render_openapi_json` — deterministic JSON rendering
- `tests/test_auth.py::ArenaServiceConfigTests` + `ArenaServiceAuthTests` — 10 tests
- `tests/test_endpoints.py::ArenaParseRouteTests` + `ArenaDispatchTests` + `ArenaOpenApiTests` — 19 tests

## Key Design Decisions

1. **Framework-free, stdlib-only** — mirrors Gateway pattern, `dependencies = []`, no aiohttp/FastAPI
2. **Localhost check before auth** — `dispatch` calls `require_localhost` BEFORE `require_auth`, ensuring non-localhost connections are rejected with 403 before any token validation
3. **Constant-time token compare** — uses `secrets.compare_digest` to prevent timing attacks
4. **Engine injection** — `ArenaServiceApp` accepts an `engine` parameter (wired in Plan 05); when `None`, handlers return `501 not_implemented`
5. **Stream endpoint routing** — `OPERATION_STREAM_ARENA` is routed by `_parse_route` but handled by the `stream()` method (Plan 02), not `dispatch`; if it reaches `dispatch`, a `405 use_stream_endpoint` error is returned
6. **Trailing slash tolerance** — `_parse_route` strips empty path segments, supporting trailing slashes on all endpoints
7. **OpenAPI security** — all operations have `BearerAuth` security requirements applied; no operation bypasses auth

## Test Results

- Task 1: 10 tests, all passing (exit 0)
- Task 2: 19 tests, all passing (exit 0)
- Total: 29 tests, all passing
