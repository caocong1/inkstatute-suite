# Feature Research

**Domain:** M2 Multi-Backend & Platform Extensions — agent backend adapters, router service, skill registry, conversation read-view completion, admin console API, and QQBot channel for InkStatute V2.
**Researched:** 2026-07-03
**Confidence:** HIGH

## Scope Note

This research covers **M2-specific features only** — the six new capabilities planned for milestone v1.6 M2. Existing v1.0–v1.5 features (WeCom service, Hermes adapter, platform contracts, feedback service, conversation-read-view basic, observability, CI gates, memory systems) are already shipped and explicitly out of scope for re-research.

M2 target features from PROJECT.md (lines 17–23):
1. Codex adapter prototype + direct provider_model adapter prototype
2. Independent Router Service
3. Skill Registry read
4. conversation-read-view completion
5. Admin Console API (read-only)
6. QQBot complete loop

## Multi-Backend Agent Adapters

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Neutral adapter contract with mode selection | LangChain Agent Protocol, AutoGen runtime registration, and OpenAI Agents SDK all define framework-agnostic interfaces. InkStatute already has `AgentBackendMode` enum (HERMES/CODEX/PROVIDER_MODEL) and `AgentBackendManifest` in `platform-contract/agent_adapter.py`. Codex/provider_model must implement the same contract as Hermes. | MEDIUM | Contract already exists in v1.1. M2 must prove Codex and provider_model adapters can satisfy `AdapterCapabilitySet` and `AgentBackendManifest` validation. Prototype scope: stub adapters that return valid manifests and handle minimal `submit_run` → `AgentResult` flow. |
| Capability probe + manifest validation | Hermes adapter already implements `bootstrap_check()` and `capabilities()` (see `packages/backends/hermes/adapter.py` lines 78–94). Codex/provider_model adapters must expose equivalent capability metadata (invocation_mode, no_channel_io, trace_support, etc.). | LOW | Reuse Hermes adapter pattern. Codex CLI adapter likely has `invocation_mode="subprocess"`; provider_model adapter has `invocation_mode="direct_llm"`. |
| Run submission → AgentResult mapping | Hermes adapter implements `submit_run()` → `RunHandle` → `get_run()` → `Run` with `AgentResult` (lines 96–146). Codex/provider_model must map their native execution model to the same `AsyncTaskState` → `AgentResultStatus` flow. | MEDIUM | Codex CLI subprocess invocation needs stdout/stderr capture → `AgentResult`. Provider_model needs SDK call → normalized response → `AgentResult`. Both must set `result_id`, `turn_id`, `status`, `reply_type`, `content` per contract. |
| Error normalization | Hermes adapter maps backend errors to `ErrorInfo` with category/code/message. Codex/provider_model must translate provider-specific errors (CLI exit codes, HTTP 429/500, SDK exceptions) into the same `ErrorCategory` enum. | MEDIUM | Provider-specific quirks isolated in adapters. Differentiator: actionable error messages (e.g., "rate limit: retry after 60s" vs generic "error"). |
| No channel IO in adapters | `AdapterCapabilitySet.no_channel_io=True` is enforced in Hermes adapter (line 90). Codex/provider_model must also be channel-agnostic — they receive `AgentTurn` and return `AgentResult`, never touch WeCom/QQ directly. | LOW | Contract enforcement. If an adapter attempts channel IO, manifest validation fails. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Streaming event support | LangChain Agent Protocol defines streaming primitives (SSE, WebSocket). Hermes adapter has stub `stream_events()` (line 148–156). Codex/provider_model could add real streaming for long-running tasks. | HIGH | Differentiator for production-ready adapters. M2 prototype can stub this, but contract should allow future streaming. |
| Artifact return support | Hermes adapter has `collect_artifacts()` (line 206–208). Codex CLI adapter could return file artifacts from subprocess output; provider_model could return structured outputs. | MEDIUM | Useful for code generation, document drafting. M2 prototype can return empty list, but contract must support it. |
| Session memory support | AutoGen and CrewAI have shared context/memory. InkStatute contract has `session_memory_support` flag. Future adapters could integrate with Hindsight (long-term memory). | HIGH | M2 prototype not required. Differentiator for M3+. |
| Approval workflow support | Hermes adapter has `submit_approval()` (line 170–204) but marks high-risk legal approvals as human-review-only. Provider_model could integrate with OpenAI Assistants API approval flows. | MEDIUM | Differentiator for non-legal domains. M2 prototype stub is sufficient. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Adapter-specific message formats | LangChain's early versions allowed per-backend message shapes. This breaks contract neutrality. | Enforce `AgentTurn` → `AgentResult` mapping in all adapters. Reject adapters that return backend-native messages. |
| Direct SDK imports in platform runtime | Babak Abbaschian's "two-file rule" (adapter + registry) isolates SDK imports. Platform runtime must never import provider SDKs. | Keep SDK imports inside `packages/backends/codex/` and `packages/backends/provider_model/`. Platform runtime only sees `BackendAdapter` protocol. |
| Hardcoded provider credentials in adapter code | Security risk. Credentials must be runtime secrets/env, not committed. | Follow Hermes pattern: `HermesBackendConfig` accepts secret_refs, not raw keys. Codex/provider_model adapters use same pattern. |
| Adapter-specific retry/backoff logic | Each provider has different retry requirements. Centralizing this in platform runtime breaks backend abstraction. | Each adapter handles its own retry/backoff internally. Platform runtime sees `ErrorInfo.retryable` flag only. |

