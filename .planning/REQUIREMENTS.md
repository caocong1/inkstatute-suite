# Milestone v1.6: M2 Multi-Backend & Platform Extensions — Requirements

**Defined:** 2026-07-03
**Milestone:** v1.6 M2 Multi-Backend & Platform Extensions
**Goal:** Extend the platform beyond Hermes-only by proving agent-backend-neutral contracts (Codex + provider_model prototypes), normalizing routing as an independent service, exposing skill metadata and operational read views, completing conversation-read-view, and adding a second channel (QQBot) to prove ChannelAdapter portability — while keeping all 9 existing V2 gates green and V2 human-gate evidence stable.

## Requirements

### Pre-Implementation Safety (SAFETY)

- [ ] **SAFETY-01**: Operator can verify that `select_agent_backend` enforces `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready` metadata, preventing prototype adapters from serving live WeCom turns during V2 human gates.
- [ ] **SAFETY-02**: Operator can run a contract-count assertion test that fails if `BackendAdapter` Protocol method count, `AdapterCapabilitySet` field count, or `ChannelAdapter` Protocol method count changes from the v1.5 baseline, preventing contract drift during M2.
- [ ] **SAFETY-03**: Operator can verify that `_FORBIDDEN_FULL_TEXT_KEYS` is unified between `store.py` and `privacy.py`, includes new backend field names (`prompt_content`, `completion_text`, `function_call_result`, `tool_output`), and that `scrub_contract_payload` is applied to every API response path.
- [ ] **SAFETY-04**: Operator can verify that all M2 feature flags (`router_service_enabled`, `skill_registry_enabled`, `admin_api_enabled`, `qqbot_channel_enabled`, `codex_backend_enabled`, `provider_model_backend_enabled`) default to `False` in `RuntimeFeatureFlags`.
- [ ] **SAFETY-05**: Operator can run output boundary fixture tests proving provider/model name leakage, API error messages, and rate-limit notices are blocked or rewritten for each new backend.
- [ ] **SAFETY-06**: Operator can run a "contract freeze" baseline hash test comparing `packages/platform-contract/` schema files against the v1.5 baseline, failing if any schema file is modified during the V2 human gate period.

### Multi-Backend Adapters (ADAPTER)

- [x] **ADAPTER-01**: Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `codex exec --json` subprocess.
- [ ] **ADAPTER-02**: Operator can configure `agent_backend.mode=provider_model` and the runtime selector routes to a direct provider_model adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `AsyncOpenAI` lazy SDK import.
- [ ] **ADAPTER-03**: Operator can run output boundary fixture tests proving Codex and provider_model backend noise (function call traces, model names, API errors) is blocked or rewritten before delivery to any channel.

### Router Service (ROUTER)

- [ ] **ROUTER-01**: Operator can inject a standalone router library into `hermes-contract-layer/mapper.py` that produces `RouteDecision` events with the same JSONL shape as the inline implementation, with a `None` default that preserves in-process fallback behavior.
- [ ] **ROUTER-02**: Operator can configure `RouteMode.RULE` and `RouteMode.SKILL` routing modes in the router service, with stateless skill lookup from the Skill Registry and intent classification via keyword/regex, producing normalized `RouteDecision` records.

### Skill Registry (SKILL)

- [ ] **SKILL-01**: Operator can query a read-only Skill Registry that exposes Hermes skill metadata as `NeutralSkillDescriptor` records with `list_skills`, `get_skill`, and `search` operations (filter by tag, category, name substring).
- [ ] **SKILL-02**: Operator can fetch `/.well-known/agent-skills/index.json` from the Skill Registry exposing skill name, description, and URL for discovery per the Cloudflare agent-skills-discovery convention.

### Conversation Read-View (READVIEW)

- [ ] **READVIEW-01**: Operator can query `conversation-read-view` with cursor-based pagination, time-range filters (`from`, `to`), and dimension filters (`user_id`, `channel`, `status`) on list endpoints, with enforced max result limits.
- [ ] **READVIEW-02**: Operator can query `conversation-read-view` by `trace_id` and receive all related events (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent) reconstructed in occurrence order.
- [ ] **READVIEW-03**: Operator can export conversation-read-view query results as CSV or JSON, and verify that all new endpoints apply read-time privacy scrubbing to response payloads.

