# Agent Platformization Plan (Codex Review Draft)

> Scope: next GSD milestone plan for moving InkStatute from the V2 lawyer WeCom bot validation shape into a reusable agent platform with solution packages. This draft reviews and supersedes `agent-platformization-plan-revised.md` without modifying production code.

---

## 1. Review Findings On The Revised Plan

### High

1. `agent-platformization-plan-revised.md:116` and `:199` blur three different privacy artifacts: repo-owned audit code, sanitized audit fixtures/summaries, and live runtime audit records. The repo can contain `runtime_audit.py`, schemas, tests, and redacted summary fixtures; live runtime audit JSONL, callback bodies, Hermes stdout/stderr, transcripts, media, DBs, and legal payloads must stay outside the repo.
2. `agent-platformization-plan-revised.md:127` makes the boundary scan impossible by banning `lawfirm` / `wecom` / `hermes` across `services/*`. Existing service names and Hermes adapter modules intentionally contain those terms. The scan must apply only to platform-neutral packages/schemas, while service and adapter packages are allowed to use implementation-specific names behind interfaces.
3. `agent-platformization-plan-revised.md:112` makes M0 "complete Phase 8 acceptance", which includes a five-workday lawyer trial. That would block platformization on a human-duration gate. M0 should unblock and protect the trial clock by proving live readiness; the five-workday trial evidence can continue as a separate human gate.
4. `agent-platformization-plan-revised.md:124-125` creates `packages/platform-core/` for "contracts + interfaces + fixture" and also puts new JSON Schema there. That fragments the existing `packages/platform-contract/` source of truth. New platform schemas should extend `platform-contract`; a new platform runtime/core package should import contracts, not redefine them.

### Medium

5. `agent-platformization-plan-revised.md:99` proposes capability probing via `GET /v1/runs/{id}` and "OPTIONS-style" probing. A non-mutating probe should prefer Hermes `/health`, `/v1/capabilities`, `/v1/models`, and static route/source checks. `GET /v1/runs/{id}` needs an existing run id; `POST /v1/runs` is a runtime validation, not a safe startup probe.
6. `agent-platformization-plan-revised.md:97` says Hermes should have no special code path, but `:103-104` preserves oneshot fallback. The correct boundary is "no Hermes-specific path in platform core"; Hermes-specific API server and oneshot behavior live inside the Hermes adapter.
7. `agent-platformization-plan-revised.md:152` says to move the WeCom implementation into `platform-core/channels/wecom/`. Moving a working live bridge/service is unnecessary risk. M3 should add channel interfaces and wrappers first, then migrate only after parity is proven.
8. `agent-platformization-plan-revised.md:83` adds `Artifact`, but V2 already has an `Artifact` nested in `AgentResult`. The new contract should be named `ArtifactRecord` or `ArtifactRef` if it is promoted to a top-level event/resource.
9. `agent-platformization-plan-revised.md:86` says `ChannelBinding` injects secrets. The contract must store only `secret_ref`, environment variable names, or KMS references; secret values are never contract data.
10. `agent-platformization-plan-revised.md:215` says TypeScript enters "business logic" while intending SDK/OpenAPI-only usage. M2 should explicitly keep Python as execution/runtime owner and TypeScript as client/API surface until a later approved phase changes that.

---

## 2. Milestone Definition

**Milestone name:** Agent Platformization Foundation

**Goal:** preserve the working V2 lawyer WeCom bot while extracting stable platform contracts, adapter interfaces, run runtime seams, and solution package boundaries that let InkStatute support more channels, agent backends, and industry packages without coupling the platform core to `lawfirm`, WeCom, or Hermes internals.

**Current baseline:**

- `origin/main` at `d81d934` has Phase 1-7 complete and Phase 8 in `human_needed`.
- V2 gates pass via `python scripts/run_v2_gates.py --json-summary`.
- WeCom live bridge currently uses InkStatute-owned ingress/egress plus Hermes one-shot subprocess, with task flow, active-task routing, delivery guard, runtime audit support, output policy, idempotency, and sender/normalization primitives.
- Hermes source contains `/v1/runs`, `/v1/runs/{id}/events`, `/v1/runs/{id}/approval`, `/v1/runs/{id}/stop`, `/v1/responses`, `/v1/chat/completions`, and `/v1/capabilities`, but platform code must treat those as Hermes adapter capabilities, not as InkStatute's public contract.

**Non-goals for this milestone:**

