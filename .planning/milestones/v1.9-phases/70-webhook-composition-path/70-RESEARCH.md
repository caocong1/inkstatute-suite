# Phase 70: Webhook Composition Path - Research

**Researched:** 2026-07-10
**Domain:** Thin InkStatute-owned QQBot webhook host composing package Protocol methods with ACK-first HTTP semantics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — discuss phase was skipped. All implementation choices are at the agent's discretion.

### Claude's Discretion
Use ROADMAP phase goal, success criteria, Phase 68–69 host patterns (`wiring.py`, secret refs, refuse-when-disabled), and codebase conventions.

### Deferred Ideas (OUT OF SCOPE)
- Smoke Protocol-path hardening → Phase 71
- Live QQ / `--live` HUMAN GATE → Phase 72
- Durable multi-worker idempotency store, FastAPI, WeCom imports, Protocol unfreeze
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HOST-01 | Thin InkStatute-owned QQBot webhook host composes `verify_and_ack` → ingress/session/feedback → `deliver` without reimplementing package crypto/normalize/send | Host calls `QQBotChannelAdapter` Protocol methods + `QQBotRuntimeIngress.handle_callback` + `handle_feedback_callback`; no local Ed25519/normalize/sender copies |
| HOST-02 | Webhook returns verify-and-ACK promptly (op=13 validation challenge and op=12 body ACK) before heavy agent work | Pure handler returns HTTP status/body from `AckResponse` before scheduling post-ACK ingress/agent/deliver; injectable scheduler proves ordering |
</phase_requirements>

## Summary

Phases 68–69 shipped `services/qqbot-service/` with secret-ref config, ADAPTER-04 isolation, and `build_qqbot_wired_runtime` (flag→config→adapter→`DefaultRunRuntime.channels`, disabled refuse). Package `inkstatute_channels_qqbot` already owns signature verify, op=13 challenge, op=12 metadata, normalize, ingress/session, feedback helper, and deliver with Fake/Urllib transports. [VERIFIED: wiring.py; adapter.py; STACK.md]

Phase 70 adds the missing **HTTP composition edge**: a pure `handle_qqbot_webhook_request` (admin-web-ui pattern) plus thin `BaseHTTPRequestHandler` wrapper that (1) captures raw body bytes once, (2) builds `RawInbound` with signature metadata, (3) awaits only `verify_and_ack`, (4) returns challenge / `{"op":12}` / refuse status immediately, then (5) schedules post-ACK message/feedback → ingress/session → `deliver` without blocking the webhook response. Unit tests use Fake transports + FakeBackend only — no live QQ network. [CITED: .planning/research/STACK.md; PITFALLS.md Pitfall 5–6]

**Primary recommendation:** Implement composition-only modules under `services/qqbot-service/src/qqbot_service/` (`webhook.py` pure handler + `http_server.py` wrapper), reuse `build_qqbot_wired_runtime`, inject a `post_ack_scheduler` for ACK-first proofs, apply `DefaultRunRuntime.output_boundary` when building egress `ChannelDelivery`, keep `dependencies = []`, and prove HOST-01/HOST-02 with Fake-only host tests.

## Project Constraints

- AGENTS.md: InkStatute owns channel ingress; Hermes is agent backend only; no WeCom import into qqbot host; no secrets in repo.
- Empty-deps culture: stdlib `http.server` only (admin-web-ui / lawyer-web-chat pattern).
- Dual default-OFF knobs already mapped in Phase 69 — webhook must use the composed factory, not bare adapter construction.
- ChannelAdapter remains frozen at 6 methods; do not edit `platform-runtime` Protocols.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw body capture + HTTP edge | Host (`http_server.py`) | — | Signature requires exact bytes; stdlib `rfile.read` once [CITED: PITFALLS Pitfall 5] |
| Pure request composition | Host (`webhook.py`) | — | Testable without binding a port [VERIFIED: admin_web_ui.server] |
| `verify_and_ack` / normalize / deliver | qqbot package adapter | Host calls only | Package owns crypto/IO [VERIFIED: adapter.py] |
| Message ingress/session | `QQBotRuntimeIngress` | Host wires after ACK | Package owns session [VERIFIED: ingress_runtime.py] |
| INTERACTION feedback | `handle_feedback_callback` | Host branches after ACK | Package owns normalize [VERIFIED: feedback_ingress.py] |
| Flag→config→channels DI | Host `wiring.py` (Phase 69) | — | Webhook consumes `QQBotWiredRuntime` |
| Output boundary on egress | `DefaultRunRuntime.output_boundary` | adapter.deliver / sender | Host applies boundary before `ChannelDelivery` content [CITED: STACK.md] |
| ACK-first scheduling | Host injectable scheduler | — | Prove HOST-02 without real threads in unit tests |
| Smoke Protocol CLI | Deferred → Phase 71 | — | Out of scope |
| Live Urllib / HUMAN GATE | Deferred → Phase 72 | — | Out of scope |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `http.server` (`BaseHTTPRequestHandler`, optional `ThreadingHTTPServer`) | 3.11+ | Thin webhook HTTP host | Matches admin-web-ui / lawyer-web-chat; zero deps [CITED: STACK.md] |
| `json`, `asyncio`, `dataclasses`, `unittest` | stdlib | Handler + Fake tests | Empty-deps culture |
| `inkstatute-channels-qqbot` | in-repo | Protocol IO + ingress/feedback | Compose, do not fork |
| `platform-runtime` | in-repo | `RawInbound`, `DefaultRunRuntime`, `FakeBackendAdapter`, `DefaultAssistantOutputBoundary`, `SolutionBinding`, `ChannelDelivery` | Existing DI + fakes |
| `qqbot_service.wiring` | Phase 69 | `build_qqbot_wired_runtime` | Single composition root |

