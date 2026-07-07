# Project Research Summary

**Project:** 墨律 InkStatute V2
**Domain:** M3 Platform Extensions — adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant
**Researched:** 2026-07-05

## Executive Summary

M3 Platform Extensions (milestone v1.7) promotes the v1.6 prototype adapters to production, adds four new platform-extension packages (MCP Connector Registry, Model Provider Gateway, Multi-Agent Runtime, Skill Registry Write), introduces hybrid routing with confidence scoring, ships the operator and lawyer Web UI layer, and adds RBAC plus multi-tenant isolation. Encryption-at-rest and retention/destruction are explicitly deferred to M4 per PROJECT.md line 40.

The single most important architectural finding is that **most M3 surfaces are already contract-ready**. Source inspection confirms the frozen v1.6 contracts already contain the fields and Protocol methods M3 needs: `BackendAdapter.stream_events()`, `collect_artifacts()`, `cancel_run()`, `submit_approval()` are all on the frozen 9-method surface; `AdapterCapabilitySet` already has `stream_event_support`, `artifact_return_support`, `session_memory_support`, `parallel_task_support` flags; `AgentResult.artifacts`, `RunEvent`/`RunEventType` (9 event types), `McpServerDescriptor`, `RouteDecision.confidence`, and `tenant_id`/`workspace_id` on all tenant-scoped events are all frozen and present. `HindsightMemory` and `MemoryOrchestrator` are already implemented with tenant-scoped bank isolation. The `WebSseChannelAdapter` already implements the frozen 6-method `ChannelAdapter` Protocol with `supports_streaming=True`.

**Implication:** M3 does NOT modify any frozen Protocol (`BackendAdapter` 9 methods, `ChannelAdapter` 6 methods, `RouterPort.decide`, `SkillRegistryPort` 3 read methods) or any contract schema. M3 is purely additive: new packages, new composite adapters, new services, capability-flag flips (`False` → `True`), and new feature flags — all default-OFF. Every new runtime dependency is an optional extra with lazy imports, preserving the `dependencies = []` invariant that keeps CI and contract tests clean. The 19 V2 gates (969 tests) must stay green throughout; the two open human gates (Phase 5 WeCom UAT + Phase 8 lawyer trial) must run against the V2 baseline without M3 contamination.

## Stack Additions

| Library | Version | Purpose | Dependency Type |
|---------|---------|---------|-----------------|
| Python stdlib `asyncio` + async generators | 3.11+ | Streaming events: `BackendAdapter.stream_events()` yields `RunEvent` records; `encode_sse_event()` already encodes SSE frames | None — stdlib |
| `openai` Python SDK | 2.44.0 | provider_model adapter + model gateway: `AsyncOpenAI` streaming, OpenAI-compatible endpoint for Ollama | Optional: `openai>=2.0`, lazy import |
| `anthropic` Python SDK | 0.116.0 | provider_model adapter + model gateway: `AsyncAnthropic` for Claude (Messages API, content blocks, thinking tokens) | Optional: `anthropic>=0.100`, lazy import |
| `ollama` Python library | 0.6.2 | provider_model adapter: Ollama native API (embeddings, model management); OpenAI-compatible endpoint covers basic chat | Optional: `ollama>=0.5`, lazy import |
| `mcp` Python SDK | 1.28.1 | MCP Connector Registry: `ClientSession` for stdio/SSE/WS transports, JSON-RPC framing, capability negotiation. Pin `<2` | Optional: `mcp>=1.27,<2`, lazy import |
| `pycasbin` (Casbin Python) | 2.8.0 | RBAC with domains: `(sub, domain=tenant_id, obj, act)` tuples map to multi-tenant isolation. `AsyncEnforcer` | Optional: `pycasbin>=2.8`, lazy import |
| Pure-Python token-bucket rate limiter | 3.11+ | Model Provider Gateway: per-provider, per-tenant rate limiting via `asyncio.monotonic()` + `collections.deque` + `asyncio.Lock` | None — stdlib (~30 lines) |
| Preact + `@preact/signals` | 10.x / 2.x | Web UI: 3KB gzipped, React-compatible, fine-grained reactivity for admin dashboard widgets | Frontend (static bundle) |
| Tailwind CSS | 4.x | Admin console styling: utility-first, zero runtime cost | Frontend (build-time) |
| `hindsight-client` | 0.7.2 | Session memory: already integrated, extended from long-term to session scope via `MemoryScope.SESSION` | Already lazy-imported in platform-runtime |
| TypeScript SDK | 5.x | Web apps consume `@inkstatute/platform-sdk-ts` API types; `RenderRecord` renderer stays DOM-free | Existing |

