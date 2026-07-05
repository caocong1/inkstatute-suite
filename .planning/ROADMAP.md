# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)
- Complete **v1.4 Long-Term Memory Productization** - Phases 26-32 shipped 2026-07-03. Productized long-term memory with Hindsight backend, singleton wiring, and contract event observability. Audit passed (20/20 requirements).
  - Archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)
- Complete **v1.5 V2 Acceptance Closure** - Phases 33-35 shipped 2026-07-03. Audited all unchecked V2 Active requirements, closed code gaps, produced acceptance readiness report. Audit passed (23/23 requirements). Autonomous closure READY; V2 acceptance BLOCKED ON HUMAN GATES (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial).
  - Archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)
- Complete **v1.6 M2 Multi-Backend & Platform Extensions** - Phases 36-44 shipped 2026-07-04. Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate coverage meta-test. Audit passed (22/22 requirements, 19/19 gates green, 969 tests).
  - Archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)
- Active **v1.7 M3 Platform Extensions** - Phases 45-57 (13 phases). Promote adapter prototypes to production-grade, extend platform surface (MCP, model gateway, multi-agent, skill write + hybrid routing), add operator and lawyer-facing Web UI, and introduce RBAC + multi-tenant isolation — while preserving the v1.6 safety strategy.
  - Requirements: `.planning/REQUIREMENTS.md`

## Current Milestone: v1.7 M3 Platform Extensions

**Goal:** Promote adapter prototypes to production-grade, extend the platform surface (MCP, model gateway, multi-agent, skill write + hybrid routing), add operator and lawyer-facing Web UI, and introduce RBAC + multi-tenant isolation — while preserving the v1.6 safety strategy.

**Requirements:** `.planning/REQUIREMENTS.md` (38 requirements)

**Key context:**
- Maintain v1.6 safety strategy: contract freeze, feature flags default OFF, output boundary enforced, human gates (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) preserved.
- All 9 new runtime lanes default-OFF; live promotion remains a human gate.
- Hermes remains the first production backend; Codex/provider_model promoted to production-grade but Hermes stays primary.
- 19 existing V2 gates must stay green throughout (no regressions).
- Phase numbering continues from v1.6 (next phase = 45).
- Critical path: A1 (P46) → A3 (P48) → B4 (P54) → B5 (P55); B1 (P50) → B3 (P53) → B4 (P54); C1 (P51) → B2 (P52) / C3+C4 (P57); C2 (P56) → C3+C4 (P57).

## Phases

- [ ] **Phase 45: M3 Pre-Implementation Safety** - Cross-cutting safety measures (9 feature flags default OFF, frozen Protocol verification, 19 V2 gates green baseline, flag-default tests, V2 human gate isolation) before any M3 feature code.
- [ ] **Phase 46: Streaming Events (A1)** - Productize `stream_events()` in Codex + provider_model adapters with guaranteed terminal event and cancellation propagation.
- [ ] **Phase 47: Artifact Return (A2)** - Productize `collect_artifacts()` + `AgentResult.artifacts` with ref-based schema and output boundary enforcement.
- [ ] **Phase 48: Multi-Provider Runners (A3)** - `AnthropicRunner` and `OllamaRunner` implementing `ProviderRunner` Protocol with error normalization.
- [ ] **Phase 49: Session Memory Wiring (A4)** - Wire existing `HindsightMemory` + `MemoryOrchestrator` into runtime as optional deps; adapters declare `session_memory_support=True` and consume `ContextBundle`.
- [ ] **Phase 50: MCP Connector Registry (B1)** - Read-only MCP Connector Registry with registration, JSON Schema tool schemas, versioning, soft-delete, and router tool-resolution join.
- [ ] **Phase 51: RBAC (C1)** - 4-role RBAC with permissions matrix, `RbacGuard` middleware, default-deny CI scan, and token-based auth with role+tenant claims.
- [ ] **Phase 52: Skill Registry Write (B2)** - `SkillRegistryWritePort` + `WritableSkillRegistry` with CRUD, immutable versioning, human-review two-person rule, and per-tenant namespaces.
- [ ] **Phase 53: Hybrid Routing (B3)** - `RouterStrategy.HYBRID` with Rule → Skill → Model cascade, confidence thresholds, and legal-risk classifier forcing high-risk queries to Hermes.
- [ ] **Phase 54: Model Provider Gateway (B4)** - Composite `BackendAdapter` wrapping multiple provider_model sub-adapters with rate limiting, fallback chains, circuit breakers, and cost tracking.
- [ ] **Phase 55: Multi-Agent Runtime Adapter (B5)** - Composite `BackendAdapter` with sequential/parallel/supervisor orchestration, handoff limits, cycle detection, and copy-on-write shared state.
- [ ] **Phase 56: Multi-Tenant Isolation (C2)** - `TenantScopeResolver` + `TenantGuard` injecting `tenant_id` filter into every read-model query, partitioned contract logs, namespaced cache keys, and migration test.
- [ ] **Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4)** - Operator dashboard Web UI with session/task/feedback/gate/health views and lawyer-facing Web chat with real SSE, session auth, and output boundary enforcement.

