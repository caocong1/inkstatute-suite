---
phase: 95
slug: bot-channel-degradation
status: draft
created: 2026-08-09
depends_on: 91
requirements: BOT-01, BOT-02, BOT-03
---

# Phase 95 — Bot Channel Degradation

## Phase Goal

WeCom 与 QQ 通道复用同一事件流并正确降级为非流式，现有生产行为一步不退。

## Requirements

- **BOT-01**: WeCom 与 QQ 通道复用同一事件流，实现非流式降级（事件聚合 + "仍在处理"业务化推送 + 最终投递）
- **BOT-02**: `services/wecom-service` 与 `services/qqbot-service` 改为 Gateway 事件流消费者，不再各自持有 agent 调用
- **BOT-03**: 现有生产行为不回退——WeCom 5 秒 ACK / AES-CBC 验签解密 / 模板卡片、QQ ED25519 验签 / 回调校验 op=13、双方幂等与重试

## Success Criteria

1. 事件降级层存在：给定一串统一事件，产出 (a) 一条最终投递消息、(b) 若干"仍在处理"业务化中间推送、(c) 产物文件投递、(d) 澄清与审批的模板卡片；降级规则来自 Phase 88 的声明且有测试
2. `services/wecom-service` 与 `services/qqbot-service` 改为 Gateway 事件流消费者，源码中不再存在直接的 agent/backend 调用
3. WeCom 现有行为不回退：5 秒 ACK、AES-CBC 验签解密、模板卡片、媒体上传下载、幂等与重试——现有测试全绿
4. QQ 现有行为不回退：ED25519 验签、回调校验 op=13、webhook 端口约束、幂等——现有 28 个 qqbot 测试文件全绿
5. 同一条任务从 WeCom 发起，律师收到的内容与 Web 端最终结果语义一致（答复 + 产物 + 澄清 + 反馈卡片）
6. 后端 meta / gateway / system 噪声在 bot 通道同样不可见（输出边界在 Gateway 与降级层双重生效）

## Existing Infrastructure

### services/wecom-service (21 source files, 18 test files)

Current architecture: webhook → verify_and_ack → post-ACK composition

**Key files and their roles:**

| File | Role | Direct agent call? |
|------|------|-------------------|
| `webhook.py` | ACK-first webhook handler; schedules post-ACK composition | Yes — `backend.get_run()` at line 166-168 |
| `ingress_runtime.py` | `WeComRuntimeIngress`: callback → AgentTurn → RunRequest → session_runtime | No (delegates to session_runtime) |
| `session_runtime.py` | `WeComSessionRuntime`: session resolution, interrupt resume, create_run | **Yes — `self.runtime.create_run()` (line 314), `self.runtime.resume_interrupt()` (line 242)** |
| `wiring.py` | `build_wecom_wired_runtime`: composes adapter + DefaultRunRuntime with backend | Injects backend into runtime |
| `agent_backend.py` | Selects agent backend manifest (Hermes mode) | No |
| `sender.py` | `build_text_send_envelope`, `build_file_send_envelope`, `build_template_card_envelope` | No |
| `protocol.py` | `verify_callback_signature` (SHA1 digest), `parse_callback_envelope`, `ack_response` ("success") | No |
| `task_flow.py` | WeCom task stages (received → ... → completed), progress notices (180s interval) | No |
| `http_server.py` | stdlib HTTP server wrapper (`WeComWebhookServer`) | No |
| `output_policy.py` | `apply_output_policy` — output boundary for WeCom sends | No |
| `idempotency.py` | `wecom_idempotency_key` — callback metadata dedup | No |
| `normalization.py` | `normalize_wecom_turn`, `normalize_wecom_feedback_callback` | No |
| `delivery_guard.py` | Delivery guard logic | No |
| `active_task_router.py` | Active task routing for follow-up messages | No |
| `owned_notices.py` | Service-owned notice builders | No |
| `runtime_audit.py` | Runtime audit trail | No |
| `memory_factory.py` / `memory_integration.py` | Memory orchestration integration | No |
| `channel_wiring.py` | Channel config loading from operator-config | No |

