# Project Research Summary

**Project:** v1.8 QQBot Channel Production
**Domain:** QQ Bot platform channel production (real ingress/egress, feedback parity, session continuity, smoke-test toolkit) added to the existing InkStatute V2 multi-channel platform
**Researched:** 2026-07-07
**Confidence:** HIGH

## Executive Summary

v1.8 QQBot Channel Production promotes the existing fixture-only QQBot adapter (`packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`) to a complete production-grade channel loop aligned with the WeCom reference channel, while preserving every V2 invariant: the frozen 6-method `ChannelAdapter` Protocol, the frozen `FeedbackSource` enum, the `dependencies = []` import-time invariant, the `qqbot_channel_enabled` default-OFF feature flag, the output boundary that suppresses Hermes/gateway/meta notices, and all 24 V2 CI gates (1,547+ tests). The QQ Bot platform differs fundamentally from WeCom in three ways that drive the entire milestone: (1) Ed25519 asymmetric webhook signatures (not WeCom's SHA-1+AES symmetric scheme), (2) JSON gateway envelopes `{id, op, d, s, t}` with a two-phase callback URL validation handshake (op=13), and (3) platform-enforced passive-reply windows (C2C 60 min / 4 replies, group 5 min / 5 replies) with `msg_id`+`msg_seq` server-side dedupe.

The recommended approach is to implement QQ Bot protocol primitives directly inside the existing `packages/channels/qqbot` package — mirroring the WeCom service's internal decomposition (signature → normalization → sender → token → session runtime) but as a channel package, not a standalone service. New runtime dependencies (`cryptography` for Ed25519, `httpx` for async OpenAPI calls) are added only as optional extras with lazy imports inside method bodies, preserving the `dependencies = []` invariant. All channel-generic logic (output policy, idempotency, delivery guard, active-task routing) is reused unchanged from `channel-core`. A new `QQBotSessionRuntime` composes the existing `platform_runtime` primitives (`RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator`, `InMemoryInterruptStore`) with QQ-specific scene-aware identity rules, mirroring the `WeComSessionRuntime` pattern without importing from `wecom_service`.

Key risks center on the QQ-vs-WeCom protocol differences: copying WeCom's SHA-1 verifier for QQ (Ed25519) would make the endpoint spoofable; missing the op=13 validation handshake prevents webhook registration entirely; ignoring the passive-reply window causes silent delivery failures (`304027 MSG_EXPIRE`); reusing WeCom's `template_card` envelope for QQ feedback cards (which use markdown+keyboard) breaks the feedback loop; and mapping `user_openid` alone to `conversation_id` (without scene scoping) causes session collisions across C2C/group/channel. Credential leakage of the QQ `access_token` into logs or contract events is a HIGH-severity risk mitigated by secret-ref-only config, `_reject_unsafe_keys` extension, and evidence redaction in the smoke-test toolkit.

## Key Findings

### Recommended Stack

The stack adds exactly two new runtime dependencies as optional extras (`[project.optional-dependencies] runtime`), imported lazily inside method bodies so the package remains importable with `dependencies = []` in CI. This mirrors the existing `provider_model` adapter pattern (lazy `AsyncOpenAI` import) and the `ollama_runner.py` pattern (lazy `urllib.request` import). Both dependencies are already transitive dependencies of the `openai` SDK used in `provider_model`, so they are already present in dev environments. No WeCom SDK, no QQ Bot SDK (`botpy` is stale — last release March 2024 — and is a WebSocket framework, not a lightweight API client), no new database, queue, or service.

**Core technologies:**
- `cryptography` (pyca/cryptography) 49.0.0: Ed25519 signature verification for QQ Bot webhook callbacks + callback URL validation signing — Python stdlib has NO Ed25519 support; this is the one mandatory new dependency, already a transitive dep of `httpx`/`openai`.
- `httpx` 0.28.1: Async HTTP client for QQ Bot OpenAPI calls (AccessToken acquisition, message send, rich media upload, interaction ACK) — native `asyncio` support, connection pooling, timeout control; already a transitive dep of the `openai` SDK.
- Python stdlib `json` + `asyncio` + `hashlib` + `hmac` + `argparse`: QQ Bot payload parsing (JSON, not XML), async runtime, idempotency keys, constant-time comparison, smoke-test CLI — no new runtime library needed beyond the two optional extras.

**Reused internal libraries (no changes):**
- `channel_core.idempotency.channel_idempotency_key`: channel-generic idempotency — QQ Bot `msg_id`/`interaction_id` map to existing stable field aliases.
- `channel_core.output_policy.apply_output_policy`: assistant output boundary — blocks Hermes/gateway/system notices before QQ envelope build.
- `channel_core.delivery_guard.assess_delivery_completion`: delivery-completion guardrails for file delivery.
- `channel_core.active_task_router` + `channel_core.owned_notices`: active-task routing and InkStatute-owned service notices.

### Expected Features

The feature landscape is sourced from official QQ Open Platform docs (bot.q.qq.com API v2) cross-checked against five open-source SDK implementations (botpy, nonebot adapter-qq, AstrBot, LangBot, OpenClaw). The MVP is the complete QQ Bot production loop aligned with WeCom parity, with QQ-platform-required differences allowed.

**Must have (table stakes):**
- Ed25519 webhook signature verification + op=13 callback URL validation handshake — without it the endpoint cannot be registered with QQ.
- Event normalization for `C2C_MESSAGE_CREATE` + `GROUP_AT_MESSAGE_CREATE` → `AgentTurn`; `INTERACTION_CREATE` → `FeedbackEvent`.
- @-bot content stripping for group messages (QQ group mode is @-gated by platform).
- Two-tier ACK: webhook ACK (op=12, HTTP 200) for message events + interaction ACK (`PUT /interactions/{id}`) for button clicks.
- Access token management (appId + clientSecret → AccessToken, 7200s TTL, auto-refresh at 60s before expiry, single-flight under concurrency).
- Text egress (`msg_type=0`) with `msg_id`+`msg_seq` passive-reply dedupe and output boundary enforcement.
- Markdown + keyboard feedback card dispatch (`msg_type=2` + `keyboard` with callback buttons `up`/`down`/`needs_fix`/`route_wrong`).
- `INTERACTION_CREATE` normalization → `FeedbackEvent` (`source="card_button"`, frozen enum) + interaction ACK + feedback dedupe.
- Runtime session continuity via `QQBotSessionRuntime` (continuous conversation, interrupt resume, memory recall) with scene-aware conversation identity.
- One-click smoke-test toolkit (CLI + fixtures + runbook, env-var credentials, evidence collection, `--dry-run` mode).
- Feature flag default-off (`qqbot_channel_enabled=False`); frozen Protocol preserved; 24 V2 gates green.

**Should have (competitive):**
- Markdown reply delivery (`msg_type=2`) for structured legal answers — QQ natively supports markdown (WeCom does not).
- Interaction recall (`is_wakeup`) for over-window long-task completion — windowed (30-day periods, 1 per period).
- Rich media inbound (image/voice/video/file `attachments[]` → `AttachmentRef` with reference-only policy).
- Rich media egress (two-step upload `/v2/.../files` → `file_info` → `msg_type=7`) for DOCX/PDF legal document delivery.

**Defer (v2+):**
- WebSocket ingress mode (stateful, Resume/op6, no public IP) — defer until webhook mode is proven; adds heartbeat/identify/reconnect complexity.
- Guild/channel management APIs (roles, permissions, sub-channels, forums, audio stage) — separate product surface outside V2 messaging-loop scope.
- QQ-built-in voice ASR passthrough — cheap but only relevant once voice inbound is supported.
- Group role-aware routing (owner/admin/member privileges) — niche, capture in metadata now.
- Active push beyond `is_wakeup` (monthly quota-managed broadcasts) — quota-capped and user-opt-in-dependent.

### Architecture Approach

The target architecture integrates new QQBot production components (marked `[NEW]`) alongside reusable existing components (marked `[REUSE]`) within the existing multi-channel platform. The frozen 6-method `ChannelAdapter` Protocol (`packages/platform-runtime/src/platform_runtime/protocols.py:208-219`) is the only integration seam — no Protocol methods are added or modified. QQ-specific capabilities (markdown delivery, interaction ACK, Ed25519 verification, keyboard buttons) are expressed through existing method implementations using `ChannelDelivery.metadata`, `AckResponse.metadata`, and `ChannelCapabilitySet.metadata`. The QQBot adapter imports from `channel-core` (frozen, shared) and `platform-runtime` (Protocol-based injection) but never from `wecom_service` (enforced by `test_no_wecom_import.py`).

**Major components:**
1. **Ed25519 Verifier** (`signature.py`, NEW) — verify QQ webhook signatures (`X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp+raw_body`); sign validation challenge (op=13) with the derived private key. Bot Secret → repeat-to-32-byte seed → Ed25519 keypair.
2. **QQ Event Normalizer** (`normalization.py`, NEW) — parse QQ gateway envelope `{op, t, d}` → `AgentTurn` (C2C/Group@) or `FeedbackEvent` (INTERACTION_CREATE); strip @-bot prefix; build scene-aware composite openid `conversation_id`.
3. **QQ Egress Sender** (`sender.py`, NEW) — build QQ send envelopes (text `msg_type=0`, markdown+keyboard `msg_type=2`); call QQ OpenAPI with access token; handle `msg_id`+`msg_seq` passive-reply dedupe; retry on transient failure; enforce passive-reply window deadline.
4. **Token Manager** (`token_manager.py`, NEW) — acquire + cache + auto-refresh QQ access token (appId+clientSecret → token, 7200s TTL, 60s overlap, single-flight refresh via `asyncio.Lock`).
5. **QQBotSessionRuntime + QQBotIngressRuntime** (`session_runtime.py` + `ingress_runtime.py`, NEW) — orchestrate session resolution, interrupt resume, active-task routing, memory recall for QQ turns; compose `platform_runtime` primitives directly (not through `wecom_service`); QQ identity rules: `qqbot:{scene}:{scene_id}:{user_openid}`.
6. **QQBotChannelAdapter** (`adapter.py`, MODIFY) — promote from fixture-only to real IO: `verify_and_ack` → Ed25519 verifier + op=13 challenge + interaction ACK metadata; `normalize_inbound` → QQ normalizer; `deliver` → QQ sender + output policy; `health` → token validity. Fixture path preserved for CI when flag is off.
7. **Smoke-Test Toolkit** (`scripts/smoke_test.py` + `runbook/`, NEW) — CLI that validates signature verification, sends text + markdown+keyboard, simulates callback, collects sanitized evidence. `--dry-run` mode for CI; live run is human gate.

### Critical Pitfalls

1. **Treating QQ Bot callback signature verification like WeCom's SHA-1 scheme** — QQ uses Ed25519 asymmetric signatures over `timestamp + raw_body` (byte-concatenated), not SHA-1 sort+HMAC. Copying WeCom's verifier makes the endpoint spoofable. Implement Ed25519 per spec with official demo vectors; read raw body before JSON parse; do not import from `wecom_service`.
2. **Missing the QQ Bot callback URL validation handshake (op=13)** — QQ performs two-phase webhook setup; the platform sends `{op:13, d:{plain_token, event_ts}}` and expects `{plain_token, signature}` where signature = Ed25519 sign(`event_ts+plain_token`). Returning a generic ACK causes URL registration to fail silently — no events ever arrive. Detect `op==13` before normal event processing; use the signing (private) key.
3. **Assuming QQ Bot passive reply has no time window (unlike WeCom)** — QQ enforces C2C 60 min / 4 replies and group 5 min / 5 replies per `msg_id`. WeCom has no deadline. A long legal task that exceeds the group window returns `304027 MSG_EXPIRE` and delivery silently fails. Distinguish ACK deadline (3s) from passive-reply deadline; track `msg_id`+`msg_seq`; surface window expiry as a delivery failure with an interim InkStatute-owned service notice.
4. **Reusing WeCom `template_card` format for QQ Bot card/feedback delivery** — QQ has no `template_card` type; it uses `msg_type=2` markdown + `keyboard` object with button rows. Sending a WeCom-shaped payload returns 400 and breaks the feedback loop. Map `delivery_type=="card"` to keyboard payload; `INTERACTION_CREATE` callback maps to `FeedbackEvent(source="card_button")` (frozen enum, no new value).
5. **Breaking session continuity by assuming QQ conversation IDs work like WeCom thread IDs** — QQ identity is scene-specific (C2C: `user_openid`; group: `group_openid`+`member_openid`; channel: `channel_id`+`guild_id`). Mapping `user_openid` alone to `conversation_id` causes C2C/group session collisions, wrong interrupt resume, and cross-scene memory leakage. Derive scene-aware key: `qqbot:{scene}:{scene_id}:{user_openid}`; partition sessions by channel + scene.

## Implications for Roadmap

Based on research, suggested phase structure (phase numbering continues from v1.7, next = 58):

### Phase 1: Ed25519 Signature Verification + Validation Challenge
**Rationale:** Every other ingress feature depends on verifying QQ callbacks. The op=13 validation handshake is required to register the webhook URL at all. This is the foundation — without it, no QQ events arrive.
**Delivers:** `signature.py` (Ed25519 key derivation, verify, sign for op=13); `config.py` modification (add `bot_secret_ref`); tests with official QQ demo vectors.
**Addresses:** Ed25519 webhook signature verification; webhook validation challenge (op=13).
**Avoids:** Pitfall 1 (wrong signature verifier); Pitfall 2 (missing validation handshake).

### Phase 2: QQ Event Normalization (Inbound)
**Rationale:** Once callbacks can be verified, the next step is parsing QQ gateway envelopes into platform contract events. Pure data transformation with no network IO — testable with fixtures.
**Delivers:** `normalization.py` (parse `{op, t, d}` → `AgentTurn`/`FeedbackEvent`); `qq_types.py` (event type constants); fixture files; tests for @-bot stripping, identity mapping, feedback action aliases.
**Uses:** `channel_core.idempotency.channel_idempotency_key` (existing).
**Implements:** QQ Event Normalizer component.
**Avoids:** Pitfall 4 (INTERACTION_CREATE → FeedbackEvent mapping, not template_card).

### Phase 3: Access Token Manager
**Rationale:** All egress (text send, markdown+keyboard send, interaction ACK) requires a valid access token. Building it before egress allows egress tests to mock the token. Can be built in parallel with Phase 2.
**Delivers:** `token_manager.py` (acquire, cache with expiry, auto-refresh at 60s before expiry, single-flight refresh); tests for token lifecycle, concurrent refresh, error handling.
**Uses:** `QQBotChannelConfig` (`app_id_ref`, `app_secret_ref` — existing).
**Avoids:** Pitfall 6 (token leakage — resolve refs only in transport client, never in Protocol metadata).

### Phase 4: QQ Egress Sender (Text + Markdown + Keyboard)
**Rationale:** With token management in place, the sender can make real OpenAPI calls. Text egress is simplest; markdown+keyboard is the feedback card carrier. Both needed before the feedback loop can dispatch cards.
**Delivers:** `sender.py` (text `msg_type=0`, markdown+keyboard `msg_type=2`, `msg_id`+`msg_seq` dedupe, retry, window-expiry failure); `adapter.py` `deliver()` modification; tests for envelope structure, msg_seq increment, output policy, retry, window expiry.
**Uses:** `httpx` (optional extra); `channel_core.output_policy` (existing); `channel_core.delivery_guard` (existing).
**Avoids:** Pitfall 3 (passive-reply window deadline); Pitfall 4 (keyboard not template_card).

### Phase 5: QQBotSessionRuntime + QQBotIngressRuntime
**Rationale:** Session continuity composes runtime primitives around normalized turns. Depends on normalization (Phase 2) and adapter (Phases 1+4). This is the orchestration layer tying ingress to the platform runtime.
**Delivers:** `session_runtime.py` (QQBotSessionRuntime mirroring WeCom pattern); `ingress_runtime.py` (callback → turn → session runtime); tests for session continuity, interrupt resume, memory recall, idempotency, no `wecom_service` import.
**Uses:** `platform_runtime` primitives (`RunRuntime`, `SessionResolutionPolicy`, `MemoryOrchestrator`, `InMemoryInterruptStore` — all existing); `channel_core.active_task_router` (existing).
**Implements:** QQBotSessionRuntime + QQBotIngressRuntime components.
**Avoids:** Pitfall 8 (scene-aware conversation key derivation, not `user_openid` alone).

### Phase 6: Adapter Integration — Promote to Real IO
**Rationale:** Wire all new modules into `QQBotChannelAdapter`. The adapter becomes the single entry point. Fixture path preserved for CI (when `qqbot_channel_enabled=False`).
**Delivers:** `adapter.py` full modification (all 6 methods gain real IO behind feature flag); `capabilities()` metadata update; tests for full real-IO loop (mocked OpenAPI), fixture loop still passes, feature flag gating, contract freeze preservation.
**Uses:** All Phase 1-5 modules.
**Avoids:** Pitfall 5 (frozen Protocol — no new methods, QQ-specific behavior via metadata).

### Phase 7: Feedback Loop Parity (Interaction ACK + FeedbackEvent Pipeline)
**Rationale:** The feedback loop requires egress (keyboard card dispatch — Phase 4) and ingress (INTERACTION_CREATE normalization — Phase 2) plus interaction ACK (egress — Phase 4). This phase wires the complete feedback loop end-to-end and validates parity with WeCom's feedback-service pipeline.
**Delivers:** End-to-end feedback wiring (INTERACTION_CREATE → normalize → FeedbackEvent → feedback-service dedupe/classify/queue); interaction ACK (host reads metadata → `PUT /interactions/{id}`); tests for feedback loop, dedupe, `FeedbackSource.CARD_BUTTON` parity, `SkillCandidate` human-review-only.
**Uses:** Phases 2, 4, 6; `feedback-service` (channel-neutral, existing).
**Avoids:** Pitfall 4 (keyboard not template_card); Pitfall 5 (no new FeedbackSource enum value).

### Phase 8: One-Click Smoke-Test Toolkit
**Rationale:** The toolkit exercises the entire real loop against the live QQ sandbox. It depends on all production features being implemented. Live run remains a human gate, but the toolkit ships in this milestone.
**Delivers:** `scripts/smoke_test.py` (CLI: validate signature, send text, send markdown+keyboard, simulate callback, collect evidence); `runbook/SMOKE_TEST_RUNBOOK.md`; `--dry-run` mode for CI; tests for dry-run, credential injection, evidence format, no secrets in output.
**Uses:** All Phase 1-7 modules; `argparse` + `os.environ` (stdlib).
**Avoids:** Pitfall 6 (credential redaction in evidence); Pitfall 9 (reproducibility — input-driven, redacted, idempotent, dry-run).

### Phase Ordering Rationale

- **Phase 1 first** because every ingress feature depends on signature verification + validation handshake; without it the webhook URL cannot be registered.
- **Phases 1+3 can run in parallel** (no interdependency) — signature verification and token management are independent foundations.
- **Phase 2 after Phase 1** because normalization is pure data transformation but real callback handling requires verification; can be built in parallel with Phase 3.
- **Phase 4 after Phase 3** because all egress requires a valid access token; the sender depends on the token manager.
- **Phase 5 after Phase 2** because session runtime composes platform primitives around normalized turns; depends on normalization producing `AgentTurn`/`FeedbackEvent`.
- **Phase 6 after Phases 1-5** because adapter integration wires all new modules into the single entry point.
- **Phase 7 after Phases 2+4+6** because the feedback loop requires both ingress (normalization) and egress (keyboard dispatch + interaction ACK).
- **Phase 8 last** because the toolkit exercises the entire real loop; depends on all production features.
- This grouping avoids pitfalls by addressing each pitfall in the phase where the relevant code is first written (signature in Phase 1, window deadline in Phase 4, scene identity in Phase 5, Protocol freeze in Phase 6, feedback mapping in Phase 7, credential redaction in Phase 8).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Ed25519 Signature):** Official QQ demo vectors must be sourced and verified; the seed derivation (repeat BotSecret to 32 bytes) is non-standard and needs careful validation against the Go reference implementation.
- **Phase 4 (Egress Sender):** QQ error code mapping (retryable vs terminal) needs API error docs research; `msg_seq` increment semantics for multi-part replies need validation against platform behavior.
- **Phase 5 (Session Runtime):** Scene-aware conversation key derivation needs validation against real QQ event payloads (C2C vs group vs channel) to confirm no cross-scene collision.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Normalization):** Well-documented QQ event structures; pure data transformation with fixture-based tests.
- **Phase 3 (Token Manager):** Standard OAuth-style token cache + refresh pattern; well-documented in QQ API docs.
- **Phase 6 (Adapter Integration):** Mechanical wiring of existing modules into the frozen Protocol; follows the existing fixture adapter pattern.
- **Phase 7 (Feedback Loop):** Mirrors WeCom feedback pipeline with QQ-specific normalization; feedback-service is channel-neutral and unchanged.
- **Phase 8 (Smoke-Test Toolkit):** Standard CLI script with env-var credentials; follows existing `argparse` + `httpx` patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Two dependencies (`cryptography`, `httpx`) are already transitive deps of `openai` SDK; both are production-stable, well-documented. Official QQ docs specify Ed25519; `cryptography` provides exact API needed. No WeCom/QQ SDK needed — direct protocol implementation mirrors WeCom reference pattern. |
| Features | HIGH | Sourced from official QQ Open Platform docs (bot.q.qq.com API v2), cross-checked against 5 open-source SDK implementations (botpy, nonebot adapter-qq, AstrBot, LangBot, OpenClaw). MVP definition validated against WeCom parity baseline. |
| Architecture | HIGH | Sourced from codebase inspection of all referenced files (adapter.py, config.py, channel-core, wecom-service, platform-runtime, platform-contract, feedback-service, conversation-read-view). Frozen Protocol, frozen enums, feature flag, and no-wecom-import constraint all verified against existing tests. |
| Pitfalls | HIGH | 10 critical pitfalls sourced from QQ platform docs (Ed25519, op=13, passive windows, keyboard vs template_card) and codebase-specific risks (frozen Protocol, no-wecom-import, credential leakage, scene identity). Each pitfall has concrete warning signs and recovery strategies. |

