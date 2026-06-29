# Requirements: 墨律 InkStatute

**Defined:** 2026-06-27  
**Source of Truth:** `docs/requirements/V2-PRD.md`  
**Core Value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

## Active V2 Requirements

Requirements for the current V2 milestone. Retired product V1 is not an active requirement source.

### Platform Boundary and Sequencing

- [x] **REQ-v2-thin-contract-layer**: InkStatute V2 must be a thin platform contract, WeCom channel service, and agent adapter layer around enabled agent backends, with Hermes lawfirm as the first production agent backend and no platform-core dependency on Hermes internals.
  - InkStatute owns WeCom receive/send for ordinary users.
  - Hermes remains the first V2 agent backend adapter, not the permanent platform or channel boundary.
  - V2 adds contract schemas, hook-based normalization, contract logs, read views, feedback normalization, contract tests, and lawyer trial support.
  - V2 adds WeCom service, agent adapter contracts, Hermes bootstrap/version boundaries, and assistant output policy before live WeCom acceptance.
  - V2 does not rebuild Hermes core, session storage, router, skill registry, MCP registry, or model gateway.
  - The V1 full-stack platform scope is not treated as an active requirement source.

- [x] **REQ-inkstatute-wecom-service**: V2 must own the WeCom receive/send service instead of using Hermes gateway as the ordinary user channel.
  - Receives WeCom callbacks/events/messages, verifies/decrypts where required, dedupes retries, and returns ACK within the channel timeout.
  - Normalizes text, file, image, voice, and button callback events into AgentTurn or FeedbackEvent inputs.
  - Sends legal assistant text, markdown-compatible text, files, images, template cards, and InkStatute-owned business status/service notices.
  - Handles WeCom access token refresh, media download/upload references, send retries, delivery errors, and idempotency without committing secrets or raw payloads.
  - Receives feedback callbacks directly and creates FeedbackEvent records; Hermes feedback.jsonl remains a compatibility/migration input only.
  - Does not perform agent reasoning; it dispatches AgentTurn to the selected agent backend adapter.

- [x] **REQ-agent-backend-adapter-contract**: V2 must define a backend-neutral agent adapter contract and runtime mode selector so Hermes, future Codex, and future direct provider-model backends can attach through the same platform contract.
  - Defines `agent_backend.mode` values: `hermes`, `codex`, and `provider_model`.
  - V2 production scope requires Hermes mode only; Codex/provider-model modes are contract-compatible future modes and must not be blocked by schema or config assumptions.
  - Adapter manifests include adapter name/version, backend version, hook/event support, invocation mode, feedback target support, session read support, artifact return support, and no-channel-io capability.
  - Adapter input/output maps to AgentTurn, AgentResult, ExecutionTrace, RouteDecision, FeedbackEvent, and output-policy events without legal-only top-level fields.
  - Contract tests include non-Hermes synthetic fixtures to prevent platform core coupling to Hermes paths, hook names, profile layout, or WeCom-only fields.

- [x] **REQ-hermes-adapter-bootstrap**: Hermes mode must be reproducible on a new server through a low-coupling adapter bootstrap path.
  - Supports reusing an existing Hermes install by detecting Hermes version, hook capability, agent invocation capability, profile path, and contract log path.
  - Supports new-server Hermes mode by installing or locating a supported Hermes version, applying a sanitized lawfirm profile bundle, linking hooks/agent adapter, restoring skills/MCP/scripts/SOUL config, and running health checks.
  - Maintains a Hermes compatibility matrix with verified versions, required hook/event/agent-invocation capabilities, config switches, and fallback behavior for version drift.
  - Runtime secrets, WeCom key/secret/token, model keys, databases, logs, feedback payloads, customer documents, and raw legal payloads are not committed and are injected through external env/secret management.
  - Copying the current live lawfirm profile is allowed only as a source for generating a sanitized bundle, not as a raw repository artifact.

