---
phase: 95
researcher: gsd-phase-researcher
date: 2026-08-09
status: complete
---

# Phase 95 Research: Bot Channel Degradation

## Executive Summary

Phase 95 transforms `services/wecom-service` and `services/qqbot-service` from direct agent-runtime callers into Gateway event-stream consumers. The existing `bot_degradation.py` pure-function aggregator from Phase 88 (`packages/platform-contract`) already declares all 13 event-type degradation rules and produces a deterministic `BotDelivery`. The task is to wire bot services to consume Gateway SSE (`GET /v1/runs/{id}/events`), feed collected events to `aggregate_events()`, and map the resulting `BotDelivery` to channel-specific `ChannelDelivery` calls — all while preserving every piece of production behavior: WeCom 5-second ACK / AES-CBC signature verification / template cards / media delivery / idempotency, and QQ ED25519 verification / op=13 validation challenge / interaction ACK / passive-reply window / wakeup / idempotency.

The critical architectural insight is that the **webhook → verify_and_ack → post-ACK scheduler** pattern is completely preserved. Only the **post-ACK composition path** changes: the old `ingress_runtime → session_runtime → runtime.create_run() / backend.get_run()` chain is replaced by `gateway_client → POST /v1/runs → GET /v1/runs/{id}/events (SSE) → aggregate_events() → adapter.deliver()`.

---

## 1. WeCom Service Inventory

**Location:** `services/wecom-service/`
**Source:** `src/wecom_service/` — 21 Python files, 3,283 total lines
**Tests:** `tests/` — 18 test files
**Dependencies (pyproject.toml):** `inkstatute-channels-wecom`, `inkstatute-operator-config`, `inkstatute-platform-runtime`

### Source File Inventory

| File | Lines | Role | Direct agent call? |
|------|-------|------|-------------------|
| `session_runtime.py` | 853 | `WeComSessionRuntime`: session resolution, interrupt resume, `runtime.create_run()` / `runtime.resume_interrupt()` | **Yes — lines 242, 314** |
| `webhook.py` | 297 | ACK-first webhook handler; schedules post-ACK composition; `backend.get_run()` at line 166-168 | **Yes — line 166** |
| `task_flow.py` | 341 | WeCom task stages (received→...→completed), progress notices (180s interval), `TaskFlow` dataclass | No |
| `ingress_runtime.py` | 245 | `WeComRuntimeIngress`: callback → AgentTurn → RunRequest → session_runtime | No (delegates) |
| `normalization.py` | 224 | `normalize_wecom_turn`, `normalize_wecom_feedback_callback` — callback → AgentTurn/FeedbackEvent dict | No |
| `http_server.py` | 222 | stdlib `WeComWebhookServer` (BaseHTTPRequestHandler), `read_request_body_once`, `default_post_ack_scheduler` | No |
| `__main__.py` | 128 | Runnable entry point: `python -m wecom_service [--host] [--port]`, default port 8082 | No |
| `runtime_audit.py` | 103 | Runtime audit trail | No |
| `agent_backend.py` | 105 | `select_agent_backend`: selects agent backend manifest (Hermes mode), validates `no_channel_io` capability | No |
| `__init__.py` | 118 | Package exports | No |
| `memory_integration.py` | 127 | `MemoryIntegrationPolicy`, `recall_for_turn`, `retain_turn_memory` | No |
| `channel_wiring.py` | 77 | `load_wecom_channel_config`, `build_wecom_channel_config` — dual-knob AND (flag + doc) | No |
| `wiring.py` | 85 | `build_wecom_wired_runtime`: composes adapter + `DefaultRunRuntime` with backend | Injects backend |
| `sender.py` | 82 | `build_text_send_envelope`, `build_file_send_envelope`, `build_template_card_envelope` | No |
| `protocol.py` | 132 | `verify_callback_signature` (SHA1 digest), `parse_callback_envelope`, `ack_response` ("success") | No |
| `memory_factory.py` | 58 | Memory factory for session runtime | No |
| `active_task_router.py` | 38 | `route_active_task_turn` for follow-up messages | No |
| `output_policy.py` | 18 | Thin shim over `channel_core.output_policy.apply_output_policy` | No |
| `idempotency.py` | 16 | `wecom_idempotency_key` — thin shim over `channel_core.idempotency.channel_idempotency_key` | No |
| `delivery_guard.py` | 7 | Thin shim over `channel_core.delivery_guard` | No |
| `owned_notices.py` | 7 | Thin shim over `channel_core.owned_notices` | No |

### Test File Inventory (18 files)

| Test File | Covers |
|-----------|--------|
| `test_webhook.py` | Webhook ACK-first handling, post-ACK composition |
| `test_ingress_runtime.py` | WeComRuntimeIngress callback → RunRequest |
| `test_session_interrupt_runtime.py` | Interrupt resume, expiry, duplicate answer |
| `test_session_memory_runtime.py` | Memory recall/retain in session runtime |
| `test_task_flow.py` | Task stages, progress notices, deadline |
| `test_agent_backend.py` | Agent backend manifest selection |
| `test_protocol.py` | Signature verification, callback parsing |
| `test_normalization.py` | Turn/feedback normalization |
| `test_http_server.py` | HTTP server body reading, response writing |
| `test_wecom_wiring.py` | Runtime composition, dual-knob config |
| `test_channel_wiring_dual_knob.py` | Dual-knob AND enablement |
| `test_output_policy.py` | Output policy classification |
| `test_delivery_guard.py` | Delivery completion assessment |
| `test_runtime_audit.py` | Runtime audit trail |
| `test_ingress_memory_runtime.py` | Memory integration in ingress |
| `test_ingress_memory_wiring.py` | Memory wiring in ingress |
| `test_channel_wiring_dual_knob.py` | Channel config dual-knob |
| `__init__.py` | (empty) |

### Current Flow (to be replaced in post-ACK composition only)

```
WeCom callback → webhook.handle_wecom_webhook_request()
  → adapter.verify_and_ack()           [5s ACK, SHA1 signature check]
  → post_ack_scheduler schedules run_post_ack_composition()
    → adapter.normalize_inbound()      [callback → AgentTurn]
    → WeComRuntimeIngress.handle_callback()
      → WeComSessionRuntime.handle_turn()
        → runtime.create_run()          ← DIRECT AGENT CALL (line 314)
        or runtime.resume_interrupt()   ← DIRECT AGENT CALL (line 242)
    → backend.get_run(run_id)           ← DIRECT AGENT CALL (line 166)
    → output_boundary.apply()
    → adapter.deliver()                 [text/file/card send envelope]
```

### What Must Be Preserved (BOT-03)