**REJECTED (with rationale):**
- `sse-starlette` — requires Starlette/FastAPI, breaks `dependencies = []`; existing `encode_sse_event()` is sufficient
- `websockets` library — WebSocket is unnecessary; SSE (unidirectional server→client) is the correct protocol
- `mcp` v2.0.0b1 — pre-release with breaking API changes; pin `>=1.27,<2`
- LiteLLM v1.90.2 — 100+ provider proxy server, massive dependency surface; gateway needs routing + rate-limit + fallback only
- `aiolimiter` v3.1.0 — token-bucket is ~30 lines of stdlib code
- LangChain / LangGraph / CrewAI / AutoGen / LlamaIndex — heavy multi-agent frameworks with 50+ transitive deps; stdlib `asyncio` composition is sufficient
- `a2a-sdk` (A2A protocol) — agent-to-agent protocol is overkill for single-platform composition
- React 19 / Next.js / Remix — 40KB+ bundle vs Preact's 3KB; SSR frameworks require Node.js server (deployment is Python ASGI)
- PostgreSQL RLS / schema-per-tenant — platform uses JSONL contract logs, not a relational database (PRD §1.2)
- `mem0` / `letta` / Chroma / Qdrant / Weaviate — Hindsight already handles embeddings (BGE-M3) and retrieval (BGE-Reranker-V2-M3) with proven tenant isolation
- scikit-learn / transformers for routing — the LLM IS the classifier
- MUI / Ant Design — 100KB+ component libraries; Tailwind utility classes suffice for an internal admin console

## Feature Categories

### Adapter Productization

**Table stakes:** Token streaming via SSE (event-typed lifecycle with guaranteed terminal event), cancellation propagation (client → runtime → adapter → provider), progress events for long tasks, artifact return (ref-based schema: `content_ref` + `sha256` + `size_bytes`, never inline binaries), session memory integration with Hindsight (runtime-level, not adapter-level — adapters receive prepared `ContextBundle`, never call Hindsight directly), multi-provider support (Anthropic Claude with Messages API normalization, Ollama local with OpenAI-compatible client), error normalization across providers (reuse v1.6 `ErrorInfo`/`ErrorCategory` pattern).

**Differentiators:** Partial result return on cancellation (preserves lawyer work — half-completed memo with `completeness_fraction`), streaming tool-call visibility (privacy-scrubbed tool name + args preview for legal auditability), per-provider capability negotiation (`AdapterCapabilitySet` flags drive gateway routing).

**Anti-features:** Auto-synthesizing legal skills from streamed outputs, inline raw document content in stream events, direct Hindsight calls from adapters, provider credentials in adapter code/config, auto-fallback that hides provider errors from operators.

### Platform Extensions

**Table stakes:** MCP Connector Registry (registration, discovery with cursor pagination, capability advertising with JSON Schema tool schemas, lifecycle with versioning/soft-delete), Model Provider Gateway (routing rules, rate limiting RPM/TPM/concurrency per tenant/provider, fallback chains with circuit breakers, cost tracking with per-tenant/matter budgets, model selection by capability tier), Multi-Agent Runtime Adapter (sequential/parallel/supervisor orchestration, handoff with context, shared state scoped to `parent_run_id`), Skill Registry write (CRUD, validation, immutable versioning, human review queue with two-person rule for legal skills), model-based routing (LLM-as-router as last escalation tier), hybrid routing (Rule → Skill → Model cascade with confidence thresholds: route ≥0.8, clarify 0.5–0.8, fallback <0.5).