## Phase Details

### Phase 45: M3 Pre-Implementation Safety

**Goal:** Operator can verify that all cross-cutting M3 safety measures (9 feature flags default OFF, frozen Protocol method counts unchanged, 19 V2 gates green baseline, flag-default tests, V2 human gate isolation) are in place before any M3 feature code is written, protecting the 969-test V2 gate suite and parallel V2 human gates.
**Depends on:** v1.6 completion (Phase 44)
**Requirements:** SAFETY-01, SAFETY-02, SAFETY-03, SAFETY-04, SAFETY-05
**Success Criteria** (what must be TRUE):
1. All 9 new M3 feature flags (`session_memory_enabled`, `mcp_registry_enabled`, `model_gateway_enabled`, `multi_agent_enabled`, `skill_registry_write_enabled`, `hybrid_routing_enabled`, `web_sse_channel_enabled`, `rbac_enabled`, `multi_tenant_enabled`) default to `False` in `RuntimeFeatureFlags`.
2. Contract-count assertion test confirms no frozen Protocol modified (`BackendAdapter` 9 methods, `ChannelAdapter` 6 methods, `RouterPort.decide`, `SkillRegistryPort` 3 read methods) and `packages/platform-contract/` baseline hash unchanged from v1.6.
3. All 19 V2 gates pass green (969+ tests) with no regressions on the M3 baseline branch.
4. A flag-default test exists for every new M3 feature flag, asserting the flag is `False` by default and the associated runtime lane is inactive when the flag is off.
5. V2 human gate evidence (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) runs against the V2 baseline without M3 feature flag contamination.

**Plans:** TBD

### Phase 46: Streaming Events (A1)

**Goal:** Operator can configure a Codex or provider_model adapter with `stream_event_support=True` and receive SSE streaming events via the frozen `stream_events()` method, with a guaranteed terminal event (completed/failed/cancelled) and client cancellation propagating through runtime → adapter → provider with `aclose()` cleanup.
**Depends on:** Phase 45
**Requirements:** STREAM-01, STREAM-02
**Success Criteria** (what must be TRUE):
1. Codex and provider_model adapters yield `RunEvent` records from `stream_events()` with real provider streaming (Codex exec JSON-lines, OpenAI/Anthropic SSE deltas) and a guaranteed terminal event (`completed`, `failed`, or `cancelled`) on every stream.
2. Client cancellation propagates through runtime → adapter → provider via `aclose()` cleanup, leaving no zombie runs; a `try/finally` block ensures the stream is closed even on exception.
3. Streaming events pass through `AssistantOutputBoundary` before reaching channels, with an allowlist of permitted event types filtering out raw provider tokens, model names, and error traces.

**Plans:** TBD

### Phase 47: Artifact Return (A2)

**Goal:** Operator can call `collect_artifacts(run_id)` on Codex and provider_model adapters and receive `ArtifactRecord` entries with ref-based schema (`content_ref`, `sha256`, `size_bytes` — never inline binaries), and `AgentResult.artifacts` is populated with terminal artifacts, with output boundary enforcement on artifact metadata.
**Depends on:** Phase 45
**Requirements:** ARTIFACT-01, ARTIFACT-02
**Success Criteria** (what must be TRUE):
1. Adapters return artifacts via frozen `collect_artifacts()` and populate `AgentResult.artifacts` with ref-based schema (`content_ref`, `sha256`, `size_bytes`); no inline binary content appears in any artifact record or contract event.
2. Artifact metadata enforces the output boundary — backend noise (model names, API error traces, function call internals) is filtered from artifact metadata fields via an allowlist.
3. Codex adapter populates `AgentResult.artifacts` and `_artifacts[run_id]` store from existing `CodexExecResult.artifact_refs`, and provider_model adapter populates artifacts from provider response file outputs.

