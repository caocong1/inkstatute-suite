# Architecture Research

**Domain:** M2 Multi-Backend & Platform Extensions — how seven new features integrate with the existing InkStatute V2 platform architecture.
**Researched:** 2026-07-03
**Confidence:** HIGH (source-confirmed against contracts, protocols, adapters, PRD §4/§6/§11/§12, and gate runner)

---

## Existing Architecture Summary

The V2 platform is already built and green (9 gates, 479 tests). The four North Star contracts live in `packages/platform-contract/` (JSON Schema + Python dataclass bindings) and `packages/platform-runtime/src/platform_runtime/protocols.py` (signature-only Protocols):

- **`ChannelAdapter`** (`protocols.py:208-219`): `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health`. Implemented by `WeComChannelAdapter` (`packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py`).
- **`BackendAdapter`** (`protocols.py:222-239`): `backend_id`, `capabilities`, `bootstrap_check`, `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts`. Implemented by `HermesBackendAdapter` (`packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py`).
- **`SolutionLoader`** (`protocols.py:242-252`): `validate`, `load`, `materialize_for`. Implemented by `DefaultSolutionLoader` (`packages/solution-loader/`).
- **`RunRuntime`** (`protocols.py:255-274`): `create_run`, `resume_interrupt`, `poll`, `stream`, `cancel`, `approve`. Implemented by `DefaultRunRuntime` (`packages/platform-runtime/src/platform_runtime/runtime.py`) — embeddable, dependency-injected, default-off via `RuntimeFeatureFlags`.

Key supporting pieces:
- **`AgentBackendMode`** enum (`agent_adapter.py:12-15`): already includes `HERMES`, `CODEX`, `PROVIDER_MODEL`. The manifest schema (`agent_adapter_manifest.schema.json`) already accepts all three modes.
- **Runtime selector** (`services/wecom-service/src/wecom_service/agent_backend.py`): `select_agent_backend()` reads `agent_backend.mode` from config, finds a matching manifest, validates it, enforces `no_channel_io=true`, and gates `live_acceptance_allowed` to Hermes (or explicitly `production_ready` non-Hermes).
- **RouteDecision** is currently produced only inside `hermes-contract-layer/mapper.py` (`map_agent_end_context`) by reverse-inferring from Hermes hook context — there is no standalone router module in `platform-runtime`.
- **conversation-read-view** (`services/conversation-read-view/`): builds a `ContractLogReadModel` from JSONL contract logs; API (`api.py`) exposes only `/conversations/{id}`, `/tasks/{id}`, and `/feedback?status=pending` — no pagination, no filtering, no trace queries, no list endpoints.
- **Channel enum** (`enums.py:33-37`): already includes `QQBOT`, `WEB`, `DESKTOP` alongside `WECOM`.

---

## M2 Integration Points

### M2-01 / M2-02: Codex & provider_model Adapters

**Integrates with:** `BackendAdapter` Protocol (`platform-runtime/protocols.py:222-239`), `AgentBackendManifest`/`AgentBackendMode` (`platform-contract/agent_adapter.py`), runtime selector (`wecom-service/agent_backend.py`).

**New vs modified:** NEW packages `packages/backends/codex/`, `packages/backends/provider_model/`. No contract changes required — `AgentBackendMode.CODEX` and `AgentBackendMode.PROVIDER_MODEL` already exist in the enum and manifest schema.

**BackendAdapter contract fit:** Both adapters implement the same 8-method Protocol. The contract is already invocation-mode-agnostic: `AdapterCapabilitySet.invocation_mode` is a free-form string (Hermes uses `"sync"`/`"oneshot"`), and `run_invocation_modes` is a string list. The Protocol methods (`submit_run` → `RunHandle`, `get_run` → `Run`, `stream_events` → `AsyncIterator[RunEvent]`) do not assume subprocess.

**Subprocess vs new run pattern:** Hermes uses a one-shot subprocess runner (`HermesOneShotRunner` Protocol, injected) plus an opt-in HTTP runs-API lane (`HermesRunsClient` with `HermesRunsTransport` Protocol). Codex and provider_model do NOT need the subprocess pattern:
- **Codex adapter:** Will likely use an HTTP/API transport (similar to `HermesRunsClient` but targeting a Codex-style agent API). The `HermesRunsTransport` Protocol pattern (host-injected `post_json`/`get_json`/`iter_json`) is a reusable seam — a similar `CodexRunsTransport` Protocol should be defined in the codex package.
- **provider_model adapter:** Direct LLM provider call (no agent framework). This is the simplest: `submit_run` calls a provider API synchronously and returns a `RunHandle` with `SUCCEEDED` status, `get_run` returns the `Run` with an `AgentResult`. No subprocess, no streaming (prototype), no cancel. `invocation_mode="direct_llm"`, `run_invocation_modes=["oneshot"]`.