- [x] **REQ-assistant-output-boundary**: InkStatute WeCom service must present a pure lawyer assistant bot to ordinary users by filtering all user-facing outbound messages through a platform-owned output boundary.
  - Blocks or rewrites Hermes/gateway lifecycle messages, update/self-update prompts, slash command/help/status/credits/insights notices, memory/tool progress, dangerous command approval, delivery failure debug text, ADMIN_NOTICE, stack traces, internal paths, commands, tokens, and profile/runtime details.
  - Allows legal business replies, clarifying questions, business-level progress messages, files/artifacts, feedback cards, and InkStatute-owned service maintenance notices.
  - Does not semantically rewrite legal conclusions, citations, factual assumptions, risk judgments, or user-provided case facts.
  - Must operate at InkStatute WeCom service send boundary; Hermes agent adapter must not send directly to ordinary WeCom users.
  - Produces privacy-safe audit evidence for blocked/rewritten output-policy events.

- [ ] **REQ-v2-development-order**: Implement V2 in the PRD order: schemas first, then testing, then Hermes shadow recording, then WeCom feedback loop, then read/feedback services, then acceptance validation.
  - Step 1 delivers platform-contract schemas, async state machine, error codes, JSON Schema/Python bindings, and fixtures.
  - Step 2 delivers contract-test-suite framework, golden examples, synthetic task runner, and CI job.
  - Step 3 delivers hermes-contract-layer minimum hook, mapper, and event writer.
  - Step 4 delivers InkStatute WeCom service, agent backend adapter contract, Hermes bootstrap/version matrix, and assistant output boundary.
  - Step 5 deploys WeCom service + Hermes agent adapter and confirms WeCom task-to-agent-to-reply-to-card-to-feedback-to-FeedbackEvent loop.
  - Step 6 delivers conversation-read-view minimum API.
  - Step 7 delivers feedback-service normalization, dedupe, classification, and skill_candidate generation.
  - Step 8 completes contract CI and composability validation.
  - Step 9 runs the five-workday lawyer trial and metrics collection.

- [x] **REQ-implementation-risk-resolution**: Resolve V2 implementation risks that do not block PRD finalization but do block development completion.
  - Confirm Hermes hook execution order, especially `contract_result_recorder` after `response_filter`.
  - Confirm whether Hermes has an inbound hook point, or document `agent:end` reverse-inference limits for AgentTurn content.
  - Confirm message_id stability across response_filter, template cards, and feedback callbacks.
  - Define long-task status source mapping to queued, running, waiting_for_user, succeeded, failed, cancelled.
  - Define feedback target, feedback idempotency, raw payload retention, storage, and redaction rules.
  - Include non-happy-path fixtures for route errors, long-task failures, repeated feedback clicks, and non-legal tasks.
  - Ensure feedback-service cannot accidentally trigger automatic legal skill modification.

### Platform Contract

- [x] **REQ-platform-contract-package**: Provide a pure-definition platform-contract package with five event schemas, async task state machine, error codes, fixtures, and bindings.
  - Defines AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision schemas.
  - Provides JSON Schema and Python types first; TypeScript types may follow after V2 priority work.
  - Defines async task states: queued, running, waiting_for_user, succeeded, failed, cancelled.
  - Defines contract_error, runtime_error, and channel_error categories.
  - Contains no runtime service logic.
  - Can be consumed by hermes-contract-layer, conversation-read-view, feedback-service, and contract-test-suite.

- [x] **REQ-contract-event-schemas**: The five contract objects must be modeled as platform events, not database table definitions, and must support traceable end-to-end relationships.
  - AgentTurn includes required turn_id, conversation_id, channel, user_id, message_type, received_at.
  - AgentResult includes required result_id, turn_id, status, reply_type and optional artifacts, execution_trace, route_mismatch, skill_candidate, error, metadata.
  - FeedbackEvent includes required feedback_id, turn_id, conversation_id, user_id, source, event_type, status, created_at.
  - ExecutionTrace includes V2-required trace_id, turn_id, started_at, ended_at, active_skill_name, matched_registered_skill, occurred_at, ingested_at, seq.
  - RouteDecision includes required route_decision_id, turn_id, primary_skill, confidence, mode, created_at.
  - All events can be related through turn_id, conversation_id, feedback_target, result_id, and artifact identifiers.
  - Legal-specific fields are placed under industry_context or other extension containers, not top-level required schema fields.

