# Agent Platformization Plan v4 (Execution-Ready GSD Draft)

> Scope: next planning draft for turning InkStatute from the V2 lawyer WeCom bot shape into a reusable agent platform with solution packages. This document supersedes `agent-platformization-plan-v3.md` as a planning artifact only. It does not modify production code or mark Phase 8 complete.
>
> Verified against the current working tree on 2026-06-29 at `main @ d81d934`, with `.planning/drafts/` untracked. Re-verify all source-line evidence before converting this draft into official GSD artifacts.

---

## 0. Review Findings On v3

### High

1. `agent-platformization-plan-v3.md:184-185` still makes the boundary scan too broad. It says neutral packages should forbid legal/Hermes/WeCom terms, but `packages/platform-contract/src/platform_contract/agent_adapter.py:12-16` already defines `AgentBackendMode.HERMES`, `CODEX`, and `PROVIDER_MODEL` in the neutral contract package. The correct rule is not "ban the words everywhere"; it is "ban hard dependencies, private paths, channel/protocol fields, lawfirm-only required fields, and unapproved literals." Backend mode enum values must be an explicit allowlist.
2. `agent-platformization-plan-v3.md:112` says Phase 10 may run in parallel with the human trial clock, but `:270-272` says Phase 09-13 should be added to ROADMAP after Phase 8 is recorded/closed. That creates a GSD sequencing contradiction. The official artifacts should be allowed to add a clearly marked next-milestone/provisional Phase 09-13 plan while Phase 8 remains `human_needed`; only runtime default-on behavior is gated by Phase 8 acceptance and parity.
3. `agent-platformization-plan-v3.md:111` says Phase 09 is "the only phase allowed to touch live behavior." That is too absolute once Phase 11+ adds default-OFF runtime seams. The safer invariant is: before Phase 8 acceptance, only Phase 09 may change the live default path; Phase 11+ may add code only behind default-OFF flags and must preserve the current WeCom plus one-shot lane as rollback.

### Medium

4. v3 has strong technical conclusions, but it does not define the draft-to-GSD promotion order. Without that order, a future automation run could update ROADMAP before requirements/ADR reconciliation, or accidentally imply Phase 8 completion.
5. v3 says every new gate must be registered directly in `scripts/run_v2_gates.py`. That runner is currently the V2 eight-gate source of truth, but Phase 09-13 should first add phase-local or versioned platform gates and aggregate them only when stable. This avoids making current V2 gates depend on unfinished default-OFF platform work.
6. v3 phase sections do not consistently spell out risks, tests, privacy boundary, and rollback. The plan needs uniform phase tables so later `$gsd-plan-phase` or autonomous execution can split work safely.
7. v3 correctly lists Hermes `/v1/capabilities`, `/v1/models`, and `/v1/runs`, but the evidence table should include `/health` and `/v1/health` too. The source registers them in `~/.hermes/hermes-agent/gateway/platforms/api_server.py:4337-4339`.
8. The attached pasted-text review is encoded as mojibake in the attachment, but its content matches the v3 additions and priorities. Treat v3 itself as the readable source for that review.

### Low

9. The working label `v1.1` is acceptable as a planning label, but it must not be treated as a release tag until GSD milestone activation.
10. `packages/platform-sdk-ts/` should remain generated/client-only. Check generated outputs in only after the generator contract is deterministic enough for CI, or keep generation as a phase artifact until then.

---

## 1. Milestone Definition

**Working milestone name:** Platform Foundation (planning label `v1.1`, not a release tag).

**GSD numbering:** Phase 09-13 only. Do not reuse the "M0-M4" alias because PRD section 11 already reserves M2/M3/M4 for different follow-on work.

**Goal:** preserve the working V2 lawyer WeCom bot while extracting stable platform contracts, run-runtime seams, channel interfaces, agent-backend adapter boundaries, and solution-package manifests. The lawyer assistant becomes the first solution package, not the definition of the platform core.

**Current baseline:**