- **5-second ACK deadline:** `ack_deadline_ms=5000` in `WeComChannelAdapter.capabilities()` (`packages/channels/wecom/adapter.py:53`)
- **AES-CBC callback signature verification:** `verify_callback_signature()` in `protocol.py:15-27` (SHA1 digest of sorted [token, timestamp, nonce, encrypted_payload])
- **Template card delivery:** `build_template_card_envelope()` in `sender.py:42-64` — produces `msgtype: "template_card"` with `card_id`, `title`, `feedback_target`
- **Media upload/download:** `build_file_send_envelope()` in `sender.py:25-39` — produces `msgtype: "file"` with `media_id`; adapter handles `delivery_type="file"` with `media_id` metadata or `artifact_refs`
- **Idempotency:** `wecom_idempotency_key()` in `idempotency.py` (shim over `channel_core.idempotency.channel_idempotency_key`); `_outcome_by_idempotency_key` dict in `WeComSessionRuntime` (line 126)
- **Output policy:** `apply_output_policy()` in `output_policy.py` (shim over `channel_core.output_policy`)
- **All 18 test files must stay green**

---

## 2. QQ Bot Service Inventory

**Location:** `services/qqbot-service/`
**Source:** `src/qqbot_service/` — 7 Python files, 1,156 total lines
**Tests:** `tests/` — 13 test files
**Dependencies (pyproject.toml):** `[]` (zero — all deps via sys.path in `__main__.py`)

### Source File Inventory

| File | Lines | Role | Direct agent call? |
|------|-------|------|-------------------|
| `webhook.py` | 373 | ACK-first webhook handler; ED25519 verify via adapter; schedules post-ACK; `_resolve_reply_text()` → `backend.get_run()` | **Yes — lines 127-150** |
| `http_server.py` | 237 | stdlib `QQBotWebhookServer`, `read_request_body_once`, `default_post_ack_scheduler` | No |
| `wiring.py` | 169 | `build_qqbot_wired_runtime`: dual-knob mapping, live-IO injection (token_manager + transport) | Injects backend |
| `__main__.py` | 125 | Runnable entry point: `python -m qqbot_service`, default port 8080 | No |
| `config.py` | 116 | `QQBotHostConfig`, `load_qqbot_host_config` — secret refs only | No |
| `secrets.py` | 105 | `resolve_secret_ref`, `normalize_config_secret_ref` — process-edge secret resolution | No |
| `__init__.py` | 31 | Package exports | No |

### Test File Inventory (13 files)

| Test File | Covers |
|-----------|--------|
| `test_webhook_composition.py` | Post-ACK composition flow |
| `test_webhook_ack_first.py` | ACK-first pattern, 5s deadline |
| `test_webhook_http_raw_body.py` | Request body preservation for signature verify |
| `test_host_skeleton.py` | Host skeleton structure |
| `test_host_safety_baseline.py` | Safety baseline checks |
| `test_wiring_vision.py` | Vision resolver wiring |
| `test_wiring_flag_config.py` | Feature flag config |
| `test_wiring_disabled_refuse.py` | Disabled channel refusal |
| `test_runtime_registration.py` | Runtime registration |
| `test_store_apply.py` | Operator config store apply |
| `test_secret_refs.py` | Secret ref normalization/resolution |
| `test_no_wecom_import.py` | No WeCom imports cross-contamination |
| `test_main.py` | Main entry point |

### QQ Bot Channel Adapter Package (`packages/channels/qqbot/`)

