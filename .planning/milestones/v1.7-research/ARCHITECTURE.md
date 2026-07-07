# Architecture Research: M3 Platform Extensions

**Domain:** M3 Platform Extensions — adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant
**Researched:** 2026-07-05
**Confidence:** HIGH (source-confirmed against frozen contracts, protocols, adapters, runtime, feature flags, and existing M2 components)

---

## Key Finding: Most M3 Surfaces Are Already Contract-Ready

A critical finding from source inspection: the frozen v1.6 contracts **already contain** the fields and Protocol methods that M3 needs. The M3 work is primarily **implementation productization and new composite components**, not contract extension. Specifically:

- `BackendAdapter` Protocol (`packages/platform-runtime/src/platform_runtime/protocols.py:222-239`) — the frozen 9 methods **already include** `stream_events`, `collect_artifacts`, `submit_approval`, `cancel_run`. Streaming, artifacts, approval, and cancel are already on the frozen surface.
- `AdapterCapabilitySet` (`packages/platform-contract/src/platform_contract/agent_adapter.py:18-33`) — **already has** `stream_event_support`, `artifact_return_support`, `session_memory_support`, `cancel_support`, `approval_support`, `live_update_support`, `parallel_task_support` flags. Adapters declare capabilities truthfully; no new flags needed.
- `AgentResult.artifacts: list[Artifact]` (`events.py:147`) — artifact return field already exists.
- `RunEvent.event_type: str` + `payload: JsonObject` (`protocols.py:137-145`) — streaming vehicle is type-open; new event kinds are string values, not new methods.
- `RunEventType` enum (`enums.py:100-109`) — already includes `MESSAGE_DELTA`, `TOOL_CALL_STARTED/COMPLETED`, `ARTIFACT_CREATED`, `APPROVAL_REQUESTED`, `STEP_STARTED/COMPLETED`, `STATE_CHANGED`, `ERROR`.
- `McpServerDescriptor` (`events.py:115-122`) — MCP registry contract shape already exists (`server_id, name, transport, capability_refs, secret_refs, metadata`).
- `RouteDecision.confidence: float` (`events.py:212`) — hybrid routing confidence field already exists.
- `ChannelMessage.tenant_id` / `ChannelDelivery.tenant_id` / `workspace_id` (`events.py:228,248-249`) and `RunRequest.tenant_id` / `workspace_id` / `session_id` (`protocols.py:111-114`) — multi-tenant fields already on contract events.
- `tenant.schema.json` — neutral tenant identity schema already exists.
- `HindsightMemory` (`packages/platform-runtime/src/platform_runtime/hindsight_memory.py`) — **already implemented**, with tenant/workspace/user → Hindsight `bank_id` isolation.
- `MemoryOrchestrator` (`packages/platform-runtime/src/platform_runtime/memory_orchestrator.py`) — **already composes** `MemoryStoreAdapter` + `ContextAssembler` and injects recalled memory refs into `ContextBundle` without raw text.
- `packages/channels/web_sse/` — **fixture-grade `WebSseChannelAdapter` already exists**, implementing the frozen 6-method `ChannelAdapter` Protocol. `Channel.WEB` enum value already present.

**Implication:** M3 does NOT modify any frozen Protocol (`BackendAdapter` 9 methods, `ChannelAdapter` 6 methods, `RouterPort.decide`, `SkillRegistryPort` 3 read methods). M3 is additive: new packages, new composite adapters, new services, capability-flag flips, and feature flags — all default-OFF.

---

## Integration Points with Existing Architecture

### 1. Streaming Events → Frozen `BackendAdapter.stream_events()`

**Connects to:** `BackendAdapter.stream_events(self, run_id: str) -> AsyncIterator[RunEvent]` (`protocols.py:233`), `RunEvent` (`protocols.py:137-145`), `RunEventType` enum (`enums.py:100-109`), `AdapterCapabilitySet.stream_event_support` (`agent_adapter.py:28`).

**How it flows:** The frozen Protocol already carries streaming. An adapter that supports streaming sets `stream_event_support=True` in its manifest and yields `RunEvent` records from `stream_events()`. `RunEvent.event_type` is a `str` (not a closed enum at the Protocol level), so new event kinds (e.g. `model_delta`, `provider_fallback`, `subagent_started`) are emitted as new string values inside `event_type` + `payload` — **no Protocol change, no contract schema change**. The existing `RunEventType` enum already covers the common cases.

