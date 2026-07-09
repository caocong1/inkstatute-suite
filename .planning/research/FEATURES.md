# Feature Research

**Domain:** QQBot production webhook host composition, runtime channel registration, Protocol-path smoke hardening, controlled live integration
**Milestone:** v1.9 QQBot Host Composition
**Researched:** 2026-07-09
**Confidence:** HIGH (sourced from v1.8 audit gaps, shipped `packages/channels/qqbot` + WeCom host pattern, `DefaultRunRuntime` / feature-flag surfaces, smoke toolkit leaf-only path, industry webhook verify→ACK patterns)

## Scope Note

**Already shipped in v1.8 — do not treat as new table stakes:** full qqbot package loop (ingress/egress/session/adapter/feedback/smoke leaf dry-run), WeCom host service pattern, ChannelAdapter / BackendAdapter / RunRuntime contracts, feedback-service, output boundary, feature flags default OFF.

**This document covers only NEW host-composition capabilities for v1.9.**

## Feature Landscape

### Table Stakes (Operators Expect These)

Missing these = cannot claim a deployable QQBot webhook host; package-level green tests are insufficient.

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| Thin production webhook host | Operators need a single HTTPS callback URL that owns verify → ACK → ingress/session/feedback → deliver. v1.8 audit gap #1: no in-repo host composing this path. | MEDIUM | **Compose, do not reimplement.** Call `QQBotChannelAdapter.verify_and_ack` / `normalize_inbound` / `deliver`, `QQBotRuntimeIngress.handle_callback`, `handle_feedback_callback`. Mirror WeCom: host owns HTTP/secrets; package owns channel logic (`wecom-service` is primitives + ingress, not a second copy of QQ crypto). Prefer thin `services/qqbot-service` (or equivalent) over bloating the package. |
| Fast verify-and-ACK before heavy work | QQ (and industry webhook practice) expects quick HTTP success; interaction ACK (`PUT /interactions/{id}`) must not leave the client spinning. | MEDIUM | Industry pattern: verify → ACK (or 202) → process. InkStatute already has two-tier ACK in the adapter; host must return webhook ACK promptly and not bury `verify_and_ack` behind long agent runs. Full async queue is **not** required for v1.9 MVP if agent work stays bounded; do not invent a new queue service unless a plan requires it. |
| Flag→config→adapter wiring | Dual knobs (`RuntimeFeatureFlags.qqbot_channel_enabled` + `QQBotChannelConfig.enabled`) both default OFF; hosts must map them or live IO stays refused while operators think the flag is on. | LOW | Documented in `packages/channels/qqbot/README.md`. Adapter must **not** import feature flags. Host factory: `enabled=flags.qqbot_channel_enabled` (+ `from_env` / secret refs). Inject `token_manager` + transport only when enabled + secrets resolved (`_live_io_ready()`). |
| Runtime registration into `DefaultRunRuntime.channels` | Without injecting `QQBotChannelAdapter` into `channels=()`, the runtime has no selected QQ channel for the host instance; registration is host construction, not auto-discovery. | LOW | Reuse `DefaultRunRuntime(..., channels=(adapter,), feature_flags=flags, backend=...)`. Do **not** auto-register inside `DefaultRunRuntime.__init__`. Registration alone ≠ inbound webhook; pair with host ingress. |
| Smoke dry-run over full adapter/session Protocol path | Leaf-only dry-run (signature/sender/feedback helpers) gives false confidence; v1.8 audit gap #3. CI must prove Protocol IO + session/ingress wiring without network. | MEDIUM | Extend `scripts/smoke_test.py --dry-run` (and/or host tests) to call `verify_and_ack` → `QQBotRuntimeIngress` / session → Fake `DefaultRunRuntime` → `deliver` with Fake transports. Keep sanitized evidence schema; never dump secrets/`calls`/raw bodies. |
| Controlled live path remains HUMAN GATE | Operators need `--live` capability with fail-closed env checks and sanitized evidence; acceptance must not be auto-claimed by CI or phase complete. | LOW–MEDIUM | Keep `scripts/smoke_test.py --live` + runbook. Evidence must set `not_live_acceptance` / refuse dry-run claiming live. Do not add a V2 gate that requires live QQ. |
| Default-OFF + ADAPTER-04 isolation preserved | Production host must not enable QQ by default, import wecom into qqbot, add package deps, or unfreeze Protocols. | LOW | Existing tests: `test_feature_flag.py`, `test_no_wecom_import.py`, `test_contract_freeze_not_violated.py`. Host may depend on qqbot + platform-runtime; qqbot package stays `dependencies=[]`. |
| Secret refs in config; values only at process edge | Hosts resolve `*_REF` / env values at startup into adapter metadata / TokenManager — never commit secrets or put raw secrets into frozen config fields. | LOW | Smoke live uses value env vars (`INKSTATUTE_QQBOT_APP_ID`, etc.); production config uses refs (`from_env`). Runbook already forbids documenting refs as smoke CLI inputs. |