**Source:** `src/inkstatute_channels_qqbot/` — 10 Python files
**Tests:** `tests/` — 23 test files (the "28 qqbot test files" in SC#4 = 13 service + 23 channel = 36 total, but the SC says "28" which likely counts a subset; all must stay green)

| File | Lines | Role |
|------|-------|------|
| `adapter.py` | 1218 | `QQBotChannelAdapter`: ED25519 verify, op=13 challenge, interaction ACK, passive reply window, wakeup, deliver (text/markdown/media/card) |
| `session_runtime.py` | 863 | `QQBotSessionRuntime`: session resolution, interrupt resume, `runtime.create_run()` / `runtime.resume_interrupt()` |
| `sender.py` | 1291 | Text/markdown/keyboard/media envelopes, passive reply window, wakeup quota, `MessageTransport` protocol, `FakeMessageTransport`, `SendError` |
| `normalization.py` | 430 | `parse_envelope`, `normalize_message_event`, `normalize_interaction_event` — QQ gateway {op, t, d} parsing |
| `ingress_runtime.py` | 307 | `QQBotRuntimeIngress`: gateway envelope → AgentTurn → RunRequest → session_runtime |
| `token_manager.py` | 194 | `TokenManager`: acquire, cache, auto-refresh, single-flight; `UrllibTokenTransport`, `FakeTokenTransport` |
| `signature.py` | 89 | `derive_seed`, `derive_keypair`, `verify_callback_signature`, `handle_validation_challenge` |
| `_ed25519.py` | 109 | Vendored Ed25519 from RFC 8032 §6.1 — pure Python, stdlib only |
| `feedback_ingress.py` | — | `handle_feedback_callback`, `ensure_interaction_ack` |
| `config.py` | — | `QQBotChannelConfig` |

### Current Flow (to be replaced in post-ACK composition only)

```
QQ callback → webhook.handle_qqbot_webhook_request()
  → adapter.verify_and_ack()           [ED25519 verify, op=13 challenge, interaction ACK]
  → post_ack_scheduler schedules run_post_ack_composition()
    → adapter.normalize_inbound()      [gateway envelope → AgentTurn]
    → QQBotRuntimeIngress.handle_callback()
      → QQBotSessionRuntime.handle_turn()
        → runtime.create_run()          ← DIRECT AGENT CALL (line 301)
        or runtime.resume_interrupt()   ← DIRECT AGENT CALL (line 244)
    → _resolve_reply_text() → backend.get_run()  ← DIRECT AGENT CALL (line 137)
    → output_boundary.apply()
    → adapter.deliver()                 [text/markdown/media/card send]
```

### What Must Be Preserved (BOT-03)

- **ED25519 signature verification:** `verify_callback_signature()` in `signature.py:50-72` — verifies `X-Signature-Ed25519` over `timestamp + request_body` using vendored Ed25519 (`_ed25519.py`, RFC 8032 §6.1)
- **op=13 validation challenge:** `handle_validation_challenge()` in `signature.py:75-89` — signs `event_ts + plain_token` with Ed25519, returns `{plain_token, signature}` response
- **Interaction ACK:** `ack_interaction()` in `sender.py` — Tier-2 PUT to QQ API with `code=0`; adapter handles `interaction_ack_required` metadata
- **Passive reply window:** `check_passive_reply_window()` in `sender.py:483-530` — C2C: 3600s / 4 replies; group: 300s / 5 replies; fail-closed for missing/unknown scene
- **Wakeup/recall:** `_deliver_wakeup()` in `adapter.py:484+` — C2C-only `is_wakeup` path with 30-day period quota (`WakeupPeriodStore`, `check_wakeup_quota()`)
- **Idempotency:** `channel_idempotency_key()` from `channel_core.idempotency`; `_outcome_by_idempotency_key` dict in `QQBotSessionRuntime` (line 129)
- **Webhook port constraints:** `__main__.py` binds to `127.0.0.1:8080` by default
- **All 13 qqbot-service test files + 23 qqbot channel test files must stay green**

---

## 3. Event Degradation Rules from Phase 88

**Location:** `packages/platform-contract/src/platform_contract/bot_degradation.py` (274 lines)
**Tests:** `packages/contract-test-suite/tests/test_bot_degradation.py` (306 lines)

### DegradationCategory Enum (8 categories)

```python
class DegradationCategory(StrEnum):
    SILENT = "silent"
    BUFFER = "buffer"
    DELIVER = "deliver"
    DISCARD = "discard"
    FOLD = "fold"
    FIRST_THEN_SILENT = "first_then_silent"
    ATTACH = "attach"
    ON_FAILURE = "on_failure"
```

### DEGRADATION_RULES (15 event type → 8 categories)

| Event Type | Category | Bot Behavior |
|------------|----------|-------------|
| `session.started` | SILENT | Drop entirely |
| `message.delta` | BUFFER | Accumulate `message_delta` / `payload.delta`, deliver on `message.completed` |
| `message.completed` | DELIVER | Set `final_message` from `payload.content` or buffered deltas; `delivered=True` |
| `thought.delta` | DISCARD | Drop (no business value for bots) |
| `tool_call.started` | FOLD | First → "正在检索法规…"; subsequent silent |
| `tool_call.delta` | FOLD | (same as above) |
| `tool_call.completed` | FOLD | (same as above) |
| `plan.updated` | FIRST_THEN_SILENT | First → "仍在处理"; subsequent silent |
| `phase.changed` | FIRST_THEN_SILENT | (same as above) |
| `elicitation.requested` | DELIVER | Append payload to `cards[]`; `delivered=True` |
| `permission.requested` | DELIVER | Append payload to `cards[]`; `delivered=True` |
| `artifact.created` | DELIVER | Append payload to `files[]`; `delivered=True` |
| `citation.recorded` | ATTACH | Extract `payload.citations[]` → append to final message |
| `run.state_changed` | ON_FAILURE | Only deliver if `payload.status == "failed"` → "处理失败…" |
| `error` | ON_FAILURE | Always deliver → "处理失败…" |

### Business-Prompt Templates (industry-neutral Chinese)

- `_TOOL_FOLD_PROMPT = "正在检索法规…"` (tool call fold)
- `_PLAN_FIRST_PROMPT = "仍在处理"` (plan/phase first occurrence)
- `_FAILURE_PROMPT = "处理失败，请稍后重试或联系管理员"` (failure)

### BotDelivery Dataclass (deterministic output)

```python
@dataclass(frozen=True, slots=True)
class BotDelivery:
    final_message: str | None = None
    intermediate_prompts: list[str] = field(default_factory=list)
    cards: list[JsonObject] = field(default_factory=list)
    files: list[JsonObject] = field(default_factory=list)
    citations: list[JsonObject] = field(default_factory=list)
    error_prompt: str | None = None
    delivered: bool = False
```

### aggregate_events() — Pure Function

- **Input:** `list[dict]` — each dict is a serialized `RunEvent` with `event_type`, `seq`, optional `payload`, `message_delta`, `error`
- **Processing:** Sorts by `seq` ascending (handles out-of-order), iterates events, applies degradation rules
- **Output:** `BotDelivery` — deterministic, pure (no side effects, no time-dependent behavior)
- **Citation appending:** If `final_message` and `citations` both exist, `_append_citations()` formats a reference section

### How Each Event Type Degrades to Non-Streaming Bot Messages

1. **`session.started` → SILENT:** Dropped entirely. Bot users don't see session lifecycle.
2. **`message.delta` → BUFFER:** Each delta's text is accumulated in `buffer_parts[]`. Not delivered until `message.completed`.
3. **`message.completed` → DELIVER:** If `payload.content` exists, that becomes `final_message`. Otherwise, buffered deltas are joined. This is the primary "final reply" delivery.
4. **`thought.delta` → DISCARD:** Agent thinking is never shown to bot users (no business value).
5. **`tool_call.started/delta/completed` → FOLD:** First tool call produces "正在检索法规…" intermediate prompt. Subsequent tool calls are silent. This gives the user a signal that work is happening.
6. **`plan.updated` / `phase.changed` → FIRST_THEN_SILENT:** First plan/phase event produces "仍在处理" intermediate prompt. Subsequent are silent.
7. **`elicitation.requested` → DELIVER as card:** The payload (containing `interrupt_id`, `questions[]` with `id`/`question`/`allow_multiple`/`options[]`) is added to `cards[]`. The consumer maps this to a WeCom template card or QQ feedback keyboard.
8. **`permission.requested` → DELIVER as card:** The payload (containing `permission_id`, `description`) is added to `cards[]`. Mapped to an approval card.
9. **`artifact.created` → DELIVER as file:** The payload (containing `artifact_id`, `kind`, `name`, `uri`) is added to `files[]`. The consumer downloads from Gateway and delivers via channel media.
10. **`citation.recorded` → ATTACH:** Citations from `payload.citations[]` are collected. If a `final_message` exists, they're appended as a formatted reference section.
11. **`run.state_changed` → ON_FAILURE:** Only delivered if `payload.status == "failed"`. Produces "处理失败…" error prompt.
12. **`error` → ON_FAILURE:** Always produces "处理失败…" error prompt.

---

## 4. Gateway SSE Consumption

### Gateway API Endpoints (relevant to bot consumption)

**Location:** `services/gateway/src/gateway/app.py` (863 lines)

| Endpoint | Method | Operation | Bot Usage |
|----------|--------|-----------|-----------|
| `/v1/sessions` | POST | `create_session` | Create session per conversation |
| `/v1/sessions` | GET | `list_sessions` | (not needed by bots) |
| `/v1/sessions/{id}` | GET | `get_session` | (not needed by bots) |
| `/v1/sessions/{id}/runs` | GET | `list_session_runs` | (not needed by bots) |
| `/v1/runs` | POST | `create_run` | **Create run with turn + solution** |
| `/v1/runs/{id}` | GET | `get_run` | (optional — check run status) |
| `/v1/runs/{id}` | POST | `cancel_run` | (optional — cancel long runs) |
| `/v1/runs/{id}/events` | GET (SSE) | `stream_run` | **Consume event stream** |
| `/v1/runs/{id}/elicitation` | POST | `submit_elicitation` | **Submit clarification answer** |
| `/v1/runs/{id}/approvals` | POST | `submit_approval` | **Submit approval decision** |
| `/v1/artifacts/{id}` | GET | `get_artifact` | **Download artifact file** |
| `/v1/uploads` | POST | `upload` | (optional — upload attachments) |
| `/v1/feedback` | POST | `submit_feedback` | **Submit user feedback** |
| `/v1/skills` | GET | `list_skills` | (not needed by bots) |
| `/v1/auth/login` | POST | `login` | (bots use Bearer token, not login) |

### SSE Streaming (`GatewayApp.stream()`)

**Location:** `app.py:264-312`

- Auth applied BEFORE yielding any SSE frames: `ctx = self._auth.require_auth(headers)`
- `Last-Event-ID` header → `parse_last_event_id()` → replay buffered events with `seq > last_seq`
- `RunEventBuffer` (`event_buffer.py`): in-memory per-run, thread-safe, FIFO eviction at 1000 events, 5-minute terminal retention
- Output boundary enforced in `GatewaySseStream.encode_event()` — blocked events return `None` (skipped)
- Live events appended to buffer for future reconnections
- Stream naturally ends at terminal state (`run.state_changed` with succeeded/failed/cancelled)

### Run Creation (`_handle_create_run()`)

**Location:** `app.py:355-371`

- Requires `turn` (AgentTurn fields) + `solution` (SolutionBinding fields) in body
- Calls `runtime.create_run(run_request)` — returns serialized run with `run_id`
- `tenant_id` from auth context

### Auth for Bot Services

**Location:** `services/gateway/src/gateway/auth.py`

- `resolve_identity()` — Bearer token first (Authorization header), session cookie fallback
- Roles: ADMIN, OPERATOR, LAWYER, VIEWER
- Tenant isolation via `check_tenant()`
- Bot/programmatic access: Bearer token (per GW-03)
- Bot services use a pre-configured Bearer token with `role=LAWYER` and a fixed `tenant_id`

### SSE Encoding (`GatewaySseStream`)

**Location:** `services/gateway/src/gateway/sse.py` (172 lines)

- Uses `encode_sse_event` from `inkstatute_channels_web_sse` package
- `encode_event(event)` — applies `DefaultAssistantOutputBoundary` to text content, returns SSE frame string or `None` if blocked
- V3 event types mapped to V2 equivalents for boundary: `message.delta` → `message_delta`, `elicitation.requested` → `approval_requested`, etc.
- Unknown V3 types: text-based rules still apply (event-type filtering primarily at ACP bridge)

### Bot Consumption Pattern

The bot service event consumer should:
1. **POST `/v1/sessions`** — create or reuse session per `conversation_id`
2. **POST `/v1/runs`** — create run with normalized `turn` + `solution` binding, get `run_id`
3. **GET `/v1/runs/{id}/events`** (SSE) — open HTTP connection with Bearer token, read SSE frames
4. **Collect events** into a list as they arrive
5. **Send intermediate prompts** when `plan.updated`/`phase.changed`/`tool_call.*` events arrive (per degradation rules)
6. **When stream ends** (terminal state) — call `aggregate_events()` on collected list
7. **Map `BotDelivery`** to channel-specific `adapter.deliver()` calls:
   - `final_message` → `delivery_type="text"` with content
   - `intermediate_prompts` → `delivery_type="text"` (sent during stream, not after)
   - `cards` → `delivery_type="card"` with card-specific metadata
   - `files` → download from `/v1/artifacts/{id}`, then `delivery_type="file"`
   - `error_prompt` → `delivery_type="text"` with error message
8. **Submit elicitation/approval answers** via POST to `/v1/runs/{id}/elicitation` or `/v1/runs/{id}/approvals` when user responds to cards

### HTTP Client Approach

- Use stdlib `urllib.request` or `http.client` (no external dependencies, matching existing pattern)
- SSE consumption: open a long-lived HTTP connection, read line-by-line, parse `data: ...` frames
- For single-firm scale (≤50 lawyers), blocking HTTP client on a daemon thread (matching existing `post_ack_scheduler` pattern) is sufficient
- `Last-Event-ID` header for reconnection: if consumer disconnects mid-stream, reconnect with last `seq` to resume without duplicates

---

## 5. WeCom Template Cards

### Current Implementation

**`sender.py:42-64`** — `build_template_card_envelope()`:
```python
def build_template_card_envelope(*, to_user: str, card_id: str, title: str, feedback_target: str) -> dict:
    decision = apply_output_policy(title)
    envelope = _base_envelope(to_user, decision)
    if decision.action != "block":
        envelope.update({
            "msgtype": "template_card",
            "template_card": {
                "card_id": card_id,
                "title": decision.visible_text or title,
                "feedback_target": feedback_target,
            },
        })
    return envelope
```

### How Clarification/Approval Maps to Cards

The `WeComChannelAdapter.deliver()` method (`packages/channels/wecom/adapter.py:107-136`) handles `delivery_type="card"`:
```python
if delivery_type == "card":
    envelope = build_template_card_envelope(
        to_user=to_user,
        card_id=_required_string(delivery.metadata, "card_id"),
        title=content or "请评价本次回复",
        feedback_target=_feedback_target(delivery),
    )
```

**Mapping from `elicitation.requested` event to WeCom template card:**
- `BotDelivery.cards[i]` contains the elicitation payload: `interrupt_id`, `questions[]` (each with `id`, `question`, `allow_multiple`, `options[]`)
- The event consumer maps this to `ChannelDelivery` with:
  - `delivery_type="card"`
  - `content` = intro text or first question
  - `metadata.card_id` = derived from `interrupt_id`
  - `metadata.feedback_target` = `interrupt_id` (for correlating user response)
  - `metadata.to_user` = WeCom user_id from original callback

**Mapping from `permission.requested` event to WeCom template card:**
- `BotDelivery.cards[i]` contains: `permission_id`, `description`
- Mapped to `ChannelDelivery` with:
  - `delivery_type="card"`
  - `content` = permission description
  - `metadata.card_id` = derived from `permission_id`
  - `metadata.feedback_target` = `permission_id`

**Feedback cards (existing behavior):**
- WeCom feedback callbacks are detected by `_is_feedback_callback()` in `adapter.py:166-170` — checks for `feedback_target`, `FeedbackTarget`, `feedback_action`, `button_action` keys or `event_key` starting with `feedback:`
- `normalize_wecom_feedback_callback()` in `normalization.py:61-129` maps to `FeedbackEvent` with actions: `up`, `down`, `needs_fix`, `route_wrong`

---

## 6. WeCom Media Handling

### Current Implementation

**`sender.py:25-39`** — `build_file_send_envelope()`:
```python
def build_file_send_envelope(*, to_user: str, media_id: str, description: str | None = None) -> dict:
    decision = apply_output_policy(description or "InkStatute file delivery")
    envelope = _base_envelope(to_user, decision)
    if decision.action != "block":
        envelope.update({
            "msgtype": "file",
            "file": {"media_id": media_id},
        })
        if decision.visible_text:
            envelope["description"] = decision.visible_text
    return envelope
```

### How Artifacts Can Be Delivered

**`WeComChannelAdapter.deliver()`** (`adapter.py:107-136`) handles `delivery_type="file"`:
```python
if delivery_type == "file":
    media_id = _media_id(delivery)  # from metadata.media_id or artifact_refs[0]
    envelope = build_file_send_envelope(to_user=to_user, media_id=media_id, description=content)
```

**`_media_id()`** (`adapter.py:219-225`):
```python
def _media_id(delivery: ChannelDelivery) -> str:
    value = delivery.metadata.get("media_id")
    if value is not None:
        return _required_string(delivery.metadata, "media_id")
    if delivery.artifact_refs:
        return delivery.artifact_refs[0]
    raise ValueError("file delivery requires media_id metadata or artifact_refs")
```

**Artifact delivery flow (new):**
1. `artifact.created` event → `BotDelivery.files[i]` with `artifact_id`, `kind`, `name`, `uri`
2. Event consumer downloads artifact from `GET /v1/artifacts/{artifact_id}` (Gateway endpoint, Bearer auth)
3. Consumer uploads artifact to WeCom media API to get `media_id` (requires network IO — currently stubbed with `network_io=False`)
4. Consumer calls `adapter.deliver()` with `delivery_type="file"`, `metadata.media_id=media_id`, `metadata.to_user=user_id`

**Note:** The actual WeCom media upload API call requires network IO that is currently stubbed (`network_io=False` in capabilities). The consumer module should delegate media upload to an injectable media uploader, keeping the fixture CI path working. The `WeComChannelAdapter` capabilities declare `supports_files=True` but `network_io=False` — meaning the adapter builds the envelope but doesn't actually POST to WeCom API.

**Inbound media (user → bot):**
- `normalize_wecom_turn()` in `normalization.py:132-158` handles `message_type` in `{"file", "image", "voice"}` — extracts `media_ref` from callback, creates `AttachmentRef` with `uri=f"wecom-media://{media_ref}"`, `bytes_stored=False`, `source_status="media_reference_only"`

---

## 7. QQ Bot Message Format

### Current Send Envelope Types

**`sender.py`** (1291 lines) provides:

| Builder | msg_type | Usage |
|---------|----------|-------|
| `build_text_envelope()` | 0 | Plain text reply |
| `build_markdown_envelope()` | 2 | Markdown-formatted reply (group: companion `content=""`) |
| `build_feedback_keyboard_envelope()` | 2 | Markdown + keyboard with 4 feedback buttons (有帮助/需改进/需要修正/路由错误) |
| `build_media_envelope()` | 7 | Rich media from uploaded `file_info` |
| `build_wakeup_text_envelope()` | 0 | C2C wakeup text (no msg_id, `is_wakeup=True`) |
| `build_wakeup_markdown_envelope()` | 2 | C2C wakeup markdown |

### QQ Bot Delivery Path

**`QQBotChannelAdapter.deliver()`** (`adapter.py:312-482`):
- Checks passive reply window (`check_passive_reply_window()`) when `msg_id` is present
- If window expired and `is_wakeup`/`allow_wakeup` → `_deliver_wakeup()` path
- If window expired and no wakeup → returns `accepted=False` with `issue_code="qqbot_passive_reply_window_expired"`
- For `file`/`image` delivery types → `_deliver_rich_media()` (two-step: upload to QQ rich media API, then send msg_type=7)
- For `card` → `build_feedback_keyboard_envelope()`
- For `markdown` → `build_markdown_envelope()`
- For `text` (default) → `build_text_envelope()`
- Live send requires `self._live_io_ready()` (enabled + token_manager + transport)
- `send_message()` POSTs to QQ API with scene-specific URL (c2c vs group, user_openid vs group_openid)

### QQ Bot Card Mapping

**Mapping from `elicitation.requested` to QQ keyboard:**
- `BotDelivery.cards[i]` → `ChannelDelivery` with `delivery_type="card"`
- `adapter.deliver()` calls `build_feedback_keyboard_envelope()` with `title`, `feedback_target`, `msg_id`, `msg_seq`
- The keyboard has 4 buttons: `up` (有帮助), `down` (需改进), `needs_fix` (需要修正), `route_wrong` (路由错误)
- For clarification cards, the consumer may need a different keyboard layout with question-specific options (this may require extending the sender or using markdown with inline keyboard)

### QQ Bot Rich Media

**`_deliver_rich_media()`** in `adapter.py`:
- Two-step: (1) upload file to QQ rich media API via `send_rich_media()` to get `file_info`, (2) send msg_type=7 with `file_info`
- Handles transient QQ codes (11242, 11252, 11263, 304082, 304083) with bounded backoff
- Terminal QQ codes (304027, 304026, 22009, 50006, 304003) → no retry

---

## 8. Existing Test Coverage

### WeCom Tests (18 files in `services/wecom-service/tests/`)

All 18 test files must stay green. Key tests that exercise the post-ACK composition path (will be affected by changes):

- `test_webhook.py` — Tests `handle_wecom_webhook_request()` and `run_post_ack_composition()`. Directly tests the agent call path that will be replaced.
- `test_ingress_runtime.py` — Tests `WeComRuntimeIngress.handle_callback()`. The ingress runtime is kept but no longer called from post-ACK.
- `test_session_interrupt_runtime.py` — Tests interrupt resume/expiry/duplicate. Session runtime kept but not called from post-ACK.
- `test_session_memory_runtime.py` — Tests memory integration in session runtime.
- `test_task_flow.py` — Tests task stages and progress notices. Task flow is referenced by the new consumer for progress timing.
- `test_agent_backend.py` — Tests backend manifest selection. May need adjustment if backend is removed from wiring.
- `test_wecom_wiring.py` — Tests `build_wecom_wired_runtime()`. Will be modified to inject Gateway client instead of backend.
- `test_channel_wiring_dual_knob.py` — Tests dual-knob config. Should remain unaffected.

Tests that should be completely unaffected:
- `test_protocol.py`, `test_normalization.py`, `test_http_server.py`, `test_output_policy.py`, `test_delivery_guard.py`, `test_runtime_audit.py`, `test_ingress_memory_runtime.py`, `test_ingress_memory_wiring.py`

### QQ Bot Tests

**qqbot-service tests (13 files in `services/qqbot-service/tests/`):**

Key affected tests:
- `test_webhook_composition.py` — Tests `run_post_ack_composition()`. Directly tests the agent call path.
- `test_webhook_ack_first.py` — Tests ACK-first pattern. Should be unaffected (ACK path preserved).
- `test_webhook_http_raw_body.py` — Tests request body preservation. Should be unaffected.
- `test_wiring_vision.py`, `test_wiring_flag_config.py`, `test_wiring_disabled_refuse.py` — Test wiring. Will be modified.
- `test_runtime_registration.py` — Tests runtime registration. May need adjustment.
- `test_host_skeleton.py`, `test_host_safety_baseline.py` — Structure/safety tests.
- `test_no_wecom_import.py` — Cross-contamination check. Must remain green.
- `test_store_apply.py`, `test_secret_refs.py`, `test_main.py` — Config/secret/main tests. Should be unaffected.

**qqbot channel tests (23 files in `packages/channels/qqbot/tests/`):**

All 23 test files test the channel adapter package, which is **unchanged** in Phase 95:
- `test_adapter_normalize.py`, `test_adapter_real_io.py`, `test_adapter_two_tier_ack.py`
- `test_contract_freeze_not_violated.py`, `test_ed25519_vectors.py`, `test_feature_flag.py`
- `test_feedback_idempotency.py`, `test_feedback_pipeline.py`, `test_feedback_source_mapping.py`
- `test_ingress_runtime.py`, `test_no_wecom_import.py`, `test_normalization.py`
- `test_qqbot_channel_adapter.py`, `test_qqbot_channel_loop.py`, `test_qqbot_idempotency.py`
- `test_sender.py`, `test_session_memory_runtime.py`, `test_session_runtime.py`
- `test_signature.py`, `test_smoke_toolkit.py`, `test_token_manager.py`
- `test_v1_8_safety_baseline.py`, `test_wakeup_recall.py`

### Gate Coverage

The 28 gates (from Phase 88 research) include:
- Gate #2: `wecom-service` — runs pytest on `services/wecom-service/src/`
- Gate #18: `qqbot-channel` — runs pytest on `packages/channels/qqbot/src/`
- Gate #19: `qqbot-service` — runs pytest on `services/qqbot-service/src/`
- Gate #21: `wecom-channel` — runs pytest on `packages/channels/wecom/src/`

All 28 gates must remain green. New files (`event_consumer.py`, `gateway_client.py`) in `services/*/src/` are automatically covered by existing gates #2 and #19.

---

## 9. AES-CBC & ED25519 Crypto Implementations

### WeCom AES-CBC Signature Verification

**Location:** `services/wecom-service/src/wecom_service/protocol.py:15-27`

```python
def verify_callback_signature(
    token: str, timestamp: str, nonce: str, msg_signature: str, encrypted_payload: str,
) -> bool:
    digest = hashlib.sha1(
        "".join(sorted([token, timestamp, nonce, encrypted_payload])).encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(digest, msg_signature)
```

- Uses SHA1 digest of sorted concatenation of [token, timestamp, nonce, encrypted_payload]
- `hmac.compare_digest` for constant-time comparison
- This is the callback signature verification — the actual AES-CBC decryption of the payload would happen at the WeCom platform level (the service receives sanitized callbacks with `raw_payload_ref`)
- The `WeComChannelAdapter.verify_and_ack()` in `packages/channels/wecom/adapter.py:67-81` currently returns `signature_status: "secret_ref_required"` — meaning actual crypto is deferred to the live host with resolved secrets

**Preservation requirement:** The `protocol.py` file is **unchanged** in Phase 95. The `verify_callback_signature()` function and `parse_callback_envelope()` remain as-is.

### QQ Bot ED25519 Signature Verification

**Location:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` (89 lines) + `_ed25519.py` (109 lines)

**Key derivation (`signature.py:21-47`):**
```python
def derive_seed(bot_secret: str) -> bytes:
    seed = bot_secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]