**What changes:** Codex adapter (`packages/backends/codex/src/inkstatute_backends_codex/adapter.py:130-133`) currently has a no-op `stream_events` (`if False: yield`). Provider_model adapter similarly. M3 productizes these by wiring real streaming from the underlying provider (Codex exec JSON-lines stream, OpenAI/Anthropic SSE deltas). The runtime's `DefaultRunRuntime.stream()` (`runtime.py`, `RunRuntime` Protocol `protocols.py:269`) already proxies to `backend.stream_events()` — no runtime change. Feature flag `streaming_lane_enabled` (`feature_flags.py:15`) already exists and gates the lane.

**New event types vs AgentResult extension:** Streaming events are transient `RunEvent` records, NOT extensions to `AgentResult`. `AgentResult` remains the terminal aggregate (frozen). New event kinds live in `RunEvent.event_type` strings + `payload`. This preserves the output boundary: streaming deltas pass through `AssistantOutputBoundary` (`ports.py:34-40`) before reaching channels, exactly as terminal `AgentResult.content` does.

### 2. Artifact Return → Frozen `BackendAdapter.collect_artifacts()` + `AgentResult.artifacts`

**Connects to:** `BackendAdapter.collect_artifacts(self, run_id: str) -> list[ArtifactRecord]` (`protocols.py:239`), `AgentResult.artifacts: list[Artifact]` (`events.py:147`), `ArtifactRecord` runtime dataclass (`protocols.py:157-164`), `ArtifactKind` enum (`enums.py:89-97`), `AdapterCapabilitySet.artifact_return_support` (`agent_adapter.py:24`), `artifact_record.schema.json`.

**How it flows:** Two complementary surfaces, both already frozen:
1. **Terminal artifacts** — `AgentResult.artifacts` carries `Artifact` records (with `uri`, `kind`, `source_refs`) in the final result. The mapper writes these into `ExecutionTrace.artifacts_written` (`events.py:196`).
2. **Side-channel artifacts** — `collect_artifacts(run_id)` returns `ArtifactRecord` (runtime shape: `artifact_id, kind, uri_ref, name, metadata`) for artifacts produced mid-run (e.g. a docx generated before the run fully completes). The runtime/host calls this after `get_run()` to harvest artifacts.

**No new contract event needed.** The `artifact_record.schema.json` and `Artifact` dataclass already exist. Adapters set `artifact_return_support=True` and populate both surfaces. Codex currently returns `artifact_refs` in `CodexExecResult` (`adapter.py:39`) but stores them in run metadata — M3 productizes this by populating `AgentResult.artifacts` and `_artifacts[run_id]` (the store at `adapter.py:63`) so `collect_artifacts` returns real records.

### 3. Session Memory (Hindsight) → Runtime-Level, NOT Adapter-Level

**Connects to:** `AdapterCapabilitySet.session_memory_support` (`agent_adapter.py:33`), `HindsightMemory` (`packages/platform-runtime/src/platform_runtime/hindsight_memory.py`), `MemoryOrchestrator` (`packages/platform-runtime/src/platform_runtime/memory_orchestrator.py`), `MemoryStoreAdapter` Protocol (`memory_adapters.py:66-88`), `ContextAssembler` + `ContextBundle` (`context_assembler.py`), `DefaultRunRuntime._attach_context_bundle()` (`runtime.py:147-168`), `MemoryRecord`/`MemoryUse` contract events.

**How it flows — runtime-level, not adapter-level:** Session memory is orchestrated by the **runtime**, not by individual backends. The adapter only declares `session_memory_support=True` to signal that it can consume a `ContextBundle` containing memory refs. The actual memory lifecycle is:

1. `MemoryOrchestrator.recall()` queries `HindsightMemory` (which implements the `Memory` long-term interface) scoped by `(tenant_id, workspace_id, user_id)` → Hindsight `bank_id` (`hindsight_memory.py:107-113`). Hindsight already enforces per-tenant/workspace/user bank isolation.
2. Recalled memory refs are injected into `ContextAssemblyInput` → `ContextBundle` by `MemoryOrchestrator`.
3. `DefaultRunRuntime._attach_context_bundle()` (`runtime.py:147-168`) attaches the `context_bundle` to `RunRequest.metadata` before calling `backend.submit_run()`. This is gated by `context_assembly_enabled` flag.
4. After run completion, `MemoryOrchestrator` can retain new memory from the result and record `MemoryUse` evidence (via `memory_events.py` `MemoryObserver`).

**Adapter-level vs runtime-level answer:** RUNTIME-LEVEL. The adapter does NOT call Hindsight directly. The adapter declares the capability flag and consumes context bundles the runtime assembles. This keeps `BackendAdapter` frozen and keeps memory provider selection (Hindsight vs others) as a host-injected `MemoryStoreAdapter` — exactly the seam `memory_adapters.py` already defines. M3 work: wire `MemoryOrchestrator` + `HindsightMemory` into `DefaultRunRuntime` as optional injected dependencies (alongside `context_assembler`), gated by a new `session_memory_enabled` feature flag.