**Plans:** TBD

### Phase 48: Multi-Provider Runners (A3)

**Goal:** Operator can configure `AnthropicRunner` and `OllamaRunner` as `ProviderRunner` Protocol implementations behind the provider_model adapter, with Messages API normalization for Anthropic, OpenAI-compatible endpoint for Ollama, and multi-provider error normalization reusing the v1.6 `ErrorInfo`/`ErrorCategory` pattern.
**Depends on:** Phase 46, Phase 47
**Requirements:** MULTIPROV-01, MULTIPROV-02, MULTIPROV-03
**Success Criteria** (what must be TRUE):
1. `AnthropicRunner` implements `ProviderRunner` Protocol with Messages API normalization (system as top-level param, content blocks, thinking tokens) via `AsyncAnthropic` lazy SDK import.
2. `OllamaRunner` implements `ProviderRunner` Protocol for local models via OpenAI-compatible endpoint, with model listing and basic chat completion.
3. Multi-provider error normalization reuses v1.6 `ErrorInfo`/`ErrorCategory` pattern — provider-specific errors (rate limits, auth failures, model unavailable) map to the same error categories with consistent `ErrorInfo` records.
4. Both runners are optional dependencies with lazy imports; `dependencies = []` invariant preserved for CI and contract tests.

**Plans:** TBD

### Phase 49: Session Memory Wiring (A4)

**Goal:** Operator can enable `session_memory_enabled` and the runtime wires existing `HindsightMemory` + `MemoryOrchestrator` as optional injected dependencies, with adapters declaring `session_memory_support=True` and consuming `ContextBundle` — never calling Hindsight directly.
**Depends on:** Phase 45
**Requirements:** SESSMEM-01
**Success Criteria** (what must be TRUE):
1. `DefaultRunRuntime` accepts optional `memory_orchestrator` and `context_assembler` injected dependencies; when `session_memory_enabled=True`, `MemoryOrchestrator.recall()` queries `HindsightMemory` scoped by `(tenant_id, workspace_id, user_id)` and injects recalled memory refs into `ContextBundle` before `backend.submit_run()`.
2. Adapters declare `session_memory_support=True` in their manifest and consume the `ContextBundle` from `RunRequest.metadata`; no adapter calls `HindsightMemory` or any memory provider directly.
3. When `session_memory_enabled=False` (default), no memory orchestration occurs and the runtime behaves identically to v1.6 — the feature is purely additive and opt-in.

**Plans:** TBD

### Phase 50: MCP Connector Registry (B1)

**Goal:** Operator can register and discover MCP tool connectors via a read-only `McpRegistryPort` in a new `packages/mcp-registry/` package, with cursor pagination, JSON Schema tool schemas, versioning, soft-delete, and router tool-resolution joining skill `required_tool_refs` to MCP `capability_refs` at read time.
**Depends on:** Phase 45
**Requirements:** MCP-01, MCP-02, MCP-03
**Success Criteria** (what must be TRUE):
1. `McpRegistryPort` implements read-only operations (`list_servers`, `get_server`, `search`) with cursor pagination, returning `McpServerDescriptor` records matching the frozen contract shape.
2. MCP registry supports registration with JSON Schema tool schemas, versioning (semantic version tracking), and soft-delete (connectors marked inactive, not removed); no auto-execution on registration — admission review required before execution.
3. Router joins skill `required_tool_refs` → MCP server `capability_refs` at read time, producing a unified tool-resolution map without modifying frozen `RouteDecision` or `NeutralSkillDescriptor` schemas.
4. `mcp_registry_enabled` defaults to `False`; the package uses optional `mcp` SDK lazy import with `dependencies = []` invariant preserved.

**Plans:** TBD

### Phase 51: RBAC (C1)

