# Plan 48-01 Summary: AnthropicRunner with Messages API Normalization

## Objective

Create `AnthropicRunner` as a `ProviderModelRunner` Protocol implementation that invokes the Anthropic Messages API via lazy SDK import. The runner normalizes the platform's `RunRequest` into Anthropic's Messages API format (system prompt as top-level `system` parameter, user message as content blocks), parses the response back into `ProviderModelExecResult`, and normalizes Anthropic SDK errors into `ErrorInfo`/`ErrorCategory`. This satisfies MULTIPROV-01.

## Tasks Completed

### Task 1: Create anthropic_runner.py with AnthropicRunner, AnthropicTransport, parse_anthropic_response, and error normalization

**Files modified:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/anthropic_runner.py` — Created `AnthropicRunner` class implementing `ProviderModelRunner` Protocol with async `invoke(req: RunRequest) -> ProviderModelExecResult`. Anthropic Messages API normalization: system prompt as top-level `system` parameter (line 300-302), user message as content blocks `[{"type":"text","text":content}]` (line 289-296), `max_tokens=4096` (line 288). `parse_anthropic_response` (line 89-172) maps `stop_reason=="end_turn"` to SUCCEEDED, `max_tokens`/`content_filter` to FAILED with `ErrorInfo(code="provider_model_truncated")`, empty completion to FAILED with `provider_model_empty_completion`. `AnthropicTransport` Protocol (line 51-60) and `FakeAnthropicTransport` test helper (line 63-79) defined for test injection. Lazy SDK import via `importlib.import_module("anthropic")` inside `invoke()` only (line 309) — never at module top level. Error normalization delegates to shared `error_normalization.normalize_provider_error` with `provider="anthropic"` (line 213-220). Model name sanitized to `"redacted"` in metadata (line 193-196). `dependencies = []` invariant preserved.
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` — Added exports for `AnthropicRunner`, `AnthropicTransport`, `FakeAnthropicTransport`, `parse_anthropic_response` (lines 10-15, 41-43, 63).
- `packages/backends/provider_model/tests/fixtures/anthropic_success.json` — Test fixture with Anthropic Messages API response (id, content blocks, stop_reason="end_turn", usage).
- `packages/backends/provider_model/tests/test_anthropic_runner.py` — 21 tests covering: parse success/truncated/content_filter/empty/multi-block, runner success via fake transport, rate_limit/auth/connection/api_status error normalization, system prompt handling, content blocks format, max_tokens in request, error details include provider="anthropic", error message sanitization, package imports cleanly without SDK, no top-level anthropic import, exports available.

**Commit:** `4a520cf` — `feat(48-01): add AnthropicRunner with Messages API normalization and lazy SDK import`

## Deviations

- **[Non-blocking]** Plan 03 later refactored the error normalization to use the shared `error_normalization.py` module. The initial Plan 01 implementation had a local `_normalize_anthropic_error` which was subsequently updated to delegate to `normalize_provider_error(exc, stage, provider="anthropic")` in commit `467ca9f`. This is consistent with the Plan 03 objective of extracting shared error normalization.

## Test Results

- **Anthropic runner tests:** 21 tests pass
  - `python3 -m unittest packages.backends.provider_model.tests.test_anthropic_runner -v` — OK
- **Full provider_model package:** 99 tests pass
  - `python3 -m unittest discover -s packages/backends/provider_model/tests` — OK

## FROZEN Contract Surfaces Verified

- `ProviderModelRunner` Protocol: unchanged (AnthropicRunner implements it structurally)
- `ProviderModelExecResult` dataclass: unchanged
- `ErrorInfo`/`ErrorCategory`: reused from platform_contract, no modifications
- `dependencies = []` invariant preserved — no `import anthropic` at module top level

## Key Design Decisions

1. **Lazy SDK import via `importlib.import_module("anthropic")`** inside `invoke()` only — package imports cleanly without the `anthropic` SDK installed.
2. **System prompt as top-level `system` parameter** — Anthropic Messages API requires system prompt outside the messages array, unlike OpenAI which puts it in messages with `role: "system"`.
3. **Content blocks format** — user message sent as `[{"type": "text", "text": content}]` per Anthropic Messages API spec.
4. **`parse_anthropic_response` maps `stop_reason`** to platform states: `end_turn` → SUCCEEDED, `max_tokens`/`content_filter` → FAILED with `provider_model_truncated`, no content → FAILED with `provider_model_empty_completion`.
5. **Model name redacted** to `"redacted"` in metadata — never appears in `AgentResult.content` or `ErrorInfo.message`.
6. **Transport abstraction** (`AnthropicTransport` Protocol + `FakeAnthropicTransport`) allows test injection without real API calls.
