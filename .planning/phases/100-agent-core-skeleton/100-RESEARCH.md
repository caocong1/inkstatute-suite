# Phase 100 Research — Agent Core Skeleton

**Phase:** 100 — Agent Core Skeleton
**Created:** 2026-08-11
**Status:** Complete
**Requirements:** CORE-01, CORE-04, CORE-09

---

## 1. lawyer-desktop Rust Agent Core — The Original to Port

### 1.1 Location & File Inventory

**Repository:** `/home/sorawatcher/workspace/lawyer-desktop/` (sibling repo, Tauri 2.11 + SolidJS)
**Rust source root:** `src-tauri/src/`

The Rust agent core is spread across 63 `.rs` files totaling **15,323 lines**. The files most relevant to Phase 100 are:

| File | Lines | Role | Phase 100 relevance |
|------|-------|------|---------------------|
| `commands/chat.rs` | 2,000 | Main turn loop (`send_message` command) | **Primary port target** — turn loop structure |
| `commands/chat_tools.rs` | 877 | Tool execution, streaming, message building | Tool execution pattern, `MAX_TOOL_ROUNDS` |
| `llm/mod.rs` | 130 | `LlmEngine` with active + fast provider slots | Provider management pattern |
| `llm/provider.rs` | 17 | `LlmProvider` trait | **Provider interface to port** |
| `llm/openai_compat.rs` | 120 | OpenAI-compatible streaming via `reqwest` | Streaming implementation reference |
| `llm/types.rs` | 102 | `ChatMessage`, `ToolCall`, `ChatRequest`, `ChatResponse`, `Usage` | Type definitions to port |
| `llm/tool_leak.rs` | 392 | Tool call leakage detection | Phase 102 (not 100) |
| `skills/router.rs` | 627 | System prompt assembly, research-gate injection | Phase 102 (not 100) |
| `skills/agent_classifier.rs` | 691 | Chat/Draft/Evidence mode classifier | Already ported in Phase 98 |
| `citations/` | 589 (3 files) | Citation extraction + verification | Phase 102 (not 100) |

### 1.2 Provider Trait (llm/provider.rs — 17 lines)

The entire Rust provider abstraction is a 17-line trait:

```rust
pub type ChatStream = Pin<Box<dyn Stream<Item = Result<String>> + Send>>;

#[async_trait]
pub trait LlmProvider: Send + Sync {
    async fn chat(&self, request: &ChatRequest) -> Result<ChatResponse>;
    async fn chat_stream(&self, request: &ChatRequest) -> Result<ChatStream>;
    fn supports_tools(&self) -> bool;
    fn model_name(&self) -> &str;
    fn config(&self) -> &ProviderConfig;
}
```

**Key observations:**
- `chat()` and `chat_stream()` are **separate methods** — the turn loop chooses which to call
- `chat_stream()` returns `Stream<Item = Result<String>>` — raw string chunks, no structured deltas
- No tool call support in streaming mode — `chat_stream()` only streams content text
- `supports_tools()` is a capability flag (all current implementations return `true`)

### 1.3 OpenAI-Compatible Provider (llm/openai_compat.rs — 120 lines)

Single concrete implementation of `LlmProvider`:

```rust
pub struct OpenAiCompatProvider {
    config: ProviderConfig,
    client: Arc<Client>,
}
```

- Uses `reqwest::Client` with 30s connect timeout, 300s total timeout
- `chat()`: non-streaming POST to `/chat/completions`, deserializes `ChatResponse`
- `chat_stream()`: streaming POST with `stream: true`, uses `response.bytes_stream().map()` to convert byte chunks to `String` chunks
- Bearer auth from `config.api_key`
- **No Anthropic or Ollama native support** — all providers go through OpenAI-compatible endpoint

### 1.4 Provider Presets (llm/mod.rs lines 65-122)

Five preset providers, all using OpenAI-compatible API:
- **qwen** — `dashscope.aliyuncs.com/compatible-mode/v1`, model `qwen-plus`
- **deepseek** — `api.deepseek.com/v1`, model `deepseek-chat`
- **kimi** — `api.moonshot.cn/v1`, model `moonshot-v1-8k`
- **openai** — `api.openai.com/v1`, model `gpt-4o`
- **ollama** — `localhost:11434/v1`, model `qwen2.5:7b`

Fast model presets (for routing/classification):
- **deepseek** — `deepseek-chat`
- **qwen** — `qwen-turbo`
- **ollama** — `qwen2.5:3b`

### 1.5 Turn Loop Architecture (chat.rs lines 765-1104)

The Rust turn loop is a `for round in 0..MAX_TOOL_ROUNDS` loop:

```
MAX_TOOL_ROUNDS = 10  (chat_tools.rs line 32)
MAX_LEAK_RETRIES = 3  (chat.rs line 36)
MAX_CONTINUATIONS = 4 (chat.rs line 40)
RESPONSE_MAX_TOKENS = 8192 (chat.rs line 42)
```

**Per-round flow:**
1. Build `ChatRequest` with `stream: false` and tools (line 776-783)
2. Call `provider.chat()` — **non-streaming** (line 799)
3. If `tool_calls` present → `run_traced_tool_calls()` → `append_tool_results()` → `continue`
4. If embedded tool calls in content → `parse_embedded_tool_calls()` → execute → `continue`
5. If `contains_tool_leakage()` → retry (up to `MAX_LEAK_RETRIES`) or fallback
6. If content non-empty → `collect_with_continuations()` → `emit_text_response()` → `break`
7. If content empty → re-request with `stream: true`, `tools: None` → `stream_response()` → `break`

**Post-loop:**
- If `leak_fallback`: send one more non-streaming request without tools
- If `!streamed` (rounds exhausted): force a streaming request without tools
- Citation audit on the final response
- Save assistant message to SQLite

### 1.6 The "整轮静默" (Whole-Round Silence) Problem

**Root cause:** chat.rs line 782 — `stream: false`.

During tool rounds, the LLM is called in **non-streaming mode**. The client sees:

| Step | What happens | Events emitted | Duration |
|------|-------------|----------------|----------|
| 1 | `emit_stream_status("thinking")` | One Tauri event with status string | Instant |
| 2 | `provider.chat()` | **Nothing** — blocks until full response | 2-30+ seconds |
| 3 | `emit_stream_status("tool")` | One Tauri event with status string | Instant |
| 4 | `run_traced_tool_calls()` | **Nothing** — blocks until all tools complete | 1-60+ seconds |
| 5 | `continue` → back to step 1 | — | — |

**No `thought.delta` events.** No `tool_call.started|delta|completed` events. The only feedback is a status string ("thinking" / "tool") emitted via Tauri's `app.emit()`, which is not a unified event.

The Rust `Tracer` (commands/trace.rs) emits trace events (`tool_call`, `tool_result`, `skill_activated`) but these go to a separate trace panel, not to the chat stream. The chat stream is silent during tool rounds.

**Evidence from the code:**
- Line 774: `emit_stream_status(&app, &conversation_id, &message_id, "thinking")` — just a status string
- Line 782: `stream: false` — non-streaming LLM call
- Line 799: `provider.chat(&chat_request).await` — blocks
- Line 854: `emit_stream_status(&app, &conversation_id, &message_id, "tool")` — just a status string
- Line 855-863: `run_traced_tool_calls()` — blocks, emits only to Tracer (not chat stream)
- Line 889: `continue` — next round, back to silence

**Only the final content round uses streaming** (line 987-1027: `stream: true`, `tools: None`).

### 1.7 Tool Execution (chat_tools.rs)

**Tool types built** (line 658 in chat.rs → `build_all_tools()`):
- Builtin tools: `select_skill`, `ask_user`, `search_workspace`, `read_file_relative`, `fetch_url`, `generate_docx`
- MCP tools: dynamically discovered from `McpManager`

**Tool execution flow** (`run_traced_tool_calls()` in chat.rs lines 1394-1501):
1. For each `ToolCall` in the batch:
   - Emit `tool_call` trace event (to Tracer, not chat stream)
   - Execute tool via `execute_tool()`
   - Emit `tool_result` trace event
   - Track retrievals for citation audit
   - Track `ask_user` for clarification turn termination
2. Return `ToolBatch { results, ask_user, retrievals }`

**`ask_user` handling:** If `ask_user` tool is called, the turn is terminated immediately with `finish_ask_user_turn()` — emits a clarification card and saves a "waiting" message.

### 1.8 Continuation Handling (chat.rs lines 1505-1585)

`collect_with_continuations()` handles `finish_reason == "length"` (token-limit truncation):
- Appends the truncated segment as an assistant message
- Appends a user message with `CONTINUE_INSTRUCTION`
- Calls `provider.chat()` again (non-streaming)
- Repeats up to `MAX_CONTINUATIONS = 4` times
- Concatenates all segments

---

## 2. packages/model-gateway — Circuit Breaker, Rate Limiting, Cost Tracking

### 2.1 File Inventory

**Location:** `packages/model-gateway/src/inkstatute_model_gateway/`

| File | Lines | Purpose |
|------|-------|---------|
| `gateway.py` | 379 | `ModelProviderGateway` — composite BackendAdapter wrapping sub-adapters |
| `circuit_breaker.py` | 157 | `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN), `CircuitBreakerRegistry` |
| `rate_limiter.py` | 151 | `RateLimiter` — RPM/TPM sliding window + concurrency semaphore |
| `cost_tracker.py` | 154 | `CostTracker` — per-tenant/matter cost accumulation with budget ceilings |
| `config.py` | 52 | `ModelProviderGatewayConfig` — gateway_id, enabled, fallback_chain, pricing, budgets |

**Total: 893 lines across 6 files.** No external dependencies (`dependencies = []` invariant preserved).

### 2.2 Circuit Breaker Pattern (circuit_breaker.py)

Three-state machine: **CLOSED → OPEN → HALF_OPEN → CLOSED**

```
CircuitBreakerConfig:
    failure_threshold: int = 5      # consecutive failures to trip
    cooldown_seconds: float = 60.0  # OPEN → HALF_OPEN transition delay
```

**State transitions:**
- **CLOSED** (normal): `can_execute()` → `True`; `record_failure()` increments counter; trips to OPEN at threshold
- **OPEN** (tripped): `can_execute()` → `False` until cooldown elapsed, then transitions to HALF_OPEN
- **HALF_OPEN** (probe): `can_execute()` → `True`; `record_success()` → CLOSED; `record_failure()` → OPEN

**Registry:** `CircuitBreakerRegistry` manages per-provider breakers:
- `get_or_create(provider_id)` → lazy-creates a `CircuitBreaker` per provider
- `can_execute(provider_id)` → delegates to per-provider breaker
- `record_success(provider_id)` / `record_failure(provider_id)` → delegates
- Injectable `clock: Callable[[], float]` for deterministic testing (default: `time.monotonic()`)

### 2.3 Rate Limiter (rate_limiter.py)

Per-tenant per-provider rate limiting with three dimensions:

```
RateLimitConfig:
    rpm: int | None = None           # requests per minute
    tpm: int | None = None           # tokens per minute
    max_concurrency: int | None = None  # concurrent requests
```

**Implementation:**
- **RPM:** 60-second sliding window using `collections.deque[float]` of timestamps. `check_rpm()` evicts old entries and checks `len(window) < rpm`.
- **TPM:** 60-second sliding window using `deque[tuple[float, int]]` of (timestamp, tokens). `check_tpm()` evicts old entries and checks `sum(tokens) + new_tokens <= tpm`.
- **Concurrency:** `asyncio.Semaphore` per (tenant, provider) pair. `acquire_concurrency()` returns the semaphore (or `None` if no limit); caller must `acquire()` / `release()`.
- All state updates protected by `asyncio.Lock()`.
- Injectable `clock: Callable[[], float]` for testing.
- If no config exists for a provider, all checks pass (no limit).

### 2.4 Cost Tracker (cost_tracker.py)

Per-tenant per-matter cost accumulation with budget ceilings:

```
PricingRate:
    input_token_cost: float = 0.0   # per-token cost (arbitrary units)
    output_token_cost: float = 0.0