**Current flow (to be replaced):**
```
WeCom callback → webhook.handle_wecom_webhook_request()
  → adapter.verify_and_ack()  [5s ACK, AES-CBC signature check]
  → post_ack_scheduler schedules run_post_ack_composition()
    → adapter.normalize_inbound()  [callback → AgentTurn]
    → WeComRuntimeIngress.handle_callback()
      → WeComSessionRuntime.handle_turn()
        → runtime.create_run() or runtime.resume_interrupt()  ← DIRECT AGENT CALL
    → backend.get_run()  ← DIRECT AGENT CALL (to get reply text)
    → output_boundary.apply()
    → adapter.deliver()  [text/file/card send envelope]
```

**What must be preserved (BOT-03):**
- 5-second ACK deadline (`ack_deadline_ms=5000` in capabilities)
- AES-CBC callback signature verification (`verify_callback_signature` in protocol.py)
- Template card delivery (`build_template_card_envelope` in sender.py)
- Media upload/download (`build_file_send_envelope` with media_id)
- Idempotency (`wecom_idempotency_key`, `_outcome_by_idempotency_key` in session_runtime)
- Retry behavior
- All 18 existing test files must stay green

### services/qqbot-service (7 source files, 13 test files)

Current architecture: webhook → verify_and_ack (ED25519) → post-ACK composition

**Key files and their roles:**

| File | Role | Direct agent call? |
|------|------|-------------------|
| `webhook.py` | ACK-first webhook handler; ED25519 verify, op=13 challenge; schedules post-ACK | Yes — `backend.get_run()` via `_resolve_reply_text()` at line 127-150 |
| `wiring.py` | `build_qqbot_wired_runtime`: dual-knob mapping, live-IO injection (token_manager + transport) | Injects backend into runtime |
| `http_server.py` | stdlib HTTP server wrapper (`QQBotWebhookServer`) | No |
| `config.py` | `QQBotHostConfig`, `load_qqbot_host_config` | No |
| `secrets.py` | `resolve_secret_ref` — secret ref resolution | No |

**QQ bot channel adapter** (`packages/channels/qqbot/`, 23 test files):
- `adapter.py` (1218 lines) — QQBotChannelAdapter with ED25519 verify, op=13, interaction ACK, passive reply window, wakeup
- `ingress_runtime.py` — `QQBotRuntimeIngress`: gateway envelope → AgentTurn → RunRequest → session_runtime
- `session_runtime.py` — `QQBotSessionRuntime`: session resolution, create_run
- `sender.py` — text/markdown/media/feedback keyboard envelopes, wakeup
- `signature.py` — ED25519 keypair derivation, signature verification, validation challenge
- `normalization.py` — QQ gateway envelope parsing, message event normalization
- `token_manager.py` — QQ Bot OpenAPI token management
- `feedback_ingress.py` — feedback callback handling

**Current flow (to be replaced):**
```
QQ callback → webhook.handle_qqbot_webhook_request()
  → adapter.verify_and_ack()  [ED25519 verify, op=13 challenge, interaction ACK]
  → post_ack_scheduler schedules run_post_ack_composition()
    → adapter.normalize_inbound()  [gateway envelope → AgentTurn]
    → QQBotRuntimeIngress.handle_callback()
      → QQBotSessionRuntime.handle_turn()
        → runtime.create_run() or runtime.resume_interrupt()  ← DIRECT AGENT CALL
    → _resolve_reply_text() → backend.get_run()  ← DIRECT AGENT CALL
    → output_boundary.apply()
    → adapter.deliver()  [text/markdown/media/card send]
```

**What must be preserved (BOT-03):**
- ED25519 signature verification (`verify_callback_signature` in signature.py)
- op=13 validation challenge handling (`handle_validation_challenge`)
- Webhook port constraints
- Interaction ACK (op=12 + interaction PUT)
- Passive reply window checking (`check_passive_reply_window`)
- Wakeup/recall support (`_deliver_wakeup`)
- Idempotency (`channel_idempotency_key`)
- All 13 qqbot-service test files + 23 qqbot channel test files must stay green

### packages/platform-contract — Bot Degradation (Phase 88)

**`bot_degradation.py`** (274 lines) — Pure-function aggregator:
- `DegradationCategory` enum: 8 categories (SILENT, BUFFER, DELIVER, DISCARD, FOLD, FIRST_THEN_SILENT, ATTACH, ON_FAILURE)
- `DEGRADATION_RULES` dict: maps 15 event types (13 categories + 3 tool_call sub-types) to categories
- `BotDelivery` dataclass: `final_message`, `intermediate_prompts`, `cards`, `files`, `citations`, `error_prompt`, `delivered`
- `aggregate_events(events: list[dict]) -> BotDelivery` — pure function, sorts by seq, deterministic output

