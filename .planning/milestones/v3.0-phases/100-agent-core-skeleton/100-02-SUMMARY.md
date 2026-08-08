# Summary: Plan 100-02 — Model Layer — LlmProvider Protocol + StreamDelta + Provider Runners + Gateway Integration

**Plan**: 100-02
**Phase**: 100 — Agent Core Skeleton
**Wave**: 2 (depends on 100-01; runs in parallel with 100-03)
**Status**: COMPLETE
**Date**: 2026-08-11

## What Was Done

Plan 100-02 created the unified model layer for the InkStatute agent core:

1. **LlmProvider Protocol + StreamDelta union** (`model/provider.py`) — the unified provider abstraction:
   - `StreamDelta` union of 5 frozen dataclass types: `ContentDelta`, `ReasoningDelta`, `ToolCallDelta`, `UsageDelta`, `FinishDelta`
   - `ChatRequest` frozen dataclass with `stream=True` default (unified streaming-only interface)
   - `LlmProvider` Protocol: `chat_stream() -> AsyncIterator[StreamDelta]`, `model_name()`, `supports_tools()`
   - `UsageAccumulator`: sums tokens from multiple `UsageDelta` events, provides `to_dict()` for event metadata

2. **FixtureProvider with TurnScript** (`fixtures.py`) — testing without external LLM calls:
   - `TurnScript`: frozen dataclass with `deltas`, `delay_seconds`, `error`
   - `FixtureProvider`: implements `LlmProvider` Protocol
   - Multi-turn scripts (round-robin per `chat_stream()` call)
   - Error injection via `TurnScript.error`
   - Delay support via `delay_seconds` (asyncio.sleep for silence threshold testing)
   - `call_count` tracking for turn limit testing
   - `RuntimeError` on script exhaustion

3. **Error normalization + config** (`model/error_normalization.py`, `model/config.py`):
   - `error_normalization.py` copied verbatim from `provider_model` (`normalize_provider_error`, `sanitize_error_message`)
   - `ProviderModelConfig` frozen dataclass (no `backend_id` — agent-core is not a BackendAdapter in Phase 100)

4. **OpenAI stream provider** (`model/openai_runner.py`):
   - `OpenAIStreamProvider` implementing `LlmProvider` Protocol
   - `chat_stream()` yields `StreamDelta` from OpenAI SSE chunks
   - `_ToolCallAccumulator`: accumulates tool call fragments (name in first chunk, arguments in subsequent chunks), finalizes on new index or finish_reason
   - `parse_sse_deltas()`: parses raw SSE `data:` lines into JSON dicts
   - `FakeOpenAITransport` with streaming support (`stream_chunks`)
   - Lazy SDK import preserved (`importlib.import_module("openai")` inside `chat_stream`)
   - Error normalization via `normalize_provider_error(provider="openai")`
   - Model name sanitized to `"redacted"`

5. **Anthropic stream provider** (`model/anthropic_runner.py`):
   - `AnthropicStreamProvider` implementing `LlmProvider` Protocol
   - Parses Anthropic SSE events: `content_block_delta` (text_delta → ContentDelta, thinking_delta → ReasoningDelta), `content_block_start` (tool_use), `input_json_delta` (accumulate), `content_block_stop` (finalize ToolCallDelta), `message_delta` (usage → UsageDelta), `message_stop` (→ FinishDelta)
   - System prompt extracted from messages to top-level `system` parameter
   - OpenAI tool format converted to Anthropic tool format
   - `FakeAnthropicTransport` with streaming support (`stream_events`)
   - Lazy SDK import preserved
   - Error normalization via `normalize_provider_error(provider="anthropic")`

6. **Ollama stream provider** (`model/ollama_runner.py`):
   - `OllamaStreamProvider` implementing `LlmProvider` Protocol
   - Reuses `_ToolCallAccumulator` from `openai_runner.py` (no duplicate parser)
   - Real HTTP streaming path via `urllib.request` (lazy import)
   - `FakeOllamaTransport` with streaming support
   - `OllamaHTTPError` with `status_code` for error normalization
   - Error normalization via `normalize_provider_error(provider="ollama")`

7. **Gateway components wrapper** (`model/gateway_components.py`):
   - `GatewayComponents`: wraps `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` from `model-gateway`
   - `before_call()`: checks circuit breaker + rate limit (RPM)
   - `after_call()`: records success/failure in circuit breaker, request in rate limiter, usage in cost tracker
   - `get_usage_summary()`: accumulated usage for current turn
   - Default mode is pass-through (no limits, no budgets)
   - `ProtectedProvider`: wraps any `LlmProvider` with gateway checks
   - Raises `ProviderBlockedError` when blocked (circuit_open / rate_limited)
   - Usage deltas accumulated during stream and recorded after
   - Injectable clocks work for deterministic testing

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 100-02-06 | Merge error_normalization.py and config.py into model/ | `735ed5e` | PASS |
| 100-02-01 | LlmProvider Protocol + StreamDelta union types | `18915f3` | PASS |
| 100-02-02 | FixtureProvider with TurnScript for testing | `6648f7d` | PASS |
| 100-02-03 | OpenAI stream provider with tool call + reasoning support | `9f3a56d` | PASS |
| 100-02-04 | Anthropic stream provider with tool call + reasoning support | `e7dece1` | PASS |
| 100-02-05 | Ollama stream provider with OpenAI-compatible streaming | `8bfa2c2` | PASS |
| 100-02-07 | Gateway components wrapper (circuit breaker + rate limiter + cost tracker) | `07e7f1b` | PASS |
| 100-02-08 | Verify model layer integration + all gates green | (verification only) | PASS |

