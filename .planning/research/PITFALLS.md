# Pitfalls Research

**Domain:** M2 Multi-Backend & Platform Extensions — adding new backends, router extraction, skill registry, read-view completion, admin API, and QQBot channel to the existing InkStatute V2 platform (milestone v1.6)
**Researched:** 2026-07-03
**Confidence:** HIGH

This research covers common mistakes when **adding M2 features to the existing InkStatute system** — a Python 3.11 async platform with 9 V2 gates (479 tests), four North Star contracts (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime), a production Hermes backend adapter, a production WeCom channel, JSONL contract event logs, an output boundary filtering Hermes meta/gateway notices, and all runtime lanes default-OFF. M2 proceeds in parallel with unfinished V2 human gates (Phase 5 + Phase 8) at accepted risk.

---

## Multi-Backend Adapter Pitfalls (Codex + provider_model)

### Pitfall: Codex/provider_model adapters pressuring BackendAdapter Protocol changes

**What goes wrong:**
The `BackendAdapter` Protocol (`packages/platform-runtime/src/platform_runtime/protocols.py:222-239`) defines 8 methods: `backend_id`, `capabilities`, `bootstrap_check`, `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts`. The Hermes adapter (`packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py`) implements all 8, but most return truthful "unsupported" responses for capabilities it lacks (e.g., `cancel_run` returns `reason: "unsupported_by_oneshot"`, `submit_approval` rejects high-risk legal approvals). When building the Codex adapter, the developer discovers Codex supports streaming events natively, and wants to add a `stream_intermediate_events` method or change `stream_events` to yield a new event type. When building the provider_model adapter, they discover direct LLM providers have no concept of "bootstrap check" or "collect artifacts" and want to make those methods optional on the Protocol. Each change ripples back to the Hermes adapter and the `DefaultRunRuntime` which calls all 8 methods.

**Warning signs:**
- A PR modifies `packages/platform-contract/src/platform_contract/agent_adapter.py` to add new capability fields or change `AdapterCapabilitySet` (currently 14 fields at line 19-33).
- A PR modifies the `BackendAdapter` Protocol signature in `protocols.py`.
- Codex/provider_model adapter tests pass but Hermes adapter tests break because the Protocol changed.
- The `test_agent_adapter_contract.py` test that validates "schema does not require hermes or lawfirm fields for provider_model" (line 60-77) starts failing because new fields were added that are backend-specific.

**Prevention:**
- Freeze the `BackendAdapter` Protocol and `AdapterCapabilitySet` for M2. New backends must work within the existing 8-method, 14-capability surface. If a backend lacks a capability, it returns a truthful "unsupported" response the way Hermes does — this pattern is already proven.
- Codex streaming should use the existing `stream_events` method and `stream_event_support` capability flag (already in `AdapterCapabilitySet` at line 28). No new Protocol methods.
- provider_model's lack of bootstrap/artifacts should map to `bootstrap_check` returning `ok=True` with minimal metadata, and `collect_artifacts` returning an empty list — not to Protocol changes.
- Add a contract test that asserts the `BackendAdapter` Protocol method count and `AdapterCapabilitySet` field count have not changed from the V2 baseline. This guards against accidental contract drift.

**Phase to address:** M2-01/M2-02 implementation phase — before writing adapter code, freeze the contract surface and add the count-assertion test.

---

### Pitfall: Prototype adapters silently becoming production-eligible through the selection gate

**What goes wrong:**
The `select_agent_backend` function (`services/wecom-service/src/wecom_service/agent_backend.py:23-58`) has a critical gate at line 49: `live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value`. However, line 50-51 has a bypass: `if requested_mode != AgentBackendMode.HERMES.value and metadata.get("production_ready") is True: live_acceptance_allowed = True`. If a Codex or provider_model manifest accidentally sets `metadata.production_ready: True`, the adapter becomes live-acceptance-eligible. Since M2 runs in parallel with V2 human gates, a misconfigured Codex prototype could be selected for a live WeCom turn during Phase 5 UAT, bypassing the Hermes-only production constraint.

**Warning signs:**
- A Codex or provider_model manifest fixture or config sets `production_ready: true`.
- The `select_agent_backend` function is modified to relax the HERMES-only live acceptance check.
- Integration tests run with `agent_backend.mode=codex` against the live WeCom service instead of mock fixtures.
- The `live_acceptance_allowed` field on `AgentBackendSelection` is ignored by the WeCom dispatch path.

**Prevention:**
- All Codex/provider_model manifests must set `metadata.production_ready: false` explicitly, and a contract test must assert this for all non-Hermes manifests.
- Add a test that verifies `select_agent_backend` returns `live_acceptance_allowed=False` when `mode != "hermes"` regardless of `production_ready` metadata — close the bypass at line 50-51.
- The WeCom dispatch path (`ingress_runtime.py`) should assert `live_acceptance_allowed` before routing a live turn to any backend, not just trust the mode.

**Phase to address:** M2-01/M2-02 implementation phase — before any Codex/provider_model manifest is committed, fix the selection gate bypass and add the assertion test.

---

### Pitfall: Output boundary rules designed for Hermes noise missing new backend-specific leakage

**What goes wrong:**
The `DefaultAssistantOutputBoundary` (`packages/platform-runtime/src/platform_runtime/output_boundary.py:82-108`) has regex rules tuned for Hermes-specific noise: `backend_lifecycle` (restart/reconnect/shutting down), `tool_progress` (tool progress/memory sync/tool call), `operator_command` (/slash commands), `secret_like` (token/key/secret patterns). Codex and direct provider_model backends produce different noise: Codex may emit "function call trace", "token usage report", "rate limit retry", "context window exceeded"; provider_model may emit "model: glm-5.2", "provider: ollama-cloud", "API key invalid", "quota exceeded". These pass through the output boundary as `ALLOW` because the regex rules don't match them, and reach the lawyer's WeCom as visible text.

**Warning signs:**
- A Codex/provider_model adapter test asserts `BoundaryDecision.action == BoundaryAction.ALLOW` for text containing provider/model names or API error messages.
- The output boundary regex rules are not updated when a new backend is added.
- Integration tests for new backends don't include output boundary fixture tests with backend-specific noise samples.
- A lawyer sees "Rate limit exceeded for model glm-5.2" or "Function call: web_search" in WeCom during parallel V2 UAT.

**Prevention:**
- For each new backend, add output boundary fixture tests with backend-specific noise samples (Codex function call traces, provider error messages, rate limit notices, token usage reports) and assert they are BLOCKed or REWRITEd.
- Add a generic "provider/model name leakage" rule to `_HARD_BLOCK_RULES` that catches patterns like `\b(?:model|provider|api[_-]?key|quota|rate[_-]?limit|token[_-]?usage)\b` in user-visible text.
- The output boundary must be backend-agnostic — do not add Codex-specific or provider_model-specific logic into the boundary itself; instead add generic patterns that catch the *class* of noise, not the specific backend's strings.