### Supporting

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `FakeMessageTransport` / `FakeTokenTransport` | Network-free live-ready path | Enabled-path unit tests |
| Package fixtures under `packages/channels/qqbot/fixtures/` | Signed envelopes / C2C / INTERACTION | Host composition tests (reuse DEMO_BOT_SECRET signing pattern from `test_adapter_two_tier_ack.py`) |
| `scripts/run_v2_gates.py` gate `qqbot-service` | CI discover | Extend PYTHONPATH only if new imports require feedback-service / contract paths |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure handler + `http.server` | FastAPI / Starlette | **Rejected** — breaks `dependencies=[]` [CITED: STACK.md] |
| Host-owned crypto | Reimplement Ed25519 in host | **Rejected** — fat-host pitfall; call `verify_and_ack` |
| Sync await ingress before HTTP return | ACK-first + scheduler | **Rejected for HOST-02** — QQ retries on slow ACK [CITED: PITFALLS Pitfall 6] |
| Put server inside `packages/channels/qqbot` | Service host | **Rejected** — package stays library-pure |
| Import `wecom_service` HTTP patterns by dependency | Copy structural pattern only | **Required** — ADAPTER-04 |

**Installation:** No new third-party packages.

## Package Legitimacy Audit

> Phase 70 installs **no** external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

## Architecture Patterns

### Call sequence (opinionated)

```text
POST /qqbot/callback
  → http_server: read Content-Length bytes ONCE from rfile
  → handle_qqbot_webhook_request(path, headers, body_bytes, wired, ...)
       → build RawInbound(
            payload_ref=...,
            metadata={
              request_body: body_bytes,          # exact bytes
              x_signature_ed25519, x_signature_timestamp,
              bot_secret: resolve_secret_ref(bot_secret_ref, env),
              payload: json.loads(body_bytes) if valid else {},
            })
       → ack = await wired.adapter.verify_and_ack(raw)
       → http_status, http_body = map_ack_to_http(ack)
            # op=13 → 200 + validation_challenge_response JSON
            # accepted → 200 + http_callback_ack_body ({"op":12})
            # refused → ack.status_code (503/401) + empty/minimal JSON
       → if ack.accepted and not challenge:
            post_ack_scheduler(lambda: run_post_ack(...))  # MUST NOT block return
       → return (http_status, http_body, headers)
  → http_server writes response immediately

post_ack (after return scheduled):
  → normalized = await adapter.normalize_inbound(raw)
  → if INTERACTION / FeedbackEvent: handle_feedback_callback(...)
  → if message AgentTurn: QQBotRuntimeIngress(runtime=wired.runtime, ...).handle_callback(payload, received_at=...)
  → on AgentResult / text reply: apply wired.runtime.output_boundary → ChannelDelivery → await adapter.deliver(...)
```

### ACK-first contract (HOST-02)

- Handler must **not** await `create_run`, ingress, or `deliver` before returning the ACK tuple.
- Unit tests inject a recording scheduler: assert response built first; assert scheduler invoked with a callable; optionally run the callable later to prove composition.
- op=13 challenge responses return immediately and **do not** schedule post-ACK work.
- Disabled / 401 paths return refuse status and do not schedule post-ACK work.

### Raw body contract (success criterion 3)

- `request_body` in `RawInbound.metadata` must be the **same bytes** read from the socket (or test-injected bytes), never `json.dumps(parsed)`.
- Header mapping is case-insensitive for `X-Signature-Ed25519` and `X-Signature-Timestamp`.
- `bot_secret` value resolved at process edge via `resolve_secret_ref(host_config.bot_secret_ref, env)` and placed only in `RawInbound.metadata` (never on config).

### Output boundary on egress

- When building `ChannelDelivery` from backend/agent text, call `wired.runtime.output_boundary` (`DefaultAssistantOutputBoundary`) and only deliver allowed visible content.
- Do not send Hermes meta/gateway/update/command notices as user-facing QQ replies.
- Prefer asserting boundary decision in a host unit test with a meta-like content fixture; do not reimplement sender policy.

### File layout (recommended)