### Contract Verification

- [x] **REQ-contract-test-suite**: Provide a contract test suite that validates schemas, replays fixtures, verifies event relationships, and enforces composability in CI.
  - Schema validation covers required fields, enums, and invalid values for all five schemas.
  - Fixture replay validates golden examples from Hermes hook output.
  - Relationship checks verify message-to-task-to-route-to-response-to-feedback continuity with a breakage rate no greater than 5%.
  - Contract log coverage for real tasks is at least 95% for paired AgentTurn and AgentResult events.
  - CI fails when schemas are inconsistent, required fields are missing, relationships break beyond tolerance, or legal fields leak into top-level required platform schema fields.
  - CI includes non-legal synthetic tasks for finance/tax, engineering, and education scenarios.

- [x] **REQ-composability-validation**: The platform contract layer must support arbitrary enabled skill, gate, MCP, tool, and output-constraint combinations without platform core changes or legal-field coupling.
  - Synthetic tasks include simple legal Q&A, contract review, legal retrieval, route mismatch, WeCom feedback, long-task failure, and non-legal tasks.
  - Each synthetic task produces schema-valid events with intact relationships.
  - Non-legal tasks do not require legal-specific fields.
  - Legal-specific data remains in industry_context or profile-specific extensions.
  - Tests fail if platform core code or top-level required schemas depend on lawfirm-only fields.

### Hermes Shadow Integration

- [x] **REQ-hermes-contract-layer**: Add a hook-based shadow contract layer to Hermes lawfirm that maps internal Hermes context and outputs into standard contract events without changing legal/business outbound behavior.
  - Provides a `contract_result_recorder` hook on `agent:end` after `response_filter`.
  - Maps final replies into AgentResult and writes contract logs.
  - Records occurred_at, ingested_at, and a monotonic sequence for every contract event.
  - Uses agent:end context and session context to infer AgentTurn where no agent:start event exists.
  - Does not alter Hermes legal/business reply content, router behavior, skill execution, MCP behavior, or model configuration.
  - Coexists with the separate InkStatute WeCom service and assistant output boundary, which may block or rewrite backend meta/gateway/update/command notices before ordinary WeCom delivery.
  - Includes mapper and event log writer code under `services/hermes-contract-layer`.
  - Contract-test-suite can replay hook output into valid standard events.

- [x] **REQ-observability-and-replay**: Contract events must be observable, replayable, and auditable enough to diagnose task flow, failures, routing, tools, gates, artifacts, and feedback.
  - Every AgentResult includes or links to ExecutionTrace.
  - ExecutionTrace can connect messages, tasks, routes, tool calls, gates, artifacts, errors, and feedback.
  - Each contract event includes occurred_at, ingested_at, and seq.
  - Test coverage includes out-of-order replay.
  - Failed long tasks expose failure stage through ExecutionTrace.errors and AgentResult.status=failed.
  - Contract logs support coverage reporting and relationship integrity checks.

### WeCom Loop and Services

- [x] **REQ-wecom-daily-test-loop**: Preserve and validate the existing WeCom daily-use loop while shadow-recording contract events and normalized feedback.
  - WeCom remains the primary V2 acceptance channel.
  - InkStatute WeCom service receives incoming lawyer tasks and returns channel acknowledgment within the WeCom timeout window.
  - InkStatute WeCom service dispatches AgentTurn to Hermes agent adapter and sends legal business text, files, and template cards after assistant output boundary.
  - contract_result_recorder records AgentResult events after Hermes prepares the response.
  - Template card feedback is captured by InkStatute WeCom service and normalized into FeedbackEvent.
  - Existing Hermes lawfirm WeCom template-card feedback behavior is used as migration evidence, but not as the target ordinary user channel.
  - Ordinary WeCom users do not see Hermes gateway/update/self-update/command/help/credits/insights/memory/tool-progress/debug notices.
  - QQ Bot and WeChat remain non-V2 acceptance channels but are not broken.