### 4. MCP Connector Registry → New Package, Connects to Router + Context Bundle

**Connects to:** `McpServerDescriptor` (`events.py:115-122`), `RouteDecision.required_tools: list[str]` (`events.py:217`), `NeutralSkillDescriptor.required_tool_refs` (`events.py:111`), `RouterService` (`packages/router-service/src/inkstatute_router_service/service.py`), `SkillRegistryPort` (`packages/skill-registry/src/inkstatute_skill_registry/registry.py:16-28`).

**How it flows:** A new `packages/mcp-registry/` package (analogous to `packages/skill-registry/`) exposes a read-only `McpRegistryPort` Protocol: `list_servers()`, `get_server(server_id)`, `search(capability=...)`. The registry is backed by connector descriptors (file-based or config-driven, same pattern as skill-registry). The router queries the MCP registry when computing `RouteDecision.required_tools` — if a routed skill declares `required_tool_refs`, the router can resolve which MCP servers provide those tools and record `server_id` refs in `RouteDecision.metadata`. The runtime then injects MCP server refs into the `ContextBundle` so the backend knows which tool connectors are available for the run.

**Connection to skill/router architecture:** The skill registry provides `required_tool_refs` per skill; the MCP registry provides `capability_refs` per server. The router joins these two: skill → required tools → MCP servers that provide them. This is a read-time join inside the router service (or a new `ToolResolver` helper) — no contract change. `McpServerDescriptor.secret_refs` (`events.py:121`) keeps secret references out of the descriptor body, consistent with the platform's reference-first privacy rule.

### 5. Model Provider Gateway → New Composite BackendAdapter Between Router and Backends

**Connects to:** `BackendAdapter` Protocol (`protocols.py:222-239`), `provider_model` adapter (`packages/backends/provider_model/`), `RouterPort.decide()` (`packages/router-service/src/inkstatute_router_service/port.py:23`), `RouteDecision` (`events.py:206-222`), runtime selector (`services/wecom-service/src/wecom_service/agent_backend.py`).

**Where it sits:** Between the router and the concrete provider adapters. The gateway is itself a `BackendAdapter` (composite/delegating pattern): it implements the same 9 frozen methods, internally holds multiple provider_model adapter instances (Anthropic, Ollama, OpenAI), and delegates `submit_run` to the chosen provider based on `RouteDecision` + rate-limit state + fallback policy.

**New service vs extension of router-service:** NEW PACKAGE `packages/model-gateway/` (library, not a standalone service — consistent with the embeddable, library-first architecture). The router-service produces `RouteDecision`; the gateway consumes it (via `RunRequest.metadata` carrying route info) and selects a provider. The gateway is injected into `DefaultRunRuntime` as the `backend` (it IS a BackendAdapter), so the runtime is unchanged. Rate-limit and fallback state live inside the gateway as host-injected stores (same `ContractLogStore`-style port pattern). The router-service is NOT extended — it remains stateless with its frozen `RouterPort.decide()`.

**Multi-provider support (Anthropic, Ollama):** The existing `provider_model` adapter (`packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py`) uses `AsyncOpenAI`. M3 adds provider-specific runners (Anthropic runner, Ollama runner) behind a `ProviderRunner` Protocol, each producing the same `AgentResult`/`ArtifactRecord` shapes. The gateway picks the runner. No Protocol change.

### 6. Multi-Agent Runtime Adapter → New Composite BackendAdapter

**Connects to:** `BackendAdapter` Protocol (`protocols.py:222-239`), `DefaultRunRuntime` (`runtime.py:25-50`), `RouteDecision.primary_skill` / `supporting_skills` (`events.py:210,214`), `RunRequest.solution` (`protocols.py:110`), `AdapterCapabilitySet.parallel_task_support` (`agent_adapter.py:32`).

**How it composes multiple BackendAdapter instances:** A new `MultiAgentBackendAdapter` (in `packages/platform-runtime/` or a new `packages/multi-agent-runtime/` package) implements the 9-method `BackendAdapter` Protocol by delegating to a registry of sub-adapters keyed by `backend_id` / `solution_id`. On `submit_run(req)`, it inspects `req.solution.backend_id` (or `RouteDecision` in `req.metadata`) to pick the sub-adapter, calls `sub.submit_run(req)`, and returns a `RunHandle` whose `backend_run_id` is namespaced by sub-adapter. `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts` all route to the correct sub-adapter via the namespaced `run_id`. For parallel multi-agent (a turn fanning out to multiple backends), the composite adapter can issue multiple `submit_run` calls and merge `RunEvent` streams — `parallel_task_support=True` declares this capability.