**Differentiators:** Per-tenant MCP connector allowlist, gateway cost-budget per matter/client, multi-agent trace reconstruction in Admin UI, skill rollback with audit trail, confidence-based clarification prompts.

**Anti-features:** Auto-promoting legal skills without human review, MCP connector auto-execution on registration, gateway auto-selecting cheapest model for legal tasks, LLM-as-router with no rule fallback, multi-agent autonomous skill creation, cross-tenant shared state in multi-agent runs.

### Operator & UX Layer

**Table stakes:** Admin Web UI (operator dashboard, session/task inspection, feedback review queue, gate status visualization, health monitoring), Lawyer-facing Web chat (session list, message history, file upload, feedback submission, multi-device sync via server-side sessions).

**Differentiators:** Cost-by-matter dashboard, fallback frequency monitor, routing confidence heatmap, streaming token display, inline artifact preview (PDF.js), multi-agent progress indicator.

**Anti-features:** Admin UI write access to contract logs (append-only), Web chat showing backend notices (output boundary applies), raw legal payload in browser storage, Admin UI exposing secrets, cross-tenant session access.

### Security & Compliance

**Table stakes:** RBAC (4 roles: admin/operator/lawyer/viewer, permissions matrix, token-based auth with JWT, enforcement at every write endpoint), multi-tenant isolation (tenant scoping on all queries, data segregation via `tenant_id` partitioning + Hindsight bank isolation, per-tenant config for connector bindings/rate limits/budgets/skills).

**Differentiators:** Per-tenant skill catalog, per-tenant model gateway budgets, audit log per tenant, role delegation.

**Anti-features:** Global admin bypassing tenant isolation, client-side-only RBAC enforcement, shared credentials across tenants, encryption-at-rest / retention-destruction (deferred to M4 per PROJECT.md line 40), auto-deletion of legal data by retention policy.

## Architecture Integration

### Key Integration Points

1. **Streaming → frozen `BackendAdapter.stream_events()`**: Adapters yield `RunEvent` records; `RunEvent.event_type` is a `str` (type-open), so new event kinds are string values — no Protocol change. Runtime's `DefaultRunRuntime.stream()` already proxies to `backend.stream_events()`. Feature flag `streaming_lane_enabled` already exists. Output boundary applies at the streaming emission point.

2. **Artifacts → frozen `collect_artifacts()` + `AgentResult.artifacts`**: Two complementary frozen surfaces — terminal artifacts in `AgentResult.artifacts` and side-channel via `collect_artifacts(run_id)` returning `ArtifactRecord`. Codex already stores `artifact_refs` in run metadata; M3 populates the frozen fields.

3. **Session memory → runtime-level, NOT adapter-level**: `MemoryOrchestrator.recall()` queries `HindsightMemory` (tenant-scoped bank_id) → injects refs into `ContextBundle` → `DefaultRunRuntime._attach_context_bundle()` attaches to `RunRequest.metadata`. Adapter declares `session_memory_support=True` and consumes the bundle; never calls Hindsight directly. M3 wires existing components as optional injected deps with `session_memory_enabled` flag.

4. **MCP Connector Registry → new `packages/mcp-registry/`**: Read-only `McpRegistryPort` (`list_servers`, `get_server`, `search`), analogous to skill-registry. Router joins skill `required_tool_refs` → MCP server `capability_refs` at read time. `McpServerDescriptor` is already frozen in contract.

5. **Model Provider Gateway → new `packages/model-gateway/` composite `BackendAdapter`**: Wraps multiple provider_model sub-adapters (Anthropic, Ollama, OpenAI) behind the 9-method Protocol. Consumes `RouteDecision` from router, selects provider, enforces rate-limit + fallback. Injected into `DefaultRunRuntime` as `backend` — runtime unchanged.

