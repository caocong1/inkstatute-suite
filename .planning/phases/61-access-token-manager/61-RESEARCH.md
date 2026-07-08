# Phase 61: Access Token Manager — Technical Research

**Phase:** 61 — Access Token Manager
**Requirements:** EGRESS-01
**Depends on:** Phase 60 (complete)
**Researched:** 2026-07-08
**Status:** Complete

## User Constraints

### Decisions (from CONTEXT.md)

Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions. `[VERIFIED: .planning/phases/61-access-token-manager/61-CONTEXT.md]`

### Deferred Ideas

None — discuss phase skipped. `[VERIFIED: 61-CONTEXT.md]`

## Project Constraints (from AGENTS.md)

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- WeCom keys, callback tokens, encoding AES keys, runtime message payloads, and media files must not be committed. `[VERIFIED: AGENTS.md]`
- Keep changes scoped to the active GSD phase and its plan. `[VERIFIED: AGENTS.md]`
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it. `[VERIFIED: AGENTS.md]`
- Prefer structured parsers and schema validators over ad hoc string parsing. `[VERIFIED: AGENTS.md]`
- `dependencies = []` invariant must hold for QQBot channel package — use Python stdlib only. `[VERIFIED: codebase — packages/channels/qqbot/pyproject.toml, packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`
- All 24 existing V2 gates must remain green throughout v1.8 (ADAPTER-04 cross-cutting safety). `[VERIFIED: .planning/ROADMAP.md line 49]`
- Frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified. `[VERIFIED: .planning/ROADMAP.md line 32]`
- QQBot adapter must NOT import from `wecom_service` (enforced by `test_no_wecom_import.py`). `[VERIFIED: .planning/REQUIREMENTS.md ADAPTER-03]`

## Critical Finding: `dependencies = []` + Async HTTP Conflict

### The Problem

The QQ Bot `getAppAccessToken` endpoint is an HTTPS POST request. The token manager must be async (it uses `asyncio.Lock` for single-flight refresh per EGRESS-01 SC-3). Python's stdlib `urllib.request` is **synchronous** — it blocks the event loop. The project has **no async HTTP client** as a dependency:

- `httpx` is NOT installed at the project level `[VERIFIED: codebase grep — no top-level httpx dependency in any pyproject.toml]`
- `aiohttp` is NOT installed `[VERIFIED: codebase grep — no aiohttp import anywhere]`
- The qqbot package `pyproject.toml` has `dependencies = []` `[VERIFIED: packages/channels/qqbot/pyproject.toml]`
- The `test_v1_8_safety_baseline.py` test asserts the literal string `dependencies = []` exists in `pyproject.toml` `[VERIFIED: packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`

### Recommended Solution: Transport Protocol Injection + Lazy `urllib` in Thread Executor

Follow the **exact pattern established by `OllamaRunner`** in `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py`:

1. **Define a `TokenTransport` Protocol** with an async method `fetch_token(app_id, client_secret) -> dict`.
2. **Provide a `FakeTokenTransport`** for tests (no HTTP, no network).
3. **Provide a `UrllibTokenTransport`** that lazily imports `urllib.request` inside the method body and runs the blocking call via `asyncio.to_thread()` (Python 3.9+, project requires 3.11+). This keeps the event loop unblocked while preserving `dependencies = []`.
4. **The token manager accepts an injected transport** — tests inject `FakeTokenTransport`, production injects `UrllibTokenTransport`.

This is the **proven codebase pattern**. The `OllamaRunner` does exactly this: `OllamaTransport` Protocol + `FakeOllamaTransport` for tests + lazy `urllib.request` in `_real_http_call()` for production. `[VERIFIED: packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py]`

**Why `asyncio.to_thread()` is the right choice:**
- Python 3.11+ (project minimum) has `asyncio.to_thread()` in stdlib `[VERIFIED: Python 3.11 stdlib]`
- It runs a synchronous function in a separate thread, returning an awaitable
- `urllib.request.urlopen()` is blocking; wrapping it in `asyncio.to_thread()` prevents event-loop blocking
- QQ Bot token refresh is infrequent (every ~7140s), so thread overhead is negligible
- No external dependency needed — pure stdlib