### Research Notes

**Codex CLI Adapter Pattern:**
- Codex CLI (Agent Client Protocol) is subprocess-based like Hermes one-shot mode.
- Expected shape: `subprocess.run(["codex", "run", "--input", json_input])` → stdout JSON → `AgentResult`.
- Codex uses AGENTS.md for agent definitions; adapter may need to generate temporary AGENTS.md or pass agent config via CLI flags.
- Codex CLI has MCP server integration; adapter could expose MCP tools as `required_tools` in `RouteDecision`.
- Prototype scope: stub that echoes input → output, validates manifest, proves contract compatibility.

**Direct Provider Model Adapter Pattern:**
- Direct LLM provider adapters (OpenAI, Anthropic, Ollama) follow ports-and-adapters pattern (see D.U.H. ADR-009, llm-adapter, ProviderProtocol).
- Expected shape: HTTP client (httpx/aiohttp) calling provider's chat/completions API → normalize response → `AgentResult`.
- Provider-specific quirks: thinking tokens (Claude), tool calling conventions (OpenAI vs Anthropic), error shapes.
- Registry-driven routing (llm-adapter pattern) is a differentiator: model registry with pricing, capabilities, access control.
- Prototype scope: stub that calls a single provider (e.g., OpenAI), validates manifest, proves contract compatibility.

**Industry Comparison:**
- LangChain Agent Protocol: framework-agnostic endpoints for agent lifecycle, streaming, subagents. InkStatute's `AgentTurn`/`AgentResult`/`ExecutionTrace` map well to this.
- AutoGen: runtime registration with `AgentType` and factory functions. InkStatute's `AgentBackendMode` enum + `AgentBackendManifest` is similar.
- OpenAI Agents SDK: adapter-specific notes for third-party providers. InkStatute's capability flags mirror this.
- CrewAI: framework-agnostic integration via LangChain. InkStatute's neutral contract is more explicit.

## Independent Router Service

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Standalone routing decision API | Production agent platforms (LangGraph Platform, Google Gemini Agent Platform) separate routing from execution. InkStatute currently embeds routing in platform-runtime. M2 must extract to `services/router-service/`. | HIGH | Router service receives `AgentTurn` → returns `RouteDecision` (primary_skill, supporting_skills, confidence, mode, gates). Must be stateless and idempotent. |
| Route normalization | Hermes router outputs `RouteDecision(primary_skill, supporting_skills, gate_before, gate_after, confidence, reason, matched_rule)` (PRD §3.3). Router service must normalize all backends to this schema. | MEDIUM | Contract already defines `RouteDecision` in `platform-contract/events.py` (lines 207–223). Router service implements the normalization logic. |
| Skill-based routing | Hermes has 312 skills across 101 categories. Router service must support skill metadata lookup (from Skill Registry) for matching user intent to skills. | MEDIUM | Depends on Skill Registry read feature. Router service queries skill metadata (name, description, tags) for routing decisions. |
| Intent-based routing | Industry pattern: classify user intent (question, task, clarification) before selecting skill. Router service should support intent classification (rule-based or LLM-based). | MEDIUM | Hermes uses pure rule routing (regex). Router service can start with rule-based, add LLM-based intent classification as differentiator. |
| Mode support (rule, model, hybrid) | LangChain ADK routing supports model-level routing. Router service should expose `RouteMode` enum (RULE, MODEL, HYBRID) per contract. | LOW | Contract already has `RouteMode` enum. Router service implements each mode. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Model-based routing with confidence scoring | Use LLM to classify intent and select skill, return confidence score. Differentiator from pure rule routing. | HIGH | Requires prompt engineering, few-shot examples, confidence calibration. M2 can prototype with one provider (e.g., OpenAI). |
| Hybrid routing (rule fallback to model) | Rule-based routing for high-confidence matches, model-based for ambiguous queries. Best of both worlds. | HIGH | Requires confidence threshold tuning. Differentiator for production robustness. |
| Route mismatch detection | Track when actual `ExecutionTrace.active_skill_name` differs from `RouteDecision.primary_skill`. Feed back to router for learning. | MEDIUM | Contract already has `route_mismatch` flag in `AgentResult` and `RouteDecision`. Router service can log mismatches for analysis. |
| Gate-aware routing | `RouteDecision` includes `gates_before` and `gates_after`. Router service should recommend gates based on skill risk level. | MEDIUM | Hermes has gates (ask-user-enforcement, cn-law-research-gate). Router service should expose gate metadata. |
| Multi-backend routing awareness | Router service should consider backend capabilities when routing (e.g., Codex may not support certain skills). | MEDIUM | Depends on adapter capability manifests. Router service queries `AdapterCapabilitySet` before routing. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Embedded routing in agent adapters | Hermes currently has embedded router. This breaks backend neutrality and makes routing non-portable. | Extract routing to standalone service. Adapters call router service via API. |
| Stateful routing decisions | Router service should be stateless. State (session context, conversation history) belongs to platform runtime or memory systems. | Router service receives `AgentTurn` + optional context hints, returns `RouteDecision`. No in-memory state. |
| Provider-specific routing logic | Routing logic should not depend on backend-specific quirks. This breaks multi-backend support. | Use neutral skill metadata and intent classification. Provider-specific routing belongs in adapters, not router service. |
| Monolithic routing rules | Hardcoded regex rules for 312 skills is unmaintainable. Externalize routing rules to config or skill metadata. | Router service loads routing rules from Skill Registry or config files. Support hot-reload. |

