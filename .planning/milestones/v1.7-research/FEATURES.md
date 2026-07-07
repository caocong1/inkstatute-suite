# Feature Research: M3 Platform Extensions

**Domain:** M3 Platform Extensions — adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant
**Researched:** 2026-07-05
**Confidence:** HIGH

## Scope Note

This research covers **M3-specific features only** — the new capabilities planned for milestone v1.7 M3 Platform Extensions. Existing v1.0–v1.6 features (WeCom service, Hermes adapter, platform contracts, feedback service, conversation-read-view, Admin Console API read-only, QQBot channel, Hindsight long-term memory, contract test suite, 19 V2 gates) are already shipped and explicitly out of scope for re-research.

M3 target features from PROJECT.md (lines 17–40):
1. Adapter productization — streaming events, artifact return, session memory (Hindsight integration), multi-provider support (Anthropic, Ollama) for Codex + provider_model adapters
2. Platform extensions — MCP Connector Registry, Model Provider Gateway, Multi-Agent Runtime Adapter, Skill Registry write, model-based + hybrid routing with confidence scoring
3. Operator & UX layer — Admin console Web UI, Lawyer-facing Web chat
4. Security & compliance (scoped) — RBAC, multi-tenant isolation (encryption + retention deferred to M4)

Research sources: MCP Registry spec (modelcontextprotocol.io), OpenAI Agents SDK docs, LangGraph/AutoGen/CrewAI orchestration patterns, LLM gateway patterns (TrueFoundry, Lushbinary, Atlan), confidence-gated routing (reaatech/confidence-router, Automatos Universal Router, Meganova 3-tier cascade), WorkOS/AWS multi-tenant RBAC guidance, Anthropic/Ollama API compatibility docs.

---

## Adapter Productization

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Token streaming via SSE | Production agent platforms (LangChain Agent Protocol, OpenAI Agents SDK, A2A/MCP) converge on SSE over HTTP for streaming. Both Anthropic Messages API and Ollama support SSE token streaming. Without streaming, long legal drafting tasks appear hung. InkStatute's Hermes adapter already has a `stream_events()` stub (`packages/backends/hermes/adapter.py` lines 148–156). | MODERATE | Event-typed lifecycle: `run.started`, `token.delta`, `tool.call`, `tool.result`, `progress`, `run.completed`, `run.error`, `run.cancelled`. Must emit explicit terminal event always (so frontend distinguishes "ended" vs "cut off"). Adapters translate provider-native stream chunks (Anthropic `content_block_delta`, Ollama `message` chunks) into neutral `StreamEvent` records. |
| Cancellation propagation | SSE streaming reference architectures use a separate REST endpoint for cancellation when using EventSource. Agent runtimes (OpenAI Agents SDK, LangGraph) support `cancel()` on running tasks. InkStatute contract already has `cancel_run()` in the BackendAdapter Protocol. | MODERATE | Cancellation must propagate from client → platform-runtime → adapter → provider. Provider cancellation: Anthropic has no native cancel (must close stream), Ollama supports in-flight abort. Adapter must emit `run.cancelled` terminal event and clean up subprocess resources (Codex CLI subprocess kill). |
| Progress events for long tasks | Agent platforms emit progress/heartbeat events for multi-step tasks (tool calls, sub-agent handoffs). Required for UX so users don't assume a hung task. | LOW | Reuse existing `ExecutionTrace` records as progress signals. Adapter emits `progress` events with `step_id`, `description`, `estimated_remaining` (optional). |
| Artifact return (files, images, structured data) | OpenAI Agents SDK defines `ToolOutputImage`, `ToolOutputFileContent`, `ToolOutputText` for rich tool outputs. Hermes adapter already has `collect_artifacts()` stub (line 206–208). Production legal agents must return drafted documents (PDF/DOCX), extracted clause tables (structured JSON), and preview images. | MODERATE | Neutral `Artifact` schema: `artifact_id`, `type` (file/image/structured), `media_type`, `filename`, `content_ref` (URL or base64 data ref — never inline large binaries in contract events per privacy rules), `sha256`, `size_bytes`. Adapters map provider-native outputs (Anthropic tool_result blocks, Codex CLI stdout files, Ollama text) to this schema. |
| Session memory integration with Hindsight | InkStatute already has Hindsight long-term memory (`packages/platform-runtime/src/platform_runtime/hindsight_memory.py`) with `aretain/arecall/areflect`, focus/retention policies, retry/observability. Contract has `session_memory_support` flag. Adapters must be able to load session context via Hindsight before run and persist run outcomes after. | MODERATE | Adapter receives `AgentTurn` with `session_id` → platform-runtime loads Hindsight memories (arecall with focus policy) → injects as context → after run, adapter emits `AgentResult` → platform-runtime aretains summary + areflects. Adapter itself should NOT call Hindsight directly (keeps memory provider in platform-runtime per v1.4 singleton wiring decision). |
| Multi-provider support (Anthropic Claude) | provider_model adapter prototype uses `AsyncOpenAI`. Anthropic Messages API differs in: message format (system as top-level param, not message role), streaming (`content_block_delta` events), tool calling (tool_use/tool_result blocks), thinking tokens (`thinking` content blocks), max_tokens is required not optional. | MODERATE | Adapter must normalize Anthropic-native shapes to neutral `AgentResult`. Use Anthropic SDK (`anthropic.AsyncAnthropic`) with lazy import inside adapter package only (two-file rule from v1.6). Provider-specific quirks (thinking blocks, system prompt position) isolated in adapter. |
| Multi-provider support (Ollama local) | Ollama exposes OpenAI-compatible `/v1/chat/completions` endpoint AND native `/api/chat`. Local models (Llama, Qwen) lack tool-calling reliability vs frontier models. Latency is local (no network) but throughput bounded by GPU. | MODERATE | Ollama adapter can reuse OpenAI-compatible client pointed at `OLLAMA_BASE_URL`. Key differences: no rate limits (local), model availability depends on local `ollama pull`, streaming chunk format slightly different, tool calling support varies by model. Useful for privacy-sensitive legal drafts (no data leaves tenant). |
| Error normalization across providers | Each provider has distinct error shapes (Anthropic: `overloaded_error`, `api_error`; Ollama: HTTP 500 with `error` field; Codex CLI: exit codes). v1.6 already requires mapping to `ErrorInfo` with `ErrorCategory` enum. | LOW | Reuse v1.6 error normalization pattern. Add provider-specific error code maps in each adapter. `retryable` flag drives gateway fallback decisions. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Partial result return on cancellation | Most platforms discard partial output on cancel. Returning the partial draft (e.g., half-completed legal memo) preserves lawyer work. | MODERATE | Adapter captures tokens emitted before cancel → assembles partial `AgentResult` with `status=cancelled` + `content=partial` + `completeness_fraction`. |
| Streaming tool-call visibility | Showing lawyers which tools/MCP connectors the agent is invoking mid-run builds trust. OpenAI Agents SDK surfaces tool calls in streaming; Anthropic surfaces `input_json_delta`. | MODERATE | Emit `tool.call` stream events with tool name + args preview (privacy-scrubbed). Differentiator for legal auditability. |
| Per-provider capability negotiation | Advertise streaming/artifact/tool-calling/vision capabilities per provider in `AdapterCapabilitySet`. Lets gateway route tasks to providers that support required capabilities. | LOW | Extend v1.6 `AdapterCapabilitySet` with `streaming`, `artifacts`, `tool_calling`, `vision`, `thinking` flags. Gateway consults these before routing. |

