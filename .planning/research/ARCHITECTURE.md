# Architecture Research

**Domain:** QQBot production webhook host composition — runtime channel registration, Protocol-path smoke hardening, controlled live QQ integration
**Researched:** 2026-07-09
**Confidence:** HIGH (sourced from v1.8 audit gaps, shipped qqbot package modules, WeCom host pattern, `DefaultRunRuntime` injection surface, smoke toolkit leaf-only path, ADAPTER-04 isolation invariants)

## Verdict (roadmap-facing)

**Create a new thin host service `services/qqbot-service/`.** Do **not** extend `services/wecom-service` with QQ webhook routes.

| Decision | Choice | Why |
|----------|--------|-----|
| Host placement | **NEW** `services/qqbot-service/` | WeCom host is WeCom-protocol-specific; ADAPTER-04 forbids qqbot↔wecom coupling; gate coverage already expects every `services/*/src` |
| Package modules | **REUSE** `packages/channels/qqbot` | v1.8 shipped composable verify/normalize/token/sender/session/ingress/adapter/feedback — host only composes |
| Runtime registration | **Host wiring module** | Maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled`, injects adapter into `DefaultRunRuntime.channels` |
| Protocol freeze | **Unchanged** | ChannelAdapter stays 6 methods; no `platform-runtime` / `platform-contract` surface edits |
| Default-OFF | **Preserved** | Dual knob: platform flag + adapter config both default `False`; host refuses live IO when either is off |
| Live acceptance | **Human gate** | `--live` / operator evidence only; dry-run never claims live acceptance |

## Standard Architecture

### System Overview

v1.8 delivered the **package** layer. v1.9 adds the missing **host** layer that joins Protocol IO with session/ingress/feedback on one webhook path.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     External Platform Layer                              │
│  ┌─────────────────────┐              ┌──────────────────────────┐       │
│  │ QQ Open Platform    │              │ WeCom (unchanged)        │       │
│  │ webhook + OpenAPI   │              │ callback + send API      │       │
│  └──────────┬──────────┘              └────────────┬─────────────┘       │
├─────────────┼──────────────────────────────────────┼─────────────────────┤
│             ▼                                      ▼                     │
│  ┌──────────────────────────┐      ┌──────────────────────────────┐      │
│  │ qqbot-service [NEW HOST] │      │ wecom-service [REUSE]        │      │
│  │ thin webhook composition │      │ WeCom-owned receive/send     │      │
│  │                          │      │ (do NOT add QQ routes here)  │      │
│  │  HTTP → RawInbound       │      └──────────────┬───────────────┘      │
│  │  → verify_and_ack        │                     │                      │
│  │  → message | feedback    │                     │                      │
│  │  → ingress/session       │                     │                      │
│  │  → deliver               │                     │                      │
│  │  → flag→config wiring    │                     │                      │
│  └──────────┬───────────────┘                     │                      │
│             │                                     │                      │
│  ┌──────────▼─────────────────────────────────────▼──────────────┐       │
│  │ packages/channels/qqbot [REUSE — v1.8 shipped]                │       │
│  │ adapter · signature · normalize · token · sender              │       │
│  │ session_runtime · ingress_runtime · feedback_ingress          │       │
│  └──────────┬────────────────────────────────────────────────────┘       │
│             │                                                            │
│  ┌──────────▼────────────────────────────────────────────────────┐       │
│  │ ChannelAdapter Protocol (6 methods, FROZEN)                   │       │
│  │ channel_id · capabilities · verify_and_ack ·                  │       │
│  │ normalize_inbound · deliver · health                          │       │
│  └──────────┬────────────────────────────────────────────────────┘       │
│             ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐        │
│  │ DefaultRunRuntime [REUSE — inject channels=[qqbot_adapter]]  │        │
│  │ + FakeBackend (smoke) / Hermes BackendAdapter (live host)    │        │
│  └──────────┬───────────────────────────────────────────────────┘        │
│             ▼                                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐       │
│  │ feedback-service │  │ channel-core     │  │ smoke_test.py     │       │
│  │ [REUSE queue]    │  │ [REUSE]          │  │ [MODIFY harden]   │       │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| QQBot webhook host | Own HTTP receive, raw-body capture, secret resolution, compose Protocol path, return ACK body | **NEW** | `services/qqbot-service/` |
| Host composition root | Wire flags→config→adapter→runtime→ingress; default-OFF refuse path | **NEW** | `services/qqbot-service/.../wiring.py` (or equivalent) |
| Host webhook handler | `verify_and_ack` → branch message/feedback/challenge → ingress or feedback queue → optional `deliver` | **NEW** | `services/qqbot-service/.../webhook.py` |
| QQBotChannelAdapter | 6-method Protocol IO (signature, normalize, deliver, health) | **REUSE** | `packages/channels/qqbot/.../adapter.py` |
| QQBotRuntimeIngress | Sanitized envelope → session runtime → `create_run` / resume | **REUSE** | `packages/channels/qqbot/.../ingress_runtime.py` |
| QQBotSessionRuntime | Session resolution / interrupt / memory orchestration | **REUSE** | `packages/channels/qqbot/.../session_runtime.py` |
| feedback_ingress | INTERACTION → FeedbackEvent dict; deferred interaction ACK | **REUSE** | `packages/channels/qqbot/.../feedback_ingress.py` |
| DefaultRunRuntime | Embeddable runtime; holds `channels` tuple | **REUSE** (host constructs) | `packages/platform-runtime/.../runtime.py` |
| RuntimeFeatureFlags | `qqbot_channel_enabled` default `False` | **REUSE** | `packages/platform-runtime/.../feature_flags.py` |
| feedback-service queue | Dedupe / classify / pending queue (channel-neutral) | **REUSE** | `services/feedback-service/.../queue.py` |
| wecom-service | WeCom-only host | **UNCHANGED** | `services/wecom-service/` |
| smoke_test.py | Dry-run + `--live` human gate; must exercise Protocol stack | **MODIFY** | `scripts/smoke_test.py` |
| ChannelAdapter Protocol | Frozen 6-method surface | **FROZEN** | `packages/platform-runtime/.../protocols.py` |

## Recommended Project Structure

```
services/qqbot-service/
├── src/qqbot_service/
│   ├── __init__.py
│   ├── wiring.py              # NEW: flag→config→adapter→DefaultRunRuntime registration
│   ├── webhook.py             # NEW: HTTP callback → RawInbound → composition
│   ├── http_server.py         # NEW: thin stdlib/async server (lawyer-web-chat pattern)
│   ├── secrets.py             # NEW: resolve secret refs from env (never commit values)
│   └── health.py              # NEW: host health wrapping adapter.health()
├── tests/
│   ├── test_wiring_default_off.py
│   ├── test_webhook_composition.py   # verify→ingress/feedback→deliver (Fake transports)
│   ├── test_runtime_registration.py
│   ├── test_no_wecom_import.py        # host also must not import wecom_service
│   └── test_gate_presence.py
├── pyproject.toml
└── README.md

