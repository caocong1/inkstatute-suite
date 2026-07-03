# Project Research Summary

**Project:** 墨律 InkStatute V2
**Domain:** M2 Multi-Backend & Platform Extensions — Codex adapter, direct provider_model adapter, Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel
**Researched:** 2026-07-03
**Confidence:** HIGH

## Key Findings

- **No contract schema changes required for M2.** All seven features integrate using existing contract shapes. `AgentBackendMode.CODEX`/`PROVIDER_MODEL` already exist in the enum (`agent_adapter.py:12-15`). `Channel.QQBOT` already exists (`enums.py:35`). `RouteDecision`, `NeutralSkillDescriptor`, `BackendAdapter` Protocol (8 methods), and `ChannelAdapter` Protocol (6 methods) are all backend/channel-agnostic and frozen-ready. V2 was deliberately built to preserve these extension points (PRD §1.3).

- **Dependency-free invariant is the hardest constraint.** Every existing package declares `dependencies = []`. No FastAPI, no Pydantic, no uvicorn, no SQLAlchemy. Services are pure-Python `handle(path, query) -> (status_code, body)` functions. M2 features must follow this pattern — SDK imports (`openai`, `qq-botpy`) are optional dependencies with lazy imports inside methods, so packages import cleanly without them installed.

- **M2 is prototype scope, not production cutover.** PRD §11 designates Codex, provider_model, and QQBot as "原型" (prototypes). Prototype scope = stub adapters with manifest validation and minimal `submit_run → AgentResult` flow; fixture-driven loop proof for QQBot. Streaming, artifacts, session memory, retry/backoff, multi-provider support, and rich media are M3+ differentiators.

- **Router Service extraction is additive, not a rewrite.** RouteDecision is currently produced inside `hermes-contract-layer/mapper.py` by reverse-inferring from Hermes hook context. M2 lifts this into a standalone library package (not HTTP service) that the mapper can delegate to. The JSONL event shape stays unchanged, so the 9 V2 gates stay green.

- **Selection gate bypass is a live safety risk.** `select_agent_backend` (`agent_backend.py:50-51`) has a bypass: non-Hermes modes with `metadata.production_ready: True` become live-acceptance-eligible. Since M2 runs parallel to V2 human gates (Phase 5 UAT + Phase 8 lawyer trial), a misconfigured prototype could serve live WeCom turns. This must be fixed before any prototype manifest is committed.

- **Privacy scrub gap already exists and widens with M2.** `store.py` rejects 7 forbidden full-text keys; `privacy.py` only checks 1 (`raw_payload`). New backends produce new field names (`prompt_content`, `completion_text`, `function_call_result`) that bypass both checks. Must unify forbidden keys and add read-time scrubbing to every API response path before extending the read-view surface.

- **QQBot risks duplicating WeCom service logic.** `wecom-service/` mixes channel-generic logic (idempotency, delivery guard, active task router, output policy) with channel-specific code. Copying it to `qqbot-service/` creates divergence bugs. Channel-generic logic must be extracted to a shared package before QQBot is built.

- **Output boundary rules are Hermes-specific.** The regex rules in `output_boundary.py` catch Hermes noise (restart, tool progress, slash commands) but not Codex/provider_model noise (function call traces, rate limit notices, model names, API errors). Generic patterns catching the *class* of noise must be added alongside each new adapter.

## Stack Additions

| Technology | Version | Purpose | Dependency Type |
|------------|---------|---------|-----------------|
| Python stdlib `subprocess` + `json` | 3.11+ | Codex adapter: invoke `codex exec` as subprocess, parse JSONL | None — stdlib |
| `codex` CLI | latest 2026 | Codex adapter runtime (host binary, not Python dep) | Host install, not pip |
| `openai` Python SDK | 2.44.0 | provider_model adapter: `AsyncOpenAI` for OpenAI-compatible endpoints | Optional: `[project.optional-dependencies] openai = ["openai>=2.0"]`, lazy import |
| `anthropic` Python SDK | 0.116.0 | provider_model adapter: `AsyncAnthropic` for Claude (optional second provider) | Optional: `[project.optional-dependencies] anthropic = ["anthropic>=0.100"]`, lazy import |
| `qq-botpy` (botpy) | 1.2.1 | QQBot channel: WebSocket gateway, message receive/send | Optional: `[project.optional-dependencies] runtime = ["qq-botpy>=1.2"]`, lazy import |
| Pure-Python handler functions | — | Router Service, Admin Console API, conversation-read-view: `handle(path, query) -> (status_code, body)` | None — stdlib pattern |
| `itertools.islice` + dict comprehensions | 3.11+ | conversation-read-view pagination and filtering | None — stdlib |
| `contract_test_suite.event_stream_replay` | internal (existing) | Skill Registry, read-view, Admin API: load/replay JSONL contract logs | None — existing |
| `run_v2_gates.py --json-summary` | internal (existing) | Admin Console API: gate status read-only views via subprocess | None — existing |
| `platform_contract.events.RouteDecision` | internal (existing) | Router Service: normalized routing decision contract event | None — existing |