### Research Notes

**Router Service Responsibilities:**
- Input: `AgentTurn` (user message, attachments, output_constraints, industry_context)
- Output: `RouteDecision` (primary_skill, supporting_skills, confidence, mode, gates, matched_rule, reason)
- Normalization: Translate backend-specific routing signals to neutral `RouteDecision` schema
- Skill lookup: Query Skill Registry for skill metadata (name, description, tags, required_tools)
- Intent classification: Rule-based (regex/keyword) or model-based (LLM classification)
- Gate recommendation: Suggest gates based on skill risk level, user permissions, compliance requirements

**Routing Patterns:**
- Skill-based routing: Match user intent to skill metadata (name, description, tags)
- Intent-based routing: Classify intent (question, task, clarification, correction) before skill selection
- Model-based routing: Use LLM to classify intent and select skill with confidence score
- Hybrid routing: Rule-based for high-confidence matches, model-based for ambiguous queries

**Industry Comparison:**
- LangChain ADK: `RoutedAgent` with explicit routing function, shared routing utility for selection and failover
- Google Gemini Agent Platform: Skill Registry for skill discovery and loading, routing based on skill metadata
- AutoGen: Message routing via `RoutedAgent` and message handlers, runtime manages agent lifecycle
- LangGraph Platform: Routing as part of orchestration layer, not standalone service

## Skill Registry Read

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Read-only skill metadata API | Google Gemini Skill Registry, Cloudflare agent-skills-discovery RFC, and AgentSkills registry all expose skill metadata via API. M2 must expose Hermes skill metadata as read-only registry. | MEDIUM | Hermes has 312 skills with SKILL.md frontmatter (name, description, tags, category). Skill Registry read API should expose this metadata. |
| Skill search and discovery | Industry pattern: search skills by name, description, tags, category. Registry should support filtering and search. | LOW | Basic search: filter by name substring, tag, category. Full-text search is differentiator. |
| Skill versioning | Hermes skills have version in frontmatter. Registry should expose version metadata. | LOW | Read-only API returns skill version. Write operations (publish, update) are out of scope for M2. |
| Skill dependency metadata | Hermes skills declare `requires_toolsets`, `requires_tools`, `fallback_for_toolsets`. Registry should expose these dependencies. | MEDIUM | Useful for routing decisions (router checks if required tools are available). |
| Progressive disclosure support | Hermes uses progressive disclosure (skills_list → skill_view → linked files). Registry should support tiered metadata loading. | MEDIUM | Level 0: minimal metadata (name, description, category). Level 1: full SKILL.md content. Level 2: linked files. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Well-known discovery endpoint | Cloudflare RFC defines `/.well-known/agent-skills/index.json` for skill discovery. Registry should support this standard. | LOW | Easy to implement, improves interoperability. |
| Skill capability flags | Expose skill capabilities (e.g., supports_streaming, requires_approval, risk_level). Useful for routing and gate decisions. | MEDIUM | Hermes doesn't have explicit capability flags, but can infer from metadata. |
| Skill usage statistics | Track how often each skill is used (from ExecutionTrace.active_skill_name). Useful for skill optimization and deprecation. | HIGH | Requires aggregation from contract logs. Differentiator for M3+. |
| Skill health status | Monitor skill health (success rate, error rate, average latency). Useful for routing decisions (avoid unhealthy skills). | HIGH | Requires aggregation from ExecutionTrace and AgentResult. Differentiator for M3+. |
| Cross-backend skill compatibility | Mark which skills are compatible with which backends (Hermes, Codex, provider_model). Useful for multi-backend routing. | MEDIUM | Requires manual tagging or automated testing. Differentiator for M2+. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Write operations (publish, update, delete) | M2 scope is read-only. Write operations introduce complexity and security risks. | Hermes manages skill lifecycle. Registry only reads Hermes skill metadata. |
| Skill execution in registry | Registry should only expose metadata, not execute skills. Execution belongs to agent backends. | Keep registry stateless and read-only. Execution is adapter responsibility. |
| Direct file system access | Registry should not directly access Hermes skill directory. This breaks abstraction. | Registry reads from indexed metadata (JSON cache or database), not raw files. |
| Real-time skill synchronization | Registry does not need real-time sync with Hermes skills. Periodic indexing is sufficient. | Use cron job or event-driven indexing when skills change. |

