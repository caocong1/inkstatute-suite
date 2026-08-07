---
phase: 100
slug: agent-core-skeleton
status: draft
created: 2026-08-11
skip_discuss: false
---

# Phase 100 — Agent Core Skeleton

## Phase Goal

存在一个 Python 自研 agent 核心骨架，其流式表现优于被移植的 Rust 原版——工具轮期间客户端不会经历整轮静默

## Requirements

- **CORE-01**: `packages/agent-core` async 流式 turn loop——首字节即流，**工具轮也流式**，不得整轮缓冲（修复 lawyer-desktop 现状缺陷）
- **CORE-04**: 上下文预算与裁剪策略，处理 skill 正文 2K–20K token 的注入成本
- **CORE-09**: 多 provider 模型层（OpenAI 兼容 / Anthropic / Ollama），由 `packages/backends/provider_model` 归并而来，复用 `packages/model-gateway` 的熔断 / 限流 / 成本追踪

## Success Criteria

1. `packages/agent-core` 存在，实现 async 流式 turn loop，产出 Phase 88 的统一事件；有多轮工具编排与轮次上限
2. **工具轮流式**：工具调用期间持续产出 `thought.delta` 与 `tool_call.started|delta|completed`，测试断言从提交到最终回复之间不存在超过阈值的事件静默期（这是对 `lawyer-desktop` 现状缺陷的修复）
3. 上下文预算与裁剪策略生效：给定 token 预算与一组 skill 正文（2K–20K token）+ 历史，装配器产出确定性的上下文并记录被裁剪内容
4. 模型层由 `packages/backends/provider_model` 归并而来，支持 OpenAI 兼容 / Anthropic / Ollama，流式与工具调用在各 provider 间归一
5. 模型层复用 `packages/model-gateway` 的熔断 / 限流 / 成本追踪，`usage` 数据进入事件流
6. 全部测试可在无外部 LLM 的情况下用 fixture provider 运行

## Codebase Scout Findings

### 1. lawyer-desktop Rust Agent Core — The Original to Port

**Location:** `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/`

**Key files:**
- `commands/chat.rs` (2,000 lines) — The main turn loop (`send_message` command)
- `commands/chat_tools.rs` (877 lines) — Tool execution, streaming, message building
- `llm/provider.rs` (17 lines) — `LlmProvider` trait: `chat()`, `chat_stream()`, `supports_tools()`, `model_name()`, `config()`
- `llm/openai_compat.rs` (120 lines) — OpenAI-compatible streaming via `reqwest::bytes_stream()`
- `llm/types.rs` (102 lines) — `ChatMessage`, `ToolCall`, `FunctionCall`, `ToolDefinition`, `ChatRequest`, `ChatResponse`, `Usage`
- `llm/tool_leak.rs` (392 lines) — Tool call leakage detection (ported in Phase 102)
- `skills/agent_classifier.rs` (691 lines) — Chat/Draft/Evidence mode classifier (ported in Phase 98)
- `skills/router.rs` (627 lines) — System prompt assembly, research-gate injection (ported in Phase 102)

**Turn loop architecture (chat.rs lines 765-1084):**

The Rust turn loop is a `for round in 0..MAX_TOOL_ROUNDS` loop (MAX_TOOL_ROUNDS=10):
1. Build `ChatRequest` with `stream: false` and tools
2. Call `provider.chat()` (non-streaming) to get tool_calls or content
3. If `tool_calls` present → execute tools → append results → `continue`
4. If embedded tool calls found in content → parse → execute → `continue`
5. If tool leakage detected → retry (up to MAX_LEAK_RETRIES=3)
6. If content is non-empty → stream it via `collect_with_continuations` → break
7. If content is empty → re-request with `stream: true` and no tools → break

**The "整轮静默" (whole-round silence) problem:**

The critical defect is at line 782: `stream: false`. During tool rounds, the LLM is called in **non-streaming mode**. The client sees:
- `emit_stream_status("thinking")` → status hint
- `provider.chat()` → **blocks until full response** (no deltas)
- `emit_stream_status("tool")` → status hint
- Tool execution → **blocks until all tools complete** (no deltas)
- Only the final content round uses `stream: true`