**Explicitly NOT recommended:** FastAPI (0.139.0), Pydantic, uvicorn, Flask, Starlette, LiteLLM (1.90.2), `openai-agents` (0.17.7), `qq-bot` (deprecated v0.8.5), any pagination library.

## Feature Table Stakes

| M2 Feature | Table Stakes (Required) | Complexity | Prototype Scope |
|------------|------------------------|------------|-----------------|
| **M2-01: Codex adapter** | Neutral adapter contract, capability probe + manifest validation, `submit_run → AgentResult` mapping, error normalization, `no_channel_io=True` | MEDIUM | Stub adapter: subprocess `codex exec --json`, manifest validation, minimal run submission. Streaming/artifacts/memory = M3+ |
| **M2-02: provider_model adapter** | Same contract as Codex; `invocation_mode="direct_llm"`; lazy SDK import | MEDIUM | Stub adapter: single provider call (OpenAI), manifest validation, proves contract compatibility. Multi-provider/streaming/tool-calling = M3+ |
| **M2-03: Router Service** | Standalone routing decision API, route normalization to `RouteDecision` schema, skill-based routing (from Skill Registry), intent classification (rule-based), `RouteMode` support | HIGH | Rule-based routing only, skill-based routing from Skill Registry, basic intent classification (keyword/regex), stateless. Model-based/hybrid routing = M3+ |
| **M2-04: Skill Registry read** | Read-only skill metadata API, skill search/discovery, skill versioning metadata, skill dependency metadata, progressive disclosure | MEDIUM | Read-only API for skill metadata (name, description, tags, category, dependencies), basic search, well-known discovery endpoint. Write ops/usage stats/health = M3+ |
| **M2-05: conversation-read-view completion** | Pagination, filtering (user/channel/status/time-range), trace reconstruction, all feedback statuses | HIGH | Cursor-based pagination, time-range queries, filtering, trace reconstruction, CSV/JSON export. Full-text search/refined view/real-time = M3+ |
| **M2-06: Admin Console API** | Sessions view, tasks view, feedback view, gates view, health view — all read-only with filtering and pagination | MEDIUM | Read-only sessions/tasks/feedback/gates/health views, basic filtering. Metrics aggregation/alerting/audit log = M3+ |
| **M2-07: QQBot complete loop** | Receive (webhook or WebSocket), send (text minimum), callback handling, idempotency, `ChannelAdapter` pattern | MEDIUM | Single receive mode, text messages only, basic callback handling, fixture-driven loop proof. Dual mode/rich media/group @mention/STT-TTS = M3+ |

**Anti-features (must avoid):** Adapter-specific message formats, direct SDK imports in platform runtime, hardcoded credentials, adapter-specific retry/backoff in runtime, write operations in Skill Registry, direct database queries bypassing contract logs, real-time streaming in read-view/admin API, unbounded result sets, QQ-specific message formats in contract, embedded routing in adapters, stateful routing, monolithic routing rules.

## Architecture Integration

### New Components (all `dependencies = []`)

| Component | Type | Integrates With | Contract Change |
|-----------|------|-----------------|-----------------|
| `packages/backends/codex/` | New package | `BackendAdapter` Protocol, runtime selector | None — `AgentBackendMode.CODEX` exists |
| `packages/backends/provider_model/` | New package | `BackendAdapter` Protocol, runtime selector | None — `AgentBackendMode.PROVIDER_MODEL` exists |
| `services/router-service/` | New library (not HTTP) | `RouteDecision` schema, `hermes-contract-layer/mapper.py`, `DefaultRunRuntime` | None — `metadata` object accommodates router version/strategy |
| `packages/skill-registry/` | New package | `NeutralSkillDescriptor`, `SolutionLoader`, `ExecutionTrace.active_skill_name` | None — `NeutralSkillDescriptor` exists |
| `services/admin-console-api/` | New service | `ContractLogReadModel` (reused), `run_v2_gates.py`, `feedback-service` | None |
| `packages/channels/qqbot/` | New package | `ChannelAdapter` Protocol | None — `Channel.QQBOT` exists |