- Do not rebuild Hermes core, router, session storage, skill registry, MCP registry, or model gateway.
- Do not replace the live WeCom path before fresh UAT proves parity.
- Do not implement production Codex, Claude Code, OpenCode, or direct provider-model adapters beyond contract-compatible fixtures.
- Do not implement full Web, Tauri, Electron, Flutter, or mobile UIs.
- Do not build a full security platform, RBAC system, WORM audit store, or automatic legal skill synthesis.

---

## 3. Target Architecture

### 3.1 Platform Core

Platform core means the reusable, industry-neutral layer:

- `packages/platform-contract/`: all JSON Schema and generated/bound Python types for platform-level events/resources.
- Future `packages/platform-runtime/` or `packages/platform-core/`: dependency-light interfaces and pure orchestration primitives that import `platform-contract` rather than redefining schemas.
- Contract test suite gates for schema compatibility, relationship integrity, composability, privacy, and boundary checks.

The platform core must not depend on Hermes source paths, WeCom protocol internals, `lawfirm` profile files, legal-specific fields, customer payloads, or runtime secrets.

### 3.2 Channel Layer

Channel adapters normalize protocol-specific input/output into platform contracts:

- Inputs become `ChannelMessage` and, when appropriate, `AgentTurn` or `FeedbackEvent`.
- Outputs become `ChannelDelivery` records with policy result, idempotency key, channel message id, and sanitized error data.
- Bindings are represented by `BotInstance` + `ChannelBinding`, where secret values are always external references.

WeCom remains the first production channel. QQBot, WeChat, Feishu, Web API, Webhook, WebSocket, and SSE are contract targets until a phase explicitly productionizes one.

### 3.3 Agent Backend Adapter Layer

All backends implement one adapter interface:

- `submit_run`
- `get_run`
- `stream_events`
- `cancel_run`
- `submit_approval`
- artifact reference collection
- tool trace normalization
- session/memory capability declaration

Adapters declare capabilities, including `supports_async_runs`, `supports_streaming_events`, `supports_cancel`, `supports_approval`, `supports_live_task_update`, `supports_parallel_tasks`, `supports_artifact_refs`, `supports_tool_trace`, `supports_session_memory`, and `no_channel_io`.

Hermes, Codex, Claude Code, OpenCode, direct provider-model, and future in-house agents are adapter implementations. None own ordinary user channel IO.

### 3.4 Solution Packages

Solution packages are product/industry bundles loaded by the platform:

- prompts/profile/SOUL references
- skills and MCP references
- output policy overlays
- eval and contract fixtures
- bootstrap manifest
- adapter configuration defaults
- secret templates with names only

`solutions/lawfirm/` becomes the first solution package. It can reference Hermes lawfirm compatibility assets, but platform contracts and platform runtime must remain industry-neutral.

### 3.5 Storage And Audit

Use three distinct storage classes:

- Contract logs: append-only, privacy-minimized, `raw_payload_ref`-first, replayable.
- Read models: derived SQLite/Postgres-ready views, never the source of authority in this milestone.
- Runtime/operator audit: private deployment evidence outside the repo unless reduced into sanitized fixture/summary form.

Blocked/rewritten output policy events should be represented as sanitized contract/runtime summary records, not raw backend text dumps.

---

## 4. Contract Additions

All additions are backward-compatible and live under `packages/platform-contract/`.

Keep existing V2 contracts:

- `AgentTurn`
- `AgentResult`
- `FeedbackEvent`
- `ExecutionTrace`
- `RouteDecision`
- `AgentBackendManifest`

Add new schemas/types:

- `ChannelMessage`: normalized inbound channel message/event.
- `ChannelDelivery`: outbound delivery attempt/result after output policy.
- `Run`: platform run resource mapped from agent/backend execution.
- `RunEvent`: lifecycle, message delta, tool event, approval event, artifact event, failure/cancel event.
- `RunStep`: coarse execution step that can map to `ExecutionTrace.steps`.
- `ToolCall`: normalized tool invocation/result summary.
- `Approval`: approval request/response with human-action boundary.
- `ArtifactRecord`: top-level artifact resource/ref, distinct from existing nested `AgentResult.artifacts`.
- `Session`: platform session abstraction, not Hermes `state.db`.
- `Tenant` / `Workspace`: identity scope for later multi-tenant isolation.
- `SolutionPackageManifest`: package metadata and resource references.
- `BotInstance` / `ChannelBinding`: bot instance and channel binding with `secret_ref` only.

Rules:

- No required top-level legal fields.
- No required top-level Hermes, WeCom, or lawfirm fields.
- Raw payloads, customer documents, runtime logs, DB paths, and secret values are forbidden.
- Relationship tests must prove `ChannelMessage -> AgentTurn -> Run -> RunEvent/RunStep -> AgentResult/ArtifactRecord -> ChannelDelivery -> FeedbackEvent`.

---

## 5. Hermes Adapter Strategy

Hermes is a backend adapter, not a platform boundary.

### Capability Probe

Startup probe is non-mutating by default:

- Inspect adapter manifest.
- Check configured base URL/credentials are present via `secret_ref`.
- Query Hermes `/health` and `/v1/capabilities` when API server mode is enabled.
- Confirm endpoints advertised for runs, events, approval, stop, responses, chat completions, sessions, skills, and toolsets.
- Confirm adapter policy requires `no_channel_io=true`.

Runtime validation may create a synthetic run only in an explicit smoke test using non-sensitive fixture content.

### Invocation Preference

Preferred order:

1. Hermes `/v1/runs` when capability probe and smoke test pass.
2. Hermes `/v1/responses` only for compatible clients or stateful response workflows that do not need platform-native run control.
3. Hermes `/v1/chat/completions` only for compatibility/simple request paths.
4. Hermes subprocess one-shot fallback when API server mode is unavailable or unsafe.

Oneshot fallback must declare no cancel, no live update, no streaming progress, and no parallel task support. User-facing control-plane notices must stay honest about those limits.

### Adapter Boundary

Hermes-specific logic belongs in `services/hermes-contract-layer/` or a future Hermes adapter package. Platform core only sees the adapter interface and normalized run events.

---

## 6. GSD Roadmap

Use continued numbering to preserve V2 history: Phase 09-13, with M0-M4 as human-readable labels.

### M0 / Phase 09: Live WeCom Stability Gate

**Goal:** prove the current lawyer WeCom bot is safe to keep using before extracting platform layers.

**Implementation boundary:** no platform refactor, no runtime API migration, no schema expansion unless needed for sanitized evidence.

**Deliverables:**

- Fresh live UAT record for document+instruction plus follow-up during active task.
- Sanitized readiness report that proves quick ACK, recurring service-owned progress, explicit final/timeout/failure/incomplete state, no false `completed`, no Hermes meta leak, and fast active-task follow-up response.
- Clarified runtime audit policy: repo contains audit code/tests/sanitized summaries only; live audit records stay outside repo.

**Acceptance criteria:**

- `python scripts/run_v2_gates.py --json-summary` passes.
- Live UAT passes or remains explicitly blocked with reason.
- Existing 08-04 live bridge and oneshot path remain rollback-ready.

**Privacy boundary:** do not commit callback payloads, media, generated legal docs, Hermes transcripts, state DBs, logs, tokens, or raw legal text.

**Rollback:** keep/restart current 08-04 live bridge; freeze platformization if the live bot regresses.

### M1 / Phase 10: Contract And Boundary Extraction

**Goal:** define platform-neutral contracts and solution package manifests without moving live code.

**Deliverables:**

- New schemas/types in `packages/platform-contract/`.
- Contract fixtures for legal and non-legal tasks.
- Initial `solutions/lawfirm/` manifest with references only.
- Boundary tests that forbid legal/Hermes/WeCom terms in platform-neutral contracts and runtime core, while allowing them in solution packages and concrete adapter/service packages.
- ADR for platform layering, package naming, and contract extension rules.

**Acceptance criteria:**

- Existing V2 contracts remain valid.
- New schema validation and relationship replay pass.
- `lawfirm` package manifest contains no secrets, logs, DBs, media, raw payloads, or customer docs.
- Non-law fixture validates without platform code changes.

**Privacy boundary:** package manifests store references and secret names only.

**Rollback:** ignore new contracts/manifests; V2 services keep current behavior.

### M2 / Phase 11: Platform Run Runtime And API Facade

**Goal:** introduce a formal platform run interface while keeping Hermes oneshot fallback.

**Deliverables:**

- Python-first `RunRuntime` interface and in-memory/dependency-light implementation.
- Hermes adapter API-server lane using `/v1/runs` behind capability probe.
- Oneshot fallback lane with explicit reduced capability manifest.
- Platform API facade for create/poll/stream/cancel/approval/artifact refs.
- OpenAPI spec and generated TypeScript SDK/client types only; no TypeScript execution logic.

**Acceptance criteria:**

