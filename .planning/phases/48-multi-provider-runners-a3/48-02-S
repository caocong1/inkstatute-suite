# Plan 48-02 Summary: OllamaRunner with OpenAI-Compatible Endpoint

## Objective

Create `OllamaRunner` as a `ProviderModelRunner` Protocol implementation that invokes Ollama's OpenAI-compatible `/v1/chat/completions` endpoint via lazy HTTP client import. The runner builds an OpenAI-compatible request payload, sends it to the Ollama endpoint, and reuses `parse_openai_response()` for response parsing since the response format is identical to OpenAI Chat Completions. HTTP errors are normalized into `ErrorInfo`/`ErrorCategory` via status-code detection. This satisfies MULTIPROV-02.

## Tasks Completed

### Task 1: Create ollama_runner.py with OllamaRunner, OllamaTransport, HTTP error normalization

**Files modified:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py` — Created `OllamaRunner` class implementing `ProviderModelRunner` Protocol with async `invoke(req: RunRequest) -> ProviderModelExecResult`. Uses OpenAI-compatible endpoint (`/v1/chat/completions`) and reuses `parse_openai_response` from `openai_runner` for response parsing (line 157-161). HTTP client lazy-imported via `urllib.request` from stdlib inside `_real_http_call()` only (line 170-171) — never at module top level. `OllamaTransport` Protocol (line 47-56) and `FakeOllamaTransport` test helper (line 59-75) defined for test injection. `OllamaHTTPError` exception class with `status_code` attribute for HTTP error normalization (line 83-88). Error normalization delegates to shared `error_normalization.normalize_provider_error` with `provider="ollama"` (line 105-114), detecting HTTP status codes via `getattr(exc, "status_code", None)`. Request payload includes `stream=False` (line 145). `dependencies = []` invariant preserved — no `import httpx` or `import urllib` at module top level.
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` — Added exports for `OllamaRunner`, `OllamaTransport`, `FakeOllamaTransport`, `OllamaHTTPError` (lines 27-32, 44, 47-49).
- `packages/backends/provider_model/tests/fixtures/ollama_success.json` — Test fixture with OpenAI-compatible chat completion response (id, model, choices, usage).
- `packages/backends/provider_model/tests/test_ollama_runner.py` — 16 tests covering: runner success via fake transport, rate_limit (429) maps to retryable, auth error (401) maps to not-retryable, forbidden (403) maps to auth error, connection error maps to retryable, server error (500) maps to api_error, reuses OpenAI response parser (source="openai_chat_completions"), request includes stream=False, request uses config model name, error details include provider="ollama", error details include status_code, error message sanitized, truncated completion maps to failed, package imports cleanly without httpx, no top-level urllib import, exports available.

**Commit:** `4839160` — `feat(48-02): add OllamaRunner with OpenAI-compatible endpoint and lazy HTTP import`

## Deviations

- **[Non-blocking]** Plan 03 later refactored the error normalization to use the shared `error_normalization.py` module. The initial Plan 02 implementation had a local `_normalize_ollama_error` which was subsequently updated to delegate to `normalize_provider_error(exc, stage, provider="ollama")` in commit `467ca9f`. This is consistent with the Plan 03 objective of extracting shared error normalization.
- **[Non-blocking]** Plan specified `urllib` (stdlib) for the lazy HTTP import. The implementation uses `urllib.request` and `urllib.error` from stdlib, which satisfies the requirement of no external HTTP library dependency.

## Test Results

- **Ollama runner tests:** 16 tests pass
  - `python3 -m unittest packages.backends.provider_model.tests.test_ollama_runner -v` — OK
- **Full provider_model package:** 99 tests pass
  - `python3 -m unittest discover -s packages/backends/provider_model/tests` — OK

## FROZEN Contract Surfaces Verified

- `ProviderModelRunner` Protocol: unchanged (OllamaRunner implements it structurally)
- `ProviderModelExecResult` dataclass: unchanged
- `ErrorInfo`/`ErrorCategory`: reused from platform_contract, no modifications
- `parse_openai_response`: reused from `openai_runner.py`, no duplicate parser needed
- `dependencies = []` invariant preserved — no `import httpx` or `import urllib` at module top level

## Key Design Decisions

1. **OpenAI-compatible endpoint reuse** — Ollama's `/v1/chat/completions` is OpenAI-compatible, so `parse_openai_response` is reused for response parsing. No duplicate parser needed.
2. **Lazy HTTP import via `urllib.request`** from stdlib inside `_real_http_call()` only — package imports cleanly without any external HTTP library. Uses stdlib to avoid adding `httpx` as a dependency.
3. **`OllamaHTTPError` with `status_code` attribute** — HTTP errors from the Ollama endpoint carry the status code, which `normalize_provider_error` detects via `getattr(exc, "status_code", None)`.
4. **HTTP status code detection** — 429 → rate_limit (retryable=True), 401/403 → auth_error (retryable=False), timeout/connection → connection_error (retryable=True), 5xx → api_error (retryable=None).
5. **`stream=False` in request** — Ollama endpoint returns a single JSON response, not an SSE stream.
6. **Transport abstraction** (`OllamaTransport` Protocol + `FakeOllamaTransport`) allows test injection without real HTTP calls.