### Modified Components

| Component | Change | Risk | Gate Impact |
|-----------|--------|------|-------------|
| `hermes-contract-layer/mapper.py` | Delegate route computation to router-service (optional, behind flag) | Low — additive; mapper keeps inline fallback | `hermes-contract-layer`, `contract-test-suite` gates must stay green |
| `conversation-read-view/api.py` + `read_model.py` | Add list endpoints, pagination, filtering, trace queries | Low — additive; existing endpoints unchanged | `conversation-read-view` gate; add backward-compat tests |
| `wecom-service/agent_backend.py` | Fix selection gate bypass (line 50-51) | Low — security fix, not behavioral change | `wecom-service` gate |
| `platform-runtime/output_boundary.py` | Add generic provider/model noise patterns | Low — additive rules | `platform-runtime` gate |
| `platform-runtime/store.py` + `privacy.py` | Unify forbidden keys, add new backend field names | Low — additive | `contract-test-suite` gate |
| `platform-runtime/feature_flags.py` | Add M2 feature flags (all default-OFF) | Low — additive | `platform-runtime` gate |
| `scripts/run_v2_gates.py` | Add gates for 6 new packages | Low — additive gates | All gates — existing 9 must stay green |

### Suggested Build Order

| Order | Feature | Rationale |
|-------|---------|-----------|
| 1 | M2-04: Skill Registry (read-only) | No dependencies on other M2 features. Provides skill metadata for router-service and admin API. Lowest risk. |
| 2 | M2-03: Router Service | Depends on Skill Registry (optional). Extracts routing additively from mapper. Must not break JSONL output. |
| 3 | M2-01: Codex adapter | Depends on stable BackendAdapter contract (already stable). Proves contract portability — core M2 thesis. |
| 4 | M2-02: provider_model adapter | Same contract as Codex, simpler (direct LLM, no agent framework). Reuses patterns from M2-01. |
| 5 | M2-05: conversation-read-view completion | Extends existing service additively. Must complete before Admin Console API (shared read model). |
| 6 | M2-06: Admin Console API | Depends on M2-05's `ContractLogReadModel`, feedback-service, gate runner. Read-only — low risk. |
| 7 | M2-07: QQBot complete loop | Most complex — new channel + service + feedback loop. Last because it touches the most surface area. |

**Parallelization:** M2-01 and M2-02 can be built in parallel once the adapter pattern is agreed. M2-05 and M2-07 can be built in parallel (different services). M2-06 must follow M2-05.

## Watch Out For