**Runtime selector routing:** `select_agent_backend()` already matches on `mode` string. To route to Codex/provider_model, the host registers their manifests in the `manifests` sequence and sets `agent_backend.mode=codex` or `provider_model`. The selector already validates the manifest and enforces `no_channel_io=true`. The `live_acceptance_allowed` flag defaults to `False` for non-Hermes unless `metadata.production_ready=true` — this is correct for prototypes (they should NOT be live-acceptance-allowed).

**Capability truthfulness:** Codex/provider_model manifests must declare truthful `AdapterCapabilitySet` values. For prototypes: `stream_event_support=False`, `cancel_support=False`, `approval_support=False`, `trace_support=True` (minimal), `artifact_return_support` per backend, `no_channel_io=True` (both must not do channel I/O — the channel is owned by InkStatute).

### M2-03: Independent Router Service

**Integrates with:** `RouteDecision` schema (`platform-contract/schemas/route_decision.schema.json` + `events.py:206-222`), `hermes-contract-layer/mapper.py` (current RouteDecision producer), `DefaultRunRuntime` (current consumer via `RunRequest`).

**What currently lives in platform-runtime that should move:** Routing does NOT currently exist as a module in `platform-runtime`. RouteDecision is produced inside `hermes-contract-layer/mapper.py:92-117` by reverse-inferring from Hermes `agent:end` hook context (`active_skill_name`, `route_confidence`, `matched_rule`). The router-service extraction is therefore: (1) lift the route-decision computation out of the Hermes mapper into a standalone service, and (2) have the Hermes mapper call the router-service (or use its output) rather than inferring inline.

**Communication with platform-runtime:** Library import, not HTTP. The existing architecture is embeddable/library-first (`DefaultRunRuntime` is dependency-injected, no network). The router-service should be a **library package** (`packages/router-service/` or `services/router-service/`) that exposes a `RouterService` Protocol/class importable by the runtime and by hermes-contract-layer. An HTTP facade can be added later but is not required for M2. This preserves the "no new runtime dependency unless PRD requires" rule.

**RouteDecision schema extension:** The current schema is sufficient for Hermes rule-based routing. For a standalone service, consider adding optional `metadata.router_service_version` and `metadata.router_strategy` to record which router produced the decision. These fit in the existing `metadata` object — **no schema change required**. The `RouteMode` enum (`matched`, `simple_qa`, `skipped`, `zero_match`) already covers the needed modes.

**Avoiding breaking 9 gates:** The router-service extraction must be additive. During M2, `hermes-contract-layer/mapper.py` continues to produce `RouteDecision` events (gate: `hermes-contract-layer`, `contract-test-suite`). The router-service is wired in as an alternative/complementary producer. The mapper's `map_agent_end_context` can delegate route computation to the router-service library while keeping the same output schema. No gate test changes if the JSONL event shape is unchanged.

### M2-04: Skill Registry (read-only)

**Integrates with:** `NeutralSkillDescriptor` (`events.py:104-112`), `SolutionLoader` (`packages/solution-loader/`), `ExecutionTrace.active_skill_name` (contract field), Hermes skill index files.

**Where skill metadata comes from:** Hermes config files — the lawfirm profile has 101 top-level directories / ~312 skills (PRD §3.2). The skill-registry reads Hermes skill index/metadata files (descriptions, input/output schemas, required tools) and normalizes them into `NeutralSkillDescriptor` records. It does NOT call an API — it reads files from the profile bundle. This is consistent with PRD §3.2: "只通过 Hermes router 日志和 skill index 读取 skill 元数据."

**Integration with SolutionLoader and BackendAdapter:** The skill-registry is a read-only query layer, not a loader. It complements `SolutionLoader` (which loads solution packages) by providing skill-level metadata. A backend adapter can query the registry to populate `ExecutionTrace.active_skill_name` context or to validate that a routed skill exists. The registry should be a **package** (`packages/skill-registry/`) importable by router-service and hermes-contract-layer.

