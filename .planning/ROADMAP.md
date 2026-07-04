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
- Active **v1.6 M2 Multi-Backend & Platform Extensions** - Phases 36-44. Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate safety for all new packages.

## Current Milestone: v1.6 M2 Multi-Backend & Platform Extensions

**Goal:** Extend the platform beyond Hermes-only by proving agent-backend-neutral contracts (Codex + provider_model prototypes), normalizing routing as an independent service, exposing skill metadata and operational read views, completing conversation-read-view, and adding a second channel (QQBot) to prove ChannelAdapter portability — while keeping all 9 existing V2 gates green and V2 human-gate evidence stable.

**Requirements:** `.planning/REQUIREMENTS.md`

## Phases

- [x] **Phase 36: M2 Pre-Implementation Safety** - Cross-cutting safety measures (selection gate bypass fix, contract freeze, privacy scrub unification, feature flags, output boundary rules) before any M2 feature code.
- [x] **Phase 37: Skill Registry Read** - Read-only Skill Registry exposing Hermes skill metadata as NeutralSkillDescriptor records with list/get/search and well-known discovery endpoint.
- [x] **Phase 38: Router Service** - Standalone router library injected into hermes-contract-layer mapper, producing RouteDecision events with RULE and SKILL routing modes.
- [x] **Phase 39: Codex Adapter Prototype** - Codex backend adapter proving BackendAdapter contract portability via codex exec subprocess with manifest validation and minimal submit_run flow.
- [x] **Phase 40: Provider Model Adapter Prototype** - Direct provider_model adapter via AsyncOpenAI lazy SDK import, plus output boundary fixture tests for both new backends.
- [x] **Phase 41: Conversation Read-View Completion** - Cursor-based pagination, time-range/dimension filters, trace reconstruction, CSV/JSON export, and read-time privacy scrubbing.
- [x] **Phase 42: Admin Console API** - Read-only Admin Console API with static token auth, sessions/tasks/feedback/gates/health views, and field allowlist excluding secrets.
- [x] **Phase 43: QQBot Channel Loop** - Channel-generic logic extraction, QQBot ChannelAdapter implementation, and fixture-driven receive→ACK→adapter→reply→card→feedback loop proof.
- [x] **Phase 44: M2 Gate Integration & Full Suite Verification** - New gates for all 6 M2 packages, meta-test for full directory coverage, and all existing gates verified green.

## Status

**Status:** PLANNING — 9 phases defined (36-44), 22 requirements mapped, 0 phases started.

## Phase Details

### Phase 36: M2 Pre-Implementation Safety

**Goal:** Operator can verify that all cross-cutting safety measures (selection gate bypass fix, contract freeze, privacy scrub unification, M2 feature flags default-OFF, output boundary rules, contract-count assertions) are in place before any M2 feature code is written, protecting the 479-test V2 gate suite and parallel V2 human gates.
**Depends on:** v1.5 completion (Phase 35)
**Requirements:** SAFETY-01, SAFETY-02, SAFETY-03, SAFETY-04, SAFETY-05, SAFETY-06
**Success Criteria** (what must be TRUE):

1. Operator can run a test proving `select_agent_backend` enforces `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready` metadata, preventing prototype adapters from serving live WeCom turns during V2 human gates.
2. Operator can run a contract-count assertion test that fails if `BackendAdapter` Protocol method count, `AdapterCapabilitySet` field count, or `ChannelAdapter` Protocol method count changes from the v1.5 baseline, preventing contract drift during M2.
3. Operator can run a test proving `_FORBIDDEN_FULL_TEXT_KEYS` is unified between `store.py` and `privacy.py`, includes new backend field names (`prompt_content`, `completion_text`, `function_call_result`, `tool_output`), and that `scrub_contract_payload` is applied to every API response path.
4. Operator can run a test proving all M2 feature flags (`router_service_enabled`, `skill_registry_enabled`, `admin_api_enabled`, `qqbot_channel_enabled`, `codex_backend_enabled`, `provider_model_backend_enabled`) default to `False` in `RuntimeFeatureFlags`.
5. Operator can run a "contract freeze" baseline hash test comparing `packages/platform-contract/` schema files against the v1.5 baseline, failing if any schema file is modified during the V2 human gate period.

**Plans:** TBD

### Phase 37: Skill Registry Read

**Goal:** Operator can query a read-only Skill Registry that exposes Hermes skill metadata as `NeutralSkillDescriptor` records with list, get, search, and well-known discovery endpoint operations.
**Depends on:** Phase 36
**Requirements:** SKILL-01, SKILL-02
**Success Criteria** (what must be TRUE):

