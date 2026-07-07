# Stack Research: M3 Platform Extensions

**Domain:** M3 Platform Extensions — adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant
**Researched:** 2026-07-05
**Confidence:** HIGH

## Architectural Constraints (Carried from v1.6)

Every existing package and service declares `dependencies = []` in `pyproject.toml`. No package uses FastAPI, aiohttp, uvicorn, SQLAlchemy, or any third-party runtime library at import time. Services are pure-Python handler functions returning `(status_code, body)` tuples (see `services/conversation-read-view/src/conversation_read_view/api.py:handle_get`). Channel/backend adapters wrap "sanitized primitives" with `network_io: False`. The AGENTS rule is explicit: *"Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it."*

**M3 strategy:** New runtime dependencies are added ONLY as optional extras (`[project.optional-dependencies]`), imported lazily inside method bodies, so packages remain importable with `dependencies = []` in CI and contract tests. This mirrors the existing `provider_model` adapter pattern (lazy `AsyncOpenAI` import) and the `hindsight_memory.py` pattern (lazy `hindsight_client` import). The contract freeze (`packages/platform-contract/`), frozen Protocols (`BackendAdapter` 9 methods, `ChannelAdapter` 6 methods), and feature-flag-default-OFF strategy are preserved.

---

## New Stack Additions

### 1. Streaming Events (Adapter Streaming)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Python stdlib `asyncio` + `async generators` | 3.11+ (CI floor) | The `BackendAdapter` Protocol already declares `async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]` (line 233 of `protocols.py`). The `RunRuntime` Protocol already declares `async def stream(self, run_id: str) -> AsyncIterator[RunEvent]` (line 269). `RunEvent` is a frozen dataclass with `event_type: str` using `RunEventType` enum (9 event types: `state_changed`, `step_started`, `step_completed`, `message_delta`, `tool_call_started`, `tool_call_completed`, `approval_requested`, `artifact_created`, `error`). No new streaming library is needed — Python 3.11 async generators are the native streaming primitive. | Adapters implement `stream_events()` as `async def` generators that `yield RunEvent(...)` instances. The existing `encode_sse_event()` in `packages/channels/web_sse/src/inkstatute_channels_web_sse/sse.py` already encodes `RunEvent` into SSE frames (`id:`, `event:`, `data:` lines). The `web_sse` ChannelAdapter already declares `supports_streaming=True` in `ChannelCapabilitySet`. M3 promotes `stream_event_support` from `False` to `True` in `AdapterCapabilitySet` for productionized adapters. | Do NOT add `sse-starlette` v3.4.5 — it requires Starlette/FastAPI as a dependency, breaking the `dependencies = []` pattern. The existing `encode_sse_event()` is a pure-stdlib SSE encoder that is sufficient. Do NOT add `websockets` library — WebSocket is not needed; SSE (unidirectional server→client) is the correct protocol for streaming run events to a thin web client. |
| `openai` Python SDK (streaming) | 2.44.0 (Jun 2026) | `AsyncOpenAI` provides `client.responses.create(stream=True)` and `client.chat.completions.create(stream=True)` returning async iterators of SSE events. `async for event in stream` maps directly to `yield RunEvent(event_type=RunEventType.MESSAGE_DELTA, ...)`. The SDK handles SSE parsing, connection management, and backpressure internally. | Lazy import inside `provider_model` adapter's `stream_events()` method. Map `response.output_text.delta` → `RunEvent(MESSAGE_DELTA)`, `response.completed` → `RunEvent(STATE_CHANGED)`. Optional dependency: `[project.optional-dependencies] openai = ["openai>=2.0"]`. | Do NOT add a separate SSE parsing library — the `openai` SDK parses SSE internally. |
| `anthropic` Python SDK (streaming) | 0.116.0 (Jul 2026) | `AsyncAnthropic` provides `client.messages.stream()` returning an async context manager with `async for event in stream` iteration. Events: `message_start`, `content_block_start`, `content_block_delta` (text deltas), `message_stop`. Maps to `RunEvent(MESSAGE_DELTA)` and `RunEvent(STATE_CHANGED)`. Python 3.9+, httpx-backed, MIT licensed. | Lazy import inside `provider_model` adapter's `stream_events()` when `provider == "anthropic"`. Optional dependency: `[project.optional-dependencies] anthropic = ["anthropic>=0.100"]`. | Do NOT use `anthropic` SDK's MCP helper functions for the MCP Connector Registry — those are Anthropic-specific tool-format converters, not a general MCP client. Use the official `mcp` SDK instead. |
| `codex` CLI (streaming) | latest (2026) | `codex exec --json` already emits JSONL events to stdout line-by-line. The existing Codex adapter reads stdout via `subprocess`. For streaming, read stdout line-by-line as an async generator: `async for line in process.stdout: yield _map_codex_event(json.loads(line))`. Codex JSONL events (`thread.started`, `turn.completed`, `item.*`, `token.*`) map to `RunEvent` types. | Extend `CodexBackendAdapter.stream_events()` to read `subprocess` stdout incrementally using `asyncio.create_subprocess_exec` + `process.stdout.readline()`. No new Python dependency — `subprocess` + `json` + `asyncio` are stdlib. | Do NOT add a Codex Python SDK — `codex exec --json` subprocess is the documented non-interactive surface. |