BudgetCeiling:
    max_cost: float
    scope: str = "tenant_matter"    # or "tenant_global"
```

**Key methods:**
- `check_budget(tenant_id, matter_id) → (within_budget, accumulated, ceiling)` — checked before each request
- `record_usage(tenant_id, matter_id, provider_id, usage) → cost_added` — called after each successful request
- `get_accumulated(tenant_id, matter_id) → float` — query accumulated cost

**Usage extraction** (`_extract_tokens()` in cost_tracker.py lines 124-147):
Handles various key names used by different providers:
- Input: `input_tokens` or `prompt_tokens`
- Output: `output_tokens` or `completion_tokens`

**Budget key:** `f"{tenant_id}:{matter_id}"` for tenant_matter scope, or `f"{tenant_id}"` for tenant_global.

### 2.5 ModelProviderGateway (gateway.py)

Composite `BackendAdapter` wrapping `dict[str, BackendAdapter]` sub-adapters:

**Two modes:**
- **Pass-through** (`config.enabled = False`, default): delegates directly to matching sub-adapter, no gateway logic
- **Enabled** (`config.enabled = True`): full pipeline

**Enabled mode flow** (`_submit_run_enabled()`, lines 148-262):
1. Check budget via `CostTracker.check_budget()` — reject if exceeded
2. Build provider order: primary first, then `fallback_chain`
3. For each provider in order:
   a. Check circuit breaker: `CircuitBreakerRegistry.can_execute(provider_id)`
   b. Check rate limits: `RateLimiter.check_rpm()` → `acquire_concurrency()`
   c. Call `adapter.submit_run(req)`
   d. Check result status
   e. On success: record success in circuit breaker, record request in rate limiter, record usage in cost tracker, return
   f. On failure: record failure in circuit breaker, continue to next provider
4. All providers exhausted: return failed `RunHandle` with `tried_providers` list

**Usage data flow:**
```
provider response → Run.metadata["provider_usage"] → _extract_usage_from_run() → CostTracker.record_usage()
```

### 2.6 Reuse Strategy for Phase 100

The agent-core's model layer should **import** (not duplicate) the individual components from model-gateway:
- `CircuitBreakerRegistry` — one per provider
- `RateLimiter` — with per-provider configs
- `CostTracker` — with pricing and budgets

The `ModelProviderGateway` composite adapter pattern is **NOT needed** — agent-core is a single backend, not a composite. But the individual components are reused directly.

**Before each provider call:**
1. `circuit_registry.can_execute(provider_id)` — skip if open
2. `rate_limiter.check_rpm(tenant_id, provider_id)` — skip if rate limited
3. `rate_limiter.acquire_concurrency(tenant_id, provider_id)` — block if at concurrency limit

**After each provider call:**
4. `circuit_registry.record_success(provider_id)` or `record_failure(provider_id)`
5. `rate_limiter.record_request(tenant_id, provider_id, tokens)`
6. `cost_tracker.record_usage(tenant_id, matter_id, provider_id, usage)`

---

## 3. packages/backends/provider_model — Provider Model Layer

### 3.1 File Inventory

**Location:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/`

| File | Lines | Purpose |
|------|-------|---------|
| `adapter.py` | 421 | `ProviderModelBackendAdapter` — BackendAdapter Protocol impl |
| `openai_runner.py` | 498 | `OpenAIClientRunner` — lazy `AsyncOpenAI` import, `FakeOpenAITransport` |
| `anthropic_runner.py` | 356 | `AnthropicRunner` — lazy `AsyncAnthropic` import, `FakeAnthropicTransport` |
| `ollama_runner.py` | 222 | `OllamaRunner` — lazy `urllib.request`, `FakeOllamaTransport` |
| `config.py` | 34 | `ProviderModelBackendConfig` — backend_id, model_name, api_key_ref, api_base_url |
| `error_normalization.py` | 137 | Shared `normalize_provider_error()`, `sanitize_error_message()` |
| `manifest.py` | — | Capability manifest builder |
| `probe.py` | — | Provider capability probe |

**Total: ~1,668 lines across 9 files.**

### 3.2 Provider Interface

Each runner implements the `ProviderModelRunner` Protocol (adapter.py line 33):

```python
class ProviderModelRunner(Protocol):
    async def invoke(self, req: RunRequest) -> ProviderModelExecResult: ...

class StreamingProviderModelRunner(Protocol):
    async def stream(self, req: RunRequest) -> AsyncIterator[ProviderModelStreamDelta]: ...
```

**`ProviderModelExecResult`** (adapter.py line 45):
```python
@dataclass(frozen=True, slots=True)
class ProviderModelExecResult:
    status: AsyncTaskState | str = AsyncTaskState.SUCCEEDED
    result: AgentResult | None = None
    completion_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    raw_payload_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

**`ProviderModelStreamDelta`** (adapter.py line 57):
```python
@dataclass(frozen=True, slots=True)
class ProviderModelStreamDelta:
    content: str
    finish_reason: str | None = None
```

### 3.3 Providers Supported

| Provider | Runner | Transport Protocol | Streaming | Tool Calls |
|----------|--------|-------------------|-----------|------------|
| OpenAI-compatible | `OpenAIClientRunner` | `OpenAITransport.create_chat_completion()` | Via `FakeStreamingProviderModelRunner` (separate) | **No** — `parse_openai_response()` only extracts content |
| Anthropic | `AnthropicRunner` | `AnthropicTransport.create_message()` | **No** — only `invoke()` | **No** |
| Ollama | `OllamaRunner` | `OllamaTransport.create_chat_completion()` | **No** — only `invoke()` | **No** (reuses OpenAI parser) |

### 3.4 Transport Abstraction Pattern

Each runner has an injectable `Transport` Protocol for testing:

```python
class OpenAITransport(Protocol):
    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject: ...

class FakeOpenAITransport:
    def __init__(self, response: JsonObject | None = None, error: Exception | None = None): ...
    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject: ...