This means during multi-round tool orchestration, the client experiences complete event silence — no `thought.delta`, no `tool_call.started|delta|completed` events. The only feedback is a status string ("thinking" / "tool") emitted via Tauri events, not unified events.

**Fix in Phase 100:** The Python turn loop must:
- Stream the LLM response even during tool rounds (use `stream: true` always)
- Emit `tool_call.started` before tool execution, `tool_call.delta` during, `tool_call.completed` after
- Emit `thought.delta` for reasoning content during tool rounds
- Enforce a silence threshold (no gap > N seconds between events)

### 2. packages/model-gateway — Circuit Breaker, Rate Limiting, Cost Tracking

**Location:** `packages/model-gateway/src/inkstatute_model_gateway/`

| File | Lines | Purpose |
|------|-------|---------|
| `gateway.py` | 379 | `ModelProviderGateway` — composite BackendAdapter wrapping sub-adapters |
| `circuit_breaker.py` | 157 | `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN), `CircuitBreakerRegistry` |
| `rate_limiter.py` | 151 | `RateLimiter` — RPM/TPM sliding window + concurrency semaphore |
| `cost_tracker.py` | 154 | `CostTracker` — per-tenant/matter cost accumulation with budget ceilings |
| `config.py` | 52 | `ModelProviderGatewayConfig` — gateway_id, enabled, fallback_chain, pricing, budgets |

**Key design patterns:**
- `ModelProviderGateway` wraps `dict[str, BackendAdapter]` sub-adapters keyed by `backend_id`
- When `config.enabled=False` (default): pass-through mode, no gateway logic
- When `config.enabled=True`: rate limiting → circuit breaker → fallback chain → cost tracking
- `_extract_usage_from_run()` extracts `provider_usage` from Run metadata for cost tracking
- Circuit breaker: trips after N consecutive failures, cooldown period, HALF_OPEN probe
- Rate limiter: 60-second sliding window for RPM/TPM, `asyncio.Semaphore` for concurrency
- Cost tracker: `PricingRate` (input_token_cost, output_token_cost), `BudgetCeiling` per tenant/matter

**Reuse strategy for Phase 100:**
The agent-core's model layer should wrap provider calls through `CircuitBreakerRegistry`, `RateLimiter`, and `CostTracker` from model-gateway. Rather than duplicating these, the agent-core imports them directly. The `ModelProviderGateway` composite adapter pattern is NOT needed (agent-core is a single backend, not a composite), but the individual components are reused.

### 3. packages/backends/provider_model — Provider Model Layer

**Location:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/`

| File | Lines | Purpose |
|------|-------|---------|
| `adapter.py` | 421 | `ProviderModelBackendAdapter` — BackendAdapter Protocol impl |
| `openai_runner.py` | 498 | `OpenAIClientRunner` — lazy `AsyncOpenAI` import, `FakeOpenAITransport` |
| `anthropic_runner.py` | 356 | `AnthropicRunner` — lazy `AsyncAnthropic` import, `FakeAnthropicTransport` |
| `ollama_runner.py` | 222 | `OllamaRunner` — lazy `urllib.request`, `FakeOllamaTransport` |
| `config.py` | 34 | `ProviderModelBackendConfig` — backend_id, model_name, api_key_ref, api_base_url |
| `error_normalization.py` | — | Shared error sanitization (URLs, tokens, paths, model names) |
| `manifest.py` | — | Capability manifest builder |

**Provider abstraction patterns:**
- Each runner has a `Transport` Protocol (injectable for tests): `OpenAITransport`, `AnthropicTransport`, `OllamaTransport`
- Each has a `Fake*Transport` for testing without real API calls
- Lazy SDK import via `importlib.import_module()` inside `invoke()` — package imports cleanly without SDKs
- `parse_openai_response()` / `parse_anthropic_response()` map provider responses to `ProviderModelExecResult`
- `ProviderModelStreamDelta` (content, finish_reason) is the streaming delta type
- `FakeStreamingProviderModelRunner` yields pre-configured deltas for testing
- Error normalization: string-based class-name detection → `ErrorInfo` with sanitized messages
- `ProviderModelBackendConfig.api_key_ref` is a reference name (e.g. "OPENAI_API_KEY"), not the actual key

