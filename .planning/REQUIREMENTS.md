# Requirements: 墨律 InkStatute V2

**Defined:** 2026-07-05
**Core Value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

## v1.7 M3 Platform Extensions Requirements

Requirements for M3 milestone. Each maps to roadmap phases (45+).

### Adapter Productization

- [ ] **STREAM-01**: Codex + provider_model adapters yield SSE streaming events via frozen `stream_events()` with guaranteed terminal event (completed/failed/cancelled)
- [ ] **STREAM-02**: Client cancellation propagates through runtime → adapter → provider with `aclose()` cleanup (no zombie runs)
- [ ] **ARTIFACT-01**: Adapters return artifacts via frozen `collect_artifacts()` + `AgentResult.artifacts` with ref-based schema (`content_ref`, `sha256`, `size_bytes` — never inline binaries)
- [ ] **ARTIFACT-02**: Artifacts enforce output boundary (backend noise filtered from artifact metadata)
- [ ] **SESSMEM-01**: Runtime wires existing `HindsightMemory` + `MemoryOrchestrator` as optional deps; adapters declare `session_memory_support=True` and consume `ContextBundle` (never call Hindsight directly)
- [ ] **MULTIPROV-01**: `AnthropicRunner` implements `ProviderRunner` Protocol with Messages API normalization (system as top-level param, content blocks, thinking tokens)
- [ ] **MULTIPROV-02**: `OllamaRunner` implements `ProviderRunner` Protocol for local models via OpenAI-compatible endpoint
- [ ] **MULTIPROV-03**: Multi-provider error normalization reuses v1.6 `ErrorInfo`/`ErrorCategory` pattern

### Platform Extensions

- [ ] **MCP-01**: MCP Connector Registry (`packages/mcp-registry/`) implements read-only `McpRegistryPort` (list_servers, get_server, search) with cursor pagination
- [ ] **MCP-02**: MCP registry supports registration with JSON Schema tool schemas, versioning, and soft-delete
- [ ] **MCP-03**: Router joins skill `required_tool_refs` → MCP `capability_refs` at read time
- [ ] **GATEWAY-01**: Model Provider Gateway (`packages/model-gateway/`) is a composite `BackendAdapter` wrapping multiple provider_model sub-adapters
- [ ] **GATEWAY-02**: Gateway enforces per-tenant/provider rate limiting (RPM/TPM/concurrency) via token-bucket
- [ ] **GATEWAY-03**: Gateway implements fallback chains with circuit breakers and tried-provider tracking
- [ ] **GATEWAY-04**: Gateway tracks per-tenant/matter cost with budget ceilings
- [ ] **MULTIAGENT-01**: Multi-Agent Runtime Adapter is a composite `BackendAdapter` delegating by `solution.backend_id`
- [ ] **MULTIAGENT-02**: Multi-agent supports sequential/parallel/supervisor orchestration with `max_handoffs=5` and cycle detection
- [ ] **MULTIAGENT-03**: Multi-agent shared state scoped to `parent_run_id` with copy-on-write isolation
- [ ] **SKILLWRITE-01**: `SkillRegistryWritePort` + `WritableSkillRegistry` implements CRUD with immutable versioning and rollback
- [ ] **SKILLWRITE-02**: Skill write requires human-review record on every write path (two-person rule for legal skills — no auto-promotion)
- [ ] **SKILLWRITE-03**: Skill write enforces per-tenant skill namespaces (no cross-tenant skill leakage)
- [ ] **HYBRID-01**: `RouterStrategy.HYBRID` implements Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5)
- [ ] **HYBRID-02**: Legal-risk classifier forces high-risk queries to Hermes regardless of confidence score
- [ ] **HYBRID-03**: `RouteDecision.confidence` populated for all hybrid routing decisions

### Operator & UX Layer

- [ ] **ADMINUI-01**: Admin Web UI (`services/admin-web-ui/`) renders operator dashboard with session/task inspection, feedback review queue, gate status, health monitoring
- [ ] **ADMINUI-02**: Admin Web UI consumes existing `admin-console-api` read endpoints + new read route branches
- [ ] **ADMINUI-03**: Admin Web UI enforces output boundary (all backend content rendered as escaped plaintext or DOMPurify-sanitized — never `innerHTML`)
- [ ] **LAWCHAT-01**: Lawyer-facing Web chat promotes existing `web_sse` ChannelAdapter from fixture-grade to production (real SSE + session auth)
- [ ] **LAWCHAT-02**: Lawyer Web chat provides session list, message history, file upload, feedback submission, multi-device sync
- [ ] **LAWCHAT-03**: Lawyer Web chat enforces same output boundary as WeCom (no backend notices)

### Security & Compliance

- [ ] **RBAC-01**: `packages/rbac/` implements 4 roles (admin/operator/lawyer/viewer) with permissions matrix and `RbacGuard` middleware
- [ ] **RBAC-02**: RBAC enforces default-deny with CI scan for unannotated endpoints
- [ ] **RBAC-03**: RBAC token-based auth with role+tenant claims (short-lived tokens)
- [ ] **TENANT-01**: `TenantScopeResolver` + `TenantGuard` injects `tenant_id` filter into every read-model query
- [ ] **TENANT-02**: Contract logs partitioned by `tenant_id`/`workspace_id` path
- [ ] **TENANT-03**: Cache keys namespaced by `tenant_id`; Hindsight bank isolation enforced per tenant
- [ ] **TENANT-04**: Migration test asserts no null `tenant_id` in tenant-scoped entities

