# Pitfalls Research: v1.8 QQBot Channel Production

**Domain:** QQBot Channel Production — real QQ Bot platform ingress/egress, feedback loop parity, runtime session continuity, and one-click smoke-test toolkit, added to an existing multi-channel platform with a working WeCom channel.
**Researched:** 2026-07-07
**Confidence:** HIGH

This research covers common mistakes when **adding real QQ Bot production features to the existing InkStatute V2 system** — a Python 3.11 async legal-domain agent platform with a frozen `ChannelAdapter` Protocol (6 methods: `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health` at `packages/platform-runtime/src/platform_runtime/protocols.py:208-219`), a frozen `FeedbackSource` enum (4 values: `card_button`, `text_command`, `web_form`, `admin_annotation`), 24 V2 CI gates (1,547+ tests), JSONL contract event logs using `raw_payload_ref` for privacy, an output boundary that suppresses Hermes/gateway/meta notices, all runtime lanes default-OFF (`qqbot_channel_enabled` defaults `False`), a shared `channel-core` package extracted in v1.6, and two open V2 human gates (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) running in parallel. The QQBot adapter currently exists as a **fixture-only** implementation (`packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`) with no network IO. v1.8 must promote it to production while preserving every one of these invariants. Phase numbering continues from v1.7 (next phase = 58).

---

## Critical Pitfalls

### Pitfall 1: Treating QQ Bot callback signature verification like WeCom's SHA-1 scheme

**What goes wrong:**
The existing WeCom callback verification (`services/wecom-service/src/wecom_service/protocol.py:15-27`) uses a simple `hashlib.sha1` digest over `sorted([token, timestamp, nonce, encrypted_payload])`. A developer copies that pattern for QQ Bot, producing a SHA-1 (or HMAC-SHA256) verifier. Every QQ Bot callback then passes verification trivially — or fails silently — because **QQ Bot uses Ed25519 asymmetric signatures**, not a symmetric hash. Worse, the QQ Bot signature is over `timestamp + raw_body` (byte-concatenated, in that exact order), not a sorted join of fields. An attacker who discovers the verifier is wrong can forge inbound callbacks and inject fake lawyer turns or fake feedback events into the runtime.

**Why it happens:**
WeCom is the only existing production channel, so its verification code is the most visible reference. The frozen `verify_and_ack` Protocol method has the same signature for both channels, creating an illusion that the verification *logic* is also shared. The developer reaches for the familiar SHA-1 pattern instead of reading the QQ Bot platform docs.

**How to avoid:**
- Implement QQ Bot signature verification per the official spec: derive a 32-byte Ed25519 seed by **repeating** the `BotSecret` string until it reaches `ed25519.SeedSize` (32 bytes), generate the keypair from that seed, then `ed25519.Verify(publicKey, timestamp+raw_body, signature)` where `signature` is the hex-decoded `X-Signature-Ed25519` header.
- Use constant-time comparison (`hmac.compare_digest` equivalent for the verify result) — do not short-circuit on boolean.
- Read the raw HTTP body **before** any JSON parsing; the signature is over the raw bytes, not a re-serialized JSON object (re-serialization changes byte ordering and breaks verification).
- Add a unit test with the official demo vectors (`secret: naOC0ocQE3shWLAfffVLB1rhYPG7`, `body: {"op":0,"d":{}}`, `timestamp: 1725442341`, expected `sig: 865ad13a...`) to prove the implementation matches the platform.
- Do **not** reuse `wecom_service.protocol.verify_callback_signature` — import nothing from `wecom_service` (enforced by `test_no_wecom_import.py`).

**Warning signs:**
- QQBot `verify_and_ack` imports `hashlib`/`sha1` instead of `cryptography`/`nacl` Ed25519.
- The verifier reads `raw.metadata.get("payload")` (parsed dict) instead of raw body bytes.
- No test uses the official QQ Bot demo vector.
- `signature_status` in `AckResponse.metadata` stays hardcoded to `"secret_ref_required"` (the fixture value) instead of `"verified"` / `"failed"`.

**Phase to address:**
Real QQ Bot ingress phase (signature verification + ACK) — design the Ed25519 verifier before writing any ingress handler code.

---

### Pitfall 2: Missing the QQ Bot callback URL validation handshake (op=13)

**What goes wrong:**
QQ Bot performs a **two-phase** webhook setup. When you register a callback URL, the platform sends a validation request with `op: 13` containing `plain_token` and `event_ts` inside `d`. The server must respond with `{"plain_token": ..., "signature": ...}` where the signature is an Ed25519 sign over `event_ts + plain_token`. A developer who only handles normal event callbacks (`op: 0` / `op: 12`) returns a generic ACK to the validation request. The platform then **rejects the callback URL registration entirely** — the bot never receives any events. The developer spends hours debugging "no events arriving" because the validation handshake was never implemented.

**Why it happens:**
WeCom has no equivalent two-phase validation; its `ack_response()` just returns `"success"`. The frozen `verify_and_ack` Protocol method has one return type (`AckResponse`), so the developer assumes one response shape covers all cases. The validation request looks superficially like a normal callback (same endpoint, same headers) but requires a fundamentally different response body.

**How to avoid:**
- Detect `op == 13` (or `t == "WEBHOOK_VERIFY"`) **before** normal signature/event processing and return the `{plain_token, signature}` validation response, not a generic `AckResponse`.
- The validation response uses the **signing** key (private key from the seed), while normal callback verification uses the **verify** key (public key). Both derive from the same seed, but the code paths are distinct.
- Add a fixture/test that replays a real `op: 13` validation request and asserts the response contains `plain_token` and a valid 128-char hex signature.
- Document that validation requests arrive **only** during URL registration / re-validation, so production traffic won't include them — but the handler must always be ready.