**Phase to address:** M2-01/M2-02 implementation phase — output boundary fixtures must be added alongside each new adapter, not deferred.

---

### Pitfall: Prototype scope creep — building production infrastructure for prototype adapters

**What goes wrong:**
The PRD §11 says Codex and provider_model are "原型" (prototypes). But during implementation, the developer builds a full Codex client with retry logic, rate limit handling, connection pooling, and session management — essentially building a production Codex integration. This introduces new runtime dependencies (HTTP client libraries, Codex SDK), new failure modes (network timeouts, API rate limits), and new test surface area. The prototype then requires production-grade error handling, monitoring, and retry logic that doesn't exist for Hermes (which is a subprocess one-shot). The 9 V2 gates now have to test against a much larger surface, and the `compileall` gate must compile new dependency code.

**Warning signs:**
- The Codex adapter package has more files than the Hermes adapter package (currently 7 source files).
- New runtime dependencies are added to `pyproject.toml` for prototype adapters.
- The adapter implements retry/rate-limit/circuit-breaker logic instead of returning `AsyncTaskState.FAILED` on first error.
- Prototype adapter tests require network access or mock HTTP servers.

**Prevention:**
- Codex/provider_model adapters must be fixture-driven prototypes: they accept injected runners (like `HermesOneShotRunner` protocol at `adapter.py:27-30`) and do not make real network calls. The prototype proves contract compatibility, not production resilience.
- No new runtime dependencies. Use stdlib only. If the adapter needs an HTTP client, inject it as a Protocol the way Hermes injects its runner.
- The adapter's `bootstrap_check` should return `ok=False` with `issues: ["prototype_not_production_ready"]` by default, requiring explicit configuration to override.

**Phase to address:** M2-01/M2-02 planning phase — scope the prototypes as contract-proof, not production integration.

---

## Router Service Extraction Pitfalls

### Pitfall: Breaking existing in-process callers when extracting routing into a standalone service

**What goes wrong:**
Routing is currently embedded in two places: (1) `DefaultRunRuntime.create_run` (`packages/platform-runtime/src/platform_runtime/runtime.py:52-68`) calls `self.backend.submit_run(backend_req)` which delegates to Hermes, and Hermes internally routes via `scripts/router.py`; (2) `active_task_router.py` (`services/wecom-service/src/wecom_service/active_task_router.py`) does fast control-plane routing for follow-up turns during active tasks. The `RouteDecision` contract event is recorded by the Hermes contract layer's mapper. Extracting routing into a standalone `services/router-service/` introduces a network boundary where `DefaultRunRuntime.create_run` must now make an async HTTP/RPC call to the router service before calling `backend.submit_run`. This changes the critical path from 1 async call to 2, and breaks the `RunRuntime` Protocol's `create_run` which is synchronous-in-spirit (it calls backend directly).

The 9 V2 gates test `DefaultRunRuntime` in-process. The `test_phase10_runruntime_contracts.py` and `test_phase55_wecom_service_loop.py` tests inject fakes directly into the runtime. If the router service extraction changes `create_run` to require a router client dependency, all these tests break unless the router client is injectable and defaults to in-process.

**Warning signs:**
- `DefaultRunRuntime.__init__` gains a new `router_client` parameter.
- `create_run` makes an additional async call before `backend.submit_run`.
- V2 gate tests for `platform-runtime` or `wecom-service` break after router extraction.
- The `RunRuntime` Protocol gains a new method or changes `create_run` signature.
- The router service is deployed as a separate process but tests still run in-process without a facade.

**Prevention:**
- Extract routing as an injectable `RouterPort` Protocol (like `AssistantOutputBoundary` in `ports.py`), not a network service. The standalone `services/router-service/` is a deployment packaging of the same logic, not a new runtime dependency.
- `DefaultRunRuntime` should accept an optional `router: RouterPort | None = None`. When `None`, routing stays in-process (delegated to backend, as today). When provided, `create_run` calls `router.route(req)` first, attaches the `RouteDecision` to `req.metadata`, then calls `backend.submit_run`.
- All existing tests continue to pass with `router=None` (default). New tests with `router=<fake>` prove the extraction path.
- The standalone service wraps the same routing logic (`scripts/router.py` rules) in an HTTP handler, but the routing rules themselves remain a pure function importable without network.

**Phase to address:** M2-03 implementation phase — design the `RouterPort` Protocol before extracting, run all 9 gates with `router=None` to confirm no regression.

---

### Pitfall: Router service introducing distributed failure modes that don't exist in-process

**What goes wrong:**
In the current in-process model, routing either succeeds or raises an exception that the runtime catches. There are no network timeouts, no connection refused errors, no serialization failures. When routing becomes a standalone service, the `create_run` path gains: router service down → timeout → what? Does the runtime fall back to backend-internal routing? Does it fail the turn? Does it retry? The Hermes backend's `scripts/router.py` is a pure regex router with no external dependencies — it never fails. But the router service wrapper adds HTTP serialization, potential JSON encoding errors, and network latency that adds to the WeCom 5s ACK deadline.

The `active_task_router.py` is even more sensitive: it classifies follow-up turns *without blocking on the active task* (line 76). If this classification requires a network call to the router service, the "fast control plane" promise is broken — a router service timeout means the user's follow-up message hangs.

**Warning signs:**
- The router service adds >100ms latency to `create_run` in tests.
- `active_task_router` is modified to call the router service instead of using its local regex classification.
- Tests for `active_task_router` require network mocks or HTTP fixtures.
- The WeCom 5s ACK deadline is consumed by router service call latency.

**Prevention:**
- The `active_task_router.py` must remain in-process in `wecom-service`. It is a fast control-plane classifier, not a skill router. Do not extract it into the router service.
- The router service should only own skill-level `RouteDecision` routing, not active-task classification.
- `RouterPort` implementations must have a configurable timeout (default: 500ms) and a fallback policy: if the router service is unavailable, fall back to `RouteDecision(mode="zero_match")` and let the backend handle routing internally — this preserves the current behavior where Hermes routes internally.
- Contract tests must cover: router service down → fallback → run still succeeds; router service slow → timeout → fallback → run still succeeds.

**Phase to address:** M2-03 implementation phase — define the fallback policy before writing the service, add failure-mode tests.

---

### Pitfall: Router extraction breaking the v2-acceptance-traceability gate

**What goes wrong:**
The 9th V2 gate (`v2-acceptance-traceability` in `run_v2_gates.py:106-108`) runs `scripts/audit_v2_requirements.py --check-gaps` which asserts no requirement has `status: gap`. If the router extraction moves code from `platform-runtime` to `services/router-service/`, the audit's file-path-based traceability matrix may report the routing requirement as a gap because the code moved to a new path the audit doesn't know about. The gate fails, blocking all M2 work even though the code is correct.

**Warning signs:**
- The `v2-acceptance-traceability` gate fails after router extraction with a "gap" for a routing-related requirement.
- `scripts/audit_v2_requirements.py` has hardcoded file paths that don't include `services/router-service/`.
- The audit traceability JSON (`acceptance/v2-traceability.json`) shows routing requirements as "gap" after the code move.

