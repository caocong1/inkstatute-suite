# Agent Platformization Plan v5 — New Milestone, Autonomous-Ready

> Companion to `agent-platform-north-star.md`. This is the execution plan for a **new milestone** ("Platform Foundation", planning label `v1.1`, GSD **Phase 09–13**). It supersedes v3/v4 as the active plan.
>
> Framing change from v4 (per user direction 2026-06-29): this is a **deliberate refactor toward a reusable agent platform**, not an additive patch on V2's `services/` layout. Interfaces are designed to the North Star; Hermes is the first backend; the lawyer pack is the first solution. The build is structured so **`$gsd-autonomous` can run Phase 09→13 hands-free**, while live cutover and the lawyer trial stay human gates *outside* the autonomous path.

---

## 1. Decisions locked (by agent, under user delegation)

1. **Refactor, phased**: build a new InkStatute-owned platform core beside the running bot (strangler-fig); reach parity behind flags; retire old path later.
2. **Tech stack**: JSON Schema contracts; **Python 3.11+ async** core (runtime/adapters/channels/loader/API); **TypeScript** client SDK + embeddable chat component; Rust/Go deferred to the north-star local runtime. (Rationale in north-star §2.)
3. **Four contracts to the North Star**: `ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, `RunRuntime` (north-star §4).
4. **Solution = backend-portable**: neutral manifest + per-backend materialization; Hermes profile is the first materialization target.
5. **Clients**: default remote/thin; runtime kept embeddable; no local runtime this milestone.
6. **Self-built agent**: north star only; this milestone just guarantees `BackendAdapter` can express it.
7. **Autonomy split**: Phase 09–13 are code+test+fixtures (autonomous). Live promotion + Phase 8 lawyer trial are **human gates not on the autonomous path**.

---

## 2. New repo structure (target; created incrementally by the phases)

```
packages/
  platform-contract/      # EXISTS — extend with new schemas + Python bindings
  platform-runtime/       # NEW — RunRuntime, the 4 Protocols, orchestration, output boundary
  platform-sdk-ts/        # NEW — generated TS client SDK + types (from OpenAPI/JSON Schema)
  contract-test-suite/    # EXISTS — extend with new gates
channels/
  wecom/                  # NEW — ChannelAdapter wrapping existing WeCom primitives
  web_sse/                # NEW — WebAPI/SSE fixture channel
backends/
  hermes/                 # NEW — BackendAdapter (one-shot first; /v1/runs after parity)
solutions/
  lawfirm/                # NEW — neutral manifest + materialize-to-hermes
  demo_non_legal/         # NEW — proves neutrality
apps/
  platform_api/           # NEW — thin server hosting RunRuntime (FastAPI/aiohttp)
  web_chat/               # NEW — embeddable TS chat component
docs/architecture/adr/    # NEW — ADR-0001..0007
```

The existing `services/wecom-service`, `services/hermes-contract-layer`, `services/conversation-read-view`, `services/feedback-service` and `scripts/inkstatute_wecom_live_bridge.py` **remain the running fallback** until the new lanes prove parity. Nothing in `services/` is deleted this milestone.

---

## 3. Governing rules (inherited from v4, kept)

- **Phase 8 stays a human gate.** Autonomous work never marks the five-workday lawyer trial complete, never substitutes fixtures for live evidence.
- **New runtime lanes are default-OFF** behind feature flags; the current WeCom + one-shot path stays default until parity + a human live smoke pass.
- **Privacy boundary**: repo holds code/schemas/tests/sanitized fixtures/sanitized summaries/ADRs/secret-name templates only. Never: callback bodies, raw messages, media, generated confidential docs, transcripts, runtime JSONL, DBs, tokens, keys, customer legal payloads, feedback originals.
- **Boundary scan = allowlist** (not word-ban): neutral packages forbid private Hermes paths, WeCom protocol payload fields, lawfirm-only/legal-only top-level required fields, raw payloads, secret values; backend-mode enum values `hermes/codex/provider_model` are allowed; concrete names allowed inside concrete packages (`channels/wecom`, `backends/hermes`, `solutions/lawfirm`).
- **Source of truth**: north-star doc for architecture; V2 PRD only for not-regressing existing lawyer-bot behavior.

---

## 4. Feature flags (default-OFF)

| Flag | Default | Purpose |
|------|---------|---------|
| `INKSTATUTE_PLATFORM_RUNTIME_ENABLED` | false | enable the new `RunRuntime` path at all |
| `INKSTATUTE_HERMES_API_RUNS_ENABLED` | false | allow Hermes `/v1/runs` lane (after parity) |
| `INKSTATUTE_HERMES_ONESHOT_FALLBACK_ENABLED` | true | keep proven rollback lane |
| `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED` | false | route WeCom through the new ChannelAdapter wrapper |
| `INKSTATUTE_WEB_SSE_CHANNEL_ENABLED` | false | enable the Web API/SSE channel |
| `INKSTATUTE_SOLUTION_LOADER_ENABLED` | false | enable the solution manifest loader |

---

## 5. Roadmap — Phase 09–13 (all autonomous-buildable)

### Phase 09 — Architecture Contracts & Schema Foundation
| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-platform-north-star`, `REQ-platform-contract-extension`, `REQ-boundary-scan-allowlist` |
| Goal | Lock the North Star contracts and extend `platform-contract` with the new schemas — non-runtime. |
| Deliverables | North-star doc promoted to `docs/architecture/`; the 4 Protocols stubbed in `packages/platform-runtime` (signatures only, no behavior); new JSON Schemas + Python bindings in `platform-contract` (`ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest`+neutral skill/mcp descriptors, `BotInstance`, `ChannelBinding`); extended `AdapterCapabilitySet`; ADR-0001..0007 drafts; boundary-scan-allowlist tool. |
| Acceptance | Existing V2 contracts still validate; new schema validation + relationship replay pass; `Run.status` uses `AsyncTaskState`; `AdapterCapabilitySet` extension is backward-compatible; boundary scan passes with allowlist; non-legal fixture validates with no platform-code change. |
| Tests | platform-contract unit tests; contract-test-suite fixture replay; boundary scan; privacy scan. |
| Privacy | Schemas/fixtures only; no secrets/raw payloads. |
| Risks | Over-modeling; false-positive boundary scan. |
| Rollback | New schemas are additive; ignore them and services keep current behavior. |