**Degradation rules (from Phase 88):**

| Category | Event Types | Behavior |
|----------|-------------|----------|
| SILENT | session.started | Drop entirely |
| BUFFER | message.delta | Accumulate, deliver on message.completed |
| DELIVER | message.completed, elicitation.requested, permission.requested, artifact.created | Send as final message/card/file |
| DISCARD | thought.delta | Drop (no business value for bots) |
| FOLD | tool_call.started/delta/completed | Collapse to "正在检索法规…" (first only) |
| FIRST_THEN_SILENT | plan.updated, phase.changed | First → "仍在处理", rest silent |
| ATTACH | citation.recorded | Append to final delivered message |
| ON_FAILURE | run.state_changed, error | Only deliver on failure |

**Business-prompt templates:**
- `_TOOL_FOLD_PROMPT = "正在检索法规…"`
- `_PLAN_FIRST_PROMPT = "仍在处理"`
- `_FAILURE_PROMPT = "处理失败，请稍后重试或联系管理员"`

**Tests:** `test_bot_degradation.py` (306 lines) — covers all 8 categories, determinism, out-of-order, full lifecycle.

### services/gateway (Phase 91, 15 source files, 12+ test files)

**Gateway API endpoints (relevant to bot consumption):**
- `POST /v1/runs` — create run (requires `turn` + `solution` in body)
- `GET /v1/runs/{id}/events` — SSE stream with `Last-Event-ID` replay
- `POST /v1/runs/{id}/elicitation` — submit elicitation answer
- `POST /v1/runs/{id}/approvals` — submit approval decision
- `GET /v1/artifacts/{id}` — download artifact
- `POST /v1/feedback` — submit feedback
- `POST /v1/sessions` — create session
- `POST /v1/auth/login` — login (unauthenticated)

**SSE streaming (`GatewayApp.stream()`):**
- Auth applied before yielding frames (`auth.require_auth(headers)`)
- `Last-Event-ID` header → replay buffered events with `seq > last_seq`
- `RunEventBuffer` — in-memory per-run, thread-safe, FIFO eviction at 1000 events
- Output boundary enforced in `GatewaySseStream.encode_event()` — blocked events return `None`
- Terminal retention: 5 minutes after terminal state

**Auth (`GatewayAuth`):**
- `resolve_identity()` — Bearer token first, session cookie fallback
- Roles: ADMIN, OPERATOR, LAWYER, VIEWER
- Tenant isolation via `check_tenant()`
- Bot/programmatic access: Bearer token

**Run creation (`_handle_create_run()`):**
- Requires `turn` (AgentTurn fields) + `solution` (SolutionBinding fields) in body
- Calls `runtime.create_run(run_request)` — returns serialized run with `run_id`
- Tenant_id from auth context

### ChannelAdapter Protocol (packages/platform-runtime)

```python
class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...
    def capabilities(self) -> ChannelCapabilitySet: ...
    async def verify_and_ack(self, raw: RawInbound) -> AckResponse: ...
    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized: ...
    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult: ...
    async def health(self) -> ComponentHealth: ...
```

Both `WeComChannelAdapter` and `QQBotChannelAdapter` implement this Protocol. The `deliver()` method accepts a `ChannelDelivery` with `content`, `metadata` (delivery_type, to_user/scene, etc.), and returns `DeliveryResult`.

## Key Decisions (Auto-Selected)

### 1. Event degradation layer location — New shared module per service

[auto] Q: "Where does the event degradation aggregator live in the bot service flow?" → Selected: "New `event_consumer.py` module in each bot service" (recommended)

**Rationale:** The `aggregate_events()` pure function already exists in `packages/platform-contract/bot_degradation.py` (Phase 88). Each bot service needs a thin consumer module that:
1. Collects events from the Gateway SSE stream
2. Feeds them to `aggregate_events()` at terminal state
3. Maps the `BotDelivery` result to channel-specific `ChannelDelivery` calls

