# Feature Research

**Domain:** QQ Bot platform channel production (V2 production-grade channel loop aligned with WeCom, with QQ-platform-required differences)
**Researched:** 2026-07-07
**Confidence:** HIGH (sourced from official QQ Open Platform docs at bot.q.qq.com API v2, cross-checked against multiple open-source SDK implementations: botpy, nonebot adapter-qq, AstrBot, LangBot, OpenClaw)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete. These are the QQ Bot production equivalents of what WeCom already ships.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real ingress — Ed25519 webhook signature verification | QQ platform requires every callback to be verified via `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp+body` using a Bot-Secret-derived Ed25519 public key. Without it the endpoint is spoofable. | MEDIUM | **QQ vs WeCom:** WeCom uses `SHA1(sort(token,timestamp,nonce,encrypted))` + AES-encrypted XML payload (`services/wecom-service/.../protocol.py:verify_callback_signature`). QQ uses Ed25519 verify (no AES, body is plaintext JSON). New verifier module required; cannot reuse WeCom's `verify_callback_signature`. Bot Secret is repeated to a 32-byte seed to derive the keypair. |
| Real ingress — webhook validation challenge (op=13) | QQ platform probes the callback URL at setup with `{op:13, d:{plain_token, event_ts}}`; server must respond `{plain_token, signature}` where signature = Ed25519 **sign**(`event_ts+plain_token`) with the derived private key. | LOW | **QQ vs WeCom:** WeCom URL verification returns decrypted `echostr`. QQ returns a signed JSON challenge. Must be handled in `verify_and_ack` path before normal event dispatch. Distinct from per-event signature verification (verify vs sign). |
| Real ingress — event payload normalization (C2C / Group@ / Group full / Channel@ / DM) | QQ pushes `C2C_MESSAGE_CREATE`, `GROUP_AT_MESSAGE_CREATE`, `GROUP_MESSAGE_CREATE`, `AT_MESSAGE_CREATE`, `DIRECT_MESSAGE_CREATE` as Dispatch (op=0) with envelope `{id, op, s, t, d}`. Users expect the bot to read their messages. | MEDIUM | **QQ vs WeCom:** QQ payload is a JSON gateway envelope (`{id,op,s,t,d}`), not WeCom's flat XML/JSON callback. `d` carries event-specific fields: `id` (msg id), `author.user_openid`/`member_openid`, `content`, `timestamp` (RFC3339), `group_openid`, `attachments[]`. Normalizer must map `t` (event type) + `d` to `AgentTurn`. Reuse `channel_core.idempotency.channel_idempotency_key` with `channel_prefix="qqbot"` and stable field `message_id` ← `d.id`. |
| Real ingress — @-bot trigger handling | In QQ groups the bot ONLY receives `GROUP_AT_MESSAGE_CREATE` when explicitly @-mentioned; `content` includes the @mention text. In C2C no @ is needed. Users expect @ to be the trigger. | LOW | **QQ vs WeCom:** WeCom receives all messages in a configured app/external chat without an @ requirement. QQ group mode is @-gated by the platform. Normalizer should strip the @-bot prefix from `content` before building `AgentTurn.content` (mirrors community `removeAt` convention). C2C path needs no stripping. |
| Real ingress — ACK (webhook op=12 + interaction ACK) | QQ expects an HTTP Callback ACK (op=12, plain 200/empty body) for every webhook event; for `INTERACTION_CREATE` (button click) an additional `PUT /interactions/{interaction_id}` with `{code}` is REQUIRED or the QQ client stays in loading state until timeout. | MEDIUM | **QQ vs WeCom:** WeCom ACK = return literal `"success"` string (`protocol.py:ack_response`). QQ webhook ACK = HTTP 200 empty; QQ interaction ACK = a separate OpenAPI PUT call. The `verify_and_ack` ChannelAdapter method must return an `AckResponse` whose metadata distinguishes `event_ack` vs `interaction_ack_required`. The interaction PUT needs access_token → depends on egress auth. |
| Real egress — access token management | All QQ OpenAPI calls require `Authorization: QQBot {ACCESS_TOKEN}`; token obtained from `https://bots.qq.com/app/getAppAccessToken` with `{appId, clientSecret}`, valid 7200s, must self-refresh near expiry (60s overlap window). | MEDIUM | **QQ vs WeCom:** WeCom uses its own access_token + corpid/secret. QQ uses appId/clientSecret → access_token. Token-based auth is deprecated by QQ in favor of Access Token. Needs a token cache + refresh helper in the QQBot channel (secret refs only in config, never raw secrets — `QQBotChannelConfig` already carries `app_id_ref`/`app_secret_ref`/`token_secret_ref`). |
| Real egress — text message delivery (C2C + Group) | `POST /v2/users/{openid}/messages` (C2C) and `POST /v2/groups/{group_openid}/messages` (Group) with `msg_type=0`, `content`. Users expect replies to arrive. | MEDIUM | **QQ vs WeCom:** WeCom send envelope uses `msgtype:"text"` + `text.content` (`sender.py:build_text_send_envelope`). QQ uses `msg_type:0` (int) + `content` (string). Group send requires `group_openid`; C2C requires `user_openid`. Must pass `msg_id` (from inbound event `d.id`) for passive reply. Output boundary (`channel_core.output_policy.apply_output_policy`) reused as-is before envelope build. |
| Real egress — passive reply window + msg_seq idempotency | QQ passive replies are time-boxed (C2C: 60 min / 4 replies per msg_id; Group: 5 min / 5 replies per msg_id). Same `msg_id + msg_seq` repeated send FAILS server-side — QQ's built-in dedupe. | LOW | **QQ vs WeCom:** WeCom idempotency is app-side (`channel_core.idempotency` + `wecom_service.idempotency`). QQ has platform-side `msg_id+msg_seq` dedupe; the adapter should still keep app-side idempotency keys for contract logs but MUST set `msg_seq` (default 1, increment for multi-part replies) to avoid QQ server rejections. Window expiry should surface as a delivery failure reason, not a silent drop. |
| Real egress — output boundary enforcement (no backend notice leak) | Ordinary QQ users must see only InkStatute lawyer-assistant output, not Hermes gateway/update/command/meta notices. V2 safety rule. | LOW | Reuse `channel_core.output_policy.apply_output_policy` unchanged (already channel-generic). Block/rewrite decisions apply identically to QQ text content. No new policy code; only wiring into the QQ envelope builder. |
| Real egress — retry on transient failure | QQ OpenAPI can return rate-limit / transient errors; delivery must retry with backoff and remain idempotent. | MEDIUM | Reuse `channel_core.delivery_guard.assess_delivery_completion` for file-delivery contract. Retry logic mirrors WeCom `delivery_guard` pattern; QQ-specific error codes (rate limit, msg_id expired, msg_seq duplicate) must map to retryable vs terminal. |
| Feedback loop — keyboard button dispatch (callback buttons) | QQ interactive cards are `keyboard` buttons attached to a markdown message (`msg_type=2` + `keyboard.content.rows[].buttons[]`). Callback button = `action.type=1` with `action.data` carrying the feedback action. | HIGH | **QQ vs WeCom:** WeCom uses `template_card` with `card_id` (`sender.py:build_template_card_envelope`). QQ uses markdown + keyboard with inline button definitions (no pre-registered card_id needed for C2C/group; custom buttons open to all bots as of 2026-04-23). Button `action.data` encodes `up`/`down`/`needs_fix`/`route_wrong`. Up to 5 rows × 5 buttons. New envelope builder required. |
| Feedback loop — INTERACTION_CREATE normalization → FeedbackEvent | When a user clicks a callback button, QQ pushes `INTERACTION_CREATE` (intent 1<<26, `type=11`). Fields: `id` (interaction_id), `scene` (c2c/group/guild), `chat_type`, `user_openid`/`group_openid`/`group_member_openid`, `data.resolved.button_data`, `data.resolved.button_id`, `data.resolved.message_id`. | MEDIUM | **QQ vs WeCom:** WeCom feedback = `button_callback` event with `EventKey` (`normalization.py:normalize_wecom_feedback_callback`). QQ feedback = `INTERACTION_CREATE` with `data.resolved.button_data`. Map `button_data` → `action` (reuse `FEEDBACK_ACTIONS` aliases `up`/`down`/`needs_fix`/`route_wrong`). `feedback_target` ← `data.resolved.message_id` or `button_id`. `source` stays `"card_button"` (no new enum value — frozen contract). Must then `PUT /interactions/{id}` to ACK. |
| Feedback loop — dedupe | QQ may duplicate-push events; `INTERACTION_CREATE` and message events can repeat. FeedbackEvent dedupe must prevent double-counting. | LOW | Reuse `channel_core.idempotency.channel_idempotency_key` with `channel_prefix="qqbot"` and stable field `callback_id` ← `interaction_id` (`d.id`). Existing `FeedbackEvent` dedupe in feedback-service reused unchanged. |
| Runtime session continuity — conversation identity | QQ has no platform-side session/thread concept. Conversation identity must be derived: C2C → `user_openid`; Group → `group_openid + member_openid`. Continuous conversation, interrupt resume, memory recall must work on top of these. | MEDIUM | **QQ vs WeCom:** WeCom has `chat_id`/`thread_id` and a 48h service window. QQ is stateless (webhook) with passive-reply windows (5–60 min). `SessionScope.conversation_id` ← composite of openids. Reuse `platform_runtime.SessionResolutionPolicy` + `WeComSessionRuntime` pattern; build a `QQBotSessionRuntime` mirroring `wecom_service.session_runtime` but with QQ identity rules. Long tasks exceeding the passive window must switch to active push / `is_wakeup` recall. |
| One-click smoke-test toolkit | Operators need a CLI script + fixtures + runbook to run a live-platform smoke test (credential injection via env vars, evidence collection). Live run remains a human gate but the toolkit ships in this milestone. | MEDIUM | New deliverable (no WeCom equivalent shipped as a one-click toolkit). CLI invokes the real adapter against QQ sandbox with env-injected appId/clientSecret/botSecret, exercises ingress validation, send text, send markdown+keyboard, click callback, and collects evidence into a sanitized JSON artifact. Must never print secrets. |
| Feature flag default-off + frozen Protocol preservation | `qqbot_channel_enabled` defaults to `False`; the 6-method ChannelAdapter Protocol must not be modified; all 24 V2 gates stay green. | LOW | Already enforced by existing tests (`test_feature_flag.py`, `test_no_wecom_import.py`, `test_contract_freeze_not_violated.py`). Production upgrade must keep these green and add real-IO paths behind the flag. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Webhook + WebSocket dual ingress mode | QQ supports both webhook (stateless, serverless-friendly, public IP required) and WebSocket (stateful, no public IP, supports Resume/op6). Supporting both maximizes deployment flexibility. | HIGH | **QQ vs WeCom:** WeCom is callback-only. QQ WebSocket mode adds heartbeat/identify/resume complexity but removes the public-HTTPS requirement. v1.8 should pick ONE mode as primary (webhook aligns closest with WeCom's callback model and the existing `verify_and_ack` shape); WebSocket can follow. Recommend webhook-first. |
| Markdown reply delivery (`msg_type=2`) | QQ natively supports markdown messages (custom content, no template needed for C2C/group). Legal answers with structure (headings, lists, links) render richer than plain text. | MEDIUM | **QQ vs WeCom:** WeCom has no native markdown; QQ does. Differentiator for readable legal output. Must still pass through `apply_output_policy` (markdown can contain URLs — QQ requires URL allowlisting in console). Channel capability `supports_markdown` should be added to capability metadata (not to the frozen Protocol). |
| Interaction recall (`is_wakeup`) for long-task follow-up | QQ allows a recall message within 30-day windows (当天/1-3天/3-7天/7-30天, 1 per period) after a user conversation. Enables "your document is ready" follow-up beyond the passive reply window. | MEDIUM | **QQ vs WeCom:** WeCom has a 48h service window. QQ's recall is windowed and stricter. Differentiator for long-running legal document tasks that exceed the 5–60 min passive window. Requires storing the last `msg_id`/`event_id` per user to send `is_wakeup=true`. |
| Rich media inbound (image/voice/video/file attachments) | QQ inbound `attachments[]` carry `content_type`, `filename`, `url`, `voice_wav_url`, `asr_refer_text` (QQ-built-in ASR). Users can send screenshots of contracts; bot can receive them. | MEDIUM | **QQ vs WeCom:** WeCom attachments use `MediaId` (media reference only). QQ attachments give direct `url` (time-limited) + built-in voice ASR text. Normalizer maps to `AttachmentRef` with `uri=qqbot-media://...` and reference-only policy (never store bytes). `asr_refer_text` can populate `AttachmentRef.metadata` for voice. |
| Rich media egress (image/file/video/voice) | Two-step: upload via `/v2/users/{openid}/files` or `/v2/groups/{group_openid}/files` (`file_type` 1/2/3/4, `url` or base64 `file_data`) → get `file_info` → send `msg_type=7` with `media=file_info`. Enables DOCX/PDF delivery for legal tasks. | HIGH | **QQ vs WeCom:** WeCom uses `media_id` upload + `msgtype:"file"` (`sender.py:build_file_send_envelope`). QQ uses `file_info` with TTL (expires; ttl=0 means permanent). Higher complexity due to two-step + TTL management. Strongly aligns with `delivery_guard.assess_delivery_completion` (file-delivery contract). |
| QQ-built-in voice ASR passthrough | QQ attachments include `asr_refer_text` for voice messages — the platform already transcribes. Avoids running a separate STT provider. | LOW | **QQ vs WeCom:** WeCom voice is `MediaId` only, no ASR. QQ gives transcription for free. Low complexity to pass through into `AgentTurn.content` when `message_type=="voice"`. |
| Group role-aware routing | QQ group events include `author.member_role` (owner/admin/member). Could route/privilege differently for group admins. | LOW | **QQ vs WeCom:** WeCom has no equivalent in the callback. Niche but cheap to capture in `industry_context`/metadata. Not required for v1.8 launch. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full guild/channel (频道) module support | QQ has a rich guild/channel API (sub-channels, roles, permissions, forums, audio). "Complete QQ coverage" sounds thorough. | The V2 milestone scope is the QQ Bot **messaging** loop (C2C + group) aligned with WeCom parity. Guild/channel modules are a separate product surface with different identity (guild_id/channel_id), permission, and audit models. Building them explodes scope and risks the frozen-Protocol constraint. | Implement only `AT_MESSAGE_CREATE`/`DIRECT_MESSAGE_CREATE` normalization (already in table stakes) and defer guild management, roles, forums, and audio-stage APIs to a later milestone. Capture guild events as normalized `AgentTurn` only. |
| Auto-active-push for task completion | "When a long task finishes, just push the answer to the user/group." | QQ active push is quota-capped (4/month per user/group) and was disabled Apr 2025–Jun 2026; group active push requires the group owner to opt in. Blind auto-push burns the monthly quota and can fail silently if the user disabled active messages (`C2C_MSG_REJECT`). | Use passive reply within the window first; for over-window completion use `is_wakeup` interaction recall (windowed, 1/period) and record a `delivery_guard` failure otherwise. Never auto-active-push without an explicit user-initiated prior event. |
| Reusing WeCom's AES/signature code for QQ | "Both are Tencent callback verification — share the code." | QQ uses Ed25519 (no AES, no encrypted payload); WeCom uses SHA1+AES-encrypted XML. The primitives, key derivation, and payload shapes are incompatible. Forcing reuse corrupts both paths and violates the no-wecom-import rule (`test_no_wecom_import.py`). | Keep QQ verification in `packages/channels/qqbot` (or channel-core as a generic Ed25519 helper). Reuse only channel-generic idempotency/output_policy/delivery_guard from `channel-core`. |
| Storing QQ attachment URLs / media bytes in contract logs | "Keep the attachment url for replay." | QQ attachment `url` is time-limited and may carry user PII (contract screenshots, voice). V2 privacy rule: logs prefer `raw_payload_ref`, no raw legal text. Storing URLs leaks content after expiry and violates privacy baselines. | Store only `attachment_id` (hash of url), `kind`, `content_type`, and a `qqbot-media://` reference URI. Never store the raw URL or bytes. Mirror WeCom's `source_status: "media_reference_only"`. |
| Modifying the frozen ChannelAdapter Protocol to add QQ-specific methods | "Add `send_markdown` / `ack_interaction` as new Protocol methods." | The 6-method ChannelAdapter Protocol is frozen (`test_contract_freeze_not_violated.py`). Adding methods breaks every channel and the contract freeze. | Encode QQ-specific behavior (markdown, interaction ACK) inside `deliver()` and `verify_and_ack()` implementations using `ChannelDelivery.metadata` and `AckResponse.metadata`. Add capability flags in `ChannelCapabilitySet.metadata`, not new Protocol methods. |
| WebSocket Resume-based session continuity | "Use QQ WebSocket op6 Resume as the session continuity mechanism." | QQ WebSocket Resume is connection-level (replay missed events after reconnect), NOT conversation session continuity. Conflating the two produces broken interrupt/resume semantics and couples session state to transport. | Use `platform_runtime` session/memory layer (RunRuntime, SessionResolutionPolicy, MemoryOrchestrator) for conversation continuity — same as WeCom. Treat WebSocket Resume purely as a transport reliability concern. |
| Auto-synthesizing skills from QQ feedback | "QQ users click 'route_wrong' → auto-create the skill." | V2 safety rule: high-risk legal feedback remains human-reviewed; V2 records `skill_candidate` only, no auto-modify of legal conclusions. | Keep `SkillCandidate(detected=True, requires_human_review=True, no_auto_modify=True)` exactly as WeCom (`normalization.py:normalize_wecom_feedback_callback`). No auto-synthesis. |

## Feature Dependencies

```
[Ed25519 webhook signature verification]
    └──requires──> [QQBotChannelConfig: bot_secret_ref / app_secret_ref]
    └──requires──> [Ed25519 verify helper (new, channel-local or channel-core)]

[Webhook validation challenge (op=13)]
    └──requires──> [Ed25519 sign helper (same key derivation as verify)]
    └──requires──> [Ed25519 webhook signature verification] (shared key derivation)

[Access token management]
    └──requires──> [QQBotChannelConfig: app_id_ref / app_secret_ref]
    └──requires──> [token cache + refresh (new, channel-local)]

[Text/markdown/card egress]
    └──requires──> [Access token management]
    └──requires──> [channel_core.output_policy.apply_output_policy] (exists)
    └──requires──> [channel_core.idempotency.channel_idempotency_key] (exists)
    └──requires──> [msg_id + msg_seq passive-reply dedupe]

[Rich media egress (image/file/video/voice)]
    └──requires──> [Access token management]
    └──requires──> [Two-step upload (/v2/.../files) → file_info → msg_type=7]
    └──requires──> [channel_core.delivery_guard.assess_delivery_completion] (exists)

[Keyboard button dispatch (feedback card)]
    └──requires──> [Markdown egress (msg_type=2 + keyboard)] (markdown is the carrier)
    └──requires──> [Access token management]

[INTERACTION_CREATE normalization → FeedbackEvent]
    └──requires──> [Ed25519 webhook signature verification] (to receive the event)
    └──requires──> [Interaction ACK: PUT /interactions/{id}] (QQ-specific)
    └──enhances──> [feedback-service dedupe] (exists, channel-neutral)
    └──requires──> [channel_core.idempotency.channel_idempotency_key] (exists)

[Interaction ACK (PUT /interactions/{id})]
    └──requires──> [Access token management]

[Runtime session continuity]
    └──requires──> [platform_runtime.RunRuntime / SessionResolutionPolicy / MemoryOrchestrator] (exists)
    └──requires──> [QQBotSessionRuntime mirroring wecom_service.session_runtime] (new, channel-local)
    └──requires──> [Conversation identity: user_openid (C2C) / group_openid+member_openid (group)]

[One-click smoke-test toolkit]
    └──requires──> [All real ingress + egress + feedback features above]
    └──requires──> [Env-var credential injection (no secrets in repo)]

[Output boundary enforcement]
    └──enhances──> [All egress paths] (reuse channel_core.output_policy, exists)

[Feature flag default-off + frozen Protocol]
    └──conflicts──> [Any feature that adds ChannelAdapter Protocol methods] (anti-feature)
```

### Dependency Notes

- **Ed25519 verification requires Bot Secret:** The same Bot Secret derivation (repeat-to-32-byte seed → Ed25519 keypair) underpins both signature verify (public key) and the validation challenge sign (private key). Implement them together in one helper module to avoid key-derivation drift.
- **All egress requires Access Token:** Text, markdown, keyboard, rich media, and the interaction ACK all call QQ OpenAPI under `Authorization: QQBot {ACCESS_TOKEN}`. The token manager is the single shared dependency for the entire egress + interaction-ACK surface.
- **Keyboard buttons require markdown carrier:** QQ keyboard messages must be attached to a `msg_type=2` markdown message (markdown `content` is required; keyboard-only is rejected). Feedback card dispatch therefore depends on the markdown egress path, not the text path.
- **INTERACTION_CREATE requires interaction ACK:** Unlike message events (HTTP 200 ACK suffices), button-click events require a separate `PUT /interactions/{interaction_id}` or the user's QQ client hangs in loading. This ACK depends on the access token (egress auth), creating a feedback→egress dependency unique to QQ.
- **Session continuity reuses platform_runtime:** The `WeComSessionRuntime` pattern (`services/wecom-service/.../session_runtime.py`) is the template. A `QQBotSessionRuntime` should mirror it with QQ identity rules; it must NOT import from `wecom_service` (enforced by `test_no_wecom_import.py`).
- **Output boundary enhances all egress:** `channel_core.output_policy.apply_output_policy` is channel-generic and already used by the fixture adapter (`adapter.py:deliver`). No new policy code; only wiring.
- **Frozen Protocol conflicts with new methods:** Any QQ-specific capability (markdown, interaction ACK, rich media) must be expressed through existing `deliver()`/`verify_and_ack()` metadata, not new Protocol methods.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the QQBot production loop against WeCom parity.

- [ ] Ed25519 webhook signature verification + validation challenge (op=13) — without it the endpoint cannot be registered with QQ.
- [ ] Event normalization for `C2C_MESSAGE_CREATE` + `GROUP_AT_MESSAGE_CREATE` (the two primary messaging surfaces) → `AgentTurn`.
- [ ] @-bot content stripping for group messages.
- [ ] Webhook ACK (op=12, HTTP 200) for message events.
- [ ] Access token management (acquire + refresh).
- [ ] Text egress (`msg_type=0`) with `msg_id`+`msg_seq` passive-reply dedupe and output boundary.
- [ ] Markdown + keyboard feedback card dispatch (`msg_type=2` + `keyboard` with callback buttons `up`/`down`/`needs_fix`/`route_wrong`).
- [ ] `INTERACTION_CREATE` normalization → `FeedbackEvent` + interaction ACK (`PUT /interactions/{id}`).
- [ ] Feedback dedupe via `channel_core.idempotency`.
- [ ] Runtime session continuity (continuous conversation, interrupt resume, memory recall) via `QQBotSessionRuntime` + `platform_runtime`.
- [ ] One-click smoke-test toolkit (CLI + fixtures + runbook, env-var credentials, evidence collection).
- [ ] Feature flag default-off; frozen Protocol preserved; 24 V2 gates green.

### Add After Validation (v1.x)

Features to add once the core loop is working on live QQ sandbox.

- [ ] Rich media egress (image/file/video/voice via two-step upload) — trigger: legal document delivery (DOCX/PDF) demand from real trial users.
- [ ] Rich media inbound (image/voice/video/file `attachments[]` → `AttachmentRef`) — trigger: users sending contract screenshots.
- [ ] Markdown reply delivery for structured legal answers — trigger: readability feedback from trial.
- [ ] Interaction recall (`is_wakeup`) for over-window long-task completion — trigger: tasks exceeding the 60-min passive window.
- [ ] `GROUP_MESSAGE_CREATE` (full group messages, requires group-owner opt-in) — trigger: groups where admins enable full-message mode.
- [ ] `AT_MESSAGE_CREATE` / `DIRECT_MESSAGE_CREATE` (guild/channel + DM) — trigger: guild-channel deployment demand.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] WebSocket ingress mode (stateful, Resume/op6, no public IP) — defer until webhook mode is proven; WebSocket adds heartbeat/identify/reconnect complexity with marginal gain for the current deployment shape.
- [ ] Guild/channel management APIs (roles, permissions, sub-channels, forums, audio stage) — defer; separate product surface outside V2 messaging-loop scope.
- [ ] QQ-built-in voice ASR passthrough into `AgentTurn.content` — defer; cheap to add but only relevant once voice inbound is supported.
- [ ] Group role-aware routing (owner/admin/member privileges) — defer; niche, capture in metadata now, act on later.
- [ ] Active push beyond `is_wakeup` (monthly quota-managed broadcasts) — defer; quota-capped and user-opt-in-dependent, low legal-assistant value.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Ed25519 webhook signature verification + challenge | HIGH | MEDIUM | P1 |
| Event normalization (C2C + Group@) | HIGH | MEDIUM | P1 |
| @-bot content stripping | HIGH | LOW | P1 |
| Webhook ACK (op=12) | HIGH | LOW | P1 |
| Access token management | HIGH | MEDIUM | P1 |
| Text egress + msg_id/msg_seq dedupe + output boundary | HIGH | MEDIUM | P1 |
| Keyboard feedback card dispatch (markdown + keyboard) | HIGH | HIGH | P1 |
| INTERACTION_CREATE → FeedbackEvent + interaction ACK | HIGH | MEDIUM | P1 |
| Feedback dedupe | HIGH | LOW | P1 |
| Runtime session continuity (QQBotSessionRuntime) | HIGH | MEDIUM | P1 |
| One-click smoke-test toolkit | HIGH | MEDIUM | P1 |
| Feature flag default-off + frozen Protocol preservation | HIGH | LOW | P1 |
| Rich media egress (image/file/video/voice) | MEDIUM | HIGH | P2 |
| Rich media inbound (attachments → AttachmentRef) | MEDIUM | MEDIUM | P2 |
| Markdown reply delivery | MEDIUM | MEDIUM | P2 |
| Interaction recall (is_wakeup) | MEDIUM | MEDIUM | P2 |
| GROUP_MESSAGE_CREATE (full group) | LOW | LOW | P2 |
| Guild/channel + DM events (AT_MESSAGE_CREATE / DIRECT_MESSAGE_CREATE) | LOW | MEDIUM | P3 |
| WebSocket ingress mode | LOW | HIGH | P3 |
| Guild management APIs (roles/permissions/forums/audio) | LOW | HIGH | P3 |
| Voice ASR passthrough | LOW | LOW | P3 |
| Group role-aware routing | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | WeCom (InkStatute baseline) | QQ Bot (official platform) | Our Approach (QQBot channel) |
|---------|--------------|--------------|--------------|
| Ingress transport | HTTPS callback (XML/JSON, AES-encrypted) | Webhook (JSON, Ed25519-signed) OR WebSocket (stateful, Resume) | Webhook-first (mirrors WeCom callback shape); WebSocket deferred |
| Signature scheme | SHA1(sort(token,ts,nonce,encrypted)) + AES | Ed25519 over `timestamp+body`; Bot-Secret-derived keypair | New Ed25519 helper; no WeCom code reuse |
| URL verification | echostr decryption | op=13 challenge: sign(event_ts+plain_token) | New challenge handler in `verify_and_ack` |
| ACK | Return `"success"` | HTTP 200 empty (op=12) + `PUT /interactions/{id}` for button clicks | Two-tier ACK: event ACK + interaction ACK |
| Message types | text/file/image/voice/template_card (string msgtype) | msg_type int: 0 text, 2 markdown, 3 ark, 4 embed, 7 media | Map to `ChannelDelivery.metadata.delivery_type`; markdown as differentiator |
| Trigger model | All messages in configured chat | Group = @-bot only; C2C = all | Strip @-prefix for group; C2C passthrough |
| Identity | UserID + chat_id | user_openid / member_openid / group_openid | Composite conversation_id from openids |
| Reply window | 48h customer-service window | C2C 60min/4 replies; Group 5min/5 replies | Surface window expiry as delivery failure; is_wakeup for over-window |
| Active push | 48h window | 4/month per target (opt-in dependent) | Avoid auto-push; use is_wakeup recall |
| Interactive cards | template_card (pre-registered card_id) | markdown + keyboard (inline buttons, no template needed for C2C/group) | Build keyboard envelope with callback buttons; reuse FeedbackEvent enum |
| Feedback callback | button_callback event (EventKey) | INTERACTION_CREATE (data.resolved.button_data) + interaction ACK | Map button_data → action; reuse feedback-service dedupe |
| Rich media egress | media_id upload + send | two-step: /files upload → file_info → msg_type=7 (TTL) | New two-step egress; delivery_guard for contract |
| Idempotency | App-side (channel_core.idempotency) | Platform-side msg_id+msg_seq + app-side | Both: set msg_seq; keep app-side idempotency key |
| Session continuity | WeComSessionRuntime + platform_runtime | No platform session; build on openids | QQBotSessionRuntime mirroring WeCom pattern |
| Auth | access_token (corpid/secret) | access_token (appId/clientSecret), 7200s | New token cache; secret refs in config |