**Goal:** Operator can enforce role-based access control via a new `packages/rbac/` package implementing 4 roles (admin/operator/lawyer/viewer) with a permissions matrix, `RbacGuard` middleware, default-deny with CI scan for unannotated endpoints, and token-based auth with role+tenant claims using short-lived tokens.
**Depends on:** Phase 45
**Requirements:** RBAC-01, RBAC-02, RBAC-03
**Success Criteria** (what must be TRUE):
1. `packages/rbac/` implements 4 roles (admin, operator, lawyer, viewer) with a declarative permissions matrix mapping endpoint → required role; `RbacGuard.check(role, endpoint)` middleware wraps admin API handlers.
2. RBAC enforces default-deny: a CI scan fails when any admin API endpoint lacks a role annotation; unannotated endpoints are treated as denied by default.
3. RBAC token-based auth issues short-lived tokens with role+tenant claims; `resolve_identity()` extracts claims from the token, with `check_auth_header` static-token fallback preserved when `rbac_enabled=False`.
4. `rbac_enabled` defaults to `False`; when disabled, the system falls back to v1.6 static-token behavior with no regression.

**Plans:** TBD

### Phase 52: Skill Registry Write (B2)

**Goal:** Operator with admin role can write skills via a new `SkillRegistryWritePort` + `WritableSkillRegistry` implementing CRUD with immutable versioning, rollback, human-review two-person rule on every write path, and per-tenant skill namespaces — gated by RBAC and `skill_registry_write_enabled` flag.
**Depends on:** Phase 51
**Requirements:** SKILLWRITE-01, SKILLWRITE-02, SKILLWRITE-03
**Success Criteria** (what must be TRUE):
1. `SkillRegistryWritePort` + `WritableSkillRegistry` implements CRUD operations in a separate `write.py` module (frozen `registry.py` read-only module untouched), with immutable versioning (every write creates a new version) and rollback to any prior version.
2. Every skill write path (create, update, delete, migration, fixture load) requires a human-review record with reviewer identity and timestamp; no `candidate` → `active` transition is possible without a human-review record — two-person rule enforced for legal skills.
3. Skill write enforces per-tenant skill namespaces; a skill created in tenant A is not visible or accessible to tenant B; contract test asserts no cross-tenant skill leakage.
4. `skill_registry_write_enabled` defaults to `False`; write endpoints are gated by RBAC admin role + the feature flag.

**Plans:** TBD

### Phase 53: Hybrid Routing (B3)

**Goal:** Operator can configure `RouterStrategy.HYBRID` to implement a Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5), where a legal-risk classifier forces high-risk queries to Hermes regardless of confidence score, and `RouteDecision.confidence` is populated for all hybrid routing decisions.
**Depends on:** Phase 50, Phase 48
**Requirements:** HYBRID-01, HYBRID-02, HYBRID-03
**Success Criteria** (what must be TRUE):
1. `RouterStrategy.HYBRID` (router-internal enum, NOT frozen `RouteMode`) implements Rule → Skill → Model cascade with confidence thresholds: route directly when confidence ≥0.8, emit clarification prompt when 0.5–0.8, fall back to safe path when <0.5.
2. Legal-risk classifier forces high-risk queries to Hermes regardless of confidence score; a test asserts that high-risk legal fixtures always route to Hermes, preventing confidence-miscalibrated routing to cheap/weak models.
3. `RouteDecision.confidence` is populated (float 0.0–1.0) for all hybrid routing decisions; the strategy is recorded in `metadata["router_strategy"]` without modifying the frozen `RouteDecision` schema.
4. `hybrid_routing_enabled` defaults to `False`; cold-start defaults to safe (Hermes) path; `ModelClassifierPort` is host-injected with `None` default preserving in-process fallback.

**Plans:** TBD

### Phase 54: Model Provider Gateway (B4)