### Admin Console API (ADMIN)

- [ ] **ADMIN-01**: Operator can authenticate to a read-only Admin Console API via a static token from env, and query sessions, tasks, feedback, gates, and health views with filtering and pagination.
- [ ] **ADMIN-02**: Operator can verify that Admin Console API health/status views use a field allowlist that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values.

### QQBot Channel (QQBOT)

- [ ] **QQBOT-01**: Operator can verify that channel-generic logic (idempotency, delivery guard, active task router, output policy) is extracted from `wecom-service` into a shared package, and that QQBot does not import directly from `wecom_service`.
- [ ] **QQBOT-02**: Operator can configure `channel=qqbot` and the runtime routes to a QQBot channel adapter that implements `ChannelAdapter` Protocol (6 methods), handles receive (single mode), send (text), and callback verification.
- [ ] **QQBOT-03**: Operator can run a fixture-driven QQBot loop proof showing receive → ACK → adapter → reply → card → FeedbackEvent end-to-end with idempotency, proving ChannelAdapter portability beyond WeCom.

### Gate Safety (GATE)

- [ ] **GATE-01**: Operator can run a V2 gate suite that includes new gates for each M2 package/service (codex, provider_model, router-service, skill-registry, admin-console-api, qqbot), with all 9 existing gates staying green and a meta-test asserting every `packages/*/src` and `services/*/src` directory is covered by a gate.

## Future Requirements (Deferred to M3+)

- Streaming event support for Codex/provider_model adapters
- Artifact return support for adapters
- Session memory support for adapters (Hindsight integration)
- Multi-provider support for provider_model adapter (Anthropic, Ollama)
- Model-based and hybrid routing with confidence scoring
- Route mismatch detection and feedback learning
- Skill Registry write operations (publish, update, delete)
- Skill usage statistics and health status
- Full-text search across conversations
- Refined view with outcome classification
- OTEL trace correlation
- Admin Console metrics aggregation, alerting, audit log
- QQBot dual receive mode (webhook + WebSocket)
- QQBot rich media (voice, video, stickers), group @mention, scheduled push, STT/TTS

## Out of Scope

- Production cutover for Codex, provider_model, or QQBot — M2 delivers prototypes proving contract portability, not production-ready backends/channels. Live promotion remains a human gate.
- V2 human gate execution (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) — these run in parallel with M2 but are not M2 deliverables. M2 must not invalidate V2 human gate evidence.
- Rebuilding Hermes core, session storage, router, skill registry, MCP registry, or model gateway — M2 extends the platform around Hermes, not forks it.
- New independent authoritative conversation database — M2 read views derive from contract logs, with Hermes sessions only as a fallback adapter.
- Automatic legal skill synthesis or modification — Skill Registry is read-only; `skill_candidate` remains human-reviewed.
- Storing raw customer legal payloads in contract logs — logs prefer references and minimized sensitive data.
- M3 scope: Multi-Agent Runtime Adapter productization, MCP Connector Registry, Model Provider Gateway, Web UI, security/compliance system (data residency, encryption, multi-tenant, RBAC, retention/destruction).

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SAFETY-01 | 36 | Not started |
| SAFETY-02 | 36 | Not started |
| SAFETY-03 | 36 | Not started |
| SAFETY-04 | 36 | Not started |
| SAFETY-05 | 36 | Not started |
| SAFETY-06 | 36 | Not started |
| ADAPTER-01 | 39 | Not started |
| ADAPTER-02 | 40 | Not started |
| ADAPTER-03 | 40 | Not started |
| ROUTER-01 | 38 | Not started |
| ROUTER-02 | 38 | Not started |
| SKILL-01 | 37 | Not started |
| SKILL-02 | 37 | Not started |
| READVIEW-01 | 41 | Not started |
| READVIEW-02 | 41 | Not started |
| READVIEW-03 | 41 | Not started |
| ADMIN-01 | 42 | Not started |
| ADMIN-02 | 42 | Not started |
| QQBOT-01 | 43 | Not started |
| QQBOT-02 | 43 | Not started |
| QQBOT-03 | 43 | Not started |
| GATE-01 | 44 | Not started |