**Warning signs:**
- The ingress handler has no branch on `op` or `t` field.
- Callback URL registration in the QQ Bot console fails with a validation error.
- No test fixture contains an `op: 13` payload.
- The smoke-test toolkit can send messages but the operator had to "manually skip" URL validation.

**Phase to address:**
Real QQ Bot ingress phase — implement validation handshake alongside signature verification in the same plan.

---

### Pitfall 3: Assuming QQ Bot passive reply has no time window (unlike WeCom)

**What goes wrong:**
WeCom has no hard reply deadline — the service can process a long legal task and deliver whenever ready. QQ Bot **enforces a passive-reply window**: C2C replies must be sent within **60 minutes** (max 4 replies per `msg_id`), group/channel replies within **5 minutes** (max 5 replies per `msg_id`). If the agent backend (Hermes) takes 8 minutes to produce a legal answer for a group message, the QQ Bot API returns error `304027` (`MSG_EXPIRE`) and the delivery silently fails. The user sees nothing. Worse, the existing `delivery_guard` (`packages/channel-core/src/channel_core/delivery_guard.py`) already handles "agent returned progress without artifact" but has **no concept of a platform-enforced reply deadline** — it will happily mark a 10-minute task as `completed` even though the QQ Bot window already closed.

**Why it happens:**
WeCom's lack of a deadline makes the deadline invisible in the existing codebase. The `ChannelDelivery` dataclass and `DeliveryResult` have no `deadline_ms` or `expires_at` field. The `ack_deadline_ms=3000` in QQBot capabilities (`adapter.py:46`) refers to the ACK window, not the reply window — a developer may conflate the two.

**How to avoid:**
- Distinguish **ACK deadline** (respond to the webhook within ~3s to avoid platform retries) from **passive-reply deadline** (send the actual reply within 5min group / 60min C2C).
- For long-running legal tasks that exceed the group 5-minute window, use **active messages** (no `msg_id` field) instead of passive replies — but active messages are limited to 4/month per user/group and require the user to not have disabled them. Design the delivery strategy per scene.
- Track `msg_id` + `msg_seq` for passive replies; increment `msg_seq` for each reply to the same `msg_id` (duplicate `msg_id + msg_seq` is rejected).
- Add a delivery-guard check: if `now > received_at + reply_window` for a passive reply, fail closed with a distinct `issue_code` (e.g. `qqbot_passive_reply_window_expired`) and surface an InkStatute-owned service notice to the user ("the assistant is still working, the reply will arrive shortly") via an active message if the user hasn't disabled them.
- Add a test: simulate a task that completes at `received_at + 6min` for a group message and assert the delivery is refused with the window-expired code, not silently sent.

**Warning signs:**
- `deliver()` ignores `msg_id` / `event_id` / `msg_seq` from the inbound payload.
- No test covers a reply sent after the 5-minute group window.
- Production logs show `304027 MSG_EXPIRE` errors that are swallowed without user-facing notice.
- The smoke-test toolkit only tests fast (<5s) replies and never exercises the deadline boundary.

**Phase to address:**
Real QQ Bot egress phase — model the passive/active reply distinction and deadline before writing the send client.

---

### Pitfall 4: Reusing WeCom template_card format for QQ Bot card/feedback delivery

**What goes wrong:**
WeCom uses a `template_card` message type with a `card_id` + `title` + `feedback_target` structure (`services/wecom-service/src/wecom_service/sender.py:42-64`). A developer copies this envelope for QQ Bot. But QQ Bot has **no `template_card` type** — it uses `msg_type` integers (0=text, 2=markdown, 3=ark, 4=embed, 7=media) plus a `keyboard` object for interactive buttons. The feedback card that WeCom renders as a native template card must be rendered on QQ Bot as a `markdown` + `keyboard` combination (or an `ark` template). Sending a WeCom-shaped `template_card` payload to the QQ Bot API returns a `400`/parameter error, and the feedback loop — the entire v1.8 feedback parity goal — breaks.

**Why it happens:**
The frozen `ChannelDelivery` type carries `metadata.delivery_type == "card"` and the fixture (`qqbot_channel_loop.json:97-129`) already uses a `card_data.buttons` shape that looks portable. The developer assumes "card" maps to a platform-native card type on both channels. The `FeedbackSource` enum is frozen at `card_button` for both channels, reinforcing the illusion that the card mechanism is identical.

**How to avoid:**
- Map `delivery_type == "card"` to a QQ Bot **keyboard** payload (`msg_type: 2` markdown with a `keyboard` object containing button rows), not a `template_card`. Each feedback button (`up`, `down`, `route_wrong`) becomes a keyboard button with a `data` payload that the callback will carry back.
- Alternatively use `msg_type: 3` (ark) with a template, but keyboard is the documented feedback-interaction primitive for QQ Bot.
- The feedback **callback** from a QQ Bot keyboard button arrives as an `INTERACTION_CREATE` event with `data.resolved.button_data` / `data.type == "button"` — not as a WeCom-style `button_callback` event. The normalizer must map this to `FeedbackEvent.source = "card_button"` (the frozen enum value) without adding a new enum value.
- Add a test: build a QQ Bot card delivery envelope and assert it contains `keyboard` (not `template_card`), and that a simulated `INTERACTION_CREATE` callback normalizes to `FeedbackEvent(source="card_button", action="up")`.
- Keep the output boundary (`apply_output_policy`) applied to the card title/markdown content before it enters the keyboard payload — backend notices can hide in markdown text too.