**Read-only query interface:** `SkillRegistry` Protocol — `list_skills() -> list[NeutralSkillDescriptor]`, `get_skill(skill_id) -> NeutralSkillDescriptor | None`, `search(query) -> list[NeutralSkillDescriptor]`. No write methods. Backed by a file-system reader over the profile bundle's skill index.

### M2-05: conversation-read-view Completion

**Integrates with:** Existing `services/conversation-read-view/` (`api.py`, `read_model.py`, `models.py`, `privacy.py`), contract JSONL logs, `feedback-service` queue.

**What's missing vs PRD spec:** Current API (`api.py:11-58`) supports only 3 endpoints: `/conversations/{id}` (single), `/tasks/{id}` (single, with trace_id fallback), `/feedback?status=pending` (only pending). Missing per PRD §4.1 and §10.2:
- **List endpoints:** `/conversations` (list with pagination), `/tasks` (list with pagination + status filter).
- **Pagination:** `limit`/`offset` or cursor-based pagination on list endpoints.
- **Filtering:** Filter by `conversation_id`, `status`, `channel`, `user_id`, date range.
- **Trace queries:** `/traces/{trace_id}` endpoint (currently only `get_task_by_trace_id` exists as an internal method).
- **Feedback filtering:** Current API rejects any `status` other than `pending` (`api.py:36-47`). Must support `triaged`, `resolved`, `dismissed`.
- **Route decision queries:** `/routes/{route_decision_id}` or embedded in task view (currently `route_decision` is embedded in `ConversationTurnView` but not independently queryable).

**Relationship to Admin Console API:** Shared read model. `conversation-read-view` owns the `ContractLogReadModel` (the derived index over contract logs). Admin Console API should **import and reuse** `ContractLogReadModel` rather than duplicating it. The admin API adds operational aggregations (health, gate status, session counts) on top of the same read model. This avoids a separate read-model database and preserves "read models come from contract logs" (PRD §4.1).

### M2-06: Admin Console API (read-only)

**Integrates with:** `ContractLogReadModel` (from conversation-read-view), `feedback-service` queue, V2 gate runner (`scripts/run_v2_gates.py`), backend adapter `bootstrap_check`/`health`.

**Relationship to existing platform API server:** There is no standalone "Platform API server" in `platform-runtime` — the runtime is an embeddable library. The WeCom service (`services/wecom-service/`) is the only HTTP-facing service. The Admin Console API is a **separate service** (`services/admin-console-api/`) that imports read models and gate results as libraries. It does NOT extend the WeCom service (different concern: operations vs channel).

**Read-only views:** `/admin/sessions` (active/recent sessions from contract logs), `/admin/tasks` (task status summary), `/admin/feedback` (all feedback statuses, aggregated), `/admin/gates` (last gate run results), `/admin/health` (component health from `bootstrap_check` + channel `health()`). All GET-only.

**Auth boundaries:** M2 is read-only. Auth is minimal — operator token or local-only binding. Full RBAC is M3 (PRD §7: "M3 必须补...RBAC"). The admin API must NOT expose raw payloads, secrets, or customer documents — reuse `privacy.scrub_contract_payload` from conversation-read-view.

### M2-07: QQBot Complete Loop

**Integrates with:** `ChannelAdapter` Protocol (`protocols.py:208-219`), `Channel` enum (`enums.py:35`: `QQBOT = "qqbot"` already exists), `wecom-service` feedback loop pattern, `feedback-service`.

**ChannelAdapter contract fit:** QQBot implements the same 6-method Protocol. The contract is channel-agnostic — `ChannelCapabilitySet` declares per-channel capabilities (text, files, cards, streaming, ack deadline). QQBot will have different capability values (e.g., QQ Bot supports text and rich messages but may not support the same template card format as WeCom).