```

- **Lazy SDK import** via `importlib.import_module("openai")` inside `invoke()` — package imports cleanly without SDKs installed
- **Fake transports** return pre-configured responses or raise pre-configured errors
- **`FakeStreamingProviderModelRunner`** (openai_runner.py line 478): yields pre-configured `ProviderModelStreamDelta` list

### 3.5 Streaming Implementation

**Current streaming** (adapter.py `stream_events()`, lines 170-231):
- `StreamingProviderModelRunner.stream()` yields `ProviderModelStreamDelta(content, finish_reason)`
- Each delta is mapped to a `RunEvent` with `event_type=RunEventType.MESSAGE_DELTA` and `payload={"message_delta": delta.content}`
- Terminal event: `RunEventType.STATE_CHANGED` with succeeded/failed status
- **No tool call support in streaming** — only content deltas
- **No reasoning/thinking support** — only content

### 3.6 Response Parsing

**`parse_openai_response()`** (openai_runner.py lines 89-175):
- Extracts `choices[0].message.content` → `AgentResult.content`
- Maps `finish_reason`: `"stop"` → SUCCEEDED, `"length"`/`"content_filter"` → FAILED with `provider_model_truncated`
- Extracts `usage` → sanitized to `prompt_tokens`, `completion_tokens`, `total_tokens`
- Model name is always sanitized to `"redacted"` in metadata
- Extracts artifact file refs from `files` / `file_ids` fields

**`parse_anthropic_response()`** (anthropic_runner.py lines 89-172):
- Extracts `content[0].text` (text blocks only) → `AgentResult.content`
- Maps `stop_reason`: `"end_turn"` → SUCCEEDED, `"max_tokens"`/`"content_filter"` → FAILED
- System prompt is a top-level `system` parameter (not in messages array)
- User message is content blocks: `[{"type": "text", "text": content}]`

**`parse_sse_deltas()`** (openai_runner.py lines 209-241):
- Parses `data: ` prefixed SSE lines
- Extracts `choices[0].delta.content` and `choices[0].finish_reason`
- Skips `data: [DONE]` and unparseable JSON

### 3.7 Error Normalization (error_normalization.py)

Shared `normalize_provider_error()` for all three providers:
- **String-based class-name detection** for SDK errors (OpenAI, Anthropic): `RateLimitError`, `AuthenticationError`, `APIConnectionError`, `APIStatusError`
- **HTTP status-code detection** for HTTP errors (Ollama): 429 → rate limit, 401/403 → auth, 5xx → API error
- All errors map to `ErrorCategory.RUNTIME_ERROR`
- Error messages are sanitized: URLs, tokens, file paths, and model names are redacted

### 3.8 What's Missing (Must Add in Phase 100)

| Gap | Description | Impact |
|-----|-------------|--------|
| **Streaming with tool calls** | Current runners only stream content, not tool call deltas | Cannot stream tool rounds — the silence problem persists |
| **Tool call parsing** | `parse_openai_response()` extracts content but not `tool_calls` | Cannot do multi-turn tool orchestration |
| **Unified streaming interface** | No common streaming interface across providers with tool call deltas | Each provider needs its own streaming logic |
| **Reasoning/thinking support** | No `reasoning_content` extraction in streaming mode | Cannot emit `thought.delta` events |
| **Anthropic streaming** | `AnthropicRunner` has no `stream()` method at all | Cannot stream Anthropic responses |

### 3.9 Merge Strategy for Phase 100

**Copy** (not move — provider_model stays for backward compat until Phase 104):
- `openai_runner.py` → `packages/agent-core/src/inkstatute_agent_core/model/openai_runner.py`
- `anthropic_runner.py` → `packages/agent-core/src/inkstatute_agent_core/model/anthropic_runner.py`
- `ollama_runner.py` → `packages/agent-core/src/inkstatute_agent_core/model/ollama_runner.py`
- `error_normalization.py` → `packages/agent-core/src/inkstatute_agent_core/model/error_normalization.py`
- `config.py` → `packages/agent-core/src/inkstatute_agent_core/model/config.py`

**Preserve:** Transport Protocol pattern, lazy SDK import, Fake transports, error normalization

**Add:** Streaming with tool call support, unified `LlmProvider` Protocol, `StreamDelta` union type

**Do NOT copy:** `ProviderModelBackendAdapter` (agent-core has its own adapter in Phase 103), `manifest.py` (agent-core declares its own capabilities)

---

## 4. packages/context-assembler — Context Budget and Trimming

### 4.1 Location

**File:** `packages/platform-runtime/src/platform_runtime/context_assembler.py` (543 lines)

There is **no separate `packages/context-assembler/` package**. The context assembler lives inside `platform-runtime`.

### 4.2 Key Classes

**`ContextAssemblyPolicy`** (line 82):
```python
@dataclass(frozen=True, slots=True)
class ContextAssemblyPolicy:
    budget_tokens: int = 2048
    chars_per_token: int = 4
    max_recent_turn_refs: int = 12
    max_artifact_refs: int = 8
    max_feedback_correction_refs: int = 6
    max_memory_refs: int = 8
    trim_strategy: str = "protected_then_feedback_memory_recent_artifact"
```

**`ContextAssemblyResult`** (line 117):
```python
@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    bundle: ContextBundle
    estimated_tokens: int
    dropped_sections: JsonObject = field(default_factory=dict)
    protected_sections: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)
    privacy: str = "no_raw_payload_or_legal_text_stored"
```

**`ContextAssemblyBudgetError`** (line 17): Raised when protected context alone exceeds the configured budget.

### 4.3 Trim Algorithm (lines 237-276)

1. Calculate `estimated_tokens` for the full bundle
2. **Protected sections** identified first: `current_turn`, `pending_clarification`, `output_policy`
3. If protected sections alone exceed budget → raise `ContextAssemblyBudgetError`
4. While `estimated > budget_tokens`:
   - Iterate trim order: `feedback_correction_refs` → `memory_refs` → `recent_turn_refs` → `artifact_refs` → `active_task_refs`
   - Pop one item from the first non-empty section
   - Record in `dropped_sections[section] += 1`
   - Re-estimate
5. If still over budget after all trimming → raise `ContextAssemblyBudgetError`

### 4.4 Token Estimation (line 475)

```python
def _estimate_tokens(event: Mapping[str, Any], policy: ContextAssemblyPolicy) -> int:
    chars_per_token = max(1, int(policy.chars_per_token))
    return math.ceil(_estimated_value_chars(event) / chars_per_token)