**Prevention:**
- Before moving any routing code, update `scripts/audit_v2_requirements.py` to recognize `services/router-service/` as a valid evidence path.
- Run the audit gate immediately after the router service package is created (even if empty) to confirm no false gap.
- The router service must be added to the `compileall` gate in `run_v2_gates.py:110-127` — missing this causes a gate failure or, worse, a silent skip.

**Phase to address:** M2-03 setup phase — update audit and gate runner before moving code.

---

## Skill Registry Read Pitfalls

### Pitfall: Coupling to Hermes skill metadata format instability

**What goes wrong:**
Hermes has 101 top-level skill directories with ~312 skills synced via symlink/copy (PRD §3.2). The skill metadata format (skill names, descriptions, gate associations, MCP tool bindings) is Hermes-internal — it is not a stable platform contract. The M2 Skill Registry reads this metadata directly. When Hermes updates its skill directory structure, skill YAML format, or symlink convention, the Skill Registry breaks. This is the exact "Hermes version drift" risk identified in PRD §13 risk #15, but now the platform has a *runtime dependency* on Hermes internals, not just a subprocess call.

The existing system avoids this coupling: the `ExecutionTrace.active_skill_name` is a plain string normalized from Hermes output, and the `RouteDecision.primary_skill` is also a string. The Skill Registry would need to parse Hermes skill index files, skill YAML/JSON configs, and potentially symlink targets — all of which are Hermes implementation details.

**Warning signs:**
- The Skill Registry imports from Hermes source paths or reads Hermes internal config files directly.
- Skill Registry tests break when Hermes skill directory structure changes.
- The Skill Registry assumes a specific skill metadata schema (field names, nesting, file format) that isn't defined in `platform-contract`.
- Skill metadata is exposed with Hermes-specific field names instead of platform-neutral names.

**Prevention:**
- Define a platform-neutral `SkillMetadataView` schema in `platform-contract` (like `AgentTurn` / `AgentResult`) with fields: `skill_id`, `display_name`, `description`, `category`, `gate_associations`, `tool_associations`, `metadata`. The Skill Registry maps Hermes-internal format to this neutral schema.
- The mapping logic must be in `services/hermes-contract-layer/` (which already owns Hermes coupling), not in the Skill Registry package itself. The Skill Registry receives already-mapped neutral metadata.
- Add a version field to the Hermes skill index reader. If the Hermes skill format changes, the reader fails gracefully with `issues: ["hermes_skill_format_unsupported"]` instead of crashing.
- Tests must use fixture skill directories, not real Hermes paths.

**Phase to address:** M2-04 design phase — define the neutral `SkillMetadataView` schema before reading any Hermes metadata.

---

### Pitfall: Read-only Skill Registry becoming a write surface for skill_candidate

**What goes wrong:**
The PRD §7 and §13 risk #11 are explicit: "V2 只记录 `skill_candidate`，不得自动修改高风险法律 skill" and "实现期要确保 `feedback-service` 不会误触发 `skillopt-runner` 的自动修订". The `test_thin_layer_boundaries.py` test `test_feedback_safety_fails_on_auto_modify_true` (line 67-77) asserts that `auto_modify: True` in skill_candidate metadata is rejected. The Skill Registry starts as read-only, but during M2 development, the temptation is to add a "register skill_candidate" endpoint so feedback-derived candidates can be written to the registry. This creates a write surface that can be accidentally triggered by the feedback loop, violating the human-review-only constraint.

**Warning signs:**
- The Skill Registry API gains a POST/PUT endpoint.
- The Skill Registry imports `FeedbackEvent` or `SkillCandidate` from `platform_contract.events` and processes them for writing.
- The Skill Registry has any method named `register`, `create`, `update`, `add`, or `save`.
- The `test_feedback_safety_fails_on_auto_modify_true` test is modified or deleted.

**Prevention:**
- The Skill Registry must have zero write methods. Its API surface is GET-only: `list_skills()`, `get_skill(skill_id)`, `search_skills(query)`.
- Add a contract test that asserts the Skill Registry module has no functions/methods matching write patterns (`register|create|update|delete|save|write|add|modify|put`).
- The `auto_modify` safety test in `test_thin_layer_boundaries.py` must remain green and unmodified.
- Skill candidates from feedback continue to flow through `feedback-service` → `FeedbackEvent.skill_candidate` → human review queue, never through the Skill Registry.

**Phase to address:** M2-04 implementation phase — enforce read-only at the contract test level before any code is written.

---

## conversation-read-view Completion Pitfalls

### Pitfall: Loading entire JSONL contract logs into memory — unbounded result sets

**What goes wrong:**
The current `ContractLogReadModel.from_records` (`services/conversation-read-view/src/conversation_read_view/read_model.py:45-127`) loads ALL records, sorts them in memory, and builds a full conversation/task index. The `load_records_from_jsonl` function (line 20-25) calls `load_event_stream` which reads the entire JSONL file. This works for V2's small fixture-based test logs but will not scale when M2 completes the read-view with pagination and filtering for production use. A production contract log with thousands of turns across hundreds of conversations will exhaust memory or take seconds to load on every API call.

The current API (`api.py:11-58`) has no pagination — it returns full conversation/task objects. Adding pagination on top of an in-memory model doesn't fix the underlying problem; it just slices an already-loaded result.

**Warning signs:**
- The read-view API gains `limit`/`offset` parameters but `from_records` still loads all records.
- Test fixtures for conversation-read-view grow beyond 100 records.
- The read-view API response time exceeds 1 second in tests.
- `ContractLogReadModel.__init__` holds references to all conversations and tasks in memory (lines 38-42).

**Prevention:**
- Before adding pagination/filtering, refactor the read model to support streaming/indexed access: either (a) build an on-disk index (SQLite) from JSONL logs that supports paginated queries, or (b) implement a streaming reader that filters records during JSONL parsing without loading all into memory.
- The API must accept `limit`, `offset`, `conversation_id` filter, `date_range` filter, and `status` filter at the query level, not at the post-load level.
- Add a test with a 10,000-record fixture that asserts the API returns paginated results without loading all records (verify via memory profiling or mock the record loader).

**Phase to address:** M2-05 design phase — choose the indexing strategy before adding API endpoints.

---

### Pitfall: Privacy scrub gap between store-time and read-time

**What goes wrong:**
The contract log store (`packages/platform-runtime/src/platform_runtime/store.py:108-137`) rejects events with `raw_payload` key and forbidden full-text keys (`case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`) at store time. The read-view privacy module (`services/conversation-read-view/src/conversation_read_view/privacy.py:9-43`) only checks for `raw_payload` — it does NOT check for the other 6 forbidden full-text keys. This means if a new backend (Codex, provider_model) writes an event that bypasses the store-time check (e.g., through a different code path, or because the event is constructed differently), the read-view will happily expose `case_facts` or `customer_document_text` to the API consumer.