| Rank | Risk | Impact | Likelihood | Prevention |
|------|------|--------|------------|------------|
| 1 | **Contract drift from new backends breaking 479-test V2 gate suite** | HIGH — breaks V2 acceptance evidence, invalidates lawyer trial | MEDIUM | Freeze `BackendAdapter` Protocol (8 methods), `AdapterCapabilitySet` (14 fields), and `ChannelAdapter` Protocol for M2. Add contract-count assertion tests. All M2 PRs run all 9 gates before merge. No schema file modifications during V2 human gate period. |
| 2 | **Prototype adapters becoming production-eligible through selection gate bypass** | HIGH — unfiltered prototype output reaches live WeCom during V2 UAT | MEDIUM | Fix `select_agent_backend` bypass at `agent_backend.py:50-51`: `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready`. All non-Hermes manifests must set `production_ready: false`. Add assertion test. |
| 3 | **Privacy scrub gap between store-time and read-time** | HIGH — violates PRD §7, exposes client legal content | HIGH (gap exists today) | Unify `_FORBIDDEN_FULL_TEXT_KEYS` between `store.py` (7 keys) and `privacy.py` (1 key). Add new backend field names (`prompt_content`, `completion_text`, `function_call_result`, `tool_output`). Apply `scrub_contract_payload` to every API response path. Add read-time privacy tests. |
| 4 | **Router service extraction breaking in-process runtime tests** | MEDIUM — breaks 9 V2 gates if not injectable | MEDIUM | Extract routing as injectable `RouterPort` Protocol with `None` default (in-process). Define fallback policy for router unavailable. Keep `active_task_router.py` in-process. Run all 9 gates with `router=None`. |
| 5 | **QQBot duplicating WeCom service logic** | MEDIUM — maintenance burden, divergence bugs | HIGH | Extract channel-generic logic (idempotency, delivery guard, active task router, output policy) to `packages/platform-runtime/` or `packages/channel-core/` BEFORE building QQBot. QQBot gets own normalization/protocol/sender. Add test asserting QQBot does not import from `wecom_service`. |
| 6 | **Output boundary missing new backend-specific noise** | MEDIUM — provider/model names, API errors reach lawyers | MEDIUM | Add generic "provider/model name leakage" rule to `_HARD_BLOCK_RULES` catching `\b(?:model\|provider\|api[_-]?key\|quota\|rate[_-]?limit\|token[_-]?usage)\b`. Add output boundary fixture tests for each new backend. Keep boundary backend-agnostic. |
| 7 | **Prototype scope creep — building production infrastructure** | MEDIUM — new runtime deps, larger test surface, gate complexity | MEDIUM | Adapters must be fixture-driven prototypes with injected runners (like `HermesOneShotRunner`). No retry/rate-limit/circuit-breaker logic. Return `AsyncTaskState.FAILED` on first error. Adapter package ≤ Hermes adapter file count (7 files). |
| 8 | **Admin Console API exposing secrets / no auth** | HIGH — operational data exposed without authentication | MEDIUM | Add minimal auth gate (static API token from env). Admin API must NOT expose: secret ref names, config paths, `secret_refs_configured` maps, `api_base_url`, `oneshot_command`. Only expose `secrets_configured: true/false`. Run on separate port from WeCom callback. Add field allowlist and leakage test. |
| 9 | **Contract instability during parallel V2 human gates** | HIGH — M2 changes invalidate the system lawyers are testing | LOW (if frozen) | Freeze `packages/platform-contract/` schema files for duration of V2 human gates. Create "contract freeze" test comparing schemas against v1.5 baseline hash. M2 PRs touching `protocols.py` or `output_boundary.py` must run all 9 gates and document green. |
| 10 | **Default-OFF lane violations — M2 features enabled without gate** | MEDIUM — new services implicitly ON | MEDIUM | Add M2 feature flags (`router_service_enabled`, `skill_registry_enabled`, `admin_api_enabled`, `qqbot_channel_enabled`, `codex_backend_enabled`, `provider_model_backend_enabled`) all default `False`. Each service checks its flag before processing. Add test asserting all M2 flags default to `False`. |

## Implications for Roadmap

### Pre-Implementation Phase (M2 Setup)

**Must complete before any feature code is written:**
- Fix `select_agent_backend` selection gate bypass (Risk 2)
- Freeze `BackendAdapter` Protocol, `AdapterCapabilitySet`, `ChannelAdapter` Protocol — add contract-count assertion tests (Risk 1)
- Unify `_FORBIDDEN_FULL_TEXT_KEYS` between `store.py` and `privacy.py` (Risk 3)
- Add M2 feature flags to `RuntimeFeatureFlags` — all default-OFF (Risk 10)
- Add generic output boundary rules for provider/model noise (Risk 6)
- Create "contract freeze" baseline hash test for V2 human gate period (Risk 9)

**Rationale:** These are cross-cutting safety measures that protect the 479-test V2 gate suite and the parallel V2 human gates. They must be in place before any new backend/channel/service code is merged.

### Phase Grouping 1: Foundation (Skill Registry + Router Service)

**Features:** M2-04 (Skill Registry read) → M2-03 (Router Service)
**Rationale:** Skill Registry has zero dependencies on other M2 features and provides metadata that Router Service consumes. Router Service extraction is additive to `hermes-contract-layer/mapper.py` and must not break JSONL output. Both are library packages, not HTTP services.
**Risk mitigation:** Run all 9 V2 gates after each merge. Router Service must be injectable with `None` default. Keep `active_task_router.py` in-process as fallback.
**Dependencies:** Skill Registry → Router Service (optional dependency for skill validation).

### Phase Grouping 2: Backend Portability (Codex + provider_model)

**Features:** M2-01 (Codex adapter) + M2-02 (provider_model adapter) — parallelizable
**Rationale:** Both prove the core M2 thesis: BackendAdapter contract portability. Codex uses subprocess (mirrors Hermes pattern); provider_model uses lazy SDK import (simplest adapter). No dependency on Router Service — adapters can use their own routing or the router-service.
**Risk mitigation:** All manifests must set `production_ready: false`. Contract-count assertion tests guard against Protocol drift. Output boundary fixtures added alongside each adapter. Fixture-driven prototypes only — no production infrastructure.
**Dependencies:** Stable BackendAdapter contract (already stable). Pre-implementation phase must be complete.