**Warning signs:**
- QQ Bot `deliver()` for `delivery_type == "card"` builds an envelope with a `template_card` key.
- No test simulates an `INTERACTION_CREATE` callback.
- Feedback button callbacks arrive but `normalize_inbound` returns a message instead of a `FeedbackEvent`.
- The `FeedbackSource` enum gains a 5th value (violates the freeze test at `test_contract_freeze_not_violated.py:44-48`).

**Phase to address:**
QQBot feedback loop parity phase — design the card→keyboard mapping and INTERACTION_CREATE normalization before implementing the feedback dispatch.

---

### Pitfall 5: Modifying the frozen ChannelAdapter Protocol to add QQ-specific methods

**What goes wrong:**
QQ Bot has platform-specific needs that the 6-method Protocol doesn't expose: access-token refresh, WebSocket heartbeat/Resume, `msg_seq` tracking, webhook-vs-websocket mode selection. A developer "fixes" this by adding a 7th method (e.g. `async def refresh_token(self) -> None`) or a new field to `ChannelCapabilitySet`. The contract-freeze test (`test_contract_freeze_not_violated.py:31-42`) immediately fails, 24 V2 gates go red, and the entire milestone blocks. Even if the test is "temporarily" updated, the freeze is a V2 acceptance invariant — modifying it invalidates prior milestone audits.

**Why it happens:**
The Protocol was designed when QQBot was fixture-only (`adapter.py:1` "fixture-grade, no network IO"). Real platform integration surfaces real needs that weren't visible at freeze time. The developer sees the Protocol as "incomplete" rather than "frozen by design."

**How to avoid:**
- The frozen Protocol defines the **channel-agnostic** surface. QQ-specific concerns (token refresh, heartbeat, mode) belong in the **adapter implementation** (`QQBotChannelAdapter` internals) or a **host-owned transport layer**, not on the Protocol.
- `verify_and_ack` can internally perform token refresh before verifying — the caller doesn't need to know.
- `capabilities()` metadata dict (`adapter.py:48-57`) can carry QQ-specific fields (`receive_mode`, `token_refresh_strategy`) without changing the `ChannelCapabilitySet` dataclass shape — verify the dataclass is not extended first.
- If a genuinely shared need emerges (e.g. all channels need token refresh), document it as a **post-v1.8 contract evolution proposal**, not an in-milestone Protocol change. The freeze is explicit in PROJECT.md: "Frozen ChannelAdapter Protocol (6 methods) must not be modified."
- Run `test_contract_freeze_not_violated.py` as the first test in every QQBot phase plan; treat any failure as a stop-work signal.

**Warning signs:**
- A PR adds a method to `ChannelAdapter` or a field to `ChannelCapabilitySet` / `AckResponse` / `DeliveryResult`.
- The contract-freeze test is modified rather than left green.
- `dir(ChannelAdapter)` returns 7 methods instead of 6.
- A developer argues "the Protocol is too restrictive for real channels."

**Phase to address:**
Pre-implementation safety phase (first phase of v1.8) — re-affirm the freeze and document where QQ-specific concerns live without Protocol changes.

---

### Pitfall 6: Letting the QQ Bot access_token leak into logs, contract events, or smoke-test evidence

**What goes wrong:**
QQ Bot uses an `AppAccessToken` (`POST https://bots.qq.com/app/getAppAccessToken` with `appId` + `clientSecret`, returns `access_token` valid 7200s). Unlike WeCom's per-callback token, this is a **bearer token for all OpenAPI calls**. A developer logs the full HTTP request/response for debugging, or writes the token into `DeliveryResult.metadata` for traceability, or the smoke-test toolkit prints the token in its evidence collection. The token then lands in JSONL contract logs, CI artifacts, or the repo — giving anyone with repo access the ability to send messages as the bot. The existing `output_policy.py` block patterns (`output_policy.py:59-80`) catch `access_token` / `api_key` / `client_secret` strings, but only in **delivery content**, not in metadata fields or log lines.

**Why it happens:**
The existing `QQBotChannelConfig` (`config.py:21-23`) already uses `app_id_ref` / `app_secret_ref` / `token_secret_ref` (references, not values) — but real network IO requires resolving those refs to actual values at runtime. The developer adds logging to debug a failed API call and forgets the token is in the headers. The smoke-test toolkit, designed to collect "evidence," naturally wants to capture the full request/response for reproducibility.

**How to avoid:**
- The adapter must resolve secret refs to values **only inside the network boundary** (the transport client), never in the Protocol-returning methods. `verify_and_ack`, `normalize_inbound`, `deliver`, `health` return metadata with `secret_refs_configured: {bool}` (as the fixture already does, `adapter.py:52-56`), never the secret values.
- Extend the existing `_reject_unsafe_keys` pattern (`ingress_runtime.py:223`) to QQ Bot metadata: reject any key matching `access_token`, `app_secret`, `client_secret`, `bot_secret`, `authorization` before writing to contract events or delivery metadata.
- The smoke-test toolkit must redact `Authorization` headers and `access_token` / `clientSecret` fields from any captured HTTP evidence. Provide a `redact_credentials(payload)` helper and assert in a test that no evidence fixture contains a token-shaped string.
- Token refresh logic must log `"token refreshed"` (event + expiry), never the token value.
- Add a test: scan all QQBot-produced `DeliveryResult.metadata` and contract event fixtures for token patterns; assert none present.