scripts/
└── smoke_test.py              # MODIFY: add Protocol-path dry-run steps

packages/channels/qqbot/       # REUSE — no Protocol changes; optional tiny host helpers only if needed
services/wecom-service/        # UNCHANGED — no QQ routes
```

### Structure Rationale

- **New service, not WeCom extension:** `wecom-service` owns WeCom crypto/XML/task-flow semantics. QQ uses Ed25519 + gateway `{op,t,d}` + two-tier ACK. Merging channels into one service recreates a multi-channel gateway (explicitly out of V2 scope) and risks violating ADAPTER-04 isolation.
- **Package stays library-pure:** v1.8 modules intentionally perform no HTTP server ownership. Host owns network edge; package owns Protocol + pure orchestration — same split as `WeComRuntimeIngress` docs ("Hosts own those concerns").
- **Wiring lives in the host:** README already states hosts map `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled`. Adapter must not import feature flags.
- **Stdlib-first HTTP:** Match `lawyer-web-chat` / qqbot `dependencies=[]` culture; avoid new framework deps unless a phase plan explicitly requires them.
- **Gate coverage:** Adding `services/qqbot-service/src` requires a V2 gate PYTHONPATH entry (`test_gate_coverage.py`).

## Architectural Patterns

### Pattern 1: Thin Host Composition (not a second adapter)

**What:** Host is a short orchestration script around already-shipped package APIs. It does not re-implement signature, normalize, session, or send logic.

**When to use:** Always for v1.9 webhook path.

**Trade-offs:** Host stays small and testable; business logic remains in the package under 321 unit tests.

**Example:**
```python
# services/qqbot-service — composition only
ack = await adapter.verify_and_ack(raw)
if not ack.accepted:
    return http_response(ack)