1. Operator can query the Skill Registry with `list_skills`, `get_skill`, and `search` operations (filter by tag, category, name substring) and receive `NeutralSkillDescriptor` records derived from Hermes skill metadata.
2. Operator can fetch `/.well-known/agent-skills/index.json` from the Skill Registry and receive skill name, description, and URL for discovery per the Cloudflare agent-skills-discovery convention.
3. Operator can verify the Skill Registry is read-only (no write, update, or delete operations) and that the `skill_registry_enabled` feature flag defaults to `False`.

**Plans:** TBD

### Phase 38: Router Service

**Goal:** Operator can inject a standalone router library into `hermes-contract-layer/mapper.py` that produces `RouteDecision` events with the same JSONL shape as the inline implementation, supporting RULE and SKILL routing modes with a `None` default that preserves in-process fallback behavior.
**Depends on:** Phase 37 (Skill Registry provides metadata for SKILL routing)
**Requirements:** ROUTER-01, ROUTER-02
**Success Criteria** (what must be TRUE):

1. Operator can inject the standalone router library into `hermes-contract-layer/mapper.py` and verify that `RouteDecision` events retain the same JSONL shape as the inline implementation, with a `None` default that preserves in-process fallback behavior and all 9 V2 gates staying green.
2. Operator can configure `RouteMode.RULE` and `RouteMode.SKILL` routing modes in the router service, with stateless skill lookup from the Skill Registry and intent classification via keyword/regex, producing normalized `RouteDecision` records.
3. Operator can verify that `router_service_enabled` defaults to `False` and that the router is injectable as a `RouterPort` Protocol with fallback policy for router unavailable.

**Plans:** TBD

### Phase 39: Codex Adapter Prototype

**Goal:** Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `codex exec --json` subprocess.
**Depends on:** Phase 36
**Requirements:** ADAPTER-01
**Success Criteria** (what must be TRUE):

1. Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter that returns a valid `AgentBackendManifest` with `production_ready: false` and `no_channel_io: true`.
2. Operator can run a capability probe against the Codex adapter and verify it passes, returning `AdapterCapabilitySet` consistent with the v1.5 baseline field count.
3. Operator can run a fixture-driven `submit_run → AgentResult` flow through the Codex adapter via `codex exec --json` subprocess and verify the result maps to the platform contract `AgentResult` schema with error normalization on first failure.

**Plans:** TBD

### Phase 40: Provider Model Adapter Prototype

**Goal:** Operator can configure `agent_backend.mode=provider_model` and the runtime selector routes to a direct provider_model adapter prototype via `AsyncOpenAI` lazy SDK import, and output boundary fixture tests prove both new backends block or rewrite backend noise before delivery.
**Depends on:** Phase 39
**Requirements:** ADAPTER-02, ADAPTER-03
**Success Criteria** (what must be TRUE):

1. Operator can configure `agent_backend.mode=provider_model` and the runtime selector routes to a provider_model adapter that returns a valid `AgentBackendManifest` with `invocation_mode="direct_llm"` and `production_ready: false`.
2. Operator can run a fixture-driven `submit_run → AgentResult` flow through the provider_model adapter via `AsyncOpenAI` lazy SDK import and verify the package imports cleanly without the SDK installed.
3. Operator can run output boundary fixture tests proving Codex and provider_model backend noise (function call traces, model names, API errors, rate-limit notices) is blocked or rewritten before delivery to any channel.

**Plans:** TBD

### Phase 41: Conversation Read-View Completion

**Goal:** Operator can query `conversation-read-view` with cursor-based pagination, time-range and dimension filters, trace reconstruction by `trace_id`, and CSV/JSON export — with read-time privacy scrubbing applied to all new endpoints.
**Depends on:** Phase 36
**Requirements:** READVIEW-01, READVIEW-02, READVIEW-03
**Success Criteria** (what must be TRUE):

1. Operator can query `conversation-read-view` list endpoints with cursor-based pagination, time-range filters (`from`, `to`), and dimension filters (`user_id`, `channel`, `status`), with enforced max result limits preventing unbounded memory usage.
2. Operator can query `conversation-read-view` by `trace_id` and receive all related events (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent) reconstructed in occurrence order.
3. Operator can export conversation-read-view query results as CSV or JSON and verify that all new endpoints apply read-time privacy scrubbing to response payloads.
4. Operator can run backward-compatibility tests proving existing endpoint response shapes are unchanged after the read-view extension.

**Plans:** TBD

### Phase 42: Admin Console API

**Goal:** Operator can authenticate to a read-only Admin Console API via a static token from env and query sessions, tasks, feedback, gates, and health views with filtering and pagination, with a field allowlist that excludes secret references.
**Depends on:** Phase 41 (Admin Console API reuses `ContractLogReadModel` from conversation-read-view)
**Requirements:** ADMIN-01, ADMIN-02
**Success Criteria** (what must be TRUE):