**Warning signs:**
- A log line contains `Authorization: QQBot eyJ...` or `access_token: ...`.
- `DeliveryResult.metadata` or `AckResponse.metadata` contains an `access_token` or `authorization` key.
- Smoke-test evidence files contain unredacted HTTP headers.
- The transport client logs full `httpx.Request` / `httpx.Response` objects.
- A `.env` file or token value appears in a git diff.

**Phase to address:**
Pre-implementation safety phase (credential safety design) AND smoke-test toolkit phase (redaction in evidence collection).

---

### Pitfall 7: Assuming WebSocket and Webhook receive modes are interchangeable

**What goes wrong:**
QQ Bot supports two receive modes: **Webhook** (HTTP callback URL, HTTPS, ports 80/443/8080/8443 only) and **WebSocket** (gateway long connection, no public endpoint needed). The platform treats them as **mutually exclusive** — once a valid HTTPS webhook URL is configured, WebSocket delivery stops. A developer builds the adapter for WebSocket mode (easier to test locally), then the operator configures a webhook URL in the console for production. The bot stops receiving events entirely because the platform switched to webhook delivery but the adapter is still expecting WebSocket. Conversely, a smoke-test built for webhook fails in a local dev environment that can't expose HTTPS on port 443.

**Why it happens:**
WeCom has only one receive mode (webhook callback), so there's no existing precedent for mode selection. The `QQBotChannelConfig` (`config.py:11-24`) has no `receive_mode` field. The developer picks one mode without realizing the platform enforces mutual exclusivity.

**How to avoid:**
- Add a `receive_mode` config field (`"webhook" | "websocket"`) to `QQBotChannelConfig` (this is an implementation config, not a Protocol change). Default to `"websocket"` for local dev / smoke-test, `"webhook"` for production.
- The adapter's `verify_and_ack` path is only used in webhook mode; in WebSocket mode, events arrive via the gateway and ACK is the WebSocket `op: 12` heartbeat-style ack, not an HTTP response. Document this clearly.
- The smoke-test toolkit must detect the configured mode and run the appropriate checks; it must not assume webhook.
- Add a test: assert that `QQBotChannelConfig.from_env` reads `INKSTATUTE_QQBOT_RECEIVE_MODE` and that the adapter's behavior branches on it.
- Document in the operator runbook: "Configure the same receive mode in the QQ Bot console as in `INKSTATUTE_QQBOT_RECEIVE_MODE`. Switching modes in the console without updating the env var will silently stop event delivery."

**Warning signs:**
- `QQBotChannelConfig` has no `receive_mode` field.
- The adapter always starts a WebSocket gateway even when webhook is configured.
- The smoke-test assumes HTTPS on port 443 is available.
- Production events stop after an operator "just registered the webhook URL."
- No test or runbook mentions the mutual exclusivity.

**Phase to address:**
Real QQ Bot ingress phase — model receive mode in config before implementing either transport.

---

### Pitfall 8: Breaking session continuity by assuming QQ Bot conversation IDs work like WeCom thread IDs

**What goes wrong:**
The existing `WeComSessionRuntime` (`services/wecom-service/src/wecom_service/session_runtime.py:92-126`) resolves sessions using `SessionScope` with `conversation_id` + `thread_id` + `user_id` + `bot_instance_id`. WeCom conversations are stable (a WeCom chat has a persistent `chat_id`). QQ Bot's identity model is **scene-specific**: a C2C message has a `user_openid`, a group message has a `group_openid` + `user_openid`, a channel message has a `channel_id` + `guild_id`. There is no single stable "conversation_id" — the same user has a different identity in C2C vs group vs channel. A developer maps `group_openid` to `conversation_id` and discovers that the user's C2C session and group session collide (same `user_id`, different conversation), or that a channel message has no `conversation_id` at all. Session continuity — the v1.8 runtime session continuity goal — breaks: interrupts resume the wrong session, memory recall pulls from the wrong conversation, and feedback is attributed to the wrong turn.

**Why it happens:**
The frozen `AgentTurn.conversation_id` (`platform_contract.events`) is a required string. The developer forces a QQ Bot field into it without considering that QQ Bot's identity is **multi-scene**. The `WeComSessionRuntime` is WeCom-specific (its name says so), but there's no `QQBotSessionRuntime` yet — the v1.8 goal is "channel-generic runtime," so the developer reaches for the WeCom runtime and hits the identity mismatch.

**How to avoid:**
- Define a QQ Bot **conversation key derivation** that is scene-aware: `qqbot:{scene}:{scene_id}:{user_openid}` where `scene` is `c2c` / `group` / `channel` and `scene_id` is the `user_openid` (C2C), `group_openid` (group), or `channel_id` (channel). This becomes `AgentTurn.conversation_id`.
- Do **not** reuse `WeComSessionRuntime` directly. The v1.8 goal is a **channel-generic runtime** — extract the session resolution logic (interrupt resume, memory recall, active-task routing) into a channel-core runtime that both WeCom and QQBot feed with scene-derived `SessionScope` values. The WeCom runtime becomes a thin wrapper (as `delivery_guard.py` already did for channel-core).
- `SessionScope.channel_id` must be `"qqbot"` (the frozen `Channel.QQBOT.value`), not `"wecom"` — the session resolver must partition by channel.
- Add a test: the same `user_openid` in a C2C message and a group message produces **different** `conversation_id` values and **different** `SessionScope` (different `channel_id` or different `conversation_id`), and interrupt resume does not cross scenes.
- Memory recall must be scoped to the conversation key, not just `user_id` — otherwise a user's group legal question leaks into their C2C session context.