### 2. MCP (Model Context Protocol) Connector Registry

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| `mcp` Python SDK (v1.x stable) | 1.28.1 (Jun 2026) | The official MCP Python SDK from `modelcontextprotocol/python-sdk` (23.5K stars, MIT, Python 3.10+). v1.x is the stable production line; v2 is in beta targeting 2026-07-28 spec release. Provides `ClientSession` for connecting to MCP servers (stdio, SSE, WebSocket transports), `Server` class for exposing tools/resources/prompts, and typed protocol messages (`ListToolsResult`, `CallToolResult`, `ListResourcesResult`). The SDK handles JSON-RPC framing, capability negotiation, and transport lifecycle. | New `packages/mcp-connector-registry/` package. The registry stores `McpServerDescriptor` records (already defined in `events.py:116` with `server_id`, `name`, `transport`, `capability_refs`, `secret_refs`). The registry itself is a pure-Python dict-based store with `handle_get/handle_post -> (status_code, body)` API (same pattern as `skill-registry`). The `mcp` SDK is an optional runtime dependency for live MCP server connections: `[project.optional-dependencies] runtime = ["mcp>=1.27,<2"]`. Pin `<2` to avoid v2 breaking changes. The registry package itself stays `dependencies = []` — it stores descriptors and validates configs without importing `mcp`. | Do NOT use `mcp` v2.0.0b1 — it's a pre-release with breaking API changes. Pin `mcp>=1.27,<2`. Do NOT add the OpenAI Agents SDK's MCP integration (`openai-agents`) — that's a multi-agent framework, not an MCP client. Do NOT build a custom JSON-RPC implementation — the `mcp` SDK handles protocol framing. |
| `McpServerDescriptor` (existing contract) | internal | Already defined as a frozen dataclass in `packages/platform-contract/src/platform_contract/events.py:116`. Already referenced in `SolutionPackageManifest.mcp_servers: list[McpServerDescriptor]` (line 416). The contract already supports MCP server registration at the solution-manifest level. | The MCP Connector Registry reads `mcp_servers` from `solutions/*/manifest.json` (same pattern as Skill Registry reading `skills` arrays). No new contract schema needed. | Do NOT add a new MCP contract event — `McpServerDescriptor` is already frozen in the contract. |

### 3. Model Provider Gateway (Routing, Rate-Limit, Fallback)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Pure-Python token-bucket rate limiter (stdlib) | 3.11+ | Rate limiting for the Model Provider Gateway is a token-bucket or sliding-window algorithm over `asyncio` time. Python stdlib `asyncio.monotonic()` + `collections.deque` + `asyncio.Lock` is sufficient for per-provider, per-tenant rate limiting. The existing `wecom_service/active_task_router.py` proves the pure-Python pattern: `re.compile` patterns, `StrEnum` classification, `dataclass` decisions, no external deps. | New `services/model-provider-gateway/` (or `packages/model-provider-gateway/`). Gateway wraps multiple provider clients (`AsyncOpenAI`, `AsyncAnthropic`, `AsyncClient` for Ollama) behind a unified `submit_completion()` method. Rate limiter is a `dataclass` with `async def acquire(self, key: str) -> None`. Fallback is a list of providers with priority ordering; on `ErrorCategory.RUNTIME_ERROR`, try next provider. `handle_post(path, body) -> (status_code, dict)` API. `dependencies = []`. | Do NOT add `aiolimiter` v3.1.0 — it's a good async rate limiter but adds a dependency. The token-bucket algorithm is ~30 lines of stdlib code. Do NOT add LiteLLM v1.90.2 as a gateway — it's a 100+ provider proxy server with caching, adds massive dependency surface. The gateway needs routing + rate-limit + fallback, not 100 provider adapters. |
| `RouteDecision` (existing contract) | internal | Already defined in `events.py:207` with `primary_skill`, `confidence`, `mode`, `gates_before`, `gates_after`, `matched_rule`, `reason`. The Router Service already produces `RouteDecision` records. The Model Provider Gateway extends routing to model selection: which provider/model to use for a given route. | Gateway consumes `RouteDecision` from the Router Service and maps `primary_skill` → provider/model configuration. No new contract event needed for basic gateway routing. | Do NOT create a new `ModelRouteDecision` contract event unless the frozen contract is extended (which requires a contract evolution phase). Use `RouteDecision.metadata` for model routing details. |
| `openai` + `anthropic` + `ollama` SDKs (multi-provider) | 2.44.0 / 0.116.0 / 0.6.2 | The gateway dispatches to multiple providers. `AsyncOpenAI` (OpenAI-compatible: OpenAI, Azure, Ollama via `base_url`), `AsyncAnthropic` (Anthropic Claude direct), `ollama.AsyncClient` (Ollama native API). All three are async-first, httpx-backed, Python 3.8+. | Lazy imports inside gateway provider clients. `[project.optional-dependencies] openai = ["openai>=2.0"]`, `anthropic = ["anthropic>=0.100"]`, `ollama = ["ollama>=0.5"]`. The gateway package stays `dependencies = []`. | Do NOT use LiteLLM as a unified provider abstraction — see above. Do NOT use `openai` SDK for Anthropic (via proxy) — direct `anthropic` SDK is cleaner for fallback proof. |