**Shared with WeCom vs unique:**
- **Shared:** The `ChannelAdapter` Protocol, `RawInbound`/`InboundNormalized`/`ChannelDelivery`/`DeliveryResult` data shapes, `AgentTurn`/`FeedbackEvent` normalization targets, output boundary policy (assistant output boundary applies to all channels), feedback loop pattern (message → agent → reply → card → feedback → FeedbackEvent).
- **Unique to QQBot:** `QQChannelConfig` (QQ Bot app ID, secret refs, token endpoint — different from WeCom's `token`/`encoding_aes_key`/`corp_id`), QQ Bot callback verification/decryption (different protocol from WeCom's AES), QQ Bot message send envelopes (different API from WeCom's text/file/card envelopes), QQ Bot feedback card format (QQ Bot interactive messages differ from WeCom template cards). A `qqbot-service` (mirroring `wecom-service`) or a `qqbot` normalization module is needed.

**Feedback loop for QQBot vs WeCom:** Same contract flow (`AgentResult.feedback_target` → channel delivers card → user clicks → `FeedbackEvent` normalized from callback). The difference is the card format and callback shape. QQBot's `normalize_inbound` must detect QQ Bot button callbacks and produce `FeedbackEvent` with `source=card_button`, same as WeCom. The `feedback-service` is channel-neutral (it consumes `FeedbackEvent` records, not raw channel callbacks) — no changes needed there.

---

## New Components

| Component | Location | Purpose | Dependencies |
|-----------|----------|---------|--------------|
| Codex BackendAdapter | `packages/backends/codex/` | Prototype BackendAdapter proving contract portability for Codex-style agent API mode | `platform-contract`, `platform-runtime` (Protocol + RunRequest/Run/RunHandle) |
| provider_model BackendAdapter | `packages/backends/provider_model/` | Prototype BackendAdapter for direct LLM provider mode (no agent framework) | `platform-contract`, `platform-runtime` |
| Router Service | `packages/router-service/` (or `services/router-service/`) | Standalone routing decision computation extracted from hermes-contract-layer mapper | `platform-contract` (RouteDecision), `skill-registry` (optional, for skill validation) |
| Skill Registry | `packages/skill-registry/` | Read-only query layer over Hermes skill index/metadata files | `platform-contract` (NeutralSkillDescriptor), profile bundle file access |
| Admin Console API | `services/admin-console-api/` | Read-only operational views (sessions, tasks, feedback, gates, health) | `conversation-read-view` (ContractLogReadModel), `feedback-service`, gate runner results, `platform-runtime` (health Protocols) |
| QQBot ChannelAdapter | `packages/channels/qqbot/` | ChannelAdapter implementation for QQ Bot channel | `platform-contract`, `platform-runtime` (ChannelAdapter Protocol), QQ Bot normalization/sender modules |
| QQBot service modules | `services/qqbot-service/` (or shared normalization in channel package) | QQ Bot callback verification, message normalization, send envelopes | `platform-contract`, mirrors `wecom-service` structure |

---

## Modified Components

| Component | Change | Risk | Gate Impact |
|-----------|--------|------|-------------|
| `hermes-contract-layer/mapper.py` | Delegate route computation to router-service library (optional, behind feature flag) | Low — additive; mapper can keep inline inference as fallback | `hermes-contract-layer` gate, `contract-test-suite` gate — must stay green; no JSONL shape change |
| `services/conversation-read-view/api.py` | Add list endpoints, pagination, filtering, trace queries, all feedback statuses | Low — additive endpoints; existing endpoints unchanged | `conversation-read-view` gate — existing tests must pass; add new tests for new endpoints |
| `services/conversation-read-view/read_model.py` | Add list/pagination support to `ContractLogReadModel` (currently single-item lookups only) | Low — add methods, don't remove existing | `conversation-read-view` gate |
| `services/wecom-service/agent_backend.py` | No change required — selector already supports codex/provider_model modes | None | `wecom-service` gate — no change |
| `scripts/run_v2_gates.py` | Add gates for new packages (codex, provider_model, router-service, skill-registry, qqbot, admin-console-api) | Low — additive gates; existing 9 gates unchanged | All gates — new gates added, existing 9 must stay green |
| `packages/platform-contract/` | No schema changes required — all M2 modes/channels already in enums | None | `platform-contract` gate — no change |

---

## Data Flow Changes

### Codex / provider_model Adapters
```
WeCom service → select_agent_backend(mode=codex|provider_model) → CodexBackendAdapter.submit_run(RunRequest)
  → Codex API / LLM provider call → RunHandle → get_run → Run(AgentResult with ExecutionTrace)
  → WeCom service output boundary → ChannelDelivery → user
```
No change to contract log flow: `DefaultRunRuntime` still appends run records and state events to `ContractLogStore` if `contract_log_enabled`. The adapter returns the same `AgentResult`/`ExecutionTrace` shapes.

### Router Service
```
Current:  Hermes agent:end hook → mapper.map_agent_end_context() → RouteDecision (inline inference)
M2:       Hermes agent:end hook → mapper → RouterService.decide(turn_context) → RouteDecision
          (or: RunRuntime.create_run → RouterService.decide → RouteDecision before submit_run)
```
The RouteDecision JSONL event shape is unchanged. The router-service becomes the authoritative route producer; the mapper becomes a thin caller. For non-Hermes backends (Codex, provider_model), the router-service is called directly by the runtime or service layer since there is no Hermes hook to reverse-infer from.

### Skill Registry
```
Profile bundle skill files → SkillRegistry.load() → NeutralSkillDescriptor[]
  → queried by RouterService (skill validation) and Admin Console API (skill listing)
```
No contract log change. Skill metadata is read at startup or on-demand from files, not streamed as events.

### conversation-read-view Completion
```
Contract JSONL logs → ContractLogReadModel (extended with list/pagination/filter indexes)
  → API: /conversations?limit=&offset=&channel=&status= → paginated response
  → API: /tasks?status=&user_id= → paginated response
  → API: /traces/{trace_id} → trace view
  → API: /feedback?status=triaged|resolved|dismissed → filtered feedback
```

### Admin Console API
```
Contract JSONL logs → ContractLogReadModel (reused from conversation-read-view)
  + feedback-service queue → /admin/feedback (aggregated)
  + gate runner results → /admin/gates
  + backend.bootstrap_check() + channel.health() → /admin/health
  → GET-only responses with privacy scrubbing
```

### QQBot Complete Loop
```
QQ Bot callback → QQBotChannelAdapter.verify_and_ack → AckResponse (5s or QQ deadline)
  → normalize_inbound → AgentTurn (channel=qqbot) or FeedbackEvent
  → RunRuntime.create_run → BackendAdapter.submit_run → AgentResult
  → output boundary → QQBotChannelAdapter.deliver → QQ Bot message/card send
  → user clicks card → QQ Bot callback → normalize_inbound → FeedbackEvent
  → feedback-service → FeedbackEvent queue
```
Same contract event flow as WeCom; only the channel-specific normalization and send envelopes differ.

---

## Suggested Build Order

Considering dependencies, risk isolation, and gate safety:

| Order | Feature | Rationale |
|-------|---------|-----------|
| 1 | **M2-04: Skill Registry (read-only)** | No dependencies on other M2 features. Provides skill metadata that router-service and admin API consume. Lowest risk — pure read-only package, no existing code changes. |
| 2 | **M2-03: Router Service** | Depends on Skill Registry (optional, for skill validation). Extracts routing from hermes-contract-layer additively. Must not break mapper JSONL output. Can be built as a library package first. |
| 3 | **M2-01: Codex adapter prototype** | Depends on stable BackendAdapter contract (already stable). No dependency on router-service (Codex can use its own routing or the router-service). Proves contract portability — the core M2 thesis. |
| 4 | **M2-02: provider_model adapter prototype** | Depends on same contract as Codex. Simpler than Codex (direct LLM, no agent framework). Can be built in parallel with M2-01 but sequenced after to reuse patterns established by Codex. |
| 5 | **M2-05: conversation-read-view completion** | Depends on stable contract log format (already stable). Extends existing service additively. Must be done before Admin Console API (which reuses its read model). |
| 6 | **M2-06: Admin Console API** | Depends on conversation-read-view's `ContractLogReadModel` (M2-05), feedback-service, gate runner. Read-only service — low risk but depends on M2-05 completion for shared read model. |
| 7 | **M2-07: QQBot complete loop** | Most complex — new channel package + service modules + feedback loop. Depends on stable ChannelAdapter contract (already stable) and feedback-service (already built). Last because it touches the most surface area and proves ChannelAdapter portability (the second M2 thesis). Can be parallelized with M2-05/M2-06 if separate developer. |

**Parallelization notes:**
- M2-01 and M2-02 can be built in parallel once the BackendAdapter pattern is agreed.
- M2-05 and M2-07 can be built in parallel (different services, no shared code changes).
- M2-06 must follow M2-05 (shared read model dependency).

**Gate safety:** Each feature adds a new gate to `run_v2_gates.py` but must not modify existing gate test expectations. The 9 existing gates must stay green after each feature merge. New gates are additive.

---

## Contract Impact

| Schema/Contract | Change Required | Details |
|-----------------|-----------------|---------|
| `AgentBackendMode` enum | **None** | `CODEX` and `PROVIDER_MODEL` already exist (`agent_adapter.py:13-15`) |
| `agent_adapter_manifest.schema.json` | **None** | Already accepts `codex` and `provider_model` modes (`schema:24-28`) |
| `AdapterCapabilitySet` | **None** | `invocation_mode` and `run_invocation_modes` are free-form strings — no enum constraint |
| `Channel` enum | **None** | `QQBOT` already exists (`enums.py:35`) |
| `ChannelAdapter` Protocol | **None** | 6-method Protocol is channel-agnostic |
| `BackendAdapter` Protocol | **None** | 8-method Protocol is backend-agnostic, does not assume subprocess |
| `RouteDecision` schema | **None** | `metadata` object accommodates `router_service_version`/`router_strategy` without schema change |
| `RouteMode` enum | **None** | `matched`/`simple_qa`/`skipped`/`zero_match` covers router-service output |
| `NeutralSkillDescriptor` | **None** | Already defined (`events.py:104-112`) — skill-registry uses it as-is |
| `RunRequest` / `Run` / `RunHandle` | **None** | Backend-neutral shapes, no Hermes-specific fields |

**Bottom line: No contract schema changes are required for M2.** All seven features integrate using existing contract shapes. This is by design — V2 was built to preserve these extension points (PRD §1.3: "契约、配置、测试不得阻碍它们后续接入").

---

## Sources

- `.planning/PROJECT.md` — M2 milestone context, target features, key constraints (lines 13-30, 62-68)
- `docs/requirements/V2-PRD.md` — §3.2 Skill system, §3.3 Routing, §3.6 Model provider, §3.7 Channels, §4.1 Module boundaries, §6.5 RouteDecision schema, §11 M2 milestone scope, §12 Dev order (lines 118-122, 132-136, 138-140, 154-193, 511-529, 636-643, 645-686)
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — `AgentBackendMode`, `AdapterCapabilitySet`, `AgentBackendManifest`, validation (lines 12-15, 18-45, 48-106)
- `packages/platform-contract/src/platform_contract/enums.py` — `Channel` (QQBOT exists), `RouteMode`, all enum domains (lines 33-37, 164-168)
- `packages/platform-contract/src/platform_contract/events.py` — `RouteDecision`, `NeutralSkillDescriptor`, `AgentTurn`, `AgentResult`, `ExecutionTrace` dataclasses (lines 104-112, 126-155, 184-222)
- `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json` — RouteDecision JSON Schema (lines 1-80)
- `packages/platform-contract/src/platform_contract/schemas/agent_adapter_manifest.schema.json` — Manifest schema with codex/provider_model modes (lines 22-29)
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, `RunRuntime` Protocols (lines 208-274)
- `packages/platform-runtime/src/platform_runtime/ports.py` — `ContractLogStore`, `AssistantOutputBoundary` injected ports (lines 30-40)
- `packages/platform-runtime/src/platform_runtime/runtime.py` — `DefaultRunRuntime` embeddable implementation (lines 25-145)
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` — `HermesBackendAdapter` one-shot + runs-API pattern (lines 27-30, 45-138)
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` — `hermes_oneshot_capabilities()` truthful capability set (lines 40-58)
- `packages/backends/hermes/src/inkstatute_backends_hermes/runs_api.py` — `HermesRunsTransport` Protocol, opt-in HTTP lane (lines 21-60)
- `packages/backends/hermes/src/inkstatute_backends_hermes/config.py` — `HermesBackendConfig` with `from_env` (lines 11-36)
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — `WeComChannelAdapter` Protocol implementation (lines 38-162)
- `packages/channels/wecom/src/inkstatute_channels_wecom/config.py` — `WeComChannelConfig` secret-ref pattern (lines 11-34)
- `services/wecom-service/src/wecom_service/agent_backend.py` — `select_agent_backend()` runtime selector, mode matching, `live_acceptance_allowed` gating (lines 23-58)
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` — `map_agent_end_context()` current RouteDecision producer (lines 29-117)
- `services/conversation-read-view/src/conversation_read_view/api.py` — Current 3-endpoint GET API, pending-only feedback filter (lines 11-58)
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — `ContractLogReadModel` with single-item lookups (lines 28-139)
- `packages/solution-loader/src/inkstatute_solution_loader/loader.py` — `DefaultSolutionLoader` validate/load/materialize_for (lines 24-191)
- `scripts/run_v2_gates.py` — 9 V2 gates definition (lines 49-127)