if challenge := ack.metadata.get("validation_challenge_response"):
    return http_json(200, challenge)
body = ack.metadata.get("http_callback_ack_body") or {"op": 12}

normalized = await adapter.normalize_inbound(raw)
if normalized.feedback is not None:
    fb = handle_feedback_callback(payload, received_at=raw.received_at)
    # compose into feedback_service.queue (PYTHONPATH), ensure_interaction_ack if pending_host
elif normalized.message is not None:
    outcome = await ingress.handle_callback(payload, received_at=raw.received_at, ...)
    # after run completes + output boundary: adapter.deliver(ChannelDelivery(...))
return http_json(ack.status_code, body)
```

### Pattern 2: Dual-Knob Default-OFF Registration

**What:** Platform flag and adapter config both default `False`. Host is the only place that maps flag → config and injects the adapter into `DefaultRunRuntime(channels=...)`.

**When to use:** Host process boot / test fixtures.

**Trade-offs:** Two knobs prevent accidental live IO if only one surface is flipped; requires host discipline.

**Example:**
```python
flags = RuntimeFeatureFlags()  # qqbot_channel_enabled=False by default
config = QQBotChannelConfig.from_env(env)
# Host maps platform flag into adapter config (README contract)
config = replace(config, enabled=bool(flags.qqbot_channel_enabled and config.enabled))
adapter = QQBotChannelAdapter(
    config,
    token_manager=token_manager if config.enabled else None,
    transport=transport if config.enabled else None,
)
runtime = DefaultRunRuntime(
    backend=backend,
    channels=(adapter,),
    feature_flags=flags,
)
ingress = QQBotRuntimeIngress(runtime=runtime, solution=solution, ...)
```

### Pattern 3: Smoke Exercises Protocol Stack, Not Leaf Helpers Alone

**What:** Dry-run must call `verify_and_ack` → `normalize_inbound` / `QQBotRuntimeIngress` → Fake `DefaultRunRuntime` → `deliver` with Fake transports. Leaf signature/sender steps may remain as secondary evidence.

**When to use:** CI dry-run and operator preflight before `--live`.

**Trade-offs:** Slightly slower dry-run; catches host-composition regressions that leaf tests miss (the v1.8 accepted gap).

## Data Flow

### Request Flow — Host Webhook (v1.9 composition)

```
[QQ Platform POST]
    │  raw body bytes + X-Signature-Ed25519 + X-Signature-Timestamp
    ▼
[qqbot-service HTTP handler]
    │  1. Capture raw body BEFORE JSON parse
    │  2. Resolve bot_secret from env/ref (never log)
    │  3. Build RawInbound(channel_id="qqbot", payload_ref, metadata={
    │       payload, request_body, x_signature_*, bot_secret, ...})
    ▼
[QQBotChannelAdapter.verify_and_ack]     # Protocol
    │  disabled → 503 | bad sig → 401 | op=13 → challenge JSON
    │  else → AckResponse(200, http_callback_ack_body={op:12},
    │          optional interaction_ack_*)
    ▼
[Branch]
    ├─ validation challenge → return challenge body immediately
    ├─ INTERACTION / feedback
    │     handle_feedback_callback → feedback_service.queue
    │     ensure_interaction_ack if pending_host + live IO ready
    └─ C2C / GROUP message
          QQBotRuntimeIngress.handle_callback
            → QQBotSessionRuntime → DefaultRunRuntime.create_run|resume
          → (async) poll/result → output boundary → adapter.deliver
    ▼
[HTTP 200 with op=12 / challenge]   # ACK deadline ~3s; heavy work after ACK
```

### Runtime Registration Flow

```
[Host boot]
    RuntimeFeatureFlags (qqbot_channel_enabled default False)
         │
         ▼ map
    QQBotChannelConfig.enabled
         │
         ▼ construct
    QQBotChannelAdapter(+ token_manager/transport only when enabled)
         │
         ▼ inject
    DefaultRunRuntime(channels=(adapter,), feature_flags=flags, backend=...)
         │
         ▼ inject
    QQBotRuntimeIngress(runtime=..., solution=..., tenant/workspace/bot=...)