### Phase 10 — Embeddable RunRuntime + Fake Backend
| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-platform-run-runtime`, `REQ-runtime-embeddability`, `REQ-runlane-output-boundary` |
| Goal | Implement `RunRuntime` as an injectable library with a fake in-memory backend; prove the run lifecycle without any live system. |
| Deliverables | `packages/platform-runtime` RunRuntime impl (create/poll/stream/cancel/approve); dependency-injection ports (storage, output_boundary, secret_resolver, feature_flags); a `FakeBackendAdapter` + `FakeChannelAdapter`; output-boundary wrapper over all run events; contract-log store (append-only, `raw_payload_ref`-first). |
| Acceptance | Run lifecycle tests pass against fakes; runtime constructs with **zero channels** (N1); no hard dependency on a server (N4); streamed events pass through output boundary; leak fixtures prove meta/tool/approval events never surface; run logs store refs/hashes only. |
| Tests | run lifecycle; run-event replay; output-boundary leak fixtures; embeddability (no-channel, no-server) tests; feature-flag default-OFF tests. |
| Privacy | Run logs reference-only. |
| Risks | Hidden coupling to a transport/channel. |
| Rollback | Library is unused unless `INKSTATUTE_PLATFORM_RUNTIME_ENABLED`. |

### Phase 11 — Hermes BackendAdapter + Parity Spike
| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-hermes-backend-adapter`, `REQ-adapter-capability-probe`, `REQ-hermes-run-parity-spike` |
| Goal | Implement the Hermes `BackendAdapter` (one-shot first), a non-mutating capability probe, and a fixture-based `/v1/runs` parity spike. |
| Deliverables | `backends/hermes` adapter implementing the Protocol via subprocess one-shot; capability probe using `/health` + `/v1/capabilities` + `/v1/models` (never `GET /v1/runs/{id}`); reduced-capability manifest for one-shot; `/v1/runs` lane behind `INKSTATUTE_HERMES_API_RUNS_ENABLED`; parity spike comparing `/v1/runs` vs one-shot on fixtures (legal Q&A, drafting+artifact, follow-up, route-mismatch, MCP/tool task, non-legal). |
| Acceptance | Adapter passes Protocol conformance tests; probe failure falls back to one-shot with sanitized audit reason; parity spike runs and reports pass/fail (one-shot stays default if it fails); `Approval` cannot auto-approve legal conclusions. |
| Tests | adapter conformance; capability probe; parity fixtures; fallback audit; privacy scan. |
| Privacy | No transcripts/payloads/secrets committed; spike uses non-sensitive fixtures. |
| Risks | `/v1/runs` not lawfirm-equivalent; probe brittle to Hermes version. |
| Rollback | Disable `INKSTATUTE_HERMES_API_RUNS_ENABLED`; one-shot only. |