**No Protocol change:** The composite is a BackendAdapter to the runtime; the runtime sees one backend. Sub-adapters are BackendAdapters to the composite. The 9-method surface is preserved at every level. This is the same structural-subtyping pattern the codebase already uses (`RouterService` implements `RouterPort` structurally).

### 7. Skill Registry Write → New Write Port + Service, Read-Only Registry Untouched

**Connects to:** `SkillRegistryPort` (`packages/skill-registry/src/inkstatute_skill_registry/registry.py:16-28` — frozen read-only, 3 methods), `NeutralSkillDescriptor` (`events.py:104-112`), `FeedbackEvent.skill_candidate` (`events.py:174`), `SkillCandidate` (`events.py:73-81`), `feedback-service` (`services/feedback-service/`).

**How it extends read-only:** The frozen `SkillRegistryPort` (3 read methods) is NOT modified. A NEW `SkillRegistryWritePort` Protocol is defined in a new `packages/skill-registry-write/` package (or a `write.py` module inside `packages/skill-registry/` that is clearly separate from the frozen `registry.py`): `upsert_skill(descriptor)`, `deprecate_skill(skill_id)`, `list_pending_candidates()`. The write path feeds from human-reviewed `FeedbackEvent.skill_candidate` records (the feedback-service already produces these; AGENTS.md mandates human review — no auto-synthesis). A new `services/skill-registry-write-api/` service exposes POST/PUT handlers gated by RBAC (admin role only) and a new `skill_registry_write_enabled` feature flag.

**New service vs extend packages/skill-registry:** BOTH — extend `packages/skill-registry/` with a separate write module (new `SkillRegistryWritePort` + `WritableSkillRegistry` class backed by a mutable store), and add a new `services/skill-registry-write-api/` for the HTTP write surface. The read API (`api.py` `handle_get`) remains unchanged. This keeps the read-only enforcement structural (read path has no write functions) while adding a clearly-separated write path.

### 8. Hybrid Routing → New Router-Internal Strategy, Frozen RouteMode Untouched

**Connects to:** `RouterPort.decide()` (`port.py:23` — frozen 1 method), `RouterStrategy` enum (`packages/router-service/src/inkstatute_router_service/strategies.py:21-30` — router-internal, NOT contract), `RouteDecision.confidence: float` (`events.py:212`), `RouteMode` enum (`enums.py:164-168` — frozen: matched/simple_qa/skipped/zero_match), `RouterService` (`service.py:28-50`).

**How it extends router-service:** Add a new `RouterStrategy.HYBRID` value to the **router-internal** `RouterStrategy` enum (this is NOT the frozen `RouteMode` enum — `strategies.py:9-13` explicitly documents this distinction). The HYBRID strategy combines RULE + SKILL + model-based scoring: it calls `classify_intent` (RULE), queries the skill registry (SKILL), and optionally calls a model-based classifier (via the Model Provider Gateway) to produce a confidence score. The result is still a `RouteDecision` with frozen `RouteMode` values; the strategy is recorded in `metadata["router_strategy"]` (already the pattern at `service.py:67`). Confidence scoring flows through `RouteDecision.confidence` (already a float field) and supporting evidence in `metadata`.

**Confidence scoring data flow:** `context` (message, skill_id, history) → HYBRID strategy → rule_score + skill_score + model_score → weighted `confidence` → `RouteDecision(mode, primary_skill, confidence, metadata)`. The model-based score is obtained by calling the Model Provider Gateway's `submit_run` with a classification prompt — this is a backend call, not a router-internal computation, so the router gains an optional `ModelClassifierPort` dependency (host-injected, default `None` → falls back to RULE+SKILL only). No contract change.

### 9. Admin Web UI → Same admin-console-api + New RBAC-Gated Endpoints

**Connects to:** `services/admin-console-api/src/admin_console_api/api.py` (`handle_admin_get` — read-only, static token auth), `auth.py` (`check_auth_header`, `resolve_admin_token`), `RuntimeFeatureFlags.admin_api_enabled` (`feature_flags.py:22`), `conversation-read-view`, `gates.py`, `health.py`, `views.py`.

**Same API vs new endpoints:** SAME API service, EXTENDED. The Admin Web UI is a new static frontend (TypeScript SDK / renderer already exists in `packages/platform-sdk-ts/`) that calls `services/admin-console-api/`. The existing `handle_admin_get` endpoints (`/sessions`, `/tasks`, `/feedback`, `/health`, `/gates`) cover current views. M3 adds new read endpoints for M3 surfaces: `/mcp-servers`, `/model-gateway/health`, `/skills` (proxy to skill-registry), `/tenants`. These are additive `handle_admin_get` route branches — no change to existing endpoints.