### Differentiators (Competitive / Platform Advantage)

Valuable for InkStatute’s multi-channel platform story; not required to close the “host exists” gap, but strengthen the milestone.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Same host shape as WeCom (channel-swappable composition) | Proves ChannelAdapter portability at **service** layer, not only package fixtures — second production channel host without forking runtime contracts. | MEDIUM | WeCom: `WeComRuntimeIngress` + protocol/sender primitives. QQ: `QQBotRuntimeIngress` + adapter Protocol. Shared: inject `RunRuntime`, solution binding, tenant/workspace/bot ids. |
| Protocol-path smoke as CI confidence gate | Dry-run that exercises the real adapter/session stack catches host wiring regressions before live UAT. | MEDIUM | Differentiator vs “unit tests green + leaf smoke.” Still not live acceptance. |
| Explicit dual-knob host factory (flags + config + live_io_ready) | Makes the default-OFF safety model auditable: one factory documents when network IO is allowed. | LOW | Returns `(runtime, adapter)` or host app with clear 503-when-disabled behavior. |
| Sanitized host/smoke evidence artifacts | Operators can archive pass/fail without leaking tokens, openids (hash only), or payloads — legal-privacy aligned. | LOW | Extend existing `inkstatute.qqbot.smoke_evidence.v1` allowlists for new Protocol-path steps. |
| Optional interaction ACK follow-up in live runbook | Documents when live `PUT /interactions/{id}` is safe (fresh interaction id) vs skip — reduces operator foot-guns. | LOW | Already sketched in `runbook/SMOKE_TEST_RUNBOOK.md`; host should expose the same semantics. |

### Anti-Features (Seem Useful — Explicitly Do Not Build)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Re-implement signature/normalize/send in the host | “Host owns the webhook, so copy the crypto.” | Divergent paths; package fixes never reach production; violates ADAPTER-04 composition model. | Thin host that **calls** adapter + ingress modules. |
| Auto-claim live QQ acceptance from CI / phase verify | “Green pipeline = production ready.” | Live needs real secrets, fresh `msg_id` window, human judgment; false acceptance. | `--live` HUMAN GATE; dry-run never sets live acceptance. |
| Auto-register QQBot inside `DefaultRunRuntime` when flag is True | “Registration should be automatic.” | Breaks embeddable DI; hides dual-knob mapping; couples runtime to one channel. | Explicit host factory `channels=(adapter,)`. |
| Unfreeze ChannelAdapter / add 7th Protocol method for “handle_webhook” | “Host needs a hook on the Protocol.” | Contract freeze + every implementer pays tax. | Host HTTP handler calls existing 6 methods. |
| Import wecom_service from qqbot (or merge hosts into one mega-gateway) | “Share WeCom ACK helpers.” | ADAPTER-04 / no-wecom invariant; V2 is not a full multi-channel gateway. | Shared logic stays in `channel-core` / `platform-runtime`; separate thin hosts. |
| New message queue / DB / service for v1.9 “scale” | Industry blogs push verify→enqueue→ACK. | Out of scope unless PRD/plan requires; adds ops surface before host exists. | Sync-or-bounded in-process composition first; queue only if ACK deadlines force it. |
| Enable QQBot flag by default in production images | “Make it work out of the box.” | Accidental live IO; secrets missing → flaky 503s or worse. | Default OFF; explicit env enable. |
| Treat `DefaultRunRuntime.channels` registration as sufficient “host done” | Checklist looks complete. | Inbound webhooks still have no URL; audit gap remains. | Registration **and** webhook ingress composition. |
| Leaf-only smoke “hardening” (more sender asserts, still no Protocol) | Easy PR. | Repeats v1.8 false confidence. | Must call adapter + session/ingress path. |
| Auto-synthesize legal skills from QQ feedback | Feedback loop “complete.” | Legal safety: human-reviewed `skill_candidate` only. | Reuse feedback-service classification; no auto-modify. |
| Claim Phase 5 WeCom UAT / Phase 8 lawyer trial as v1.9 done | Milestone closure pressure. | Carried human gates; not host-composition scope. | Leave carried; do not delete trial artifacts. |