**Warning signs:**
- `conversation_id` is set to `user_openid` alone (collides across scenes).
- `QQBotSessionRuntime` is a copy-paste of `WeComSessionRuntime` with "qqbot" string-replaced.
- A C2C interrupt is resumed by a group message from the same user.
- Memory recall returns context from a different scene.
- No test covers the same user across C2C + group + channel scenes.

**Phase to address:**
Runtime session continuity phase — design scene-aware conversation key derivation before wiring the runtime.

---

### Pitfall 9: Smoke-test toolkit producing non-reproducible runs

**What goes wrong:**
The v1.8 smoke-test toolkit is a "one-click" CLI that sends a real message through the QQ Bot platform and collects evidence. A developer builds it with hardcoded timestamps, live `msg_id` values, or token-dependent assertions. The next operator run (different token, different `msg_id`, different time) fails even though the bot works correctly. Or worse: the toolkit passes on the developer's machine (with their `.env`) but fails in CI or on another operator's machine because it depended on an unrecorded env var, a specific receive mode, or a leftover WebSocket connection. The "one-click" promise breaks and the human gate (live platform run) can't be reliably executed.

**Why it happens:**
Reproducibility is a cross-cutting concern that's easy to overlook when the toolkit "works on my machine." Live platform runs inherently involve non-deterministic values (`msg_id`, `event_id`, `access_token`, timestamps). The developer hardcodes the values from their successful run instead of parameterizing and redacting them.

**How to avoid:**
- The toolkit must be **input-driven**: all credentials via env vars (`INKSTATUTE_QQBOT_APP_ID_REF`, `INKSTATUTE_QQBOT_APP_SECRET_REF`, `INKSTATUTE_QQBOT_RECEIVE_MODE`, etc.), all test messages from fixtures (not inline strings), all assertions on **structure + status codes**, not on exact `msg_id` / `token` / timestamp values.
- Evidence collection must record: scenario name, input fixture ref, HTTP status codes, error codes (e.g. `304027`), normalized `AgentTurn` / `FeedbackEvent` field shapes (with values redacted to refs/hashes), and a pass/fail per step. It must **not** record raw tokens, raw user message text, or raw `msg_id` values (use `msg_id_ref` = hash).
- The toolkit must be **idempotent**: running it twice produces the same pass/fail result (use distinct `msg_seq` values or distinct fixture messages to avoid `msg_id` dedupe rejection on re-run).
- Provide a `--dry-run` mode that validates config + fixtures + signature verification logic without hitting the live platform. The live run is the human gate; the dry run is CI-able.
- Add a test: run the toolkit in dry-run mode in CI and assert it passes without any live credentials.

**Warning signs:**
- The toolkit has hardcoded `msg_id`, `access_token`, or timestamp values in assertions.
- Evidence files contain raw `msg_id` or token values.
- The toolkit passes locally but fails in CI or for another operator.
- Re-running the toolkit immediately fails (duplicate `msg_id + msg_seq`).
- There is no `--dry-run` mode.

**Phase to address:**
Smoke-test toolkit phase — design reproducibility and redaction before writing the CLI.

---

### Pitfall 10: WebSocket gateway disconnect losing events without Resume