**Merge strategy for Phase 100:**
The three runners (OpenAI, Anthropic, Ollama) are merged into `packages/agent-core` as the unified model layer. The transport abstraction pattern is preserved. The `ProviderModelBackendAdapter` itself is NOT needed (agent-core has its own BackendAdapter in Phase 103), but the runners, transports, response parsers, and error normalization are reused.

**What's missing in the current runners (must add in Phase 100):**
- **Streaming with tool calls**: Current runners only do non-streaming `invoke()` or simple streaming `stream()` — no tool call support in streaming mode
- **Tool call parsing**: `parse_openai_response()` extracts content but not `tool_calls` from the response
- **Unified streaming interface**: No common streaming interface across providers that includes tool call deltas

### 4. packages/context-assembler — Context Budget and Trimming

**Location:** `packages/platform-runtime/src/platform_runtime/context_assembler.py` (543 lines)

**Key classes:**
- `ContextAssemblyPolicy` (line 82): `budget_tokens=2048`, `chars_per_token=4`, `trim_strategy="protected_then_feedback_memory_recent_artifact"`
- `ContextAssemblyResult` (line 117): includes `estimated_tokens`, `dropped_sections`, `protected_sections`
- `ContextAssembler` (line 142): `assemble()` method with deterministic trim
- `ContextAssemblyBudgetError` (line 17): raised when protected context exceeds budget

**Trim algorithm (lines 237-276):**
1. Calculate `estimated_tokens` for the full bundle
2. While `estimated > budget_tokens`: iterate trim order (feedback → memory → recent → artifact → active_task), pop one item from first non-empty section, record in `dropped_sections`, re-estimate
3. If still over budget after all trimming: raise `ContextAssemblyBudgetError`

**Token estimation (line 475):**
```python
def _estimate_tokens(event, policy):
    chars_per_token = max(1, int(policy.chars_per_token))
    return math.ceil(_estimated_value_chars(event) / chars_per_token)
```

**Phase 100 adaptation:**
The agent-core's context assembler needs to handle skill body injection (2K-20K token bodies) in addition to conversation history. The skill-materializer's `body_injector.py` already implements section-priority deterministic trim for SKILL.md bodies with CJK-aware token estimation. Phase 100's context assembler combines:
- Conversation history trimming (from `context_assembler.py` pattern)
- Skill body injection (from `body_injector.py` pattern)
- Total context budget enforcement across system prompt + history + skill bodies

### 5. Phase 88 Unified Events — The Event Vocabulary

**Location:** `packages/platform-contract/src/platform_contract/`

**Key files:**
- `unified_events.py` (289 lines) — 15 typed payload dataclasses for 13 event categories
- `enums.py` (247 lines) — `RunEventType` StrEnum with V3 unified event types
- `events.py` (591 lines) — V2 dataclasses (AgentResult, ErrorInfo, Artifact, etc.)

**Event types relevant to Phase 100 (from `RunEventType` enum):**
```python
SESSION_STARTED = "session.started"
MESSAGE_DELTA_V3 = "message.delta"        # Content streaming
MESSAGE_COMPLETED = "message.completed"   # Final content
THOUGHT_DELTA = "thought.delta"           # Reasoning/thinking streaming
TOOL_CALL_STARTED_V3 = "tool_call.started"
TOOL_CALL_DELTA = "tool_call.delta"       # Tool execution progress
TOOL_CALL_COMPLETED_V3 = "tool_call.completed"
PLAN_UPDATED = "plan.updated"
PHASE_CHANGED = "phase.changed"
RUN_STATE_CHANGED = "run.state_changed"
ERROR = "error"
```