- `.planning/STATE.md:5-8` records `human_needed` and says fresh live WeCom task-flow UAT is pending.
- `.planning/ROADMAP.md:190-210` keeps Phase 8 as Lawyer Trial Acceptance with four plans completed but human evidence still pending.
- `origin/main @ d81d934` is the latest pushed baseline.
- The live bridge uses InkStatute-owned WeCom ingress/egress and Hermes subprocess one-shot through `scripts/inkstatute_wecom_live_bridge.py`.
- Hermes HTTP endpoints exist, including `/health`, `/v1/capabilities`, `/v1/models`, `/v1/responses`, `/v1/chat/completions`, and `/v1/runs`, but `/v1/runs` lawfirm-profile equivalence is not proven.

**Non-goals for Phase 09-13:**

- Do not rebuild Hermes core, router, session storage, skill registry, MCP registry, model gateway, or lawfirm business logic.
- Do not replace the live WeCom default path before Phase 8 evidence and run-lane parity pass.
- Do not productize Codex, Claude Code, OpenCode, or direct provider-model adapters beyond fixtures and contract compatibility.
- Do not build full Web, Tauri, Electron, Flutter, or mobile products.
- Do not build the full M3 security platform, RBAC, WORM audit store, or automatic legal skill synthesis.

---

## 2. Governing Rules

### 2.1 Source Of Truth

`docs/requirements/V2-PRD.md` remains the source of truth until a new milestone requirements section is explicitly approved. Phase 09-13 must record where it supersedes or pulls forward part of PRD section 11.

### 2.2 Phase 8 Gate

Phase 8 remains a human gate. Platformization work never auto-completes the five-workday lawyer trial or substitutes fixtures for live evidence.

Allowed before Phase 8 acceptance:

- Phase 09 live-readiness evidence and additive repair if needed to protect the existing bot.
- Phase 10 non-runtime work: schemas, fixtures, ADRs, requirements, manifests, boundary tests.
- Phase 11+ code only when default-OFF and rollback-safe; no live default change.

Default-on runtime promotion requires:

1. Phase 8 live UAT/trial evidence accepted, or the user explicitly approves a default-OFF spike outside the live path.
2. Parity fixtures prove the new lane matches the current one-shot lawfirm behavior for routing, skills, gates, MCP use, artifacts, and user-visible output policy.
3. A live smoke pass proves no regression in WeCom ACK, progress, final/incomplete/failure state, artifact delivery, follow-up handling, and Hermes meta leak prevention.

### 2.3 PRD Section 11 Reconciliation

PRD section 11 reserves:

- M2: Codex/provider-model prototypes, router/skill registry reading, read-view completion, Admin Console read API, QQBot loop.
- M3: multi-agent runtime productization, MCP registry, model gateway, Web frontend, security platform.
- M4: document pipeline, Tauri, automatic skill synthesis.

Phase 09-13 pulls forward only contract/interface groundwork from that future scope. It does not productize the deferred M2/M3/M4 items.

### 2.4 Boundary Scan Policy

Boundary scans must be precise:

- For neutral packages (`packages/platform-contract`, future `packages/platform-runtime`), forbid private Hermes paths, WeCom protocol payload fields, lawfirm-only required fields, legal-only top-level required fields, raw payload content, and secret values.
- Allow explicit backend mode enum values such as `hermes`, `codex`, and `provider_model` in adapter contracts because they already exist and are part of V2.
- Allow concrete names inside concrete packages: `services/wecom-service`, `services/hermes-contract-layer`, future channel adapters, and `solutions/lawfirm`.
- Require non-legal fixtures to prove a platform contract can be used without lawfirm assumptions.

### 2.5 Privacy Boundary

Repository-allowed artifacts:

- Source code, schemas, generated bindings, tests, sanitized fixtures, sanitized summaries, ADRs, runbooks, and secret-name templates.

Repository-forbidden artifacts:

- WeCom callback bodies, raw messages, media files, generated confidential documents, Hermes stdout/stderr transcripts, runtime JSONL logs, DB files, tokens, API keys, customer legal payloads, feedback originals, and unredacted audit records.

---

## 3. Target Architecture

### 3.1 Platform Contract

`packages/platform-contract/` remains the single source of JSON Schema and Python bindings. New contracts are additive and backward-compatible.

Existing contracts remain authoritative:

- `AgentTurn`
- `AgentResult`
- `FeedbackEvent`
- `ExecutionTrace`
- `RouteDecision`
- `AgentBackendManifest`
- `AdapterCapabilitySet`