**Write endpoints:** Skill Registry write requires POST/PUT. A new `handle_admin_post` (and `handle_admin_put`) is added to `admin-console-api`, gated by RBAC (admin role) + `skill_registry_write_enabled` flag. The read-only `handle_admin_get` is unchanged. This breaks the "read-only" characterization of admin-console-api, so the service should be renamed conceptually to "admin-console" (drop "-api" read-only framing) OR the write API is a separate `services/admin-write-api/` service. Recommendation: separate `services/admin-write-api/` to preserve the read-only safety property of `admin-console-api` (the contract-test-suite has a `test_read_only.py` gate that must stay green).

### 10. Lawyer-Facing Web Chat → Promote Existing `web_sse` ChannelAdapter

**Connects to:** `packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py` (`WebSseChannelAdapter` — fixture-grade, 6-method `ChannelAdapter` Protocol), `Channel.WEB` enum (`enums.py:36`), `ChannelCapabilitySet.supports_streaming` (`protocols.py:63`), `packages/channel-core/` (shared channel logic), `DefaultRunRuntime` (accepts `channels: Iterable[ChannelAdapter]`).

**New ChannelAdapter vs web-sse-channel extension:** EXTEND EXISTING. The `WebSseChannelAdapter` already implements the frozen 6-method `ChannelAdapter` Protocol and already declares `supports_streaming=True`, `supports_files=True` (`adapter.py:36-45`). M3 promotes it from fixture-grade (`fixture_only: True`, `network_io: False`) to production-grade by: (1) adding a real SSE server transport (the `sse.py` module already exists), (2) adding session auth (RBAC — lawyer role), (3) wiring `verify_and_ack` / `normalize_inbound` / `deliver` to real HTTP instead of fixture metadata. No Protocol change — the 6 methods are frozen and already implemented. A new `web_sse_channel_enabled` feature flag gates promotion.

**How it connects to channel architecture:** Identical to WeCom/QQBot — the runtime accepts `channels: Iterable[ChannelAdapter]` (`runtime.py:32`); the web_sse adapter is registered alongside wecom and qqbot. Inbound web messages become `AgentTurn` (channel="web"); deliveries become `ChannelDelivery`. Feedback from web chat becomes `FeedbackEvent` with `source="web_form"` (already supported by `FeedbackSource` enum `enums.py:135`). The output boundary applies identically.

### 11. RBAC → Middleware Layer in admin-console-api + web_sse Auth

**Connects to:** `services/admin-console-api/src/admin_console_api/auth.py` (static token), `api.py` (auth gate at `api.py:51-68`), `web_sse` channel session auth, `services/admin-write-api/` (new), `RuntimeFeatureFlags`.

**Middleware vs service-level:** MIDDLEWARE. The current `auth.py` does a single static-token check. M3 extends this to a two-layer auth: (1) authentication (resolve identity from token/JWT/claims — extend `auth.py` with `resolve_identity()`), (2) authorization (role-based guard — new `packages/rbac/` or `admin_console_api/rbac.py` with `RbacGuard.check(role, endpoint)`). The guard wraps `handle_admin_get` / `handle_admin_post` as a middleware step between the existing flag gate and route dispatch (`api.py:39-70`). Endpoint → required-role mapping is declarative (e.g. `/sessions` → `viewer`, `/skills` POST → `admin`, `/mcp-servers` → `operator`).

**New package:** `packages/rbac/` (library) defining `Role`, `Permission`, `RbacPolicy` (endpoint→role map), and `RbacGuard`. Imported by `admin-console-api`, `admin-write-api`, and `web_sse` channel (lawyer role for chat, operator role for health). Roles: `admin`, `operator`, `lawyer`, `viewer`. Feature flag `rbac_enabled` (default OFF — when OFF, falls back to existing static-token behavior to preserve v1.6 gate green).

### 12. Multi-Tenant Isolation → Service-Level Scoping on Existing tenant_id Fields

**Connects to:** `ChannelMessage.tenant_id` / `workspace_id` (`events.py:228-229`), `ChannelDelivery.tenant_id` / `workspace_id` (`events.py:248-249`), `RunRequest.tenant_id` / `workspace_id` / `session_id` (`protocols.py:111-114`), `tenant.schema.json`, `HindsightMemory._bank_id()` (`hindsight_memory.py:107-113`), `conversation-read-view`, `admin-console-api`, `ContractLogStore` (`ports.py:30-31`).

**tenant_id in events vs service-level scoping:** BOTH, but the contract side is already done — no new fields on frozen events. `AgentTurn` and `AgentResult` do NOT carry `tenant_id` (they are turn-level/result-level; tenant is resolved at the `RunRequest` and `ChannelMessage` level). The tenant scope flows: `ChannelMessage.tenant_id` → `RunRequest.tenant_id` → `DefaultRunRuntime` → `backend.submit_run(req)` → backend sees `req.tenant_id`. M3 adds a `TenantScopeResolver` that enforces every read query (conversation-read-view, admin-console-api) filters by the caller's tenant_id. This is SERVICE-LEVEL scoping: a new `TenantGuard` middleware in admin-console-api and conversation-read-view that injects `tenant_id` filter into every read-model query.