### Anti-features (legal/safety concerns)

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Auto-synthesizing legal skills from streamed outputs | Same v1.6 rule: V2 records `skill_candidate` but does not auto-modify legal conclusion skills. Streaming must not become a backdoor for auto-skill-creation. | Stream events are display-only; skill write requires human review queue (see Skill Registry write). |
| Inline raw document content in stream events | Privacy rule: contract logs prefer `raw_payload_ref`, must not store sensitive full text. Streaming full document text through contract events violates this. | Stream events carry text deltas for display only; artifacts use `content_ref` (URL/blob ref), not inline base64 in events. |
| Direct Hindsight calls from adapters | v1.4 decided memory provider is a platform-runtime singleton. Adapters calling Hindsight directly would break singleton wiring and observability. | Adapters receive prepared context and emit results; platform-runtime handles aretain/arecall/areflect. |
| Provider credentials in adapter code or config files | Security risk; v1.6 anti-feature carried forward. | Use `secret_refs` in adapter config, resolved from env/runtime secret store at boot. |
| Auto-fallback that hides provider errors from operators | Gateway fallback is good, but silently swallowing errors hides incidents. | Fallback events must be logged with original error; Admin UI surfaces fallback frequency. |

---

## Platform Extensions

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| MCP Connector Registry — registration | MCP Registry spec (modelcontextprotocol.io) defines `server.json` format with name, packages, runtime (args/env), capabilities, version. InkStatute needs a private registry (not the public one) for tenant-scoped MCP connectors. | MODERATE | `ConnectorDescriptor`: `connector_id`, `name`, `version`, `transport` (stdio/sse/http), `command`/`url`, `env_refs`, `capabilities` (tools/resources/prompts), `tool_schemas`, `tenant_id`, `registered_at`, `registered_by`. Registration via Admin API (write — requires RBAC admin role). |
| MCP Connector Registry — discovery | MCP Registry API: `GET /v0.1/servers` with cursor pagination, search, `updated_since` for incremental sync. InkStatute registry must support list/get/search by capability. | LOW | Reuse conversation-read-view cursor pagination pattern. Search by name substring, capability tag, tenant scope. |
| MCP Connector Registry — capability advertising | MCP servers advertise `tools`, `resources`, `prompts` capabilities. Tool schemas (JSON Schema for inputs/outputs) must be stored so router and agents can select connectors. | MODERATE | On registration, registry probes connector (or trusts declared schema) → stores `tool_schemas` as JSON Schema. Router service queries schemas for skill routing. |
| MCP Connector Registry — lifecycle (enable/disable/version) | Production registries support versioning and soft-delete. Connectors can be disabled without unregistering (for incident response). | MODERATE | `status` field (active/disabled/deprecated). Version field per MCP spec. Soft-delete with `deleted_at`. `updated_since` sync support. |
| Model Provider Gateway — routing rules | LLM gateways (TrueFoundry, Lushbinary, Atlan) all provide rule-based routing: by tenant, task type, capability, cost tier. InkStatute gateway sits between router-service and adapters. | MODERATE | `RoutingRule`: `rule_id`, `match` (tenant/task_type/capability_required), `target_provider`, `target_model`, `priority`. Evaluates in priority order. |
| Model Provider Gateway — rate limiting | Production gateways enforce RPM, TPM (tokens-per-minute), cost-per-minute, concurrency per user/team/model (TrueFoundry). Fixed window / sliding window / token bucket strategies. | MODERATE | Per-tenant + per-provider limits. Sliding window for RPM, token bucket for TPM. 429 responses trigger fallback. Limits configurable via Admin API. |
| Model Provider Gateway — fallback chains | Gateways auto-fallback on 429/500/timeout to alternate provider (Atlan, Lushbinary). Turns hard vendor dependency into resilient multi-provider setup. | MODERATE | `FallbackChain`: ordered list of `(provider, model)` tuples. Triggered by `ErrorInfo.retryable=true` or specific error categories. Circuit breaker per provider (consecutive failures → open). |
| Model Provider Gateway — cost tracking | Agentic workloads are highest-cost LLM pattern; budget caps are primary safety mechanism (TrueFoundry). Gateway must track input/output tokens, compute cost per request, enforce daily budgets. | MODERATE | Per-request `CostRecord`: `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `tenant_id`, `task_id`. Aggregated per-tenant daily. Soft/hard budget limits with alert thresholds (50/75/90%). |
| Model Provider Gateway — model selection | Gateway must select model by capability (vision, tool-use, long-context) and cost tier. Provider model registry with pricing + capability metadata. | MODERATE | `ModelDescriptor`: `model_id`, `provider`, `capabilities`, `context_window`, `pricing` (input/output per 1M tokens), `tier` (frontier/standard/local). Gateway matches task requirements to model. |
| Multi-Agent Runtime Adapter — orchestration | OpenAI Agents SDK, AutoGen, CrewAI, LangGraph all support multi-agent orchestration. InkStatute needs an adapter that can run multiple sub-agents (e.g., research agent + drafting agent + citation agent) for complex legal tasks. | COMPLEX | `MultiAgentAdapter` implements BackendAdapter Protocol but internally orchestrates sub-agents. Patterns: sequential (handoff), parallel (fan-out/fan-in), supervisor (coordinator-worker). Must map to neutral `AgentResult`. |
| Multi-Agent Runtime Adapter — handoff | OpenAI Agents SDK: agents delegate via `handoffs` to sub-agents. Handoff = one agent transfers control to another with context. | MODERATE | `HandoffEvent`: `from_agent`, `to_agent`, `context_summary`, `reason`. Recorded in `ExecutionTrace`. Sub-agent runs as nested run with parent `run_id`. |
| Multi-Agent Runtime Adapter — shared state | LangGraph uses typed state channels; AutoGen uses shared context; CrewAI has built-in memory. Multi-agent runs need shared scratchpad. | COMPLEX | `SharedState`: key-value store scoped to `parent_run_id`. Sub-agents read/write. Must respect privacy scrubbing (no raw legal text in shared state without ref). |
| Skill Registry write — CRUD | v1.6 shipped Skill Registry read only. Production requires create/update/delete for skill descriptors. | MODERATE | `create_skill`, `update_skill`, `delete_skill` (soft), `list_revisions`. Write operations require RBAC admin/operator role. |
| Skill Registry write — validation | Skills must be validated before registration (schema, required fields, no duplicate names). | LOW | JSON Schema validation on `NeutralSkillDescriptor`. Reject malformed. Validate `tags`, `category`, `required_tools` references exist. |
| Skill Registry write — versioning | Google Gemini Skill Registry uses `Skill` + `SkillRevision` entities with lifecycle. MCP Registry versions servers. InkStatute must version skills. | MODERATE | Immutable revisions: each update creates new `SkillRevision` with `version`, `created_at`, `created_by`. `current_version` pointer. Rollback = move pointer. |
| Skill Registry write — human review queue for legal skills | v1.6 rule: high-risk legal feedback remains human-reviewed; V2 records `skill_candidate` but does not auto-synthesize legal conclusion skills. Legal skills must go through review queue before going live. | MODERATE | `SkillCandidate` (from feedback) → review queue → human approves/rejects → approved becomes `SkillRevision` in `pending` status → second human gate (operator) promotes to `active`. Two-person rule for legal skills. |
| Model-based routing (LLM-as-router) | Automatos Universal Router Tier 3, Meganova 3-tier cascade, reaatech/confidence-router all use LLM classification as fallback router. LLM receives agent/skill descriptions + user intent → returns selected route + confidence. | MODERATE | Use small/fast model (e.g., Ollama local or Claude Haiku) as router LLM. Prompt includes candidate skills' descriptions + tags. Returns `{skill_id, confidence, reasoning}`. Only fires when rule-based + skill-based routing fall below threshold. |
| Hybrid routing (rule + model) | Meganova 3-tier cascade: Tier 1 rule-based → confidence ≥ 0.8? → route; else Tier 2 semantic → confidence ≥ 0.8? → route; else Tier 3 LLM. Cheapest tier first, escalate only on low confidence. | MODERATE | InkStatute already has RULE + SKILL modes (v1.6 router-service). Add MODEL mode as escalation tier. Cascade: RULE → SKILL → MODEL. Each tier produces `RouteDecision` with `confidence` + `method`. Exit on threshold. |
| Confidence scoring + thresholds | reaatech/confidence-router: `routeThreshold` (0.8), `fallbackThreshold` (0.3), `clarificationEnabled`. Below route threshold but above fallback → ask clarification. Below fallback → human/escalation. | MODERATE | `RouteDecision.confidence` already in contract. Add `route_threshold` (default 0.8, operator-configurable), `clarification_threshold` (default 0.5). Below clarification → return clarification prompt to user instead of routing. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-tenant MCP connector allowlist | Tenants can only use approved connectors (security/compliance). Differentiator for legal vertical. | MODERATE | `ConnectorBinding`: tenant_id → connector_id → status. Router only sees connectors bound to tenant. |
| Gateway cost-budget per matter/client | Legal billing: track LLM cost per matter (case) not just per tenant. Enables cost recovery. | MODERATE | `CostRecord` extended with `matter_id` (optional). Admin UI reports cost-by-matter. |
| Multi-agent trace reconstruction | Show full sub-agent handoff graph in Admin UI. Differentiator for legal auditability. | MODERATE | `ExecutionTrace` extended with `parent_run_id`, `sub_agent_id`. conversation-read-view reconstructs tree. |
| Skill rollback with audit trail | Legal skills need auditable rollback (who approved, who rolled back, why). | LOW | `SkillRevision` + `SkillAuditEvent` (approved/rejected/activated/deactivated/rolled-back). |
| Confidence-based clarification prompts | Instead of routing low-confidence to wrong skill, ask user a clarifying question. reaatech pattern. | MODERATE | When `confidence < clarification_threshold`, router returns `RouteDecision` with `action=clarify` + `clarification_prompt`. Platform-runtime sends prompt to user via channel. |

### Anti-features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Auto-promoting legal skills without human review | v1.6 safety rule. Legal conclusion skills must be human-reviewed. Auto-promotion = unauthorized practice risk. | Two-person rule: feedback → skill_candidate → reviewer approves → operator activates. No auto-activation. |
| MCP connector auto-execution on registration | Security risk: a registered connector could auto-run tools. | Registration only stores metadata; execution requires explicit router/agent invocation with RBAC. |
| Gateway auto-selecting cheapest model regardless of quality | Cost optimization must not silently downgrade legal task quality. | Routing rules can prefer cost but must respect capability requirements. Fallback to cheaper model only on provider failure, not by default for legal tasks. |
| LLM-as-router with no rule fallback | Pure LLM routing is slow + costly + non-deterministic. Meganova cascade shows rule-first is better. | LLM router is always last tier; rule + skill tiers exit first when confident. |
| Multi-agent autonomous skill creation | Sub-agents creating new skills autonomously bypasses human review. | Sub-agents can only emit `skill_candidate` (like feedback); promotion is human-gated. |
| Cross-tenant shared state in multi-agent | Multi-tenant isolation must hold even in multi-agent runs. | `SharedState` scoped to `parent_run_id` which is tenant-scoped; no cross-tenant reads. |

---

## Operator & UX Layer

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Admin Web UI — operator dashboard | v1.6 shipped Admin Console API (read-only). Production operator tools (Langfuse, GNW trace analytics, Microsoft Agent 365) provide Web UI dashboards. InkStatute needs Web UI consuming the existing API. | MODERATE | React/Next.js (or similar) SPA consuming Admin Console API. Dashboard: active sessions, running tasks, recent feedback, gate status, health summary. Reuse existing API field allowlist. |
| Admin Web UI — session/task inspection | Drill-down from dashboard to individual session/task detail. conversation-read-view already supports cursor pagination + filters. | MODERATE | Web views call conversation-read-view API + Admin Console API. Show message history, trace reconstruction, artifacts, feedback linked to session. |
| Admin Web UI — feedback review queue | v1.6 feedback-service produces pending queues. Operators need UI to review, classify, approve/reject skill candidates. | MODERATE | Feedback list view → detail view → approve/reject actions. Write operations require RBAC operator/admin role. Links to skill_candidate review. |
| Admin Web UI — gate status visualization | 19 V2 gates (969 tests) must stay green. Operators need visibility into gate health. | LOW | Gate status panel: per-gate pass/fail, last-run timestamp, test count. Polls CI/gate API. |
| Admin Web UI — health monitoring | Hermes health checks already exist (`bootstrap_check`). Gateway/provider/connector health needed. | LOW | Health panel: per-adapter status, per-provider latency/error rate, MCP connector reachability, Hindsight status. |
| Lawyer-facing Web chat — session list | Lawyers need to see their conversation history across WeCom + Web. | MODERATE | Web chat frontend calls conversation-read-view (scoped to lawyer's tenant + user). Session list with last-message preview, timestamp, status. |
| Lawyer-facing Web chat — message history | Load full message history for a session. conversation-read-view supports this. | LOW | Reuse conversation-read-view API. Render message bubbles, artifacts (file downloads, image previews), feedback cards. |
| Lawyer-facing Web chat — file upload | WeCom supports file delivery; Web chat must too. Uploaded files become artifacts/inputs to agent runs. | MODERATE | Upload → store in tenant-scoped blob storage → create `Artifact` ref → include in `AgentTurn.inputs`. Respect privacy: no raw legal text in contract logs, use `content_ref`. |
| Lawyer-facing Web chat — feedback submission | Lawyers submit feedback (thumbs up/down, text) on assistant replies. v1.6 feedback normalization already exists for WeCom. | LOW | Web feedback → `FeedbackEvent` (same schema as WeCom feedback) → feedback-service. Dedupe + classify same as WeCom. |
| Lawyer-facing Web chat — multi-device | Lawyers switch between WeCom (mobile) and Web (desktop). Sessions must sync. | MODERATE | Sessions are server-side (conversation-read-view is the source of truth, not client). Web and WeCom both read/write same session via platform-runtime. No client-side session state. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Admin UI — cost-by-matter dashboard | Legal billing insight: which matters cost most in LLM usage. | MODERATE | Aggregate `CostRecord` by `matter_id`. Chart top matters by cost. |
| Admin UI — fallback frequency monitor | Shows how often gateway falls back (provider reliability signal). | LOW | Count fallback events per provider. Alert if fallback rate > threshold. |
| Admin UI — routing confidence heatmap | Shows distribution of routing confidence across recent tasks. Reveals ambiguous intents. | LOW | Histogram of `RouteDecision.confidence` by method (rule/skill/model). |
| Lawyer Web chat — streaming token display | Show tokens as they generate (parity with WeCom experience where applicable). | MODERATE | Web chat subscribes to SSE stream from adapter (via platform-runtime). Render token deltas. |
| Lawyer Web chat — artifact preview inline | Preview PDFs/images in chat without download. | MODERATE | Artifact viewer component. PDF.js for PDFs, img tag for images. |
| Lawyer Web chat — multi-agent progress indicator | Show which sub-agent is working (research/drafting/citation). | MODERATE | Consume `progress` stream events. Display step list with status. |

### Anti-features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Admin UI write access to contract logs | Contract logs are append-only evidence. Edit UI would break replayability. | Admin UI is read-only for contract logs; write only for skill registry + feedback review + config. |
| Lawyer Web chat showing backend notices | Same v1.0 output boundary: Hermes gateway/meta/system notices must not leak. | Web chat renders only filtered assistant output (same output boundary as WeCom). |
| Lawyer Web chat raw legal payload in browser storage | Privacy: don't cache raw legal documents in localStorage. | Use server-side session; browser holds only display tokens, not raw payloads. |
| Admin UI exposing secrets/tokens | v1.6 Admin Console API has field allowlist excluding secrets. | Web UI consumes same allowlisted API; no secret fields rendered. |
| Lawyer Web chat cross-tenant session access | Multi-tenant isolation must hold in Web UI. | Session list scoped to `tenant_id` + `user_id` from auth token. |

---

## Security & Compliance

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| RBAC — roles (admin, operator, lawyer, viewer) | Standard SaaS RBAC (WorkOS, AWS, Oso). 4 roles cover InkStatute personas: admin (full config), operator (review queues, health), lawyer (chat + own sessions), viewer (read-only dashboards). | MODERATE | `Role` enum in platform-contract. Role assigned per user per tenant. Stored in user profile. |
| RBAC — permissions matrix | WorkOS: map roles to permissions (actions on resources). Resources: sessions, tasks, feedback, skills, connectors, gateway config, users, tenants. Actions: read/write/delete/approve. | MODERATE | `PermissionMatrix`: role → resource → action → bool. Enforced at API layer (Admin Console API, Skill Registry write, Gateway config). |
| RBAC — token-based auth | v1.6 Admin Console API uses static token auth. Production needs per-user tokens with role claims. | MODERATE | JWT or opaque token with `user_id`, `tenant_id`, `role`, `exp`. Validated at API gateway. Reuse v1.6 static token as fallback for service-to-service. |
| RBAC — enforcement at every write endpoint | Oso/WorkOS: every write endpoint checks permission. Read endpoints respect field allowlist (v1.6). | MODERATE | Middleware: extract token → resolve role → check `PermissionMatrix[role][resource][action]`. Deny by default. |
| Multi-tenant isolation — tenant scoping | AWS prescriptive guidance: Tenant A users cannot view Tenant B data. Every query must be tenant-scoped. | MODERATE | `tenant_id` on every entity (session, task, feedback, skill, connector, cost record). All queries filter by `tenant_id` from auth token. No unscoped queries. |
| Multi-tenant isolation — data segregation | WorkOS: tenant isolation is a security property RBAC must enforce. Storage-level segregation (per-tenant prefix or per-tenant DB). | MODERATE | Contract logs: per-tenant partition or `tenant_id` index. Blob storage: per-tenant prefix. Hindsight: per-tenant memory namespace. |
| Multi-tenant isolation — per-tenant config | Tenants have different connector allowlists, gateway limits, skill sets, RBAC role assignments. | MODERATE | `TenantConfig`: connector bindings, rate limits, budget caps, enabled skills, custom routing rules. Loaded at request time. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-tenant skill catalog | Different law firms have different skill sets. Tenant-scoped skill visibility. | MODERATE | Skill Registry queries filter by `tenant_id` (private skills) + public skills. |
| Per-tenant model gateway budgets | Firm A on tight budget, Firm B unlimited. | LOW | `TenantConfig.gateway_budget`. Gateway enforces per-tenant. |
| Audit log per tenant | Legal compliance: who did what, when, scoped to tenant. | MODERATE | `AuditEvent`: `tenant_id`, `user_id`, `action`, `resource`, `timestamp`. Append-only. Admin UI view per tenant. |
| Role delegation (operator promotes viewer) | Admin can delegate operator role. | LOW | Admin-only user management endpoint. |

### Anti-features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Global admin bypassing tenant isolation | A super-admin who sees all tenants' legal data is a privacy/compliance risk. | Even admin role is tenant-scoped; cross-tenant access requires separate audit-logged escalation role (defer to M4 if needed). |
| Client-side RBAC enforcement only | Client-side checks are bypassable. | All enforcement server-side; client only hides/shows UI. |
| Shared credentials across tenants | Breaks isolation. | Per-tenant auth tokens; no shared tenant credentials. |
| Encryption-at-rest / retention-destruction in M3 | PROJECT.md line 40 explicitly defers encryption + retention/destruction to M4. | Scope out; document as M4. RBAC + multi-tenant isolation are the M3 security scope. |
| Auto-deletion of legal data by retention policy | Legal data often must be retained (evidence). Auto-deletion = legal risk. | Retention/destruction deferred to M4 with legal review. |

---

## Complexity Assessment

| Feature | Complexity | Reasoning |
|---------|------------|-----------|
| Token streaming (SSE) | MODERATE | Event-typed lifecycle + provider stream normalization + terminal event guarantee. Contract stub exists. |
| Cancellation propagation | MODERATE | Cross-layer propagation; provider-native cancel differs (Anthropic no native, Ollama abort, Codex subprocess kill). |
| Progress events | LOW | Reuse ExecutionTrace as progress signals. |
| Artifact return | MODERATE | Neutral Artifact schema + content_ref (no inline binaries) + provider output mapping. |
| Session memory (Hindsight) | MODERATE | Wire adapter → platform-runtime Hindsight singleton. Adapter receives prepared context, emits results. No direct Hindsight calls. |
| Anthropic provider support | MODERATE | Lazy SDK import, normalize Messages API differences (system param, content blocks, thinking). |
| Ollama provider support | MODERATE | OpenAI-compatible client + local model quirks (no rate limit, model availability, tool-calling variance). |
| Error normalization | LOW | Reuse v1.6 pattern; add provider error code maps. |
| MCP Connector Registry | MODERATE | Registration + discovery + capability advertising + lifecycle. Follows MCP Registry spec with tenant scoping. |
| Model Provider Gateway | COMPLEX | Routing rules + rate limiting + fallback chains + cost tracking + model selection. Multiple interacting subsystems. |
| Multi-Agent Runtime Adapter | COMPLEX | Orchestration patterns (sequential/parallel/supervisor) + handoff + shared state. Hardest feature. |
| Skill Registry write (CRUD) | MODERATE | Standard CRUD + validation + versioning. |
| Skill Registry human review queue | MODERATE | Two-person rule for legal skills + audit trail. |
| Model-based routing (LLM-as-router) | MODERATE | Small model as classifier + prompt with skill descriptions. |
| Hybrid routing (cascade) | MODERATE | Rule → Skill → Model cascade with confidence thresholds. Existing router-service extended. |
| Confidence scoring + thresholds | MODERATE | Threshold config + clarification prompts on low confidence. |
| Admin Web UI | MODERATE | SPA consuming existing APIs; mostly frontend work. Write actions need RBAC. |
| Lawyer Web chat | MODERATE | Session list + history + file upload + feedback + streaming. Frontend-heavy. |
| RBAC | MODERATE | 4 roles + permissions matrix + token auth + enforcement middleware. |
| Multi-tenant isolation | MODERATE | tenant_id scoping + data segregation + per-tenant config. Must be enforced everywhere. |

**Most complex (highest risk):** Multi-Agent Runtime Adapter, Model Provider Gateway.
**Moderate bulk:** Adapter productization, Web UI, RBAC, multi-tenant, hybrid routing.
**Lower complexity:** Progress events, error normalization, gate status visualization, health monitoring.

---

## Dependencies on Existing Features

| New Feature | Depends On (Existing) | Dependency Nature |
|-------------|----------------------|-------------------|
| Streaming events | BackendAdapter Protocol (`stream_events` stub in Hermes adapter), platform-contract `AgentTurn`/`AgentResult` | Contract already has stub; M3 fills implementation. |
| Artifact return | BackendAdapter Protocol (`collect_artifacts` stub), platform-contract | Contract stub exists; M3 defines neutral `Artifact` schema. |
| Session memory (Hindsight) | Hindsight long-term memory (`hindsight_memory.py`, `aretain/arecall/areflect`), platform-runtime singleton wiring (v1.4 phase 32) | Adapters use platform-runtime-prepared context; Hindsight stays singleton. |
| Anthropic/Ollama provider support | provider_model adapter prototype (`packages/backends/provider_model`), `AsyncOpenAI` lazy import pattern | Extend prototype to multi-provider; add Anthropic + Ollama SDK adapters. |
| MCP Connector Registry | Skill Registry read pattern (`packages/skill-registry`), Admin Console API auth | Reuse registry + cursor pagination patterns. Registration via Admin API. |
| Model Provider Gateway | Router Service (`packages/router-service`), provider_model adapter, error normalization | Gateway sits between router and adapters; reuses `RouteDecision` + `ErrorInfo`. |
| Multi-Agent Runtime Adapter | BackendAdapter Protocol, `ExecutionTrace`, platform-runtime run management | Implements BackendAdapter; nested runs with parent_run_id. |
| Skill Registry write | Skill Registry read (`packages/skill-registry`), feedback-service `skill_candidate` | Extends read registry with CRUD; review queue consumes feedback candidates. |
| Model-based / hybrid routing | Router Service (RULE + SKILL modes), `RouteDecision.confidence` field | Adds MODEL mode as escalation tier; confidence threshold logic. |
| Admin Web UI | Admin Console API (read-only, static token auth, field allowlist), conversation-read-view, feedback-service | Web UI consumes existing APIs; adds write actions for skill/feedback review (needs RBAC). |
| Lawyer Web chat | conversation-read-view (cursor pagination, filters), WeCom service output boundary, feedback-service | Reuses read-view for history; same output boundary; same FeedbackEvent schema. |
| RBAC | Admin Console API static token auth (v1.6) | Extends static token to per-user JWT with role claims; permissions matrix middleware. |
| Multi-tenant isolation | platform-contract `tenant_id` fields (if present), conversation-read-view filters, Hindsight namespaces | Requires tenant_id on all entities; enforced in all queries. May need schema additions. |
| All Web/UI features | WeCom service output boundary, privacy scrubbing (conversation-read-view) | Web UI inherits same output filtering + privacy rules. |
| All security features | V2 human gates (Phase 5 UAT, Phase 8 lawyer trial), 19 V2 gates | RBAC + multi-tenant must not break existing gates; human gates preserved. |

### Cross-Feature Dependencies (New → New)

| New Feature | Depends On (New) | Notes |
|-------------|------------------|-------|
| Admin Web UI write actions | RBAC | Write endpoints require role enforcement. |
| Lawyer Web chat file upload | Artifact return schema | Uploaded files use same `Artifact` schema. |
| Model Provider Gateway fallback | Multi-provider adapter support | Fallback needs ≥2 working providers. |
| Hybrid routing MODEL tier | Model Provider Gateway | LLM-as-router calls gateway for classifier model. |
| Skill Registry human review queue | RBAC (operator/admin role) | Review actions require role. |
| MCP Connector Registry registration | RBAC (admin role) | Registration requires admin. |
| Multi-tenant isolation | RBAC (tenant_id from auth token) | Isolation needs tenant-scoped tokens. |
| Cost-by-matter dashboard | Gateway cost tracking | Needs `matter_id` in CostRecord. |

---

## Key Findings Summary

1. **Streaming** is SSE-based with event-typed lifecycle (`run.started` → `token.delta` → `tool.call` → `run.completed`); terminal event always emitted; cancellation via separate endpoint. Industry has converged on SSE over HTTP (A2A, MCP both use it).
2. **Artifacts** use reference-based schema (`content_ref` URL/blob, `sha256`, `media_type`) — never inline large binaries in contract events (privacy rule). OpenAI Agents SDK `ToolOutputImage`/`ToolOutputFileContent` is the reference pattern.
3. **Session memory** stays in platform-runtime (Hindsight singleton per v1.4); adapters receive prepared context and emit results — no direct Hindsight calls from adapters.
4. **Multi-provider**: Anthropic Messages API differs structurally (system as top-level param, content blocks, thinking tokens, required max_tokens); Ollama is OpenAI-compatible but local (no rate limits, model-availability-dependent, weaker tool-calling). Both isolated in adapter packages (two-file rule).
5. **MCP Connector Registry** follows official MCP Registry spec (`server.json`, cursor pagination, `updated_since` sync) but is private/tenant-scoped. Registration probes/trusts tool schemas for router use.
6. **Model Provider Gateway** is the most complex new subsystem: routing rules + rate limiting (RPM/TPM/concurrency per tenant/provider) + fallback chains with circuit breakers + cost tracking with per-tenant/matter budgets + model selection by capability. Agentic workloads make budget caps a primary safety mechanism.
7. **Multi-Agent Runtime Adapter** is the highest-risk feature: orchestration patterns (sequential/parallel/supervisor), handoff with context, shared state scoped to parent_run_id. Must map to neutral AgentResult and respect tenant isolation.
8. **Hybrid routing** is a cascade (Rule → Skill → Model) with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5). LLM-as-router is last tier using small/fast model. reaatech/confidence-router and Meganova 3-tier cascade are reference patterns.
9. **Skill Registry write** for legal skills requires two-person human review (skill_candidate → reviewer approves → operator activates). No auto-promotion of legal conclusion skills (v1.6 safety rule preserved).
10. **RBAC**: 4 roles (admin/operator/lawyer/viewer), permissions matrix (role × resource × action), JWT with role+tenant claims, enforcement at every write endpoint. Multi-tenant isolation via `tenant_id` on all entities + all queries scoped.
11. **Anti-features flagged**: auto-skill-synthesis, inline raw legal text in events/streams, direct Hindsight calls from adapters, auto-MCP-execution on registration, gateway auto-downgrade for legal tasks, pure-LLM routing without rule fallback, global admin bypassing tenant isolation, client-side-only RBAC, encryption/retention (deferred to M4), auto-deletion of legal data.
12. **Encryption + retention/destruction explicitly deferred to M4** per PROJECT.md line 40 — must not be pulled into M3 scope.

---

*Feature research for: M3 Platform Extensions (adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant)*
*Researched: 2026-07-05*