## Feature Dependencies

```
v1.8 qqbot package (adapter, ingress, session, feedback, sender, signature)
    └──requires──> Thin production webhook host
                       └──requires──> Flag→config→adapter factory
                       └──requires──> DefaultRunRuntime.channels registration
                       └──enhances──> Protocol-path smoke dry-run

Flag→config mapping ──requires──> RuntimeFeatureFlags.qqbot_channel_enabled
                               └──requires──> QQBotChannelConfig.enabled + token_manager/transport when live

Protocol-path smoke ──requires──> Fake transports + FakeBackendAdapter
                               └──conflicts──> Live Urllib transports in default CI

Controlled --live ──enhances──> Host + smoke toolkit
                └──conflicts──> Auto-claim acceptance / CI-required live gate

WeCom host pattern ──informs──> QQ host shape (do not copy WeCom crypto)
```

### Dependency Notes

- **Host requires v1.8 package modules:** Host is composition only; if it reimplements leaves, milestone fails its own audit criteria.
- **Registration requires flag→config:** Injecting a disabled adapter into `channels` is not “enabled registration.”
- **Protocol-path smoke requires Fake stack:** Must not require `INKSTATUTE_QQBOT_*` value secrets in CI.
- **Live enhances but does not gate:** Host + dry-run Protocol path can ship without live evidence; live remains operator-run.
- **WeCom informs shape, not code:** Reuse DI / ingress-boundary pattern; never import `wecom_service` into qqbot.

## MVP Definition

### Launch With (v1.9)

Minimum to close v1.8 host-level gaps without claiming live acceptance.

- [ ] Thin QQBot webhook host composing `verify_and_ack` → ingress/session/feedback → `deliver` (default-OFF)
- [ ] Host factory: flag→`QQBotChannelConfig`→`QQBotChannelAdapter`→`DefaultRunRuntime.channels`
- [ ] Smoke `--dry-run` exercises full adapter/session Protocol path with Fake transports + sanitized evidence
- [ ] Controlled `--live` path retained as HUMAN GATE (fail-closed env; no auto-claim)
- [ ] ADAPTER-04 / Protocol freeze / no-wecom / flag default OFF preserved

### Add After Validation (v1.9.x / next)

- [ ] Durable wakeup/idempotency stores beyond process-local (when multi-instance host is real)
- [ ] Stronger verify→enqueue→ACK if QQ ACK deadlines force async under load
- [ ] Host health/readiness endpoints aligned with admin-console operational views
- [ ] Operator-run live evidence archived under human-gate process (still not CI-required)

### Future Consideration (later milestones)

- [ ] Full multi-channel gateway unifying WeCom + QQ + WeChat behind one process
- [ ] WebSocket QQ ingress mode (v1.8 deferred; webhook-first remains)
- [ ] Auto live acceptance / synthetic lawyer trial from smoke
- [ ] Production Codex/provider_model as required backends for QQ host

## Feature Prioritization Matrix

