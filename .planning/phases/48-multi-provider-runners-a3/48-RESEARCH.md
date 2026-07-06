# Phase 48: Multi-Provider Runners (A3) - Research

**Researched:** 2026-07-06
**Domain:** Multi-provider LLM runners, Anthropic Messages API normalization, Ollama OpenAI-compatible endpoint, error normalization reuse
**Confidence:** HIGH

## Summary

Phase 48 adds two new `ProviderModelRunner` Protocol implementations — `AnthropicRunner` and `OllamaRunner` — alongside the existing `OpenAIClientRunner`. Both runners follow the exact same architectural pattern as `OpenAIClientRunner`: they implement the `ProviderModelRunner` Protocol (which requires `async def invoke(self, req: RunRequest) -> ProviderModelExecResult`), use lazy SDK/HTTP imports inside `invoke()` so the package imports cleanly without external dependencies, and normalize provider-specific errors into `ErrorInfo`/`ErrorCategory` from `platform_contract`.

`AnthropicRunner` normalizes the Anthropic Messages API, which differs from OpenAI's Chat Completions in three key ways: (1) the system prompt is a top-level `system` parameter, not a message in the messages array; (2) message content uses content blocks (`[{"type": "text", "text": "..."}]`) instead of plain strings; (3) tool use follows Anthropic's `tool_use`/`tool_result` block format. The runner converts the platform's `RunRequest.turn.content` into the Anthropic Messages API format, invokes `AsyncAnthropic.messages.create()` via a lazy `importlib.import_module("anthropic")` call, and parses the response back into `ProviderModelExecResult`.

`OllamaRunner` uses Ollama's OpenAI-compatible endpoint (`/v1/chat/completions`), which means the request/response format is identical to OpenAI's Chat Completions API. The runner uses a lazy HTTP client import (urllib from stdlib, or httpx if available) to POST to the Ollama endpoint, and reuses the existing `parse_openai_response` function for response parsing since the format is OpenAI-compatible.

Multi-provider error normalization extends the existing `_normalize_api_error` pattern from `openai_runner.py` to handle provider-specific error class names. The existing `ErrorCategory` enum (`CONTRACT_ERROR`, `RUNTIME_ERROR`, `CHANNEL_ERROR`) and `ErrorInfo` dataclass (`category`, `code`, `message`, `stage`, `retryable`, `details`, `metadata`) are reused without modification — provider-specific detail goes into `ErrorInfo.details`.