New contracts:

- `ChannelMessage`
- `ChannelDelivery`
- `Run`
- `RunEvent`
- `RunStep`
- `ToolCall`
- `Approval`
- `ArtifactRecord`
- `Session`
- `Tenant`
- `Workspace`
- `SolutionPackageManifest`
- `BotInstance`
- `ChannelBinding`

Rules:

- `Run.status` maps to the existing `AsyncTaskState` enum: queued, running, waiting_for_user, succeeded, failed, cancelled.
- `ArtifactRecord` is a top-level artifact ref/resource and does not rename or replace nested `AgentResult.artifacts`.
- `Approval` models tool/run approval and must not become a path for auto-approving high-risk legal conclusions.
- `ChannelBinding` stores `secret_ref` only.

### 3.2 Platform Runtime

Future `packages/platform-runtime/` holds dependency-light protocols and pure orchestration:

- `RunRuntime`
- channel adapter protocol
- backend adapter protocol
- event replay helpers
- feature-flag checks
- output-boundary wrappers for run events

It imports `platform-contract` and does not redefine schemas.

### 3.3 Channel Layer

Channel adapters own protocol normalization and delivery:

- inbound protocol event -> `ChannelMessage`
- actionable user turn -> `AgentTurn`
- feedback callback -> `FeedbackEvent`
- outbound attempt -> `ChannelDelivery`

WeCom remains the first production channel. Web API/SSE, Webhook, WebSocket, QQBot, WeChat, and Feishu stay fixtures or contract targets until a phase explicitly productionizes one.

Channel adapters must not call backend adapters directly. They submit through `RunRuntime`.

### 3.4 Agent Backend Adapter Layer

Backends implement a single interface:

- `submit_run`
- `get_run`
- `stream_events`
- `cancel_run`
- `submit_approval`
- artifact ref collection
- tool trace normalization
- session/memory declaration

Capabilities extend the existing `AdapterCapabilitySet` rather than creating a parallel schema. Phase 11 should add optional fields such as:

- `run_invocation_modes`
- `stream_event_support`
- `cancel_support`
- `approval_support`
- `live_update_support`
- `parallel_task_support`
- `session_memory_support`

Existing fields such as `invocation_mode`, `artifact_return_support`, `trace_support`, `session_read_support`, and `no_channel_io` remain valid.

### 3.5 Solution Packages

Solution packages are product/industry bundles:

- prompts/profile/SOUL references
- skill and MCP references
- output policy overlays
- eval and contract fixtures
- bootstrap manifest
- adapter config defaults
- secret templates by name only

`solutions/lawfirm/` is the first package. A solution references adapter config; it is not itself a backend mode.

### 3.6 Storage And Audit

Use three storage classes:

- Contract logs: append-only, replayable, privacy-minimized, `raw_payload_ref` first.
- Read models: derived SQLite/Postgres-ready views, not authoritative this milestone.
- Runtime/operator audit: private deployment evidence outside the repo unless converted into sanitized summaries.

Blocked/rewritten output-policy events record sanitized summaries only.

---

## 4. Hermes Adapter Strategy

Hermes is a backend adapter, not a channel boundary.

### 4.1 Capability Probe

Startup probe is non-mutating:

- Load adapter manifest and feature flags.
- Check base URL and credentials via `secret_ref` only.
- Query `/health` or `/v1/health`.
- Query `/v1/capabilities`.
- Query `/v1/models`.
- Verify advertised route support for runs/events/approval/stop/responses/chat-completions.
- Require `no_channel_io=true`.

Do not probe with `GET /v1/runs/{id}` because it requires an existing run id. Synthetic `POST /v1/runs` belongs to an explicit smoke/parity test with non-sensitive fixtures.

### 4.2 Invocation Preference

Default remains subprocess one-shot until parity passes.

Candidate preference after parity:

1. `/v1/runs` for async runs, event streams, cancel, approval, and artifacts.
2. `/v1/responses` for compatibility/stateful response workflows that do not need platform-native run control.
3. `/v1/chat/completions` for simple compatibility paths only.
4. subprocess one-shot fallback when API server mode is unavailable, unsafe, or not equivalent.