6. **Multi-Agent Runtime → new composite `BackendAdapter`**: Delegates to `dict[agent_id, BackendAdapter]` sub-adapters. `parallel_task_support=True` for fan-out. Namespaced `run_id` routes `get_run`/`stream_events`/`cancel_run` to correct sub-adapter. No Protocol change — composite IS a BackendAdapter.

7. **Skill Registry Write → new `SkillRegistryWritePort` + `services/admin-write-api/`**: Frozen `SkillRegistryPort` (3 read methods) untouched. New write module in separate file/package. Write path feeds from human-reviewed `FeedbackEvent.skill_candidate`. Gated by RBAC (admin role) + `skill_registry_write_enabled` flag.

8. **Hybrid Routing → router-internal `RouterStrategy.HYBRID`**: Added to router-internal enum (NOT frozen `RouteMode`). Combines RULE + SKILL + optional `ModelClassifierPort` (host-injected, default `None`). Result is still frozen `RouteDecision` with `confidence` field. Strategy recorded in `metadata["router_strategy"]`.

9. **Admin Web UI → extends `admin-console-api`**: Same API service, new read endpoints (`/mcp-servers`, `/model-gateway/health`, `/skills`, `/tenants`). RBAC middleware step between flag gate and route dispatch. Static frontend in `services/admin-web-ui/`.

10. **Lawyer Web Chat → promote existing `web_sse` ChannelAdapter**: From fixture-grade to production: real SSE transport, session auth (RBAC lawyer role). 6-method Protocol unchanged. `web_sse_channel_enabled` flag gates promotion.

11. **RBAC → `packages/rbac/` middleware**: `RbacGuard.check(role, endpoint)` wraps `handle_admin_get/post`. Endpoint→role mapping is declarative. `rbac_enabled` flag (default OFF → falls back to static-token behavior).

12. **Multi-Tenant → `TenantScopeResolver` + `TenantGuard`**: Service-level scoping on existing `tenant_id` fields. `TenantGuard` injects `tenant_id` filter into every read-model query. Contract logs partitioned by `tenant_id`/`workspace_id` path. Hindsight bank isolation already proven.

### New Components

| Component | Location | Responsibility |
|---|---|---|
| `packages/mcp-registry/` | NEW | Read-only MCP connector registry (`McpRegistryPort`) |
| `packages/model-gateway/` | NEW | Composite `BackendAdapter`: routing, rate-limit, fallback, cost tracking |
| `packages/multi-agent-runtime/` | NEW | Composite `BackendAdapter`: multi-agent orchestration |
| `packages/rbac/` | NEW | `Role`, `Permission`, `RbacPolicy`, `RbacGuard` middleware |
| `packages/skill-registry-write/` | NEW | `SkillRegistryWritePort` + `WritableSkillRegistry` |
| `services/admin-write-api/` | NEW | POST/PUT handlers for skill write + MCP registry admin |
| `services/admin-web-ui/` | NEW | Static frontend (TypeScript + Preact) |
| `TenantScopeResolver` / `TenantGuard` | NEW module | Resolve caller tenant_id, enforce scoping on read queries |
| `packages/backends/provider_model/` (runners) | EXTEND | `AnthropicRunner`, `OllamaRunner` behind `ProviderRunner` Protocol |
| `packages/channels/web_sse/` | EXTEND | Promote from fixture-grade to production SSE + session auth |

### Modified Components (additive only — frozen surfaces preserved)

