# Agent Platformization Plan v3 (Synthesis Draft)

> Scope: the next GSD milestone plan that moves InkStatute from the V2 lawyer-WeCom validation shape into a reusable agent platform with solution packages — **without** modifying production code in the planning commit.
>
> This draft supersedes both `agent-platformization-plan-revised.md` and `agent-platformization-plan-codex.md`. It keeps the codex draft's correct findings, fixes the issues the codex draft missed, and grounds every load-bearing claim in source evidence verified on 2026-06-29 against `origin/main @ d81d934`.
>
> 中文摘要：本版在 codex 版基础上修正了三处关键遗漏（M0–M4 标签与 PRD 第 11 节既有里程碑冲突、`/v1/runs` 是否真正执行 lawfirm profile 尚未验证、流式 run 事件的 output boundary 缺口），并把所有声明锚定到已核实的源码位置。

---

## 0. Evidence Base (verified 2026-06-29)

Every claim below was checked against the working tree, not assumed.

| Claim | Status | Evidence |
|-------|--------|----------|
| Phase 1–7 complete, Phase 8 `human_needed` | TRUE | `.planning/STATE.md:5-14`, `.planning/ROADMAP.md:219-227` |
| HEAD is `d81d934` on `main`, last commit guards WeCom delivery completion | TRUE | `git log` |
| `packages/platform-contract/` is the single schema source (7 schemas) | TRUE | `packages/platform-contract/src/platform_contract/schemas/*.json` |
| `packages/platform-core/` and `solutions/` do **not** exist yet; `apps/` is empty | TRUE | repo inventory |
| 08-04 modules exist: task_flow, active_task_router, delivery_guard, runtime_audit, output_policy, agent_backend, sender, normalization, idempotency, owned_notices | TRUE | `services/wecom-service/src/wecom_service/*.py` |
| `AsyncTaskState` is a locked enum: queued/running/waiting_for_user/succeeded/failed/cancelled | TRUE | `packages/platform-contract/src/platform_contract/enums.py:6-14` |
| `Artifact` already exists nested under `AgentResult.artifacts` | TRUE | `events.py`, PRD `docs/requirements/V2-PRD.md:425-437` |
| `AdapterCapabilitySet` already exists with 7 fields | TRUE | `agent_adapter.py:18-27` |
| `scripts/run_v2_gates.py --json-summary` runs 8 sequential fail-fast gates | TRUE | `scripts/run_v2_gates.py` |
| Live bridge uses Hermes **subprocess one-shot**, not the HTTP API | TRUE | `scripts/inkstatute_wecom_live_bridge.py`, `STATE.md:105` |
| Hermes exposes `/v1/capabilities`, `/v1/models`, `/v1/chat/completions`, `/v1/responses`, `/v1/runs`(+`{id}`,`/events`,`/approval`,`/stop`) | TRUE | `~/.hermes/hermes-agent/gateway/platforms/api_server.py:4340-4377` |
| PRD §11 already defines M2/M3/M4 with **different** content; `STATE.md` reserves "M2-M4" | TRUE | `docs/requirements/V2-PRD.md:638-643`, `.planning/STATE.md:162` |
| No ADRs exist yet (0 locked) | TRUE | `.planning/intel/SYNTHESIS.md:9,18`, `.planning/INGEST-CONFLICTS.md` |

**Not verifiable from this repo (must stay an assumption / runtime spike):** whether Hermes `/v1/runs` executes the **lawfirm profile** (router + skills + gates + MCP + output) identically to the proven one-shot path. The endpoint exists; its lawfirm-equivalence does not. See §5 and the M2 parity spike.

---

## 1. Review Of The Codex Draft

### 1.1 Codex findings that are correct and retained (verified)

