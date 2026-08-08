# Phase 100 Discussion Log — Agent Core Skeleton

**Phase:** 100 — Agent Core Skeleton
**Mode:** auto
**Date:** 2026-08-11
**Requirements:** CORE-01, CORE-04, CORE-09

---

## Gray Area Analysis

12 gray areas identified, all auto-selected with recommended options.

---

### Gray Area 1: Turn Loop Architecture

**Question:** How to structure the async turn loop?

**Options considered:**
- A) Async generator yielding unified events (`async def run_turn() -> AsyncIterator[RunEvent]`)
- B) Callback-based with event emission functions
- C) Actor model with message passing
- D) Direct port of Rust's synchronous loop with async wrappers

**Selected: A — Async generator yielding unified events**

**Rationale:** The turn loop is an async generator that yields `RunEvent` objects. This design naturally composes with SSE streaming (the Gateway consumes the generator via `stream_events()`), allows interleaving LLM streaming deltas with tool execution events, and makes the silence threshold enforceable at the generator level. It matches the `BackendAdapter.stream_events()` method returning `AsyncIterator[RunEvent]`. The Rust original uses Tauri event emission (push model); the Python version uses pull-based async iteration, which is cleaner for streaming and testable with `FixtureProvider`.

**Evidence:**
- `packages/platform-contract/src/platform_contract/unified_events.py` — 15 typed payload dataclasses
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` line 170 — `async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]`
- Rust `commands/chat.rs` line 765 — `for round in 0..MAX_TOOL_ROUNDS` loop

---

### Gray Area 2: Tool Call Streaming (Fixing the Silence Problem)

**Question:** How to emit events during tool calls to fix the "整轮静默" defect?

**Options considered:**
- A) Always stream LLM responses; emit `tool_call.started|delta|completed` around each tool; emit `thought.delta` heartbeats
- B) Non-streaming tool rounds but with periodic status events
- C) Separate streaming thread for tool round progress
- D) Port Rust behavior as-is (non-streaming tool rounds)

**Selected: A — Always stream with interleaved tool events**

**Rationale:** The Rust original (chat.rs line 782) uses `stream: false` during tool rounds, causing complete event silence — no `thought.delta`, no `tool_call.*` events. The client sees only status string changes ("thinking" / "tool"). This is the known defect that PROJECT.md Key Decision #7 explicitly calls out: "工具轮必须流式 — lawyer-desktop 现状是工具轮非流式（先整轮拿 tool_calls，仅最终 content 流），这是要修的缺陷而非要移植的资产". The fix uses `provider.chat_stream()` for ALL rounds, emits `tool_call.started` before each tool execution, `tool_call.delta` during, `tool_call.completed` after, and `thought.delta` for reasoning content and heartbeats.

**Evidence:**
- `lawyer-desktop/src-tauri/src/commands/chat.rs` line 782 — `stream: false` during tool rounds
- `lawyer-desktop/src-tauri/src/commands/chat.rs` line 854 — `emit_stream_status("tool")` (only a status string, not a unified event)
- `.planning/PROJECT.md` Key Decision — "工具轮必须流式"
- Success criterion 2 — "测试断言从提交到最终回复之间不存在超过阈值的事件静默期"

---

### Gray Area 3: Event Emission Mapping

**Question:** How to map agent core events to Phase 88 unified events?

**Options considered:**
- A) EventEmitter helper class with seq numbering, silence threshold, and typed payload convenience methods
- B) Direct `RunEvent` construction at each emission point
- C) Event bus / pub-sub pattern
- D) Separate event emitter per event type

**Selected: A — EventEmitter helper class**

**Rationale:** A dedicated `EventEmitter` class wraps the turn loop's async generator, assigns monotonic `seq` numbers (for SSE replay via Last-Event-ID), tracks `last_event_time` for silence threshold enforcement, and creates `RunEvent` objects with typed payloads from `unified_events.py` dataclasses. It provides convenience methods (`emit_message_delta()`, `emit_thought_delta()`, `emit_tool_call_started()`, etc.) that keep the turn loop code clean and ensure consistent event structure.

**Evidence:**
- `packages/platform-contract/src/platform_contract/unified_events.py` — `serialize_payload()`, `EVENT_TYPE_TO_PAYLOAD_CLASS` mapping
- `packages/platform-contract/src/platform_contract/enums.py` lines 100-124 — `RunEventType` with V3 unified types
- Phase 91 Gateway SSE — `Last-Event-ID` by `seq` replay

---

### Gray Area 4: Provider Abstraction

**Question:** How to unify OpenAI/Anthropic/Ollama providers?

**Options considered:**
- A) Unified `LlmProvider` Protocol with `async def chat_stream(request) -> AsyncIterator[StreamDelta]` where StreamDelta includes content, reasoning, tool_calls, and finish_reason
- B) Separate `chat()` and `chat_stream()` methods (matching Rust trait)
- C) Provider-specific interfaces with adapter layer
- D) Use LiteLLM or similar third-party abstraction

**Selected: A — Unified LlmProvider Protocol with streaming-only interface**

**Rationale:** The Rust `LlmProvider` trait has separate `chat()` and `chat_stream()` methods, which led to the non-streaming tool round defect. The Python version unifies into a single `chat_stream()` method that always streams. `StreamDelta` is a union type covering content, reasoning, tool calls, usage, and finish reason. Each provider runner translates its native streaming format to this unified type. The transport abstraction pattern from `provider_model` is preserved for testing.

**Evidence:**
- `lawyer-desktop/src-tauri/src/llm/provider.rs` — `LlmProvider` trait with `chat()` and `chat_stream()`
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` line 209 — `parse_sse_deltas()` already parses SSE streaming
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` line 58 — `ProviderModelStreamDelta(content, finish_reason)`

---

### Gray Area 5: Context Budget Integration

**Question:** How to integrate context-assembler for skill body injection?

**Options considered:**
- A) New `AgentContextAssembler` combining context_assembler.py history trimming + body_injector.py skill body injection
- B) Reuse `ContextAssembler` from platform-runtime directly
- C) Reuse `SkillBodyInjector` from skill-materializer directly
- D) Build a new context assembler from scratch

**Selected: A — Combine both existing patterns**

**Rationale:** Phase 97's `body_injector.py` implements section-priority deterministic trim for SKILL.md bodies with CJK-aware token estimation. The platform-runtime's `context_assembler.py` implements conversation history trimming with protected-then-trim order. Phase 100's `AgentContextAssembler` combines both: system prompt (protected), skill body injection (section-priority trim), conversation history (feedback → memory → recent → artifact trim), total budget enforcement, deterministic output, and trim reporting.

**Evidence:**
- `packages/platform-runtime/src/platform_runtime/context_assembler.py` lines 82-90 — `ContextAssemblyPolicy` with budget_tokens, trim_strategy
- `packages/platform-runtime/src/platform_runtime/context_assembler.py` lines 237-276 — trim algorithm
- `packages/skill-materializer/src/inkstatute_skill_materializer/body_injector.py` lines 1-30 — section-priority trim with CJK-aware token estimation
- Phase 97 CONTEXT.md gray area 6 — "Section-priority deterministic trim with trim report"

---

### Gray Area 6: Fixture Provider for Testing

**Question:** How to test the turn loop without external LLM calls?

**Options considered:**
- A) Scripted `FixtureProvider` with `TurnScript` objects containing pre-configured stream deltas and tool calls
- B) Extend existing `FakeOpenAITransport` to support multi-turn scripts
- C) Mock at the HTTP level with recorded responses
- D) Use a local Ollama instance in CI

**Selected: A — Scripted FixtureProvider**

**Rationale:** The existing `FakeOpenAITransport` / `FakeAnthropicTransport` / `FakeOllamaTransport` patterns return a single response, not a multi-turn tool orchestration sequence. The `FixtureProvider` accepts a list of `TurnScript` objects, each containing pre-configured `StreamDelta` lists. This enables testing multi-turn tool orchestration, the silence threshold assertion (with configurable delays), tool call streaming events, error recovery, and turn limit enforcement — all without real API calls. Success criterion 6 requires "全部测试可在无外部 LLM 的情况下用 fixture provider 运行".

**Evidence:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` line 65 — `FakeOpenAITransport` (single response)
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` line 478 — `FakeStreamingProviderModelRunner` (list of deltas)
- Success criterion 6 — "全部测试可在无外部 LLM 的情况下用 fixture provider 运行"

---

### Gray Area 7: Turn Limit

**Question:** What's the max turns? How to enforce?

**Options considered:**
- A) Configurable `max_turns` (default 10, matching Rust's MAX_TOOL_ROUNDS); emit `error` + `run.state_changed` when exceeded
- B) Hard-coded 10 turns
- C) No limit (rely on LLM to stop calling tools)
- D) Configurable with different defaults per mode (Chat/Draft/Evidence)

**Selected: A — Configurable max_turns (default 10)**

**Rationale:** The Rust original uses `MAX_TOOL_ROUNDS = 10` (chat_tools.rs line 32). The Python version makes this configurable via `AgentCoreConfig.max_turns` (default 10). When exceeded, emit `error` event with `code="turn_limit_exceeded"` and `run.state_changed` to failed. This prevents infinite tool-calling loops and is testable with FixtureProvider scripts that exceed the limit.

**Evidence:**
- `lawyer-desktop/src-tauri/src/commands/chat_tools.rs` line 32 — `pub const MAX_TOOL_ROUNDS: usize = 10`
- Success criterion 1 — "有多轮工具编排与轮次上限"

---

### Gray Area 8: Error Recovery

**Question:** How to handle tool failures without crashing the turn loop?

**Options considered:**
- A) Tool failures produce `tool_call.completed` with `status="error"`; error appended as tool result; LLM can recover in next round
- B) Tool failures crash the turn with an `error` event
- C) Tool failures trigger automatic retry (matching Rust's leak retry pattern)
- D) Tool failures are silently logged and the turn continues

**Selected: A — Error events with recovery**

**Rationale:** The Rust original returns `Err(String)` from `execute_tool()`, which propagates up and can crash the turn. The Python version catches tool execution exceptions, emits `tool_call.completed` with `status="error"` and `ErrorInfo`, appends the error as a tool result message, and continues to the next round. The LLM sees the error and can retry, use a different tool, or produce a final answer. This is more resilient and matches Phase 101's success criterion: "工具失败不导致整轮崩溃而是产出 `error` 事件并可恢复".

**Evidence:**
- `lawyer-desktop/src-tauri/src/commands/chat_tools.rs` line 329 — `execute_tool` returns `Result<String, String>`
- `packages/platform-contract/src/platform_contract/unified_events.py` line 69 — `ToolCallCompletedPayload` has `error: ErrorInfo | None` field
- Phase 101 success criterion 2 — "工具失败不导致整轮崩溃而是产出 `error` 事件并可恢复"

---

### Gray Area 9: Model Layer Merge Strategy

**Question:** How to merge backends/provider_model into agent-core?

**Options considered:**
- A) Copy runners, transports, parsers, error normalization into agent-core; preserve transport abstraction; add streaming + tool call support; leave provider_model in place until Phase 104
- B) Move all code from provider_model to agent-core; delete provider_model immediately
- C) Import provider_model as a dependency (no merge)
- D) Rewrite from scratch using the same patterns

**Selected: A — Copy with enhancements, leave original for Phase 104**

**Rationale:** CORE-09 says the model layer is "由 `packages/backends/provider_model` 归并而来". The merge copies the three runners, their transports, response parsers, and error normalization into `packages/agent-core/src/inkstatute_agent_core/model/`. The transport abstraction pattern is preserved. Streaming with tool call support is added (current runners only stream content, not tool calls). `ProviderModelBackendAdapter` is NOT copied (agent-core has its own adapter in Phase 103). `provider_model` stays in place for backward compat until Phase 104 (CONV-01).

**Evidence:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/` — 8 source files
- REQUIREMENTS.md CORE-09 — "由 `packages/backends/provider_model` 归并而来"
- Phase 104 CONV-01 — retires `packages/backends/hermes` and `packages/backends/codex` (provider_model retirement not explicitly listed but implied by merge)