```

- Simple chars-per-token heuristic (default 4 chars = 1 token)
- `_estimated_value_chars()` recursively counts characters in all string values of the event dict
- **Not CJK-aware** — Chinese characters are counted as 0.25 tokens each (same as ASCII)

### 4.5 Skill Body Injection (from Phase 97's body_injector.py)

**File:** `packages/skill-materializer/src/inkstatute_skill_materializer/body_injector.py` (499 lines)

**`SkillBodyInjector`** class:
- `budget_tokens` (default 2048) and `chars_per_token` (default 4)
- **CJK-aware token estimation**: `token_estimate = CJK_chars * 1.0 + non_CJK_chars // chars_per_token`
- Parses SKILL.md into sections by `## ` headers
- **Section priority assignment:**
  - **Protected** (never trimmed): frontmatter + description + first `##` section
  - **High**: sections containing "research-gate" or "ask-user" in header
  - **Low**: sections containing "example", "appendix", or "reference" in header
  - **Medium**: all other sections
- **Trim algorithm:** Remove lowest-priority section with most tokens until under budget
- **Deterministic:** Same input + same budget → same output (no random, no LLM)
- **`read_skill_body(skill_id, index_path, budget_tokens)`** — reads SKILL.md on-demand from source repo via skill-index.json

### 4.6 Phase 100 Adaptation

The agent-core's `AgentContextAssembler` combines both patterns:

| Layer | Source | Budget section |
|-------|--------|----------------|
| System prompt | New (agent-core) | Protected (never trimmed) |
| Skill body injection | `body_injector.py` pattern | Section-priority trim (protected → high → medium → low) |
| Conversation history | `context_assembler.py` pattern | Feedback → memory → recent → artifact → active_task |
| Total budget | New (agent-core) | Enforced across all sections |

**Determinism guarantee:** Same input + same budget → same output. All trim decisions are recorded in `dropped_sections` and `trimmed_skill_sections` for observability.

---

## 5. Phase 88 Unified Events — Event Vocabulary

### 5.1 Location

**Files:**
- `packages/platform-contract/src/platform_contract/unified_events.py` (289 lines) — 15 typed payload dataclasses
- `packages/platform-contract/src/platform_contract/enums.py` (247 lines) — `RunEventType` StrEnum
- `packages/platform-contract/src/platform_contract/events.py` (591 lines) — V2 dataclasses (AgentResult, ErrorInfo, Artifact, etc.)

### 5.2 RunEventType Enum (enums.py lines 100-124)

```python
class RunEventType(StrEnum):
    # V2 (legacy, retained)
    STATE_CHANGED = "state_changed"
    MESSAGE_DELTA = "message_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    ERROR = "error"
    # V3 unified (ACP-isomorphic)
    SESSION_STARTED = "session.started"
    MESSAGE_DELTA_V3 = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    THOUGHT_DELTA = "thought.delta"
    TOOL_CALL_STARTED_V3 = "tool_call.started"
    TOOL_CALL_DELTA = "tool_call.delta"
    TOOL_CALL_COMPLETED_V3 = "tool_call.completed"
    PLAN_UPDATED = "plan.updated"
    PHASE_CHANGED = "phase.changed"
    ELICITATION_REQUESTED = "elicitation.requested"
    PERMISSION_REQUESTED = "permission.requested"
    ARTIFACT_CREATED_V3 = "artifact.created"
    CITATION_RECORDED = "citation.recorded"
    RUN_STATE_CHANGED = "run.state_changed"
```

### 5.3 Payload Dataclasses (unified_events.py)

**Events the agent core must emit:**

| Event type | Payload class | Key fields |
|------------|--------------|------------|
| `message.delta` | `MessageDeltaPayload` | `delta: str`, `message_id: str \| None` |
| `message.completed` | `MessageCompletedPayload` | `content: str`, `message_id: str \| None` |
| `thought.delta` | `ThoughtDeltaPayload` | `delta: str` |
| `tool_call.started` | `ToolCallStartedPayload` | `tool_call_id: str`, `tool_name: str`, `kind: str \| None`, `title: str \| None` |
| `tool_call.delta` | `ToolCallDeltaPayload` | `tool_call_id: str`, `content: str \| None`, `status: str \| None` |
| `tool_call.completed` | `ToolCallCompletedPayload` | `tool_call_id: str`, `status: str`, `content: str \| None`, `file_locations: list[str]`, `raw_input_ref: str \| None`, `raw_output_ref: str \| None`, `error: ErrorInfo \| None` |
| `phase.changed` | `PhaseChangedPayload` | `phase: str`, `previous_phase: str \| None` |
| `run.state_changed` | `RunStateChangedPayload` | `status: str`, `previous_status: str \| None`, `error: ErrorInfo \| None` |
| `error` | `ErrorEventPayload` | `error: ErrorInfo` |

### 5.4 Serialization Helpers (unified_events.py)

```python
def serialize_payload(payload: Any) -> JsonObject:
    """Convert a payload dataclass to a plain dict."""
    return asdict(payload)

def deserialize_payload(event_type: str, data: JsonObject) -> Any:
    """Return the correct payload dataclass for event_type from data."""
    cls = EVENT_TYPE_TO_PAYLOAD_CLASS.get(event_type)
    if cls is None:
        raise KeyError(f"Unknown V3 event type: {event_type!r}")
    return _dict_to_dataclass(cls, data)
```

### 5.5 RunEvent Structure (platform_runtime.protocols)

The `RunEvent` is the carrier for all unified events:

```python
@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: str       # UUID
    run_id: str
    event_type: str     # RunEventType value
    occurred_at: str    # ISO-8601 timestamp
    seq: int            # monotonic sequence number for SSE replay
    payload: JsonObject
    metadata: JsonObject
```

### 5.6 How the Agent Core Should Emit Events