**Goal:** Operator can configure a Model Provider Gateway (`packages/model-gateway/`) as a composite `BackendAdapter` wrapping multiple provider_model sub-adapters, with per-tenant/provider rate limiting (RPM/TPM/concurrency), fallback chains with circuit breakers and tried-provider tracking, and per-tenant/matter cost tracking with budget ceilings.
**Depends on:** Phase 48, Phase 53
**Requirements:** GATEWAY-01, GATEWAY-02, GATEWAY-03, GATEWAY-04
**Success Criteria** (what must be TRUE):
1. `packages/model-gateway/` implements a composite `BackendAdapter` wrapping multiple provider_model sub-adapters (Anthropic, Ollama, OpenAI) behind the frozen 9-method Protocol; injected into `DefaultRunRuntime` as `backend` with no runtime change.
2. Gateway enforces per-tenant/provider rate limiting (RPM, TPM, concurrency) via a pure-Python token-bucket implementation using `asyncio.monotonic()` + `collections.deque` + `asyncio.Lock` (~30 lines, no external dependency).
3. Gateway implements fallback chains with circuit breakers (open/half-open/closed states) and tried-provider tracking; cascading failures are prevented by circuit breaker isolation and cost ceiling enforcement.
4. Gateway tracks per-tenant/matter cost with budget ceilings; when a budget is exceeded, the gateway refuses the request and emits an error event — no auto-downgrade for legal tasks (legal-risk classifier forces high-risk queries to Hermes regardless of cost).

**Plans:** TBD

### Phase 55: Multi-Agent Runtime Adapter (B5)

**Goal:** Operator can configure a Multi-Agent Runtime Adapter as a composite `BackendAdapter` delegating by `solution.backend_id`, supporting sequential/parallel/supervisor orchestration with `max_handoffs=5`, cycle detection, and shared state scoped to `parent_run_id` with copy-on-write isolation.
**Depends on:** Phase 54, Phase 50
**Requirements:** MULTIAGENT-01, MULTIAGENT-02, MULTIAGENT-03
**Success Criteria** (what must be TRUE):
1. Multi-Agent Runtime Adapter is a composite `BackendAdapter` delegating to `dict[agent_id, BackendAdapter]` sub-adapters by `solution.backend_id`; namespaced `run_id` routes `get_run`/`stream_events`/`cancel_run` to the correct sub-adapter.
2. Multi-agent supports sequential, parallel, and supervisor orchestration patterns with `max_handoffs=5` limit and cycle detection (visited-set prevents infinite handoff loops); `asyncio.Semaphore` bounds concurrency for parallel fan-out.
3. Multi-agent shared state is scoped to `parent_run_id` with copy-on-write isolation; sub-agent state mutations do not leak to sibling sub-agents or the parent run; no cross-tenant shared state in multi-agent runs.
4. `multi_agent_enabled` defaults to `False`; the composite adapter is injected as `backend` with no Protocol change — the composite IS a `BackendAdapter`.

**Plans:** TBD

### Phase 56: Multi-Tenant Isolation (C2)

**Goal:** Operator can enable multi-tenant isolation via `TenantScopeResolver` + `TenantGuard` that injects `tenant_id` filter into every read-model query, with contract logs partitioned by `tenant_id`/`workspace_id` path, cache keys namespaced by `tenant_id`, Hindsight bank isolation enforced per tenant, and a migration test asserting no null `tenant_id`.
**Depends on:** Phase 51
**Requirements:** TENANT-01, TENANT-02, TENANT-03, TENANT-04
**Success Criteria** (what must be TRUE):
1. `TenantScopeResolver` resolves caller `tenant_id` from RBAC token claims; `TenantGuard` injects `tenant_id` filter into every read-model query, preventing cross-tenant data access at the data layer.
2. Contract logs are partitioned by `tenant_id`/`workspace_id` path; JSONL writers and readers scope file paths by tenant, preventing one firm's client matters from bleeding into another firm's view.
3. Cache keys are namespaced by `tenant_id`; Hindsight bank isolation is enforced per tenant (existing `bank_id` mapping extended with explicit tenant guard); no shared cache keys across tenants.
4. A migration test asserts no null `tenant_id` in any tenant-scoped entity (events, artifacts, memory records, skill descriptors); a dedicated tenant-isolation gate (20th gate) runs fixture-based cross-tenant access denial tests.

**Plans:** TBD

### Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4)