**Payload dataclasses (from `unified_events.py`):**
- `MessageDeltaPayload(delta, message_id, metadata)` — content streaming
- `ThoughtDeltaPayload(delta, metadata)` — reasoning streaming
- `ToolCallStartedPayload(tool_call_id, tool_name, kind, title, metadata)` — tool starts
- `ToolCallDeltaPayload(tool_call_id, content, status, metadata)` — tool progress
- `ToolCallCompletedPayload(tool_call_id, status, content, file_locations, raw_input_ref, raw_output_ref, error, metadata)` — tool finishes
- `RunStateChangedPayload(status, previous_status, error, metadata)` — state transitions
- `ErrorEventPayload(error, metadata)` — errors

**How the agent core should emit these:**
The turn loop is an `async def run_turn() -> AsyncIterator[RunEvent]` generator. Each event is a `RunEvent` with:
- `event_type`: one of the `RunEventType` values
- `payload`: the corresponding payload dataclass serialized to dict via `serialize_payload()`
- `seq`: monotonic sequence number for SSE replay
- `occurred_at`: ISO timestamp

The agent-core creates a helper `EventEmitter` that wraps the async generator, assigns seq numbers, and ensures no silence gaps > threshold.

### 6. Fixture Provider — Testing Without External LLM

**Existing patterns in provider_model:**
- `FakeOpenAITransport` (openai_runner.py line 65): `__init__(response, error)`, `async create_chat_completion(request_payload) -> JsonObject`
- `FakeAnthropicTransport` (anthropic_runner.py line 63): same pattern, `async create_message(request_payload) -> JsonObject`
- `FakeOllamaTransport` (ollama_runner.py line 59): same pattern
- `FakeStreamingProviderModelRunner` (openai_runner.py line 478): `__init__(deltas: list[ProviderModelStreamDelta])`, `async stream(req) -> AsyncIterator[ProviderModelStreamDelta]`

**Phase 100 fixture provider:**
A new `FixtureProvider` class in `packages/agent-core` that:
- Accepts a script of pre-configured events (deltas, tool_calls, tool_results, final content)
- Implements the same `LlmProvider` Protocol as real providers
- Streams events according to the script with configurable delays
- Supports multi-turn tool orchestration scripts (round 1: tool_calls, round 2: final content)
- Enables testing the silence threshold assertion without real API calls

### 7. Turn Loop Design — Async Structure

**Rust original (chat.rs):**
```
for round in 0..MAX_TOOL_ROUNDS:
    1. Build ChatRequest (stream=false, tools=...)
    2. provider.chat() → get response
    3. If tool_calls → execute → append results → continue
    4. If content → stream_response() → break
    5. If empty → stream_response(stream=true, tools=None) → break
```

**Python Phase 100 design:**
```
async def run_turn(messages, tools, provider, context, config) -> AsyncIterator[RunEvent]:
    for round in range(config.max_turns):
        yield phase_changed("research" or "draft" or ...)
        yield thought_delta("正在分析...")

        # ALWAYS stream — even during tool rounds
        async for delta in provider.chat_stream(request):
            if delta.is_reasoning:
                yield thought_delta(delta.reasoning)
            if delta.is_content:
                yield message_delta(delta.content)
            if delta.is_tool_call:
                yield tool_call_started(delta.tool_call)

        if tool_calls:
            for tool_call in tool_calls:
                yield tool_call_started(tool_call)
                result = await execute_tool(tool_call)
                yield tool_call_delta(tool_call.id, progress)
                yield tool_call_completed(tool_call.id, result)
                append to messages
            continue  # next round

        # No tool calls → final content already streamed
        yield message_completed(full_content)
        yield run_state_changed("succeeded")
        return

    # Turn limit reached
    yield error("turn_limit_exceeded")
    yield run_state_changed("failed")
```