When M2 extends the read-view with trace queries and admin API access, the surface area for this gap increases — more fields are exposed, more query paths exist, and the privacy scrub only catches one of seven forbidden keys.

**Warning signs:**
- The read-view API returns fields containing `case_facts`, `document_text`, or `full_text` in test fixtures.
- The `scrub_contract_payload` function in `privacy.py` is not updated when new forbidden keys are added to `store.py`.
- A new backend adapter writes contract events through a path that doesn't go through `InMemoryContractLogStore._reject_forbidden_payload_storage`.
- The admin console API (M2-06) reads contract logs directly without going through `scrub_contract_payload`.

**Prevention:**
- Unify the forbidden keys: `privacy.py` must import and check the same `_FORBIDDEN_FULL_TEXT_KEYS` set from `store.py` (currently hardcoded separately). Single source of truth.
- Add a read-time privacy test that asserts ALL forbidden keys (not just `raw_payload`) are rejected by `scrub_contract_payload`.
- Every read-view API endpoint and admin console API endpoint must pipe responses through `scrub_contract_payload` — add a test that verifies this by injecting a fixture with each forbidden key and asserting rejection.
- When Codex/provider_model adapters write contract events, verify they go through `ContractLogStore.append` which enforces store-time rejection.

**Phase to address:** M2-05 implementation phase — fix the privacy scrub gap before extending the API surface.

---

### Pitfall: Breaking existing query consumers when extending the API

**What goes wrong:**
The current API (`api.py:11-58`) has three routes: `/conversations/{id}`, `/tasks/{id}`, `/feedback?status=pending`. The feedback route has a hard constraint at line 36-47: `status` must be `"pending"` — any other value returns 400. When M2 extends the API with pagination, filtering, and trace queries, the developer adds new query parameters (`limit`, `offset`, `date_from`, `date_to`, `channel`, `status`) and new routes (`/traces/{id}`, `/conversations`, `/tasks`). If the existing route behavior changes (e.g., `/feedback` now accepts `status=resolved`), existing consumers that expect 400 for non-pending status break. If the response shape changes (e.g., `_with_contract_metadata` adds new fields), consumers that parse the response with strict schema validation break.

**Warning signs:**
- The `/feedback?status=pending` route behavior changes (e.g., now returns all statuses, or the 400 error is removed).
- The response shape of existing routes gains new required fields.
- The `not_found_response` format changes.
- Existing `test_api.py` tests are modified to accommodate new behavior instead of new tests being added for new routes.

**Prevention:**
- Existing routes must remain backward-compatible: `/conversations/{id}`, `/tasks/{id}`, `/feedback?status=pending` keep their current behavior exactly.
- New routes (`/conversations` with pagination, `/tasks` with filtering, `/traces/{id}`) are additive.
- New query parameters on existing routes must be optional and default to current behavior.
- Add a "backward compatibility" test suite that pins the exact response shape of existing routes using golden fixtures.

**Phase to address:** M2-05 implementation phase — add backward compatibility tests before extending the API.

---

## Admin Console API Pitfalls

### Pitfall: No auth system — read-only endpoints exposed without authentication

**What goes wrong:**
The existing codebase has no authentication system. The `conversation-read-view` API (`api.py`) is a pure function `handle_get` with no auth check. The WeCom service uses callback verification (token/AES key) but that's channel auth, not API auth. When M2 adds the Admin Console API with endpoints for sessions, tasks, feedback, gates, and health, these endpoints expose operational data (session IDs, task statuses, feedback content, gate states, health details) with no authentication. Even though the endpoints are "read-only," the data they expose is sensitive: conversation metadata, user IDs, feedback content, backend health details, secret reference names.

The `WeComChannelConfig.capabilities()` and `health()` methods already expose `secret_refs_configured` booleans (which secrets are configured) in `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py:55-63` and `137-152`. The admin API would aggregate these across all channels and backends, giving an attacker a map of the system's secret configuration.

**Warning signs:**
- The Admin Console API has no auth middleware or token check.
- Health/status endpoints expose `secret_refs_configured` maps, config paths, or backend metadata.
- The admin API is deployed on the same port as the WeCom service callback handler.
- No test asserts that unauthenticated requests are rejected.

**Prevention:**
- M2-06 must include a minimal auth gate: at minimum, a static API token validated from environment variable (not committed to repo). All admin API endpoints require this token in an `Authorization` header.
- Add a test that asserts all admin API endpoints return 401 without a valid token.
- The admin API must NOT expose: secret reference names, secret values, config file paths, backend internal metadata, or `secret_refs_configured` maps. Instead, expose only `secrets_configured: true/false` (boolean, not which secrets).
- The admin API must run on a separate port from the WeCom callback handler to prevent channel-traffic exposure.

**Phase to address:** M2-06 design phase — define the auth gate and data redaction policy before building endpoints.

---

### Pitfall: Read-only Admin Console scope creep to read-write operations

**What goes wrong:**
The PRD §11 says Admin Console API is "只读" (read-only). But during implementation, the operator says "it would be convenient to restart a gate from the admin console" or "can I dismiss a feedback item from the admin API?" The developer adds a POST endpoint to dismiss feedback, then a POST to retry a failed task, then a POST to toggle a feature flag. Each addition turns the read-only admin API into a write surface that bypasses the default-OFF lane gates and the human-gated live promotion process. The `RuntimeFeatureFlags` (`packages/platform-runtime/src/platform_runtime/feature_flags.py:12-26`) are default-OFF — but an admin API that can toggle them at runtime defeats the human-gate safety model.

**Warning signs:**
- The Admin Console API gains POST/PUT/DELETE endpoints.
- The admin API can modify `RuntimeFeatureFlags` at runtime.
- The admin API can dismiss/triage feedback (changing `FeedbackEvent.status` from `pending` to `dismissed`).
- The admin API can cancel runs or submit approvals (duplicating `BackendAdapter.cancel_run` / `submit_approval`).

**Prevention:**
- The Admin Console API must be GET-only. Add a contract test that asserts no POST/PUT/DELETE handlers exist in the admin API module.
- The admin API must not import `RuntimeFeatureFlags`, `BackendAdapter.submit_run`, `BackendAdapter.cancel_run`, or `BackendAdapter.submit_approval`.
- If operators need write operations, that is M3 scope (PRD §11: M3 includes "安全合规体系"). Document this explicitly in the M2 plan.

**Phase to address:** M2-06 implementation phase — enforce GET-only at the contract test level.

---

### Pitfall: Admin health/status endpoints leaking internal system structure

**What goes wrong:**
The admin API exposes health/status views for operators. The `ComponentHealth` dataclass (`packages/platform-runtime/src/platform_runtime/protocols.py:69-76`) includes `component_id`, `detail`, and `metadata`. The WeCom adapter's `health()` returns `channel_id`, `network_io: False`, and `secret_refs_configured` map. The Hermes adapter's `bootstrap_check` returns `backend_id`, `invocation_mode`, `no_channel_io`, `runner_injected`, `oneshot_command_configured`. When the admin API aggregates these, it exposes: which channels are configured, which backends are available, what invocation modes are supported, whether runners are injected, what commands are configured. This is internal system structure that an attacker can use to understand the attack surface.