**Overall confidence:** HIGH

### Gaps to Address

- **QQ Bot official demo vectors for Ed25519:** The official docs provide a demo vector (`secret: naOC0ocQE3shWLAfffVLB1rhYPG7`, `body: {"op":0,"d":{}}`, `timestamp: 1725442341`); this must be validated against the `cryptography` library's Ed25519 implementation during Phase 1 planning. If the seed derivation (repeat-to-32-bytes) produces a different keypair than expected, a Go-reference cross-check is needed.
- **QQ error code → retryable/terminal mapping:** The QQ OpenAPI error docs list codes (`304026` MSG_ID error, `304027` MSG_EXPIRE, `20028` ChannelHitWriteRateLimit, `22009` msg limit exceed, `429` rate limit, `504000-504999` frequency errors) but the retry semantics for each need validation during Phase 4 planning — some may be retryable with backoff, others terminal.
- **WebSocket Resume (op=6) persistence:** If WebSocket mode is ever implemented (deferred to v2+), the `s` sequence persistence strategy (durable store, not in-memory) needs design. Not a v1.8 gap since webhook mode is primary.
- **Live QQ sandbox validation:** The smoke-test toolkit's live run is a human gate; the dry-run mode is CI-able but cannot validate real platform behavior (token acquisition, message delivery, interaction ACK). The first live run during Phase 8 will surface any platform-specific quirks not captured in docs.

