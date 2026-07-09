# Project Research Summary

**Project:** 墨律 InkStatute — v1.9 QQBot Host Composition
**Domain:** Thin production QQBot webhook host composition over shipped v1.8 channel packages
**Researched:** 2026-07-09
**Confidence:** HIGH

## Executive Summary

v1.9 closes the accepted v1.8 audit gaps: there is still no deployable InkStatute-owned QQBot webhook host, no production wiring of `QQBotChannelAdapter` into `DefaultRunRuntime.channels`, and smoke dry-run only exercises leaf helpers. Experts in this repo build channel hosts as thin composition layers — stdlib HTTP edge, package-owned Protocol IO, explicit DI into `DefaultRunRuntime` — not as second adapters or multi-channel gateways. Package-level QQBot (signature, normalize, token, egress, session, ingress, feedback, leaf smoke) is already validated and must be reused, not re-selected.

The recommended approach is a new `services/qqbot-service/` with `dependencies=[]`, mirroring admin-web-ui’s pure `handle_*_request` + `http.server` pattern and WeCom’s host/package split (without importing `wecom_service`). Host factory maps dual default-OFF knobs (`RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled`), injects transports only when live-ready, registers the adapter into `channels=()`, and composes `verify_and_ack` → message/feedback branch → ingress/session → `deliver`. Smoke extends `scripts/smoke_test.py --dry-run` across the full adapter/session Protocol path with Fakes; `--live` stays a HUMAN GATE.

Key risks are fat-host reimplementation, dual-knob desync, raw-body signature breakage, leaf-only smoke false confidence, Protocol unfreeze, WeCom import leakage, Hermes meta leak on QQ deliver, and auto-claiming live acceptance. Mitigate with composition-only host APIs, REG matrix tests, ACK-first webhook semantics, Protocol-path smoke evidence, freeze/no-wecom gates, output-boundary fixtures, and operator attestation for LIVE.

## Key Findings

### Recommended Stack

No new PyPI packages. Reuse vendored `_ed25519` + lazy `urllib` transports already shipped in v1.8; do not reintroduce `cryptography` / `httpx`. Host HTTP uses Python 3.11+ stdlib `http.server` with a testable pure handler. Composition imports existing `inkstatute-channels-qqbot`, `platform-runtime`, `feedback-service`, and Fake adapters for dry-run.

**Core technologies:**
- Python 3.11+ stdlib `http.server` — thin production webhook host — matches admin-web-ui / lawyer-web-chat; zero new deps
- `inkstatute-channels-qqbot` 0.1.0 — adapter / ingress / session / feedback primitives — host composes, never forks
- `platform-runtime` (`DefaultRunRuntime`, `RuntimeFeatureFlags`) — channel registration via constructor injection — no Protocol change
- `feedback-service` — INTERACTION → queue normalize/dedupe — PYTHONPATH composition like package tests
- stdlib `asyncio` + Fake transports — sync HTTP → async Protocol methods; CI dry-run without network

**What NOT to add:** FastAPI/Starlette, `qq-botpy` / WebSocket mode, new DB/queue/Redis, Protocol unfreeze, flag defaults flipped to True, WeCom imports into qqbot host.

Details: [STACK.md](STACK.md)

### Expected Features

v1.8 package loop is **not** new table stakes. v1.9 table stakes are host-composition capabilities only.

**Must have (table stakes):**
- Thin production webhook host composing `verify_and_ack` → ingress/session/feedback → `deliver` (default-OFF)
- Fast verify-and-ACK before heavy agent work (op=13 challenge + op=12 body promptly)
- Flag→config→adapter factory (dual knobs + transport injection for `_live_io_ready`)
- Explicit `DefaultRunRuntime.channels` registration (not auto-discovery)
- Smoke dry-run over full adapter/session Protocol path with Fake transports + sanitized evidence
- Controlled `--live` path retained as HUMAN GATE (no CI auto-claim)
- ADAPTER-04 / Protocol freeze / no-wecom / secrets-as-refs preserved

**Should have (competitive):**
- WeCom-parity host shape (channel-swappable composition at service layer)
- Protocol-path smoke as CI confidence gate
- Explicit dual-knob factory with 503-when-disabled
- Sanitized evidence allowlist extensions for new Protocol steps