**Effect on contract logs:** Contract logs (JSONL via `ContractLogStore.append`) already record tenant_id on channel-scoped events (`ChannelMessage`, `ChannelDelivery`). For turn-level events (`AgentTurn`, `AgentResult`, `ExecutionTrace`), tenant_id is recoverable via the `turn_id` → `ChannelMessage` join (the conversation-read-view already does trace reconstruction by `trace_id`). M3 does NOT add `tenant_id` to `AgentTurn`/`AgentResult` (that would be a frozen-schema change). Instead, the read views enforce tenant scoping at query time by joining to `ChannelMessage.tenant_id`. `HindsightMemory` already enforces tenant isolation at the memory bank level.

---

## New Components

| Component | Location | Responsibility | Dependencies |
|---|---|---|---|
| `packages/mcp-registry/` | NEW | Read-only MCP connector registry: `McpRegistryPort` (`list_servers`, `get_server`, `search`), backed by `McpServerDescriptor` records. | `platform-contract` (McpServerDescriptor), `platform-runtime` (feature flags) |
| `packages/model-gateway/` | NEW | Composite `BackendAdapter` that routes `submit_run` to provider_model sub-adapters (Anthropic, Ollama, OpenAI) with rate-limit + fallback. | `packages/backends/provider_model`, `platform-runtime` (BackendAdapter Protocol), `router-service` (RouteDecision) |
| `packages/multi-agent-runtime/` | NEW (or module in `platform-runtime`) | Composite `BackendAdapter` that delegates to multiple sub-adapters by `solution.backend_id`; supports parallel fan-out. | `platform-runtime` (BackendAdapter, RunRequest), `platform-contract` |
| `packages/rbac/` | NEW | `Role`, `Permission`, `RbacPolicy`, `RbacGuard` middleware library. | none (pure library) |
| `packages/skill-registry-write/` | NEW (or `write.py` in `skill-registry`) | `SkillRegistryWritePort` (`upsert_skill`, `deprecate_skill`, `list_pending_candidates`), `WritableSkillRegistry` class. | `packages/skill-registry` (NeutralSkillDescriptor), `platform-contract`, `feedback-service` (skill_candidate source) |
| `services/admin-write-api/` | NEW | POST/PUT handlers for skill write + MCP registry admin, gated by RBAC (admin role) + feature flags. | `packages/skill-registry-write`, `packages/rbac`, `packages/mcp-registry`, `platform-runtime` (feature flags) |
| `services/admin-web-ui/` | NEW | Static frontend (TypeScript SDK + renderer) calling `admin-console-api` + `admin-write-api`. | `packages/platform-sdk-ts`, `services/admin-console-api`, `services/admin-write-api` |
| `packages/backends/provider_model/` (Anthropic/Ollama runners) | EXTEND | New `AnthropicRunner`, `OllamaRunner` behind `ProviderRunner` Protocol. | existing `provider_model` package |
| `packages/channels/web_sse/` (production promotion) | EXTEND | Promote from fixture-grade to real SSE server + session auth. | `packages/rbac`, `packages/channel-core` |
| `TenantScopeResolver` / `TenantGuard` | NEW module in `platform-runtime` or `packages/rbac/` | Resolve caller tenant_id and enforce scoping on read queries. | `platform-contract` (tenant_id fields), `conversation-read-view`, `admin-console-api` |

---

## Modified Components

**NONE of the following are modified in their frozen surface. Modifications are additive (new feature flags, new injected dependencies, new route branches) only.**