**Warning signs:**
- Health endpoints return `metadata` fields from `ComponentHealth` or `BootstrapStatus` without redaction.
- The admin API exposes package names, service paths, or adapter class names.
- Health responses include `oneshot_command` or `api_base_url` values from `HermesBackendConfig`.
- The admin API returns a system topology map showing all channels, backends, and their connections.

**Prevention:**
- Define an `AdminHealthView` neutral schema that exposes only: `component_type` (channel/backend/runtime), `component_id`, `ok: bool`, `detail: str` (human-readable status, not internal paths). No `metadata` passthrough.
- Add a redaction layer that strips `metadata` from `ComponentHealth` and `BootstrapStatus` before exposing to the admin API.
- Test that admin health responses do not contain: file paths, command strings, URLs, secret reference names, adapter class names, or package paths.

**Phase to address:** M2-06 implementation phase — build the redaction layer alongside the health endpoints.

---

## QQBot Channel Pitfalls

### Pitfall: QQ-specific logic leaking into the shared ChannelAdapter contract

**What goes wrong:**
The `ChannelAdapter` Protocol (`packages/platform-runtime/src/platform_runtime/protocols.py:208-219`) defines 5 methods: `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health`. The WeCom adapter (`packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py`) imports WeCom-specific modules: `normalize_wecom_turn`, `normalize_wecom_feedback_callback`, `parse_callback_envelope`, `build_text_send_envelope`, `build_file_send_envelope`, `build_template_card_envelope`. These are WeCom-specific implementations of the contract methods.