### 4. Multi-Agent Runtime Adapter

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Pure-Python async orchestrator (stdlib `asyncio`) | 3.11+ | Multi-agent orchestration is deterministic routing code wrapping LLM calls. The existing `BackendAdapter` Protocol (9 methods, frozen) is the agent interface. A multi-agent runtime is an orchestrator that calls multiple `BackendAdapter.submit_run()` instances and merges results. Python 3.11 `asyncio.gather()` for parallel agents, `asyncio.create_task()` for background agents, `asyncio.Queue` for inter-agent message passing. No framework needed — the pattern is: orchestrator class holds `dict[agent_id, BackendAdapter]`, routes `RunRequest` to sub-agents, collects `RunEvent` streams, emits merged `RunEvent` stream. | New `packages/backends/multi_agent/` package. `MultiAgentBackendAdapter` implements `BackendAdapter` Protocol (9 methods). `AdapterCapabilitySet` with `parallel_task_support=True`. Orchestrator config: `MultiAgentConfig(agents: dict[str, AgentConfig], routing_strategy: str)`. Sub-agents are existing `BackendAdapter` implementations (Hermes, Codex, provider_model). `dependencies = []`. | Do NOT add LangChain (`langchain-adk` v0.3.14), LangGraph, CrewAI, AutoGen, or LlamaIndex `AgentWorkflow` — these are heavy multi-agent frameworks with large dependency trees that break the `dependencies = []` pattern. The "7 building blocks" pattern (direct SDK calls + deterministic routing + circuit breaker) is the correct approach. Do NOT add `justpipe` v0.12.0 — zero-dependency but adds an unproven abstraction; stdlib `asyncio` is sufficient. Do NOT add A2A protocol (`a2a-sdk`) — agent-to-agent protocol is overkill for a single-platform multi-agent runtime. |
| `BackendAdapter` Protocol (existing, frozen) | internal | The 9-method Protocol (`backend_id`, `capabilities`, `bootstrap_check`, `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts`) is the agent interface. Multi-agent runtime composes multiple `BackendAdapter` instances. | `MultiAgentBackendAdapter` wraps `dict[agent_id, BackendAdapter]` and delegates Protocol methods to sub-agents. `submit_run()` routes to the appropriate sub-agent based on `RunRequest.metadata["target_agent"]` or orchestrator logic. `stream_events()` merges `AsyncIterator[RunEvent]` from multiple sub-agents with sequence number normalization. | Do NOT modify the `BackendAdapter` Protocol — it's frozen. The multi-agent adapter IS a `BackendAdapter`, preserving contract compatibility. |

### 5. RBAC (Role-Based Access Control)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| `pycasbin` (Casbin Python) | 2.8.0 (Feb 2026) | The mature Python Casbin library (1.7K stars, Apache-2.0). Supports RBAC, RBAC with domains/tenants (multi-tenant isolation), ABAC. Has `AsyncEnforcer` for async/await code. Model files (`.conf`) define RBAC policy structure; policy files (`.csv`) or DB adapters store rules. The RBAC-with-domains model maps directly to multi-tenant isolation: `(sub, domain, obj, act)` tuples where `domain` = `tenant_id`. | New `packages/rbac/` package. `CasbinRbacGuard` wraps `AsyncEnforcer` with model file `rbac_model.conf` (RBAC with domains). The guard exposes `async def enforce(user: str, tenant_id: str, resource: str, action: str) -> bool`. Admin Console API and Web chat endpoints call `guard.enforce()` before handling requests. Optional dependency: `[project.optional-dependencies] runtime = ["pycasbin>=2.8"]`. The package stays `dependencies = []` — model/policy files are static config, enforcement logic is pure-Python dict lookups in tests. | Do NOT add `casbin-fastapi-decorator` v1.2.1 — it requires FastAPI as a dependency. The existing services use pure-function handlers, not FastAPI. Do NOT add `fastapi-permission` or `fastapi-authz` — same FastAPI dependency issue. Do NOT build a custom RBAC from scratch — Casbin's domain/tenant model is well-tested and maps exactly to the multi-tenant requirement. |
| `Tenant` + `Workspace` + `BotInstance` (existing contract) | internal | Already defined as frozen dataclasses in `events.py`: `Tenant` (line 391, `tenant_id`, `name`, `status`), `Workspace` (line 400, `workspace_id`, `tenant_id`, `name`), `BotInstance` (line 428, `bot_instance_id`, `tenant_id`, `workspace_id`). `ChannelMessage`, `ChannelDelivery`, `Run`, `Session`, `MemoryRecord` all carry `tenant_id` + `workspace_id` fields. The contract already supports multi-tenant data partitioning. | RBAC enforcement uses `tenant_id` as the Casbin domain. Role assignments are `(user_id, role, tenant_id)` tuples. Resources are API paths or contract event types. | Do NOT add new contract events for RBAC — use `metadata` fields on existing events for audit trails. |