def derive_keypair(bot_secret: str) -> tuple[bytes, bytes]:
    seed = derive_seed(bot_secret)
    public_key = secret_to_public(seed)
    return (public_key, seed)
```

**Signature verification (`signature.py:50-72`):**
```python
def verify_callback_signature(
    public_key: bytes, signature_hex: str, timestamp: str, body_bytes: bytes,
) -> bool:
    sig = bytes.fromhex(signature_hex)
    if len(sig) != 64:
        return False
    msg = timestamp.encode("utf-8") + body_bytes
    return verify(public_key, msg, sig)
```

**Validation challenge (`signature.py:75-89`):**
```python
def handle_validation_challenge(
    bot_secret: str, plain_token: str, event_ts: str,
) -> dict[str, str]:
    _, seed = derive_keypair(bot_secret)
    msg = (event_ts + plain_token).encode("utf-8")
    sig = sign(seed, msg)
    return {"plain_token": plain_token, "signature": sig.hex()}
```

**Vendored Ed25519 (`_ed25519.py`):**
- Pure Python implementation from RFC 8032 §6.1
- Uses only `hashlib.sha512` — no external crypto packages
- Functions: `secret_to_public()`, `sign()`, `verify()`
- Curve math, scalar clamping, point operations copied verbatim from RFC
- **Must not be modified**

**Preservation requirement:** Both `signature.py` and `_ed25519.py` are **unchanged** in Phase 95. The `QQBotChannelAdapter.verify_and_ack()` method that calls these functions is also unchanged.

---

## 10. Idempotency & Retry

### WeCom Idempotency

**Inbound (callback → run creation):**
- `wecom_idempotency_key()` in `idempotency.py` — thin shim over `channel_core.idempotency.channel_idempotency_key(callback, channel_prefix="wecom")`
- Uses callback metadata (message_id, conversation_id, user_id) to produce a stable SHA256-based key
- `WeComSessionRuntime._outcome_by_idempotency_key` dict (line 126) — caches outcomes by idempotency key; duplicate callbacks return the cached outcome with `DUPLICATE_ANSWER_IGNORED` action

**Outbound (delivery retry):**
- No explicit retry mechanism in the current WeCom service — delivery is fire-and-forget via `adapter.deliver()`
- The `post_ack_scheduler` runs on a daemon thread; if it fails, the error handler logs the exception type only
- `DeliveryResult.accepted` indicates success/failure but no retry loop

**Task flow idempotency:**
- `task_stage_idempotency_key()` in `task_flow.py:282-283` — `f"wecom-task:{task_id}:{stage}:{seq}"`
- Each task stage record has a unique idempotency key

### QQ Bot Idempotency

**Inbound (callback → run creation):**
- `channel_idempotency_key()` from `channel_core.idempotency` — used in `QQBotChannelAdapter.normalize_inbound()` (line 296, 307)
- `QQBotSessionRuntime._outcome_by_idempotency_key` dict (line 129) — same pattern as WeCom
- Feedback idempotency: `idempotency_key = f"{msg_id}:{button_identity}"` in `normalization.py:386`

**Outbound (delivery retry):**
- `send_message()` in `sender.py` has bounded backoff for transient failures: `_BACKOFF_SECONDS = (0.05, 0.1, 0.2)` — 3 retry attempts
- Transient QQ codes: `{11242, 11252, 11263, 304082, 304083}` → retry
- Transient HTTP statuses: `{429, 500, 504}` → retry
- Terminal QQ codes: `{304027, 304026, 22009, 50006, 304003}` → no retry
- Interaction ACK: QQ code 3 (duplicate) treated as non-fatal

**Wakeup quota idempotency:**
- `WakeupPeriodStore.try_reserve()` — atomic claim under lock; `release()` on failure; `commit()` on success
- 1 wakeup per (openid, period) within 30 days

### Gateway Event Seq Dedup (new in Phase 95)

- Gateway SSE provides `seq`-based ordering and `Last-Event-ID` replay
- If consumer disconnects and reconnects, it resumes from last `seq` without duplicates
- `aggregate_events()` is pure and deterministic — same events always produce the same `BotDelivery`
- `RunEventBuffer.replay(run_id, last_seq)` returns events with `seq > last_seq`, ordered by seq

### Two-Layer Idempotency Design (Phase 95)

1. **Inbound (callback → Gateway run creation):** Existing `wecom_idempotency_key` / `channel_idempotency_key` dedup is preserved. The webhook handler still checks idempotency before creating a Gateway run.
2. **Outbound (event consumption → delivery):** Gateway `seq`-based event dedup + `aggregate_events()` determinism. Delivery `delivery_id` derived from `run_id` + delivery index for natural dedup. Retry with exponential backoff up to 3 times on `adapter.deliver()` failure.

---

## 11. Wiring Changes Required

### WeCom Wiring (`services/wecom-service/src/wecom_service/wiring.py`)

**Current:** `build_wecom_wired_runtime()` composes:
- `WeComChannelAdapter` (from `inkstatute_channels_wecom`)
- `DefaultRunRuntime` with `backend` parameter (from `platform_runtime`)
- Vision resolver from operator config

**New:** Replace `DefaultRunRuntime` + `backend` with:
- `GatewayClient` config (base URL, Bearer token ref, tenant_id)
- The `WeComWiredRuntime` dataclass needs a `gateway_client` field instead of (or in addition to) `runtime`
- The `runtime` field may be kept for backward compat but the post-ACK composition no longer uses it

**`__main__.py` changes:**
- Currently uses `FakeBackendAdapter()` as default backend
- New: use a Gateway client config from env vars (e.g., `INKSTATUTE_GATEWAY_URL`, `INKSTATUTE_GATEWAY_BEARER_TOKEN_REF`)

### QQ Bot Wiring (`services/qqbot-service/src/qqbot_service/wiring.py`)

**Current:** `build_qqbot_wired_runtime()` composes:
- `QQBotChannelAdapter` with optional `token_manager` + `transport` (live IO)
- `DefaultRunRuntime` with `backend` parameter
- Vision resolver from operator config

**New:** Replace `DefaultRunRuntime` + `backend` with:
- `GatewayClient` config (base URL, Bearer token ref, tenant_id)
- The `QQBotWiredRuntime` dataclass needs a `gateway_client` field
- Live IO (token_manager, transport) for QQ API sends remains unchanged — it's needed for `adapter.deliver()` to actually POST messages to QQ

---

## 12. ChannelDelivery Protocol

**Location:** `packages/platform-runtime/src/platform_runtime/protocols.py:89-96`

```python
@dataclass(frozen=True, slots=True)
class ChannelDelivery:
    delivery_id: str
    channel_id: ChannelId  # "wecom" or "qqbot"
    run_id: RunId | None = None
    result: AgentResult | None = None
    content: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