### Research Notes

**Hermes Skill Metadata Structure:**
- SKILL.md frontmatter: name, description, version, author, license, platforms, metadata.hermes.tags, metadata.hermes.category, metadata.hermes.requires_toolsets, metadata.hermes.requires_tools, metadata.hermes.fallback_for_toolsets, metadata.hermes.config
- Progressive disclosure: skills_list (minimal metadata), skill_view (full content), linked files (references, templates, scripts)
- Skill directory structure: `~/.hermes/skills/` with subdirectories for each skill

**Skill Registry API Design:**
- `GET /skills` — list all skills with minimal metadata (name, description, category, tags)
- `GET /skills/{skill_id}` — get full skill metadata (SKILL.md content, dependencies, config)
- `GET /skills?tag={tag}` — filter skills by tag
- `GET /skills?category={category}` — filter skills by category
- `GET /.well-known/agent-skills/index.json` — well-known discovery endpoint (Cloudflare RFC)

**Industry Comparison:**
- Google Gemini Skill Registry: Skill and SkillRevision entities, lifecycle and versioning, built-in gcp-skill-registry skill for self-management
- Cloudflare agent-skills-discovery RFC: .well-known URI path, index.json with name/type/description/url, SKILL.md standard
- AgentSkills registry: CLI-based (agentskills search/pull/push), standardized skill format (SKILL.md + scripts/references/assets), version control
- SkillHub registry: Namespace-based skill management (@namespace/skill_slug), ClawHub-compatible API, authentication and visibility

## Conversation Read-View Completion

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Pagination for large result sets | Langfuse v2 API, Narrative API, and CallSphere all use cursor-based pagination for agent data. Existing conversation-read-view has no pagination. M2 must add pagination. | MEDIUM | Cursor-based pagination (preferred) or offset-based. Langfuse uses cursor for performance. Narrative uses sequence_no for incremental reads. |
| Time-range queries | Langfuse v2 API supports `fromStartTime` and `toStartTime` filters. GNW trace analytics supports time-range filtering. M2 must support time-range queries. | LOW | Filter by `occurred_at` or `ingested_at` in contract logs. |
| Filtering by user, channel, status | Industry pattern: filter conversations by user_id, channel, status (active/completed). Existing API only supports conversation_id/task_id lookup. | MEDIUM | Add query parameters: `?user_id=...&channel=...&status=...`. |
| Trace reconstruction | GNW trace analytics supports trace reconstruction (trace_id → turns, tool calls, output messages). Langfuse groups observations by traceId. M2 must support trace reconstruction. | HIGH | Query by trace_id, return all related events (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent). |
| Conversation-level view | Existing API supports conversation_id lookup. Must extend to show all turns in conversation with metadata. | LOW | Already exists in `ContractLogReadModel.get_conversation()`. Need to add pagination and filtering. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cursor-based pagination with gap-free reads | Narrative API uses `current_version` and `since` for gap-free incremental reads. This is stronger than simple cursor pagination. | HIGH | Implement sequence_no-based incremental reads. Response includes `current_version`, next request uses `since=current_version`. |
| Correlation with OTEL traces | Sunholo ailang correlates sessions with OTEL traces via session.id. Useful for debugging. | MEDIUM | If InkStatute adopts OTEL, add `by_span/{spanId}` endpoint to get chat context for a trace. |
| Search across conversations | GNW trace analytics supports search by content substring. Useful for finding similar issues. | HIGH | Requires full-text search index (Elasticsearch, Postgres full-text search). Differentiator for M3+. |
| Refined view with outcome classification | GNW trace analytics has "Refined" view classifying outcomes (recovered from errors, no-tool answers, promptless turns). Useful for quality analysis. | MEDIUM | Requires client-side or server-side classification logic. Differentiator for M2+. |
| Export to CSV/JSON | GNW trace analytics supports CSV export. Useful for offline analysis. | LOW | Add `?format=csv` or `?format=json` parameter to list endpoints. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Offset-based pagination for large datasets | Langfuse v2 deprecated offset-based pagination for performance reasons. Use cursor-based pagination. | Implement cursor-based pagination with `cursor` and `limit` parameters. |
| Real-time streaming of conversation updates | Read-view is for historical analysis, not real-time updates. Use streaming events for real-time. | Keep read-view async and batch-oriented. Real-time updates belong to streaming service. |
| Direct database queries bypassing contract logs | Read-view must derive from contract logs, not direct database access. This ensures consistency and replayability. | All queries go through `ContractLogReadModel` built from contract event records. |
| Unbounded result sets | Always enforce pagination limits (default 50, max 1000 per Langfuse pattern). | Require `limit` parameter, enforce max limit. |

### Research Notes