## Sources

### Primary (HIGH confidence)
- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html` — Ed25519 signature verification flow, seed derivation, header fields, demo vectors.
- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html` — Webhook vs WebSocket modes, OpCode table (0/1/2/6/7/9/10/11/12/13), payload structure, callback URL validation flow.
- `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html` — AccessToken acquisition, auth header format, 7200s TTL, API base URL.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html` — Send message endpoints, `msg_type` values, rate limits, passive reply windows, `msg_id`+`msg_seq` dedupe.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/trans/msg-btn.html` — Keyboard button configuration, `INTERACTION_CREATE` event, interaction ACK.
- `bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/rich-media.html` — Rich media upload flow, `file_type` values.
- `bot.q.qq.com/wiki/develop/api-v2/openapi/error/error.html` — Error codes (304026, 304027, 20028, 22009, 429, 504000-504999).
- Existing codebase inspection: `packages/channels/qqbot/`, `packages/channel-core/`, `services/wecom-service/`, `packages/platform-runtime/`, `packages/platform-contract/`, `services/feedback-service/`, `services/conversation-read-view/` — all referenced files read and verified.

### Secondary (MEDIUM confidence)
- Open-source SDK cross-checks: `tencent-connect/botpy` (official SDK, stale), nonebot adapter-qq, AstrBot (`qo_webhook_server.py` — Ed25519 seed/sign), LangBot (callback validation structure), OpenClaw qqbot (webhook vs websocket, media skill, two-step send) — community implementations confirming official docs.
- `pypi.org/project/cryptography/` (v49.0.0, Jun 2026), `pypi.org/project/httpx/` (v0.28.1) — version compatibility and API stability.
- `cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/` — Ed25519 API reference.

### Tertiary (LOW confidence)
- QQ Bot sandbox environment behavior — sandbox mode is documented to bypass rate limits, but exact behavioral differences from production need live validation during Phase 8.
- QQ client markdown rendering differences (mobile vs desktop) — community-reported but not officially documented; needs testing during trial.

---
*Research completed: 2026-07-07*
*Ready for roadmap: yes*