The turn loop is an `async def run_turn() -> AsyncIterator[RunEvent]` generator. Each event:
- `event_type`: one of the `RunEventType` V3 values
- `payload`: the corresponding payload dataclass serialized to dict via `serialize_payload()`
- `seq`: monotonic sequence number (assigned by `EventEmitter`)
- `occurred_at`: ISO-8601 timestamp

An `EventEmitter` helper class wraps the async generator:
- Assigns monotonic `seq` numbers for SSE replay (Phase 91 Last-Event-ID support)
- Tracks `last_event_time` and emits heartbeat `thought.delta` if silence > threshold
- Provides convenience methods: `emit_message_delta()`, `emit_thought_delta()`, `emit_tool_call_started()`, `emit_tool_call_completed()`, `emit_error()`, `emit_state_changed()`

### 5.7 ACP Event Mapping (acp-client/event_mapping.py)

The ACP event bridge already maps ACP `session/update` variants to unified events:

| ACP update type | Unified event type |
|----------------|-------------------|
| `agent_message_chunk` | `message.delta` |
| `agent_message` | `message.completed` |
| `agent_thought_chunk` | `thought.delta` |
| `plan` / `plan_update` | `plan.updated` |
| `elicitation/create` | `elicitation.requested` |
| `session/request_permission` | `permission.requested` |

The agent core should emit the same unified event types directly (it is not an ACP backend — it emits unified events natively).

---

## 6. Fixture Provider Patterns — Testing Without External LLM

### 6.1 Existing Fake Transport Patterns

**`FakeOpenAITransport`** (openai_runner.py lines 65-79):
```python
class FakeOpenAITransport:
    def __init__(self, response: JsonObject | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        if self.error is not None:
            raise self.error
        return self.response or {}
```

**`FakeAnthropicTransport`** (anthropic_runner.py lines 63-79): Same pattern, `create_message()`.

**`FakeOllamaTransport`** (ollama_runner.py lines 59-75): Same pattern, `create_chat_completion()`. Also stores `last_request` for assertion.

**`FakeStreamingProviderModelRunner`** (openai_runner.py lines 478-486):
```python
class FakeStreamingProviderModelRunner:
    def __init__(self, deltas: list[ProviderModelStreamDelta]) -> None:
        self._deltas = list(deltas)

    async def stream(self, req: RunRequest) -> AsyncIterator[ProviderModelStreamDelta]:
        for delta in self._deltas:
            yield delta
```

### 6.2 FakeBackendAdapter (platform-runtime/fakes.py)

**`FakeBackendAdapter`** (fakes.py lines 56-200+):
- In-memory backend with deterministic run lifecycle scripts
- `submit_statuses` parameter controls the status sequence (default: QUEUED → RUNNING → SUCCEEDED)
- `append_message_delta()` method to add streaming events
- `clarification_result` parameter for interrupt testing
- Tracks `submitted_requests`, `cancelled_run_ids`, `submitted_approvals`
- Used extensively in platform-runtime tests

### 6.3 ACP Echo Agent Fixture (acp-client/tests/fixtures/echo_agent.py)

A standalone 168-line Python script that implements a minimal ACP agent over stdio:
- Handles `initialize`, `session/new`, `session/prompt`, `session/cancel`, `session/close`
- `session/prompt` emits `agent_message_chunk` notifications (streaming) then a final `agent_message`
- Capabilities overridable via `ECHO_AGENT_CAPABILITIES` env var
- No external imports beyond stdlib (`sys`, `json`, `uuid`)

**`configurable_echo_agent.py`** — A more advanced fixture that supports configurable responses and elicitation.

### 6.4 Phase 100 Fixture Provider Design

The existing fake transports are too simple for testing the turn loop — they return a single response, not a multi-turn tool orchestration sequence. Phase 100 needs a **`FixtureProvider`** that accepts a script:

```python
script = [
    TurnScript(deltas=[
        ToolCallDelta(tool_call_id="call_1", tool_name="legal_search", arguments='{"query":"合同法"}'),
    ]),
    TurnScript(deltas=[
        ContentDelta(content="根据检索结果..."),
    ]),
]
provider = FixtureProvider(script)
```

**Features needed:**
- Multi-turn tool orchestration without real API calls
- Configurable delays between deltas (for silence threshold testing)
- Tool call streaming events
- Error recovery (script can include error deltas)
- Turn limit enforcement (script with N > max_turns rounds)
- Implements the same `LlmProvider` Protocol as real providers

---

## 7. Turn Loop Design — Async Structure

### 7.1 Rust Original (chat.rs lines 765-1104)

```
for round in 0..MAX_TOOL_ROUNDS:
    1. emit_stream_status("thinking")          // Tauri event (not unified)
    2. Build ChatRequest (stream=false, tools=...)
    3. provider.chat() → blocks                 // NO events during LLM call
    4. If tool_calls → emit_stream_status("tool") // Tauri event
       → run_traced_tool_calls() → blocks       // NO events during tools
       → append_tool_results() → continue
    5. If embedded tool calls → parse → execute → continue
    6. If tool leakage → retry (up to MAX_LEAK_RETRIES=3)
    7. If content non-empty → collect_with_continuations() → emit_text_response() → break
    8. If content empty → stream_response(stream=true, tools=None) → break
```

### 7.2 Python Phase 100 Design