### 6. Multi-Tenant Isolation

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Application-level tenant_id partitioning (existing pattern) | internal | The contract already carries `tenant_id` + `workspace_id` on all tenant-scoped events (`ChannelMessage`, `ChannelDelivery`, `Run`, `Session`, `MemoryRecord`, `BotInstance`). The existing `HindsightMemory._bank_id()` method (line 107 of `hindsight_memory.py`) already implements tenant isolation: `f"ink-{tenant_id}:{workspace_id}:{user_id}"` maps to a Hindsight `bank_id`. This is application-level isolation — each tenant gets a separate memory bank. | M3 extends this pattern: (1) Contract log files are partitioned by `tenant_id` in the file path (e.g., `contract_logs/{tenant_id}/{workspace_id}/`). (2) The `ContractLogReadModel` filters by `tenant_id` in dict comprehensions. (3) RBAC enforcement (Casbin domain = `tenant_id`) prevents cross-tenant access. (4) Hindsight bank isolation is already proven. No new library. | Do NOT add database-level isolation (PostgreSQL RLS, schema-per-tenant) — the platform uses JSONL contract logs, not a relational database (PRD §1.2: "不建独立 Conversation API + 数据库"). Do NOT add SQLite per-tenant databases — the existing `sqlite_memory.py` is a single-file fallback, not a multi-tenant store. Do NOT add `asyncpg` or `aiosqlite` for tenant isolation — application-level `tenant_id` filtering on in-memory dicts and JSONL files is sufficient at lawyer-trial scale. |
| `pycasbin` RBAC with domains | 2.8.0 | Casbin's RBAC-with-domains model provides policy-level tenant isolation: users can only access resources within their assigned domain (`tenant_id`). This is the access-control layer of multi-tenant isolation, complementing the data-level partitioning. | Same `packages/rbac/` package. Model file uses `g3 = _, _, _` (sub, domain, obj) policy definition. | See RBAC section above for what NOT to add. |

### 7. Web UI (Admin Console + Lawyer Chat)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Preact | 10.x (stable) | 3KB gzipped, React-compatible API, built-in Signals for fine-grained reactivity. The existing `apps/web_chat/src/render.ts` renderer is explicitly "DOM-free" and produces `RenderRecord` objects that "the host can map into React, Preact, lit-html, raw DOM, or a server-side template" (line 4-7). Preact is the lightest framework that preserves the `RenderRecord` → DOM mapping pattern. For the lawyer chat, Preact consumes SSE-streamed `RunEvent` records (via the existing `encode_sse_event()` encoder) and maps `RenderRecord` objects to Preact components. | `apps/web_chat/` extends with Preact host components that consume `RenderRecord[]` from `render.ts`. The renderer stays DOM-free; Preact is the host layer. `apps/admin_console/` (new) uses Preact + `@preact/signals` for state management. Both apps consume the pure-Python API handlers via HTTP (deployment layer wraps `handle_get/handle_post` in an ASGI server). | Do NOT add React 19 (40KB+) — the existing renderer comment explicitly lists Preact as a valid host. React's bundle size and VDOM overhead are unnecessary for a thin chat + admin dashboard. Do NOT add Next.js or Remix — server-side rendering frameworks add build complexity and a Node.js server dependency. The deployment layer is Python ASGI, not Node.js. |
| `@preact/signals` | 2.x | Fine-grained reactivity for Preact without VDOM diffing. Admin console dashboard widgets (session list, task status, gate health) update independently when new data arrives via SSE polling. | State management in `apps/admin_console/`. Signals for `sessions`, `tasks`, `feedback`, `gates`, `health` views. Each signal updates from SSE/poll responses without re-rendering the entire dashboard. | Do NOT add Redux or Zustand — `@preact/signals` is lighter and built for Preact. Do NOT add TanStack Query — the admin console polls simple JSON endpoints, not complex GraphQL/REST queries. |
| `lit-html` / Lit | 3.x | Alternative to Preact for Web Components. The existing renderer comment lists `lit-html` as a valid host. Lit produces framework-agnostic Custom Elements that can be embedded in any page. Useful if the lawyer chat needs to be embedded as a widget in third-party legal portals. | Optional alternative for embeddable widget scenarios. If the chat is a standalone page, Preact is simpler. If it must be embedded as a `<inkstatute-chat>` Custom Element, Lit is better. | Do NOT use both Preact AND Lit — pick one per app. Preact for admin console (dashboard), Lit only if lawyer chat needs Web Component embedding. |
| TypeScript (existing) | 5.x | The existing `apps/web_chat/` and `packages/platform-sdk-ts/` are already TypeScript. The `RenderRecord` interface and `ChatEventInput` interface are defined in `render.ts`. | New `apps/admin_console/` is TypeScript. Extends `@inkstatute/platform-sdk-ts` for API client types. | Do NOT add a separate TypeScript build system — the existing apps use `tsc` directly with no bundler framework. |
| Tailwind CSS | 4.x | Utility-first CSS for rapid admin console layout. The realworld framework comparison shows Tailwind v4 is used across all frameworks. Zero runtime CSS-in-JS overhead. | `apps/admin_console/` styles. Tailwind config scans `.tsx` files for class names. | Do NOT add CSS-in-JS (styled-components, emotion) — Tailwind is build-time, zero runtime cost. Do NOT add a component library (MUI, Ant Design) — they add 100KB+ and impose design system constraints. Simple Tailwind utility classes are sufficient for an internal admin console. |