**Goal:** Operator can use an Admin Web UI (`services/admin-web-ui/`) rendering an operator dashboard with session/task inspection, feedback review queue, gate status, and health monitoring, and lawyers can use a Web chat interface with real SSE, session auth, message history, file upload, feedback submission, and multi-device sync — both enforcing the output boundary.
**Depends on:** Phase 51, Phase 56, Phase 50, Phase 54, Phase 46, Phase 47
**Requirements:** ADMINUI-01, ADMINUI-02, ADMINUI-03, LAWCHAT-01, LAWCHAT-02, LAWCHAT-03
**Success Criteria** (what must be TRUE):
1. Admin Web UI (`services/admin-web-ui/`) renders an operator dashboard with session/task inspection, feedback review queue, gate status visualization, and health monitoring; built with Preact + Tailwind (static bundle, no Node.js server required).
2. Admin Web UI consumes existing `admin-console-api` read endpoints plus new read route branches (`/mcp-servers`, `/model-gateway/health`, `/skills`, `/tenants`); RBAC middleware enforces role-based access between flag gate and route dispatch.
3. Admin Web UI enforces the output boundary: all backend content is rendered as escaped plaintext or DOMPurify-sanitized content — never `innerHTML`; CSP headers and httpOnly cookies prevent XSS; no secrets or raw legal payloads in browser storage.
4. Lawyer-facing Web chat promotes existing `web_sse` ChannelAdapter from fixture-grade to production with real SSE transport and RBAC session auth (lawyer role); provides session list, message history, file upload, feedback submission, and multi-device sync via server-side sessions.
5. Lawyer Web chat enforces the same output boundary as WeCom — no backend notices (gateway/meta/system/update/command) reach the lawyer; `web_sse_channel_enabled` defaults to `False`.

**Plans:** TBD

## v1.7 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 45. M3 Pre-Implementation Safety | 0/0 | Not Started | — |
| 46. Streaming Events (A1) | 0/0 | Not Started | — |
| 47. Artifact Return (A2) | 0/0 | Not Started | — |
| 48. Multi-Provider Runners (A3) | 0/0 | Not Started | — |
| 49. Session Memory Wiring (A4) | 0/0 | Not Started | — |
| 50. MCP Connector Registry (B1) | 0/0 | Not Started | — |
| 51. RBAC (C1) | 0/0 | Not Started | — |
| 52. Skill Registry Write (B2) | 0/0 | Not Started | — |
| 53. Hybrid Routing (B3) | 0/0 | Not Started | — |
| 54. Model Provider Gateway (B4) | 0/0 | Not Started | — |
| 55. Multi-Agent Runtime Adapter (B5) | 0/0 | Not Started | — |
| 56. Multi-Tenant Isolation (C2) | 0/0 | Not Started | — |
| 57. Admin Web UI + Lawyer Web Chat (C3+C4) | 0/0 | Not Started | — |

## v1.7 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFETY-01 | 45 | Pending |
| SAFETY-02 | 45 | Pending |
| SAFETY-03 | 45 | Pending |
| SAFETY-04 | 45 | Pending |
| SAFETY-05 | 45 | Pending |
| STREAM-01 | 46 | Pending |
| STREAM-02 | 46 | Pending |
| ARTIFACT-01 | 47 | Pending |
| ARTIFACT-02 | 47 | Pending |
| MULTIPROV-01 | 48 | Pending |
| MULTIPROV-02 | 48 | Pending |
| MULTIPROV-03 | 48 | Pending |
| SESSMEM-01 | 49 | Pending |
| MCP-01 | 50 | Pending |
| MCP-02 | 50 | Pending |
| MCP-03 | 50 | Pending |
| RBAC-01 | 51 | Pending |
| RBAC-02 | 51 | Pending |
| RBAC-03 | 51 | Pending |
| SKILLWRITE-01 | 52 | Pending |
| SKILLWRITE-02 | 52 | Pending |
| SKILLWRITE-03 | 52 | Pending |
| HYBRID-01 | 53 | Pending |
| HYBRID-02 | 53 | Pending |
| HYBRID-03 | 53 | Pending |
| GATEWAY-01 | 54 | Pending |
| GATEWAY-02 | 54 | Pending |
| GATEWAY-03 | 54 | Pending |
| GATEWAY-04 | 54 | Pending |
| MULTIAGENT-01 | 55 | Pending |
| MULTIAGENT-02 | 55 | Pending |
| MULTIAGENT-03 | 55 | Pending |
| TENANT-01 | 56 | Pending |
| TENANT-02 | 56 | Pending |
| TENANT-03 | 56 | Pending |
| TENANT-04 | 56 | Pending |
| ADMINUI-01 | 57 | Pending |
| ADMINUI-02 | 57 | Pending |
| ADMINUI-03 | 57 | Pending |
| LAWCHAT-01 | 57 | Pending |
| LAWCHAT-02 | 57 | Pending |
| LAWCHAT-03 | 57 | Pending |