One-shot fallback declares no cancel, no live update, no streaming progress, and no parallel task support.

### 4.3 Lawfirm Equivalence Spike

Phase 11 must compare `/v1/runs` with the current one-shot lane on fixture tasks:

- legal Q&A
- document drafting with requested artifact
- follow-up during active task
- route mismatch
- tool/MCP-using task
- non-legal synthetic task

The spike checks routing, skill/gate behavior, MCP/tool trace, artifact references, final user-facing text, output policy, and state transitions. Failure keeps one-shot as default.

### 4.4 Streaming Output Boundary

Every run-event/delta path must pass through the assistant output boundary before ordinary WeCom delivery. Fixtures must prove meta/tool/approval/gateway/internal events do not leak to ordinary users.

---

## 5. Feature Flags

New runtime lanes are default-OFF until phase acceptance:

| Flag | Default | Purpose |
|------|---------|---------|
| `INKSTATUTE_PLATFORM_RUNTIME_ENABLED` | false | Enables `RunRuntime` path at all |
| `INKSTATUTE_HERMES_API_RUNS_ENABLED` | false | Allows Hermes `/v1/runs` lane |
| `INKSTATUTE_HERMES_ONESHOT_FALLBACK_ENABLED` | true | Keeps current rollback lane |
| `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED` | false | Routes WeCom through channel wrapper |
| `INKSTATUTE_WEB_SSE_FIXTURE_ENABLED` | false | Enables Web API/SSE fixture channel |
| `INKSTATUTE_SOLUTION_LOADER_ENABLED` | false | Enables solution manifest loader |

Feature flag names are planning names. Implementation may rename them, but the acceptance gate must preserve the same default-OFF semantics.

---

## 6. GSD Roadmap

### Phase 09: Live WeCom Stability Gate

| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-live-wecom-stability` |
| Goal | Protect the current lawyer bot before platform extraction. |
| Scope | Existing live path only; additive evidence and minimal repairs if live UAT requires them. No platform refactor. |
| Deliverables | Fresh live UAT record; sanitized readiness report; runtime audit policy clarification; rollback runbook for current bridge. |
| Acceptance | V2 gates pass; live UAT passes or is explicitly blocked; no false `completed`; no Hermes meta leak; quick ACK/progress/final/incomplete/failure behavior verified; active-task follow-up is fast. |
| Tests | `python scripts/run_v2_gates.py --json-summary`; Phase 8 UAT checklist; delivery guard/output policy targeted tests if repaired. |
| Privacy | No raw callback payloads, media, legal docs, logs, DBs, tokens, transcripts, or raw legal text committed. |
| Risks | Repairing live behavior may disturb the current bridge. |
| Rollback | Restart/keep the 08-04 live bridge and one-shot path; freeze later platform phases if regression occurs. |

### Phase 10: Contract And Boundary Extraction

| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-platform-contract-extension`, `REQ-solution-packaging-manifest`, `REQ-platform-boundary-scan`, `REQ-milestone-namespace-reconciliation` |
| Goal | Add neutral contracts, manifests, ADRs, and boundary gates without runtime behavior changes. |
| Scope | Non-runtime only. Safe to run while Phase 8 human evidence remains pending. |
| Deliverables | New schemas in `platform-contract`; legal and non-legal fixtures; initial `solutions/lawfirm/` manifest with refs only; boundary scan with backend-mode allowlist; ADR-0001 through ADR-0006 drafts; requirements additions. |
| Acceptance | Existing V2 contracts still validate; new relationship replay passes; `Run.status` uses `AsyncTaskState`; no schema fork; lawfirm manifest contains no secrets/logs/DBs/media/raw payloads/customer docs; non-legal fixture validates without platform code changes. |
| Tests | Platform-contract unit tests; contract-test-suite fixture replay; privacy scan; boundary scan with allowlist for `hermes/codex/provider_model` mode values. |
| Privacy | Manifests store refs and secret names only. |
| Risks | Over-modeling and false-positive boundary scans. |
| Rollback | Ignore new contracts/manifests; current services continue unchanged. |

### Phase 11: Platform Run Runtime And API Facade

| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-platform-run-runtime`, `REQ-adapter-capability-probe`, `REQ-hermes-run-parity-spike`, `REQ-runlane-output-boundary` |
| Goal | Introduce a formal run runtime and API facade without replacing the proven one-shot lane. |
| Scope | Runtime seams default-OFF behind feature flags. |
| Deliverables | Python-first `RunRuntime` in `packages/platform-runtime`; additive `AdapterCapabilitySet` extension; non-mutating Hermes probe; fake adapter fixtures; Hermes `/v1/runs` parity spike; one-shot fallback manifest; platform API facade for create/poll/stream/cancel/approval/artifact refs; OpenAPI and generated TS SDK/client types in `packages/platform-sdk-ts/`. |
| Acceptance | Fake adapter tests pass; Hermes probe failure falls back to one-shot with sanitized audit reason; parity spike passes before `/v1/runs` can be promoted; tenant/workspace/session/bot/channel ids flow through run records; streaming output boundary prevents meta/tool/gateway leaks; `Approval` cannot auto-approve legal conclusions. |
| Tests | Run create/poll/stream/cancel/approval tests; capability probe tests; parity fixtures; run-event replay; output-boundary leak fixtures; privacy scan; feature-flag default tests. |
| Privacy | Run logs store refs/hashes, not raw payloads or secrets. |
| Risks | `/v1/runs` may not execute lawfirm profile equivalently; event streams may leak backend meta; capability model may fork. |
| Rollback | Disable `INKSTATUTE_HERMES_API_RUNS_ENABLED` and route through current one-shot task-flow path. |

### Phase 12: Channel Interface And Client Embedding Surface

| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-channel-adapter-interface`, `REQ-multichannel-fixture`, `REQ-client-embedding-contract` |
| Goal | Make WeCom one channel implementation under a shared interface, then prove one non-WeCom fixture channel. |
| Scope | Wrap before moving. WeCom production behavior remains independently rollback-ready. |
| Deliverables | Channel adapter protocol; wrapper around existing WeCom primitives; Web API + SSE fixture channel; delivery/feedback/idempotency/output-policy fixtures per channel; client embedding guidance for Web/Tauri/Electron/Flutter/mobile via platform API/SDK. |
| Acceptance | Existing WeCom tests pass with no production regression; one non-WeCom channel fixture passes end to end; channel adapters cannot call backend adapters directly; secret refs are isolated per bot/channel binding. |
| Tests | Channel normalization tests; delivery/idempotency tests; feedback dedupe tests; output-policy fixtures; dependency-boundary scan. |
| Privacy | Channel bindings contain `secret_ref` only and cannot share raw protocol payloads across channels. |
| Risks | Channel abstraction may leak protocol details or disturb live WeCom behavior. |
| Rollback | Turn off per-channel flags; use current WeCom service path directly. |

### Phase 13: Multi-Solution Packaging

| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-solution-package-loader`, `REQ-solution-privacy-gate`, `REQ-nonlegal-solution-composability` |
| Goal | Prove lawfirm is a solution package, not platform core. |
| Scope | Package manifests and loader with no external side effects. |
| Deliverables | Complete `solutions/lawfirm/` manifest and sanitized resources; `solutions/demo_non_legal/` package; solution loader; solution boundary/privacy gates; composability report. |
| Acceptance | Lawfirm package runs through platform contracts with zero new legal top-level fields; demo non-legal package runs through the same contracts with no platform code change; solution scan rejects secrets/logs/DBs/media/raw payloads/customer docs/confidential artifacts. |
| Tests | Solution manifest validation; privacy scan; non-legal composability gate; loader no-side-effect tests. |
| Privacy | Solution bundles are distributable only when sanitized. |
| Risks | Solution package becomes a hidden platform fork or smuggles adapter assumptions. |
| Rollback | Mark package `compatibility_only`; platform core remains usable. |

---

## 7. Test And Gate Strategy

Current V2 runner:

- Keep `scripts/run_v2_gates.py --json-summary` as the current V2 fail-fast gate.

Phase-local additions:

- Phase 10 may add package-local contract and boundary tests.
- Phase 11 may add a separate platform-runtime test entrypoint until stable.
- Phase 12 may add channel fixture tests under the relevant package.
- Phase 13 may add solution-package validation tests.

Aggregation rule:

- New gates can be registered into `scripts/run_v2_gates.py` only when they are stable, deterministic, and do not require disabled runtime lanes, external secrets, live WeCom, or Hermes API server availability.
- Live WeCom acceptance remains a human/live gate, not a fixture gate.

Required new test categories:

- contract schema validation
- fixture replay and relationship integrity
- boundary scan with allowlists
- privacy scan for manifests/fixtures/planning docs
- run-event replay
- adapter capability probe
- `/v1/runs` vs one-shot parity
- run-lane output-boundary leak tests
- cancel/approval/artifact tests
- tenant/workspace/session/bot/channel binding consistency
- solution package composability and privacy

---

## 8. ADR Set

Write these before or during Phase 10:

1. `ADR-0001-agent-platform-layering.md`: platform contract vs platform runtime vs concrete adapters vs solution packages.
2. `ADR-0002-contract-extension-policy.md`: append-only V2 compatibility, `platform-contract` ownership, `AdapterCapabilitySet` extension, `ArtifactRecord` naming.
3. `ADR-0003-hermes-adapter-invocation.md`: capability probe, `/v1/runs` parity requirement, `/v1/responses` and chat-completions compatibility, one-shot fallback.
4. `ADR-0004-storage-audit-and-human-review.md`: contract logs, read models, runtime audit, privacy, and legal human-review invariant.
5. `ADR-0005-python-ts-runtime-split.md`: Python runtime and orchestration; TypeScript only OpenAPI/SDK/client surface in this milestone.
6. `ADR-0006-milestone-namespace-reconciliation.md`: Phase 09-13 naming and how it pulls forward selected PRD section 11 contract/interface work without reusing M2/M3/M4.
7. `ADR-0007-boundary-scan-allowlist.md`: neutral-package scan policy, backend-mode allowlist, concrete adapter/service/solution exceptions.

---

## 9. Draft-To-GSD Promotion Order

Use this order if the user accepts v4:

1. Keep Phase 8 state intact. Do not mark `.planning/STATE.md` complete.
2. Add a short milestone reconciliation note to `.planning/PROJECT.md` explaining Platform Foundation as the next planned milestone and preserving Phase 8 human gate.
3. Add new requirements to `.planning/REQUIREMENTS.md` under a new "Platform Foundation Requirements" section, not mixed into completed V2 requirements.
4. Add Phase 09-13 to `.planning/ROADMAP.md` as next-milestone/provisional phases, with a clear note that Phase 10 non-runtime work may proceed while Phase 8 remains human-needed and Phase 11+ default-on runtime promotion is gated.
5. Create ADR skeletons under the repo's chosen ADR location. If no ADR directory exists, create one intentionally, for example `docs/architecture/adr/`.
6. Create per-phase plan directories only when starting each phase, following existing `.planning/phases/<number>-<slug>/` conventions.
7. Do not edit production code in the planning commit.
8. Run a secret/privacy scan on all new planning docs before commit.

---

## 10. Open Assumptions

- Hermes `/v1/runs` exists but lawfirm-profile equivalence is unproven.
- The current one-shot WeCom live path remains the operational default through Phase 11 unless the user explicitly promotes a new lane after parity.
- The next milestone can be planned before Phase 8 completion, but runtime default changes remain gated.
- Generated TS SDK is useful only after OpenAPI and contract generation become deterministic.
- Full security platform, Web UI, Tauri, document pipeline, and automatic skill synthesis remain future PRD section 11 work.

---

## 11. Immediate Next Step

If this v4 draft is accepted, convert it into official GSD artifacts in this order:

1. requirements additions
2. ADR skeletons
3. PROJECT/ROADMAP reconciliation
4. Phase 09 discussion/plan
5. Phase 10 contract/boundary plan

The first implementation phase should be Phase 09 or Phase 10 depending on user priority:

- Choose Phase 09 if live UAT evidence is still the operational blocker.
- Choose Phase 10 if the user wants platform planning/contracts to proceed while the five-workday trial clock is waiting on humans.

---

*Draft generated by Codex review on 2026-06-29. Planning artifact only; no production code changes are implied.*