This keeps the degradation rules in the contract package (shared, tested) while the consumption + delivery mapping is service-specific (WeCom template cards vs QQ feedback keyboards have different envelope shapes). A new `event_consumer.py` in each service preserves the existing module structure and test isolation.

### 2. Gateway consumption mechanism — HTTP client consuming SSE stream

[auto] Q: "How do bot services consume Gateway SSE?" → Selected: "HTTP client that consumes the SSE stream endpoint" (recommended)

**Rationale:** The Gateway provides `GET /v1/runs/{id}/events` as an SSE stream with `Last-Event-ID` replay. Bot services should consume this stream using a simple HTTP client (stdlib `urllib.request` or `http.client`) that:
1. Opens a connection to `GET /v1/runs/{id}/events` with a Bearer token
2. Reads SSE frames as they arrive
3. Collects events into a list
4. When the stream closes (terminal state), calls `aggregate_events()` on the collected list
5. Maps the `BotDelivery` to channel-specific deliveries

This is simpler than polling and leverages the existing Gateway infrastructure. The SSE stream naturally ends at terminal state (`run.state_changed` with succeeded/failed/cancelled), so the consumer knows when to aggregate and deliver. For single-firm scale (≤50 lawyers), a blocking HTTP client on a daemon thread (matching the existing `post_ack_scheduler` pattern) is sufficient.

### 3. Run creation via Gateway — HTTP POST to /v1/runs

[auto] Q: "How do bot services create runs via Gateway?" → Selected: "HTTP POST to /v1/runs with Bearer token auth" (recommended)

**Rationale:** BOT-02 requires bot services to be Gateway consumers, not direct runtime callers. The post-ACK composition changes from:
- **Old:** `runtime.create_run(run_request)` → `backend.get_run(run_id)` → extract reply text → `adapter.deliver()`
- **New:** HTTP `POST /v1/runs` (with turn + solution) → get `run_id` → HTTP `GET /v1/runs/{id}/events` (SSE) → collect events → `aggregate_events()` → map `BotDelivery` to `adapter.deliver()` calls

The bot service constructs the `turn` payload from the normalized inbound callback (existing `normalize_inbound` → `AgentTurn`), and uses a fixed `solution` binding (configured per bot instance). A Bearer token authenticates the bot service to the Gateway.

### 4. Template card mapping — elicitation/permission → channel-specific cards

[auto] Q: "How do clarification/approval events map to WeCom template cards and QQ keyboards?" → Selected: "Map BotDelivery.cards to channel-specific card envelopes via delivery metadata" (recommended)

**Rationale:** The `aggregate_events()` function collects `elicitation.requested` and `permission.requested` payloads into `BotDelivery.cards`. The event consumer maps each card payload to:
- **WeCom:** `build_template_card_envelope()` — existing sender function, produces WeCom template_card with card_id, title, feedback_target
- **QQ:** `build_feedback_keyboard_envelope()` — existing QQ sender function, produces QQ keyboard with feedback buttons

The card payload from the unified event contains `interrupt_id`, `questions` (for elicitation) or `permission_id`, `description` (for permission). The consumer maps these to the channel-specific card fields. The existing `adapter.deliver()` method already handles `delivery_type="card"` for both channels.

### 5. Media/artifact delivery — Download from Gateway, upload to channel media API

[auto] Q: "How are artifacts delivered via bot channels?" → Selected: "Download artifact from Gateway /v1/artifacts/{id}, then deliver via channel adapter deliver() with file type" (recommended)

**Rationale:** `artifact.created` events produce `BotDelivery.files` entries with artifact metadata. The consumer:
1. Downloads the artifact content from `GET /v1/artifacts/{id}` (Gateway endpoint, auth required)
2. For WeCom: uploads to WeCom media API to get `media_id`, then calls `adapter.deliver()` with `delivery_type="file"` and `media_id` in metadata
3. For QQ: calls `adapter.deliver()` with `delivery_type="file"` and the artifact reference

The existing `WeComChannelAdapter.deliver()` already handles `delivery_type="file"` with `media_id` metadata (line 112-114 in adapter.py). The QQ adapter handles `delivery_type in {"file", "image"}` via `_deliver_rich_media()`.

**Note:** The actual media upload to WeCom API requires network IO that is currently stubbed (network_io=False in capabilities). The consumer module should delegate media upload to an injectable media uploader, keeping the fixture CI path working.