**v1.7 Coverage: 42/42 requirements mapped (100%)**

## Archived: v1.6 M2 Multi-Backend & Platform Extensions

**Goal:** Extend the platform beyond Hermes-only by proving agent-backend-neutral contracts (Codex + provider_model prototypes), normalizing routing as an independent service, exposing skill metadata and operational read views, completing conversation-read-view, and adding a second channel (QQBot) to prove ChannelAdapter portability — while keeping all existing V2 gates green and V2 human-gate evidence stable.

**Requirements:** `.planning/milestones/v1.6-REQUIREMENTS.md`

### v1.6 Phases

- [x] **Phase 36: M2 Pre-Implementation Safety** - Cross-cutting safety measures (selection gate bypass fix, contract freeze, privacy scrub unification, feature flags, output boundary rules) before any M2 feature code.
- [x] **Phase 37: Skill Registry Read** - Read-only Skill Registry exposing Hermes skill metadata as NeutralSkillDescriptor records with list/get/search and well-known discovery endpoint.
- [x] **Phase 38: Router Service** - Standalone router library injected into hermes-contract-layer mapper, producing RouteDecision events with RULE and SKILL routing modes.
- [x] **Phase 39: Codex Adapter Prototype** - Codex backend adapter proving BackendAdapter contract portability via codex exec subprocess with manifest validation and minimal submit_run flow.
- [x] **Phase 40: Provider Model Adapter Prototype** - Direct provider_model adapter via AsyncOpenAI lazy SDK import, plus output boundary fixture tests for both new backends.
- [x] **Phase 41: Conversation Read-View Completion** - Cursor-based pagination, time-range/dimension filters, trace reconstruction, CSV/JSON export, and read-time privacy scrubbing.
- [x] **Phase 42: Admin Console API** - Read-only Admin Console API with static token auth, sessions/tasks/feedback/gates/health views, and field allowlist excluding secrets.
- [x] **Phase 43: QQBot Channel Loop** - Channel-generic logic extraction, QQBot ChannelAdapter implementation, and fixture-driven receive→ACK→adapter→reply→card→feedback loop proof.
- [x] **Phase 44: M2 Gate Integration & Full Suite Verification** - New gates for all 6 M2 packages, meta-test for full directory coverage, and all existing gates verified green.

### v1.6 Status

**Status:** COMPLETE — all 9 phases shipped (36-44), 22/22 requirements satisfied, 19/19 V2 gates green (969 tests).

**Full archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

## Archived: v1.5 V2 Acceptance Closure

**Goal:** Audit all unchecked V2 Active requirements against the actual codebase, close every code gap found, mark validated requirements in PROJECT.md, and produce a final V2 acceptance readiness report so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain before V2 is formally accepted.

**Requirements:** `.planning/milestones/v1.5-REQUIREMENTS.md`

### v1.5 Phases

- [x] **Phase 33: V2 Requirement Audit & Traceability Infrastructure** - Build deterministic audit tooling that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied/partial/gap/human_gate.
- [x] **Phase 34: V2 Code Gap Closure** - Close every genuine code gap identified by the audit in existing services/packages with tests, keeping all V2 gate suites green.
- [x] **Phase 35: V2 Acceptance Readiness Report & Traceability Update** - Update PROJECT.md traceability honestly and produce the final V2 acceptance readiness report with human-gate documentation.

### v1.5 Status

**Status:** COMPLETE — all 3 phases shipped (33-35), 23/23 requirements satisfied, 479 tests green.

### v1.5 Phase Details

#### Phase 33: V2 Requirement Audit & Traceability Infrastructure

**Goal:** Operator can run a deterministic audit that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied, partial, gap, or human_gate using three-level verification.
**Depends on:** v1.4 completion (Phase 32)
**Requirements:** AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06, AUDIT-07
**Success Criteria** (what must be TRUE):