**Existing conversation-read-view Implementation:**
- `ContractLogReadModel` in `services/conversation-read-view/src/conversation_read_view/read_model.py` (lines 28–140)
- Supports: `get_conversation(conversation_id)`, `get_task(task_id)`, `get_task_by_trace_id(trace_id)`
- Builds indexes from contract event records (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent)
- No pagination, no filtering, no time-range queries

**M2 Extensions Required:**
- Add pagination: cursor-based or sequence_no-based incremental reads
- Add filtering: user_id, channel, status, time-range
- Add trace reconstruction: query by trace_id, return all related events
- Add export: CSV/JSON format option
- Add search: content substring search (differentiator)

**Industry Comparison:**
- Langfuse v2 Observations API: cursor-based pagination, fromStartTime/toStartTime filters, traceId filter, fields parameter for field groups
- Narrative API: sequence_no-based incremental reads with gap-free guarantees, current_version for polling pattern
- GNW trace analytics: Trace Explorer (filter by session/trace/prompt), Conversation Browser (search, sortable columns, pagination, CSV export), Refined view with outcome classification
- Sunholo ailang: list sessions, get full conversation, paginated messages, search conversations, by-span correlation with OTEL traces

## Admin Console API (Read-Only)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Sessions view | Anthropic API monitoring, Microsoft Agent 365 observability, and Google Gemini Managed Agents all expose session-level operational views. M2 must expose read-only sessions API. | MEDIUM | List sessions with metadata (user_id, channel, status, created_at, last_activity). Filter by user, channel, status, time-range. |
| Tasks view | Operators need to see task-level metrics (success rate, error rate, average latency). M2 must expose read-only tasks API. | MEDIUM | List tasks with metadata (task_id, turn_id, status, skill, backend, created_at, completed_at). Filter by skill, backend, status, time-range. |
| Feedback view | Operators need to see feedback queue (pending, triaged, resolved). Existing conversation-read-view has basic feedback endpoint. M2 must extend to full feedback view. | LOW | Extend existing `/feedback` endpoint with filtering (status, event_type, user_id, time-range), pagination. |
| Gates view | V2 has 9 CI gates. Operators need to see gate status (pass/fail, last run, coverage). M2 must expose read-only gates API. | MEDIUM | Query V2 gate runner results, expose gate status per suite. Filter by suite, status, time-range. |
| Health view | Operators need to see component health (WeCom service, Hermes adapter, router service, skill registry). M2 must expose read-only health API. | LOW | Aggregate health checks from all components. Expose overall health status and per-component status. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Metrics aggregation | Anthropic API monitoring supports hourly/daily views for capacity planning. M2 could aggregate metrics (token usage, cost, success rate) per time granularity. | HIGH | Requires aggregation from contract logs and ExecutionTrace.model_usage. Differentiator for M3+. |
| Alerting integration | Microsoft Agent 365 supports centralized observability with alerting. M2 could integrate with alerting systems (Prometheus, PagerDuty). | HIGH | Requires metrics export and alert rule configuration. Differentiator for M3+. |
| Audit log view | Operators need to see audit trail of configuration changes, deployments, gate runs. M2 could expose read-only audit log API. | MEDIUM | Requires audit event logging. Differentiator for M2+. |
| User activity dashboard | Operators need to see user activity (active users, task volume, feedback rate). M2 could expose user activity dashboard API. | MEDIUM | Requires aggregation from contract logs. Differentiator for M2+. |
| Skill performance dashboard | Operators need to see skill performance (usage frequency, success rate, error rate). M2 could expose skill performance dashboard API. | HIGH | Requires aggregation from ExecutionTrace.active_skill_name. Differentiator for M3+. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Write operations (configuration changes, gate execution) | M2 scope is read-only. Write operations introduce security risks and complexity. | Keep API read-only. Configuration changes belong to separate admin service. |
| Direct database access | Admin Console API should derive data from contract logs and existing services, not direct database access. | All queries go through conversation-read-view, feedback-service, gate runner, health checks. |
| Real-time streaming | Admin Console is for operational monitoring, not real-time updates. Use streaming events for real-time. | Keep API async and batch-oriented. Real-time updates belong to streaming service. |
| Unbounded result sets | Always enforce pagination limits. | Require `limit` parameter, enforce max limit. |

### Research Notes

**Admin Console API Design:**
- `GET /admin/sessions` — list sessions with filtering (user_id, channel, status, time-range), pagination
- `GET /admin/sessions/{session_id}` — get session details with turns
- `GET /admin/tasks` — list tasks with filtering (skill, backend, status, time-range), pagination
- `GET /admin/tasks/{task_id}` — get task details with execution trace
- `GET /admin/feedback` — list feedback with filtering (status, event_type, user_id, time-range), pagination
- `GET /admin/gates` — list gate status with filtering (suite, status, time-range)
- `GET /admin/health` — get overall health status and per-component health
- `GET /admin/metrics` — get aggregated metrics (token usage, cost, success rate) per time granularity (differentiator)

**Industry Comparison:**
- Anthropic API monitoring: hourly/daily views for capacity planning, cost reconciliation, single integration for multiple granularities
- Microsoft Agent 365 observability: OTel standards support, cross-platform flexibility, centralized observability in admin center
- Google Gemini Managed Agents API: system architecture with isolated sandbox environments, network access controls
- OpenAI Global Admin Console: SSO settings, tenant admin management, invite management (work-in-progress)