**Primary recommendation:** Create `anthropic_runner.py` and `ollama_runner.py` modules following the `openai_runner.py` pattern (lazy import, transport abstraction for testing, error normalization via string-based class-name detection). Extract shared error normalization into a common `error_normalization.py` module that all three runners use. Wire both new runners into `__init__.py` exports. All work stays within the `inkstatute_backends_provider_model` package — no frozen contract surfaces are modified.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MULTIPROV-01 | `AnthropicRunner` implements `ProviderRunner` Protocol with Messages API normalization (system prompt handling, message format conversion, tool use format), lazy SDK import, and `dependencies = []` invariant | §Architecture Patterns (AnthropicRunner), §Code Examples (Messages API normalization), §Common Pitfalls (lazy import) |
| MULTIPROV-02 | `OllamaRunner` implements `ProviderRunner` Protocol using OpenAI-compatible endpoint (`/v1/chat/completions`), lazy HTTP client import, and `dependencies = []` invariant | §Architecture Patterns (OllamaRunner), §Code Examples (OpenAI-compatible endpoint) |
| MULTIPROV-03 | Multi-provider error normalization reuses the v1.6 `ErrorInfo`/`ErrorCategory` pattern — provider-specific errors (rate limits, auth failures, timeouts, content filter) map to the existing `ErrorCategory` enum with provider-specific detail in `ErrorInfo.detail` | §Architecture Patterns (error normalization), §Code Examples (normalize_provider_error) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** Runner configs use `api_key_ref` (reference name), not actual key values. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Contract logs should prefer references such as `raw_payload_ref`.** Runner results use ref-based metadata. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Add tests before or with behavior changes**, especially for schemas, mappers, event ordering, dedupe, and fixture replay. [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** Use structured JSON parsing for provider responses. [VERIFIED: AGENTS.md §Coding Rules]
- **Do not introduce a new service, database, queue, or runtime dependency.** `dependencies = []` invariant must be preserved — lazy SDK imports only inside runner methods. [VERIFIED: AGENTS.md §Coding Rules, pyproject.toml]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Anthropic Messages API normalization | Backend adapter (provider_model) | — | Runner owns provider-specific protocol conversion; SDK lazy-imported |
| Ollama OpenAI-compatible endpoint | Backend adapter (provider_model) | — | Runner owns HTTP call; client lazy-imported |
| ProviderRunner Protocol conformance | Backend adapter (provider_model) | — | All runners implement `ProviderModelRunner.invoke()` returning `ProviderModelExecResult` |
| Multi-provider error normalization | Backend adapter (provider_model) | — | Shared `_normalize_provider_error` maps provider exceptions to `ErrorInfo`/`ErrorCategory` |
| Package exports | Backend adapter (provider_model) | — | `__init__.py` re-exports new runner classes and transport abstractions |
| `dependencies = []` invariant | pyproject.toml | — | No external SDK imports at module top level |

## Standard Stack

### Core

No new external packages are installed. This phase uses only the existing Python standard library and existing project packages. [VERIFIED: codebase grep — `dependencies = []` in `packages/backends/provider_model/pyproject.toml:15`]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `importlib` | 3.14+ | Lazy SDK imports inside runner methods | Already used in `openai_runner.py` [VERIFIED: codebase] |
| Python stdlib `json` | 3.14+ | JSON parsing for provider responses | Already used in `openai_runner.py` [VERIFIED: codebase] |
| Python stdlib `urllib` | 3.14+ | HTTP requests for Ollama (fallback if no httpx) | Standard library — no dependency needed [VERIFIED: Python stdlib] |
| `platform-contract` | existing | `ErrorInfo`, `ErrorCategory`, `AgentResult`, `AgentResultStatus`, `ReplyType` | Frozen contract — no modifications [VERIFIED: test_contract_freeze.py] |
| `platform-runtime` | existing | `RunRequest` | Runtime owns request shape [VERIFIED: codebase] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `anthropic` SDK | optional | Anthropic Messages API | Lazy-imported inside `AnthropicRunner.invoke()` only — not a package dependency |
| `httpx` | optional | HTTP client for Ollama | Lazy-imported inside `OllamaRunner.invoke()` only — not a package dependency; urllib fallback |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Lazy `importlib.import_module("anthropic")` | Top-level `import anthropic` | Rejected — breaks `dependencies = []` invariant. Must use lazy import inside `invoke()` method. |
| httpx for Ollama HTTP | Python stdlib `urllib` | urllib is always available (no dependency). httpx is optional — if available, use it; otherwise fall back to urllib. Both are lazy-imported. |
| New `ProviderRunner` Protocol | Existing `ProviderModelRunner` Protocol | Must use existing Protocol — `ProviderModelRunner` is already defined in `adapter.py` with `async def invoke(self, req: RunRequest) -> ProviderModelExecResult`. New runners implement this Protocol. |
| New error enum values | Existing `ErrorCategory` enum | Must use existing frozen enum — `ErrorCategory.RUNTIME_ERROR` covers all provider errors. Provider-specific detail goes in `ErrorInfo.details` and `ErrorInfo.code`. |

**Installation:**
```bash
# No packages to install — this phase uses only existing project packages and Python stdlib
```

**Version verification:** Not applicable — no new packages installed. Python 3.14.6 confirmed on the target machine. [VERIFIED: `python3 --version`]

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project packages and Python stdlib. The `dependencies = []` invariant on the provider_model package must be preserved. [VERIFIED: `packages/backends/provider_model/pyproject.toml:15`]

## Architecture Patterns

### System Architecture Diagram

```
Operator configures:
  ProviderModelBackendAdapter(runner=AnthropicRunner(...))
  ProviderModelBackendAdapter(runner=OllamaRunner(...))
  ProviderModelBackendAdapter(runner=OpenAIClientRunner(...))

All runners implement ProviderModelRunner Protocol:
  async def invoke(self, req: RunRequest) -> ProviderModelExecResult

                    ┌─────────────────────────────────┐
                    │  ProviderModelBackendAdapter     │
                    │  (adapter.py)                    │
                    │  runner: ProviderModelRunner     │
                    └──────────┬──────────────────────┘
                               │ invoke(req)
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
  │ OpenAIClient    │ │ AnthropicRunner │ │ OllamaRunner    │
  │ Runner          │ │                 │ │                 │
  │ (openai_runner  │ │ (anthropic_     │ │ (ollama_runner  │
  │  .py)           │ │  runner.py)     │ │  .py)           │
  │                 │ │                 │ │                 │
  │ Lazy import:    │ │ Lazy import:    │ │ Lazy import:    │
  │ importlib       │ │ importlib       │ │ urllib / httpx  │
  │ ("openai")      │ │ ("anthropic")   │ │                 │
  │                 │ │                 │ │                 │
  │ Transport:      │ │ Transport:      │ │ Transport:      │
  │ OpenAITransport │ │ AnthropicTrans  │ │ OllamaTransport │
  │ (Protocol)      │ │ port (Protocol) │ │ (Protocol)      │
  │                 │ │                 │ │                 │
  │ Error:          │ │ Error:          │ │ Error:          │
  │ _normalize_     │ │ _normalize_     │ │ _normalize_     │
  │  api_error()    │ │  provider_      │ │  provider_      │
  │                 │ │  error()        │ │  error()        │
  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
           │                   │                   │
           ▼                   ▼                   ▼
  ┌─────────────────────────────────────────────────────────┐
  │  ProviderModelExecResult                                │
  │  status: AsyncTaskState                                 │
  │  result: AgentResult (with ErrorInfo if failed)         │
  │  completion_id, artifact_refs, metadata                 │
  └─────────────────────────────────────────────────────────┘
```

### AnthropicRunner Pattern

The `AnthropicRunner` follows the exact same pattern as `OpenAIClientRunner`:

1. **Transport Protocol** — `AnthropicTransport` Protocol with `async def create_message(self, request_payload: JsonObject) -> JsonObject`. Tests inject a `FakeAnthropicTransport`.
2. **Lazy SDK import** — `importlib.import_module("anthropic")` inside `invoke()` only, never at module top level.
3. **Messages API normalization** — Converts `RunRequest.turn.content` to Anthropic Messages API format:
   - System prompt → top-level `system` parameter (not in messages array)
   - User message → `[{"role": "user", "content": [{"type": "text", "text": content}]}]`
   - Response parsing: `response.content[0].text` → `AgentResult.content`, `stop_reason == "end_turn"` → `SUCCEEDED`
4. **Error normalization** — Anthropic SDK exceptions (`RateLimitError`, `AuthenticationError`, `APIConnectionError`, `APIStatusError`) mapped to `ErrorInfo` via string-based class-name detection.
5. **`dependencies = []` invariant** — No `import anthropic` at module top level. [VERIFIED: `openai_runner.py` pattern]

### OllamaRunner Pattern

The `OllamaRunner` follows a similar pattern but uses HTTP instead of an SDK:

1. **Transport Protocol** — `OllamaTransport` Protocol with `async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject`. Tests inject a `FakeOllamaTransport`.
2. **Lazy HTTP import** — `urllib.request` from stdlib (always available) or `httpx` (optional, lazy-imported if available) inside `invoke()` only.
3. **OpenAI-compatible endpoint** — POST to `{base_url}/v1/chat/completions` with `{"model": ..., "messages": [...], "stream": false}`. Response format is identical to OpenAI Chat Completions.
4. **Response parsing** — Reuses `parse_openai_response()` from `openai_runner.py` since the response format is OpenAI-compatible.
5. **Error normalization** — HTTP errors (429 rate limit, 401 auth, timeout, connection refused) mapped to `ErrorInfo` via HTTP status code detection.
6. **`dependencies = []` invariant** — No `import httpx` at module top level. urllib is stdlib. [VERIFIED: Python stdlib]

### Error Normalization Pattern

The existing `_normalize_api_error` in `openai_runner.py` uses string-based class-name detection because the SDK cannot be imported at module top level. This pattern is extended to a shared `_normalize_provider_error` function that handles all three providers:

| Provider | Error Class Pattern | ErrorInfo Code | Retryable |
|----------|-------------------|----------------|-----------|
| OpenAI | `RateLimitError` | `provider_model_rate_limit` | `True` |
| OpenAI | `AuthenticationError` | `provider_model_auth_error` | `False` |
| OpenAI | `APIConnectionError`/`Timeout` | `provider_model_connection_error` | `True` |
| OpenAI | `APIStatusError` | `provider_model_api_error` | `None` |
| Anthropic | `RateLimitError` | `provider_model_rate_limit` | `True` |
| Anthropic | `AuthenticationError` | `provider_model_auth_error` | `False` |
| Anthropic | `APIConnectionError`/`Timeout` | `provider_model_connection_error` | `True` |
| Anthropic | `APIStatusError` | `provider_model_api_error` | `None` |
| Ollama | HTTP 429 | `provider_model_rate_limit` | `True` |
| Ollama | HTTP 401/403 | `provider_model_auth_error` | `False` |
| Ollama | Timeout/Connection | `provider_model_connection_error` | `True` |
| Ollama | HTTP 5xx | `provider_model_api_error` | `None` |

All errors map to `ErrorCategory.RUNTIME_ERROR` — the existing enum has only `CONTRACT_ERROR`, `RUNTIME_ERROR`, `CHANNEL_ERROR`, and provider errors are runtime errors. Provider-specific detail goes in `ErrorInfo.details` (e.g., `{"provider": "anthropic", "status_code": 429}`). [VERIFIED: `enums.py:17-22`]

## Don't Hand-Roll

| What | Use Instead | Why |
|------|-------------|-----|
| Anthropic Messages API request format | Anthropic SDK's `messages.create()` | The SDK handles content block formatting, system prompt handling, and tool use format. We just normalize the request payload and parse the response. |
| Ollama chat completion | Ollama's `/v1/chat/completions` endpoint | OpenAI-compatible — reuse `parse_openai_response()` for response parsing. |
| Error normalization | Shared `_normalize_provider_error()` function | All three providers map to the same `ErrorInfo`/`ErrorCategory` pattern. String-based class-name detection for SDK errors, HTTP status codes for Ollama. |
| Response parsing | `parse_openai_response()` for Ollama, new `parse_anthropic_response()` for Anthropic | Ollama is OpenAI-compatible; Anthropic has a different response format. |

## Common Pitfalls

1. **Importing SDK at module top level** — The `anthropic` and `httpx` packages are NOT package dependencies. They must be lazy-imported inside `invoke()` methods only. The package must import cleanly without them. [VERIFIED: `openai_runner.py` pattern, `test_package_imports_cleanly_without_openai_sdk`]

2. **Anthropic system prompt in messages array** — Anthropic's Messages API requires the system prompt as a top-level `system` parameter, NOT as a `{"role": "system"}` message in the messages array. Putting it in the messages array will cause an API error. [CITED: Anthropic Messages API documentation]

3. **Anthropic content blocks vs plain strings** — Anthropic's Messages API uses content blocks (`[{"type": "text", "text": "..."}]`) for message content, not plain strings. The response also uses content blocks — `response.content[0].text` extracts the text. [CITED: Anthropic Messages API documentation]

4. **Ollama base URL trailing slash** — The Ollama endpoint is `{base_url}/v1/chat/completions`. If `base_url` has a trailing slash, the URL becomes `{base_url}//v1/chat/completions`. Normalize by stripping trailing slashes. [ASSUMED: common HTTP client pattern]

5. **Error message sanitization** — Error messages from provider APIs may contain URLs, tokens, file paths, and model names. The existing `_sanitize_error_message()` function strips these. New runners must reuse it. [VERIFIED: `openai_runner.py:269-276`]

6. **Frozen contract surfaces** — `ErrorCategory` enum, `ErrorInfo` dataclass, `AgentResult` dataclass, `ProviderModelRunner` Protocol, and `ProviderModelExecResult` dataclass are all frozen. Do not modify them. [VERIFIED: `test_contract_freeze.py`, `test_contract_count_freeze.py`]

## Code Examples

### AnthropicRunner invoke() pattern

```python
class AnthropicRunner:
    """Runner that invokes AsyncAnthropic.messages.create lazily."""

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: AnthropicTransport | None = None,
        api_key_resolver: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport
        self._api_key_resolver = api_key_resolver or _default_api_key_resolver

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        # Normalize to Anthropic Messages API format
        request_payload: JsonObject = {
            "model": self.config.model_name,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": req.turn.content or ""}],
                }
            ],
        }
        # System prompt as top-level parameter if configured
        system_prompt = self.config.metadata.get("system_prompt")
        if system_prompt:
            request_payload["system"] = system_prompt

        try:
            if self._transport is not None:
                response = await self._transport.create_message(request_payload)
            else:
                # Real SDK path — lazy import
                anthropic_module = importlib.import_module("anthropic")
                AsyncAnthropic = getattr(anthropic_module, "AsyncAnthropic")
                cred = self._api_key_resolver(self.config.api_key_ref)
                client = AsyncAnthropic(
                    api_key=cred,
                    base_url=self.config.api_base_url,
                )
                message = await client.messages.create(**request_payload)
                response = _message_to_dict(message)
        except Exception as exc:
            return self._build_error_result(exc, req)

        return parse_anthropic_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )
```

### Anthropic response parsing

```python
def parse_anthropic_response(
    response: JsonObject,
    run_id: str,
    turn_id: str,
) -> ProviderModelExecResult:
    """Map an Anthropic Messages API response to ProviderModelExecResult."""
    content_blocks = response.get("content", []) or []
    text_parts: list[str] = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    content = "".join(text_parts) if text_parts else None

    stop_reason = response.get("stop_reason")
    completion_id = response.get("id")
    usage = response.get("usage", {}) or {}
    model = response.get("model", "unknown")

    # Determine status
    if stop_reason == "end_turn" and content is not None:
        status = AsyncTaskState.SUCCEEDED
        result_status = AgentResultStatus.SUCCESS
        error = None
    elif stop_reason in ("max_tokens", "content_filter"):
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_truncated",
            stage="completion",
            message=f"completion truncated: {stop_reason}",
        )
    else:
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_empty_completion",
            stage="completion",
            message="empty completion with no content",
        )

    result = AgentResult(
        result_id=f"provider-model-result-{run_id}",
        turn_id=turn_id,
        status=result_status,
        reply_type=ReplyType.TEXT,
        content=content,
        error=error,
        metadata={
            "provider_completion_id": completion_id,
            "source": "anthropic_messages",
        },
    )

    return ProviderModelExecResult(
        status=status,
        result=result,
        completion_id=completion_id,
        metadata={
            "provider_completion_id": completion_id,
            "provider_usage": _sanitize_usage(usage),
            "provider_model": "redacted",
        },
    )
```

### OllamaRunner invoke() pattern

```python
class OllamaRunner:
    """Runner that invokes Ollama's OpenAI-compatible endpoint lazily."""

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: OllamaTransport | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport

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
        except Exception as exc:
            return self._build_error_result(exc, req)

        # Reuse OpenAI response parser — Ollama is OpenAI-compatible
        return parse_openai_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )
```

### Shared error normalization

```python
def _normalize_provider_error(
    exc: Exception,
    stage: str,
    *,
    provider: str = "unknown",
) -> ErrorInfo:
    """Normalize a provider exception into a sanitized ErrorInfo.

    Works for all providers — uses string-based class-name detection
    for SDK errors (OpenAI, Anthropic) and HTTP status code detection
    for Ollama.
    """
    exc_name = type(exc).__name__

    # Check for HTTP status code attribute (Ollama)
    status_code = getattr(exc, "status_code", None)

    if "RateLimit" in exc_name or status_code == 429:
        code = "provider_model_rate_limit"
        retryable = True
    elif "Authentication" in exc_name or "Auth" in exc_name or status_code in (401, 403):
        code = "provider_model_auth_error"
        retryable = False
    elif "Connection" in exc_name or "Timeout" in exc_name or "timeout" in exc_name.lower():
        code = "provider_model_connection_error"
        retryable = True
    elif "APIStatus" in exc_name or "API" in exc_name or (status_code and status_code >= 500):
        code = "provider_model_api_error"
        retryable = None
    else:
        code = "provider_model_unknown_error"
        retryable = None

    message = _sanitize_error_message(str(exc))

    return ErrorInfo(
        category=ErrorCategory.RUNTIME_ERROR,
        code=code,
        message=message,
        stage=stage,
        retryable=retryable,
        details={"provider": provider} if status_code else {"provider": provider},
    )
```