1. Operator runs `scripts/audit_v2_requirements.py` and receives a complete requirement-to-code traceability matrix with file paths, test modules, gate names, and schema IDs for each unchecked V2 Active requirement, reproducible across runs.
2. Operator can inspect a per-requirement evidence bundle showing which files implement each requirement, which tests cover it, which gate suite proves it, and which fixtures exercise it.
3. Each unchecked requirement is classified as `satisfied`, `partial`, `gap`, or `human_gate` using three-level verification (schema definition → library surface → production wiring path), preventing the false-positive pattern seen in v1.4 MEM-07/MEM-16.
4. CI runs a 9th V2 gate (`v2-acceptance-traceability`) that fails when any requirement is `status: gap` or evidence is missing.
5. Operator can read a machine-readable JSON traceability sidecar (`acceptance/v2-traceability.json`) and a PRD §10 criterion-to-test mapping showing which specific tests and fixtures prove each §10.1–10.4 acceptance criterion.

**Plans:** TBD

#### Phase 34: V2 Code Gap Closure

**Goal:** Every genuine code gap identified by the Phase 33 audit is closed in-place with tests, and all existing V2 gate suites pass green with no regressions.
**Depends on:** Phase 33
**Requirements:** GAP-01, GAP-02, GAP-03, GAP-04, GAP-05, GAP-06, GAP-07, GAP-08, GAP-09
**Success Criteria** (what must be TRUE):

1. All genuine code gaps identified by the audit in WeCom service (receive/send, ACK, normalization, delivery, feedback callbacks, idempotency, retry, output policy), assistant output boundary, feedback normalization, conversation-read-view, CI composability, and observability/replay/privacy baselines are closed with tests.
2. All 7 existing V2 gate suites (424+ tests) pass green after gap closure with no regressions.
3. Operator can view a composability fixture coverage report showing which §10.3 synthetic task types are covered by fixtures and which are missing.
4. Operator can view a privacy/output-boundary fixture evidence summary proving gateway/update/command/meta samples are blocked or rewritten per §10.2.

**Plans:** TBD

#### Phase 35: V2 Acceptance Readiness Report & Traceability Update

**Goal:** Operator can read a final V2 acceptance readiness report and updated PROJECT.md traceability that honestly distinguishes autonomous code closure from remaining human gates.
**Depends on:** Phase 34
**Requirements:** DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07
**Success Criteria** (what must be TRUE):

1. PROJECT.md Active requirements are updated — validated requirements move to Validated with phase references and stale sections are updated, while human-gate requirements (Phase 5 live WeCom UAT, Phase 8 five-workday lawyer trial) remain unchecked until real evidence exists.
2. Operator can read a V2 acceptance readiness report (`.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`) mirroring PRD §10.1–10.4 structure with satisfied criteria, closed gaps, and remaining human gates.
3. Operator can read Phase 5 live WeCom UAT documentation (pre-UAT fixture evidence summary, operator checklist, pass/fail criteria) and Phase 8 five-workday lawyer trial documentation (trial protocol, metric-collection template, §10.4 thresholds, trial-log template).
4. The readiness report uses a two-tier status model (autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES) and classifies each V2-PRD §13 residual risk as source-resolved, implementation-resolved, or live-evidence-pending.

**Plans:** TBD

### v1.5 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 33. V2 Requirement Audit & Traceability Infrastructure | 1/1 | Complete | 2026-07-03 |
| 34. V2 Code Gap Closure | 1/1 | Complete | 2026-07-03 |
| 35. V2 Acceptance Readiness Report & Traceability Update | 1/1 | Complete | 2026-07-03 |

### v1.5 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | 33 | Complete |
| AUDIT-02 | 33 | Complete |
| AUDIT-03 | 33 | Complete |
| AUDIT-04 | 33 | Complete |
| AUDIT-05 | 33 | Complete |
| AUDIT-06 | 33 | Complete |
| AUDIT-07 | 33 | Complete |
| GAP-01 | 34 | Complete |
| GAP-02 | 34 | Complete |
| GAP-03 | 34 | Complete |
| GAP-04 | 34 | Complete |
| GAP-05 | 34 | Complete |
| GAP-06 | 34 | Complete |
| GAP-07 | 34 | Complete |
| GAP-08 | 34 | Complete |
| GAP-09 | 34 | Complete |
| DOC-01 | 35 | Complete |
| DOC-02 | 35 | Complete |
| DOC-03 | 35 | Complete |
| DOC-04 | 35 | Complete |
| DOC-05 | 35 | Complete |
| DOC-06 | 35 | Complete |
| DOC-07 | 35 | Complete |

**v1.5 Coverage: 23/23 requirements mapped (100%)**
