# Phase 95 — Bot Channel Degradation: Discussion Log

**Mode:** Auto (--auto)
**Date:** 2026-08-09
**Requirements:** BOT-01, BOT-02, BOT-03
**Depends on:** Phase 91 (Unified Gateway — complete)

---

## Gray Area Analysis

10 gray areas identified, all auto-selected with recommended options.

---

### Gray Area 1: Event degradation layer location

**Question:** Where does the event degradation aggregator live in the bot service flow? Should it be a new shared package, a module in each service, or inline in the webhook handler?

**Options:**
- A) New shared package `packages/bot-degradation-consumer` — shared consumer logic
- B) New `event_consumer.py` module in each bot service — service-specific consumption + delivery mapping
- C) Inline in webhook handler's `run_post_ack_composition()` — minimal new files

**Auto-selected: B — New `event_consumer.py` module in each bot service**

**Rationale:** The degradation *rules* already live in `packages/platform-contract/bot_degradation.py` (Phase 88, EVT-05 complete) as the pure function `aggregate_events()`. What's needed is a *consumer* that:
1. Collects events from the Gateway SSE stream
2. Calls `aggregate_events()` at terminal state
3. Maps the `BotDelivery` result to channel-specific `ChannelDelivery` calls

WeCom template cards and QQ feedback keyboards have different envelope shapes, so the delivery mapping is inherently service-specific. A shared package would require abstraction over two different card formats with no reuse benefit. A per-service module keeps the existing module structure and test isolation while leveraging the shared degradation rules from the contract package.

---

### Gray Area 2: Gateway consumption mechanism

**Question:** How do bot services consume the Gateway event stream? SSE long-poll, HTTP polling, or webhook callback from Gateway?

**Options:**
- A) SSE long-poll — HTTP client opens `GET /v1/runs/{id}/events` and reads frames as they arrive
- B) HTTP polling — periodically `GET /v1/runs/{id}` to check status, then fetch events
- C) Gateway webhook callback — Gateway pushes events to a bot service webhook

**Auto-selected: A — SSE long-poll (HTTP client consuming SSE stream)**

**Rationale:** The Gateway already provides `GET /v1/runs/{id}/events` as an SSE stream with `Last-Event-ID` replay (GW-02 complete). This is the natural consumption pattern:
- The stream is live — events arrive as they're produced, no polling delay
- `Last-Event-ID` handles reconnection without duplicates
- The stream ends at terminal state — the consumer knows when to aggregate and deliver
- No additional Gateway endpoint or push mechanism needed
- For single-firm scale (≤50 lawyers), a blocking HTTP client on a daemon thread matches the existing `post_ack_scheduler` pattern

Polling (B) adds latency and complexity. Webhook callback (C) requires a new Gateway→bot push mechanism that doesn't exist and would add a reverse-dependency.

---

### Gray Area 3: Run creation via Gateway

**Question:** How do bot services create runs? Direct HTTP POST to Gateway, or keep runtime injection but route through a Gateway shim?

**Options:**
- A) HTTP POST to `POST /v1/runs` with Bearer token — bot service is a pure Gateway client
- B) Keep `DefaultRunRuntime` injection but add a Gateway routing shim — runtime calls go through Gateway
- C) In-process Gateway call — bot service imports Gateway app and calls `dispatch()` directly

**Auto-selected: A — HTTP POST to /v1/runs with Bearer token auth**

**Rationale:** BOT-02 explicitly requires "源码中不再存在直接的 agent/backend 调用". Option B keeps a runtime in the process, which is a direct agent call. Option C creates a circular dependency (bot service imports Gateway, Gateway imports runtime). Option A is the clean Gateway consumer pattern:
- Bot service constructs `turn` payload from normalized inbound callback
- HTTP `POST /v1/runs` with Bearer token → returns `run_id`
- HTTP `GET /v1/runs/{id}/events` (SSE) → collect events
- `aggregate_events()` → `adapter.deliver()`

The `turn` payload is built from the existing `normalize_inbound()` → `AgentTurn` → serialize to dict. The `solution` binding is configured per bot instance (fixed `solution_id` + `backend_id`).

---

### Gray Area 4: Template card mapping

**Question:** How do `elicitation.requested` and `permission.requested` events map to WeCom template cards and QQ feedback keyboards?

**Options:**
- A) Map `BotDelivery.cards` to channel-specific card envelopes via delivery metadata
- B) Send cards as plain text with link to web UI
- C) Send cards as markdown with inline buttons

**Auto-selected: A — Map BotDelivery.cards to channel-specific card envelopes**