**WeCom delivery metadata fields:**
- `delivery_type`: "text" | "file" | "card"
- `to_user`: WeCom user_id
- `media_id`: for file delivery
- `card_id`, `feedback_target`: for card delivery
- `received_at`, `reply_count`, `output_boundary`

**QQ Bot delivery metadata fields:**
- `delivery_type`: "text" | "markdown" | "card" | "file" | "image"
- `scene`: "c2c" | "group"
- `user_openid`, `group_openid`: scene-specific identifiers
- `msg_id`, `message_id`, `msg_seq`: for passive reply window
- `reply_count`, `received_at`
- `is_wakeup`, `allow_wakeup`: for wakeup path
- `output_boundary`

---

## 13. Output Boundary Double Enforcement

### First Enforcement: Gateway SSE

**Location:** `services/gateway/src/gateway/sse.py:36-57`

- `GatewaySseStream.encode_event()` applies `DefaultAssistantOutputBoundary` to each event's text content
- Events with blocked content return `None` (skipped, not yielded)
- V3 event types mapped to V2 equivalents for boundary checking
- Text-based rules apply even for unknown event types

### Second Enforcement: Bot Degradation Layer

- `SILENT` category: `session.started` dropped entirely
- `DISCARD` category: `thought.delta` dropped (agent thinking never reaches bots)
- `FOLD` category: `tool_call.*` collapsed to generic "正在检索法规…" — actual tool details never shown
- `ON_FAILURE` category: `run.state_changed` only delivered on failure — success state changes are silent