### Phase Grouping 3: Read Views (conversation-read-view + Admin Console API)

**Features:** M2-05 (conversation-read-view completion) → M2-06 (Admin Console API)
**Rationale:** Admin Console API reuses `ContractLogReadModel` from conversation-read-view. Read-view completion is additive (new endpoints, existing ones unchanged). Admin API is read-only with auth gate and field allowlist.
**Risk mitigation:** Backward compatibility tests pin existing route response shapes. Privacy scrub applied to every API response. Admin API auth gate (static token from env) and field allowlist before exposing any endpoints. Choose indexing strategy (on-disk index or streaming reader) before adding pagination to avoid unbounded memory.
**Dependencies:** M2-05 must complete before M2-06 (shared read model).

### Phase Grouping 4: Channel Portability (QQBot)

**Features:** M2-07 (QQBot complete loop)
**Rationale:** Most complex feature — new channel package + service + feedback loop. Proves ChannelAdapter portability (second M2 thesis). Last because it touches the most surface area.
**Risk mitigation:** Extract channel-generic logic from `wecom-service/` to shared package BEFORE building QQBot. QQ Bot feedback must map to existing `FeedbackEvent.source` enum values (no new enum values). All QQ Bot API interactions behind injected Protocols (fixture-driven, not live). Output boundary must be applied in `DefaultRunRuntime` (runtime-level, not channel-level) — verify and add multi-channel boundary test. `ack_deadline_ms` and retry parameters configurable per-channel.
**Dependencies:** Stable ChannelAdapter contract (already stable). Channel-generic logic extraction must be done first. Pre-implementation phase must be complete.

### Gate Safety (All Phases)

- Each M2 feature adds a new gate to `run_v2_gates.py` (additive — existing 9 gates unchanged)
- Every new package must be added to gate runner PYTHONPATH and `compileall` paths
- Add meta-test asserting every `packages/*/src` and `services/*/src` directory is covered by a gate
- All 9 existing V2 gates must stay green after each feature merge
- No `packages/platform-contract/` schema file modifications during V2 human gate period

## Sources

- `.planning/PROJECT.md` — M2 milestone context, target features, key constraints
- `docs/requirements/V2-PRD.md` — §3.2 Skill system, §3.3 Routing, §3.6 Model provider, §3.7 Channels, §4.1 Module boundaries, §6 Contract events, §7 Safety/compliance, §11 M2 scope, §12 Dev order
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — `AgentBackendMode`, `AdapterCapabilitySet`, `AgentBackendManifest`
- `packages/platform-contract/src/platform_contract/enums.py` — `Channel` (QQBOT exists), `RouteMode`
- `packages/platform-contract/src/platform_contract/events.py` — `RouteDecision`, `NeutralSkillDescriptor`, `AgentTurn`, `AgentResult`, `ExecutionTrace`, `FeedbackEvent`
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, `RunRuntime` Protocols
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — `DefaultAssistantOutputBoundary` regex rules
- `packages/platform-runtime/src/platform_runtime/store.py` — `_FORBIDDEN_FULL_TEXT_KEYS`, store-time rejection
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags` all default-OFF
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` — `HermesBackendAdapter` pattern, `HermesOneShotRunner` Protocol
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — `WeComChannelAdapter` pattern
- `services/wecom-service/src/wecom_service/agent_backend.py` — `select_agent_backend` selection gate, live acceptance bypass
- `services/wecom-service/src/wecom_service/active_task_router.py` — pure-Python routing precedent
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` — current `RouteDecision` producer
- `services/conversation-read-view/src/conversation_read_view/` — `ContractLogReadModel`, `api.py`, `privacy.py`
- `scripts/run_v2_gates.py` — 9 V2 gate definitions
- Codex CLI documentation — `codex exec --json`, `--output-schema`, non-interactive mode
- OpenAI Python SDK — PyPI v2.44.0, AsyncOpenAI, streaming helpers
- Anthropic Python SDK — PyPI v0.116.0, AsyncAnthropic
- QQ Bot Python SDK — `tencent-connect/botpy` v1.2.1, WebSocket gateway, event handlers
- LangChain Agent Protocol, AutoGen, OpenAI Agents SDK — framework-agnostic adapter patterns
- Langfuse v2, Narrative API, GNW trace analytics — pagination and read-view patterns
- Cloudflare agent-skills-discovery RFC — `.well-known` URI, SKILL.md standard
- D.U.H. ADR-009, llm-adapter, Babak Abbaschian ports-and-adapters — provider isolation patterns