---

### Gray Area 10: Circuit Breaker Reuse

**Question:** How to reuse model-gateway's circuit breaker, rate limiter, and cost tracker?

**Options considered:**
- A) Import `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` from `inkstatute_model_gateway` directly; wrap each provider call
- B) Copy the code into agent-core (duplicate)
- C) Create a new gateway wrapper around agent-core's model layer
- D) Use model-gateway's `ModelProviderGateway` composite adapter

**Selected: A — Import directly from model-gateway**

**Rationale:** The model-gateway components are designed for reuse — they have no external dependencies (`dependencies = []` invariant) and accept injectable clocks for testing. The agent-core imports them directly and wraps each provider call through circuit breaker → rate limiter → cost tracker. The `ModelProviderGateway` composite adapter is NOT needed (agent-core is a single backend, not a composite of multiple backends).

**Evidence:**
- `packages/model-gateway/src/inkstatute_model_gateway/circuit_breaker.py` — `CircuitBreakerRegistry` with injectable clock
- `packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py` — `RateLimiter` with injectable clock
- `packages/model-gateway/src/inkstatute_model_gateway/cost_tracker.py` — `CostTracker` with `PricingRate`, `BudgetCeiling`
- Success criterion 5 — "模型层复用 `packages/model-gateway` 的熔断 / 限流 / 成本追踪"