### Safety & Gates (cross-cutting)

- [ ] **SAFETY-01**: All 9 new feature flags default `False` (`session_memory_enabled`, `mcp_registry_enabled`, `model_gateway_enabled`, `multi_agent_enabled`, `skill_registry_write_enabled`, `hybrid_routing_enabled`, `web_sse_channel_enabled`, `rbac_enabled`, `multi_tenant_enabled`)
- [ ] **SAFETY-02**: No frozen Protocol modified (`BackendAdapter` 9 methods, `ChannelAdapter` 6 methods, `RouterPort.decide`, `SkillRegistryPort` 3 read methods)
- [ ] **SAFETY-03**: All 19 V2 gates stay green throughout M3 (969+ tests, no regressions)
- [ ] **SAFETY-04**: Flag-default test added alongside every new feature flag
- [ ] **SAFETY-05**: V2 human gates (Phase 5 + Phase 8) run against V2 baseline without M3 contamination

## Future Requirements (deferred to M4+)

### Encryption & Retention (M4)

- **ENCRYPT-01**: Encryption at rest for contract logs and artifact store
- **ENCRYPT-02**: Encryption in transit for all inter-service communication
- **RETENTION-01**: Retention policy with per-tenant configurable retention periods
- **RETENTION-02**: Destruction policy with audit trail for legal data deletion

### QQBot Extensions (M4+)

- **QQBOT-EXT-01**: QQBot dual receive mode (webhook + WebSocket)
- **QQBOT-EXT-02**: QQBot rich media support (images, files, cards)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Encryption at rest / retention-destruction automation | Deferred to M4 per PROJECT.md — M3 covers RBAC + multi-tenant only |
| QQBot dual receive mode + rich media | Deferred to M4 — QQBot loop proven in v1.6, extensions not M3 priority |
| Tauri desktop app | Not part of V2 acceptance — web-first delivery |
| WeChat complete V2 loop | Not part of V2 acceptance — WeCom is the acceptance channel |
| Auto-synthesizing legal skills from streamed outputs | Violates legal safety invariant — high-risk feedback stays human-reviewed |
| Inline raw document content in stream events / artifacts | Violates `raw_payload_ref` privacy discipline — refs only in contract events |
| Direct Hindsight calls from adapters | Adapters consume `ContextBundle`, never call memory providers directly |
| Auto-MCP-execution on registration | MCP connectors require admission review before execution |
| Gateway auto-downgrade for legal tasks | Legal-risk classifier forces high-risk queries to Hermes regardless of cost |
| Pure-LLM routing without rule fallback | Hybrid routing always has Rule → Skill → Model cascade, never LLM-only |
| Global admin bypassing tenant isolation | All roles scoped to `tenant_id` — no global bypass |
| Client-side-only RBAC enforcement | RBAC enforced at middleware layer (server-side), client is advisory only |
| Rebuilding Hermes core / session storage / router | V2 calls Hermes as agent backend, not a fork |
| PostgreSQL RLS / schema-per-tenant | Platform uses JSONL contract logs, not a relational DB (PRD §1.2) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STREAM-01 | TBD | Pending |
| STREAM-02 | TBD | Pending |
| ARTIFACT-01 | TBD | Pending |
| ARTIFACT-02 | TBD | Pending |
| SESSMEM-01 | TBD | Pending |
| MULTIPROV-01 | TBD | Pending |
| MULTIPROV-02 | TBD | Pending |
| MULTIPROV-03 | TBD | Pending |
| MCP-01 | TBD | Pending |
| MCP-02 | TBD | Pending |
| MCP-03 | TBD | Pending |
| GATEWAY-01 | TBD | Pending |
| GATEWAY-02 | TBD | Pending |
| GATEWAY-03 | TBD | Pending |
| GATEWAY-04 | TBD | Pending |
| MULTIAGENT-01 | TBD | Pending |
| MULTIAGENT-02 | TBD | Pending |
| MULTIAGENT-03 | TBD | Pending |
| SKILLWRITE-01 | TBD | Pending |
| SKILLWRITE-02 | TBD | Pending |
| SKILLWRITE-03 | TBD | Pending |
| HYBRID-01 | TBD | Pending |
| HYBRID-02 | TBD | Pending |
| HYBRID-03 | TBD | Pending |
| ADMINUI-01 | TBD | Pending |
| ADMINUI-02 | TBD | Pending |
| ADMINUI-03 | TBD | Pending |
| LAWCHAT-01 | TBD | Pending |
| LAWCHAT-02 | TBD | Pending |
| LAWCHAT-03 | TBD | Pending |
| RBAC-01 | TBD | Pending |
| RBAC-02 | TBD | Pending |
| RBAC-03 | TBD | Pending |
| TENANT-01 | TBD | Pending |
| TENANT-02 | TBD | Pending |
| TENANT-03 | TBD | Pending |
| TENANT-04 | TBD | Pending |
| SAFETY-01 | TBD | Pending |
| SAFETY-02 | TBD | Pending |
| SAFETY-03 | TBD | Pending |
| SAFETY-04 | TBD | Pending |
| SAFETY-05 | TBD | Pending |

**Coverage:**
- v1.7 requirements: 38 total
- Mapped to phases: 0
- Unmapped: 38 ⚠️ (to be filled by roadmapper)

---
*Requirements defined: 2026-07-05*
*Last updated: 2026-07-05 after M3 requirement definition*