## Sources

- Official QQ Open Platform docs (bot.q.qq.com, API v2):
  - 事件订阅与通知 (event-emit): payload `{id,op,s,t,d}`, opcodes (0 Dispatch, 12 HTTP Callback ACK, 13 回调地址验证), intents bitmask (GROUP_AND_C2C_EVENT 1<<25, INTERACTION 1<<26, MESSAGE_AUDIT 1<<27).
  - 安全和授权 (sign): Ed25519 verification, `X-Signature-Ed25519` / `X-Signature-Timestamp` headers, Bot-Secret repeat-to-32-byte-seed key derivation, validation challenge sign(event_ts+plain_token).
  - 接口调用与鉴权 (api-use): `https://bots.qq.com/app/getAppAccessToken` (appId+clientSecret → access_token, 7200s), `Authorization: QQBot {ACCESS_TOKEN}`, base URL `https://api.sgroup.qq.com`.
  - 发送消息 (send): `/v2/users/{openid}/messages`, `/v2/groups/{group_openid}/messages`, msg_type 0/2/3/4/7, msg_id+msg_seq, event_id, is_wakeup, passive/active quotas (C2C 60min/4, Group 5min/5, active 4/month, is_wakeup 30-day windows).
  - 富媒体消息 (rich-media): `/v2/users/{openid}/files`, `/v2/groups/{group_openid}/files`, file_type 1/2/3/4, file_info+ttl, msg_type=7.
  - 事件 (event): C2C_MESSAGE_CREATE, GROUP_AT_MESSAGE_CREATE, GROUP_MESSAGE_CREATE, AT_MESSAGE_CREATE, DIRECT_MESSAGE_CREATE field structures (id, author.user_openid/member_openid, content, timestamp RFC3339, group_openid, attachments[]).
  - 消息按钮 (msg-btn): keyboard structure, button action.type 0/1/2, INTERACTION_CREATE (type=11) fields (id, scene, chat_type, user_openid/group_openid/group_member_openid, data.resolved.button_data/button_id/message_id), interaction ACK `PUT /interactions/{id}` with code 0/1/2/3.
  - Markdown 消息 (markdown): custom content + custom_template_id+params, C2C/group open to all bots.