```python
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

### 7.3 Key Differences from Rust

| Aspect | Rust original | Python Phase 100 |
|--------|--------------|-----------------|
| LLM call mode | `stream: false` during tool rounds | **Always `stream: true`** |
| Events during LLM call | None (blocks) | `thought.delta`, `message.delta` streamed |
| Events during tool execution | None (blocks, trace-only) | `tool_call.started`, `tool_call.delta`, `tool_call.completed` |
| Event type | Tauri `app.emit()` (push) | `AsyncIterator[RunEvent]` (pull) |
| Silence enforcement | None | EventEmitter heartbeat (default 5s) |
| Turn limit | `MAX_TOOL_ROUNDS = 10` (hardcoded) | `config.max_turns` (default 10, configurable) |
| Error recovery | `Err(String)` propagates up → turn crash | Tool errors → `tool_call.completed` with error → continue |
| Continuation | `collect_with_continuations()` (up to 4) | Not in Phase 100 scope (deferred) |

### 7.4 Turn Limit Enforcement

When `max_turns` is reached:
1. Emit `error` event with `code="turn_limit_exceeded"`, `message="达到最大轮次上限"`
2. Emit `run.state_changed` with `status="failed"`
3. Stop the generator

Testable with `FixtureProvider` by providing a script with more rounds than `max_turns`.

### 7.5 Error Recovery Patterns

**Tool failure handling:**
1. Catch tool execution exceptions
2. Emit `tool_call.completed` with `status="error"` and `ErrorInfo` in the payload
3. Append the error message as a tool result (`role="tool"`, `content="Error: ..."`) to message history
4. Continue to the next round — the LLM can see the error and decide to retry, use a different tool, or produce a final answer
5. If the LLM keeps failing until `max_turns`, the turn limit handler kicks in

This is more resilient than the Rust original, where `execute_tool()` returns `Err(String)` which propagates up and crashes the turn (chat.rs line 1472: `format!("工具执行失败：{}。请改用其他工具或继续作答。", e)` — the error is converted to a tool result string, but the overall error handling is less structured).

---

## 8. Event Silence Threshold — The Key Metric

### 8.1 The Problem

The "整轮静默" (whole-round silence) problem means that during tool rounds, the client experiences complete event silence — no events for the entire duration of the LLM call + tool execution. This can be 30+ seconds with no feedback.

### 8.2 Threshold Definition

**`silence_threshold_seconds`** (default 5s, configurable via `AgentCoreConfig`):

If no event has been emitted for more than `silence_threshold_seconds`, the `EventEmitter` emits a heartbeat `thought.delta` event with a progress message and `metadata={"heartbeat": true}`.

**Heartbeat messages** (contextual):
- Before LLM call: "正在思考..." / "正在分析您的法律问题..."
- During tool execution: "正在执行工具: {tool_name}..."
- Between rounds: "正在整合工具结果..."

### 8.3 How to Measure Event Timing in Tests

**Test approach:**
1. Use `FixtureProvider` with configurable delays between deltas
2. Record `occurred_at` timestamps for each emitted `RunEvent`
3. Calculate gaps: `gap[i] = occurred_at[i+1] - occurred_at[i]`
4. Assert: `max(gap) <= silence_threshold_seconds + heartbeat_tolerance`

**Test implementation pattern:**
```python
async def test_no_silence_during_tool_rounds():
    provider = FixtureProvider(
        script=[
            TurnScript(deltas=[ToolCallDelta(...)], delay_seconds=8),
            TurnScript(deltas=[ContentDelta("结果...")]),
        ],
        config=AgentCoreConfig(silence_threshold_seconds=5),
    )
    events = []
    async for event in run_turn(..., provider, ...):
        events.append(event)

    # Assert no gap > threshold (accounting for heartbeat)
    timestamps = [parse_iso(e.occurred_at) for e in events]
    gaps = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]
    max_gap = max(gaps)
    assert max_gap <= 5.5  # threshold + small tolerance