```

Registration does **not** live inside `packages/platform-runtime` (no auto-discovery registry). It is explicit host construction — same embeddable DI style as Phase 10 `DefaultRunRuntime`.

### Smoke Protocol-Path Flow (hardened dry-run)

```
scripts/smoke_test.py --dry-run
    │
    ├─ [existing] signature leaf (demo vectors)          # keep
    ├─ [NEW] adapter.verify_and_ack(Fake RawInbound)     # Protocol
    ├─ [NEW] adapter.normalize_inbound OR ingress.handle_callback
    │         with FakeBackend + DefaultRunRuntime
    │         (run_runtime_enabled=True only inside smoke fixture flags)
    ├─ [NEW] adapter.deliver(ChannelDelivery) via FakeMessageTransport
    ├─ [existing] feedback handle_feedback_callback      # keep / fold in
    └─ sanitize_evidence → not_live_acceptance=true
```

`--live` remains a separate human gate: real env secrets, Urllib transports, never auto-claim acceptance.

### Key Data Flow Changes vs v1.8

1. **Host owns the webhook edge** that v1.8 left as an accepted gap.
2. **`DefaultRunRuntime.channels` becomes non-empty** for QQ in host/smoke wiring (was unused for production QQ).
3. **Smoke stops being leaf-only** — Protocol + session path become first-class dry-run steps.
4. **No change** to Hermes gateway ownership, contract schemas, or ChannelAdapter method count.

## New vs Modified vs Frozen

| Item | Action |
|------|--------|
| `services/qqbot-service/` | **NEW** |
| `scripts/smoke_test.py` | **MODIFY** (Protocol-path steps + evidence allowlist) |
| V2 gate list / PYTHONPATH | **MODIFY** (cover new service src) |
| `packages/channels/qqbot` | **REUSE** (touch only if tiny host-facing export needed) |
| `services/wecom-service` | **UNCHANGED** |
| `packages/platform-runtime/protocols.py` | **FROZEN** |
| `packages/platform-contract` | **FROZEN** |
| `RuntimeFeatureFlags.qqbot_channel_enabled` default | **UNCHANGED** (`False`) |
| Hermes gateway as channel boundary | **FORBIDDEN** |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Controlled trial (v1.9) | Single-process host; in-memory interrupt/wakeup stores; Fake transports in CI; Urllib in live |
| Multi-instance | Shared token cache + durable wakeup/interrupt stores injected by host; ACK-first then async run processing |
| High volume | Queue after ACK; host-layer only — package Protocol methods stay sync-callable |

### Scaling Priorities

1. **ACK deadline first:** Return op=12 / challenge within QQ's ~3s window; run agent work after ACK.
2. **Token single-flight:** Reuse v1.8 TokenManager locking under concurrent deliver.

## Anti-Patterns

### Anti-Pattern 1: Extending wecom-service with QQ Routes

**What people do:** Add `/qqbot/callback` next to WeCom handlers "to share one deployable."

**Why it's wrong:** Couples unrelated crypto/payload stacks; invites wecom imports into QQ paths; recreates multi-channel gateway; violates ADAPTER-04 spirit and v1.8 isolation tests.

**Do this instead:** New `services/qqbot-service/` that imports `inkstatute_channels_qqbot` + `platform_runtime` + `feedback_service` only.

### Anti-Pattern 2: Putting Registration Inside platform-runtime

**What people do:** Auto-register QQBot when `qqbot_channel_enabled=True` inside `DefaultRunRuntime.__init__`.

**Why it's wrong:** Runtime would depend on a concrete channel package, breaking embeddability and Protocol neutrality.

**Do this instead:** Host constructs adapter and passes `channels=(adapter,)`.

### Anti-Pattern 3: Smoke Leaf-Only "Green" as Host Proof

**What people do:** Keep dry-run on signature/sender helpers and claim host composition done.

**Why it's wrong:** Exactly the v1.8 audit gap — package-internal wiring ≠ production webhook composition.

**Do this instead:** Dry-run must invoke adapter Protocol methods and session/ingress with FakeBackend.

### Anti-Pattern 4: Claiming Live Acceptance from CI

**What people do:** Flip `--live` in CI or set `not_live_acceptance=false` from dry-run.

**Why it's wrong:** Live QQ requires operator secrets and human judgment; milestone done-definition excludes auto-claimed live acceptance.

**Do this instead:** Dry-run always `not_live_acceptance=true`; `--live` is HUMAN GATE with sanitized evidence only.

### Anti-Pattern 5: Hermes Gateway as QQ Ingress

**What people do:** Point QQ webhook at Hermes gateway adapters.

**Why it's wrong:** InkStatute owns channel ingress/egress; Hermes provides agent logic only (`AGENTS.md`).

**Do this instead:** QQ → `qqbot-service` → `DefaultRunRuntime` → Hermes `BackendAdapter`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| QQ webhook | Host HTTP POST; raw body + Ed25519 headers → `RawInbound` | Host captures bytes before JSON parse |
| QQ OpenAPI | Adapter `deliver` / `ack_interaction` via injected transport | Live only when dual-knob ON + transports injected |
| Hermes | Unchanged BackendAdapter via runtime | Channel tag `qqbot` only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| qqbot-service ↔ packages/channels/qqbot | Direct import of adapter/ingress/feedback helpers | Host composes; package stays IO-injectable |
| qqbot-service ↔ platform-runtime | Construct `DefaultRunRuntime`, flags, Fake/real backend | No Protocol edits |
| qqbot-service ↔ feedback-service | Pass FeedbackEvent dicts into queue helpers | Same composition as package tests |
| qqbot-service ↔ wecom-service | **None** | Enforce with host-level no-wecom-import test |
| smoke_test ↔ host/package | Prefer calling same composition helpers host uses | Avoid divergent "smoke-only" path |

## Suggested Build Order (phases)

Dependency-respecting order for roadmap planning:

1. **Host skeleton + safety baseline**
   - Create `services/qqbot-service` package layout, pyproject, gate PYTHONPATH
   - Tests: default-OFF, no wecom import, no Protocol/contract edits
   - *Avoids:* shipping HTTP before wiring invariants

2. **Runtime registration / wiring**
   - Implement flag→config→`QQBotChannelAdapter`→`DefaultRunRuntime.channels` factory
   - Unit-test registration with FakeBackend; disabled path refuses live IO
   - *Depends on:* skeleton; *enables:* ingress composition

3. **Webhook composition path**
   - HTTP handler: raw body → `verify_and_ack` → challenge / feedback / `QQBotRuntimeIngress` → `deliver`
   - Fake transports only in unit tests; ACK-first semantics
   - *Depends on:* wiring; *closes:* v1.8 host-composition gap

4. **Smoke Protocol-path hardening**
   - Extend `scripts/smoke_test.py` dry-run to exercise adapter + session/ingress + deliver
   - Expand evidence allowlist; keep `not_live_acceptance=true`
   - *Depends on:* composition helpers (can share host wiring functions)

5. **Controlled live integration capability**
   - Host + smoke `--live` path with env secrets + Urllib transports
   - Runbook updates; **do not** auto-claim live acceptance (HUMAN GATE)
   - *Depends on:* dry-run Protocol path green

**Phase ordering rationale:** Safety/wiring before HTTP edge; composition before smoke claims; live last and gated. Package modules are already complete — do not re-phase signature/normalize/token work.

**Research flags for later phase research:**
- Host HTTP server choice (stdlib vs minimal ASGI): likely standard patterns; confirm in plan-phase only if deps proposed
- Async post-ACK worker vs in-request FakeBackend completion for smoke: needs phase-level decision
- Live QQ operator evidence schema: reuse smoke evidence v1 with extra live steps

## Sources

- `.planning/PROJECT.md` — v1.9 milestone goal and active HOST/SMOKE/LIVE requirements
- `.planning/milestones/v1.8-MILESTONE-AUDIT.md` — accepted host-level gaps
- `packages/channels/qqbot/README.md` — host responsibility for flag→config mapping
- `packages/channels/qqbot/.../adapter.py` — Protocol IO + `_live_io_ready` gate
- `packages/channels/qqbot/.../ingress_runtime.py` — host-callable ingress (no network)
- `packages/channels/qqbot/.../feedback_ingress.py` — feedback composition helper
- `packages/platform-runtime/.../protocols.py` — frozen ChannelAdapter (6 methods)
- `packages/platform-runtime/.../runtime.py` — `DefaultRunRuntime(channels=...)`
- `packages/platform-runtime/.../feature_flags.py` — `qqbot_channel_enabled=False`
- `services/wecom-service/.../ingress_runtime.py` — reference host/package split pattern
- `scripts/smoke_test.py` — current leaf-only dry-run (gap to close)
- `AGENTS.md` — InkStatute owns channel boundary; Hermes is agent backend only
- Prior v1.8 architecture research in this file (package-layer baseline; host deferred)

---
*Architecture research for: v1.9 QQBot Host Composition*
*Researched: 2026-07-09*