When building QQBot, the developer discovers QQ Bot has different callback verification (not WeCom's AES/token), different message types (QQ rich media, QQ inline keyboards vs WeCom template cards), and different feedback mechanisms (QQ button callbacks vs WeCom template card callbacks). The temptation is to add QQ-specific fields to `ChannelCapabilitySet` (e.g., `supports_qq_inline_keyboard`) or to `ChannelDelivery` metadata (e.g., `qq_message_type`). This pollutes the neutral contract with channel-specific fields, exactly the pattern the PRD §1.2 warns against: "平台核心不依赖法律字段、不依赖 Hermes 内部目录结构".

**Warning signs:**
- `ChannelCapabilitySet` (`protocols.py:57-66`) gains new fields specific to QQ (e.g., `supports_inline_keyboard`, `supports_qq_rich_media`).
- `ChannelDelivery` metadata keys include channel-specific names (`qq_msg_type`, `qq_chat_type`).
- The QQBot adapter imports from `wecom_service` modules instead of having its own normalization.
- The `ChannelAdapter` Protocol changes to accommodate QQ-specific behavior.

**Prevention:**
- Freeze `ChannelCapabilitySet` and `ChannelAdapter` Protocol for M2. QQBot must work within the existing 8-capability surface (`supports_text`, `supports_files`, `supports_cards`, `supports_images`, `supports_voice`, `supports_streaming`, `ack_deadline_ms`, `idempotency_strategy`).
- QQ-specific message types map to existing capabilities: QQ inline keyboards → `supports_cards=True`; QQ rich media → `supports_files=True` / `supports_images=True`.
- QQBot gets its own `services/qqbot-service/` with its own normalization, verification, and sender modules — do not import from `wecom_service`.
- Channel-specific metadata stays in `ChannelDelivery.metadata` as opaque key-value pairs, not in the contract schema's top-level fields.

**Phase to address:** M2-07 design phase — freeze the channel contract surface before building QQBot.

---

### Pitfall: Duplicating WeCom service logic instead of abstracting shared channel concerns

**What goes wrong:**
The WeCom service (`services/wecom-service/`) contains: `normalization.py`, `protocol.py`, `sender.py`, `ingress_runtime.py`, `delivery_guard.py`, `output_policy.py`, `idempotency.py`, `session_runtime.py`, `active_task_router.py`, `task_flow.py`, and more. Much of this is WeCom-specific, but some is channel-generic: idempotency logic, delivery guard, output policy, session runtime, active task routing. When building QQBot, the developer copies the entire `wecom-service/` directory, renames it to `qqbot-service/`, and modifies the WeCom-specific parts. Now there are two copies of idempotency logic, two copies of delivery guard, two copies of session runtime — and when a bug is fixed in one, it's not fixed in the other.

The `active_task_router.py` is especially risky: its regex patterns (`_STATUS_RE`, `_CANCEL_RE`, `_NEW_TASK_RE` at lines 181-183) contain Chinese keywords (进度, 状态, 取消, 停止) that are channel-independent. Duplicating this logic means the two channels' intent classification diverges over time.

**Warning signs:**
- `services/qqbot-service/` contains files that are byte-for-byte copies of `services/wecom-service/` files (except for class names).
- `idempotency.py`, `delivery_guard.py`, or `output_policy.py` is duplicated across channel services.
- `active_task_router.py` is copied to `qqbot-service/` with the same regex patterns.
- A bug fix in `wecom-service/idempotency.py` is not applied to `qqbot-service/idempotency.py`.

**Prevention:**
- Before building QQBot, audit `wecom-service/` for channel-generic vs. channel-specific logic. Move channel-generic logic to `packages/platform-runtime/` or a new `packages/channel-core/` package.
- `active_task_router.py` is channel-generic (it classifies text intent, not channel-specific callbacks). Move it to `packages/platform-runtime/` and have both WeCom and QQBot services import it.
- `idempotency.py` and `delivery_guard.py` are likely channel-generic — extract to shared package.
- `normalization.py`, `protocol.py`, `sender.py` are channel-specific — QQBot gets its own versions.
- The extraction must be done BEFORE QQBot is built, not after — otherwise the duplication is already entrenched.

**Phase to address:** M2-07 pre-implementation phase — extract shared channel logic before writing QQBot.

---

### Pitfall: QQ Bot feedback loop diverging from WeCom's FeedbackEvent normalization

**What goes wrong:**
The WeCom feedback loop is carefully normalized: `normalize_wecom_feedback_callback` produces a `FeedbackEvent` with `source: "card_button"`, `event_type` classification, `action` (up/down/needs_fix/route_wrong), and `skill_candidate` for route mismatches. The `feedback-service` then deduplicates, classifies, and queues. QQ Bot has a different feedback mechanism (QQ inline keyboard buttons, QQ message reactions, or QQ command-based feedback). If the QQBot adapter normalizes feedback differently — e.g., different `source` enum value, different `action` mapping, or missing `skill_candidate` generation — the feedback-service's deduplication and classification logic breaks for QQ-originated feedback.

The `FeedbackEvent` schema (PRD §6.3) defines `source` as `enum(card_button, text_command, web_form, admin_annotation)`. QQ Bot feedback must map to one of these — if the developer adds `qq_button` as a new source value, it breaks the schema.

**Warning signs:**
- The QQBot adapter produces `FeedbackEvent` records with `source` values not in the PRD §6.3 enum.
- QQ Bot feedback lacks `skill_candidate` generation for route mismatches.
- The `feedback-service` tests don't include QQ-originated feedback fixtures.
- QQ Bot feedback deduplication uses a different idempotency key scheme than WeCom.

**Prevention:**
- QQ Bot feedback must map to existing `FeedbackEvent.source` enum values: QQ inline keyboard buttons → `card_button`, QQ text commands → `text_command`. No new enum values.
- QQ Bot feedback normalization must produce the same `FeedbackEvent` shape as WeCom: same `event_type` classification, same `action` mapping, same `skill_candidate` generation for route mismatches.
- Add feedback-service tests with QQ-originated feedback fixtures that assert the same deduplication and classification behavior as WeCom fixtures.
- The idempotency key for QQ Bot feedback must follow the same scheme: channel-specific callback metadata hashed into a stable key.

**Phase to address:** M2-07 implementation phase — define QQ-to-FeedbackEvent mapping before building the feedback path.

---

### Pitfall: QQ Bot API instability and rate limits breaking the complete loop

**What goes wrong:**
WeCom has a stable enterprise API with well-documented rate limits and callback semantics. QQ Bot API is less mature: the QQ Bot platform may change message formats, callback signatures, rate limits, or card templates without notice. The WeCom service has retry and idempotency logic tuned for WeCom's retry behavior (WeCom retries callbacks every few seconds). QQ Bot may have different retry intervals, different ACK deadlines, or different rate limit headers. If the QQBot service copies WeCom's retry/idempotency parameters without tuning for QQ Bot's actual behavior, the complete loop (receive → ACK → agent → send → feedback) breaks under real QQ Bot traffic.

**Warning signs:**
- QQBot service uses WeCom's `ack_deadline_ms: 5000` without verifying QQ Bot's actual ACK deadline.
- QQBot service retry logic uses WeCom's retry intervals without checking QQ Bot API documentation.
- No rate limit handling for QQ Bot API send calls.
- QQ Bot card/template format changes break the `deliver` method silently.

**Prevention:**
- QQBot is a prototype proving ChannelAdapter portability (PRD §11: "QQBot 完整闭环"). It must complete the loop but is not a production cutover. Scope it as: fixture-driven loop proof, not live QQ Bot deployment.
- All QQ Bot API interactions must be behind injected Protocols (like `HermesOneShotRunner`), not hardcoded API calls. Tests use fixtures, not live QQ Bot API.
- `ack_deadline_ms` and retry parameters must be configurable per-channel, not hardcoded from WeCom values.
- Add a test that verifies the QQBot complete loop (receive → ACK → normalize → dispatch → deliver → feedback) works end-to-end with fixtures.

**Phase to address:** M2-07 implementation phase — scope as fixture-driven prototype, inject all QQ Bot API calls.

---

## Cross-Cutting Pitfalls (M2 parallel to V2 human gates)

### Pitfall: Contract instability during parallel M2 work breaking V2 human gate evidence

**What goes wrong:**
M2 proceeds in parallel with V2 human gates (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial). The V2 acceptance readiness report (`v1.5-V2-ACCEPTANCE-READINESS.md`) documents the state of the system at v1.5 closure. If M2 work modifies the `platform-contract` schemas, the `BackendAdapter` Protocol, the `ChannelAdapter` Protocol, or the output boundary rules, the system that the lawyers are testing during Phase 8 is no longer the system that was audited at v1.5. A schema change to `AgentResult` or `RouteDecision` could break the contract log replay that the V2 gates validate, causing the 9 gates to fail during the lawyer trial — which would invalidate the trial evidence.

The `v2-acceptance-traceability` gate (9th gate) checks for requirement gaps. If M2 adds new requirements or moves code, the audit may report gaps that didn't exist at v1.5 closure, failing the gate while lawyers are mid-trial.

**Warning signs:**
- M2 PRs modify files in `packages/platform-contract/src/platform_contract/schemas/`.
- M2 PRs modify `packages/platform-runtime/src/platform_runtime/protocols.py`.
- M2 PRs modify `packages/platform-runtime/src/platform_runtime/output_boundary.py`.
- The 9 V2 gates fail during the V2 human gate period.
- The `v2-acceptance-traceability` audit reports new gaps during M2 work.

**Prevention:**
- Freeze `packages/platform-contract/` schema files for the duration of V2 human gates. Any M2 work that requires schema changes must be deferred until V2 acceptance is complete or explicitly approved as accepted risk.
- M2 work that touches `protocols.py` or `output_boundary.py` must run all 9 V2 gates before merge and document that gates remain green.
- Create a "contract freeze" test that compares current schema files against a v1.5 baseline hash — if schemas change, the test fails and requires explicit override.
- The `v2-acceptance-traceability` audit must continue to pass throughout M2 — if M2 code moves break the audit, fix the audit before merging, not after.

**Phase to address:** All M2 phases — enforce contract freeze from M2-01 through M2-07.

---

### Pitfall: Gate runner PYTHONPATH gaps when adding new packages

**What goes wrong:**
The V2 gate runner (`scripts/run_v2_gates.py:49-128`) has explicit PYTHONPATH entries for each gate. The `contract-test-suite` gate (line 100-104) has 11 PYTHONPATH entries. When M2 adds new packages (`packages/backends/codex`, `packages/backends/provider_model`, `packages/channels/qqbot`, `services/router-service`, `services/skill-registry`, `services/admin-console-api`), each must be added to the gate runner's PYTHONPATH and `compileall` paths. Missing a path causes either: (a) the gate fails with `ModuleNotFoundError`, or (b) worse, the gate silently passes because the new package's tests aren't discovered (the v1.4 audit found a PYTHONPATH regression that had been hiding 3 broken gates since v1.2 — PITFALLS.md v1.5 Pitfall 3).

**Warning signs:**
- A new package is created but not added to `run_v2_gates.py`.
- The `compileall` gate doesn't compile the new package's `src/` directory.
- The `contract-test-suite` gate doesn't include the new package in its PYTHONPATH.
- New package tests pass in isolation (`python -m unittest discover`) but not through the gate runner.
- A gate that should test the new package silently skips it because the path is missing.

**Prevention:**
- For each new M2 package, add a gate entry in `run_v2_gates.py` with the correct PYTHONPATH, following the existing pattern.
- Add all new package `src/` paths to the `compileall` gate (line 110-127).
- Add all new package `src/` paths to the `contract-test-suite` gate PYTHONPATH (line 103) if the contract tests need to import them.
- Add a meta-test that asserts every `packages/*/src` and `services/*/src` directory is covered by either a gate PYTHONPATH or `compileall`.

**Phase to address:** Each M2 feature phase — add gate entries when creating the package, not after.

---

### Pitfall: Default-OFF lane violations — M2 features enabled without human gate

**What goes wrong:**
All runtime lanes are default-OFF (`RuntimeFeatureFlags` in `feature_flags.py:13-19`: `run_runtime_enabled`, `streaming_lane_enabled`, `channel_delivery_enabled`, `approval_lane_enabled`, `contract_log_enabled`, `context_assembly_enabled` — all `False`). M2 adds new services (router-service, skill-registry, admin-console-api) that may need their own feature flags. If these services are deployed without a default-OFF flag, they are implicitly ON, violating the "live promotion is human-gated" principle. The router service, if deployed as a standalone process and connected to the runtime, effectively enables routing outside the backend's control — a lane that was previously implicit (backend-internal) becomes explicit (external service) without a gate.

**Warning signs:**
- New M2 services have no feature flag and are ON by default.
- The router service is deployed and connected to `DefaultRunRuntime` without a `router_enabled` flag.
- The admin console API is deployed without an `admin_api_enabled` flag.
- The skill registry is queried by the runtime without a `skill_registry_enabled` flag.
- M2 feature flags are added to `RuntimeFeatureFlags` but default to `True`.

**Prevention:**
- Add M2 feature flags to `RuntimeFeatureFlags` (or a new `M2FeatureFlags` dataclass) with all defaults `False`: `router_service_enabled`, `skill_registry_enabled`, `admin_api_enabled`, `qqbot_channel_enabled`, `codex_backend_enabled`, `provider_model_backend_enabled`.
- Each M2 service must check its flag before processing. The runtime must check `router_service_enabled` before calling the router port.
- Tests for M2 features must explicitly enable the flag (as existing tests do with `RuntimeFeatureFlags(run_runtime_enabled=True)`).
- Add a test that asserts all M2 feature flags default to `False`.

**Phase to address:** M2 setup phase — define all M2 feature flags with default-OFF before any service code is written.

---

## Privacy & Safety Pitfalls

### Pitfall: Contract log privacy regression from new backend event shapes

**What goes wrong:**
The contract log store (`store.py:108-137`) rejects events with `raw_payload` and 6 forbidden full-text keys. But Codex and provider_model backends produce different event shapes than Hermes. Codex may include `function_call_result` with full text; provider_model may include `prompt_content` or `completion_text` with user legal content. These field names are not in the `_FORBIDDEN_FULL_TEXT_KEYS` set (`store.py:130-137`: `case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`). New backend events with sensitive legal content in fields like `prompt_content`, `completion_text`, `function_call_result`, or `tool_output` pass the store-time check and get persisted in contract logs — violating the PRD §7 rule: "契约日志只引用原始 payload（`raw_payload_ref`），不存敏感全文".

**Warning signs:**
- Codex/provider_model adapter tests write contract events with fields containing legal text that aren't in `_FORBIDDEN_FULL_TEXT_KEYS`.
- New backend event fixtures contain `prompt_content`, `completion_text`, `function_call_result`, or `tool_output` fields with full text.
- The `_FORBIDDEN_FULL_TEXT_KEYS` set is not updated when new backends are added.
- Contract log replay tests for new backends contain sensitive legal content.

**Prevention:**
- Before adding Codex/provider_model adapters, audit their event shapes for new field names that could carry sensitive text. Add any new sensitive field names to `_FORBIDDEN_FULL_TEXT_KEYS` in `store.py`.
- Consider a positive-list approach instead of a deny-list: contract log events may only contain fields from an allowlist (`turn_id`, `conversation_id`, `content` (hashed), `raw_payload_ref`, `metadata`, etc.). Any field not on the allowlist is rejected. This is safer than chasing new backend field names.
- Add a test that asserts Codex/provider_model contract events are rejected by `_reject_forbidden_payload_storage` when they contain full-text legal content.

**Phase to address:** M2-01/M2-02 implementation phase — update forbidden keys before writing adapter event mappers.

---

### Pitfall: Output boundary bypass through new channel delivery paths

**What goes wrong:**
The output boundary (`output_boundary.py`) filters text before user visibility. But it's applied in the runtime's delivery path, not in the channel adapter. When QQBot is added as a second channel, the `DefaultRunRuntime` must apply the output boundary to QQBot deliveries just as it does for WeCom. If the QQBot adapter is wired directly to the backend's output (bypassing the runtime's delivery path), the output boundary is skipped, and backend noise (Hermes gateway notices, Codex function call traces, provider error messages) reaches QQ Bot users.