**Alternative considered and rejected:** Adding `httpx` as an optional dependency via `[project.optional-dependencies]`. Rejected because:
1. The `test_v1_8_safety_baseline.py` test checks for the literal string `dependencies = []` — adding an `[project.optional-dependencies]` section does not break this test, but the research SUMMARY.md recommendation to use `httpx` as an optional extra was for Phase 62 (egress sender), not Phase 61 (token manager). `[VERIFIED: .planning/research/SUMMARY.md — "httpx 0.28.1: Async HTTP client for QQ Bot OpenAPI calls"]`
2. For Phase 61 specifically, the token endpoint is a single POST call with no connection pooling benefit. `urllib` + `asyncio.to_thread()` is sufficient and preserves the zero-dependency invariant cleanly.
3. The `OllamaRunner` precedent proves `urllib` + lazy import + transport injection works for async code in this codebase.

**Prescriptive recommendation:** Use `urllib.request` + `asyncio.to_thread()` + transport injection for Phase 61. If Phase 62 (egress sender) needs connection pooling or more complex HTTP, it can revisit `httpx` as an optional extra then. Phase 61's token manager is a single endpoint with infrequent calls.

## QQ Bot getAppAccessToken API (Verified from Official Docs)

### Endpoint

| Property | Value |
|----------|-------|
| HTTP URL | `https://bots.qq.com/app/getAppAccessToken` |
| HTTP Method | `POST` |
| Content-Type | `application/json` |

`[CITED: bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html — 获取调用凭证]`

### Request Format