## QQBot Complete Loop

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Receive (webhook or WebSocket) | QQ Bot platform supports HTTP webhook and WebSocket callbacks (mutually exclusive). M2 must support at least one receive mode. | MEDIUM | Webhook: HTTPS callback URL with signature verification (X-Signature-Ed25519, X-Signature-Timestamp). WebSocket: Gateway connection with heartbeat, identify, resume. |
| Send (text, image, file, embed) | QQ Bot API supports text, image, file, embed, ark, markdown messages. M2 must support at least text messages. | MEDIUM | Use QQ Bot API v2 (52 endpoints, 70 methods). Send text via `message.sendTextMessage`, images via `message.sendImageMessage`. |
| Callback handling (button clicks, interactions) | QQ Bot supports interaction events (MESSAGE_REACTION_ADD, etc.). M2 must handle feedback callbacks similar to WeCom. | MEDIUM | Map QQ interaction events to `FeedbackEvent` per contract. Support button clicks for feedback collection. |
| Idempotency and retry | QQ Bot has no built-in idempotency. M2 must implement idempotency (similar to WeCom). | MEDIUM | Use session_id + msg_id as idempotency key. In-memory dedupe for repeated sends. |
| Channel adapter pattern | WeCom has `WeComChannelAdapter` implementing `ChannelAdapter` protocol. QQBot must follow same pattern. | LOW | Create `QQBotChannelAdapter` in `packages/channels/qqbot/`. Implement same methods: `channel_id()`, `capabilities()`, `verify_and_ack()`, `normalize_inbound()`, `deliver()`, `health()`. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dual receive mode support (webhook + WebSocket) | QQ Bot platform supports both modes. Supporting both provides flexibility for different deployment scenarios. | HIGH | Implement receive mode switch via config (`BUB_QQ_RECEIVE_MODE=webhook|websocket`). Differentiator for production robustness. |
| Rich media support (voice, video, stickers) | QQ Bot supports voice, video, stickers. WeCom supports text, image, file, card. Supporting rich media is a differentiator. | MEDIUM | Requires media upload/download handling. Differentiator for user experience. |
| Group @mention support | QQ Bot supports group @mentions for triggering bot responses. WeCom supports group chats. Group @mention is a differentiator. | LOW | Parse @mention in group messages, trigger bot response. |
| Scheduled push support | QQ Bot supports scheduled push messages. WeCom supports proactive message push. Scheduled push is a differentiator. | MEDIUM | Implement scheduled message queue. Differentiator for automation. |
| STT/TTS support | QQ Bot supports speech-to-text and text-to-speech. WeCom supports voice messages. STT/TTS is a differentiator. | HIGH | Requires integration with STT/TTS services. Differentiator for accessibility. |

### Anti-Features

| Anti-Feature | Why Avoid | Mitigation |
|--------------|-----------|------------|
| Direct QQ Bot SDK dependency on platform runtime | Platform runtime should not import QQ Bot SDK directly. Use adapter pattern. | Keep QQ Bot SDK inside `packages/channels/qqbot/`. Platform runtime only sees `ChannelAdapter` protocol. |
| QQ-specific message formats in contract | Contract must remain channel-neutral. QQ-specific message shapes belong in adapter. | Normalize QQ messages to `AgentTurn`/`FeedbackEvent` per contract. QQ-specific fields in `metadata`. |
| Hardcoded QQ credentials in adapter code | Security risk. Credentials must be runtime secrets/env. | Follow WeCom pattern: `QQBotChannelConfig` accepts secret_refs, not raw keys. |
| QQ-specific routing logic | Routing should be channel-agnostic. QQ-specific routing belongs in adapter or router service. | Router service uses neutral skill metadata. QQ adapter can add channel-specific hints in `metadata`. |

### Research Notes

**QQ Bot Platform Comparison with WeCom:**
- Connection: QQ uses WebSocket or HTTP webhook; WeCom uses WebSocket SDK or HTTP callback
- Authentication: QQ uses App ID + Secret; WeCom uses Bot ID + Secret or Corp ID + Corp Secret
- Encryption: QQ has no encryption (or SDK-managed); WeCom uses AES encryption for callbacks
- Group support: QQ supports group @mentions; WeCom supports group chats
- Media types: QQ supports text, image, voice, video, file; WeCom supports text, image, file, card
- Message types: QQ supports text, embed, ark, markdown; WeCom supports text, markdown, file, card
- Callback validation: QQ uses ed25519 signature; WeCom uses token + encoding AES key

**QQ Bot Receive Loop:**
- Webhook mode: HTTPS callback URL, signature verification (X-Signature-Ed25519, X-Signature-Timestamp), op=13 for validation
- WebSocket mode: Gateway connection, heartbeat (op=1/11), identify (op=2), resume (op=6), hello (op=10)
- Event types: MESSAGE_CREATE, GUILD_CREATE, CHANNEL_CREATE, GUILD_MEMBER_ADD, MESSAGE_REACTION_ADD, etc.