**Key differences from Rust:**
1. **Always streaming**: `provider.chat_stream()` instead of `provider.chat()` — even during tool rounds
2. **Events during tools**: `tool_call.started|delta|completed` events emitted during tool execution
3. **Thought deltas**: `thought.delta` events for reasoning content during tool rounds
4. **Silence threshold**: EventEmitter enforces no gap > threshold between events
5. **Turn limit**: Configurable `max_turns` (default 10, matching Rust's MAX_TOOL_ROUNDS)

### 8. Tool Call Streaming — Fixing the Silence Problem

**Rust problem (chat.rs lines 765-890):**
During tool rounds, the flow is:
1. `emit_stream_status("thinking")` — one Tauri event
2. `provider.chat()` — **blocks** (no events for entire LLM call duration)
3. `emit_stream_status("tool")` — one Tauri event
4. `run_traced_tool_calls()` — **blocks** (no events for all tool executions)
5. `continue` — back to step 1

No `thought.delta` or `tool_call.*` events are emitted. The client sees only status string changes.

**Python fix:**
1. `yield thought_delta("正在检索相关法规...")` — before LLM call
2. `async for delta in provider.chat_stream(request):` — stream LLM response
   - `yield thought_delta(delta.reasoning)` — reasoning content as it arrives
   - Accumulate tool_calls from stream
3. For each tool_call:
   - `yield tool_call_started(tool_call.id, tool_call.name)` — before execution
   - `yield tool_call_delta(tool_call.id, "正在执行...")` — during execution
   - `result = await execute_tool(tool_call)` — actual execution
   - `yield tool_call_completed(tool_call.id, result)` — after execution
4. `yield thought_delta("工具执行完成，正在整合结果...")` — transition

**Event silence threshold:**
The EventEmitter tracks `last_event_time`. If no event has been emitted for > `silence_threshold_seconds` (default 5s), it emits a `thought.delta` heartbeat with a progress message. This ensures the client never experiences "整轮静默".

## Key Decisions (Auto-Selected)

### 1. Package Location: New `packages/agent-core/`

[auto] Q: "Where should the agent core code live?" → Selected: "New package `packages/agent-core/`" (recommended default)

**Rationale:** Follows the package-per-concern pattern established throughout V3. Phase 100 creates the skeleton; Phases 101-103 add tools, guardrails, and dual entry points into the same package. A new gate `agent-core` is registered in `scripts/run_v2_gates.py` with `agent_core_src` path variable.

### 2. Turn Loop Architecture: Async generator yielding unified events

[auto] Q: "How to structure the async turn loop?" → Selected: "Async generator (`async def run_turn() -> AsyncIterator[RunEvent]`) yielding Phase 88 unified events" (recommended)

**Rationale:** The turn loop is an async generator that yields `RunEvent` objects. This design:
- Naturally composes with SSE streaming (Gateway consumes the generator)
- Allows interleaving LLM streaming deltas with tool execution events
- Makes the silence threshold enforceable at the generator level
- Matches the `stream_events()` method in the BackendAdapter Protocol
- The Rust original uses Tauri event emission (push model); the Python version uses pull-based async iteration, which is cleaner for streaming

### 3. Tool Call Streaming: Always-stream with interleaved tool events

[auto] Q: "How to emit events during tool calls (fixing the silence problem)?" → Selected: "Always stream LLM responses (even during tool rounds); emit `tool_call.started|delta|completed` around each tool execution; emit `thought.delta` heartbeats" (recommended — fixes the known defect)

**Rationale:** The Rust original calls `provider.chat()` (non-streaming) during tool rounds, causing complete event silence. The Python fix:
- Uses `provider.chat_stream()` for ALL rounds (tool rounds and final content rounds)
- Emits `tool_call.started` before each tool execution, `tool_call.delta` during, `tool_call.completed` after
- Emits `thought.delta` for reasoning content and as heartbeat during long operations
- The EventEmitter enforces a silence threshold (default 5s) — if no event for > threshold, emit a `thought.delta` heartbeat

### 4. Event Emission: EventEmitter helper with seq numbering and silence threshold

[auto] Q: "How to map to Phase 88 unified events?" → Selected: "EventEmitter helper class that wraps the async generator, assigns seq numbers, enforces silence threshold, and produces RunEvent objects with typed payloads" (recommended)

**Rationale:** A dedicated `EventEmitter` class:
- Wraps the turn loop's async generator
- Assigns monotonic `seq` numbers for SSE replay (Phase 91 Last-Event-ID support)
- Tracks `last_event_time` and emits heartbeat `thought.delta` if silence > threshold
- Creates `RunEvent` objects with the correct `event_type`, `payload` (from `unified_events.py` dataclasses), `occurred_at`, `seq`
- Provides convenience methods: `emit_message_delta()`, `emit_thought_delta()`, `emit_tool_call_started()`, `emit_tool_call_completed()`, `emit_error()`, `emit_state_changed()`

### 5. Provider Abstraction: Unified LlmProvider Protocol with streaming + tool calls

[auto] Q: "How to unify OpenAI/Anthropic/Ollama?" → Selected: "Unified `LlmProvider` Protocol with `async def chat_stream(request) -> AsyncIterator[StreamDelta]` where StreamDelta includes content, reasoning, tool_calls, and finish_reason" (recommended)

**Rationale:** The Rust `LlmProvider` trait has separate `chat()` and `chat_stream()` methods. The Python version unifies into a single `chat_stream()` method that always streams. `StreamDelta` is a union type:
- `ContentDelta(content: str)` — text content
- `ReasoningDelta(reasoning: str)` — thinking/reasoning content
- `ToolCallDelta(tool_call_id: str, tool_name: str, arguments: str)` — tool call from LLM
- `UsageDelta(usage: dict)` — token usage
- `FinishDelta(finish_reason: str)` — stream end

Each provider runner (OpenAI, Anthropic, Ollama) implements this Protocol by translating their native streaming format. The transport abstraction pattern from `provider_model` is preserved (injectable transports for testing).

### 6. Context Budget: Combine context_assembler + body_injector patterns

[auto] Q: "How to integrate context-assembler?" → Selected: "New `AgentContextAssembler` in agent-core that combines the conversation history trimming pattern from `context_assembler.py` with the skill body injection pattern from `body_injector.py`" (recommended)

**Rationale:** Phase 97's `body_injector.py` already implements section-priority deterministic trim for SKILL.md bodies with CJK-aware token estimation. The platform-runtime's `context_assembler.py` implements conversation history trimming with a protected-then-trim order. Phase 100's `AgentContextAssembler` combines both:
- System prompt (protected, never trimmed)
- Skill body injection (section-priority trim from body_injector)
- Conversation history (feedback → memory → recent → artifact trim order from context_assembler)
- Total budget enforcement across all sections
- Deterministic: same input + same budget → same output
- Records `dropped_sections` and `trimmed_skill_sections` for observability

### 7. Fixture Provider: Scripted FixtureProvider with configurable event sequences

[auto] Q: "How to test without external LLM?" → Selected: "Scripted `FixtureProvider` that accepts a list of `TurnScript` objects, each containing pre-configured stream deltas, tool calls, and timing" (recommended)

**Rationale:** The existing `FakeOpenAITransport` / `FakeAnthropicTransport` / `FakeOllamaTransport` patterns are too simple for testing the turn loop — they return a single response, not a multi-turn tool orchestration sequence. The `FixtureProvider` accepts a script:
```python
script = [
    TurnScript(deltas=[ToolCallDelta("call_1", "legal_search", '{"query":"合同法"}')]),
    TurnScript(deltas=[ContentDelta("根据检索结果...")]),
]
provider = FixtureProvider(script)
```
This enables testing:
- Multi-turn tool orchestration without real API calls
- The silence threshold assertion (configurable delays between deltas)
- Tool call streaming events
- Error recovery (script can include error deltas)
- Turn limit enforcement (script with N > max_turns rounds)

### 8. Turn Limit: Configurable max_turns (default 10)

[auto] Q: "What's the max turns? How to enforce?" → Selected: "Configurable `max_turns` (default 10, matching Rust's MAX_TOOL_ROUNDS); when exceeded, emit `error` event with `turn_limit_exceeded` code and `run.state_changed` to failed" (recommended)

**Rationale:** The Rust original uses `MAX_TOOL_ROUNDS = 10` (chat_tools.rs line 32). The Python version makes this configurable via `AgentCoreConfig.max_turns` (default 10). When the turn limit is reached:
- Emit `error` event with `code="turn_limit_exceeded"`, `message="达到最大轮次上限"`
- Emit `run.state_changed` with `status="failed"`
- Stop the generator

This prevents infinite tool-calling loops and is testable with the FixtureProvider.

### 9. Error Recovery: Tool failures produce error events, not crashes

[auto] Q: "How to handle tool failures without crashing?" → Selected: "Tool failures produce `tool_call.completed` with `status="error"` and `error` field; the turn loop appends the error as a tool result message and continues to the next round; if the LLM cannot recover after max_turns, emit `error` event" (recommended)

**Rationale:** The Rust original returns `Err(String)` from `execute_tool()`, which propagates up and crashes the turn. The Python version:
- Catches tool execution exceptions
- Emits `tool_call.completed` with `status="error"` and `ErrorInfo` in the payload
- Appends the error message as a tool result (`role="tool"`, `content="Error: ..."`) to the message history
- Continues to the next round — the LLM can see the error and decide to retry, use a different tool, or produce a final answer
- If the LLM keeps failing until `max_turns`, the turn limit handler kicks in

This is more resilient than the Rust original and matches the success criterion: "工具失败不导致整轮崩溃而是产出 `error` 事件并可恢复" (from Phase 101, but the skeleton should support it).

### 10. Model Layer Merge: Move runners into agent-core, preserve transports

[auto] Q: "How to merge backends/provider_model into agent-core?" → Selected: "Copy the three runners (OpenAI, Anthropic, Ollama), their transports, response parsers, and error normalization into `packages/agent-core/src/inkstatute_agent_core/model/`; preserve the transport abstraction for testing; add streaming + tool call support that the current runners lack" (recommended)

**Rationale:** CORE-09 says the model layer is "由 `packages/backends/provider_model` 归并而来". The merge:
- **Copies** (not moves — provider_model stays for backward compat until Phase 104): `openai_runner.py`, `anthropic_runner.py`, `ollama_runner.py`, `error_normalization.py`, `config.py`
- **Preserves**: Transport Protocol pattern, lazy SDK import, Fake transports, error normalization
- **Adds**: Streaming with tool call support (current runners only stream content, not tool calls), unified `LlmProvider` Protocol, `StreamDelta` union type
- **Does NOT copy**: `ProviderModelBackendAdapter` (agent-core has its own adapter in Phase 103), `manifest.py` (agent-core declares its own capabilities)

### 11. Circuit Breaker Reuse: Import model-gateway components directly

[auto] Q: "How to reuse model-gateway's circuit breaker?" → Selected: "Import `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` from `inkstatute_model_gateway` directly; wrap each provider call through circuit breaker + rate limiter; record usage in cost tracker" (recommended)

**Rationale:** The model-gateway components are designed for reuse — they have no external dependencies (`dependencies = []` invariant) and accept injectable clocks for testing. The agent-core's model layer:
- Creates a `CircuitBreakerRegistry` per provider
- Creates a `RateLimiter` with per-provider configs
- Creates a `CostTracker` with pricing and budgets
- Before each provider call: check circuit breaker → check rate limit → acquire concurrency
- After each provider call: record success/failure in circuit breaker → record request in rate limiter → record usage in cost tracker
- Usage data flows into events via `RunStateChangedPayload.metadata["provider_usage"]`

### 12. Usage Data in Events: Attach to run.state_changed and message.completed

[auto] Q: "How to flow usage data into event stream?" → Selected: "Attach `provider_usage` dict to `message.completed` payload metadata and `run.state_changed` payload metadata; accumulate across all rounds in a turn" (recommended)

**Rationale:** The model-gateway's `_extract_usage_from_run()` already extracts `provider_usage` from Run metadata. The agent-core:
- Accumulates usage across all rounds in a turn (prompt_tokens, completion_tokens, total_tokens)
- Attaches to `MessageCompletedPayload.metadata["provider_usage"]` — final content event
- Attaches to `RunStateChangedPayload.metadata["provider_usage"]` — terminal state event
- The cost tracker uses the same usage dict for cost calculation
- Usage is sanitized (no model names, no API keys) — following the existing `_sanitize_usage()` pattern

## Dependencies

- **Phase 88** (unified events) — provides `RunEvent`, `unified_events.py` payload dataclasses, `RunEventType` enum
- **Phase 97** (skill materialization) — provides `body_injector.py` pattern for skill body injection, `skill-index.json` for skill metadata
- **packages/model-gateway** — provides `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` for reuse
- **packages/backends/provider_model** — provides runner patterns, transport abstractions, error normalization for merge
- **packages/platform-runtime** — provides `context_assembler.py` pattern, `RunRequest`, `RunEvent`, `RunHandle` types
- **packages/platform-contract** — provides `unified_events.py`, `enums.py`, `events.py` dataclasses

## Package Structure (Proposed)

```
packages/agent-core/
├── src/inkstatute_agent_core/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry (Phase 103)
│   ├── turn_loop.py             # Async turn loop generator
│   ├── event_emitter.py         # EventEmitter with seq + silence threshold
│   ├── context.py               # AgentContextAssembler (history + skill bodies)
│   ├── config.py                # AgentCoreConfig (max_turns, silence_threshold, budget)
│   ├── fixtures.py              # FixtureProvider, TurnScript for testing
│   ├── model/
│   │   ├── __init__.py
│   │   ├── provider.py          # LlmProvider Protocol, StreamDelta types
│   │   ├── openai_runner.py     # OpenAI-compatible (merged from provider_model)
│   │   ├── anthropic_runner.py  # Anthropic Messages API (merged)
│   │   ├── ollama_runner.py     # Ollama OpenAI-compatible (merged)
│   │   ├── error_normalization.py  # Shared error sanitization (merged)
│   │   └── gateway_components.py   # Circuit breaker / rate limiter / cost tracker wrappers
│   └── tools/                   # Phase 101 (empty in Phase 100)
│       └── __init__.py
├── tests/
│   ├── test_turn_loop.py        # Turn loop tests with FixtureProvider
│   ├── test_event_emitter.py    # EventEmitter seq + silence threshold tests
│   ├── test_context.py          # Context assembler tests
│   ├── test_fixture_provider.py # Fixture provider tests
│   ├── test_model_layer.py      # Model layer streaming + tool call tests
│   ├── test_silence_threshold.py # Silence threshold assertion tests
│   └── fixtures/
│       └── turn_scripts.py      # Pre-configured turn scripts for tests
└── pyproject.toml
```

## Gate Registration

New gate `agent-core` must be registered in `scripts/run_v2_gates.py`:
- Add `agent_core_src` path variable
- Add `Gate("agent-core", ...)` entry with correct PYTHONPATH
- Add `packages/agent-core/src` to compileall paths
- Update `test_audit_v2_requirements.py` gate count assertion (37 → 38)
- `gate-coverage` meta-test auto-discovers `packages/agent-core/src`

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Streaming with tool calls varies across providers (OpenAI streams tool_call deltas, Anthropic doesn't) | Unified `StreamDelta` type with provider-specific translation; FixtureProvider tests cover all delta types |
| Silence threshold heartbeat may confuse event consumers | Heartbeat `thought.delta` events have `metadata={"heartbeat": true}` for filtering |
| Merging provider_model runners creates code duplication until Phase 104 | Acceptable — provider_model stays for backward compat; Phase 104 retires it |
| Context budget with skill bodies (2K-20K tokens) may exceed typical context windows | Budget is configurable; default is generous (32K tokens); trim report records what was cut |
| FixtureProvider scripts may not cover all real LLM behaviors | Scripts are extensible; real provider tests are deferred to integration testing (not in CI) |