The WeCom adapter's `deliver` method (`adapter.py:106-135`) builds send envelopes but does NOT apply the output boundary — that's the runtime's job. If QQBot's `deliver` method is wired differently (e.g., directly from backend `stream_events` to channel `deliver`), the boundary is bypassed.

**Warning signs:**
- QQBot delivery tests don't include output boundary assertion.
- The QQBot service has a code path from `BackendAdapter.stream_events` → `QQBotChannelAdapter.deliver` that doesn't pass through `DefaultAssistantOutputBoundary.apply`.
- QQBot users see backend meta/gateway/function-call text during testing.
- The output boundary is applied in `wecom-service` specifically, not in `platform-runtime` generically.

**Prevention:**
- The output boundary must be applied in `DefaultRunRuntime` (platform-runtime), not in individual channel services. This ensures all channels get boundary filtering by default.
- Verify that `DefaultRunRuntime` applies the boundary to ALL channel deliveries, not just WeCom. If the current code only applies it for WeCom, refactor to apply it generically.
- Add a test with a multi-channel runtime (WeCom + QQBot fake) that asserts the output boundary is applied to both channels' deliveries.
- The QQBot adapter's `deliver` method should receive already-filtered text, not raw backend output.

**Phase to address:** M2-07 implementation phase — verify output boundary is runtime-level, not channel-level; add multi-channel boundary test.

---

### Pitfall: Admin Console API exposing secrets through health/status/config views

**What goes wrong:**
The `WeComChannelConfig` exposes `token_secret_ref`, `encoding_aes_key_secret_ref`, `corp_id_ref` — these are secret *reference names* (not values), but even reference names reveal the system's secret management structure. The `HermesBackendConfig` exposes `api_base_url` and `oneshot_command`. The `BootstrapStatus.metadata` includes `oneshot_command_configured: bool` and `runner_injected: bool`. When the admin API aggregates health/status across all channels and backends, it may expose: which secret references are configured, what API URLs are used, what commands are configured, whether runners are injected. An attacker who gains admin API access gets a complete map of the system's sensitive configuration.

The PRD §7 is explicit: "WeCom token、encoding AES key、secret、access token、media 文件、回调原文、用户消息原文不得提交到仓库" and "密钥只通过环境变量或密钥管理系统引用". The admin API must not become a side-channel for secret discovery.

**Warning signs:**
- Admin API health endpoints return `secret_refs_configured` maps showing which secrets are configured.
- Admin API config views return `api_base_url`, `oneshot_command`, or `profile_name` values.
- Admin API responses include environment variable names or secret reference names.
- The admin API has a `/config` endpoint that dumps service configuration.