- Open-source SDK cross-checks: nonebot adapter-qq, AstrBot (qqofficial_webhook/qo_webhook_server.py — Ed25519 seed/sign), LangBot (callback validation structure), OpenClaw qqbot (webhook vs websocket comparison, Ed25519 auto-verify), tencent-connect/openclaw-qqbot (media skill, two-step send).
- Existing InkStatute codebase (parity baseline):
  - `services/wecom-service/src/wecom_service/protocol.py` (WeCom signature verify, ACK `"success"`, callback envelope parse).
  - `services/wecom-service/src/wecom_service/normalization.py` (WeCom turn + feedback normalization, FEEDBACK_ACTIONS, SkillCandidate).
  - `services/wecom-service/src/wecom_service/sender.py` (text/file/template_card envelope builders).
  - `services/wecom-service/src/wecom_service/ingress_runtime.py` + `session_runtime.py` (session continuity pattern to mirror).
  - `packages/channel-core/src/channel_core/` (idempotency, output_policy, delivery_guard, active_task_router, owned_notices — all reused unchanged).
  - `packages/channels/qqbot/` (existing fixture-only adapter, 6-method Protocol, config secret refs, feature flag, no-wecom-import test).

---
*Feature research for: QQ Bot platform channel production (v1.8 QQBot Channel Production milestone)*
*Researched: 2026-07-07*
