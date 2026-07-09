# Phase 61: Access Token Manager — Pattern Mapping

**Phase:** 61 — Access Token Manager
**Output:** PATTERNS.md
**Status:** Complete

## Files To Create / Modify

| # | File | Action | Role |
|---|------|--------|------|
| 1 | `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py` | NEW | QQ Bot access token acquisition, caching, auto-refresh, single-flight |
| 2 | `packages/channels/qqbot/tests/test_token_manager.py` | NEW | Unit tests for token_manager.py (lifecycle, single-flight, error handling, import safety) |
| 3 | `packages/channels/qqbot/tests/test_no_wecom_import.py` | MODIFY | Add token_manager.py AST import-isolation coverage |

---

## File 1: `token_manager.py` (NEW)

### Role & Data Flow

QQ Bot access token manager. Acquires token via `POST https://bots.qq.com/app/getAppAccessToken` using `appId + clientSecret`, caches with `expires_in` TTL (default 7200s), auto-refreshes 60s before expiry, single-flight concurrent refresh via `asyncio.Lock`. Uses transport injection (Protocol + Fake + lazy urllib) to preserve `dependencies = []` invariant.

**Public API:**
- `TokenTransport` (Protocol) — async `fetch_token(app_id, client_secret) -> dict`
- `FakeTokenTransport` — test transport (no HTTP, configurable response/error)
- `UrllibTokenTransport` — production transport (lazy `urllib.request` + `asyncio.to_thread`)
- `TokenError` — exception with sanitized message + `status_code`
- `TokenManager` — cache + auto-refresh + single-flight, `async get_token() -> str`, `invalidate()`

### Analog 1A: Transport Protocol + Fake + Lazy urllib

**Closest analog:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py`

This is the **exact pattern** to follow — Protocol + Fake + lazy urllib inside method body.

#### Excerpt: OllamaTransport Protocol (lines 47-56)

```python
class OllamaTransport(Protocol):
    """Transport abstraction for Ollama OpenAI-compatible endpoint.

    Tests inject a fake transport so no real HTTP client or network
    access is required.
    """

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON chat completion response dict."""
        ...
```

**Adaptation for token_manager.py:** `TokenTransport` Protocol with `async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]`.

#### Excerpt: FakeOllamaTransport (lines 59-75)

```python
class FakeOllamaTransport:
    """Convenience fake transport for tests (no HTTP client required)."""

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.last_request: JsonObject | None = None

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        return self.response or {}
```

**Adaptation for token_manager.py:** `FakeTokenTransport` with `response`, `error`, `call_count`, `last_app_id`, `last_client_secret` tracking. Default response `{"access_token": "fixture-token", "expires_in": 7200}`.

#### Excerpt: OllamaRunner constructor with transport injection (lines 132-139)

```python
class OllamaRunner:
    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: OllamaTransport | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport
```

**Adaptation for token_manager.py:** `transport: TokenTransport | None = None` — if None, default to `UrllibTokenTransport()`.

#### Excerpt: invoke() dispatch — transport vs real HTTP (lines 141-162)

```python
    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        request_payload: JsonObject = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": req.turn.content}],
            "stream": False,
        }

        try:
            if self._transport is not None:
                response = await self._transport.create_chat_completion(request_payload)
            else:
                response = await self._real_http_call(request_payload)
        except Exception as exc:  # noqa: BLE001 - normalize all errors
            return self._build_error_result(exc, req)

        return parse_openai_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )
```

**Note:** OllamaRunner uses `if self._transport is not None` to dispatch. For token_manager.py, the research recommends defaulting `self._transport = transport or UrllibTokenTransport()` in `__init__`, so `get_token()` always calls `self._transport.fetch_token()` — simpler dispatch, no if/else branch.

#### Excerpt: _real_http_call — lazy urllib import + POST + error handling (lines 163-191)

```python
    async def _real_http_call(self, request_payload: JsonObject) -> JsonObject:
        """Make a real HTTP call to the Ollama endpoint.

        Uses ``urllib.request`` from stdlib (lazy import). This path is
        never exercised in tests — tests inject a :class:`FakeOllamaTransport`.
        """

        import urllib.request
        import urllib.error

        base_url = self.config.api_base_url or "http://localhost:11434"
        url = base_url.rstrip("/") + "/v1/chat/completions"

        data = json.dumps(request_payload).encode("utf-8")
        req_obj = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req_obj, timeout=self.config.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaHTTPError(body, status_code=exc.code) from exc
```

**Key conventions to replicate:**
1. `import urllib.request` and `import urllib.error` **inside** the method body — NOT at module top level.
2. `urllib.request.Request(url, data=..., headers={"Content-Type": "application/json"}, method="POST")`.
3. `urllib.request.urlopen(req, timeout=...)` with `# noqa: S310` comment.
4. `urllib.error.HTTPError` caught and re-raised as a custom exception with `status_code`.
5. `json.loads(body)` for response parsing.

**Adaptation for token_manager.py `UrllibTokenTransport`:**
- URL: `https://bots.qq.com/app/getAppAccessToken`
- Request body: `{"appId": app_id, "clientSecret": client_secret}`
- Wrap blocking call in `asyncio.to_thread(self._blocking_fetch, app_id, client_secret)` — OllamaRunner calls `_real_http_call` directly (it's already async but the urllib call blocks); token_manager must use `asyncio.to_thread` to avoid blocking the event loop.
- Catch `urllib.error.HTTPError` → `TokenError("QQ Bot token request failed", status_code=exc.code)`.
- Catch `urllib.error.URLError` → `TokenError("QQ Bot token endpoint unreachable")`.

#### Excerpt: OllamaHTTPError custom exception (lines 83-88)

```python
class OllamaHTTPError(Exception):
    """HTTP error from Ollama endpoint with status code for normalization."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