- [x] **REQ-conversation-read-view**: Build a read-only conversation and task view from contract logs, using Hermes sessions only as a fallback read model rather than an authoritative new session store.
  - Reads contract event logs as the primary source.
  - Provides GET /conversations/{id}, GET /tasks/{id}, and GET /feedback?status=pending as the V2 minimum API set.
  - Supports lookup by conversation_id, task_id, and trace_id.
  - May use sessions.db only through an explicitly Hermes-specific adapter and only to fill gaps.
  - Does not create an independent authoritative conversation database.

- [x] **REQ-feedback-service**: Normalize InkStatute WeCom feedback callbacks and compatibility Hermes feedback.jsonl/preview data into FeedbackEvent records, classify feedback, dedupe repeated callbacks, and produce pending queues for human review.
  - Reads InkStatute WeCom feedback callback records as the primary source.
  - Reads Hermes feedback.jsonl and pending_previews.jsonl only as compatibility/migration input references.
  - Produces FeedbackEvent records with source, event_type, action, status, raw_payload_ref, and association to turn/result/conversation where available.
  - Dedupes repeated button clicks, network retries, and repeated shim writes using an idempotency key.
  - Classifies feedback into rating, correction, fact_missing, citation_error, route_mismatch, format_issue, compliance_issue, and skill_candidate categories.
  - Marks route_mismatch feedback and records skill_candidate evidence.
  - Does not change the feedback channel or template card dispatch flow.
  - Does not automatically modify legal conclusion skills.

### Safety and Acceptance

- [x] **REQ-security-privacy-baseline**: V2 must enforce minimum privacy, security, and legal-work-product safeguards without adding a complete M3 security platform.
  - Customer materials, case facts, and contract content are confidential by default.
  - Contract logs reference raw payloads using raw_payload_ref and avoid storing sensitive full text by default.
  - Logs avoid complete ID numbers, phone numbers, bank accounts, addresses, and other sensitive values.
  - Secrets are referenced through Hermes existing secret management or environment variables, not stored in plaintext.
  - Admin-only notices and backend/gateway/system/update/command notices are not exposed to ordinary users.
  - Legal outputs preserve the working-draft-for-lawyer-review principle.
  - High-risk feedback does not automatically alter legal conclusions, statute references, cause-of-action judgments, jurisdiction judgments, or liability conclusions.
  - skill_candidate.requires_human_review is true for V2 skill-candidate flows.

- [ ] **REQ-lawyer-trial-acceptance**: Validate V2 through a five-workday real lawyer trial using the Hermes lawfirm WeCom bot.
  - At least one lawyer uses the WeCom bot continuously for five workdays.
  - At least 15 real tasks are completed, with at least 12 producing clear business output.
  - At least three task categories are covered from contract review, legal retrieval Q&A, document drafting, judgment analysis, and case analysis.
  - Long tasks over 60 seconds have success rate at least 80%.
  - Ordinary tasks have end-to-end success rate at least 85%.
  - Feedback capture rate is at least 60%.
  - Positive feedback share is at least 60%; otherwise a categorized repair plan exists.
  - Negative feedback has a recorded response action within 48 hours.
  - route_mismatch count is no more than 3, and each item has a structured skill_candidate or routing_rule_candidate.

## Platform Foundation (v1.1) Requirements

Requirements for the new milestone (GSD Phase 09–13). Architecture basis: `.planning/drafts/agent-platform-north-star.md`. Execution plan: `.planning/drafts/agent-platformization-plan-v5.md`. These are autonomous-buildable (code + tests + fixtures). Live cutover and the Phase 8 lawyer trial are human gates outside the autonomous path.