## Files Created

- `packages/agent-core/src/inkstatute_agent_core/model/provider.py` — LlmProvider Protocol, StreamDelta union, ChatRequest, UsageAccumulator
- `packages/agent-core/src/inkstatute_agent_core/model/config.py` — ProviderModelConfig
- `packages/agent-core/src/inkstatute_agent_core/model/error_normalization.py` — normalize_provider_error, sanitize_error_message
- `packages/agent-core/src/inkstatute_agent_core/model/openai_runner.py` — OpenAIStreamProvider, FakeOpenAITransport, _ToolCallAccumulator, parse_sse_deltas
- `packages/agent-core/src/inkstatute_agent_core/model/anthropic_runner.py` — AnthropicStreamProvider, FakeAnthropicTransport, _extract_system_prompt, _convert_tools_to_anthropic
- `packages/agent-core/src/inkstatute_agent_core/model/ollama_runner.py` — OllamaStreamProvider, FakeOllamaTransport, OllamaHTTPError
- `packages/agent-core/src/inkstatute_agent_core/model/gateway_components.py` — GatewayComponents, ProtectedProvider, ProviderBlockedError
- `packages/agent-core/src/inkstatute_agent_core/fixtures.py` — FixtureProvider, TurnScript
- `packages/agent-core/tests/test_model_provider.py` — 30 tests
- `packages/agent-core/tests/test_fixture_provider.py` — 24 tests
- `packages/agent-core/tests/test_openai_runner.py` — 23 tests
- `packages/agent-core/tests/test_anthropic_runner.py` — 21 tests
- `packages/agent-core/tests/test_ollama_runner.py` — 18 tests
- `packages/agent-core/tests/test_gateway_components.py` — 25 tests

## Files Modified

None. All 100-01 files (config.py, event_emitter.py, __init__.py) are untouched. No 100-03 files (turn_loop.py, context.py) were created or modified.

## Test Results

- **agent-core gate**: 260 tests, all PASS (61 from 100-01 + 199 from 100-02)
  - `test_config.py`: 18 tests (from 100-01)
  - `test_event_emitter.py`: 43 tests (from 100-01)
  - `test_model_provider.py`: 30 tests (StreamDelta, ChatRequest, UsageAccumulator, LlmProvider Protocol)
  - `test_fixture_provider.py`: 24 tests (single-turn, multi-turn, error injection, delay, script exhaustion)
  - `test_openai_runner.py`: 23 tests (content, reasoning, tool call accumulation, usage, error handling, SSE parsing)
  - `test_anthropic_runner.py`: 21 tests (text, reasoning, tool use, usage, system prompt, tool conversion, error handling)
  - `test_ollama_runner.py`: 18 tests (content, tool call, reasoning, usage, HTTP error status codes, request building)
  - `test_gateway_components.py`: 25 tests (circuit breaker, rate limiter, cost tracker, pass-through, ProtectedProvider, injectable clocks)
- **Full gate suite**: 38 gates, all green, `"passed": true`
- **provider-model-backend gate**: 103 tests, all PASS (original runners untouched — we copied, not moved)
- **model-gateway gate**: 80 tests, all PASS (we import from it, not modify it)
- **No external dependencies added**: `dependencies = []` in pyproject.toml

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] LlmProvider Protocol created (chat_stream, model_name, supports_tools)
- [x] StreamDelta union created (ContentDelta, ReasoningDelta, ToolCallDelta, UsageDelta, FinishDelta)
- [x] FixtureProvider created (TurnScript with deltas, delay_seconds, error)
- [x] OpenAI/Anthropic/Ollama runners with streaming + tool calls
- [x] Circuit breaker/rate limiter/cost tracker integrated (from model-gateway)
- [x] Usage data in events (UsageDelta + UsageAccumulator + get_usage_summary)
- [x] All 38 gates green
- [x] SUMMARY.md with Self-Check: PASSED

## Deviations

None. All tasks completed as specified in the plan with no deviations.

## Notes for Subsequent Plans

- The `LlmProvider` Protocol is the unified interface for all providers — Plans 100-03 (turn loop) and 100-04 (integration tests) use it
- `FixtureProvider` is ready for use by 100-03 (turn loop testing) and 100-04 (integration tests)
- `ProtectedProvider` wraps any `LlmProvider` with gateway checks — the turn loop can use it or use raw providers
- `UsageAccumulator` is available for attaching usage data to `run.state_changed` events
- The `model/` sub-package is now populated — `model/__init__.py` may need updating in 100-03 or 100-04 to export key types
- All three runners preserve lazy SDK imports — the package imports cleanly without `openai`, `anthropic`, or any HTTP library installed
- The `_ToolCallAccumulator` in `openai_runner.py` is reused by `ollama_runner.py` (Ollama is OpenAI-compatible)
- Error normalization is shared across all three runners via `model/error_normalization.py`