| Component | Modification (additive only) | Frozen surface preserved |
|---|---|---|
| `packages/platform-contract/` | NONE. No schema changes, no enum additions, no new dataclass fields. | All 5 contracts + enums + AdapterCapabilitySet + Protocols unchanged |
| `packages/platform-runtime/src/platform_runtime/protocols.py` | NONE. BackendAdapter (9), ChannelAdapter (6), RouterPort (1), SkillRegistryPort (3) unchanged. | All Protocol method counts unchanged |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | ADD new flags: `session_memory_enabled`, `mcp_registry_enabled`, `model_gateway_enabled`, `multi_agent_enabled`, `skill_registry_write_enabled`, `hybrid_routing_enabled`, `web_sse_channel_enabled` (production), `rbac_enabled`, `multi_tenant_enabled`. All default `False`. | Existing 12 flags unchanged |
| `packages/platform-runtime/src/platform_runtime/runtime.py` | ADD optional injected deps to `DefaultRunRuntime.__init__`: `memory_orchestrator`, `model_gateway` (as `backend` replacement), `tenant_scope_resolver`. Existing constructor params unchanged. | `RunRuntime` Protocol (6 methods) unchanged |
| `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` | Productize `stream_events` (real JSON-lines stream), `collect_artifacts` (populate `_artifacts` store), flip `stream_event_support`/`artifact_return_support` to `True` in manifest. | 9-method BackendAdapter surface unchanged |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` | Add Anthropic/Ollama runners, productize streaming + artifacts, flip capability flags. | 9-method BackendAdapter surface unchanged |
| `packages/router-service/src/inkstatute_router_service/strategies.py` | ADD `RouterStrategy.HYBRID` (router-internal enum, NOT contract `RouteMode`). | `RouterPort.decide()` (1 method) unchanged; `RouteMode` enum unchanged |
| `packages/router-service/src/inkstatute_router_service/service.py` | ADD `_decide_hybrid()` method, optional `model_classifier` dependency. | `decide()` signature unchanged |
| `packages/skill-registry/src/inkstatute_skill_registry/` | ADD separate `write.py` module (or new package) — do NOT modify `registry.py` (frozen read-only `SkillRegistryPort`). | `SkillRegistryPort` (3 read methods) unchanged |
| `services/admin-console-api/src/admin_console_api/api.py` | ADD new read route branches (`/mcp-servers`, `/model-gateway/health`, `/skills`, `/tenants`); ADD RBAC middleware step. | `handle_admin_get` signature unchanged; existing routes unchanged |
| `services/admin-console-api/src/admin_console_api/auth.py` | ADD `resolve_identity()` for RBAC; keep `check_auth_header` as fallback when `rbac_enabled=False`. | Existing auth functions unchanged |
| `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | Already accepts `router: RouterPort \| None` (`mapper.py:38`) — wire hybrid router through this existing seam. | `map_agent_end_context` signature unchanged |
| `packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py` | Promote to production: real SSE transport, session auth. Flip `fixture_only`/`network_io` metadata. | 6-method ChannelAdapter surface unchanged |

---

## Data Flow Changes

### Streaming + Artifacts Flow (M3 productized)

```
Channel inbound → ChannelAdapter.normalize_inbound → AgentTurn
  → RouterPort.decide → RouteDecision (with required_tools from MCP registry join)
  → DefaultRunRuntime.create_run
    → MemoryOrchestrator.recall (Hindsight, tenant-scoped) → ContextBundle
    → backend.submit_run(req with context_bundle)   [backend = ModelGateway or MultiAgentAdapter]
    → backend.stream_events(run_id) → RunEvent stream (event_type strings: message_delta, tool_call_*, artifact_created)
        → AssistantOutputBoundary.apply (filters backend noise)
        → ChannelAdapter.deliver (streaming deltas to web_sse / wecom)
    → backend.get_run → Run with AgentResult.artifacts
    → backend.collect_artifacts → list[ArtifactRecord]
    → ContractLogStore.append (agent_turn, route_decision, execution_trace, agent_result)
    → MemoryOrchestrator.retain (new memory from result, tenant-scoped)
```

### Hybrid Routing Flow

```
context (message, skill_id, history)
  → RouterService.decide (strategy=HYBRID)
    → classify_intent (RULE score)
    → SkillRegistry.search (SKILL score)
    → ModelClassifierPort.classify (model score, via Model Provider Gateway, optional)
    → weighted confidence → RouteDecision(mode, primary_skill, confidence, metadata{router_strategy:"hybrid", scores})
  → hermes-contract-layer mapper consumes RouteDecision (existing router= seam)
```

### MCP Registry Join Flow

```
SkillRegistry.get_skill(skill_id) → NeutralSkillDescriptor.required_tool_refs
  → McpRegistry.search(capability=tool_ref) → list[McpServerDescriptor]
  → RouteDecision.required_tools + metadata.mcp_server_refs
  → ContextBundle includes mcp_server_refs
  → backend consumes mcp_server_refs to call MCP tools during run
```

### RBAC + Multi-Tenant Request Flow

```
HTTP request → admin-console-api
  → feature_flags.require_enabled("admin_api_enabled")
  → auth.resolve_identity (token → identity + role + tenant_id)   [rbac_enabled=True]
  → RbacGuard.check(role, endpoint) → 403 if insufficient
  → TenantGuard.inject_tenant_scope(tenant_id) → read model query filtered by tenant_id
  → handle_sessions/handle_tasks/handle_feedback (existing, now tenant-scoped)
```

### Skill Registry Write Flow