### Platform Core Contracts

- [x] **REQ-platform-north-star**: The platform must be designed to four backend-, channel-, and industry-neutral interface contracts so channels, agent backends, and solutions are independently swappable.
  - Defines `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, and `RunRuntime` as the stable seams.
  - The lawyer assistant is the first solution, Hermes the first backend, WeCom the first channel; none defines the platform core.
  - Platform core must not depend on Hermes paths, WeCom protocol internals, or legal fields.
  - The North Star architecture is recorded under `docs/architecture/` and is authoritative for platform shape.

- [x] **REQ-platform-contract-extension**: Extend `platform-contract` additively with new platform resources/events without breaking V2 schemas.
  - Adds `ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest` (+ neutral skill/mcp descriptors), `BotInstance`, `ChannelBinding`.
  - `Run.status` reuses the existing `AsyncTaskState` enum.
  - `ArtifactRecord` is a top-level ref distinct from nested `AgentResult.artifacts`.
  - `AdapterCapabilitySet` is extended backward-compatibly; `validate_agent_backend_manifest` stays valid.
  - Relationship replay proves `ChannelMessage → AgentTurn → Run → RunEvent/RunStep → AgentResult/ArtifactRecord → ChannelDelivery → FeedbackEvent`.

- [x] **REQ-boundary-scan-allowlist**: Boundary scans for neutral packages must use an allowlist policy, not a blanket word ban.
  - Neutral packages forbid private Hermes paths, WeCom protocol payload fields, lawfirm-only/legal-only top-level required fields, raw payloads, and secret values.
  - Backend-mode enum values `hermes`/`codex`/`provider_model` are allowed in adapter contracts.
  - Concrete names are allowed inside concrete packages (`channels/wecom`, `backends/hermes`, `solutions/lawfirm`).
  - A non-legal fixture must validate without lawfirm assumptions.

### Platform Runtime

- [x] **REQ-platform-run-runtime**: Provide a Python-first `RunRuntime` that owns run lifecycle, session, output boundary, audit, and feature flags through injected ports.
  - Implements create/poll/stream/cancel/approve.
  - Speaks the `BackendAdapter` Protocol and never embeds backend-specific logic.
  - Persists contract logs append-only and `raw_payload_ref`-first.
  - All lanes are gated by default-OFF feature flags.

- [x] **REQ-runtime-embeddability**: `RunRuntime` must be an embeddable library with no hard dependency on a network server or any specific channel.
  - Constructs with zero channels (embedded mode) and with no server.
  - Dependencies (backend, loader, channels, storage, output boundary, secret resolver, flags) are injected.
  - A server, a Tauri sidecar, or an Electron child process are thin hosts of the same library.
  - Local desktop/mobile runtime is not implemented this milestone, only kept possible.

- [x] **REQ-runlane-output-boundary**: Every run event/delta path must pass through the assistant output boundary before ordinary-user delivery.
  - Streamed tool/approval/gateway/meta/internal events never reach ordinary users.
  - Leak fixtures prove the boundary on the streaming lane.
  - The boundary does not semantically rewrite legal business conclusions.
  - Blocked/rewritten events are recorded as sanitized summaries only.

### Hermes Backend Adapter

- [x] **REQ-hermes-backend-adapter**: Implement Hermes as a `BackendAdapter`, defaulting to subprocess one-shot, with `/v1/runs` as an opt-in lane.
  - Passes `BackendAdapter` Protocol conformance tests.
  - One-shot declares reduced capabilities (no cancel/live-update/streaming/parallel).
  - The `/v1/runs` lane is behind a default-OFF flag.
  - Materializes the bound solution into a Hermes profile; the runtime never sees profile internals.

- [x] **REQ-adapter-capability-probe**: Provide a non-mutating startup capability probe for backends.
  - Uses `/health`, `/v1/capabilities`, `/v1/models`; never `GET /v1/runs/{id}`.
  - Returns a capability set mapped to `AdapterCapabilitySet`.
  - Probe failure falls back to one-shot with a sanitized audit reason.
  - Requires `no_channel_io=true` for ordinary-user backends.

- [x] **REQ-hermes-run-parity-spike**: Prove or refute that Hermes `/v1/runs` executes the lawfirm profile equivalently to one-shot before promotion.
  - Compares routing, skill/gate behavior, MCP/tool trace, artifacts, final user text, output policy, and state transitions on fixtures.
  - Covers legal Q&A, drafting+artifact, follow-up, route-mismatch, MCP task, and a non-legal task.
  - Failure keeps one-shot as the default lane.
  - Uses non-sensitive fixtures only.

### Channels and Clients

- [x] **REQ-channel-adapter-interface**: Define and implement the `ChannelAdapter` interface and wrap the existing WeCom primitives behind it.
  - The WeCom wrapper is behind a default-OFF flag and does not regress production behavior.
  - Channel adapters submit through `RunRuntime` and never call backends directly.
  - Inbound normalizes to `ChannelMessage`/`AgentTurn`/`FeedbackEvent`; outbound is `ChannelDelivery`.
  - Secret refs are isolated per `BotInstance`/`ChannelBinding`.

- [ ] **REQ-multichannel-fixture**: Prove a non-WeCom channel end-to-end to validate channel neutrality.
  - Provides a Web API + SSE channel passing end-to-end against fakes.
  - Per-channel delivery/feedback/idempotency/output-policy fixtures exist.
  - No production-grade requirement beyond passing fixtures.

- [ ] **REQ-client-embedding-surface**: Ship the platform API server, a TypeScript client SDK, and an embeddable web chat component.
  - `apps/platform_api` hosts `RunRuntime` via HTTP + SSE/WebSocket.
  - `packages/platform-sdk-ts` is generated deterministically from OpenAPI.
  - `apps/web_chat` renders `RunEvent` streaming and is embeddable by Tauri/Electron/Flutter webview.
  - Clients default to remote/thin; local runtime is reserved, not implemented.

### Solutions

- [x] **REQ-solution-loader**: Provide a `SolutionLoader` that validates, loads, and materializes solution packages with no undeclared side effects.
  - `validate`/`load`/`materialize_for` are the loader operations.
  - `materialize_for("hermes")` produces/refreshes a sanitized profile bundle.
  - The loader is enabled behind a default-OFF flag.

- [ ] **REQ-solution-backend-portability**: Solutions must be described in a backend-neutral format and materialized per backend.
  - Manifest holds `persona_ref`, neutral skill descriptors, MCP refs, output-policy overlay, eval fixtures, adapter config defaults, secret-name templates, and `industry_context` defaults.
  - No Hermes-runtime-shaped fields at the contract level.
  - The lawyer solution runs with zero new legal top-level fields in platform core.

- [ ] **REQ-solution-privacy-gate**: A solution privacy scan must reject any sensitive content in solution bundles.
  - Rejects secrets, logs, DBs, media, raw payloads, customer docs, and confidential artifacts.
  - Bundles are distributable only when sanitized.

- [ ] **REQ-nonlegal-solution-composability**: A non-legal demo solution must run through the same platform contracts with no platform-code change.
  - `demo_non_legal` passes composability gates.
  - Platform core stays industry-neutral; legal fields stay in `industry_context`.

## Deferred Beyond V2

### M2

- Codex adapter prototype.
- Direct provider-model adapter prototype.
- Independent Router Service normalization upgrade.
- Skill Registry reading and conversation-read-view completion.
- Admin Console API read-only surface.
- QQBot complete loop.

### M3

- Multi Agent Runtime Adapter productization.
- MCP Connector Registry and Model Provider Gateway.
- Web frontend.
- Complete security platform: encryption, tenancy, RBAC, retention/destruction, WORM audit logs, key rotation.

### M4

- Full Document Pipeline for Office editing, template inheritance, and style migration.
- Tauri desktop.
- Automatic Skill synthesis.

## Out of Scope

Explicitly excluded from V2 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Retired V1 platform scope | V2 PRD replaces V1 as the active requirement source. |
| Rebuilding Hermes core/runtime systems | V2 is an agent adapter layer around the existing Hermes lawfirm backend, not a Hermes fork. |
| Production Codex/provider-model adapters | V2 defines the agent backend adapter contract and mode shape; production implementation is deferred beyond V2. |
| Independent authoritative conversation database | V2 read APIs derive from contract logs; Hermes sessions are fallback only. |
| Full multi-channel gateway | V2 builds the minimum InkStatute WeCom service only. |
| Hermes gateway as ordinary user WeCom channel | V2 owns WeCom receive/send; Hermes gateway is migration evidence or non-user-facing operator tooling only. |
| Full Web UI or Tauri desktop | Deferred beyond V2; WeCom is the V2 acceptance channel. |
| Automatic legal skill modification | High-risk legal feedback must remain human-reviewed. |
| Raw legal payload storage in contract logs by default | Contract logs must prefer references and minimize sensitive content. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-platform-contract-package | Phase 1 | Complete |
| REQ-contract-event-schemas | Phase 1 | Complete |
| REQ-contract-test-suite | Phase 2 | Complete |
| REQ-implementation-risk-resolution | Phase 3 | Complete |
| REQ-hermes-contract-layer | Phase 4 | Complete |
| REQ-observability-and-replay | Phase 4 | Complete |
| REQ-inkstatute-wecom-service | Phase 5.5 | Complete |
| REQ-agent-backend-adapter-contract | Phase 5.5 | Complete |
| REQ-hermes-adapter-bootstrap | Phase 5.5 | Complete |
| REQ-assistant-output-boundary | Phase 5.5 | Complete |
| REQ-wecom-daily-test-loop | Phase 5 | Complete |
| REQ-conversation-read-view | Phase 6 | Complete |
| REQ-feedback-service | Phase 6 | Complete |
| REQ-composability-validation | Phase 7 | Complete |
| REQ-security-privacy-baseline | Phase 7 | Complete |
| REQ-v2-thin-contract-layer | Phase 7 | Complete |
| REQ-lawyer-trial-acceptance | Phase 8 | Pending |
| REQ-v2-development-order | Phase 8 | Pending |
| REQ-platform-north-star | Phase 09 | Planned |
| REQ-platform-contract-extension | Phase 09 | Planned |
| REQ-boundary-scan-allowlist | Phase 09 | Planned |
| REQ-platform-run-runtime | Phase 10 | Planned |
| REQ-runtime-embeddability | Phase 10 | Planned |
| REQ-runlane-output-boundary | Phase 10 | Planned |
| REQ-hermes-backend-adapter | Phase 11 | Planned |
| REQ-adapter-capability-probe | Phase 11 | Planned |
| REQ-hermes-run-parity-spike | Phase 11 | Planned |
| REQ-channel-adapter-interface | Phase 12 | Planned |
| REQ-multichannel-fixture | Phase 12 | Planned |
| REQ-client-embedding-surface | Phase 12 | Planned |
| REQ-solution-loader | Phase 13 | Planned |
| REQ-solution-backend-portability | Phase 13 | Planned |
| REQ-solution-privacy-gate | Phase 13 | Planned |
| REQ-nonlegal-solution-composability | Phase 13 | Planned |

**Coverage:**

- Active V2 requirements: 18 total (mapped to Phase 1–8)
- Platform Foundation (v1.1) requirements: 16 total (mapped to Phase 09–13)
- Total mapped: 34
- Unmapped: 0

---
*Requirements defined: 2026-06-27*
*Last updated: 2026-06-29 — added Platform Foundation (v1.1) milestone requirements for Phase 09–13*