| Feature | User/Operator Value | Implementation Cost | Priority |
|---------|---------------------|---------------------|----------|
| Thin production webhook host | HIGH | MEDIUM | P1 |
| Flag→config→adapter factory | HIGH | LOW | P1 |
| `DefaultRunRuntime.channels` registration | HIGH | LOW | P1 |
| Protocol-path smoke dry-run | HIGH | MEDIUM | P1 |
| Controlled `--live` HUMAN GATE (keep + document) | HIGH | LOW | P1 |
| Sanitized evidence for new smoke steps | MEDIUM | LOW | P2 |
| WeCom-parity host DX (README/runbook) | MEDIUM | LOW | P2 |
| Async queue-buffered webhook | LOW (now) | HIGH | P3 |
| Multi-channel mega-gateway | LOW (now) | HIGH | P3 |
| WebSocket ingress | LOW (now) | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.9 launch (closes audit gaps)
- P2: Should have when cheap / documentation-adjacent
- P3: Explicitly defer

## Expected Behavior (InkStatute QQBot Host Composition)

1. **Disabled by default:** With flags/config OFF, webhook returns refuse/503-style behavior; no live OpenAPI; fixture/CI path remains green.
2. **Enabled host path:** HTTP callback → adapter `verify_and_ack` (incl. op=13 challenge) → message path via `QQBotRuntimeIngress` / session → runtime run → output boundary → `deliver`; INTERACTION path via `handle_feedback_callback` + interaction ACK semantics.
3. **Runtime sees the channel:** Constructed `DefaultRunRuntime` includes the QQ adapter in `channels` when the host enables QQ; mapping is explicit in host wiring.
4. **Smoke dry-run:** Exercises that same Protocol/session stack with Fakes; exit 0 + sanitized evidence; `not_live_acceptance=true`.
5. **Smoke live:** Operator-only; requires value env vars + fresh passive-reply `msg_id`; evidence must not be treated as milestone acceptance without human sign-off.

## Competitor / Ecosystem Feature Analysis

| Concern | Industry webhook hosts | Hermes / bot frameworks | InkStatute v1.9 approach |
|---------|------------------------|-------------------------|-------------------------|
| Callback ownership | Dedicated receiver service | Often gateway-owned | InkStatute-owned thin host (not Hermes gateway) |
| ACK latency | verify → enqueue → 202 | Varies | Prefer fast ACK via existing adapter two-tier ACK; queue optional later |
| Channel registration | Plugin registries / DI | Adapter registration tables | Explicit `DefaultRunRuntime(channels=...)` DI |
| CI confidence | Contract tests + recorded fixtures | Live sandbox flaky | Protocol-path dry-run + package unit tests; live human gate |
| Multi-channel | Shared gateway | Monolith adapters | Separate hosts; shared contracts (`channel-core`, Protocols) |

## Sources

- In-repo: `.planning/PROJECT.md` (v1.9 goals), `.planning/milestones/v1.8-MILESTONE-AUDIT.md` (host gaps), `.planning/MILESTONES.md`
- In-repo: `packages/channels/qqbot/` (adapter, ingress_runtime, config, README flag→config), `scripts/smoke_test.py`, `runbook/SMOKE_TEST_RUNBOOK.md`
- In-repo: `services/wecom-service/` (host-callable ingress primitives pattern), `packages/platform-runtime` (`DefaultRunRuntime`, `RuntimeFeatureFlags.qqbot_channel_enabled`)
- Sibling research: `.planning/research/ARCHITECTURE.md`, `STACK.md`, `PITFALLS.md` (v1.9 host composition)
- Ecosystem (MEDIUM confidence, pattern only): webhook verify→ACK / async worker guidance — [webhooks.cc verify-enqueue-ACK](https://webhooks.cc/blog/stop-doing-business-logic-in-webhook-handlers), [tolinku webhook architecture patterns](https://tolinku.com/blog/webhook-architecture-patterns/)

---
*Feature research for: v1.9 QQBot Host Composition*
*Researched: 2026-07-09*
*Replaces prior v1.8 QQ channel production FEATURES landscape for roadmap consumption*
