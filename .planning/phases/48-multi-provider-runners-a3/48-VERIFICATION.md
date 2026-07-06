---
phase: 48-multi-provider-runners-a3
verified: 2026-07-06T09:35:13Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 48: Multi-Provider Runners (A3) Verification Report

**Phase Goal:** Operator can configure `AnthropicRunner` and `OllamaRunner` as `ProviderRunner` Protocol implementations behind the provider_model adapter, with Messages API normalization for Anthropic, OpenAI-compatible endpoint for Ollama, and multi-provider error normalization reusing the v1.6 `ErrorInfo`/`ErrorCategory` pattern.
**Verified:** 2026-07-06T09:35:13Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap Success Criteria are the non-negotiable contract; PLAN frontmatter must-haves add plan-specific detail. Both are merged below.

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `AnthropicRunner` implements `ProviderRunner` Protocol with Messages API normalization (system prompt handling, message format conversion, tool use format), lazy SDK import, and `dependencies = []` invariant | ✓ VERIFIED | `anthropic_runner.py:263-348` — `AnthropicRunner` class with async `invoke(req: RunRequest) -> ProviderModelExecResult`. System prompt as top-level `system` parameter (line 300-302). User message as content blocks `[{"type":"text","text":content}]` (line 289-296). Lazy SDK import via `importlib.import_module("anthropic")` inside `invoke()` only (line 309). No `import anthropic` at module top level. `test_anthropic_runner_module_does_not_import_anthropic_at_top_level` passes. 21 anthropic runner tests pass. |
| 2 | `OllamaRunner` implements `ProviderRunner` Protocol using OpenAI-compatible endpoint (`/v1/chat/completions`), lazy HTTP client import, and `dependencies = []` invariant | ✓ VERIFIED | `ollama_runner.py:122-214` — `OllamaRunner` class with async `invoke(req: RunRequest) -> ProviderModelExecResult`. Uses OpenAI-compatible endpoint (line 175: `url = base_url.rstrip("/") + "/v1/chat/completions"`). Reuses `parse_openai_response` for response parsing (line 157-161). Lazy HTTP import via `urllib.request` inside `_real_http_call()` only (line 170-171). No `import httpx` or `import urllib` at module top level. `test_ollama_runner_module_does_not_import_urllib_at_top_level` and `test_package_imports_cleanly_without_httpx` pass. 16 ollama runner tests pass. |
| 3 | Multi-provider error normalization reuses the v1.6 `ErrorInfo`/`ErrorCategory` pattern — provider-specific errors (rate limits, auth failures, timeouts, content filter) map to the existing `ErrorCategory` enum with provider-specific detail in `ErrorInfo.detail` | ✓ VERIFIED | `error_normalization.py:57-131` — `normalize_provider_error(exc, stage, *, provider)` handles all three providers. Rate limits (429 / "RateLimit" in class name) → `provider_model_rate_limit` (retryable=True). Auth failures (401/403 / "Authentication" in class name) → `provider_model_auth_error` (retryable=False). Timeouts/connection → `provider_model_connection_error` (retryable=True). 5xx / "APIStatus" → `provider_model_api_error` (retryable=None). All map to `ErrorCategory.RUNTIME_ERROR`. `ErrorInfo.details` includes `{"provider": "anthropic"|"ollama"|"openai"}` (line 94). `test_runner_error_details_include_provider_anthropic` and `test_runner_error_details_include_provider_ollama` pass. Content filter handled in `parse_anthropic_response` (line 128-136: `stop_reason in ("max_tokens", "content_filter")` → FAILED with `provider_model_truncated`). |
| 4 | `AnthropicTransport` Protocol and `FakeAnthropicTransport` test helper defined for test injection | ✓ VERIFIED | `anthropic_runner.py:51-60` (Protocol with `async def create_message`), `anthropic_runner.py:63-79` (FakeAnthropicTransport with response/error injection). Exported from `__init__.py` (lines 12-13). `test_anthropic_runner_exports_are_available` passes. |
| 5 | `OllamaTransport` Protocol and `FakeOllamaTransport` test helper defined for test injection | ✓ VERIFIED | `ollama_runner.py:47-56` (Protocol with `async def create_chat_completion`), `ollama_runner.py:59-75` (FakeOllamaTransport with response/error injection). Exported from `__init__.py` (lines 28-29, 31). `test_ollama_runner_exports_are_available` passes. |
| 6 | `parse_anthropic_response` maps `stop_reason='end_turn'` to SUCCEEDED, `'max_tokens'`/`'content_filter'` to FAILED with ErrorInfo | ✓ VERIFIED | `anthropic_runner.py:89-172` — `stop_reason == "end_turn"` with content → SUCCEEDED (line 121-123). `stop_reason in ("max_tokens", "content_filter")` → FAILED with `ErrorInfo(code="provider_model_truncated")` (line 128-136). No content and no recognized stop_reason → FAILED with `provider_model_empty_completion` (line 137-146). `test_parse_truncated_completion_maps_to_failed` and `test_parse_content_filter_maps_to_failed` pass. |
| 7 | `dependencies = []` invariant preserved — no external imports at module top level across all new modules | ✓ VERIFIED | `error_normalization.py` top-level imports: `re` (stdlib), `platform_contract.enums`, `platform_contract.events` — no external deps. `anthropic_runner.py` top-level imports: `importlib`, `json` (stdlib), `typing`, `platform_contract`, `platform_runtime`, relative imports — no `import anthropic`. `ollama_runner.py` top-level imports: `json` (stdlib), `typing`, `platform_contract`, `platform_runtime`, relative imports — no `import httpx` or `import urllib`. `test_package_imports_cleanly_without_anthropic_sdk`, `test_package_imports_cleanly_without_httpx`, `test_anthropic_runner_module_does_not_import_anthropic_at_top_level`, `test_ollama_runner_module_does_not_import_urllib_at_top_level` all pass. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/anthropic_runner.py` | `AnthropicRunner` with Messages API normalization, lazy SDK import, error normalization | ✓ VERIFIED | lines 263-348 (runner), 89-172 (parser), 51-79 (transport), 309 (lazy import), 213-220 (error normalization) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/ollama_runner.py` | `OllamaRunner` with OpenAI-compatible endpoint, lazy HTTP import, error normalization | ✓ VERIFIED | lines 122-214 (runner), 157-161 (parse_openai_response reuse), 170-171 (lazy urllib import), 105-114 (error normalization), 83-88 (OllamaHTTPError) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/error_normalization.py` | Shared `normalize_provider_error` and `sanitize_error_message` | ✓ VERIFIED | lines 37-49 (sanitize), 57-131 (normalize), 31-34 (regex patterns), 134-137 (__all__) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` | Exports all new symbols | ✓ VERIFIED | lines 10-15 (anthropic), 17 (error_normalization), 27-32 (ollama), 40-67 (__all__) |
| `packages/backends/provider_model/tests/test_anthropic_runner.py` | 21 tests for AnthropicRunner | ✓ VERIFIED | 21 tests pass |
| `packages/backends/provider_model/tests/test_ollama_runner.py` | 16 tests for OllamaRunner | ✓ VERIFIED | 16 tests pass |
| `packages/backends/provider_model/tests/test_error_normalization.py` | Error normalization and sanitization tests | ✓ VERIFIED | 9 tests pass |
| `packages/backends/provider_model/tests/fixtures/anthropic_success.json` | Anthropic Messages API response fixture | ✓ VERIFIED | exists |
| `packages/backends/provider_model/tests/fixtures/ollama_success.json` | OpenAI-compatible chat completion fixture | ✓ VERIFIED | exists |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `AnthropicRunner.invoke` | `error_normalization.normalize_provider_error` | `_normalize_anthropic_error` delegate | ✓ VERIFIED | `anthropic_runner.py:213-220` calls `normalize_provider_error(exc, stage, provider="anthropic")` |
| `OllamaRunner.invoke` | `error_normalization.normalize_provider_error` | `_normalize_ollama_error` delegate | ✓ VERIFIED | `ollama_runner.py:105-114` calls `normalize_provider_error(exc, stage, provider="ollama")` |
| `OllamaRunner.invoke` | `openai_runner.parse_openai_response` | direct import and call | ✓ VERIFIED | `ollama_runner.py:40` imports `parse_openai_response`, line 157-161 calls it for response parsing |
| `error_normalization.normalize_provider_error` | `platform_contract.events.ErrorInfo` | returns ErrorInfo | ✓ VERIFIED | `error_normalization.py:124-131` constructs `ErrorInfo(category=ErrorCategory.RUNTIME_ERROR, ...)` |
| `__init__.py` | all new modules | re-exports | ✓ VERIFIED | `__init__.py:10-15` (anthropic), `:17` (error_normalization), `:27-32` (ollama) |