```

**Adaptation for token_manager.py:** `TokenError(Exception)` with `message: str` and `status_code: int | None = None` keyword argument.

#### Excerpt: __all__ export list (lines 217-222)

```python
__all__ = [
    "OllamaRunner",
    "OllamaTransport",
    "FakeOllamaTransport",
    "OllamaHTTPError",
]
```

**Adaptation:** `__all__ = ["TokenManager", "TokenTransport", "FakeTokenTransport", "UrllibTokenTransport", "TokenError"]`

### Analog 1B: asyncio.Lock Single-Flight

**Closest analog:** `packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py` and `cost_tracker.py`

#### Excerpt: rate_limiter.py — Lock creation + async with self._lock (lines 48-59, 78-88)

```python
class RateLimiter:
    def __init__(
        self,
        configs: dict[str, RateLimitConfig] | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._configs = dict(configs or {})
        self._clock = clock or _default_clock
        self._rpm_windows: dict[tuple[str, str], deque[float]] = {}
        self._tpm_windows: dict[tuple[str, str], deque[tuple[float, int]]] = {}
        self._semaphores: dict[tuple[str, str], asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()
```

```python
    async def check_rpm(self, tenant_id: str, provider_id: str, now: float | None = None) -> bool:
        """Return True if a new request is within the RPM limit."""
        cfg = self._config(provider_id)
        if cfg is None or cfg.rpm is None:
            return True
        ts = now if now is not None else self._clock()
        key = (tenant_id, provider_id)
        async with self._lock:
            window = self._rpm_windows.setdefault(key, deque())
            self._evict_old_timestamps(window, ts)
            return len(window) < cfg.rpm
```

#### Excerpt: cost_tracker.py — Lock creation + async with self._lock (lines 55-65, 97-111)

```python
class CostTracker:
    def __init__(
        self,
        pricing: dict[str, PricingRate] | None = None,
        budgets: dict[str, BudgetCeiling] | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._pricing = dict(pricing or {})
        self._budgets = dict(budgets or {})
        self._accumulated: dict[str, float] = {}
        self._lock = asyncio.Lock()
```

```python
    async def record_usage(
        self,
        tenant_id: str,
        matter_id: str | None,
        provider_id: str,
        usage: JsonObject,
    ) -> float:
        """Record token usage and return the cost added."""
        cost = self._calculate_cost(provider_id, usage)
        if cost == 0.0:
            return 0.0
        key = self._budget_key(tenant_id, matter_id)
        async with self._lock:
            self._accumulated[key] = self._accumulated.get(key, 0.0) + cost
        return cost
```

**Adaptation for token_manager.py `get_token()`:** The single-flight pattern adds a **fast path** (no lock) before the slow path (lock + re-check):

```python
async def get_token(self) -> str:
    # Fast path: cached token still valid (no lock needed)
    if self._token is not None and not self._is_near_expiry():
        return self._token

    # Slow path: acquire lock, re-check, refresh if still expired
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
```

The re-check inside the lock is critical — without it, multiple coroutines waiting on the lock would each refresh the token sequentially, defeating single-flight.

### Analog 1C: Injectable Clock

**Closest analog:** `packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py`

#### Excerpt: _default_clock + injectable clock in __init__ (lines 23-24, 52-55)

```python
def _default_clock() -> float:
    return time.monotonic()
```

```python
    def __init__(
        self,
        configs: dict[str, RateLimitConfig] | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._configs = dict(configs or {})
        self._clock = clock or _default_clock
```

**Adaptation for token_manager.py:** Identical pattern — module-level `_default_clock()` returning `time.monotonic()`, constructor accepts `clock: Callable[[], float] | None = None`, stored as `self._clock = clock or _default_clock`.

**Why `time.monotonic()` not `time.time()`:** Wall clock can go backwards (NTP adjustments, timezone changes). `time.monotonic()` is monotonically increasing — correct for cache expiry tracking.

### Analog 1D: Module Header & Imports

**Closest analog:** `ollama_runner.py` header (lines 1-26) + `rate_limiter.py` docstring (lines 1-10)

#### Excerpt: ollama_runner.py imports (lines 22-26)

```python
from __future__ import annotations

import json
from typing import Any, Protocol
```

#### Excerpt: rate_limiter.py docstring + imports (lines 1-18)

```python
"""Per-tenant/provider rate limiting (RPM/TPM/concurrency).

Pure-Python implementation using:
- ``collections.deque`` for sliding-window RPM/TPM tracking.
- ``asyncio.Semaphore`` for concurrency limits.
- ``asyncio.Lock`` for safe concurrent state updates.
- ``asyncio.monotonic()`` as the default time source (injectable for tests).

No external dependencies — ``dependencies = []`` invariant preserved.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable
```

**Adaptation for token_manager.py imports:**
```python
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Protocol
```

**CRITICAL:** `urllib.request` and `urllib.error` must NOT appear at module top level. They are imported lazily inside `UrllibTokenTransport._blocking_fetch()`.

### Analog 1E: Credential Injection (No Raw Secrets)

**Closest analog:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py`

#### Excerpt: QQBotChannelConfig ref-only fields (lines 11-25)

```python
@dataclass(frozen=True, slots=True)
class QQBotChannelConfig:
    """QQBot channel settings.

    The channel is deliberately disabled by default and carries only references
    to external runtime secrets (no raw secrets).
    """

    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    bot_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

**Pattern:** Config stores `app_id_ref` and `app_secret_ref` (reference strings, NOT raw secrets). The host/caller resolves these refs to actual `app_id` and `client_secret` strings from the runtime secret store, then passes them to `TokenManager.__init__(app_id=..., client_secret=...)`. The token manager itself never reads env vars or files.

### Analog 1F: __init__.py Export Decision

**Closest analog:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py`

#### Excerpt: Current __init__.py (lines 1-6)

```python
"""QQBot channel adapter package."""

from .adapter import QQBotChannelAdapter
from .config import QQBotChannelConfig

__all__ = ["QQBotChannelAdapter", "QQBotChannelConfig"]
```

**Decision:** Phase 61 does NOT need to modify `__init__.py`. `TokenManager` is an internal module used by the adapter/sender (Phase 62), not a top-level package export. The `normalization.py` module from Phase 60 was also NOT exported from `__init__.py` — same precedent.

---

## File 2: `test_token_manager.py` (NEW)

### Role & Data Flow

Unit tests for `token_manager.py` covering: lifecycle (acquire, cache, auto-refresh), concurrent refresh single-flight, error handling (HTTP error, missing fields, sanitized messages), and import safety (no top-level urllib).

### Analog 2A: IsolatedAsyncioTestCase + FakeTransport usage

**Closest analog:** `packages/backends/provider_model/tests/test_ollama_runner.py`

#### Excerpt: IsolatedAsyncioTestCase class + FakeOllamaTransport injection (lines 60-71)

```python
class OllamaRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_success_via_fake_transport(self) -> None:
        response = _load_fixture("ollama_success.json")
        runner = OllamaRunner(transport=FakeOllamaTransport(response=response))

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )
```

#### Excerpt: FakeTransport with error injection (lines 73-90)

```python
    async def test_runner_rate_limit_error_maps_to_retryable(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("rate limit exceeded", status_code=429)
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_rate_limit"
        )
        self.assertIs(result.result.error.retryable, True)
```

#### Excerpt: test imports (lines 1-23)

```python
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import AgentResult, AgentTurn, Channel, JsonObject, MessageType
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeOllamaTransport,
    OllamaHTTPError,
    OllamaRunner,
    ProviderModelBackendConfig,
    ProviderModelExecResult,
)
```

**Adaptation for test_token_manager.py imports:**
```python
from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from inkstatute_channels_qqbot.token_manager import (
    FakeTokenTransport,
    TokenError,
    TokenManager,
)
```

### Analog 2B: Injectable Clock Test Pattern

**Closest analog:** `packages/model-gateway/tests/test_rate_limiter.py`

#### Excerpt: injectable `now` parameter for time simulation (lines 14-27)

```python
class TestRpmLimiting(unittest.IsolatedAsyncioTestCase):
    async def test_rpm_under_limit_allows(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=60)}
        limiter = RateLimiter(cfg)
        result = await limiter.check_rpm("tenant-1", "provider-a", now=0.0)
        self.assertTrue(result)

    async def test_rpm_over_limit_rejects(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=2)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        await limiter.record_request("tenant-1", "provider-a", now=0.1)
        result = await limiter.check_rpm("tenant-1", "provider-a", now=0.2)
        self.assertFalse(result)
```

**Note:** RateLimiter passes `now` as a method parameter. TokenManager uses an injectable `clock` callable in `__init__` instead. Tests use a mutable `now` variable captured by a lambda:

```python
now = 1000.0
manager = TokenManager(
    app_id="fixture-app-id",
    client_secret="fixture-secret",
    transport=transport,
    clock=lambda: now,
)
await manager.get_token()
now = 1000.0 + 7141.0  # simulate time passing
token = await manager.get_token()
```

### Analog 2C: No Top-Level urllib Import Test

**Closest analog:** `packages/backends/provider_model/tests/test_ollama_runner.py` (lines 275-311)

#### Excerpt: top-level urllib import check (lines 275-311)

```python
class PackageImportTests(unittest.TestCase):
    def test_ollama_runner_module_does_not_import_urllib_at_top_level(self) -> None:
        source_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "src"
            / "inkstatute_backends_provider_model"
            / "ollama_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for line in source.splitlines():
            stripped = line.lstrip()
            # Skip comments and string literals.
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Only check top-level (non-indented) lines.
            if line.startswith(" ") or line.startswith("\t"):
                continue
            # Top-level urllib import is forbidden (must be lazy inside invoke).
            self.assertFalse(
                stripped.startswith("import urllib"),
                f"top-level 'import urllib' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from urllib"),
                f"top-level 'from urllib' forbidden: {line!r}",
            )
            # Top-level httpx import is forbidden.
            self.assertFalse(
                stripped.startswith("import httpx"),
                f"top-level 'import httpx' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from httpx"),
                f"top-level 'from httpx' forbidden: {line!r}",
            )
```

**Adaptation for test_token_manager.py:** Same pattern, pointing to `token_manager.py` source path:
```python
source_path = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "inkstatute_channels_qqbot"
    / "token_manager.py"
)
```

### Analog 2D: Concurrent Single-Flight Test

**No direct analog in existing codebase** — this is a new test pattern. The closest async concurrency pattern is in `test_rate_limiter.py` (asyncio.Semaphore with `asyncio.wait_for` timeout, lines 98-110):

```python
    async def test_concurrency_limit(self) -> None:
        cfg = {"provider-a": RateLimitConfig(max_concurrency=1)}
        limiter = RateLimiter(cfg)
        sem = await limiter.acquire_concurrency("tenant-1", "provider-a")
        self.assertIsNotNone(sem)
        await sem.acquire()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=0.1)
            self.fail("Should have timed out")
        except asyncio.TimeoutError:
            pass
        sem.release()
```

**Adaptation for single-flight test:** Use `asyncio.gather` to launch 10 concurrent `get_token()` calls and assert `transport.call_count` only incremented by 1:

```python
results = await asyncio.gather(*[manager.get_token() for _ in range(10)])
self.assertEqual(transport.call_count, 2)  # 1 initial + 1 refresh, not 10
self.assertTrue(all(t == "token-002" for t in results))
```

---

## File 3: `test_no_wecom_import.py` (MODIFY)

### Role & Data Flow

Add a new test method `test_token_manager_does_not_import_wecom_service` to the existing `NoWecomImportTests` class, following the exact AST inspection pattern already used for `adapter.py`, `config.py`, `__init__.py`, `_ed25519.py`, `signature.py`, and `normalization.py`.

### Analog: Existing AST import-isolation pattern

**Closest analog:** The file itself — `packages/channels/qqbot/tests/test_no_wecom_import.py`

#### Excerpt: helper function + PACKAGE_SRC constant (lines 13-27)

```python
PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src" / "inkstatute_channels_qqbot"


def _imported_modules(source: str) -> list[str]:
    """Return all module names referenced in import statements."""
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules
```

#### Excerpt: normalization.py test method — the most recent precedent (Phase 60, lines 76-83)

```python
    def test_normalization_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "normalization.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"normalization.py imports from wecom_service: {module}",
            )
```

**Adaptation for token_manager.py:** Add an identical method, changing `normalization.py` → `token_manager.py`:

```python
    def test_token_manager_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "token_manager.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"token_manager.py imports from wecom_service: {module}",
            )
```

**Insertion point:** After the `test_normalization_does_not_import_wecom_service` method (line 83), before `test_adapter_imports_channel_core` (line 85). This keeps the per-module wecom-isolation tests grouped together.

---

## Summary: Pattern Source Map

| Pattern | Analog File | Lines |
|---------|-------------|-------|
| Transport Protocol | `ollama_runner.py` | 47-56 |
| FakeTransport | `ollama_runner.py` | 59-75 |
| Transport injection in constructor | `ollama_runner.py` | 132-139 |
| Lazy urllib + POST + error handling | `ollama_runner.py` | 163-191 |
| Custom HTTP exception with status_code | `ollama_runner.py` | 83-88 |
| `__all__` export list | `ollama_runner.py` | 217-222 |
| `asyncio.Lock` creation | `rate_limiter.py` | 59 |
| `async with self._lock` critical section | `rate_limiter.py` | 85-88 |
| `asyncio.Lock` in cost tracker | `cost_tracker.py` | 65, 91-95, 109-110 |
| Injectable clock (`_default_clock` + `time.monotonic`) | `rate_limiter.py` | 23-24, 52-55 |
| Module docstring (`dependencies = []` note) | `rate_limiter.py` | 1-10 |
| `IsolatedAsyncioTestCase` + FakeTransport | `test_ollama_runner.py` | 60-71 |
| FakeTransport with error injection | `test_ollama_runner.py` | 73-90 |
| No top-level urllib import test | `test_ollama_runner.py` | 275-311 |
| Injectable time in tests | `test_rate_limiter.py` | 14-27 |
| Async concurrency test (`asyncio.gather`/`wait_for`) | `test_rate_limiter.py` | 98-110 |
| AST import-isolation test | `test_no_wecom_import.py` | 13-27, 76-83 |
| Ref-only credential config | `config.py` | 11-25 |
| `__init__.py` no-export for internal modules | `__init__.py` | 1-6 |