- `feature_flags.py`: ADD 9 new flags (all default `False`): `session_memory_enabled`, `mcp_registry_enabled`, `model_gateway_enabled`, `multi_agent_enabled`, `skill_registry_write_enabled`, `hybrid_routing_enabled`, `web_sse_channel_enabled`, `rbac_enabled`, `multi_tenant_enabled`
- `runtime.py`: ADD optional injected deps (`memory_orchestrator`, `model_gateway`, `tenant_scope_resolver`) — existing constructor params unchanged
- `strategies.py`: ADD `RouterStrategy.HYBRID` (router-internal, NOT contract `RouteMode`)
- `service.py`: ADD `_decide_hybrid()` + optional `model_classifier` dependency
- `skill-registry/`: ADD separate `write.py` module — `registry.py` (frozen read-only) untouched
- `admin-console-api/api.py`: ADD new read route branches + RBAC middleware step
- `admin-console-api/auth.py`: ADD `resolve_identity()` — keep `check_auth_header` as fallback
- Codex/provider_model adapters: Productize `stream_events`/`collect_artifacts`, flip capability flags to `True`

## Critical Pitfalls

1. **Skill Registry write auto-modifying legal conclusion skills** — A feedback-to-skill auto-promotion pipeline turns a poisoned/misclassified feedback event into a live legal skill. In multi-tenant, a skill for tenant A could leak to tenant B. **Prevention:** Human approval record required on every write path (including admin/migration/fixture); immutable versioned skills with rollback; per-tenant skill namespaces at registry layer; contract test asserting no `candidate`→`active` path without human-review record.

2. **Output boundary bypass via streaming, artifacts, or Web UI** — Three new bypass paths: streaming surfaces raw provider tokens/model names/error traces; artifacts carry backend noise; Web UI renders backend output directly. **Prevention:** Boundary at the streaming emission point (allowlist of event types); artifact metadata field allowlist; Web UI renders all backend content as escaped plaintext or via DOMPurify (never `innerHTML`); regression test streaming provider noise fixtures.

3. **`raw_payload_ref` privacy violation via artifacts, memory, or dashboards** — Full document text leaks through inline artifact content, unredacted memory store entries, or admin dashboard endpoints that skip the read-view scrubbing. **Prevention:** Artifacts use refs only in contract events (full content in scoped object store); memory entries store references not full text; Web UI dashboards reuse `conversation-read-view` scrubbing; contract test asserting no `*payload`/`*text`/`*body` full-content fields.

4. **High-risk feedback auto-routing in hybrid routing** — A confidence-miscalibrated router routes high-risk legal questions to a cheap/weak model, bypassing the Hermes reviewed skill set. Cold-start bias sends the first (most consequential) lawyer questions to the cheapest path. **Prevention:** Legal-risk classifier forces high-risk queries to Hermes regardless of confidence; confidence calibration validated against legal-domain eval set; cold-start defaults to safe (Hermes) path; test asserting high-risk fixtures always route to Hermes.

5. **Multi-tenant cross-tenant legal data leakage** — A missing tenant filter in one query, a shared cache key without `tenant_id`, a memory store with loose namespace filters — any causes one law firm's client matters to bleed into another firm's view (breach of client confidentiality). **Prevention:** Tenant isolation at data layer (query interceptor injects tenant filter); cache keys namespaced by `tenant_id`; per-tenant memory namespaces with hard isolation; migration test asserting no null `tenant_id`; dedicated tenant-isolation gate (20th gate).

**Additional pitfalls:** Streaming cancellation not propagating (orphan billing + zombie runs — `try/finally` with `aclose()` + bounded `asyncio.Queue`); MCP malicious tool schemas and capability escalation (admission review + sandboxed execution); gateway cascading failures and fallback loops (circuit breaker + tried-provider tracking + cost ceiling); multi-agent deadlock and infinite handoff (`max_handoffs=5` + cycle detection + copy-on-write state + `asyncio.Semaphore`); RBAC role explosion and default-allow (fixed role set + default-deny CI scan + short-lived tokens); XSS via chat content in Web UI (DOMPurify + httpOnly cookies + CSP); feature flags not defaulting OFF (flag-default test per feature); M3 features breaking 19 V2 gates via contract event drift (gate coverage per PR); V2 human gates disrupted by M3 runtime changes (environment separation).

## Build Order Recommendation