### 8. Anthropic SDK (Multi-Provider Support)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| `anthropic` Python SDK | 0.116.0 (Jul 2026) | Official Anthropic Python library, MIT, Python 3.9+, httpx-backed. `AsyncAnthropic` client with `client.messages.create()` and `client.messages.stream()`. Supports Claude Opus 4, Sonnet 4, Haiku models. Streaming via `async for event in stream` with `content_block_delta` events for text deltas. | `packages/backends/provider_model/` adapter: when `config.provider == "anthropic"`, lazy import `from anthropic import AsyncAnthropic`. Map `messages.create()` → `AgentResult`, `messages.stream()` → `AsyncIterator[RunEvent]`. Optional dependency: `[project.optional-dependencies] anthropic = ["anthropic>=0.100"]`. | Do NOT use `anthropic` SDK for non-Anthropic providers — use `openai` SDK with `base_url` for OpenAI-compatible, `ollama` for Ollama native. Do NOT use Anthropic's MCP helper functions — use the official `mcp` SDK for MCP connector registry. |

### 9. Ollama Client (Multi-Provider Support)

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| `ollama` Python library | 0.6.2 (Apr 2026) | Official Ollama Python client, MIT, Python 3.8+. `AsyncClient` with `AsyncClient().chat(model=..., messages=..., stream=True)` returning async iterator. Also supports `AsyncClient().embed()` for embeddings. Ollama runs locally (no API key needed) — useful for on-premise legal deployments with data residency requirements. | `packages/backends/provider_model/` adapter: when `config.provider == "ollama"`, lazy import `from ollama import AsyncClient`. Map `AsyncClient().chat()` → `AgentResult`, `AsyncClient().chat(stream=True)` → `AsyncIterator[RunEvent]`. Optional dependency: `[project.optional-dependencies] ollama = ["ollama>=0.5"]`. Alternative: use `AsyncOpenAI(base_url="http://localhost:11434/v1")` for OpenAI-compatible Ollama access (no `ollama` package needed). | Do NOT use `ollama` library if already using `AsyncOpenAI` with `base_url` — the OpenAI-compatible endpoint covers basic chat. Use `ollama` library only for Ollama-native features (embeddings, model management, multimodal). |

### 10. Hindsight Session Memory Integration

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| `hindsight-client` | 0.7.2 (latest PyPI) | Already integrated in `packages/platform-runtime/src/platform_runtime/hindsight_memory.py`. The `HindsightMemory` class wraps `hindsight_client.Hindsight` with `aretain()`, `arecall()`, `areflect()` async methods. Tenant isolation via `_bank_id(tenant_id, workspace_id, user_id)` → `ink-{tenant}:{workspace}:{user}` bank ID. Uses BGE-M3 embeddings and BGE-Reranker-V2-M3 (configured server-side in Hindsight). | M3 extends Hindsight from long-term memory to session memory: (1) `AdapterCapabilitySet.session_memory_support` promoted from `False` to `True` for productionized adapters. (2) Adapters call `HindsightMemory.arecall()` before `submit_run()` to inject session context into the prompt. (3) Adapters call `HindsightMemory.aretain()` after `submit_run()` to persist conversation turns. (4) `RunRequest.session_id` (already in Protocol, line 114) links runs to Hindsight bank sessions. No new library — `hindsight-client` is already a lazy import in `platform-runtime`. | Do NOT add a second memory backend for session memory — Hindsight already supports session-scoped banks via `bank_id` naming. Do NOT add `mem0` or `letta` (MemGPT) — Hindsight is the validated memory backend with proven tenant isolation. Do NOT add a vector database (Chroma, Qdrant, Weaviate) — Hindsight handles embeddings and retrieval internally. |
| `MemoryRecord` + `MemoryCandidate` (existing contract) | internal | Already defined as frozen dataclasses in `events.py`: `MemoryRecord` (line 459, with `scope: MemoryScope`, `sensitivity: MemorySensitivity`, `status: MemoryStatus`, `session_id`, `ttl_expires_at`, `deleted_at`), `MemoryCandidate` (line 483, with `requires_human_review: bool = True`). `MemoryScope` enum includes `SESSION`, `USER`, `WORKSPACE`, `TENANT` (line 171). The contract already supports session-scoped memory. | Session memory uses `MemoryScope.SESSION` with `session_id` linking. Adapters produce `MemoryRecord` events with `scope=SESSION` after each turn. `MemoryCandidate` records with `requires_human_review=True` preserve the legal safety gate. | Do NOT add new memory contract events — `MemoryRecord` and `MemoryCandidate` are frozen. Use `metadata` for adapter-specific memory details. |