```

### 8.4 How to Assert No Silence Periods

**Key assertions:**
1. **No gap > threshold:** `max(gaps) <= silence_threshold_seconds + tolerance`
2. **Heartbeat presence:** During long operations, heartbeat `thought.delta` events with `metadata={"heartbeat": true}` must be present
3. **Event ordering:** `tool_call.started` must come before `tool_call.completed`; `message.delta` events must come before `message.completed`
4. **Seq monotonicity:** `seq` values must be strictly increasing
5. **Event coverage:** During tool rounds, at least one `thought.delta` or `tool_call.*` event must be emitted

---

## 9. packages/agent-core — Does It Exist Yet?

**No.** `packages/agent-core/` does **not** exist. It must be created from scratch in Phase 100.

**Current packages directory** (23 packages):
```
packages/
├── acp-client/
├── acp-event-bridge/
├── backends/
├── channel-core/
├── channels/
├── contract-test-suite/
├── mcp-registry/
├── model-gateway/
├── multi-agent-adapter/
├── operator-config/
├── platform-contract/
├── platform-runtime/
├── platform-sdk-ts/
├── practice-profile/
├── rbac/
├── router-service/
├── skill-index/
├── skill-materializer/
├── skill-registry/
├── solution-loader/
└── ui-core/
```

**No `agent-core/` directory.** Phase 100 creates it.

---

## 10. Existing Agent Patterns — How Current Backends Work

### 10.1 Hermes Backend (packages/backends/hermes/)

**Files:**
- `adapter.py` (423 lines) — `HermesBackendAdapter` implementing BackendAdapter 9-method Protocol
- `config.py` — `HermesBackendConfig`
- `manifest.py` — Capability manifest builder
- `parity.py` — Parity checking
- `probe.py` — Capability probe
- `runs_api.py` — Hermes Runs API client

**Pattern:**
- Injected `HermesOneShotRunner` Protocol (like provider_model's runner pattern)
- `submit_run()` delegates to runner or Runs API
- `stream_events()` yields `RunEvent` objects from stored events
- Reference-first: `raw_payload_ref` in metadata, no sensitive full text

**Note:** This backend is being replaced by the ACP adapter (Phase 89) and will be retired in Phase 104.

### 10.2 ACP Backend Adapter (packages/acp-client/adapter.py — 655 lines)

**`ACPBackendAdapter`** — The production entry point for driving any ACP-speaking agent:
- Implements BackendAdapter 9-method Protocol
- `submit_run()` spawns ACP subprocess (per_session mode), initializes protocol, creates session, sends prompt
- `stream_events()` streams `session/update` notifications, mapped to unified events via `map_acp_update_to_run_event()`
- `ACPBackendConfig`: `backend_id`, `command` tuple, `env`, `process_mode`, `timeout_seconds`, `required_capabilities`, `hermes_home`
- Hermes compatibility matrix: `{"0.19.0": ["streaming", "session_update", "session_cancel", "session_close"], ...}`

### 10.3 How They Interface with the Agent

The platform runtime calls the `BackendAdapter` Protocol (9 methods):
1. `backend_id() → str`
2. `capabilities() → AdapterCapabilitySet`
3. `bootstrap_check() → BootstrapStatus`
4. `submit_run(req: RunRequest) → RunHandle`
5. `get_run(run_id) → Run`
6. `stream_events(run_id) → AsyncIterator[RunEvent]`
7. `cancel_run(run_id) → Run`
8. `submit_approval(run_id, approval) → Run`
9. `collect_artifacts(run_id) → list[ArtifactRecord]`

**The agent core (Phase 100) does NOT implement BackendAdapter yet** — that's Phase 103. Phase 100 implements the internal turn loop, model layer, and context assembler. The BackendAdapter wrapper comes in Phase 103 when the agent core gets dual entry points.

### 10.4 ModelProviderGateway as Composite Adapter

The `ModelProviderGateway` (model-gateway/gateway.py) is a composite `BackendAdapter` that wraps multiple sub-adapters. It implements the same 9-method Protocol but delegates to sub-adapters with rate limiting, circuit breaking, and cost tracking.

For Phase 100, the agent-core's model layer is **not** a composite adapter — it's a set of provider runners wrapped with circuit breaker / rate limiter / cost tracker components. The composite adapter pattern is not needed.

---

## 11. Gate Registration

### 11.1 Current Gate Count

**37 gates** currently registered (confirmed in `test_audit_v2_requirements.py` line 460: `assertEqual(len(gate_names), 37)` and `test_integration.py` line 723: `test_gate_count_is_37`).

### 11.2 Phase 100 Gate Addition

New gate `agent-core` must be registered in `scripts/run_v2_gates.py`:
- Add `agent_core_src` path variable pointing to `packages/agent-core/src`
- Add `Gate("agent-core", ...)` entry with correct PYTHONPATH
- Add `packages/agent-core/src` to compileall paths
- Update `test_audit_v2_requirements.py` gate count assertion: `37 → 38`
- Update `services/gateway/tests/test_integration.py` gate count: `test_gate_count_is_37` → `test_gate_count_is_38`
- `gate-coverage` meta-test auto-discovers `packages/agent-core/src`

---

## 12. Package Structure (Proposed)

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

---

## 13. Dependencies

| Dependency | Provides | Required for |
|------------|----------|-------------|
| Phase 88 (unified events) | `RunEvent`, `unified_events.py` payload dataclasses, `RunEventType` enum | Event emission |
| Phase 97 (skill materialization) | `body_injector.py` pattern, `skill-index.json` | Context budget with skill bodies |
| `packages/model-gateway` | `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` | Model layer resilience |
| `packages/backends/provider_model` | Runner patterns, transport abstractions, error normalization | Model layer merge |
| `packages/platform-runtime` | `context_assembler.py` pattern, `RunRequest`, `RunEvent`, `RunHandle` types | Context assembler, event types |
| `packages/platform-contract` | `unified_events.py`, `enums.py`, `events.py` dataclasses | Event types, payload dataclasses |

---

## 14. Key Constants from Rust Original

| Constant | Value | Location | Python equivalent |
|----------|-------|----------|-------------------|
| `MAX_TOOL_ROUNDS` | 10 | chat_tools.rs:32 | `AgentCoreConfig.max_turns` (default 10) |
| `MAX_LEAK_RETRIES` | 3 | chat.rs:36 | Phase 102 (not 100) |
| `MAX_CONTINUATIONS` | 4 | chat.rs:40 | Deferred (not in Phase 100 scope) |
| `RESPONSE_MAX_TOKENS` | 8192 | chat.rs:42 | `AgentCoreConfig.max_tokens` (default 8192) |
| Temperature | 0.3 | chat.rs:781 | `AgentCoreConfig.temperature` (default 0.3) |

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Streaming with tool calls varies across providers (OpenAI streams tool_call deltas, Anthropic doesn't) | Unified `StreamDelta` type with provider-specific translation; FixtureProvider tests cover all delta types |
| Silence threshold heartbeat may confuse event consumers | Heartbeat `thought.delta` events have `metadata={"heartbeat": true}` for filtering |
| Merging provider_model runners creates code duplication until Phase 104 | Acceptable — provider_model stays for backward compat; Phase 104 retires it |
| Context budget with skill bodies (2K-20K tokens) may exceed typical context windows | Budget is configurable; default is generous (32K tokens); trim report records what was cut |
| FixtureProvider scripts may not cover all real LLM behaviors | Scripts are extensible; real provider tests are deferred to integration testing (not in CI) |
| `dependencies = []` invariant must be preserved for agent-core | Lazy SDK imports (same as provider_model pattern); model-gateway components have no external deps |

---

## 16. Summary of Key Findings

1. **`packages/agent-core/` does not exist** — must be created from scratch
2. **The Rust turn loop (2,000 lines)** uses non-streaming `provider.chat()` during tool rounds, causing the "整轮静默" defect — the Python port must always stream
3. **`packages/model-gateway` (893 lines)** provides reusable `CircuitBreakerRegistry`, `RateLimiter`, `CostTracker` — import directly, do not duplicate
4. **`packages/backends/provider_model` (~1,668 lines)** provides three runner patterns with transport abstraction — copy into agent-core, add streaming + tool call support
5. **Context assembly** combines `context_assembler.py` (conversation history trim) with `body_injector.py` (skill body section-priority trim) — both are deterministic
6. **Phase 88 unified events** provide 15 typed payload dataclasses — the agent core emits `RunEvent` objects with these payloads
7. **Fixture provider** needs to be more sophisticated than existing `Fake*Transport` patterns — must support multi-turn scripts with configurable delays
8. **Gate count goes from 37 to 38** — new `agent-core` gate registered in `scripts/run_v2_gates.py`
9. **The silence threshold (default 5s)** is the key metric — EventEmitter enforces it via heartbeat `thought.delta` events
10. **Turn limit (default 10)** matches Rust's `MAX_TOOL_ROUNDS` — configurable, emits `error` + `run.state_changed` when exceeded