```
FeedbackEvent.skill_candidate (human-reviewed in feedback-service)
  → admin-write-api POST /skills (RBAC: admin role, flag: skill_registry_write_enabled)
  → WritableSkillRegistry.upsert_skill(NeutralSkillDescriptor)
  → SkillRegistry (read side) now returns updated descriptor on next list_skills()
  → router-service SKILL strategy picks up new skill
```

---

## Suggested Build Order

The build order respects dependencies: security primitives before UI, registry before router extensions, composite adapters before multi-agent, and contract-ready features before those needing new components.

### Phase Group A — Adapter Productization (no new components, contract-ready)

**A1. Streaming events productization** — Codex + provider_model `stream_events` real implementations, flip capability flags. Depends on: nothing (frozen Protocol already supports it). Unlocks: web_sse streaming delivery, admin UI live-run view.

**A2. Artifact return productization** — Codex + provider_model `collect_artifacts` + `AgentResult.artifacts` population. Depends on: nothing. Unblocks: admin UI artifact view, lawyer chat file delivery.

**A3. Multi-provider runners (Anthropic, Ollama)** — New `ProviderRunner` implementations behind existing `provider_model` adapter. Depends on: A1/A2 (so the new runners share streaming/artifact productization). Unlocks: Model Provider Gateway.

**A4. Session memory wiring** — Wire existing `HindsightMemory` + `MemoryOrchestrator` into `DefaultRunRuntime` as optional injected deps, add `session_memory_enabled` flag. Depends on: nothing (components already exist). Unlocks: tenant-scoped recall in all backends.

### Phase Group B — Platform Extensions (new packages, depend on A)

**B1. MCP Connector Registry** — New `packages/mcp-registry/` (read-only, analogous to skill-registry). Depends on: nothing (uses existing `McpServerDescriptor`). Unlocks: router tool-resolution, multi-agent tool sharing.

**B2. Skill Registry write** — New `SkillRegistryWritePort` + `WritableSkillRegistry` + `services/admin-write-api/`. Depends on: RBAC (C1) for write gating, feedback-service (exists) for skill_candidate source. Unlocks: feedback-driven skill evolution.

**B3. Hybrid routing** — Add `RouterStrategy.HYBRID` + `ModelClassifierPort`. Depends on: B1 (MCP registry for tool resolution), A3 (model gateway for model-based classification). Unlocks: confidence-scored routing.

**B4. Model Provider Gateway** — New `packages/model-gateway/` composite BackendAdapter. Depends on: A3 (multi-provider runners), B3 (consumes RouteDecision). Unlocks: rate-limit/fallback, multi-agent provider selection.

**B5. Multi-Agent Runtime Adapter** — New composite BackendAdapter. Depends on: B4 (gateway as one sub-adapter), B1 (MCP for shared tools). Unlocks: parallel multi-backend runs.

### Phase Group C — Security & Operator Layer (depend on B for endpoints to protect)

**C1. RBAC** — New `packages/rbac/` + middleware in admin-console-api. Depends on: nothing (pure library) but must come before any write API or Web UI. Unlocks: admin-write-api, web_sse auth, tenant guards.

**C2. Multi-tenant isolation** — `TenantScopeResolver` + `TenantGuard` in read views + admin API. Depends on: C1 (RBAC provides identity/tenant resolution). Unlocks: tenant-scoped admin UI, tenant-scoped web chat.

**C3. Admin Web UI** — New `services/admin-web-ui/` static frontend. Depends on: C1 (RBAC), C2 (tenant scoping), B1/B4 (new read endpoints), A1 (streaming for live-run view). Unlocks: operator visualization.

**C4. Lawyer-facing Web chat** — Promote `web_sse` to production. Depends on: C1 (RBAC lawyer role), C2 (tenant isolation), A1 (streaming delivery), A2 (artifact/file delivery). Unlocks: web channel acceptance.

### Dependency Rationale (critical path)

- **A1 → A3 → B4 → B5**: streaming must work before multi-provider, which must work before the gateway, which must work before multi-agent composition.
- **B1 → B3 → B4**: MCP registry must exist before hybrid routing can resolve tools, which must exist before the gateway consumes route decisions.
- **C1 → B2 / C3 / C4**: RBAC is the gate for every write surface and every user-facing surface. It must ship before skill-write, admin UI, and web chat.
- **C2 → C3 / C4**: tenant isolation must ship before multi-tenant Web UI and web chat expose the platform to multiple tenants.
- **A4 is independent** — session memory wiring can ship in parallel with A1/A2 since `HindsightMemory` and `MemoryOrchestrator` already exist.
- **All phases preserve 19 V2 gates**: every new lane is feature-flag default-OFF; no frozen Protocol is modified; the contract-test-suite `test_contract_freeze_not_violated.py` (in each channel/backend package) stays green throughout.