**Rationale:** Both channel adapters already have card delivery support:
- WeCom: `build_template_card_envelope()` in `sender.py` → `adapter.deliver()` with `delivery_type="card"`
- QQ: `build_feedback_keyboard_envelope()` in `sender.py` → `adapter.deliver()` with `delivery_type="card"`

The `aggregate_events()` function collects `elicitation.requested` and `permission.requested` payloads into `BotDelivery.cards`. The event consumer maps each card payload to the channel-specific card fields:
- `interrupt_id` → `feedback_target` (WeCom) / keyboard callback (QQ)
- `questions` → card title/body text
- `permission_id` → approval card

Option B loses the interactive card UX. Option C is not supported by WeCom (no markdown buttons).

---

### Gray Area 5: Media/artifact delivery

**Question:** How are artifacts (docx files, etc.) delivered via bot channels?

**Options:**
- A) Download from Gateway `/v1/artifacts/{id}`, upload to channel media API, deliver via adapter
- B) Send a Gateway download link as text message
- C) Gateway pushes artifact directly to channel

**Auto-selected: A — Download from Gateway, upload to channel media, deliver via adapter**

**Rationale:** The existing `WeComChannelAdapter.deliver()` handles `delivery_type="file"` with `media_id` metadata (adapter.py line 112-114). The QQ adapter handles `delivery_type in {"file", "image"}` via `_deliver_rich_media()`. The consumer:
1. Downloads artifact content from `GET /v1/artifacts/{id}` (Gateway, auth required)
2. For WeCom: uploads to WeCom media API → gets `media_id` → `adapter.deliver()` with `delivery_type="file"`, `media_id` in metadata
3. For QQ: `adapter.deliver()` with `delivery_type="file"` and artifact reference

Option B gives a link that expires and requires the lawyer to leave WeCom/QQ. Option C requires a new Gateway→channel push mechanism. The media upload step requires network IO (currently stubbed); the consumer delegates to an injectable media uploader to keep the fixture CI path working.

---

### Gray Area 6: Intermediate push behavior

**Question:** How many "仍在处理" intermediate messages should be sent? At what interval? What content?

**Options:**
- A) Use existing `task_flow.py` `progress_interval_seconds` (180s) for timing
- B) Send only the degradation-rule prompts (first plan/phase → "仍在处理", first tool_call → "正在检索法规…")
- C) Send a fixed number (e.g., 3) at fixed intervals

**Auto-selected: A — Use existing task_flow progress_interval_seconds (180s)**

**Rationale:** The existing `task_flow.py` has `progress_interval_seconds=180.0` and `progress_notice_due()` logic that has been in production. The consumer:
1. Sends "仍在处理" when the first `plan.updated` or `phase.changed` arrives (FIRST_THEN_SILENT rule)
2. Sends "正在检索法规…" when the first `tool_call.*` arrives (FOLD rule)
3. Sends additional "仍在处理" at 180-second intervals if the run is still active (leveraging task_flow timing)
4. Sends the final aggregated message at terminal state

This preserves the existing WeCom progress notice UX (180s interval) while adapting it to the event stream model. Option B gives too few prompts for long-running tasks. Option C is arbitrary.

---

### Gray Area 7: Idempotency & retry

**Question:** How to handle bot message delivery retries and deduplication across Gateway consumption?

**Options:**
- A) Existing channel idempotency + Gateway seq-based event dedup
- B) New dedup layer with persistent message store
- C) No retry — fire and forget

**Auto-selected: A — Existing channel idempotency + Gateway seq-based event dedup**

**Rationale:** Two layers of idempotency already exist:
1. **Inbound:** `wecom_idempotency_key` / `channel_idempotency_key` dedup in the webhook handler — preserved unchanged
2. **Outbound:** Gateway SSE `seq`-based ordering + `Last-Event-ID` replay — no duplicates on reconnect

The `aggregate_events()` function is pure and deterministic — same events always produce the same `BotDelivery`. For delivery retry: if `adapter.deliver()` returns `accepted=False`, retry with exponential backoff (3 attempts), then log. The `delivery_id` is derived from `run_id` + delivery index for natural dedup.

Option B adds a persistent store for single-firm scale where it's unnecessary. Option C risks message loss.

---

### Gray Area 8: Existing behavior preservation

**Question:** How to ensure 5s ACK, AES-CBC, ED25519, op=13, media upload/download, idempotency, and retry don't regress?