- **Three privacy artifacts separated** (codex High #1). Repo may hold `runtime_audit.py`, schemas, tests, redacted summaries; live JSONL/callback bodies/transcripts/DBs/legal payloads stay out. Matches `runtime_audit.py` being in-repo while raw payloads are not.
- **Boundary scan must not ban `lawfirm`/`wecom`/`hermes` across `services/*`** (codex High #2). Verified: service and adapter packages legitimately contain those names (`services/wecom-service`, `services/hermes-contract-layer`). The scan applies only to industry-neutral contract/runtime-core packages.
- **M0 must not be "complete Phase 8 acceptance"** (codex High #3). The five-workday trial is a human-duration gate; blocking platformization on it is wrong. Retained, with a sharper reconciliation in §3 and §6.
- **Keep `platform-contract` as the single schema source** (codex High #4). Verified there is exactly one schema package today; a second schema home (`platform-core`) would fragment it.
- **Non-mutating capability probe** (codex Medium #5). Verified `/v1/capabilities` (`api_server.py:4341`) and `/v1/models` (`:4340`) are GET with no run id; `GET /v1/runs/{id}` needs an existing run. Codex is right to prefer `/health` + `/v1/capabilities` + `/v1/models`.
- **"No Hermes-specific path in platform core," not "no Hermes path anywhere"** (codex Medium #6). Retained.
- **Wrap WeCom before migrating it** (codex Medium #7). Moving a live bridge is needless risk; add interface + wrapper first, migrate after parity. Retained.
- **`ArtifactRecord`, not `Artifact`** (codex #8). Verified collision: `Artifact` is already a nested type. Retained.
- **`secret_ref` only, never secret values** (codex #9). Matches PRD §7 (`docs/requirements/V2-PRD.md:543-556`). Retained.
- **Python owns runtime; TypeScript is SDK/OpenAPI surface only** (codex #10). Retained.

The codex draft is a genuine improvement over the revised draft. The items below are what it still gets wrong or omits.

### 1.2 New findings the codex draft missed

**H1 — Milestone label collision with PRD §11 (HIGH).**
The codex draft labels Phase 09–13 as "M0–M4." But `docs/requirements/V2-PRD.md:638-643` already assigns M2/M3/M4 to *different* content (Codex/provider-model adapters, Router/Skill registries, Model Gateway, Web, security platform, Document Pipeline, Tauri, auto skill synthesis), and `.planning/STATE.md:162` records "Deferred to M2-M4" for those exact items. Reusing "M0–M4" silently overloads a reserved namespace and will corrupt traceability.
**Fix:** drop the "M0–M4" alias. Use GSD phase numbers only (**Phase 09–13**) under a named milestone **"Platform Foundation (v1.1)"**, and add an explicit reconciliation note that this milestone *pulls forward and re-scopes* parts of PRD §11 M2, superseding that table where they overlap.

**H2 — Sequencing against Phase 8 acceptance and the PRD dependency (HIGH/MED).**
PRD §11 makes later milestones depend on "V2 验收通过" (V2 acceptance passing); Phase 8 is still `human_needed`. The codex draft de-couples the trial from M0 but never states the governing rule.
**Fix:** make it explicit — **non-runtime work (contracts, fixtures, manifests, ADRs: Phase 10) may proceed in parallel with the live trial clock because it cannot touch the running bot; any live-path runtime change (Phase 11+) is gated on Phase 8 acceptance OR a default-OFF feature flag with proven parity.** Phase 8 evidence is never marked complete by platformization work.

**M3 — Extend the existing `AdapterCapabilitySet`, do not invent a parallel one (MED).**
`agent_adapter.py:18-27` already defines 7 capability fields (`hook_event_support`, `invocation_mode`, `feedback_target_support`, `session_read_support`, `artifact_return_support`, `trace_support`, `no_channel_io`). The codex draft lists ~10 new flags (`supports_async_runs`, `supports_cancel`, ...) without reconciling them to the existing model, which would create two capability schemas.
**Fix:** Phase 11 **extends** `AdapterCapabilitySet` and `agent_adapter_manifest.schema.json` additively, maps old→new, and keeps `validate_agent_backend_manifest()` backward-compatible.

**M4 — No requirement IDs (MED).**
Every existing phase maps to `REQ-*` (see `.planning/intel/SYNTHESIS.md:24-39`). The codex roadmap has none, so it cannot enter `.planning/REQUIREMENTS.md` cleanly.
**Fix:** introduce new REQ IDs (proposed in §6) and map each phase to them.

**M5 — `/v1/runs` lawfirm-equivalence is unproven (MED, this is the riskiest gap).**
The live bridge deliberately uses one-shot because that is the proven lawfirm path (`STATE.md:105`). The codex draft treats `/v1/runs` as the preferred lane after a *capability* probe, but capability presence ≠ lawfirm-profile execution parity (routing, skills, gates, MCP, SOUL, output policy). Switching the primary lane without proving this risks a silent behavior regression for real lawyer tasks.
**Fix:** add an explicit **M2 parity spike** that compares `/v1/runs` output against the one-shot path on fixture tasks *before* `/v1/runs` is allowed to be primary; until parity passes, one-shot stays default.

**M6 — Output boundary must cover the streaming run-event lane (MED).**
Today `apply_output_policy` filters one-shot text (`output_policy.py`). A `/v1/runs` + `/events` lane introduces a *new* leak surface: streamed tool-progress, approval prompts, and gateway notices in the event stream (PRD §4.1.3 forbids these to ordinary users, `docs/requirements/V2-PRD.md:232-249`).
**Fix:** Phase 11 requires the assistant output boundary to wrap **every** run-event/delta path, with fixtures proving meta/tool/approval/gateway events never reach ordinary WeCom users.

**M7 — Preserve the V2 human-review invariant across the new `Approval` contract (LOW/MED).**
PRD §7 keeps high-risk legal conclusions human-reviewed and `skill_candidate.requires_human_review` always true (`docs/requirements/V2-PRD.md:554`). A platform `Approval` resource (mapping Hermes `/v1/runs/{id}/approval`) is for *tool/run* approval and must not become an auto-approval path for legal conclusions.
**Fix:** state the invariant in the `Approval` contract and ADR-0004.

**L8 — Name the TS SDK and gate-registration homes (LOW).**
The codex draft leaves the OpenAPI/TS SDK location and the new-gate wiring implicit. `run_v2_gates.py` is the source-of-truth gate list (8 gates) and new gates must be registered there; the TS SDK needs a defined home (`packages/platform-sdk-ts/`, generated, not hand-written) so the empty `apps/` does not accrete drift.

**L9 — Re-include the solution-vs-adapter-config boundary the revised draft raised (LOW).**
The revised draft's debt note (its §1.2) flagged that "lawfirm solution package" vs "`agent_backend.mode=hermes`" can blur and pollute non-legal composability tests. The codex draft dropped it.
**Fix:** define that a `SolutionPackage` *references* an adapter **config**, and the non-legal composability gate runs a non-legal package through the *same* adapter contract to prove neutrality.

---

## 2. Milestone Definition

**Milestone:** Platform Foundation (working label **v1.1**; GSD **Phase 09–13**).
**Do NOT** reuse the "M0–M4" alias — it collides with PRD §11 (see H1).

**Goal:** preserve the working V2 lawyer WeCom bot while extracting stable platform contracts, adapter interfaces, a run-runtime seam, channel interfaces, and solution-package boundaries — so InkStatute can add channels, agent backends, and industry packages without coupling the platform core to `lawfirm`, WeCom, or Hermes internals.

**Reconciliation with PRD §11 (required):** this milestone pulls forward and re-scopes the *contract/adapter/channel* portions of PRD-§11 "M2" (Codex/provider-model adapter shape, read-view completion, multi-channel seam) into Phase 09–13 as **contract-and-interface work only**. It does **not** deliver productized Codex/provider-model backends, a security platform, Web/Tauri UIs, or auto skill synthesis — those remain in PRD-§11 M3/M4. The new milestone PRD/section must record this supersession explicitly.

**Non-goals (unchanged from codex, retained):**
- No rebuild of Hermes core, router, session storage, skill registry, MCP registry, or model gateway.
- No replacement of the live WeCom path before fresh UAT proves parity.
- No production Codex/Claude-Code/OpenCode/direct-provider adapters beyond contract-compatible fixtures.
- No full Web/Tauri/Electron/Flutter/mobile UIs.
- No security platform, RBAC, WORM store, or automatic legal-skill synthesis.

---

## 3. Governing Sequencing Rule (resolves H2)

1. **Phase 09** protects and proves the live bot; it is the only phase allowed to touch live behavior, and only additively.
2. **Phase 10** is non-runtime (schemas, fixtures, manifests, ADRs). It may run **in parallel with the human trial clock** because it cannot affect the running bot.
3. **Phase 11+** introduces runtime seams. Each new lane (run-runtime, Hermes API-server lane, channel wrappers) lands **default-OFF behind a feature flag**; the proven one-shot + current WeCom path stays default until parity fixtures + a live smoke pass.
4. **Phase 8 acceptance is never satisfied by platformization work.** The five-workday trial evidence remains a separate human gate owned by `.planning/phases/08-lawyer-trial-acceptance/08-UAT.md`.

---

## 4. Target Architecture

### 4.1 Platform core (industry-neutral)
- `packages/platform-contract/` remains the **single** home for JSON Schema + Python bindings for platform events/resources (extend it; do not fork it).
- A new dependency-light `packages/platform-runtime/` holds **interfaces and pure orchestration** (e.g., `RunRuntime`, channel/back-end adapter protocols). It **imports** `platform-contract`; it never redefines schemas.
- The core must not depend on Hermes paths, WeCom protocol internals, `lawfirm` profile files, legal fields, customer payloads, or secrets.

### 4.2 Channel layer
- Adapters normalize protocol IO into contracts: inbound → `ChannelMessage` (+ `AgentTurn`/`FeedbackEvent`), outbound → `ChannelDelivery` (policy result, idempotency key, channel message id, sanitized error).
- Bindings: `BotInstance` + `ChannelBinding`, secret values always external `secret_ref`.
- WeCom stays the first production channel; QQBot/WeChat/Feishu/Web/Webhook/WS/SSE are contract targets until a phase productionizes one.

### 4.3 Agent backend adapter layer
- One interface for all backends: `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, artifact-ref collection, tool-trace normalization, session/memory capability declaration.
- Capabilities are declared by **extending the existing `AdapterCapabilitySet`** (M3), not by a parallel model.
- Hermes, Codex, Claude Code, OpenCode, direct provider-model are adapter implementations. None own ordinary-user channel IO (`no_channel_io=true`).

### 4.4 Solution packages
- Product/industry bundles loaded by the platform: prompt/profile/SOUL refs, skills + MCP refs, output-policy overlays, eval/contract fixtures, bootstrap manifest, **adapter config defaults**, secret *templates* (names only).
- `solutions/lawfirm/` is the first package. A `SolutionPackage` references an adapter **config**; it is not itself a backend mode (resolves L9).

### 4.5 Storage and audit (three classes)
- **Contract logs:** append-only, privacy-minimized, `raw_payload_ref`-first, replayable.
- **Read models:** derived views (the existing `conversation-read-view`), never the authority this milestone.
- **Runtime/operator audit:** private deployment evidence; only sanitized summaries enter the repo. Blocked/rewritten output-policy events are stored as sanitized summary records, never raw backend text.

---

## 5. Contract Additions

All additions are backward-compatible and live under `packages/platform-contract/`.

**Keep (unchanged):** `AgentTurn`, `AgentResult`, `FeedbackEvent`, `ExecutionTrace`, `RouteDecision`, `AgentBackendManifest` (+ `AdapterCapabilitySet`).

**Add:**
- `ChannelMessage` / `ChannelDelivery` — normalized inbound event / post-policy outbound attempt.
- `Run` / `RunEvent` / `RunStep` — platform run resource; **`Run.status` binds to the existing `AsyncTaskState` enum** (no parallel state model). `RunStep` maps to `ExecutionTrace.steps`.
- `ToolCall` — normalized tool invocation/result summary.
- `Approval` — request/response with the human-action boundary; **must not auto-approve legal conclusions** (M7).
- `ArtifactRecord` — top-level artifact ref, **distinct** from nested `AgentResult.artifacts` (avoids the verified `Artifact` collision).
- `Session` — platform session abstraction, not Hermes `state.db`.
- `Tenant` / `Workspace` — identity scope for later isolation.
- `SolutionPackageManifest` — package metadata + resource refs.
- `BotInstance` / `ChannelBinding` — bot instance + binding with `secret_ref` only.

**Rules:**
- No required top-level legal/Hermes/WeCom/lawfirm fields; legal data stays in `industry_context`/`metadata`.
- Raw payloads, customer docs, runtime logs, DB paths, secret values are forbidden.
- Relationship tests must prove `ChannelMessage → AgentTurn → Run → RunEvent/RunStep → AgentResult/ArtifactRecord → ChannelDelivery → FeedbackEvent`, consistent with PRD §6.6.

---

## 6. GSD Roadmap (Phase 09–13)

Continue numbering to preserve V2 history. Each phase lists proposed **new REQ IDs** (resolves M4) for `.planning/REQUIREMENTS.md`.

### Phase 09 — Live WeCom Stability Gate
**REQ-live-wecom-stability.** Goal: prove the current lawyer bot is safe to keep using before any extraction.
**Boundary:** no refactor, no API migration, no schema expansion except for sanitized evidence; additive files only; do not change signatures of `task_flow` / `delivery_guard` / `output_policy`.
**Deliverables:** fresh live UAT (document+instruction plus follow-up during an active task); sanitized readiness report (quick ACK, recurring service-owned progress, explicit final/timeout/failure/incomplete, no false `completed`, no Hermes meta leak, fast active-task follow-up); clarified runtime-audit policy (code/tests/summaries in-repo, live records out).
**Acceptance:** `run_v2_gates.py --json-summary` passes; live UAT passes or is explicitly blocked with reason; 08-04 bridge + one-shot remain rollback-ready.
**Privacy:** no callback payloads/media/generated docs/transcripts/DBs/logs/tokens/raw legal text committed.
**Rollback:** keep/restart 08-04 bridge; freeze platformization if the bot regresses.

### Phase 10 — Contract & Boundary Extraction (non-runtime; parallel-safe)
**REQ-platform-contract-extension, REQ-solution-packaging-manifest, REQ-platform-boundary-scan.**
**Deliverables:** new schemas/types in `platform-contract` (§5); legal + non-legal contract fixtures; initial `solutions/lawfirm/` manifest (refs only); boundary tests forbidding legal/Hermes/WeCom terms in **neutral** packages while allowing them in solution/adapter/service packages; ADRs (§8).
**Acceptance:** existing V2 contracts still valid; new schema validation + relationship replay pass; lawfirm manifest has no secrets/logs/DBs/media/raw payloads/customer docs; a non-legal fixture validates with **zero** platform-code changes; `Run.status` validated against `AsyncTaskState`.
**Privacy:** manifests store references + secret *names* only.
**Rollback:** ignore new contracts/manifests; services keep current behavior.

### Phase 11 — Platform Run Runtime & API Facade (feature-flagged, default-OFF)
**REQ-platform-run-runtime, REQ-adapter-capability-probe, REQ-runlane-output-boundary.**
**Deliverables:** Python-first `RunRuntime` interface + dependency-light impl in `packages/platform-runtime/`; **extend** `AdapterCapabilitySet` (M3); non-mutating capability probe using `/health` + `/v1/capabilities` + `/v1/models` (NOT `GET /v1/runs/{id}`); **`/v1/runs` parity spike** vs one-shot on fixtures (M5) — one-shot stays default until parity passes; one-shot fallback lane with an explicit reduced-capability manifest (no cancel/live-update/streaming/parallel); platform API facade for create/poll/stream/cancel/approval/artifact-refs; **output boundary wraps every run-event/delta lane** with leak fixtures (M6); OpenAPI spec + generated TS SDK in `packages/platform-sdk-ts/` (no TS execution logic).
**Acceptance:** create/poll/stream/cancel/approval pass against fake + Hermes-fixture adapters; probe failure falls back to one-shot with audited reason; `tenant_id`/`workspace_id`/`session_id`/`bot_instance_id`/`channel_binding_id` flow through run records; no raw payload or secret in Run logs; meta/tool/approval/gateway events never reach ordinary users; `Approval` cannot auto-approve legal conclusions (M7).
**Privacy:** tokens/payloads external; logs use refs + hashes.
**Rollback:** disable the API-server lane; run via current one-shot task-flow path.

### Phase 12 — Channel Interface & Client Embedding Surface (feature-flagged)
**REQ-channel-adapter-interface, REQ-multichannel-fixture.**
**Deliverables:** channel-adapter interface + **wrapper** around existing WeCom primitives (wrap first, migrate later — codex Medium #7); a Web API + SSE fixture channel; delivery/feedback/idempotency/output-policy fixtures per channel; SDK guidance (clients default to platform API/SDK; local runtime only for approved local-file/secret/intranet cases).
**Acceptance:** WeCom tests pass with no production regression; ≥1 non-WeCom channel fixture passes end-to-end; channel adapters cannot call backend adapters directly (must go through `RunRuntime`).
**Privacy:** bindings isolate secret refs per channel + bot instance.
**Rollback:** per-channel feature flags; WeCom remains independent fallback.

### Phase 13 — Multi-Solution Packaging
**REQ-solution-package-loader, REQ-solution-privacy-gate.**
**Deliverables:** complete `solutions/lawfirm/` manifest + sanitized resources; `solutions/demo_non_legal/` package (prompts/fixtures/policy/adapter config); solution-package loader with no external side effects; solution privacy + boundary gates.
**Acceptance:** lawfirm package runs through platform contracts with **zero** new legal fields in core; demo non-legal package runs through the **same** contracts with no platform-code change; privacy scan rejects secrets/logs/DBs/media/raw payloads/customer docs/confidential artifacts.
**Privacy:** bundles distributable only when sanitized.
**Rollback:** mark a package `compatibility_only`; core stays usable.

---

## 7. Test Gates

**Every phase:** `run_v2_gates.py --json-summary`; package-local unit tests; schema validation for changed schemas; fixture replay + relationship integrity; privacy scan (fixtures/manifests/solutions/planning docs); boundary scan for neutral packages.

**New gates (must be registered in `scripts/run_v2_gates.py`, the 8-gate source of truth — L8):**
- channel normalization/delivery/idempotency tests
- run-event replay tests; `Run.status` ↔ `AsyncTaskState` consistency
- adapter capability-probe tests
- cancel/approval/artifact tests
- run-lane output-boundary leak tests (M6)
- tenant/workspace/session/bot/channel-binding consistency tests
- solution-package manifest + privacy tests
- `/v1/runs` ↔ one-shot parity fixtures (M5)

**Live gates:** fixtures can never pass live WeCom acceptance; the Phase 8 trial clock stays human-gated and is never auto-completed by platformization work (H2).

---

## 8. ADRs To Write

1. `ADR-0001-agent-platform-layering.md` — platform core vs concrete adapters vs solution packages.
2. `ADR-0002-contract-extension-policy.md` — append-only V2 compatibility; schema ownership under `platform-contract`; extend `AdapterCapabilitySet`/`Artifact` rather than fork (M3, codex #8).
3. `ADR-0003-hermes-adapter-invocation.md` — `/v1/runs` preferred **after parity spike**; `/v1/responses` + chat-completions compatibility; one-shot fallback; capability probe via `/v1/capabilities`+`/v1/models` (M5).
4. `ADR-0004-storage-audit-and-human-review.md` — contract logs, read models, runtime audit, privacy, and the `Approval`/legal human-review invariant (M7).
5. `ADR-0005-python-ts-runtime-split.md` — Python runtime; TS = OpenAPI/SDK/client only; SDK home `packages/platform-sdk-ts/` (L8).
6. `ADR-0006-milestone-namespace-reconciliation.md` — Phase 09–13 supersedes the contract/adapter/channel parts of PRD §11 M2; "M0–M4" alias retired (H1).

---

## 9. Assumptions

- GSD numbering continues as **Phase 09–13**; the "M0–M4" alias is dropped (H1).
- V2 PRD stays source of truth until a new milestone PRD section records the §11 reconciliation.
- The existing WeCom live bridge remains operational fallback throughout Phase 09–11.
- Hermes `/v1/runs` endpoints exist (verified) but their **lawfirm-profile equivalence is unproven** and is treated as a spike, not a fact (M5).
- The Hermes capability probe is runtime evidence, not InkStatute's public API.
- User-visible legal-assistant behavior must not regress during extraction.

---

## 10. Risk & Rollback Summary

| Risk | Trigger | Rollback |
|------|---------|----------|
| Phase 09 change regresses live bot | live UAT shows any Phase-8 metric regression | freeze Phase 10+, restart 08-04 bridge |
| `/v1/runs` ≠ lawfirm behavior | parity spike fails | keep one-shot default; do not promote `/v1/runs` |
| Streaming run events leak meta/tool/gateway text | output-boundary leak fixture fails | disable API-server lane; one-shot only |
| Capability model forks | two capability schemas appear | block; extend existing `AdapterCapabilitySet` only |
| Milestone label collision | "M0–M4" reused anywhere | enforce Phase 09–13 naming in CI/docs (ADR-0006) |
| Solution becomes hidden fork | boundary/privacy scan fails | mark package `compatibility_only` |
| Tenant isolation bleed | tenant/workspace consistency test fails | disable API-server lane |
| Channel abstraction leaks protocol | channel adapter calls backend directly | per-channel flag off |

---

## 11. Execution Notes For GSD

When converting this draft into official artifacts:
- Update `.planning/PROJECT.md` with the Platform Foundation (v1.1) goal and the PRD-§11 reconciliation.
- Add new `REQ-*` entries (§6) to `.planning/REQUIREMENTS.md`.
- Add **Phase 09–13** to `.planning/ROADMAP.md` (numbers only — no "M0–M4" alias) after the Phase 8 human gate is recorded/closed; preserve Phase 8 evidence docs.
- Write ADR-0001…0006 (§8).
- Do not edit production code in the planning commit.
- Keep new runtime lanes default-OFF behind feature flags until parity + live smoke pass (§3).

---

*Synthesis draft generated 2026-06-29. Supersedes `agent-platformization-plan-revised.md` and `agent-platformization-plan-codex.md`. Planning artifact only — not an implementation commit.*