**QQ Bot Send Loop:**
- Text message: `message.sendTextMessage(channelId, content)`
- Image message: `message.sendImageMessage(channelId, imageUrl)`
- Embed message: `message.sendEmbedMessage(channelId, {title, description, color, fields})`
- Markdown message: `message.sendMarkdownMessage(channelId, {content})`
- Reply message: `message.sendReplyMessage(channelId, content, originalMessageId)`

**QQ Bot Callback Loop:**
- Button clicks: MESSAGE_REACTION_ADD event
- Interaction events: interaction intent type
- Map to `FeedbackEvent` per contract: feedback_id, turn_id, event_type, action, rating, message

**Industry Comparison:**
- Hermes WeCom integration: WebSocket SDK or HTTP callback, encrypted XML callbacks, proactive message push via message/send API
- Hermes QQ integration: botpy SDK, C2C and group messages, rich media upload, WebSocket or HTTP callback
- Bub QQ plugin: HTTP webhook receiver with callback validation, ed25519 signature, receive transport switch (webhook/websocket), in-memory idempotency
- AstrBot QQ Official Webhook: HTTPS callback URL, callback validation, proactive message push, support for text/image/voice/video/file

## Complexity Assessment

| Feature Area | Complexity | Rationale |
|--------------|------------|-----------|
| Multi-backend agent adapters (Codex + provider_model) | MEDIUM | Contract already exists. Adapters follow Hermes pattern. Prototype scope is stub adapters with manifest validation and minimal run submission. Streaming, artifacts, memory support are differentiators (HIGH). |
| Independent Router Service | HIGH | Requires extracting routing from platform-runtime, implementing normalization logic, skill-based/intent-based/model-based routing, gate-aware routing. Model-based routing and hybrid routing are differentiators (HIGH). |
| Skill Registry Read | MEDIUM | Read-only API is straightforward. Progressive disclosure, well-known discovery endpoint, skill capability flags are differentiators (MEDIUM). Usage statistics, health status, cross-backend compatibility are differentiators (HIGH). |
| Conversation Read-View Completion | HIGH | Requires adding pagination (cursor-based or sequence_no-based), filtering (user, channel, status, time-range), trace reconstruction, search. Cursor-based pagination with gap-free reads is differentiator (HIGH). Search, refined view, export are differentiators (MEDIUM-HIGH). |
| Admin Console API (Read-Only) | MEDIUM | Sessions, tasks, feedback, gates, health views are table stakes (MEDIUM). Metrics aggregation, alerting integration, audit log, user activity dashboard, skill performance dashboard are differentiators (HIGH). |
| QQBot Complete Loop | MEDIUM | Receive (webhook/WebSocket), send (text/image/file), callback handling, idempotency, channel adapter pattern are table stakes (MEDIUM). Dual receive mode, rich media, group @mention, scheduled push, STT/TTS are differentiators (HIGH). |

## Dependencies on Existing Capabilities

| M2 Feature | Dependency on Existing v1.0–v1.5 Capabilities | Dependency Strength |
|------------|-----------------------------------------------|---------------------|
| Codex adapter prototype | `platform-contract/agent_adapter.py` (AgentBackendMode, AgentBackendManifest, AdapterCapabilitySet), `packages/backends/hermes/adapter.py` (pattern reference) | STRONG — reuses contract and adapter pattern |
| Provider_model adapter prototype | `platform-contract/agent_adapter.py` (AgentBackendMode, AgentBackendManifest, AdapterCapabilitySet), `packages/backends/hermes/adapter.py` (pattern reference) | STRONG — reuses contract and adapter pattern |
| Independent Router Service | `platform-contract/events.py` (RouteDecision schema), Hermes router logic (scripts/router.py), Skill Registry read (for skill metadata lookup) | MEDIUM — reuses contract schema, depends on Skill Registry |
| Skill Registry Read | Hermes skill metadata (SKILL.md frontmatter, progressive disclosure), `platform-contract/events.py` (NeutralSkillDescriptor schema) | STRONG — reads Hermes skill metadata, reuses contract schema |
| Conversation Read-View Completion | `services/conversation-read-view/` (ContractLogReadModel, existing API), `platform-contract/events.py` (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent) | STRONG — extends existing read model and API |
| Admin Console API (Read-Only) | `services/conversation-read-view/` (sessions, tasks, feedback), `services/feedback-service/` (feedback queue), `scripts/run_v2_gates.py` (gate status), component health checks | MEDIUM — aggregates data from existing services |
| QQBot Complete Loop | `packages/channels/wecom/` (WeComChannelAdapter pattern), `platform-contract/events.py` (AgentTurn, FeedbackEvent, ChannelMessage, ChannelDelivery), `services/wecom-service/` (normalization pattern) | STRONG — reuses channel adapter pattern and contract schemas |

## M2-Prototype Scope vs Production-Ready Scope