**Options:**
- A) Keep webhook/verify_and_ack/adapter intact; replace only post-ACK composition's agent call path
- B) Rewrite the entire webhook handler with new architecture
- C) Keep everything and add Gateway consumer as a parallel path

**Auto-selected: A — Preserve webhook + verify_and_ack + adapter; replace only post-ACK composition**

**Rationale:** The critical preservation targets are in the webhook → verify_and_ack → adapter path, which is completely independent of how runs are created and results are fetched. By replacing only the post-ACK composition's agent call path:
- `webhook.py` → **unchanged** (ACK-first, 5s deadline, post-ACK scheduling)
- `adapter.verify_and_ack()` → **unchanged** (AES-CBC / ED25519 / op=13)
- `adapter.normalize_inbound()` → **unchanged** (callback → AgentTurn)
- `adapter.deliver()` → **unchanged** (send envelopes)
- `sender.py` / `signature.py` / `protocol.py` → **unchanged**
- `http_server.py` → **unchanged**

The **only** change is in `run_post_ack_composition()` and `wiring.py`:
- Old: `ingress_runtime` → `session_runtime` → `runtime.create_run()` / `backend.get_run()`
- New: `event_consumer` → `gateway_client` → `aggregate_events()` → `adapter.deliver()`

All existing tests that don't depend on direct runtime calls remain green. Tests that do depend on runtime calls (e.g., `test_agent_backend.py`, `test_session_runtime.py`) are updated to test the new path or marked as testing the old (preserved but unused) modules.

---

### Gray Area 9: Bot → Gateway auth

**Question:** How do bot services authenticate with the Gateway?

**Options:**
- A) Pre-configured Bearer token per bot instance (secret ref)
- B) Session cookie (bot logs in via /v1/auth/login)
- C) No auth (Gateway allows bot services without auth)

**Auto-selected: A — Pre-configured Bearer token per bot instance**

**Rationale:** The Gateway already supports Bearer token auth for bot/programmatic access (GW-03 complete). `resolve_identity()` tries Bearer token first. Each bot service uses a pre-configured Bearer token:
- Stored as a secret ref (e.g., `wecom_gateway_token_ref`, `qqbot_gateway_token_ref`)
- Resolved via `resolve_secret_ref()` (QQ) or env (WeCom) — existing pattern
- Token has `role=LAWYER` and fixed `tenant_id` for the bot's tenant
- No secrets in code, resolved at process edge (AGENTS.md safety rule)

Option B requires login flow management for a service. Option C violates the Gateway's auth requirement.

---

### Gray Area 10: Session management

**Question:** How do bot services manage sessions via the Gateway?

**Options:**
- A) Create or reuse Gateway session per WeCom/QQ conversation_id
- B) Create a new session per run (no session reuse)
- C) No session management (Gateway handles it implicitly)

**Auto-selected: A — Create or reuse Gateway session per conversation_id**

**Rationale:** The Gateway provides `POST /v1/sessions` to create sessions. The bot service maps the channel `conversation_id` to a Gateway session:
1. First message from a conversation: `POST /v1/sessions` with `conversation_id` → store `session_id` in memory
2. Subsequent messages: reuse `session_id` in `POST /v1/runs` body
3. Session mapping is in-memory (single-firm scale)

This preserves the existing session resolution behavior (continue vs new session, interrupt resume) while routing through the Gateway. The existing `SessionResolutionPolicy` logic in `session_runtime.py` is replaced by Gateway session management — the Gateway's `RunRuntime` handles session-based run creation.

Option B loses conversation context. Option C doesn't work — the Gateway requires a `session_id` in run creation.

---

## Summary

| # | Gray Area | Selection |
|---|-----------|-----------|
| 1 | Event degradation layer location | New `event_consumer.py` per service |
| 2 | Gateway consumption mechanism | SSE long-poll (HTTP client) |
| 3 | Run creation via Gateway | HTTP POST to /v1/runs with Bearer token |
| 4 | Template card mapping | Map BotDelivery.cards to channel-specific envelopes |
| 5 | Media/artifact delivery | Download from Gateway, upload to channel media API |
| 6 | Intermediate push behavior | Existing task_flow 180s interval + degradation prompts |
| 7 | Idempotency & retry | Existing channel idempotency + Gateway seq dedup |
| 8 | Existing behavior preservation | Replace only post-ACK composition; keep webhook/adapter intact |
| 9 | Bot → Gateway auth | Pre-configured Bearer token per bot instance |
| 10 | Session management | Create/reuse Gateway session per conversation_id |

All selections are the recommended options. No user override needed (--auto mode).