**Defer (v1.9.x / later):**
- Durable wakeup/idempotency stores for multi-instance
- Async verify→enqueue→ACK queue service
- Multi-channel mega-gateway; WebSocket QQ ingress
- Auto live acceptance / synthetic lawyer trial from smoke

Details: [FEATURES.md](FEATURES.md)

### Architecture Approach

**Create `services/qqbot-service/`.** Do not extend `wecom-service` with QQ routes. Package stays library-pure; host owns HTTP edge, secret resolution, wiring, and ACK-first composition. ChannelAdapter remains frozen at 6 methods; registration is host construction, not `platform-runtime` auto-discovery.

**Major components:**
1. `qqbot-service` webhook host — HTTP receive, raw-body capture, compose Protocol path, return ACK
2. Host wiring factory — flag→config→adapter→`DefaultRunRuntime.channels`→ingress
3. Reused `QQBotChannelAdapter` / `QQBotRuntimeIngress` / `QQBotSessionRuntime` / `feedback_ingress` — Protocol IO + session/feedback
4. Reused `DefaultRunRuntime` + `RuntimeFeatureFlags` — embeddable runtime; flags default OFF
5. Modified `scripts/smoke_test.py` — Protocol-path dry-run + live HUMAN GATE

Details: [ARCHITECTURE.md](ARCHITECTURE.md)

### Critical Pitfalls