**What goes wrong:**
In WebSocket receive mode, the QQ Bot gateway requires periodic heartbeats and supports `Opcode 6 Resume` with the last-seen `s` (sequence) to replay missed events after a reconnect. A developer implements heartbeat but not Resume (or implements Resume but doesn't persist `s` across reconnects). When the connection drops — which it will, on network blips or platform maintenance — the bot silently loses every event that arrived during the disconnect. A lawyer's message vanishes. The session runtime never sees the turn, the interrupt never resumes, and the user gets no reply. The delivery guard can't catch this because it operates on turns the runtime *received*, not turns the platform *sent*.

**Why it happens:**
WeCom is webhook-based (the platform retries on non-ACK), so there's no existing Resume pattern. WebSocket reconnect logic is easy to get "mostly right" — heartbeats keep the connection alive, and a naive reconnect works until the first disconnect-with-events. The developer tests in a stable environment where disconnects don't happen.

**How to avoid:**
- Persist the last-processed `s` (sequence) value to a durable store (not in-memory) after each event is normalized and acked. On reconnect, send `Opcode 6 Resume` with that `s` to replay missed events.
- Do **not** re-send `Opcode 2 Identify` on reconnect — the docs are explicit that Resume replaces Identify after the initial connection.
- Add a timeout: if Resume doesn't replay the expected events within N seconds, fall back to a full reconnect (Identify) and log a `resume_fallback` event.
- Add a test: simulate a disconnect after event `s=5`, reconnect, and assert events `s=6,7,8` are replayed and processed.
- The smoke-test toolkit should include a "reconnect resilience" scenario that kills the WebSocket and verifies event recovery.

**Warning signs:**
- The gateway client persists `s` in memory only (lost on process restart).
- Reconnect sends `Identify` instead of `Resume`.
- No test simulates a disconnect with in-flight events.
- Production logs show reconnects but no `resume` events.
- Users report "I sent a message but the bot never replied" after a deploy.

**Phase to address:**
Real QQ Bot ingress phase (WebSocket transport) — implement Resume alongside heartbeat in the gateway client.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copy-paste `WeComSessionRuntime` as `QQBotSessionRuntime` with string replacements | Fast parity, one file | Two runtimes drift; bug fixes applied twice; channel-generic runtime goal unmet; scene-aware identity never implemented | Never — v1.8 explicitly requires a channel-generic runtime |
| Hardcode `msg_type: 0` (text) for all QQ Bot deliveries | Avoids learning ark/markdown/keyboard | Feedback cards can't render; file/image delivery impossible; milestone goal of "cards" unmet | Only for the very first text-only smoke-test, replaced before feedback phase |
| Skip `msg_seq` tracking, rely on `msg_id` alone | Simpler send logic | Duplicate replies to the same `msg_id` are rejected by the platform; multi-part legal answers fail mid-stream | Never in production; acceptable in dry-run only |
| Log full HTTP request/response for QQ Bot API debugging | Fast debugging | `access_token` / `clientSecret` leak into logs and possibly contract events | Never in committed code; acceptable in a local uncommitted debug branch only |
| Use webhook mode for local dev without HTTPS | No TLS cert needed locally | Platform rejects non-HTTPS callback URLs; validation handshake never tested; production surprises | Use WebSocket mode for local dev instead; webhook only in staging/prod |
| Reuse WeCom `template_card` envelope shape for QQ Bot | One envelope builder | QQ Bot API rejects `template_card`; feedback loop breaks; output boundary not applied to keyboard markdown | Never |
| Store `access_token` in `QQBotChannelConfig` for reuse | Avoid re-fetching | Token expires (7200s); stale token causes 401s; token value in config object risks logging/leak | Never — refresh on demand, keep only in transport client memory |

## Integration Gotchas

Common mistakes when connecting the QQ Bot platform to the existing InkStatute system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| QQ Bot signature verification ↔ `verify_and_ack` Protocol | Reusing WeCom SHA-1 verifier; signing over parsed JSON instead of raw body | Implement Ed25519 per QQ Bot spec; sign/verify over `timestamp + raw_body` bytes; use official demo vectors in tests |
| QQ Bot callback validation (op=13) ↔ `verify_and_ack` | Returning generic `AckResponse` to validation request; URL registration fails | Detect `op==13` first; return `{plain_token, signature}` using the signing (private) key; test with a real validation fixture |
| QQ Bot access_token ↔ `QQBotChannelConfig` | Storing token value in config; logging token in `DeliveryResult.metadata` | Resolve `app_secret_ref` to value only in transport client; return `secret_refs_configured: {bool}` in Protocol metadata; redact all evidence |
| QQ Bot `msg_id` / `event_id` ↔ `ChannelDelivery` | Ignoring passive-reply window; sending active messages when passive is required | Track `msg_id` + `msg_seq`; enforce 5min (group) / 60min (C2C) window; fall back to active message with user notice if window expired |
| QQ Bot keyboard feedback ↔ `FeedbackEvent.source` enum | Adding a 5th `FeedbackSource` value for QQ | Map QQ `INTERACTION_CREATE` button callback to existing `card_button` value; freeze test stays green |
| QQ Bot scene identity ↔ `SessionScope.conversation_id` | Mapping `user_openid` alone to `conversation_id` (collides across C2C/group/channel) | Derive scene-aware key: `qqbot:{scene}:{scene_id}:{user_openid}`; partition sessions by channel + scene |
| QQ Bot WebSocket Resume ↔ session runtime | Not persisting sequence `s`; losing events on reconnect | Persist `s` durably; send `Opcode 6 Resume` on reconnect; test disconnect-with-events recovery |
| QQ Bot receive mode ↔ `QQBotChannelConfig` | No `receive_mode` field; adapter assumes one mode | Add `receive_mode` config; branch adapter behavior; document mutual exclusivity in runbook |
| channel-core reuse ↔ no `wecom_service` import | Importing WeCom helpers into QQBot adapter (violates `test_no_wecom_import.py`) | Import only from `channel_core`; if logic is missing from channel-core, extract it there first (as v1.6 did) |
| Output boundary ↔ QQ Bot markdown/ark content | Applying `apply_output_policy` only to text, not to markdown/ark/keyboard payloads | Apply boundary to all user-visible content fields (markdown body, ark prompt, keyboard button labels) before send |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous `access_token` refresh on every API call | High latency per send; platform rate limit on `getAppAccessToken` | Cache token with expiry; refresh only when `expires_in - 60s < now`; single-flight refresh under concurrency | >1 msg/s or concurrent sends |
| Blocking the event loop in Ed25519 verification | Slow ACKs; platform webhook timeout (3s); event retries | Ed25519 verify is CPU-fast (<1ms) but ensure no blocking IO in the verify path; use `asyncio.to_thread` if any IO | High webhook concurrency |
| One WebSocket connection per bot instance without sharding | Single connection bottleneck; no horizontal scaling | QQ Bot supports sharding via gateway; plan for `shard_count > 1` only if single shard saturates | >100 events/s (not v1.8 scope, but document) |
| Re-normalizing duplicate callbacks without idempotency cache | CPU waste; duplicate turns enter runtime | Use `channel_idempotency_key` (already in channel-core) with a process-local cache; the session runtime already dedupes by idempotency key | Platform retries (common on slow ACK) |
| Sending multi-part legal answers as N passive replies to one `msg_id` | Hits 4-reply (C2C) / 5-reply (group) cap; later parts rejected | Chunk into ≤4 (C2C) / ≤5 (group) replies, or send first part as passive + rest as active messages | Long legal answers (>4 parts) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging QQ Bot `access_token` or `clientSecret` in debug output | Token theft → impersonate bot, send messages as bot, exfiltrate user data | Redact `Authorization` headers in all log/evidence paths; extend `_reject_unsafe_keys` to QQ Bot metadata; test that no fixture contains token patterns |
| Committing `.env` with `INKSTATUTE_QQBOT_APP_SECRET_REF` resolved values | Permanent credential leak in git history | `.env` in `.gitignore` (verify); config uses `_ref` env var names, never values; pre-commit hook scans for `clientSecret` patterns |
| Smoke-test evidence containing raw user legal message text | Client legal material / work product committed to repo | Evidence records `content_ref` (hash) + `content_source_status`, never `content` value; redact all user text to refs |
| Skipping signature verification "for testing" | Forged inbound callbacks inject fake turns / feedback into runtime | Verification is mandatory in production; `qqbot_channel_enabled` must not bypass verification; dry-run mode still verifies signatures |
| Using `access_token` in URL query params instead of `Authorization` header | Token logged in proxy/CDN access logs | Always use `Authorization: QQBot {token}` header per spec; never in query string |
| Webhook endpoint on non-HTTPS or non-allowed port (not 80/443/8080/8443) | Platform rejects registration; or plaintext token transit | Enforce HTTPS + allowed ports in deployment; smoke-test validates endpoint config before live run |

## UX Pitfalls

Common user experience mistakes when adding QQ Bot as a lawyer-facing channel.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Bot only responds to @-bot in groups, but no documentation tells lawyers | Lawyers message the group and get no reply; assume bot is broken | Document the @-bot trigger requirement in the operator runbook and in the bot's auto-reply when a non-@ group message arrives (if platform allows) |
| Feedback card renders as raw ark JSON on QQ clients that don't support keyboard | Lawyers see JSON instead of buttons; feedback loop unusable | Detect client capability via `capabilities()`; fall back to text-based feedback ("reply 'good' or 'needs_fix'") when keyboard unsupported |
| Passive reply window expires silently for long legal tasks | Lawyer waits, gets no answer; task completed but undelivered | Send an interim InkStatute-owned service notice ("still working...") within the window; deliver final answer as active message |
| Same legal conversation split across C2C and group with no shared context | Lawyer has to re-explain the case in each scene | Document that session continuity is scene-scoped by design (privacy); consider a future "cross-scene link" feature only after privacy review |
| Bot sends active messages without user opt-in awareness | Users disabled active messages; delivery fails; or users feel spammed | Only send active messages when necessary (window expiry); respect user's platform-level opt-out; log `active_message_attempted` events |
| Markdown rendering differs between QQ clients (mobile vs desktop) | Legal formatting (numbered lists, bold) renders inconsistently | Test markdown on both QQ mobile + desktop; fall back to plain text for critical formatting; avoid QQ-specific markdown extensions |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Signature verification:** Often missing the raw-body (vs parsed-JSON) signing — verify the verifier reads `request.body` bytes, not `json.loads(body)`
- [ ] **Callback validation handshake:** Often missing the `op=13` branch — verify a validation fixture passes through the handler and returns `{plain_token, signature}`
- [ ] **Passive reply window:** Often missing the 5min/60min deadline check — verify a test simulates a late reply and asserts refusal with `qqbot_passive_reply_window_expired`
- [ ] **`msg_seq` tracking:** Often missing the sequence increment for multi-part replies — verify duplicate `msg_id + msg_seq` is detected and incremented
- [ ] **Feedback card → keyboard mapping:** Often a WeCom `template_card` copy — verify the QQ Bot envelope contains `keyboard`, not `template_card`
- [ ] **`INTERACTION_CREATE` normalization:** Often not mapped to `FeedbackEvent` — verify a button callback produces `FeedbackEvent(source="card_button")`
- [ ] **Access token refresh:** Often a one-time fetch with no expiry handling — verify the token is refreshed before `expires_in` and the old token's 60s overlap is handled
- [ ] **WebSocket Resume:** Often missing `s` persistence — verify a disconnect test replays missed events via `Opcode 6 Resume`
- [ ] **Scene-aware conversation key:** Often `user_openid` alone — verify C2C and group messages from the same user produce different `conversation_id` values
- [ ] **Credential redaction in evidence:** Often raw tokens in evidence files — verify a scan test finds no token patterns in any smoke-test evidence fixture
- [ ] **Receive mode config:** Often no `receive_mode` field — verify `from_env` reads `INKSTATUTE_QQBOT_RECEIVE_MODE` and the adapter branches on it
- [ ] **Output boundary on markdown/ark:** Often only applied to text — verify `apply_output_policy` runs on markdown body and keyboard button labels
- [ ] **No `wecom_service` import:** Often a sneaky import for "reuse" — verify `test_no_wecom_import.py` stays green
- [ ] **Contract freeze:** Often a Protocol "improvement" — verify `test_contract_freeze_not_violated.py` (6 methods, 4 FeedbackSource values) stays green
- [ ] **Feature flag default:** Often flipped to `True` for testing — verify `qqbot_channel_enabled` defaults `False` and the smoke-test explicitly enables it

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong signature verifier (SHA-1 instead of Ed25519) | MEDIUM | Replace verifier; re-register callback URL (platform re-sends validation); rotate `BotSecret` if any forged callbacks were processed; audit contract events for injected turns |
| Missing callback validation handshake | LOW | Add `op=13` branch; re-register callback URL in console; validation request re-arrives |
| Passive reply window expiry in production | MEDIUM | Add deadline check + interim notice; re-send failed answers as active messages (if user hasn't disabled); add monitoring for `304027` errors |
| WeCom `template_card` sent to QQ Bot API | LOW | Replace with keyboard envelope; no data corruption (API rejected the payload); re-dispatch feedback cards |
| Frozen Protocol modified (7 methods) | HIGH | Revert Protocol change; move QQ-specific logic into adapter internals; re-run all 24 gates; re-audit affected milestone; if shipped, treat as contract evolution with version bump |
| `access_token` leaked into logs/repo | HIGH | Rotate `clientSecret` immediately (platform console); purge logs/artifacts with token; scan git history; add redaction test; notify security if repo is shared |
| WebSocket events lost (no Resume) | MEDIUM | Implement Resume with `s` persistence; for already-lost events, no recovery (users must re-send); add reconnect test |
| Session collision across QQ scenes | MEDIUM | Redefine conversation key derivation; migrate existing session state (if any) to new keys; test cross-scene isolation |
| Non-reproducible smoke-test | LOW | Parameterize all inputs; redact evidence; add `--dry-run`; re-run and verify pass/fail is stable |
| Receive mode mismatch (webhook configured, adapter on WebSocket) | LOW | Align `INKSTATUTE_QQBOT_RECEIVE_MODE` with console config; restart adapter; no data loss (events queue on the platform side briefly) |

## Pitfall-to-Phase Mapping

How v1.8 phases should address these pitfalls. Phase numbering continues from v1.7 (next = 58).

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Wrong signature verifier (Ed25519 vs SHA-1) | QQ Bot ingress phase | Test passes with official QQ Bot demo vectors; verifier reads raw body bytes |
| Missing callback validation handshake (op=13) | QQ Bot ingress phase | `op=13` fixture returns `{plain_token, signature}`; URL registration succeeds in staging |
| Passive reply window expiry | QQ Bot egress phase | Late-reply test refuses with `qqbot_passive_reply_window_expired`; interim notice sent within window |
| WeCom template_card reused for QQ Bot | QQ Bot feedback parity phase | QQ Bot card envelope contains `keyboard`, not `template_card`; `INTERACTION_CREATE` normalizes to `FeedbackEvent` |
| Frozen Protocol modified | Pre-implementation safety phase | `test_contract_freeze_not_violated.py` green (6 methods, 4 FeedbackSource values); no Protocol PR in milestone |
| Access token / credential leakage | Pre-implementation safety phase + smoke-test phase | No token patterns in any metadata/evidence/log; `_reject_unsafe_keys` extended to QQ Bot fields; redaction test green |
| Receive mode mutual exclusivity | QQ Bot ingress phase | `QQBotChannelConfig.receive_mode` read from env; adapter branches; runbook documents exclusivity |
| Session collision across QQ scenes | Runtime session continuity phase | C2C + group + channel from same user produce distinct `conversation_id`; interrupt resume stays scene-scoped |
| Non-reproducible smoke-test | Smoke-test toolkit phase | `--dry-run` passes in CI without credentials; live run pass/fail stable across operators; evidence redacted |
| WebSocket events lost (no Resume) | QQ Bot ingress phase (WebSocket transport) | Disconnect test replays events `s=6,7,8` via `Opcode 6 Resume`; `s` persisted durably |

## Sources

- QQ Bot official docs — 安全和授权 (Ed25519 signature verification, BotSecret seed derivation, demo vectors): https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html
- QQ Bot official docs — 事件订阅与通知 (Webhook vs WebSocket mutual exclusivity, allowed ports 80/443/8080/8443, op=13 validation handshake, Opcode 6 Resume): https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html
- QQ Bot official docs — 接口调用与鉴权 (AppAccessToken, 7200s expiry, 60s overlap, Authorization header format): https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html
- QQ Bot official docs — 发送消息 (passive vs active messages, msg_id/msg_seq dedupe, 60min/5min reply windows, 4/5 reply caps, monthly active limits, msg_type 0/2/3/4/7, keyboard object): https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html
- QQ Bot official docs — openapi 错误 (error codes 304026 MSG_ID error, 304027 MSG_EXPIRE, 20028 ChannelHitWriteRateLimit, 22009 msg limit exceed, 429 rate limit, 504000-504999 frequency errors): https://bot.q.qq.com/wiki/develop/api-v2/openapi/error/error.html
- QQ Bot official docs — ARK 消息 (ark template structure, app/view/ver/meta fields): https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/ark.html
- QQ Bot official docs — 基础消息对话 (@-bot trigger, / command panel): https://bot.q.qq.com/wiki/develop/api-v2/client-func/intro/baseinfo.html
- Community adapter — YougLin-dev/adapter-qq-bot (webhook signature verification, op=13 validation, WebSocket gateway, scene-specific send APIs, keyboard callbacks): https://github.com/YougLin-dev/adapter-qq-bot
- Community adapter — bubbuild/bub-contrib (receive mode mutual exclusivity, BUB_QQ_RECEIVE_MODE, validation flow): https://github.com/bubbuild/bub-contrib/blob/main/packages/bub-qq/README.md
- Existing codebase — WeCom reference: `services/wecom-service/src/wecom_service/protocol.py` (SHA-1 signature), `sender.py` (template_card), `session_runtime.py` (session resolution), `normalization.py` (callback normalization), `ingress_runtime.py` (runtime ingress, `_reject_unsafe_keys`)
- Existing codebase — channel-core: `packages/channel-core/src/channel_core/idempotency.py`, `output_policy.py`, `delivery_guard.py`, `active_task_router.py`
- Existing codebase — QQBot fixture adapter: `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `config.py`
- Existing codebase — freeze tests: `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py`, `test_no_wecom_import.py`
- Project context: `.planning/PROJECT.md` (v1.8 milestone goals, safety constraints, frozen Protocol, 24 gates)

---
*Pitfalls research for: v1.8 QQBot Channel Production — real QQ Bot platform ingress/egress, feedback loop parity, runtime session continuity, smoke-test toolkit*
*Researched: 2026-07-07*