### 11. Skill Registry Write Operations

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Pure-Python JSON file writer (stdlib) | 3.11+ | The existing `packages/skill-registry/` reads `solutions/*/manifest.json` `skills` arrays via stdlib `json`. Write operations are the inverse: validate a `NeutralSkillDescriptor` (already in contract, line 105), append to the `skills` array in `manifest.json`, write back via `json.dump()`. The legal safety gate is preserved: `SkillCandidate.requires_human_review = True` (line 79) — write operations only create `candidate` status entries, never auto-modify legal conclusions. | Extend `packages/skill-registry/` with `handle_post(path, body) -> (status_code, dict)` for `POST /skills` (create candidate) and `POST /skills/{name}/approve` (human-approved promotion). Write operations are guarded by RBAC (`pycasbin` — only `skill_admin` role can approve). `dependencies = []`. | Do NOT add a database for skill storage — `manifest.json` files are the source of truth (same as M2 read pattern). Do NOT add `jsonschema` library for validation — the existing `validate_agent_backend_manifest()` pattern uses manual dict validation. Do NOT auto-promote skill candidates — the human review gate is a safety requirement. |

### 12. Model-Based and Hybrid Routing with Confidence Scoring

| Library | Version | Why It Fits | Integration Point | What NOT to Add |
|---------|---------|-------------|-------------------|-----------------|
| Pure-Python confidence scoring (stdlib) | 3.11+ | The existing `RouteDecision` contract (line 207) already has `confidence: float` and `mode: RouteMode`. The existing Router Service (`packages/router-service/`) already produces `RouteDecision` with RULE and SKILL modes. Model-based routing adds a third mode: use an LLM to classify the turn and produce a confidence score. Hybrid routing combines rule-based + model-based: if rule confidence > threshold, use rule; otherwise, fall back to model-based classification. | Extend `packages/router-service/` with `MODEL` mode (add to `RouteMode` enum — requires contract evolution or use `metadata["mode"] = "model"`). The model-based router calls a lightweight LLM (via `AsyncOpenAI` or `AsyncAnthropic`) with a classification prompt. Confidence score = model's logprob or explicit confidence in structured output. Hybrid: `if rule_confidence > 0.8: use_rule() else: use_model()`. `dependencies = []` with optional `[project.optional-dependencies] openai = ["openai>=2.0"]`. | Do NOT add a dedicated ML classification library (scikit-learn, transformers) — the LLM IS the classifier. Do NOT add `sentence-transformers` for embedding-based routing — Hindsight already provides BGE-M3 embeddings if needed. Do NOT add `RouteMode.MODEL` to the frozen enum without a contract evolution phase — use `metadata` for new modes until the contract is formally extended. |

---

## Existing Stack Leveraged

| Component | Location | How Reused in M3 |
|-----------|----------|------------------|
| `BackendAdapter` Protocol (9 methods, frozen) | `packages/platform-runtime/src/platform_runtime/protocols.py:222` | Multi-agent runtime implements this Protocol; all adapters (Codex, provider_model, multi_agent) conform to it. No modification. |
| `ChannelAdapter` Protocol (6 methods, frozen) | `packages/platform-runtime/src/platform_runprotocols.py:208` | Web chat SSE channel extends the existing `web_sse` adapter. No modification. |
| `RunEvent` + `RunEventType` (9 event types) | `packages/platform-contract/src/platform_contract/events.py:290` + `enums.py:100` | Streaming events use these frozen types. Adapters yield `RunEvent` instances. No modification. |
| `encode_sse_event()` | `packages/channels/web_sse/src/inkstatute_channels_web_sse/sse.py:15` | SSE encoding for streaming events to web clients. Already handles `RunEvent` → SSE frame mapping with forbidden-payload-key filtering. No modification. |
| `RenderRecord` + `render.ts` | `apps/web_chat/src/render.ts:14` | Lawyer chat UI consumes `RenderRecord[]` from the existing DOM-free renderer. Preact host maps records to DOM. No modification to renderer. |
| `HindsightMemory` | `packages/platform-runtime/src/platform_runtime/hindsight_memory.py:32` | Session memory integration. Already has `aretain()`, `arecall()`, `areflect()` with tenant isolation. Extended to session scope. |
| `ContractLogReadModel` | `services/conversation-read-view/src/conversation_read_view/read_model.py` | Admin console API reuses this for sessions/tasks/feedback views. Extended with tenant_id filtering for multi-tenant isolation. |
| `RuntimeFeatureFlags` | `packages/platform-runtime/src/platform_runtime/feature_flags.py:13` | Extended with new flags: `mcp_registry_enabled`, `model_gateway_enabled`, `multi_agent_enabled`, `skill_write_enabled`, `web_ui_enabled`, `rbac_enabled`. All default `False`. |
| `RouteDecision` contract event | `packages/platform-contract/src/platform_contract/events.py:207` | Model gateway and hybrid routing produce/consume this. `confidence` field used for hybrid routing threshold. |
| `McpServerDescriptor` contract | `packages/platform-contract/src/platform_contract/events.py:116` | MCP Connector Registry stores these. Already in `SolutionPackageManifest.mcp_servers`. |
| `NeutralSkillDescriptor` contract | `packages/platform-contract/src/platform_contract/events.py:105` | Skill Registry write operations create these. |
| `MemoryRecord` + `MemoryCandidate` + `MemoryScope` | `packages/platform-contract/src/platform_contract/events.py:459,483` + `enums.py:171` | Session memory uses `MemoryScope.SESSION`. Write operations create `MemoryCandidate` with `requires_human_review=True`. |
| `Tenant` + `Workspace` + `BotInstance` | `packages/platform-contract/src/platform_contract/events.py:391,400,428` | Multi-tenant isolation. All tenant-scoped events carry `tenant_id` + `workspace_id`. |
| `AgentBackendMode` enum | `packages/platform-contract/src/platform_contract/agent_adapter.py:12` | Already has `HERMES`, `CODEX`, `PROVIDER_MODEL`. Multi-agent mode uses `metadata["mode"] = "multi_agent"` (or contract evolution adds `MULTI_AGENT`). |
| `AdapterCapabilitySet` | `packages/platform-contract/src/platform_contract/agent_adapter.py:18` | Already has `stream_event_support`, `artifact_return_support`, `session_memory_support`, `parallel_task_support` fields. M3 promotes these from `False` to `True` for productionized adapters. No new fields needed. |
| Pure-function handler pattern | `services/conversation-read-view/src/conversation_read_view/api.py` | All new services (MCP registry, model gateway, admin console write API) follow `handle_get/handle_post -> (status_code, body)` pattern. `dependencies = []`. |
| `event_stream_replay` | `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` | Contract test fixtures for all new features. Validates event ordering, schema compliance, tenant isolation. |
| `@inkstatute/platform-sdk-ts` | `packages/platform-sdk-ts/` | TypeScript SDK for web apps. Admin console and lawyer chat import API types from here. |