### 6. Intermediate push behavior — Time-based with existing task_flow interval

[auto] Q: "How many '仍在处理' messages? When? Content?" → Selected: "Use existing task_flow progress_interval_seconds (180s) for intermediate pushes" (recommended)

**Rationale:** The existing `task_flow.py` already has `progress_interval_seconds=180.0` (3 minutes) and `progress_notice_due()` logic. The event consumer should:
1. Send the first intermediate prompt when `plan.updated` or `phase.changed` arrives (per degradation rules: FIRST_THEN_SILENT → "仍在处理")
2. Send additional "仍在处理" prompts at 180-second intervals if the run is still active (leveraging existing task_flow logic)
3. The `tool_call` fold prompt ("正在检索法规…") is sent once when the first tool_call event arrives

This preserves the existing WeCom progress notice behavior (180s interval) while adapting it to the event stream model. The consumer tracks elapsed time from the first event and sends intermediate prompts via `adapter.deliver()` with `delivery_type="text"`.

### 7. Idempotency & retry — Existing idempotency keys + Gateway event seq dedup

[auto] Q: "How to handle bot message delivery retries? Dedup?" → Selected: "Existing channel idempotency + Gateway seq-based event dedup" (recommended)

**Rationale:** Two layers of idempotency:
1. **Inbound (callback → run creation):** Existing `wecom_idempotency_key` / `channel_idempotency_key` dedup is preserved. The webhook handler still checks idempotency before creating a Gateway run.
2. **Outbound (event consumption → delivery):** The Gateway SSE stream provides `seq`-based ordering and `Last-Event-ID` replay. If the consumer disconnects and reconnects, it resumes from the last `seq` without duplicates. The `aggregate_events()` function is pure and deterministic — same events always produce the same `BotDelivery`.

For delivery retry: if `adapter.deliver()` fails (returns `accepted=False`), the consumer retries with exponential backoff up to 3 times, then logs the failure. The delivery `delivery_id` is derived from `run_id` + delivery index, providing natural dedup.

### 8. Existing behavior preservation — Keep webhook/verify_and_ack/adapter intact, replace only post-ACK composition

[auto] Q: "How to ensure 5s ACK, AES-CBC, ED25519, etc. don't regress?" → Selected: "Preserve webhook + verify_and_ack + adapter unchanged; replace only post-ACK composition's agent call path" (recommended)

**Rationale:** The critical preservation targets are:
- `webhook.py` — ACK-first pattern, 5s deadline, post-ACK scheduling → **unchanged**
- `adapter.verify_and_ack()` — AES-CBC (WeCom) / ED25519 + op=13 (QQ) → **unchanged**
- `adapter.normalize_inbound()` — callback → AgentTurn → **unchanged**
- `adapter.deliver()` — send envelopes → **unchanged**
- `sender.py` / `signature.py` / `protocol.py` → **unchanged**
- `http_server.py` → **unchanged**
- `wiring.py` — backend injection → **modified** (remove direct backend, add Gateway client)

The **only** code that changes is the post-ACK composition path:
- **Old:** `ingress_runtime.py` → `session_runtime.py` → `runtime.create_run()` / `backend.get_run()`
- **New:** `event_consumer.py` → Gateway HTTP client → `aggregate_events()` → `adapter.deliver()`

The `ingress_runtime.py` and `session_runtime.py` files are **not deleted** — they are kept for reference but the post-ACK composition no longer calls them. The `wiring.py` is modified to inject a Gateway client instead of a `DefaultRunRuntime` with a backend. All existing tests that don't depend on direct runtime calls remain green.

### 9. Bot → Gateway auth — Service Bearer token

[auto] Q: "How do bot services authenticate with Gateway?" → Selected: "Pre-configured Bearer token per bot instance" (recommended)

**Rationale:** The Gateway already supports Bearer token auth for bot/programmatic access (GW-03). Each bot service uses a pre-configured Bearer token (stored as a secret ref, resolved via `resolve_secret_ref()` in QQ, or via env in WeCom). The token has `role=LAWYER` and a fixed `tenant_id` for the bot's tenant. This is consistent with the existing secret-ref pattern (no secrets in code, resolved at process edge).

### 10. Session management — Create session per conversation, reuse across runs

[auto] Q: "How do bot services manage sessions via Gateway?" → Selected: "Create or reuse Gateway session per WeCom/QQ conversation_id" (recommended)