1. **Fat host reimplements package logic** — compose public adapter/ingress/feedback APIs only; no duplicated Ed25519/normalize/send
2. **Package-green ≠ host complete** — done requires webhook entrypoint + Protocol-path dry-run, not 321 unit tests alone
3. **Dual-knob desync** — map `qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and inject transports when live IO intended
4. **Raw-body / signature break** — read bytes once before JSON parse; never default-bypass verify
5. **Leaf-only smoke or CI `--live`** — dry-run must call adapter + session/ingress + deliver with Fakes; live stays operator HUMAN GATE
6. **Protocol unfreeze / WeCom import / meta leak / Phase 08 deletion** — keep 6/9 methods; no `wecom_service` in qqbot; `apply_output_policy` on all egress; preserve lawyer-trial artifacts

Details: [PITFALLS.md](PITFALLS.md)

## Implications for Roadmap

Based on research, suggested phase structure (roadmap may renumber):

### Phase 1: Host Skeleton + Safety Baseline (SAFETY/HOST)
**Rationale:** Gate coverage and isolation invariants must exist before HTTP composition ships.
**Delivers:** `services/qqbot-service/` package layout, `pyproject.toml` with `dependencies=[]`, V2 gate PYTHONPATH entry, tests for default-OFF / no-wecom / no Protocol-contract edits.
**Addresses:** Default-OFF + ADAPTER-04 isolation; secret-ref discipline.
**Avoids:** Protocol unfreeze; WeCom import leakage; Phase 08 deletion; shipping HTTP before wiring invariants.

### Phase 2: Runtime Registration / Wiring (REG)
**Rationale:** Ingress composition needs a factory that correctly maps dual knobs and injects the adapter into `channels=()`.
**Delivers:** `wiring.py` factory: flags→`QQBotChannelConfig`→`QQBotChannelAdapter`→`DefaultRunRuntime(channels=...)`; FakeBackend unit tests; disabled path refuses live IO.
**Addresses:** Flag→config→adapter wiring; runtime registration.
**Avoids:** Dual-knob desync; auto-register inside `DefaultRunRuntime`; registration-without-webhook treated as done (pair with Phase 3).

### Phase 3: Webhook Composition Path (HOST)
**Rationale:** Closes v1.8 audit gap #1 — the missing production callback URL path.
**Delivers:** Pure `handle_qqbot_webhook_request` + thin `http.server` wrapper; raw body → `verify_and_ack` → challenge / feedback / `QQBotRuntimeIngress` → output boundary → `deliver`; ACK-first semantics; Fake transports in unit tests.
**Addresses:** Thin production webhook host; fast verify-and-ACK.
**Avoids:** Fat host; body re-serialization; sync agent before ACK; Hermes meta leak; Hermes-as-channel-boundary.

### Phase 4: Smoke Protocol-Path Hardening (SMOKE)
**Rationale:** Leaf-only dry-run was the v1.8 false-confidence gap; CI must prove host/package Protocol wiring without network.
**Delivers:** Extended `scripts/smoke_test.py --dry-run` steps (`adapter_ack`, normalize/ingress, deliver); evidence allowlist; `not_live_acceptance=true`.
**Addresses:** Full adapter/session Protocol-path smoke; sanitized evidence.
**Avoids:** Leaf-only “hardening”; Urllib/network in CI dry-run.

### Phase 5: Controlled Live Integration (LIVE)
**Rationale:** Live capability is required for operators but must not redefine milestone acceptance.
**Delivers:** Host + smoke `--live` with env secrets + Urllib transports; runbook updates; sanitized candidate evidence only.
**Addresses:** Controlled live path as HUMAN GATE.
**Avoids:** Auto-claim live acceptance from CI/`--live` exit 0; conflating Phase 05/08 WeCom gates with QQ live.

### Phase Ordering Rationale

- Safety/wiring before HTTP edge — prevents shipping an insecure or desynced host
- Composition before smoke claims — smoke must call the same helpers the host uses
- Live last and gated — dry-run Protocol path can ship without live evidence
- Package modules are complete — do not re-phase signature/normalize/token work

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (HOST):** Async post-ACK worker vs in-request completion for long agent runs — decide ACK scheduling under QQ ~3s window
- **Phase 5 (LIVE):** Operator evidence / attestation schema for human-gate archive (reuse smoke evidence v1 with live steps)

Phases with standard patterns (skip research-phase):
- **Phase 1 (SAFETY/HOST skeleton):** admin-web-ui + gate-coverage patterns are established
- **Phase 2 (REG):** README already documents flag→config; constructor injection is frozen embeddable pattern
- **Phase 4 (SMOKE):** Extend existing smoke toolkit; Fake stack already in-repo

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | In-repo patterns (admin-web-ui, qqbot empty-deps, urllib/_ed25519); explicit rejection of v1.8 draft cryptography/httpx |
| Features | HIGH | Sourced from v1.8 audit gaps + PROJECT.md active HOST/SMOKE/LIVE requirements |
| Architecture | HIGH | Clear NEW vs REUSE vs FROZEN table; WeCom parallel documented without coupling |
| Pitfalls | HIGH | Host-composition pitfalls mapped to phases; QQ raw-body/op=13 docs + prior forge incidents as pattern warnings |

**Overall confidence:** HIGH

### Gaps to Address

- **Post-ACK concurrency model:** Whether v1.9 MVP uses bounded in-process follow-up vs a minimal async worker — resolve in Phase 3 plan; do not invent a queue service unless ACK deadlines force it
- **HTTP server binding details:** stdlib `ThreadingHTTPServer` vs shared-loop thread for asyncio — confirm in plan-phase only if deps are proposed (default: stdlib, no ASGI)
- **Live attestation fields:** Exact operator sign-off artifact shape for LIVE acceptance — document in runbook; keep out of CI gates
- **Multi-instance durability:** In-memory wakeup/idempotency acceptable for controlled trial; flag as tech debt if multi-worker deploy appears

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — v1.9 milestone goals and active requirements
- `.planning/milestones/v1.8-MILESTONE-AUDIT.md` — host / registration / smoke gaps
- `packages/channels/qqbot/` — adapter, ingress, config, transports, freeze/no-wecom tests
- `packages/platform-runtime/` — `DefaultRunRuntime`, `RuntimeFeatureFlags`, frozen Protocols
- `services/admin-web-ui/` — stdlib HTTP + pure handler pattern
- `services/wecom-service/` — host/package split reference (library-only; no QQ routes)
- `scripts/smoke_test.py` — leaf dry-run + `--live` HUMAN GATE baseline
- `AGENTS.md` — channel ownership, secrets, output boundary, empty-deps culture

### Secondary (MEDIUM confidence)
- QQ Bot signature / event subscription docs — raw body + op=13 validation patterns
- Industry webhook verify→ACK guidance — pattern only; queue deferred for v1.9 MVP

### Tertiary (LOW–MEDIUM confidence)
- External forge incidents when webhook verify skipped — pattern match, not InkStatute-specific
- Community webhook XOR WebSocket notes — confirms webhook-first scope for v1.9

---
*Research completed: 2026-07-09*
*Ready for roadmap: yes*