- Run create/poll/stream/cancel/approval tests pass against fake adapters and Hermes fixture adapters.
- Capability probe failures fall back to oneshot with audited reason.
- `tenant_id`, `workspace_id`, `session_id`, `bot_instance_id`, and `channel_binding_id` flow through run records.
- No raw payload or secret value enters Run logs.

**Privacy boundary:** auth tokens and payloads remain external; logs use refs and hashes.

**Rollback:** disable API-server lane and run via current oneshot task-flow path.

### M3 / Phase 12: Channel Interface And Client Embedding Surface

**Goal:** make WeCom one channel implementation under a shared channel interface, then add a Web API/SSE fixture channel.

**Deliverables:**

- Channel adapter interface and wrapper around existing WeCom primitives.
- Web API + SSE fixture channel.
- Delivery, feedback, idempotency, and output policy fixtures for each channel.
- SDK guidance for Web/Tauri/Electron/Flutter/mobile clients: default to platform API/SDK; use local runtime only for approved local file, local secret, or intranet tool cases.

**Acceptance criteria:**

- WeCom tests still pass with no production behavior regression.
- At least one non-WeCom channel fixture passes end to end.
- Channel adapters cannot call backend adapters directly; they submit through platform runtime.

**Privacy boundary:** channel bindings isolate secret refs per channel and bot instance.

**Rollback:** per-channel feature flags; WeCom remains independent fallback.

### M4 / Phase 13: Multi-Solution Packaging

**Goal:** prove `lawfirm` is just one solution package by adding a non-legal demo package.

**Deliverables:**

- Complete `solutions/lawfirm/` package manifest and sanitized resources.
- `solutions/demo_non_legal/` package with prompts, fixtures, policy, and adapter config.
- Solution package loader with no external side effects.
- Solution privacy and boundary gates.

**Acceptance criteria:**

- Lawfirm package runs through platform contracts without adding legal fields to platform core.
- Demo non-legal package runs through the same contracts without platform code changes.
- Solution package privacy scan rejects secrets, logs, DBs, media, raw payloads, customer docs, and generated confidential artifacts.

**Privacy boundary:** solution bundles are distributable only when sanitized.

**Rollback:** mark a solution package `compatibility_only`; platform core remains usable.

---

## 7. Test Gates

Every phase:

- `python scripts/run_v2_gates.py --json-summary`
- package-local unit tests for touched packages
- schema validation for new/changed schemas
- fixture replay and relationship integrity checks
- privacy scan for fixtures, manifests, solution packages, and planning docs
- boundary scan for platform-neutral packages

New gates:

- channel normalization/delivery/idempotency tests
- run event replay tests
- adapter capability probe tests
- cancel/approval/artifact tests
- tenant/workspace/session/bot/channel binding consistency tests
- solution package manifest and privacy tests

Live gates:

- Fixture evidence cannot pass live WeCom acceptance.
- Phase 8 trial clock remains human-gated and must not be silently marked complete by platformization work.

---

## 8. ADRs To Write

1. `ADR-0001-agent-platform-layering.md`: platform core vs concrete adapters vs solution packages.
2. `ADR-0002-contract-extension-policy.md`: append-only V2 compatibility and schema ownership under `platform-contract`.
3. `ADR-0003-hermes-adapter-invocation.md`: `/v1/runs` preferred, `/v1/responses` and chat completions compatibility, oneshot fallback.
4. `ADR-0004-storage-and-audit-boundaries.md`: contract logs, read models, runtime audit, and privacy.
5. `ADR-0005-python-ts-runtime-split.md`: Python execution/runtime, TypeScript OpenAPI/SDK/client surface only for this milestone.

---

## 9. Assumptions

- Continue GSD numbering as Phase 09-13.
- Keep V2 PRD as the source of truth until a new milestone PRD/requirements document is approved.
- Existing WeCom live bridge remains the operational fallback throughout M0-M2.
- Hermes API server capability probe is treated as runtime evidence, not as a platform public API.
- User-visible legal assistant behavior must not regress during architecture extraction.

---

## 10. Execution Notes For GSD

When converting this draft into official GSD artifacts:

- Update `.planning/PROJECT.md` with the new milestone goal.
- Add requirements for contracts, runtime, channel interfaces, adapter interfaces, solution packaging, privacy, and live stability.
- Update `.planning/ROADMAP.md` with Phase 09-13, or create a new milestone roadmap after archiving/closing the current Phase 8 state.
- Preserve Phase 8 human gate and evidence docs.
- Do not edit production code in the planning commit.

---

*Draft generated by Codex review on 2026-06-29. This is a planning artifact, not an implementation commit.*