**Prevention:**
- The admin API must have a strict allowlist of fields it can expose. For health: `component_type`, `component_id`, `ok`, `detail` (human-readable). For config: nothing — config views are M3 scope with proper RBAC.
- Add a test that asserts admin API responses do not contain: `_ref`, `secret`, `token`, `key`, `url`, `command`, `path`, `password` (case-insensitive substring match on response JSON keys).
- The admin API must not have a `/config` or `/secrets` endpoint. If operators need config inspection, that is M3 scope.

**Phase to address:** M2-06 implementation phase — build the field allowlist and leakage test before exposing any endpoints.

---

## Top 5 Risks (Ranked)

### Risk 1: Contract drift from new backends breaking the 479-test V2 gate suite
**Impact:** HIGH — breaks V2 acceptance evidence, invalidates lawyer trial, blocks all M2 progress
**Likelihood:** MEDIUM — the Protocol is well-defined but adapter-specific pressure is real
**Mitigation:** Freeze `BackendAdapter` Protocol, `AdapterCapabilitySet`, and `ChannelAdapter` Protocol for M2. Add contract-count assertion tests. All M2 PRs must run all 9 gates before merge. No schema file modifications during V2 human gate period.

### Risk 2: Prototype adapters becoming production-eligible through the selection gate bypass
**Impact:** HIGH — a Codex/provider_model prototype could serve live WeCom turns during V2 UAT, producing unfiltered output
**Likelihood:** MEDIUM — the bypass exists in `agent_backend.py:50-51` today
**Mitigation:** Fix the `select_agent_backend` bypass: `live_acceptance_allowed` must be `False` for all non-Hermes modes regardless of `production_ready` metadata. Add assertion test. All non-Hermes manifests must set `production_ready: false`.

### Risk 3: Privacy scrub gap between store-time and read-time leaking sensitive legal content
**Impact:** HIGH — violates PRD §7 privacy baselines, exposes client legal content through read-view/admin API
**Likelihood:** HIGH — the gap already exists (`privacy.py` checks 1 key, `store.py` checks 7 keys)
**Mitigation:** Unify forbidden keys between `store.py` and `privacy.py`. Add new backend field names to forbidden keys before writing adapter event mappers. Add read-time privacy tests for all forbidden keys. Apply `scrub_contract_payload` to every API response path.

### Risk 4: Router service extraction breaking in-process runtime tests and introducing distributed failure modes
**Impact:** MEDIUM — breaks 9 V2 gates if not done with injectable facade, adds latency/failure to critical path
**Likelihood:** MEDIUM — extraction is a structural change to the runtime's critical path
**Mitigation:** Extract routing as an injectable `RouterPort` Protocol with `None` default (in-process). Define fallback policy for router service unavailable. Keep `active_task_router.py` in-process. Run all 9 gates with `router=None` to confirm no regression.

### Risk 5: QQBot channel duplicating WeCom service logic instead of abstracting shared concerns
**Impact:** MEDIUM — creates maintenance burden, divergence bugs, and makes future channel additions harder
**Likelihood:** HIGH — the WeCom service has significant channel-generic logic mixed with channel-specific code
**Mitigation:** Extract channel-generic logic (idempotency, delivery guard, active task router, output policy application) to `packages/platform-runtime/` or `packages/channel-core/` BEFORE building QQBot. QQBot gets its own normalization/protocol/sender modules. Add a test that asserts QQBot does not import from `wecom_service`.

---

## Sources

- `.planning/PROJECT.md` — M2 milestone context, target features, key constraints (lines 13-30)
- `docs/requirements/V2-PRD.md` — §5 non-goals (line 351-368), §7 safety/compliance (line 543-556), §11 M2 scope (line 636-643), §13 risks (line 688-708), §3.2 skill system (line 116-118), §3.3 routing (line 120-122), §4.1.2 adapter contract (line 209-213)
- `AGENTS.md` — safety/privacy rules (lines 30-37), coding rules (lines 39-45)
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — `AgentBackendMode` enum (line 12-15), `AdapterCapabilitySet` (line 18-33), `AgentBackendManifest` (line 36-45), `validate_agent_backend_manifest` (line 48-106)
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `ChannelAdapter` Protocol (line 208-219), `BackendAdapter` Protocol (line 222-239), `RunRuntime` Protocol (line 255-273), `ChannelCapabilitySet` (line 57-66), `ChannelDelivery` (line 88-95)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `RuntimeFeatureFlags` all default-OFF (line 13-19)
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — `DefaultAssistantOutputBoundary` regex rules (line 82-108)
- `packages/platform-runtime/src/platform_runtime/store.py` — `_reject_forbidden_payload_storage` (line 108-115), `_FORBIDDEN_FULL_TEXT_KEYS` (line 130-137)
- `packages/platform-runtime/src/platform_runtime/runtime.py` — `DefaultRunRuntime.create_run` (line 52-68), `DefaultRunRuntime.__init__` (line 28-50)
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` — `HermesBackendAdapter` (line 45-413), `HermesOneShotRunner` Protocol (line 27-30), truthful "unsupported" returns (line 158-168, 170-204)
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` — `build_hermes_oneshot_manifest` (line 17-37), `hermes_oneshot_capabilities` (line 40-58)
- `packages/backends/hermes/src/inkstatute_backends_hermes/config.py` — `HermesBackendConfig` (line 12-37)
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — `WeComChannelAdapter` (line 38-162), WeCom-specific imports (line 25-31), `secret_refs_configured` in health (line 137-152)
- `packages/channels/wecom/src/inkstatute_channels_wecom/config.py` — `WeComChannelConfig` (line 12-34)
- `services/wecom-service/src/wecom_service/agent_backend.py` — `select_agent_backend` (line 23-58), live acceptance bypass (line 49-51)
- `services/wecom-service/src/wecom_service/active_task_router.py` — `route_active_task_turn` (line 69-165), Chinese regex patterns (line 181-183)
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — `ContractLogReadModel.from_records` loads all records (line 45-127)
- `services/conversation-read-view/src/conversation_read_view/privacy.py` — `scrub_contract_payload` only checks `raw_payload` (line 9-43)
- `services/conversation-read-view/src/conversation_read_view/api.py` — `handle_get` routes (line 11-58), feedback status 400 constraint (line 36-47)
- `packages/contract-test-suite/tests/test_agent_adapter_contract.py` — provider_model fixture validation (line 52-58), schema neutrality assertion (line 60-77)
- `packages/contract-test-suite/tests/test_thin_layer_boundaries.py` — `assert_feedback_human_review_safety` (line 67-77), platform contract import boundary (line 12-20)
- `scripts/run_v2_gates.py` — 9 gate definitions (line 63-128), PYTHONPATH per gate (line 51-61), `compileall` paths (line 110-127)
- `.planning/ROADMAP.md` — v1.5 closure status (line 12-13), 479 tests green (line 31)
- `.planning/research/PITFALLS.md` (v1.5) — Pitfall 3 PYTHONPATH regression history (line 73-79), Pitfall 1 production wiring false positive pattern (line 13-39)