---

### Gray Area 11: Usage Data in Events

**Question:** How to flow usage data into the event stream?

**Options considered:**
- A) Attach `provider_usage` to `message.completed` and `run.state_changed` payload metadata; accumulate across rounds
- B) Separate `usage.updated` event type
- C) Attach to every `message.delta` event
- D) Only in Run metadata (not in events)

**Selected: A — Attach to message.completed and run.state_changed**

**Rationale:** Usage data (prompt_tokens, completion_tokens, total_tokens) is accumulated across all rounds in a turn and attached to the `MessageCompletedPayload.metadata["provider_usage"]` and `RunStateChangedPayload.metadata["provider_usage"]`. This follows the existing pattern in `model-gateway/gateway.py` where `_extract_usage_from_run()` extracts `provider_usage` from Run metadata. The cost tracker uses the same usage dict for cost calculation. Usage is sanitized (no model names, no API keys) following the existing `_sanitize_usage()` pattern.

**Evidence:**
- `packages/model-gateway/src/inkstatute_model_gateway/gateway.py` line 361 — `_extract_usage_from_run(run)` extracts `provider_usage`
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` line 244 — `_sanitize_usage()` keeps only safe token-count fields
- `packages/platform-contract/src/platform_contract/unified_events.py` line 39 — `MessageCompletedPayload` has `metadata: JsonObject`
- Success criterion 5 — "`usage` 数据进入事件流"

---

### Gray Area 12: Package Location and Gate Registration

**Question:** Where should the agent core code live and how to register its gate?

**Options considered:**
- A) New `packages/agent-core/` with `agent_core_src` path variable and `Gate("agent-core", ...)` entry
- B) Add to existing `packages/platform-runtime/`
- C) Add to existing `packages/backends/` as a new sub-package
- D) New top-level `services/agent-core/`

**Selected: A — New packages/agent-core/ with dedicated gate**

**Rationale:** Follows the package-per-concern pattern established throughout V3. Phase 100 creates the skeleton; Phases 101-103 add tools, guardrails, and dual entry points into the same package. A new gate `agent-core` is registered in `scripts/run_v2_gates.py` with `agent_core_src` path variable, `Gate("agent-core", ...)` entry, and compileall path. The `gate-coverage` meta-test auto-discovers `packages/agent-core/src`. Gate count assertion in `test_audit_v2_requirements.py` updates from 37 to 38.

**Evidence:**
- AGENTS.md — "Every new `packages/*/src` and `services/*/src` directory must be covered by a gate"
- Phase 97-04-SUMMARY.md — gate registration pattern (path variable + Gate() entry + compileall + gate count update)
- `scripts/run_v2_gates.py` — existing gate registration pattern

---

## Summary

| # | Gray Area | Selected Option |
|---|-----------|-----------------|
| 1 | Turn loop architecture | Async generator yielding unified events |
| 2 | Tool call streaming | Always-stream with interleaved tool events |
| 3 | Event emission mapping | EventEmitter helper with seq + silence threshold |
| 4 | Provider abstraction | Unified LlmProvider Protocol with StreamDelta union |
| 5 | Context budget integration | Combine context_assembler + body_injector patterns |
| 6 | Fixture provider | Scripted FixtureProvider with TurnScript objects |
| 7 | Turn limit | Configurable max_turns (default 10) |
| 8 | Error recovery | Tool failures produce error events, LLM can recover |
| 9 | Model layer merge | Copy runners + transports into agent-core, enhance with streaming + tool calls |
| 10 | Circuit breaker reuse | Import model-gateway components directly |
| 11 | Usage data in events | Attach to message.completed and run.state_changed metadata |
| 12 | Package location | New packages/agent-core/ with dedicated gate |

All 12 gray areas auto-selected with recommended options. No unresolved questions.