**SC#6 requirement:** Backend meta / gateway / system noise must be invisible in bot channels. The Gateway SSE already filters these (first enforcement). The degradation layer's SILENT/DISCARD/FOLD rules provide additional filtering (second enforcement). The existing `output_policy.py` / `apply_output_policy()` in each service provides a third layer at delivery time.

---

## 14. Session Management via Gateway

### Current Session Resolution (to be replaced)

**WeCom:** `WeComSessionRuntime.handle_turn()` in `session_runtime.py:128-328`:
- Checks idempotency key cache
- Checks pending interrupt (resume vs expire)
- Checks active task (follow-up routing)
- Calls `resolve_session_turn()` from `platform_runtime.session_resolver`
- Actions: `RESUME_INTERRUPT`, `ACTIVE_TASK_FOLLOW_UP`, `CONTINUE_SESSION`, `START_NEW_SESSION`

**QQ Bot:** `QQBotSessionRuntime.handle_turn()` in `session_runtime.py:131-315`:
- Same pattern as WeCom
- Additional: `SKIPPED_NON_MESSAGE` for non-message events

### New Session Management (via Gateway)

1. **First message from a conversation:** `POST /v1/sessions` with `conversation_id` → store `session_id` mapping
2. **Subsequent messages:** Reuse stored `session_id` in `POST /v1/runs` body
3. **Session mapping:** In-memory dict (single-firm scale) — `conversation_id → session_id`
4. **Interrupt resume:** When a user responds to an elicitation card, `POST /v1/runs/{id}/elicitation` with the answer — the Gateway routes this to the backend
5. **The existing `SessionResolutionPolicy` logic is replaced by Gateway session management** — the Gateway's `create_run` endpoint accepts an optional `session_id` for continuation