### Phase 12 — Channel Interface + WeCom Wrapper + Web/SSE + Client SDK
| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-channel-adapter-interface`, `REQ-multichannel-fixture`, `REQ-client-embedding-surface` |
| Goal | Make WeCom one implementation under `ChannelAdapter`; add a Web API/SSE channel; ship the platform API server, TS SDK, and embeddable chat component. |
| Deliverables | `channels/wecom` wrapper around existing primitives (behind flag); `channels/web_sse` fixture channel; `apps/platform_api` thin server hosting RunRuntime; `packages/platform-sdk-ts` generated from OpenAPI; `apps/web_chat` embeddable component rendering `RunEvent` streaming; per-channel delivery/feedback/idempotency/output-policy fixtures. |
| Acceptance | Existing WeCom tests pass with no production regression; one non-WeCom channel passes end-to-end against fakes; channel adapters never call backends directly (boundary scan); secret refs isolated per `BotInstance`/`ChannelBinding`; OpenAPI generates deterministically. |
| Tests | channel normalization/delivery/idempotency; feedback dedupe; output-policy fixtures; dependency-boundary scan; SDK generation smoke. |
| Privacy | `ChannelBinding` `secret_ref` only; no cross-channel payload sharing. |
| Risks | Channel abstraction leaking protocol; disturbing live WeCom. |
| Rollback | Per-channel flags off; current WeCom service path direct. |
| Note | Live WeCom remains served by the existing `services/wecom-service` path until a human promotes the wrapper after parity. |

### Phase 13 — SolutionLoader + Lawyer & Non-Legal Solutions
| Field | Plan |
|-------|------|
| Requirement IDs | `REQ-solution-loader`, `REQ-solution-backend-portability`, `REQ-solution-privacy-gate`, `REQ-nonlegal-solution-composability` |
| Goal | Prove the lawyer pack is a backend-portable solution, not platform core, and that a non-legal pack runs through the same contracts. |
| Deliverables | `SolutionLoader` impl; `solutions/lawfirm` neutral manifest + `materialize_for("hermes")` producing/refreshing a sanitized profile bundle; `solutions/demo_non_legal` pack; composability + solution-privacy gates. |
| Acceptance | Lawyer solution runs through platform contracts with **zero new legal top-level fields**; demo non-legal solution runs through the same contracts with no platform-code change; solution privacy scan rejects secrets/logs/DBs/media/raw payloads/customer docs; `materialize_for` has no undeclared side effects. |
| Tests | manifest validation; non-legal composability; solution privacy scan; loader no-side-effect tests. |
| Privacy | Bundles distributable only when sanitized. |
| Risks | Solution becomes a hidden fork / smuggles adapter assumptions. |
| Rollback | Mark a solution `compatibility_only`; core stays usable. |

---

## 6. Human gates (OUTSIDE the autonomous run)

These are **not** Phase 09–13 and must not block autonomous execution:
- **G-LIVE**: promote any new lane to default-ON for real lawyers — requires a human live smoke pass after parity.
- **G-TRIAL**: the Phase 8 five-workday lawyer trial — remains `human_needed` in milestone v1.0.

The autonomous build delivers a fully tested platform on fakes/fixtures + a parity report; humans decide cutover.

---

## 7. Test & gate strategy

- Keep `python scripts/run_v2_gates.py --json-summary` as the current V2 fail-fast gate (do not make it depend on default-OFF platform work).
- Each phase adds **phase-local / package-local** tests first. A new aggregate entrypoint `scripts/run_platform_gates.py` collects platform tests; it is wired into `run_v2_gates.py` only once stable, deterministic, and free of live/secret/Hermes-API dependencies.
- Live WeCom acceptance stays a human gate, never a fixture gate.

---

## 8. ADR set (authored in Phase 09)

`ADR-0001` platform layering · `ADR-0002` contract extension policy (extend `AdapterCapabilitySet`/`ArtifactRecord`) · `ADR-0003` Hermes invocation (probe, `/v1/runs` parity, one-shot fallback) · `ADR-0004` storage/audit + legal human-review invariant · `ADR-0005` Python core / TS client split · `ADR-0006` milestone namespace (Phase 09–13 vs PRD §11) · `ADR-0007` boundary-scan allowlist.

---

## 9. Autonomous execution (hand to Codex)

Prereqs already in place: `.planning/config.json` has `mode: yolo`, `auto_advance: true`, `skip_discuss: true`, `parallelization: true`. Milestone `v1.1` with Phase 09–13 is registered in `ROADMAP.md`/`REQUIREMENTS.md`/`STATE.md`.

Run, hands-free:

```
$gsd-autonomous --from 9 --to 13
```

Step-by-step alternative:

```
$gsd-progress --next --auto
```

Both run discuss(skipped)→plan→execute per phase with plan-check + verifier + nyquist gates from config. Phase 8 (v1.0 trial) and live cutover remain human and are not touched.

---

*Plan v5 authored 2026-06-29 under user delegation. Architecture basis: `agent-platform-north-star.md`.*