| Feature Area | M2-Prototype Scope | Production-Ready Scope (Future) |
|--------------|-------------------|-------------------------------|
| Codex adapter | Stub adapter with manifest validation, minimal run submission (echo input → output), proves contract compatibility | Full subprocess integration with Codex CLI, streaming event support, artifact return, session memory, error handling, retry/backoff |
| Provider_model adapter | Stub adapter with manifest validation, minimal run submission (single provider call), proves contract compatibility | Multi-provider support (OpenAI, Anthropic, Ollama, etc.), streaming, tool calling normalization, provider-specific retry/backoff, pricing metadata, access control |
| Router Service | Rule-based routing only, skill-based routing (from Skill Registry), basic intent classification (keyword/regex), stateless API | Model-based routing with confidence scoring, hybrid routing (rule fallback to model), route mismatch detection and feedback, gate-aware routing, multi-backend routing awareness |
| Skill Registry Read | Read-only API for skill metadata (name, description, tags, category, dependencies), basic search (filter by tag/category), well-known discovery endpoint | Write operations (publish, update, delete), skill versioning and lifecycle management, skill capability flags, usage statistics, health status, cross-backend compatibility marking |
| Conversation Read-View Completion | Cursor-based pagination, time-range queries, filtering (user, channel, status), trace reconstruction, export to CSV/JSON | Full-text search across conversations, refined view with outcome classification, correlation with OTEL traces, real-time streaming updates, advanced analytics |
| Admin Console API | Sessions view, tasks view, feedback view, gates view, health view (all read-only), basic filtering and pagination | Metrics aggregation (token usage, cost, success rate) per time granularity, alerting integration, audit log view, user activity dashboard, skill performance dashboard |
| QQBot Complete Loop | Single receive mode (webhook or WebSocket), text messages only, basic callback handling (button clicks), idempotency, channel adapter pattern | Dual receive mode (webhook + WebSocket), rich media support (voice, video, stickers), group @mention support, scheduled push, STT/TTS support |

## Sources

- `.planning/PROJECT.md` — M2 target features (lines 17–23), existing v1.0–v1.5 capabilities (lines 34–52)
- `docs/requirements/V2-PRD.md` — §3 现有 lawfirm profile 能力盘点 (lines 110–145), §6 契约事件定义 (lines 399–570), §12 开发顺序 (lines 645–686)
- `packages/platform-contract/src/platform_contract/events.py` — AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, RouteDecision, ChannelMessage, ChannelDelivery schemas
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — AgentBackendMode enum, AgentBackendManifest, AdapterCapabilitySet, validation logic
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` — HermesBackendAdapter implementation pattern (bootstrap_check, submit_run, get_run, stream_events, cancel_run, submit_approval, collect_artifacts)
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — WeComChannelAdapter implementation pattern (channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health)
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — ContractLogReadModel implementation (from_records, get_conversation, get_task, get_task_by_trace_id)
- `services/conversation-read-view/src/conversation_read_view/api.py` — Existing API implementation (handle_get, parse_query_string, not_found_response)
- LangChain Agent Protocol — framework-agnostic APIs for agent lifecycle, streaming, subagents
- LangChain Backends — BackendProtocol for pluggable memory backends
- AutoGen Agent and Agent Runtime — RoutedAgent, agent runtime registration, message routing
- OpenAI Agents SDK — adapter-specific notes, third-party adapters, Models guide
- Google Gemini Skill Registry — Skill and SkillRevision entities, lifecycle and versioning, gcp-skill-registry skill
- Cloudflare agent-skills-discovery RFC — .well-known URI path, index.json, SKILL.md standard
- AgentSkills registry — CLI-based skill registry, standardized skill format, version control
- Langfuse v2 Observations API — cursor-based pagination, fromStartTime/toStartTime filters, traceId filter
- Narrative API — sequence_no-based incremental reads with gap-free guarantees
- GNW trace analytics — Trace Explorer, Conversation Browser, Refined view, CSV export
- Sunholo ailang — chat history integration, OTEL trace correlation, search across conversations
- Anthropic API monitoring — hourly/daily views for capacity planning, cost reconciliation
- Microsoft Agent 365 observability — OTel standards, cross-platform flexibility, centralized observability
- QQ Bot official documentation — event subscription, message receive/send, webhook/WebSocket modes
- Hermes WeCom integration — WebSocket SDK vs HTTP callback, encrypted XML callbacks
- Hermes skills documentation — Creating Skills, Working with Skills, progressive disclosure
- D.U.H. ADR-009 provider adapters — ProviderProtocol port, Anthropic/Ollama adapters, provider-specific isolation
- llm-adapter — Provider-agnostic LLM adapter, registry-driven routing, normalized outputs
- ProviderProtocol agents — Unified Agent Protocol, multi-provider support, functional state management
- Babak Abbaschian ports and adapters — Two-file rule, hexagonal architecture, provider isolation

---
*Feature research for: M2 Multi-Backend & Platform Extensions (agent backend adapters, router service, skill registry, conversation read-view completion, admin console API, QQBot channel)*
*Researched: 2026-07-03*