```json
{
  "appId": "APPID",
  "clientSecret": "CLIENTSECRET"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `appId` | string | Yes | Obtained from the Open Platform admin console |
| `clientSecret` | string | Yes | Obtained from the Open Platform admin console |

`[CITED: bot.q.qq.com — api-use.html 请求参数]`

### Response Format

```json
{
  "access_token": "ACCESS_TOKEN",
  "expires_in": 7200
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `access_token` | string | The obtained credential |
| `expires_in` | number | Credential validity time, in seconds. Currently a value within 7200 seconds. |

`[CITED: bot.q.qq.com — api-use.html 返回参数]`

### Error Code

| Code | Value |
|------|-------|
| 0 | ok |

`[CITED: bot.q.qq.com — api-use.html 错误码]`

### Token Lifecycle (Critical for Cache Logic)

From the official docs "其他说明" (Other Notes):

> 目前 `access_token` 生命周期默认 `7200` 秒，每次请求不会刷新新的 `access_token`，开发者需要在过期后自行刷新 `access_token`，保证调用链路权限正常。
>
> 在上一个 `access_token` 接近过期时间 `60` 秒内，获取 `access_token` 时，会获得一个新的 `access_token`，老的 `access_token` 在这个`60`秒内仍然有效。

**Translation/interpretation:**
1. The `access_token` lifetime defaults to **7200 seconds** (2 hours).
2. Each request does NOT refresh an existing token — the developer must refresh after expiry.
3. Within the **last 60 seconds** before expiry, requesting a new token returns a NEW `access_token`, and the OLD token remains valid for those 60 seconds (overlap window).

`[CITED: bot.q.qq.com — api-use.html 其他说明]`

**Implication for the token manager:**
- Cache the token with `expires_in` from the response (default 7200s, but use the actual returned value).
- Auto-refresh **60 seconds before expiry** (per EGRESS-01 SC-2 and the official docs' 60s overlap window).
- The 60s overlap means there is no downtime during refresh — old token works while new one is obtained.

### Authorization Header for Downstream API Calls

All QQ Bot OpenAPI calls (not the token endpoint itself) use:

```
Authorization: QQBot {ACCESS_TOKEN}
```

The base URL for OpenAPI calls is `https://api.sgroup.qq.com`. `[CITED: bot.q.qq.com — api-use.html 鉴权方式]`

**Note:** The token manager itself does NOT send the `Authorization` header — it acquires the token. Phase 62 (egress sender) will use the token in the `Authorization` header. Phase 61 only needs to acquire and cache the token.

## Standard Stack

### Target Module

- **`packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`** (NEW) — QQ Bot access token acquisition, caching, auto-refresh, and single-flight concurrent refresh. Public API:
  - `TokenManager` class — async token manager with `async get_token() -> str` method
  - `TokenTransport` Protocol — async transport abstraction for the HTTP call
  - `FakeTokenTransport` — test transport (no HTTP, configurable response/error)
  - `UrllibTokenTransport` — production transport (lazy `urllib.request` + `asyncio.to_thread`)
  - `TokenError` — exception for token acquisition failures

`[ASSUMED — module name from ROADMAP SC-1 ("token_manager.py acquires access token")]`

### Existing Modules to Reuse

- **`QQBotChannelConfig`** (`packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py`) — already has `app_id_ref` and `app_secret_ref` fields (reference-only, no raw secrets). `[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py:11-12]`
- **`asyncio`** (stdlib) — `asyncio.Lock` for single-flight refresh, `asyncio.to_thread` for non-blocking urllib. `[VERIFIED: Python 3.11+ stdlib]`
- **`urllib.request`** + **`urllib.error`** (stdlib) — HTTP POST for token acquisition, lazy-imported inside method body. `[VERIFIED: packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py:170-171 — precedent for lazy urllib import]`
- **`json`** (stdlib) — request/response serialization. `[VERIFIED: stdlib]`
- **`time`** (stdlib) — `time.monotonic()` for cache expiry tracking (injectable clock for tests). `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:10 — `_default_clock` pattern with injectable clock]`

### Test Framework

- **`unittest`** (stdlib) — matches all existing qqbot tests. `[VERIFIED: packages/channels/qqbot/tests/]`
- **`unittest.IsolatedAsyncioTestCase`** — for async test methods (precedent: `packages/backends/provider_model/tests/test_ollama_runner.py:55`). `[VERIFIED: codebase — OllamaRunnerTests uses IsolatedAsyncioTestCase]`
- No pytest-specific features used.

## Architecture Patterns

### Where the Token Manager Fits

```
Phase 61: token_manager.py
  ├── TokenTransport (Protocol) — async fetch_token(app_id, client_secret) -> dict
  ├── FakeTokenTransport — test transport (no HTTP)
  ├── UrllibTokenTransport — production transport (lazy urllib + asyncio.to_thread)
  └── TokenManager — cache + auto-refresh + single-flight
        ├── get_token() -> str  (async, public API)
        ├── _refresh()          (async, private, lock-guarded)
        └── _is_near_expiry()   (sync, private, checks monotonic clock)

Phase 62 (future): sender.py will call token_manager.get_token() to get
  the access token for the Authorization header in QQ OpenAPI calls.
```

`[ASSUMED — architecture inferred from ROADMAP SC-1 through SC-4 + OllamaRunner transport injection pattern]`

### Module Layout (Phase 61 additions)

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── __init__.py          # exports QQBotChannelAdapter, QQBotChannelConfig
├── _ed25519.py          # Phase 59: vendored RFC 8032 Ed25519
├── signature.py         # Phase 59: signature verify + validation challenge
├── config.py            # Phase 59: bot_secret_ref field (app_id_ref, app_secret_ref already exist)
├── adapter.py           # Phase 59/60: signature verify + normalization delegation
├── normalization.py     # Phase 60: gateway envelope parser + event normalizer
└── token_manager.py     # NEW: access token acquisition + cache + auto-refresh + single-flight
```

`[ASSUMED — module placement follows Phase 59/60 pattern of adding new modules to the qqbot package]`

### Transport Injection Pattern (from OllamaRunner)

The `OllamaRunner` in `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py` establishes the exact pattern to follow:

1. **Protocol** (`OllamaTransport`): async method `create_chat_completion(request_payload) -> JsonObject`
2. **Fake** (`FakeOllamaTransport`): stores `response` and `error`, returns/raises in the async method
3. **Real** (`OllamaRunner._real_http_call`): lazy `import urllib.request` inside the method, `urllib.request.urlopen()` with timeout, parse JSON response
4. **Runner** (`OllamaRunner`): accepts `transport: OllamaTransport | None = None`; if transport is None, calls `_real_http_call`; if transport is provided, calls `transport.create_chat_completion()`

`[VERIFIED: packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py:55-107, 170-193]`

**QQBot adaptation:**
- `TokenTransport` Protocol: `async fetch_token(app_id: str, client_secret: str) -> dict`
- `FakeTokenTransport`: configurable `response` dict and optional `error` exception
- `UrllibTokenTransport`: lazy `urllib.request` inside `fetch_token`, wrapped in `asyncio.to_thread`
- `TokenManager`: accepts `transport: TokenTransport | None = None`; if None, uses `UrllibTokenTransport`

### asyncio.Lock Single-Flight Pattern

The `asyncio.Lock` pattern for single-flight refresh is established in the codebase by `RateLimiter` and `CostTracker`:

```python
# From rate_limiter.py (VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:59)
self._lock = asyncio.Lock()

async def check_rpm(self, ...):
    async with self._lock:
        # critical section — only one coroutine at a time
        ...
```

**Single-flight token refresh pattern:**

```python
async def get_token(self) -> str:
    # Fast path: cached token still valid (no lock needed)
    if self._token and not self._is_near_expiry():
        return self._token

    # Slow path: acquire lock, re-check (another coroutine may have refreshed)
    async with self._lock:
        if self._token and not self._is_near_expiry():
            return self._token  # another coroutine already refreshed

        # This coroutine does the refresh
        response = await self._transport.fetch_token(self._app_id, self._client_secret)
        self._token = response["access_token"]
        self._expires_at = self._clock() + response["expires_in"]
        return self._token
```

**Key points:**
1. The fast path (token valid) does NOT acquire the lock — avoids contention under concurrent egress.
2. The slow path acquires the lock, then **re-checks** if the token is still expired — another coroutine may have refreshed it while this one was waiting for the lock.
3. Only the coroutine that finds the token still expired after acquiring the lock performs the actual HTTP refresh.
4. All coroutines waiting on the lock get the refreshed token from the re-check.

`[VERIFIED: pattern confirmed by rate_limiter.py and cost_tracker.py asyncio.Lock usage; single-flight re-check pattern is standard asyncio practice]`

### Cache Structure

```python
@dataclass
class _TokenCache:
    token: str
    expires_at: float  # monotonic timestamp
```

Or simply store as instance attributes on `TokenManager`:

```python
class TokenManager:
    def __init__(self, ...):
        self._token: str | None = None
        self._expires_at: float = 0.0  # monotonic timestamp of expiry
        self._lock = asyncio.Lock()
```

**Expiry check:**
```python
def _is_near_expiry(self) -> bool:
    # Refresh 60s before actual expiry (EGRESS-01 SC-2)
    return self._clock() >= (self._expires_at - self._refresh_margin)
```

Where `self._refresh_margin = 60.0` (seconds before expiry to trigger refresh).

`[VERIFIED: EGRESS-01 SC-2 — "auto-refreshed 60s before expiry"; CITED: bot.q.qq.com — 60s overlap window]`

### Injectable Clock for Tests

Follow the `RateLimiter` pattern with an injectable clock:

```python
# From rate_limiter.py (VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:10)
def _default_clock() -> float:
    return time.monotonic()

class TokenManager:
    def __init__(self, ..., clock: Callable[[], float] | None = None):
        self._clock = clock or _default_clock
```

Tests inject a controllable clock to simulate time passing without real delays. `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:57-58, packages/model-gateway/tests/test_rate_limiter.py]`

### Credential Injection (No Raw Secrets in Code)

The `QQBotChannelConfig` already has `app_id_ref` and `app_secret_ref` fields (reference-only strings, NOT raw secrets). `[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py:11-12]`

**Pattern:** The token manager should accept `app_id` and `client_secret` as constructor parameters (strings). The host/caller is responsible for resolving `app_id_ref` → actual `app_id` from the runtime secret store. The token manager itself never reads env vars or files — it receives already-resolved credentials.

```python
class TokenManager:
    def __init__(
        self,
        *,
        app_id: str,
        client_secret: str,
        transport: TokenTransport | None = None,
        clock: Callable[[], float] | None = None,
        refresh_margin: float = 60.0,
    ):
        ...
```

**Tests use fixture credentials** — never real secrets. The test constants should be clearly labeled as fixture values:

```python
FIXTURE_APP_ID = "fixture-app-id-001"
FIXTURE_CLIENT_SECRET = "fixture-client-secret-001"
```

`[VERIFIED: AGENTS.md — "Never commit secrets, tokens..."; VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py — ref-only pattern]`

## Don't Hand-Roll

- **HTTP client**: Use stdlib `urllib.request` (lazy import inside method body). Do NOT add `httpx`, `aiohttp`, or `requests` as a dependency. `[VERIFIED: packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py:170-171 — precedent]`
- **Async lock**: Use `asyncio.Lock` (stdlib). Do NOT implement custom mutex logic. `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:59, cost_tracker.py:50]`
- **Thread offloading**: Use `asyncio.to_thread()` (Python 3.9+ stdlib). Do NOT manually manage `ThreadPoolExecutor` for a single blocking call. `[VERIFIED: Python 3.11+ stdlib]`
- **JSON parsing**: Use `json.loads()` / `json.dumps()` (stdlib). Do NOT use `eval()` or custom parsers. `[VERIFIED: AGENTS.md — "Prefer structured parsers"]`
- **Time tracking**: Use `time.monotonic()` (stdlib) for cache expiry. Do NOT use `time.time()` (wall clock can go backwards). `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:10 — uses time.monotonic()]`
- **Token transport abstraction**: Use `typing.Protocol` (stdlib). Do NOT use ABCs for this — Protocol is structural and matches the `OllamaTransport` precedent. `[VERIFIED: packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py:43-52]`

## Common Pitfalls

1. **Top-level `import urllib`**: The `OllamaRunner` test (`test_ollama_runner.py:296-306`) explicitly checks that `urllib` is NOT imported at module top level. While the qqbot package does not currently have this test, the established codebase convention is lazy import inside method bodies. Import `urllib.request` inside the `fetch_token` method, NOT at module top level. `[VERIFIED: packages/backends/provider_model/tests/test_ollama_runner.py:296-306]`

2. **Blocking the event loop with `urllib`**: `urllib.request.urlopen()` is synchronous and blocks the event loop. MUST wrap it in `asyncio.to_thread()` to avoid blocking. Direct `await` on a synchronous call does NOT make it async — it still blocks. `[VERIFIED: Python asyncio documentation]`

3. **Missing the re-check after acquiring the lock**: After `async with self._lock:`, another coroutine may have already refreshed the token while this one was waiting. MUST re-check `self._is_near_expiry()` inside the lock before refreshing. Without the re-check, multiple coroutines sequentially refresh the token (defeating single-flight). `[VERIFIED: standard asyncio.Lock single-flight pattern]`

4. **Using `time.time()` instead of `time.monotonic()`**: Wall clock time (`time.time()`) can go backwards (NTP adjustments, timezone changes). Cache expiry MUST use `time.monotonic()` which is monotonically increasing. `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:10]`

5. **Hardcoding `expires_in = 7200`**: The API returns `expires_in` in the response. While the docs say "currently 7200 seconds", the value could change. Use the actual `response["expires_in"]` value for cache TTL, not a hardcoded 7200. The 60s refresh margin is the only hardcoded constant. `[CITED: bot.q.qq.com — "目前是7200秒之内的值" (currently a value within 7200 seconds)]`

6. **Storing the raw `access_token` in logs or contract events**: The `access_token` is a secret credential. It must NOT appear in logs, error messages, metadata, or contract events. Error messages must be sanitized (no token, no URL, no credentials). `[VERIFIED: AGENTS.md — "Never commit secrets, tokens..."; VERIFIED: .planning/research/SUMMARY.md — "Credential leakage of the QQ access_token into logs or contract events is a HIGH-severity risk"]`

7. **Not handling API error responses**: The API could return non-200 status codes, malformed JSON, or missing `access_token`/`expires_in` fields. The transport must raise a `TokenError` with a sanitized message. The token manager must propagate this error to callers (who decide retry/fail behavior). `[ASSUMED — defensive error handling per AGENTS.md coding rules]`

8. **Importing from `wecom_service`**: The `test_no_wecom_import.py` test uses AST inspection. The new `token_manager.py` must NOT import from `wecom_service`. The test file must be updated to add `token_manager.py` coverage. `[VERIFIED: packages/channels/qqbot/tests/test_no_wecom_import.py]`

9. **Breaking `dependencies = []`**: Do NOT add any package to `pyproject.toml` dependencies. Use stdlib only (`asyncio`, `json`, `time`, `urllib` (lazy), `typing`, `dataclasses`). `[VERIFIED: packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`

10. **Not making the clock injectable**: Without an injectable clock, testing token expiry/refresh requires `asyncio.sleep(7200)` which makes tests impractically slow. The clock MUST be injectable, following the `RateLimiter` pattern. `[VERIFIED: packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py:57-58]`

11. **Using `asyncio.Lock` across different event loops**: `asyncio.Lock()` created in `__init__` binds to the running event loop. In Python 3.10+, `asyncio.Lock()` no longer takes a `loop` parameter and binds lazily. Tests using `IsolatedAsyncioTestCase` create a new event loop per test method — the lock should be created in `__init__` and will bind correctly when first used. `[VERIFIED: Python 3.10+ asyncio changes]`

## Code Examples

### token_manager.py — Transport Protocol + Fakes

```python
"""QQ Bot access token manager — acquire, cache, auto-refresh, single-flight.

Uses asyncio.Lock for single-flight concurrent refresh and a transport
protocol for HTTP calls (lazy urllib in production, fake transport in tests).
No external dependencies — stdlib only (dependencies = [] invariant preserved).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Protocol


def _default_clock() -> float:
    return time.monotonic()


class TokenTransport(Protocol):
    """Transport abstraction for the QQ Bot getAppAccessToken endpoint.

    Tests inject a fake transport so no real HTTP client or network
    access is required.
    """

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        """Return the parsed JSON response from getAppAccessToken."""
        ...


class FakeTokenTransport:
    """Convenience fake transport for tests (no HTTP client required)."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.call_count = 0
        self.last_app_id: str | None = None
        self.last_client_secret: str | None = None

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        self.call_count += 1
        self.last_app_id = app_id
        self.last_client_secret = client_secret
        if self.error is not None:
            raise self.error
        return self.response or {"access_token": "fixture-token", "expires_in": 7200}


class TokenError(Exception):
    """Token acquisition failure with a sanitized message."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UrllibTokenTransport:
    """Production transport using lazy urllib.request + asyncio.to_thread.

    The HTTP client (urllib.request from stdlib) is imported inside
    fetch_token only — never at module top level — so the package
    imports cleanly without any external HTTP library.
    """

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._blocking_fetch, app_id, client_secret)

    def _blocking_fetch(self, app_id: str, client_secret: str) -> dict[str, Any]:
        import urllib.request
        import urllib.error

        url = "https://bots.qq.com/app/getAppAccessToken"
        data = json.dumps({"appId": app_id, "clientSecret": client_secret}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            raise TokenError(
                "QQ Bot token request failed",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TokenError("QQ Bot token endpoint unreachable") from exc
```

`[ASSUMED — code structure follows OllamaRunner pattern + EGRESS-01 requirements]`

### token_manager.py — TokenManager Class

```python
class TokenManager:
    """QQ Bot access token manager with cache, auto-refresh, and single-flight.

    Acquires the access token via POST /getAppAccessToken using appId +
    clientSecret, caches it with the returned expires_in TTL, auto-refreshes
    60 seconds before expiry, and ensures concurrent refresh is single-flight
    via asyncio.Lock (no duplicate token requests).
    """

    def __init__(
        self,
        *,
        app_id: str,
        client_secret: str,
        transport: TokenTransport | None = None,
        clock: Callable[[], float] | None = None,
        refresh_margin: float = 60.0,
    ) -> None:
        self._app_id = app_id
        self._client_secret = client_secret
        self._transport = transport or UrllibTokenTransport()
        self._clock = clock or _default_clock
        self._refresh_margin = refresh_margin
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        """Return a valid access token, refreshing if needed.

        Fast path: return cached token if not near expiry (no lock).
        Slow path: acquire lock, re-check, refresh if still expired.
        """
        if self._token is not None and not self._is_near_expiry():
            return self._token

        async with self._lock:
            # Re-check: another coroutine may have refreshed while we waited.
            if self._token is not None and not self._is_near_expiry():
                return self._token

            response = await self._transport.fetch_token(
                self._app_id, self._client_secret
            )
            self._token = self._extract_token(response)
            self._expires_at = self._clock() + self._extract_expiry(response)
            return self._token

    def _is_near_expiry(self) -> bool:
        """Return True if the token expires within the refresh margin."""
        return self._clock() >= (self._expires_at - self._refresh_margin)

    @staticmethod
    def _extract_token(response: dict[str, Any]) -> str:
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise TokenError("QQ Bot token response missing access_token")
        return token

    @staticmethod
    def _extract_expiry(response: dict[str, Any]) -> float:
        expires_in = response.get("expires_in")
        if not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise TokenError("QQ Bot token response missing or invalid expires_in")
        return float(expires_in)

    def invalidate(self) -> None:
        """Force the next get_token() call to refresh (e.g., after a 401)."""
        self._token = None
        self._expires_at = 0.0
```

`[ASSUMED — code structure follows EGRESS-01 SC-1 through SC-4 + OllamaRunner + RateLimiter patterns]`

### Test Example — Lifecycle

```python
class TokenManagerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_call_acquires_token(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
            clock=lambda: now,
        )

        token = await manager.get_token()

        self.assertEqual(token, "token-001")
        self.assertEqual(transport.call_count, 1)

    async def test_cached_token_reused_within_validity(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
            clock=lambda: now,
        )

        await manager.get_token()
        now = 5000.0  # 4000s later, still within 7200 - 60 = 7140s
        token = await manager.get_token()

        self.assertEqual(token, "token-001")
        self.assertEqual(transport.call_count, 1)  # no second HTTP call

    async def test_auto_refresh_60s_before_expiry(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
            clock=lambda: now,
        )

        await manager.get_token()
        # Move to 7141s later — past the 60s margin (7200 - 60 = 7140)
        now = 1000.0 + 7141.0
        transport.response = {"access_token": "token-002", "expires_in": 7200}
        token = await manager.get_token()

        self.assertEqual(token, "token-002")
        self.assertEqual(transport.call_count, 2)  # refreshed
```

`[ASSUMED — test structure follows OllamaRunnerTests + RateLimiter test patterns]`

### Test Example — Concurrent Refresh Single-Flight

```python
class TokenManagerConcurrentRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_refresh_is_single_flight(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
            clock=lambda: now,
        )

        # First call to populate cache
        await manager.get_token()
        self.assertEqual(transport.call_count, 1)

        # Move past expiry margin
        now = 1000.0 + 7141.0

        # 10 concurrent get_token() calls — only 1 should trigger refresh
        transport.response = {"access_token": "token-002", "expires_in": 7200}
        results = await asyncio.gather(*[manager.get_token() for _ in range(10)])

        self.assertEqual(transport.call_count, 2)  # only 1 refresh, not 10
        self.assertTrue(all(t == "token-002" for t in results))
```

`[ASSUMED — test verifies EGRESS-01 SC-3 single-flight requirement]`

### Test Example — Error Handling

```python
class TokenManagerErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_error_raises_token_error(self) -> None:
        transport = FakeTokenTransport(error=TokenError("auth failed", status_code=401))
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_missing_access_token_in_response(self) -> None:
        transport = FakeTokenTransport(response={"expires_in": 7200})  # no access_token
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_missing_expires_in_in_response(self) -> None:
        transport = FakeTokenTransport(response={"access_token": "token-001"})
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_invalidate_forces_refresh(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-secret",
            transport=transport,
        )

        await manager.get_token()
        self.assertEqual(transport.call_count, 1)

        manager.invalidate()
        await manager.get_token()
        self.assertEqual(transport.call_count, 2)  # forced refresh
```

`[ASSUMED — test verifies EGRESS-01 SC-4 error handling requirement]`

### Test Example — No Top-Level urllib Import

```python
class TokenManagerImportSafetyTests(unittest.TestCase):
    """Verify token_manager.py has no top-level urllib import (lazy import only)."""

    def test_no_top_level_urllib_import(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "inkstatute_channels_qqbot"
            / "token_manager.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if line.startswith(" ") or line.startswith("\t"):
                continue
            self.assertFalse(
                stripped.startswith("import urllib"),
                f"top-level 'import urllib' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from urllib"),
                f"top-level 'from urllib' forbidden: {line!r}",
            )
```

`[VERIFIED: pattern from packages/backends/provider_model/tests/test_ollama_runner.py:288-316]`

## Validation Architecture

### Test Files

1. **`tests/test_token_manager.py`** (NEW) — Unit tests for `token_manager.py`:
   - **Lifecycle (SC-1, SC-2):**
     - First call acquires token via `fetch_token` (transport called once)
     - Cached token reused within validity (transport not called again)
     - Auto-refresh 60s before expiry (transport called again at expiry margin)
     - `expires_in` from response used as TTL (not hardcoded 7200)
     - `invalidate()` forces next call to refresh
   - **Concurrent refresh single-flight (SC-3):**
     - 10 concurrent `get_token()` calls after expiry → only 1 transport call
     - All 10 coroutines receive the same refreshed token
     - Lock re-check: coroutine that waited gets the already-refreshed token
   - **Error handling (SC-4):**
     - HTTP error (401, 500) → `TokenError` raised
     - Network error → `TokenError` raised
     - Missing `access_token` in response → `TokenError` raised
     - Missing `expires_in` in response → `TokenError` raised
     - Invalid `expires_in` (zero, negative, non-numeric) → `TokenError` raised
     - Error message does NOT contain the token or credentials (sanitized)
   - **Import safety:**
     - No top-level `import urllib` or `from urllib` in `token_manager.py`
     - No `import httpx` or `import aiohttp` anywhere

2. **`tests/test_no_wecom_import.py`** (MODIFIED) — Add `token_manager.py` AST coverage:
   - New test method `test_token_manager_does_not_import_wecom_service`

3. **Existing tests must remain green:**
   - `test_v1_8_safety_baseline.py` — `dependencies = []` still holds, 6 Protocol methods, 4 FeedbackSource values
   - `test_contract_freeze_not_violated.py` — frozen contract surfaces unchanged
   - `test_no_wecom_import.py` — all source files including new `token_manager.py` pass
   - `test_feature_flag.py` — flag still default-off
   - `test_signature.py` — Phase 59 signature tests
   - `test_normalization.py` — Phase 60 normalization tests
   - All other qqbot tests

`[ASSUMED — test file structure follows Phase 59/60 pattern + SC-4 "Tests cover lifecycle, concurrent refresh, and error handling"]`

### V2 Gate Verification

Run `python3 scripts/run_v2_gates.py` to verify all 24+ V2 gates remain green (ADAPTER-04). Phase 60 confirmed gates green. `[VERIFIED: .planning/phases/60-qq-event-normalization/60-VERIFICATION.md]`

### Test Execution

```bash
cd packages/channels/qqbot
python -m pytest tests/ -v
# or
python -m unittest discover -s tests -v
```

`[VERIFIED: existing qqbot test execution pattern]`

## Summary of Key Decisions for the Planner

1. **Create `token_manager.py`** as a new module in `packages/channels/qqbot/src/inkstatute_channels_qqbot/`. Contains: `TokenTransport` Protocol, `FakeTokenTransport`, `UrllibTokenTransport`, `TokenError`, `TokenManager` class.

2. **Transport injection pattern** — follow the `OllamaRunner` precedent: Protocol + Fake + lazy urllib. Tests inject `FakeTokenTransport`; production uses `UrllibTokenTransport` with lazy `urllib.request` inside method body + `asyncio.to_thread()`.

3. **`asyncio.Lock` single-flight** — fast path (no lock) for valid cached token; slow path (lock + re-check + refresh) for expired token. Re-check inside the lock prevents duplicate refresh when multiple coroutines wait.

4. **7200s TTL from response** — use `response["expires_in"]` as the cache TTL, NOT a hardcoded 7200. Auto-refresh 60s before expiry (`refresh_margin = 60.0`).

5. **Injectable clock** — `clock: Callable[[], float] | None = None` defaulting to `time.monotonic()`. Tests inject a controllable clock to simulate time passing without real delays.

6. **Credential injection** — `TokenManager` receives `app_id` and `client_secret` as constructor strings. The host resolves `app_id_ref`/`app_secret_ref` from the runtime secret store. No env var reading or file access inside the token manager.

7. **`TokenError` with sanitized messages** — error messages must NOT contain the token, credentials, or URLs. HTTP status code is preserved as `TokenError.status_code` for caller retry logic.

8. **`invalidate()` method** — allows callers (e.g., Phase 62 sender) to force a refresh after receiving a 401 from a downstream API call (token may have been revoked early).

9. **No new dependencies** — stdlib only (`asyncio`, `json`, `time`, `urllib` (lazy), `typing`, `dataclasses`). `dependencies = []` invariant holds.

10. **Update `test_no_wecom_import.py`** to add `token_manager.py` AST import-isolation coverage.

11. **No `__init__.py` export change needed** — `TokenManager` is an internal module used by the adapter/sender, not a top-level package export. If Phase 62 needs it, it can import from `.token_manager`. Exporting it from `__init__.py` is optional but not required for Phase 61.

## Confidence Summary

| Claim | Confidence | Source |
|-------|------------|--------|
| getAppAccessToken endpoint is `POST https://bots.qq.com/app/getAppAccessToken` | HIGH | Official QQ Bot docs (fetched) |
| Request format is `{"appId": ..., "clientSecret": ...}` | HIGH | Official QQ Bot docs (fetched) |
| Response format is `{"access_token": ..., "expires_in": 7200}` | HIGH | Official QQ Bot docs (fetched) |
| Token TTL is 7200s with 60s overlap window | HIGH | Official QQ Bot docs (fetched) |
| `dependencies = []` invariant is tested | HIGH | Codebase — test_v1_8_safety_baseline.py |
| OllamaRunner transport injection pattern is the correct precedent | HIGH | Codebase — ollama_runner.py |
| `asyncio.Lock` single-flight pattern is established in codebase | HIGH | Codebase — rate_limiter.py, cost_tracker.py |
| `asyncio.to_thread()` is available in Python 3.11+ | HIGH | Python stdlib docs |
| Injectable clock pattern is established in codebase | HIGH | Codebase — rate_limiter.py |
| `urllib` must be lazy-imported (not top-level) | HIGH | Codebase — ollama_runner.py + test_ollama_runner.py |
| Token must not leak into logs/events | HIGH | AGENTS.md + research SUMMARY.md |
| `test_no_wecom_import.py` must be updated for new module | HIGH | Codebase — Phase 59/60 precedent |
| `time.monotonic()` is correct for cache expiry (not `time.time()`) | HIGH | Codebase precedent + Python docs |
| Phase 61 does NOT need `httpx` (urllib + to_thread sufficient) | HIGH | Codebase precedent + API analysis |