### Phase Group A — Adapter Productization (no new components, contract-ready)

- **A1. Streaming events** — Productize `stream_events` in Codex + provider_model, flip capability flags. Depends on: nothing. Unlocks: web_sse streaming, admin UI live-run view.
- **A2. Artifact return** — Productize `collect_artifacts` + `AgentResult.artifacts`. Depends on: nothing. Unlocks: admin UI artifact view, lawyer chat file delivery.
- **A3. Multi-provider runners** — Anthropic + Ollama `ProviderRunner` implementations. Depends on: A1/A2. Unlocks: Model Provider Gateway.
- **A4. Session memory wiring** — Wire existing `HindsightMemory` + `MemoryOrchestrator` into runtime as optional deps. Depends on: nothing (components exist). Ships in parallel with A1/A2.

### Phase Group B — Platform Extensions (new packages, depend on A)

- **B1. MCP Connector Registry** — New `packages/mcp-registry/` (read-only). Depends on: nothing. Unlocks: router tool-resolution.
- **B2. Skill Registry write** — New `SkillRegistryWritePort` + `admin-write-api/`. Depends on: C1 (RBAC). Unlocks: feedback-driven skill evolution.
- **B3. Hybrid routing** — `RouterStrategy.HYBRID` + `ModelClassifierPort`. Depends on: B1, A3. Unlocks: confidence-scored routing.
- **B4. Model Provider Gateway** — New `packages/model-gateway/` composite BackendAdapter. Depends on: A3, B3. Unlocks: rate-limit/fallback.
- **B5. Multi-Agent Runtime Adapter** — New composite BackendAdapter. Depends on: B4, B1. Unlocks: parallel multi-backend runs.

### Phase Group C — Security & Operator Layer (depend on B for endpoints to protect)

- **C1. RBAC** — New `packages/rbac/` + middleware. Depends on: nothing (pure library) but must ship before any write API or Web UI. Unlocks: admin-write-api, web_sse auth, tenant guards.
- **C2. Multi-tenant isolation** — `TenantScopeResolver` + `TenantGuard`. Depends on: C1. Unlocks: tenant-scoped admin UI, tenant-scoped web chat.
- **C3. Admin Web UI** — New `services/admin-web-ui/` static frontend. Depends on: C1, C2, B1/B4, A1. Unlocks: operator visualization.
- **C4. Lawyer-facing Web chat** — Promote `web_sse` to production. Depends on: C1, C2, A1, A2. Unlocks: web channel acceptance.

**Critical path:** A1 → A3 → B4 → B5 (streaming before multi-provider before gateway before multi-agent). B1 → B3 → B4 (MCP registry before hybrid routing before gateway). C1 → B2 / C3 / C4 (RBAC is the gate for every write and user-facing surface). C2 → C3 / C4 (tenant isolation before multi-tenant UI). A4 is independent (parallel with A1/A2).

## Confidence

**HIGH** — All four research outputs (STACK, FEATURES, ARCHITECTURE, PITFALLS) are source-confirmed against frozen contracts, protocols, adapters, runtime, feature flags, and existing M2 components. The key architectural finding (most surfaces are already contract-ready) was verified by direct inspection of `protocols.py:222-239`, `agent_adapter.py:18-33`, `events.py:115-122,147,207-212,228-249,391-428,459-483`, `enums.py:100-109,164-168`, `hindsight_memory.py:107-113`, `memory_orchestrator.py`, `runtime.py:147-168`, `feature_flags.py:15`, and `web_sse/adapter.py`. Stack recommendations are pinned to specific stable versions (not pre-releases). Pitfalls are drawn from documented real-world patterns (LLM chat UI CVEs, LLM gateway cascading failures, multi-tenant data leakage cases) and mapped to specific prevention tests. The only MEDIUM-confidence area is multi-agent orchestration complexity (COMPLEX rating, highest-risk feature) — the pure-stdlib `asyncio` approach is sound but unproven at production scale for legal-domain multi-agent workflows.