---

## Validation Architecture

### Required New Tests

1. **Event consumer tests** (`test_event_consumer.py` in each service):
   - Given a sequence of Gateway SSE events, `aggregate_events()` produces expected `BotDelivery`
   - `BotDelivery.final_message` → `adapter.deliver()` with `delivery_type="text"`
   - `BotDelivery.cards` → `adapter.deliver()` with `delivery_type="card"`
   - `BotDelivery.files` → artifact download + `adapter.deliver()` with `delivery_type="file"`
   - `BotDelivery.intermediate_prompts` → delivered during stream (not after)
   - `BotDelivery.error_prompt` → `adapter.deliver()` with error text
   - Citations appended to final message
   - Output boundary: blocked events don't produce deliveries

2. **Gateway client tests** (`test_gateway_client.py` in each service):
   - `POST /v1/sessions` → returns `session_id`
   - `POST /v1/runs` → returns `run_id`
   - `GET /v1/runs/{id}/events` (SSE) → yields events
   - `Last-Event-ID` reconnection → resumes from correct seq
   - `POST /v1/runs/{id}/elicitation` → submits answer
   - `GET /v1/artifacts/{id}` → downloads artifact
   - Bearer token auth
   - Error handling (Gateway unavailable, 401, 404, 500)

3. **Integration tests:**
   - Full flow: webhook → verify_and_ack → post-ACK → Gateway client → SSE → aggregate → deliver
   - Same task from WeCom → final result semantically consistent with Web
   - Backend noise invisible in bot deliveries
   - Idempotency: duplicate callback → no duplicate Gateway run
   - Reconnection: SSE disconnect → reconnect → no duplicate deliveries