---

## Integration Notes

### Contract Freeze Preservation

1. **No frozen Protocol modifications:** `BackendAdapter` (9 methods), `ChannelAdapter` (6 methods), `SolutionLoader`, `RunRuntime` remain unchanged. Multi-agent runtime IS a `BackendAdapter`; MCP registry uses existing `McpServerDescriptor`; model gateway wraps existing `BackendAdapter` instances.

2. **No frozen enum modifications without evolution:** `RouteMode` has `MATCHED`, `SIMPLE_QA`, `SKIPPED`, `ZERO_MATCH`. Model-based routing uses `metadata["routing_mode"] = "model"` until a formal contract evolution phase adds `MODEL` to the enum. `AgentBackendMode` similarly uses `metadata` for `MULTI_AGENT` mode.

3. **`AdapterCapabilitySet` fields already exist:** `stream_event_support`, `artifact_return_support`, `session_memory_support`, `parallel_task_support`, `cancel_support`, `approval_support` are all defined (lines 28-33). M3 sets these to `True` for productionized adapters — this is a value change, not a schema change.

### Feature Flag Strategy

New `RuntimeFeatureFlags` fields (all default `False`):
```python
mcp_registry_enabled: bool = False
model_gateway_enabled: bool = False
multi_agent_enabled: bool = False
skill_write_enabled: bool = False
hybrid_routing_enabled: bool = False
web_ui_enabled: bool = False
rbac_enabled: bool = False
multi_tenant_isolation_enabled: bool = False
```

Each new runtime lane is gated by `flags.require_enabled("mcp_registry_enabled")` etc. Live promotion remains a human gate.

### Dependency Strategy

All new Python packages maintain `dependencies = []` in `pyproject.toml`. Runtime dependencies are optional extras:

```toml
[project.optional-dependencies]
openai = ["openai>=2.0"]           # provider_model, model gateway, hybrid routing
anthropic = ["anthropic>=0.100"]   # provider_model, model gateway
ollama = ["ollama>=0.5"]           # provider_model (Ollama native)
mcp = ["mcp>=1.27,<2"]            # MCP connector registry (live connections)
rbac = ["pycasbin>=2.8"]          # RBAC enforcement (live deployments)
```

All imports are lazy (inside method bodies), so packages import without optional deps installed. CI and contract tests run with `dependencies = []`.

### Web UI Deployment

The Python services remain pure-function handlers. The deployment layer wraps them in an ASGI server (e.g., `uvicorn` or `hypercorn` — deployment concern, not package concern). Web apps (`apps/web_chat/`, `apps/admin_console/`) are static TypeScript bundles served by the same ASGI server or a CDN. SSE streaming from `encode_sse_event()` flows through the ASGI server to the browser's `EventSource` API.

### Tenant Isolation Chain

```
Request → RBAC (Casbin domain=tenant_id) → API handler (filters by tenant_id)
  → ContractLogReadModel (dict comprehension: {k:v for k,v in items if v.tenant_id == tenant_id})
  → HindsightMemory (bank_id = ink-{tenant}:{workspace}:{user})
  → Contract log writer (path: contract_logs/{tenant_id}/{workspace_id}/)
```

Every layer enforces tenant isolation independently. RBAC prevents unauthorized access; data layer filters by `tenant_id`; memory layer uses isolated banks; log writer partitions by tenant path.

---

## Rejected Alternatives