**Rationale:** The Gateway provides `POST /v1/sessions` to create sessions. The bot service maps the WeCom/QQ `conversation_id` to a Gateway session:
1. On first message from a conversation: `POST /v1/sessions` with `conversation_id` → store `session_id`
2. On subsequent messages: reuse the stored `session_id` in `POST /v1/runs` body
3. Session mapping is in-memory (single-firm scale) or could be persisted later

This preserves the existing session resolution behavior (continue vs new session) while routing through the Gateway. The existing `SessionResolutionPolicy` logic in `session_runtime.py` is replaced by Gateway session management.

## Key Files

### New Files

- `services/wecom-service/src/wecom_service/event_consumer.py` — Gateway SSE consumer + degradation aggregator + delivery mapper
- `services/qqbot-service/src/qqbot_service/event_consumer.py` — Gateway SSE consumer + degradation aggregator + delivery mapper
- `services/wecom-service/src/wecom_service/gateway_client.py` — Thin HTTP client for Gateway API (create run, stream events, submit elicitation, download artifact)
- `services/qqbot-service/src/qqbot_service/gateway_client.py` — Thin HTTP client for Gateway API
- `services/wecom-service/tests/test_event_consumer.py` — Event consumer + degradation integration tests
- `services/qqbot-service/tests/test_event_consumer.py` — Event consumer + degradation integration tests
- `services/wecom-service/tests/test_gateway_client.py` — Gateway client unit tests
- `services/qqbot-service/tests/test_gateway_client.py` — Gateway client unit tests

### Modified Files

- `services/wecom-service/src/wecom_service/webhook.py` — `run_post_ack_composition()` calls event_consumer instead of ingress_runtime
- `services/qqbot-service/src/qqbot_service/webhook.py` — `run_post_ack_composition()` calls event_consumer instead of ingress_runtime
- `services/wecom-service/src/wecom_service/wiring.py` — Inject Gateway client config instead of DefaultRunRuntime + backend
- `services/qqbot-service/src/qqbot_service/wiring.py` — Inject Gateway client config instead of DefaultRunRuntime + backend

### Unchanged Files (preserved for BOT-03)

- `services/wecom-service/src/wecom_service/protocol.py` — AES-CBC signature verification
- `services/wecom-service/src/wecom_service/sender.py` — Send envelope builders
- `services/wecom-service/src/wecom_service/output_policy.py` — Output policy
- `services/wecom-service/src/wecom_service/idempotency.py` — Idempotency keys
- `services/wecom-service/src/wecom_service/http_server.py` — HTTP server
- `services/wecom-service/src/wecom_service/task_flow.py` — Task flow stages (referenced by consumer for progress timing)
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — WeComChannelAdapter
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — QQBotChannelAdapter
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` — ED25519
- `packages/platform-contract/src/platform_contract/bot_degradation.py` — Degradation rules (from Phase 88)

### Existing Files to Reference

- `packages/platform-contract/src/platform_contract/bot_degradation.py` — `aggregate_events()`, `BotDelivery`, `DEGRADATION_RULES`
- `services/gateway/src/gateway/app.py` — Gateway API endpoints, run creation, SSE streaming
- `services/gateway/src/gateway/sse.py` — SSE encoding with output boundary
- `services/gateway/src/gateway/event_buffer.py` — Event buffer with Last-Event-ID replay
- `packages/platform-runtime/src/platform_runtime/protocols.py` — ChannelAdapter Protocol, ChannelDelivery, RunEvent

## Patterns Established

- **Bot as Gateway consumer:** Bot services consume the same Gateway API as web/desktop clients, using Bearer token auth
- **Degradation at consumption:** The pure-function `aggregate_events()` from Phase 88 is the single degradation point; bot services map its output to channel-specific deliveries
- **Preserved ACK path:** The webhook → verify_and_ack → post-ACK schedule pattern is unchanged; only the post-ACK composition's agent call path is replaced
- **Channel adapter reuse:** The existing `adapter.deliver()` method handles all delivery types (text, file, card) — the consumer maps `BotDelivery` fields to `ChannelDelivery` metadata
- **Output boundary double enforcement:** Gateway SSE enforces output boundary (first point); the degradation aggregator's SILENT/DISCARD rules provide second-layer filtering for bot channels