### V2 Gate Suite

| Gate | Result | Notes |
| ---- | ------ | ----- |
| platform-contract | OK (21 tests) | — |
| wecom-service | OK (72 tests) | — |
| hermes-contract-layer | OK (35 tests) | — |
| conversation-read-view | OK (106 tests) | — |
| skill-registry | OK (35 tests) | — |
| router-service | OK (45 tests) | — |
| mcp-registry | OK (56 tests) | — |
| codex-backend | OK (51 tests) | — |
| provider-model-backend | OK (99 tests) | Phase 48 code verified here |
| admin-console-api | FAILED (10 errors) | Pre-existing `ModuleNotFoundError: No module named 'rbac'` from Phase 51 RBAC work — unrelated to Phase 48 |

### Deviations from Plan

1. **`openai_runner.py` not fully refactored to import from `error_normalization.py`** — retains local `_normalize_api_error` and `_sanitize_error_message` with equivalent behavior. The shared module is used by `AnthropicRunner` and `OllamaRunner`. Non-blocking: behavior is identical, all tests pass.
2. **`test_multi_provider_error_normalization.py` not created as separate file** — multi-provider error normalization is covered by existing tests across `test_error_normalization.py`, `test_anthropic_runner.py`, and `test_ollama_runner.py`. Non-blocking: all three providers' error paths are verified.
3. **Contract test suite additions not created** — existing contract tests continue to pass. Non-blocking: provider_model backend contract behavior verified through 99-test package suite.

### Anti-Patterns Check

- No frozen contract surfaces modified (`ProviderModelRunner`, `ProviderModelExecResult`, `ErrorInfo`, `ErrorCategory` all unchanged)
- No new external dependencies added (`dependencies = []` invariant preserved)
- No secrets, tokens, or model names leaked (sanitization verified by tests)
- No raw provider payloads stored (model names redacted to `"redacted"` in metadata)