4. **Existing tests that must stay green:**
   - All 18 WeCom service tests
   - All 13 QQ bot service tests
   - All 23 QQ bot channel tests
   - All 2 WeCom channel tests
   - All 28 gates (especially #2 wecom-service, #18 qqbot-channel, #19 qqbot-service, #21 wecom-channel)

### Test Placement

- Event consumer tests → `services/wecom-service/tests/test_event_consumer.py` (gate #2)
- Gateway client tests → `services/wecom-service/tests/test_gateway_client.py` (gate #2)
- Same for QQ bot → `services/qqbot-service/tests/` (gate #19)
- Degradation integration tests → extend existing `test_webhook_composition.py` or new `test_event_consumer.py`

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `runtime.create_run()` breaks session/interrupt tests | High | Keep `session_runtime.py` and `ingress_runtime.py` as-is (not deleted); only the post-ACK composition path stops calling them |
| Gateway SSE consumer blocks post-ACK daemon thread | Medium | Use async consumption or timeout-based reads; the existing `post_ack_scheduler` already runs on a daemon thread |
| WeCom media upload requires network IO not currently implemented | Medium | Delegate to injectable media uploader; fixture CI path uses stub (same as current `network_io=False`) |
| QQ passive reply window expires during long Gateway runs | Medium | Consumer should check window before delivering; use wakeup path if available |
| Gateway Bearer token not configured → bot service fails | Medium | Fail-closed: if token ref not resolvable, post-ACK composition records `completed_no_reply` (same as current missing backend) |
| Existing wiring tests break when backend is removed | Medium | Modify wiring tests to expect Gateway client config instead of backend; keep `FakeBackendAdapter` for backward compat where needed |
| `test_no_wecom_import.py` breaks if new shared module imports WeCom from QQ | Low | Keep `event_consumer.py` and `gateway_client.py` service-specific; no cross-channel imports |
| SSE frame parsing differs from Gateway encoding | Low | Use same `encode_sse_event` / parse pattern from `inkstatute_channels_web_sse` |

---

## Recommendations

1. **New `event_consumer.py` per service:** Each bot service gets its own `event_consumer.py` that:
   - Accepts a `GatewayClient` and `ChannelAdapter`
   - Creates a Gateway session (or reuses one)
   - Creates a Gateway run from the normalized `AgentTurn`
   - Consumes the SSE stream, collecting events
   - Sends intermediate prompts as they arrive (per degradation rules)
   - At terminal state, calls `aggregate_events()` and maps `BotDelivery` to `adapter.deliver()` calls

2. **New `gateway_client.py` per service:** Thin HTTP client using stdlib `urllib.request`:
   - `create_session(conversation_id) → session_id`
   - `create_run(turn, solution, session_id) → run_id`
   - `stream_events(run_id, last_seq) → Iterator[dict]` (SSE consumer)
   - `submit_elicitation(run_id, answer) → response`
   - `submit_approval(run_id, decision) → response`
   - `download_artifact(artifact_id) → bytes`
   - `submit_feedback(feedback_data) → response`
   - All methods use Bearer token auth

3. **Preserve all unchanged files:** `protocol.py`, `sender.py`, `signature.py`, `_ed25519.py`, `adapter.py`, `normalization.py`, `http_server.py`, `output_policy.py`, `idempotency.py`, `task_flow.py` — all unchanged.

4. **Modify only `webhook.py` and `wiring.py`:** The `run_post_ack_composition()` function in each service's `webhook.py` is modified to call `event_consumer` instead of `ingress_runtime`. The `wiring.py` is modified to inject Gateway client config instead of `DefaultRunRuntime` + backend.

5. **Keep `ingress_runtime.py` and `session_runtime.py` as-is:** Not deleted, not modified. They remain for reference and for any tests that directly exercise them. The post-ACK composition simply stops calling them.

6. **Injectable media uploader for WeCom:** The `event_consumer.py` should accept an optional `media_uploader` callable that uploads bytes to WeCom media API and returns a `media_id`. In fixture CI, this is a stub. In production, it's a real HTTP call.

7. **Intermediate prompt timing:** Use the existing `task_flow.py` `progress_interval_seconds=180.0` for additional "仍在处理" prompts beyond the first one from `plan.updated`/`phase.changed`. The consumer tracks elapsed time from the first event and sends prompts at 180-second intervals if the run is still active.

8. **Session mapping:** Simple in-memory `dict[str, str]` mapping `conversation_id → session_id`. No persistence needed at single-firm scale. On service restart, a new session is created for each conversation (acceptable — the Gateway retains run history).

9. **Gateway client config via env vars:**
   - `INKSTATUTE_GATEWAY_URL` (default: `http://127.0.0.1:8081`)
   - `INKSTATUTE_GATEWAY_BEARER_TOKEN_REF` (secret ref, resolved via existing `resolve_secret_ref()` pattern)
   - `INKSTATUTE_GATEWAY_TENANT_ID` (default: `default-tenant`)

10. **Test strategy:** New tests use a `FakeGatewayClient` that yields fixture events from a list, simulating the SSE stream. This keeps tests network-free and deterministic. The `FakeGatewayClient` implements the same interface as `GatewayClient` but returns canned responses.