1. Operator can authenticate to the Admin Console API via a static token from env and query sessions, tasks, feedback, gates, and health views with filtering and pagination, receiving read-only responses.
2. Operator can verify that Admin Console API health/status views use a field allowlist that excludes secret reference names, config paths, `secret_refs_configured` maps, and `api_base_url` values — only exposing `secrets_configured: true/false`.
3. Operator can verify that `admin_api_enabled` defaults to `False` and that the Admin Console API runs `run_v2_gates.py --json-summary` via subprocess for gate status views without importing gate internals.

**Plans:** TBD

### Phase 43: QQBot Channel Loop

**Goal:** Operator can verify that channel-generic logic is extracted from `wecom-service` into a shared package, and that a QQBot channel adapter implements the `ChannelAdapter` Protocol with a fixture-driven receive→ACK→adapter→reply→card→feedback loop proving ChannelAdapter portability.
**Depends on:** Phase 36
**Requirements:** QQBOT-01, QQBOT-02, QQBOT-03
**Success Criteria** (what must be TRUE):

1. Operator can verify that channel-generic logic (idempotency, delivery guard, active task router, output policy) is extracted from `wecom-service` into a shared package, and that QQBot does not import directly from `wecom_service`.
2. Operator can configure `channel=qqbot` and the runtime routes to a QQBot channel adapter that implements the `ChannelAdapter` Protocol (6 methods), handles receive (single mode), send (text), and callback verification.
3. Operator can run a fixture-driven QQBot loop proof showing receive → ACK → adapter → reply → card → FeedbackEvent end-to-end with idempotency, proving ChannelAdapter portability beyond WeCom.
4. Operator can verify that `qqbot_channel_enabled` defaults to `False` and that QQ Bot feedback maps to existing `FeedbackEvent.source` enum values without adding new enum values.

**Plans:** TBD

### Phase 44: M2 Gate Integration & Full Suite Verification

**Goal:** Operator can run a V2 gate suite that includes new gates for each M2 package/service, with all 9 existing gates staying green and a meta-test asserting every `packages/*/src` and `services/*/src` directory is covered by a gate.
**Depends on:** Phase 37, Phase 38, Phase 39, Phase 40, Phase 41, Phase 42, Phase 43
**Requirements:** GATE-01
**Success Criteria** (what must be TRUE):

1. Operator can run new V2 gates for each M2 package/service (codex, provider_model, router-service, skill-registry, admin-console-api, qqbot) and verify they pass with fixture-driven tests.
2. Operator can run all existing V2 gates and verify they stay green with no regressions after all M2 features are merged.
3. Operator can run a meta-test asserting every `packages/*/src` and `services/*/src` directory is covered by a gate, failing if any directory is uncovered.

**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 36. M2 Pre-Implementation Safety | 3/3 | Complete | Safety gates, contract freeze, feature flags |
| 37. Skill Registry Read | 3/3 | Complete | Skill Registry with list/get/search |
| 38. Router Service | 3/3 | Complete | Router library with RULE/SKILL modes |
| 39. Codex Adapter Prototype | 3/3 | Complete | 596 tests, 12 gates |
| 40. Provider Model Adapter Prototype | 3/3 | Complete | 641 tests, 13 gates |
| 41. Conversation Read-View Completion | 3/3 | Complete | 747 tests, 13 gates |
| 42. Admin Console API | 3/3 | Complete | 860 tests, 14 gates |
| 43. QQBot Channel Loop | 3/3 | Complete | 921 tests, 15 gates |
| 44. M2 Gate Integration & Full Suite Verification | 3/3 | Complete | 969 tests, 19 gates |

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFETY-01 | 36 | Satisfied |
| SAFETY-02 | 36 | Satisfied |
| SAFETY-03 | 36 | Satisfied |
| SAFETY-04 | 36 | Satisfied |
| SAFETY-05 | 36 | Satisfied |
| SAFETY-06 | 36 | Satisfied |
| SKILL-01 | 37 | Satisfied |
| SKILL-02 | 37 | Satisfied |
| ROUTER-01 | 38 | Satisfied |
| ROUTER-02 | 38 | Satisfied |
| ADAPTER-01 | 39 | Satisfied |
| ADAPTER-02 | 40 | Satisfied |
| ADAPTER-03 | 40 | Satisfied |
| READVIEW-01 | 41 | Satisfied |
| READVIEW-02 | 41 | Satisfied |
| READVIEW-03 | 41 | Satisfied |
| ADMIN-01 | 42 | Satisfied |
| ADMIN-02 | 42 | Satisfied |
| QQBOT-01 | 43 | Satisfied |
| QQBOT-02 | 43 | Satisfied |
| QQBOT-03 | 43 | Satisfied |
| GATE-01 | 44 | Satisfied |

**Coverage: 22/22 requirements mapped (100%)**

---

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