| File | Role |
|------|------|
| `services/qqbot-service/src/qqbot_service/webhook.py` | Pure `handle_qqbot_webhook_request`, `map_ack_to_http`, `run_post_ack_composition` |
| `services/qqbot-service/src/qqbot_service/http_server.py` | `QQBotWebhookServer(BaseHTTPRequestHandler)` + optional `serve_qqbot_webhook` helper |
| `services/qqbot-service/tests/test_webhook_ack_first.py` | HOST-02: op=13 / op=12 / refuse + scheduler ordering |
| `services/qqbot-service/tests/test_webhook_composition.py` | HOST-01: Fake path message + feedback → deliver |
| `services/qqbot-service/tests/test_webhook_http_raw_body.py` | Raw-body once + signature via handler bytes |

## Don't Hand-Roll

| Problem | Existing Solution | Where |
|---------|-------------------|-------|
| Ed25519 verify / op=13 | `adapter.verify_and_ack` / `handle_validation_challenge` | `adapter.py`, `signature.py` |
| op=12 body | `ack.metadata["http_callback_ack_body"]` | adapter Tier-1 ACK |
| Message → session/run | `QQBotRuntimeIngress.handle_callback` | `ingress_runtime.py` |
| INTERACTION → FeedbackEvent | `handle_feedback_callback` | `feedback_ingress.py` |
| Egress send | `adapter.deliver` + Fake/Urllib transports | `adapter.py`, `sender.py` |
| Flag→config DI | `build_qqbot_wired_runtime` | `wiring.py` |
| Secret resolve | `resolve_secret_ref` | `secrets.py` |
| HTTP pure-handler pattern | `handle_admin_web_ui_request` | `admin_web_ui/server.py` |

## Common Pitfalls (phase-relevant)

1. **Fat host** — copying crypto/normalize into webhook.py → compose package APIs only.
2. **Re-serialize body** — `json.dumps` before verify → pass raw bytes.
3. **Slow ACK** — await agent before HTTP return → injectable scheduler + ACK-first tests.
4. **Bare adapter** — bypassing `build_qqbot_wired_runtime` → always use wired bundle.
5. **WeCom import** — AST gate must stay green on new modules.
6. **Urllib in unit tests** — Fake transports only; no network.
7. **Smoke/live scope creep** — leave Phase 71/72 alone.

## Validation Architecture

| Requirement | Test approach | Command shape |
|-------------|---------------|---------------|
| HOST-02 op=13 / op=12 / refuse | Unit: signed fixtures through pure handler; assert body + scheduler not run for challenge/refuse | `unittest … test_webhook_ack_first` |
| HOST-02 ACK before agent | Recording `post_ack_scheduler`; assert return precedes scheduled work execution | same |
| HOST-01 composition | Enabled wired runtime + FakeBackend + Fake transports; message and INTERACTION paths; deliver call recorded | `unittest … test_webhook_composition` |
| Raw body + HTTP wrapper | Handler/server builds RawInbound from injected bytes; demo-vector signature still verifies | `unittest … test_webhook_http_raw_body` |
| Regression | Full `services/qqbot-service/tests` discover + `qqbot-service` gate | existing gate |

## Open Questions

None blocking. Discretion choices locked below for planning.

## Discretion Decisions (planner-locked)

| ID | Decision |
|----|----------|
| W-01 | Pure `handle_qqbot_webhook_request` returns `(status: int, body: bytes \| str, headers: dict)`; tests never bind a port for HOST-01/02 core proofs |
| W-02 | Route: `POST /qqbot/callback` only (other paths → 404); GET → 405 |
| W-03 | ACK-first via injectable `post_ack_scheduler: Callable[[Callable[[], None]], None]`; default production scheduler may use `threading.Thread(target=..., daemon=True).start` inside http_server only |
| W-04 | Always compose through `build_qqbot_wired_runtime` / injected `QQBotWiredRuntime` — never construct bare `QQBotChannelAdapter` in webhook modules |
| W-05 | Post-ACK message path uses `QQBotRuntimeIngress` with `wired.runtime` + injectable `SolutionBinding` / tenant ids (test defaults OK) |
| W-06 | Post-ACK INTERACTION path uses `handle_feedback_callback`; optional `ensure_interaction_ack` only when prior metadata says `pending_host` and live_io_ready |
| W-07 | Egress: map AgentResult/text through `wired.runtime.output_boundary` before `adapter.deliver` |
| W-08 | No new deps; no smoke CLI changes; no Urllib in unit tests; no Protocol edits |

## Sources

- `.planning/research/STACK.md`, `SUMMARY.md`, `PITFALLS.md` (v1.9 host composition)
- `.planning/phases/69-*/69-RESEARCH.md`, `69-*-SUMMARY.md`, `wiring.py`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` (verify_and_ack Tier-1/2)
- `services/admin-web-ui/src/admin_web_ui/server.py` (pure handler pattern)
- ROADMAP Phase 70 success criteria; REQUIREMENTS HOST-01/HOST-02

*Research confidence: HIGH — all primitives exist; Phase 70 is composition + ACK-first HTTP edge only.*