| Recommended | Alternative | Reason Rejected |
|-------------|-------------|-----------------|
| Python stdlib async generators for streaming | `sse-starlette` v3.4.5 | Requires Starlette/FastAPI as dependency. The existing `encode_sse_event()` is a pure-stdlib SSE encoder that's already proven. Adding Starlette breaks the `dependencies = []` pattern. |
| Python stdlib async generators for streaming | `websockets` library | WebSocket is bidirectional but unnecessary for run-event streaming (server→client only). SSE is simpler, works through proxies, and matches the existing `encode_sse_event()` + `EventSource` pattern. |
| `mcp` SDK v1.28.1 (stable) | `mcp` SDK v2.0.0b1 (beta) | v2 is a pre-release with breaking API changes, targeting 2026-07-28 spec release. Not production-ready. Pin `mcp>=1.27,<2`. |
| `mcp` SDK for MCP connector registry | OpenAI Agents SDK MCP integration | `openai-agents` is a multi-agent framework, not an MCP client library. Adds unnecessary agent orchestration abstractions. |
| `pycasbin` v2.8.0 for RBAC | `casbin-fastapi-decorator` v1.2.1 | Requires FastAPI. The existing services use pure-function handlers, not FastAPI routes. |
| `pycasbin` v2.8.0 for RBAC | Custom RBAC from scratch | Casbin's domain/tenant model is well-tested, supports ABAC, and maps exactly to multi-tenant isolation. Building from scratch risks security bugs. |
| `pycasbin` v2.8.0 for RBAC | `fastapi-permission` / `fastapi-authz` | All FastAPI-specific. Breaks the pure-function handler pattern. |
| Application-level `tenant_id` partitioning | PostgreSQL Row-Level Security (RLS) | The platform uses JSONL contract logs, not PostgreSQL (PRD §1.2). RLS requires a relational database. |
| Application-level `tenant_id` partitioning | Schema-per-tenant or database-per-tenant | Same issue — no relational database. Application-level filtering on in-memory dicts and JSONL files is sufficient at lawyer-trial scale. |
| Preact 10.x for Web UI | React 19 | 40KB+ bundle vs 3KB. The existing renderer explicitly lists Preact as a valid host. React's VDOM overhead is unnecessary for a thin chat + admin dashboard. |
| Preact 10.x for Web UI | Svelte / SolidJS / Vue 3 | All are viable but add ecosystem divergence. Preact's React-compat layer means any React ecosystem component can be used if needed. The existing TypeScript SDK and renderer are framework-agnostic. |
| Preact 10.x for Web UI | Next.js / Remix | Server-side rendering frameworks require a Node.js server. The deployment layer is Python ASGI. Static SPA bundles served by the ASGI server or CDN are simpler. |
| Pure-Python `asyncio` orchestrator for multi-agent | LangChain / LangGraph / CrewAI / AutoGen | Heavy frameworks with large dependency trees (LangChain alone pulls 50+ packages). Break `dependencies = []`. The "7 building blocks" pattern (direct SDK + deterministic routing + circuit breaker) is proven and stdlib-only. |
| Pure-Python `asyncio` orchestrator for multi-agent | `justpipe` v0.12.0 | Zero-dependency but unproven (3 stars, 2 contributors). stdlib `asyncio` is battle-tested and sufficient. |
| Pure-Python `asyncio` orchestrator for multi-agent | A2A protocol (`a2a-sdk`) | Agent-to-agent protocol is designed for cross-framework interop. Within a single platform, direct `BackendAdapter` composition is simpler. |
| `openai` + `anthropic` + `ollama` SDKs for multi-provider | LiteLLM v1.90.2 | Heavy dependency (proxy server, caching, 100+ provider adapters). Overkill for 3 providers. Direct SDKs are lighter and prove contract portability. |
| `ollama` v0.6.2 for Ollama native | `AsyncOpenAI(base_url="http://localhost:11434/v1")` only | The OpenAI-compatible endpoint covers basic chat. Use `ollama` library for native features (embeddings, model management). Both are valid; `ollama` is needed only for native features. |
| `hindsight-client` v0.7.2 for session memory | `mem0` / `letta` (MemGPT) | Hindsight is the validated memory backend with proven tenant isolation (bank-per-tenant). Adding a second memory backend adds complexity without benefit. |
| `hindsight-client` v0.7.2 for session memory | Chroma / Qdrant / Weaviate (vector DB) | Hindsight handles embeddings (BGE-M3) and retrieval (BGE-Reranker-V2-M3) internally. A separate vector DB duplicates this capability. |
| Pure-Python JSON file writer for Skill Registry write | SQLAlchemy + database for skill storage | `manifest.json` files are the source of truth (M2 pattern). A database violates "no new authoritative database" (PRD §1.2). |
| Pure-Python confidence scoring for hybrid routing | scikit-learn / transformers for classification | The LLM IS the classifier. Adding ML libraries for routing classification is redundant when an LLM call produces the confidence score directly. |
| Tailwind CSS v4 for admin console styling | MUI / Ant Design / Chakra UI | Component libraries add 100KB+ and impose design system constraints. An internal admin console needs simple utility styling, not a full design system. |
| `@preact/signals` for state management | Redux / Zustand / TanStack Query | Signals are lighter (built for Preact) and sufficient for dashboard widget reactivity. Redux/Zustand add unnecessary boilerplate. TanStack Query is for complex REST/GraphQL caching, not simple JSON polling. |
| Lazy imports + optional extras for all new deps | Required dependencies in `pyproject.toml` | Breaks the `dependencies = []` pattern that all 13 existing packages and 5 services follow. CI and contract tests must run without optional deps. |
