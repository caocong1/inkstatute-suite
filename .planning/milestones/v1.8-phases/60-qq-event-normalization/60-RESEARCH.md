# Phase 60: QQ Event Normalization — Technical Research

**Phase:** 60 — QQ Event Normalization
**Requirements:** INGRESS-03, INGRESS-04, INGRESS-05
**Depends on:** Phase 59 (complete)
**Researched:** 2026-07-07
**Status:** Complete

## User Constraints

### Decisions (from CONTEXT.md)

Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions. `[VERIFIED: .planning/phases/60-qq-event-normalization/60-CONTEXT.md]`

### Deferred Ideas

None — discuss phase skipped. `[VERIFIED: 60-CONTEXT.md]`

## Project Constraints (from AGENTS.md)

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- Contract logs should prefer references such as `raw_payload_ref` and must not store sensitive full text by default. `[VERIFIED: AGENTS.md]`
- Prefer structured parsers and schema validators over ad hoc string parsing. `[VERIFIED: AGENTS.md]`
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it. `[VERIFIED: AGENTS.md]`
- `dependencies = []` invariant must hold for QQBot channel package — use Python stdlib only. `[VERIFIED: codebase — packages/channels/qqbot/pyproject.toml, packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`
- All 24 existing V2 gates must remain green throughout v1.8 (ADAPTER-04 cross-cutting safety). `[VERIFIED: .planning/ROADMAP.md line 49]`
- Frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified. `[VERIFIED: .planning/ROADMAP.md line 32]`
- QQBot adapter must NOT import from `wecom_service` (enforced by `test_no_wecom_import.py`). `[VERIFIED: .planning/REQUIREMENTS.md ADAPTER-03]`
- No new `FeedbackSource` enum values added (frozen at 4 values). `[VERIFIED: .planning/REQUIREMENTS.md INGRESS-05, .planning/ROADMAP.md Phase 60 SC-4]`

## Standard Stack

### Target Module

- **`packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py`** (NEW) — QQ Bot gateway envelope parser and event normalizer. Pure functions, no network IO, no wecom_service import. Public API:
  - `parse_envelope(payload: Mapping[str, Any]) -> QQBotEvent` — parse `{op, t, d}` into a typed event category
  - `normalize_message_event(event: QQBotEvent, *, received_at: str) -> AgentTurn` — C2C/GROUP_AT_MESSAGE_CREATE → `AgentTurn`
  - `normalize_interaction_event(event: QQBotEvent, *, created_at: str) -> FeedbackEvent` — INTERACTION_CREATE → `FeedbackEvent`
  - Typed event categories via a `QQBotEventCategory` enum or frozen dataclass (C2C_MESSAGE, GROUP_AT_MESSAGE, INTERACTION, VALIDATION_CHALLENGE, UNKNOWN)

`[ASSUMED — module name and API shape inferred from ROADMAP SC-1 ("normalization.py parses gateway envelope") and analogous wecom_service/normalization.py pattern]`

### Existing Modules to Reuse (NO import from wecom_service)

- **`platform_contract.events`** — `AgentTurn`, `FeedbackEvent`, `AttachmentRef`, `SkillCandidate` dataclasses `[VERIFIED: packages/platform-contract/src/platform_contract/events.py:126-181]`
- **`platform_contract.enums`** — `Channel.QQBOT`, `FeedbackSource.CARD_BUTTON`, `FeedbackAction.{UP,DOWN,NEEDS_FIX,ROUTE_WRONG}`, `FeedbackEventType.{RATING,CORRECTION,ROUTE_MISMATCH}`, `FeedbackStatus.PENDING`, `MessageType.TEXT` `[VERIFIED: packages/platform-contract/src/platform_contract/enums.py:33-162]`
- **`channel_core.idempotency`** — `channel_idempotency_key(callback, channel_prefix="qqbot")` for stable idempotency keys `[VERIFIED: packages/channel-core/src/channel_core/idempotency.py]`
- **`contract_test_suite.schema_validation`** — `validate_event("agent_turn", event)` and `validate_event("feedback_event", event)` for schema validation in tests `[VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py:96-116]`

### Test Framework

- **`unittest`** (stdlib) — matches all existing qqbot tests. All tests are `unittest.TestCase` subclasses. `[VERIFIED: packages/channels/qqbot/tests/]`
- No pytest-specific features used.

### Fixture Format

- **JSON fixtures** in `packages/channels/qqbot/fixtures/` — sanitized, no raw payloads, `raw_payload_ref` references only. `[VERIFIED: packages/channels/qqbot/fixtures/qqbot_channel_loop.json]`

## QQ Bot Gateway Envelope Structure (Verified from Official Docs)

### Envelope: `{op, t, d, id, s}`

The QQ Bot gateway payload (both webhook and websocket) uses this structure:

```json
{
  "id": "event_id",
  "op": 0,
  "d": {},
  "s": 42,
  "t": "GATEWAY_EVENT_NAME"
}
```

| Field | Description |
|-------|-------------|
| `id`  | Event ID |
| `op`  | Opcode (see table below) |
| `s`   | Sequence number (websocket only — identifies message uniqueness) |
| `t`   | Event type (mainly used when op=0 Dispatch) |
| `d`   | Event content (payload data — varies by event type) |

`[CITED: bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html — 通用数据结构 Payload]`

### OpCode Table

| Code | Name | Mode | Direction | Description |
|------|------|------|-----------|-------------|
| 0 | Dispatch | webhook/websocket | Receive | Server pushes events |
| 1 | Heartbeat | websocket | Send/Receive | Heartbeat |
| 2 | Identify | websocket | Send | Client auth |
| 6 | Resume | websocket | Send | Client resume |
| 7 | Reconnect | websocket | Receive | Server notify reconnect |
| 9 | Invalid Session | websocket | Receive | Identify/resume param error |
| 10 | Hello | websocket | Receive | First message after WS connect |
| 11 | Heartbeat ACK | websocket | Receive/Reply | Heartbeat success |
| **12** | **HTTP Callback ACK** | **webhook** | **Reply** | **Client ACK for webhook mode** |
| **13** | **回调地址验证 (Validation Challenge)** | **webhook** | **Receive** | **Platform validates callback URL** |

`[CITED: bot.q.qq.com — event-emit.html OpCode 含义]`

**Phase 60 relevant opcodes:**
- **op=0 (Dispatch)**: Normal event dispatch. The `t` field identifies the event type. This is where C2C_MESSAGE_CREATE, GROUP_AT_MESSAGE_CREATE, and INTERACTION_CREATE arrive.
- **op=13 (Validation Challenge)**: Already handled by Phase 59's `signature.py` `handle_validation_challenge()`. Phase 60 should recognize and dispatch this category but the signing logic is already implemented.
- **op=12 (HTTP Callback ACK)**: Used for webhook ACK responses (Phase 65 scope, not Phase 60).

### Event Types (op=0 Dispatch, `t` field)

| Event Type | Intent | Trigger | Scene |
|------------|--------|---------|-------|
| `C2C_MESSAGE_CREATE` | 1<<25 | User sends message to bot in DM | c2c |
| `GROUP_AT_MESSAGE_CREATE` | 1<<25 | User @-mentions bot in group | group |
| `GROUP_MESSAGE_CREATE` | 1<<25 | All group messages (when enabled) | group |
| `INTERACTION_CREATE` | 1<<26 | User clicks callback button | c2c/group/guild |
| `FRIEND_ADD` | 1<<25 | User adds bot as friend | c2c |
| `FRIEND_DEL` | 1<<25 | User deletes bot | c2c |
| `GROUP_ADD_ROBOT` | 1<<25 | Bot added to group | group |
| `GROUP_DEL_ROBOT` | 1<<25 | Bot removed from group | group |

`[CITED: bot.q.qq.com — event-emit.html 事件订阅Intents]`

**Phase 60 must handle:** `C2C_MESSAGE_CREATE`, `GROUP_AT_MESSAGE_CREATE`, `INTERACTION_CREATE`, and `op=13` validation challenge. Other event types should dispatch to an "unknown/ignored" category (not crash).

### C2C_MESSAGE_CREATE Payload (`d` field)

```json
{
  "author": {
    "user_openid": "E4F4AEA33253A2797FB897C50B81D7ED"
  },
  "content": "123",
  "id": "ROBOT1.0_.b6nx.CVryAO0nR58RXuU6SC.m92gc19j02qKqdm8ek!",
  "timestamp": "2023-11-06T13:37:18+08:00",
  "attachments": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Platform message ID (used for passive reply) |
| `author` | object | Sender |
| `author.user_openid` | string | User openid |
| `content` | string | Text message content |
| `timestamp` | string | Message time (RFC3339) |
| `attachments` | object[] | Rich media attachments (image/voice/video/file) |

`[CITED: bot.q.qq.com — server-inter/message/send-receive/event.html 单聊消息]`

### GROUP_AT_MESSAGE_CREATE Payload (`d` field)

```json
{
  "author": {
    "member_openid": "E4F4AEA33253A2797FB897C50B81D7ED"
  },
  "content": " 123",
  "group_openid": "C9F778FE6ADF9D1D1DBE395BF744A33A",
  "id": "ROBOT1.0_eBIyWnxpmSu6uLQ7u7fU0eGloKGYg4eEa737vRyKnMCgyZjKi7JLYkQ9B0VapbiY",
  "timestamp": "2023-11-06T13:37:18+08:00",
  "attachments": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Platform message ID |
| `author` | object | Sender |
| `author.member_openid` | string | User's member openid in this group |
| `author.member_role` | string | Role: owner, admin, member |
| `author.bot` | bool | Is bot |
| `content` | string | Message content (starts with @bot mention + leading space) |
| `group_openid` | string | Group openid |
| `timestamp` | string | Message time (RFC3339) |
| `attachments` | object[] | Rich media attachments |

`[CITED: bot.q.qq.com — server-inter/message/send-receive/event.html 群聊@机器人]`

**Key observation:** The `content` field in GROUP_AT_MESSAGE_CREATE starts with a leading space after the @-mention is stripped by the platform. The example shows `"content": " 123"` — the leading space is the residual after the @bot mention. Phase 60 must strip this to get plain text `"123"`.

### INTERACTION_CREATE Payload (`d` field)

```json
{
  "chat_type": 2,
  "data": {
    "resolved": {
      "button_data": "回调按钮",
      "button_id": "21",
      "user_id": "E4F4AEA33253A2797FB897C50B81D7ED"
    },
    "type": 11
  },
  "id": "30540ff7-9d8f-4737-83f1-e116ce6afa8b",
  "type": 11,
  "version": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Platform event ID (used for `PUT /interactions/{id}` ACK) |
| `type` | int | 11 = message button, 12 = DM quick menu |
| `scene` | string | Event scene: `c2c`, `group`, `guild` |
| `chat_type` | int | 0 = guild, 1 = group, 2 = c2c |
| `timestamp` | string | Trigger time (RFC3339) |
| `guild_id` | string | Guild openid (guild scene only) |
| `channel_id` | string | Channel openid (guild scene only) |
| `user_openid` | string | User openid (c2c scene only) |
| `group_openid` | string | Group openid (group scene only) |
| `group_member_openid` | string | Group member openid (group scene only) |
| `data.resolved.button_data` | string | Button data value (set when sending the button) |
| `data.resolved.button_id` | string | Button ID |
| `data.resolved.user_id` | string | Operating user ID (guild scene only) |
| `data.resolved.feature_id` | string | Button ID (custom menu only) |
| `data.resolved.message_id` | string | Message ID (guild scene only) |
| `version` | int | Default 1 |

`[CITED: bot.qq.com/wiki/develop/api-v2/server-inter/message/trans/msg-btn.html — 消息按钮 INTERACTION_CREATE]`

**Note on doc typo:** The official doc spells the field as `data.resoloved.button_data` (with a typo "resoloved" instead of "resolved"). The actual JSON payload example uses `"resolved"` (correct spelling). The normalizer should accept both spellings defensively but prefer `"resolved"`. `[CITED: bot.qq.com — msg-btn.html field table vs JSON example]`

## Architecture Patterns

### Where QQ Bot Event Normalization Fits

```
HTTP Webhook Callback
  → Phase 59: signature.py verify_callback_signature() (Ed25519)
  → Phase 59: signature.py handle_validation_challenge() (op=13)
  → Phase 60: normalization.py parse_envelope() → typed event category
  → Phase 60: normalization.py normalize_message_event() → AgentTurn
  → Phase 60: normalization.py normalize_interaction_event() → FeedbackEvent
  → Phase 64: ingress_runtime.py → session_runtime.py (future)
```

`[VERIFIED: Phase 59 adapter.py verify_and_ack already handles signature + op=13; Phase 60 adds the envelope parsing + normalization layer]`

### Module Layout (Phase 60 additions)

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── __init__.py          # exports QQBotChannelAdapter, QQBotChannelConfig
├── _ed25519.py          # Phase 59: vendored RFC 8032 Ed25519
├── signature.py         # Phase 59: signature verify + validation challenge
├── config.py            # Phase 59: bot_secret_ref field
├── adapter.py           # MODIFIED: normalize_inbound delegates to normalization.py
└── normalization.py     # NEW: gateway envelope parser + event normalizer
```

`[ASSUMED — module placement follows Phase 59 pattern of adding new modules to the qqbot package]`

### Existing normalize_inbound (to be refactored)

The current `adapter.py` `normalize_inbound` method (lines 175-199) uses a simple fixture-grade payload format where `RawInbound.metadata["payload"]` contains pre-normalized fields like `conversation_id`, `user_id`, `type`, `action`, etc. `[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:175-199]`

Phase 60 should:
1. Create `normalization.py` with envelope parsing and event normalization as pure functions
2. Refactor `adapter.py` `normalize_inbound` to delegate to `normalization.py` when the payload is a real QQ Bot gateway envelope (`{op, t, d}`)
3. Preserve backward compatibility with the existing fixture format (the `qqbot_channel_loop.json` fixture and `test_qqbot_channel_loop.py` must still pass)

`[ASSUMED — approach inferred from ROADMAP SC-1 ("normalization.py parses gateway envelope") + need to preserve existing tests]`

### Scene-Aware conversation_id Format

**Format:** `qqbot:{scene}:{scene_id}:{user_openid}`

| Scene | scene | scene_id source | user_openid source |
|-------|-------|-----------------|-------------------|
| C2C DM | `c2c` | `user_openid` (from `d.author.user_openid`) | `d.author.user_openid` |
| Group @-bot | `group` | `group_openid` (from `d.group_openid`) | `d.author.member_openid` |

`[VERIFIED: .planning/REQUIREMENTS.md INGRESS-04 — "scene-aware composite conversation_id (qqbot:{scene}:{scene_id}:{user_openid})"]`

**Examples:**
- C2C: `qqbot:c2c:E4F4AEA33253A2797FB897C50B81D7ED:E4F4AEA33253A2797FB897C50B81D7ED`
  (scene_id = user_openid, user_openid = same user_openid)
- Group: `qqbot:group:C9F778FE6ADF9D1D1DBE395BF744A33A:E4F4AEA33253A2797FB897C50B81D7ED`
  (scene_id = group_openid, user_openid = member_openid)

`[ASSUMED — format derived from REQUIREMENTS.md INGRESS-04 + QQ Bot payload field names]`

### @-bot Prefix Stripping

QQ group @-bot messages arrive with the @-mention prefix in the `content` field. The platform delivers content like `" 123"` (leading space after mention stripping by QQ platform, or the raw mention text).

**Stripping strategy:** Strip leading `@<token>` mention + whitespace from content. The Hermes QQ Bot adapter uses:

```python
import re
stripped = re.sub(r"^@\S+\s*", "", content.strip())
```

`[CITED: github.com/NousResearch/hermes-agent — gateway/platforms/qqbot/adapter.py _strip_at_mention]`

**Important:** The QQ official GROUP_AT_MESSAGE_CREATE example shows `"content": " 123"` — the leading space suggests QQ may already strip the mention marker but leave whitespace. The normalizer should:
1. Strip leading `@<non-whitespace>` patterns (e.g., `@botname`, `@12345`)
2. Strip leading/trailing whitespace
3. Return empty string if content was only the mention

`[ASSUMED — based on QQ docs example + Hermes adapter pattern]`

For C2C_MESSAGE_CREATE, no @-mention stripping is needed (DM messages don't have @-bot prefix).

### INTERACTION_CREATE → FeedbackEvent Mapping

**`data.resolved.button_data` → `FeedbackAction` mapping:**

| button_data value | FeedbackAction | FeedbackEventType | Notes |
|-------------------|----------------|-------------------|-------|
| `up` | `UP` ("up") | `RATING` ("rating") | rating=1.0 |
| `down` | `DOWN` ("down") | `CORRECTION` ("correction") | |
| `needs_fix` | `NEEDS_FIX` ("needs_fix") | `CORRECTION` ("correction") | |
| `route_wrong` | `ROUTE_WRONG` ("route_wrong") | `ROUTE_MISMATCH` ("route_mismatch") | route_mismatch=True, skill_candidate set |

`[VERIFIED: .planning/REQUIREMENTS.md INGRESS-05 — "action mapped from button data.resolved.button_data (up/down/needs_fix/route_wrong)"]`

**The existing adapter.py already implements this mapping** in `_feedback_action()` (lines 359-372) and `_feedback_from_payload()` (lines 278-311). Phase 60 should extract this logic into `normalization.py` as a pure function, preserving the same alias mapping:

```python
aliases = {
    "thumbs_up": "up",
    "like": "up",
    "thumbs_down": "down",
    "dislike": "down",
    "fix": "needs_fix",
    "route_mismatch": "route_wrong",
}
```

`[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:359-372]`

**scene-aware conversation_id for INTERACTION_CREATE:**

| chat_type | scene | scene_id | user_openid |
|-----------|-------|----------|-------------|
| 2 (c2c) | `c2c` | `user_openid` | `user_openid` |
| 1 (group) | `group` | `group_openid` | `group_member_openid` |
| 0 (guild) | `guild` | `channel_id` | `data.resolved.user_id` |

`[CITED: bot.qq.com — msg-btn.html INTERACTION_CREATE field table]`

**Note:** Guild scene (chat_type=0) is out of scope for v1.8 (V2 PRD focuses on WeCom; QQ Bot guild features are deferred). The normalizer should handle c2c and group; guild can dispatch to unknown or be handled minimally.

### FeedbackEvent Required Fields

From the `FeedbackEvent` dataclass and JSON schema:

```python
@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    feedback_id: str          # REQUIRED — generate from event id if not provided
    turn_id: str              # REQUIRED — derive from message_id or generate stable id
    conversation_id: str      # REQUIRED — scene-aware qqbot:{scene}:{scene_id}:{user_openid}
    user_id: str              # REQUIRED — user_openid or group_member_openid
    source: FeedbackSource    # REQUIRED — "card_button" (frozen enum)
    event_type: FeedbackEventType  # REQUIRED — rating/correction/route_mismatch
    status: FeedbackStatus    # REQUIRED — "pending"
    created_at: str           # REQUIRED — from event timestamp or received_at
    action: FeedbackAction | None  # OPTIONAL — up/down/needs_fix/route_wrong
    # ... other optional fields
```

`[VERIFIED: packages/platform-contract/src/platform_contract/events.py:158-181, schemas/feedback_event.schema.json]`

### AgentTurn Required Fields

```python
@dataclass(frozen=True, slots=True)
class AgentTurn:
    turn_id: str              # REQUIRED — generate from message id
    conversation_id: str      # REQUIRED — scene-aware qqbot:{scene}:{scene_id}:{user_openid}
    channel: Channel          # REQUIRED — "qqbot"
    user_id: str              # REQUIRED — user_openid or member_openid
    message_type: MessageType # REQUIRED — "text"
    received_at: str          # REQUIRED — from event timestamp or received_at
    content: str | None       # OPTIONAL — stripped text content
    # ... other optional fields
```

`[VERIFIED: packages/platform-contract/src/platform_contract/events.py:125-137, schemas/agent_turn.schema.json]`

## Existing Code Insights

### FeedbackSource Enum (FROZEN — do NOT modify)

```python
class FeedbackSource(StrEnum):
    CARD_BUTTON = "card_button"
    TEXT_COMMAND = "text_command"
    WEB_FORM = "web_form"
    ADMIN_ANNOTATION = "admin_annotation"
```

`[VERIFIED: packages/platform-contract/src/platform_contract/enums.py:132-136]`

**Enforced by 3 tests:**
- `test_contract_freeze_not_violated.py:44-48` — asserts exactly 4 values
- `test_v1_8_safety_baseline.py:48-52` — asserts exactly 4 values
- `test_feedback_source_mapping.py:100-122` — asserts 4 values + no new members

`[VERIFIED: packages/channels/qqbot/tests/]`

### FeedbackAction Enum (FROZEN — do NOT modify)

```python
class FeedbackAction(StrEnum):
    UP = "up"
    DOWN = "down"
    NEEDS_FIX = "needs_fix"
    ROUTE_WRONG = "route_wrong"
```

`[VERIFIED: packages/platform-contract/src/platform_contract/enums.py:150-154]`

### Channel Enum (FROZEN — already has QQBOT)

```python
class Channel(StrEnum):
    WECOM = "wecom"
    QQBOT = "qqbot"
    WEB = "web"
    DESKTOP = "desktop"
```

`[VERIFIED: packages/platform-contract/src/platform_contract/enums.py:33-37]`

### ChannelAdapter Protocol (FROZEN — 6 methods)

```python
class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...
    def capabilities(self) -> ChannelCapabilitySet: ...
    async def verify_and_ack(self, raw: RawInbound) -> AckResponse: ...
    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized: ...
    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult: ...
    async def health(self) -> ComponentHealth: ...
```

`[VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py:208-219]`

**Enforced by:** `test_contract_freeze_not_violated.py:31-42` and `test_v1_8_safety_baseline.py:35-37` — both assert exactly 6 methods.

### test_no_wecom_import.py Isolation Invariant

The test uses AST inspection to verify no qqbot source file imports from `wecom_service`. Currently covers: `adapter.py`, `config.py`, `__init__.py`, `_ed25519.py`, `signature.py`.

**Phase 60 must add coverage for `normalization.py`** — add a test method like:

```python
def test_normalization_does_not_import_wecom_service(self) -> None:
    source = (PACKAGE_SRC / "normalization.py").read_text(encoding="utf-8")
    modules = _imported_modules(source)
    for module in modules:
        self.assertFalse(
            module.startswith("wecom_service"),
            f"normalization.py imports from wecom_service: {module}",
        )
```

`[VERIFIED: packages/channels/qqbot/tests/test_no_wecom_import.py — pattern for adding new module coverage]`

### WeCom normalization.py (REFERENCE ONLY — do NOT import)

The WeCom service has an analogous `normalization.py` with `normalize_wecom_turn()` and `normalize_wecom_feedback_callback()` functions. Key patterns to mirror (not copy):

1. **Pure functions** returning dict-shaped events (WeCom returns dicts; QQBot should return `AgentTurn`/`FeedbackEvent` dataclass instances to match the existing adapter pattern)
2. **`_required()` helper** — raises `ValueError` for missing required fields
3. **`_stable_id()` helper** — SHA-256 digest truncated to 16 chars for generated IDs
4. **`_feedback_action()` with alias mapping** — same alias dict used in both WeCom and existing QQBot adapter
5. **`_feedback_event_type()` mapping** — up→rating, route_wrong→route_mismatch, else→correction
6. **`raw_payload_ref` in metadata** — reference only, no raw payload storage
7. **Schema validation in tests** — `validate_event("agent_turn", event)` and `validate_event("feedback_event", event)`

`[VERIFIED: services/wecom-service/src/wecom_service/normalization.py — reference pattern, NOT imported]`

### How Phase 59 Output Feeds Phase 60

Phase 59's `verify_and_ack` method in `adapter.py` (lines 66-173) performs:
1. Signature verification (Ed25519 over `timestamp + request_body`)
2. op=13 validation challenge handling (signs `{event_ts + plain_token}`)
3. Returns `AckResponse` with `signature_status: "verified"` for valid non-op=13 payloads

After `verify_and_ack` succeeds, the host calls `normalize_inbound(raw: RawInbound)` with the same `RawInbound`. Phase 60's `normalization.py` is called from within `normalize_inbound` to parse the gateway envelope `{op, t, d}` from `raw.metadata["payload"]` (or `raw.metadata` itself) and produce `AgentTurn` or `FeedbackEvent`.

`[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:66-199 — verify_and_ack then normalize_inbound flow]`

**Key input:** The verified payload is available in `raw.metadata["payload"]` (a dict) or `raw.metadata["request_body"]` (bytes). Phase 60 should parse the JSON envelope from the payload dict. The raw body bytes are for signature verification only (Phase 59); Phase 60 works with the parsed JSON.

## Don't Hand-Roll

- **Envelope parsing:** Use structured dict access with type checking. Do NOT use ad hoc string parsing on JSON. `[VERIFIED: AGENTS.md — "Prefer structured parsers and schema validators"]`
- **Schema validation:** Use `contract_test_suite.schema_validation.validate_event()` in tests to verify normalized events satisfy the JSON Schema. `[VERIFIED: services/wecom-service/tests/test_normalization.py — pattern]`
- **Idempotency keys:** Use `channel_core.idempotency.channel_idempotency_key()` — do NOT re-implement digest logic. `[VERIFIED: packages/channel-core/src/channel_core/idempotency.py]`
- **Feedback action aliases:** Reuse the existing alias mapping from `adapter.py:359-372` (thumbs_up→up, like→up, etc.). Do NOT invent new aliases. `[VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:359-372]`
- **Feedback event type mapping:** Reuse the existing mapping: up→rating, route_wrong→route_mismatch, else→correction. `[VERIFIED: adapter.py:280, wecom-service/normalization.py:190-195]`
- **Stable ID generation:** Use SHA-256 digest truncated to 16 chars (existing `_stable_id` pattern). `[VERIFIED: adapter.py:413-415, wecom-service/normalization.py:205-207]`

## Common Pitfalls

1. **Importing from wecom_service:** The `test_no_wecom_import.py` test uses AST inspection. ANY import statement referencing `wecom_service` in `normalization.py` will fail the test. The WeCom normalization.py is a REFERENCE PATTERN only — re-implement the logic, do not import it. `[VERIFIED: packages/channels/qqbot/tests/test_no_wecom_import.py]`

2. **Adding new FeedbackSource enum values:** Three tests enforce the frozen 4-value enum. Do NOT add `QQBOT_BUTTON` or any new source. Use `FeedbackSource.CARD_BUTTON` (value `"card_button"`) which already exists. `[VERIFIED: test_contract_freeze_not_violated.py, test_v1_8_safety_baseline.py, test_feedback_source_mapping.py]`

3. **Modifying frozen Protocol/schemas:** Do NOT add methods to `ChannelAdapter`, fields to `AgentTurn`/`FeedbackEvent`, or values to any platform-contract enum. All QQ-specific data flows through `metadata` fields. `[VERIFIED: .planning/ROADMAP.md ADAPTER-04]`

4. **Breaking existing fixture tests:** The existing `qqbot_channel_loop.json` fixture and `test_qqbot_channel_loop.py` use a pre-normalized payload format (not real QQ Bot gateway envelopes). The refactored `normalize_inbound` must still handle this format OR the fixture must be updated with real envelope structure. **Recommendation:** Support both — detect if payload is a real gateway envelope (`has `{op, t, d}` keys`) vs. legacy fixture format, and dispatch accordingly. `[VERIFIED: packages/channels/qqbot/fixtures/qqbot_channel_loop.json, tests/test_qqbot_channel_loop.py]`

5. **`data.resoloved` typo:** The official QQ docs have a typo in the field table (`resoloved` instead of `resolved`), but the JSON example uses the correct spelling (`resolved`). The normalizer should look up `data.resolved.button_data` but defensively also check `data.resoloved.button_data`. `[CITED: bot.qq.com — msg-btn.html]`

6. **@-mention stripping edge cases:** Group message content may be:
   - `" 123"` (leading space after QQ strips mention marker)
   - `"@botname 123"` (raw mention text still present)
   - `""` (empty after stripping — should produce empty content, not crash)
   The stripper should handle all cases gracefully. `[CITED: bot.q.qq.com — event.html GROUP_AT_MESSAGE_CREATE example, github.com/NousResearch/hermes-agent _strip_at_mention]`

7. **scene_id for C2C:** In C2C_MESSAGE_CREATE, there is no `group_openid`. The scene_id is the `user_openid` itself (from `d.author.user_openid`). This means `conversation_id = qqbot:c2c:{user_openid}:{user_openid}` — the scene_id and user_openid are the same value for C2C. `[ASSUMED — derived from INGRESS-04 format + C2C payload structure]`

8. **INTERACTION_CREATE user identity:** For group scene, the user is `group_member_openid` (not `user_openid`). For c2c scene, the user is `user_openid`. The normalizer must select the correct field based on `chat_type`/`scene`. `[CITED: bot.qq.com — msg-btn.html field table]`

9. **turn_id derivation for INTERACTION_CREATE:** INTERACTION_CREATE does not have a direct `turn_id` — it references a message that was sent earlier. The `turn_id` should be derived from `data.resolved.message_id` (guild scene) or generated as a stable ID from the interaction event id. The existing adapter uses `_stable_id("qqbot-turn", raw.payload_ref)` as fallback. `[VERIFIED: adapter.py:284]`

10. **feedback_target for INTERACTION_CREATE:** The existing adapter requires `feedback_target` (line 291: `_required_string(payload, "feedback_target")`). For real INTERACTION_CREATE events, there is no explicit `feedback_target` field — it should be derived from `data.resolved.message_id` or the original message reference. The normalizer should make this optional or derive it from available fields. `[VERIFIED: adapter.py:291, CITED: bot.qq.com — msg-btn.html]`

11. **`dependencies = []` invariant:** Do NOT add any package to `pyproject.toml` dependencies. Use stdlib only (`json`, `re`, `hashlib`, `dataclasses`, `typing`, `datetime`). `[VERIFIED: packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`

12. **Raw payload storage:** Never store raw QQ Bot payload content in the normalized event. Use `raw_payload_ref` (a reference string) in metadata. The existing `_assert_no_forbidden_payload_keys()` in adapter.py (lines 375-385) rejects keys containing `rawpayload`, `rawbody`, `callbackbody`. `[VERIFIED: adapter.py:375-385, AGENTS.md privacy rules]`

## Code Examples

### normalization.py — Envelope Parser

```python
"""QQ Bot gateway envelope parser and event normalizer.

Parses the QQ Bot gateway envelope {op, t, d} into typed event categories
and normalizes C2C/group messages into AgentTurn and INTERACTION_CREATE
into FeedbackEvent. Pure functions — no network IO, no wecom_service import.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from platform_contract.enums import (
    Channel,
    FeedbackAction,
    FeedbackEventType,
    FeedbackSource,
    FeedbackStatus,
    MessageType,
)
from platform_contract.events import AgentTurn, FeedbackEvent, SkillCandidate

JsonObject = dict[str, Any]


class QQBotEventCategory(StrEnum):
    C2C_MESSAGE = "c2c_message"
    GROUP_AT_MESSAGE = "group_at_message"
    INTERACTION = "interaction"
    VALIDATION_CHALLENGE = "validation_challenge"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QQBotEvent:
    """Parsed QQ Bot gateway event."""
    category: QQBotEventCategory
    op: int
    event_type: str | None  # the `t` field
    data: Mapping[str, Any]  # the `d` field
    event_id: str | None  # the `id` field
    raw_payload_ref: str | None = None


def parse_envelope(payload: Mapping[str, Any]) -> QQBotEvent:
    """Parse a QQ Bot gateway envelope {op, t, d} into a typed event."""
    op = int(payload.get("op", -1))
    t = _optional_string(payload.get("t"))
    d = payload.get("d")
    if not isinstance(d, Mapping):
        d = {}
    event_id = _optional_string(payload.get("id"))

    # op=13 → validation challenge (already handled by signature.py)
    if op == 13:
        category = QQBotEventCategory.VALIDATION_CHALLENGE
    elif op == 0 and t == "C2C_MESSAGE_CREATE":
        category = QQBotEventCategory.C2C_MESSAGE
    elif op == 0 and t == "GROUP_AT_MESSAGE_CREATE":
        category = QQBotEventCategory.GROUP_AT_MESSAGE
    elif op == 0 and t == "INTERACTION_CREATE":
        category = QQBotEventCategory.INTERACTION
    else:
        category = QQBotEventCategory.UNKNOWN

    return QQBotEvent(
        category=category,
        op=op,
        event_type=t,
        data=d,
        event_id=event_id,
        raw_payload_ref=_optional_string(payload.get("raw_payload_ref")),
    )
```

### normalization.py — Message Event → AgentTurn

```python
def normalize_message_event(
    event: QQBotEvent,
    *,
    received_at: str,
    payload_ref: str | None = None,
) -> AgentTurn:
    """Normalize C2C_MESSAGE_CREATE or GROUP_AT_MESSAGE_CREATE into AgentTurn."""
    d = event.data

    if event.category == QQBotEventCategory.C2C_MESSAGE:
        scene = "c2c"
        user_openid = _required_string(d.get("author", {}), "user_openid")
        scene_id = user_openid
        content = _optional_string(d.get("content")) or ""
    elif event.category == QQBotEventCategory.GROUP_AT_MESSAGE:
        scene = "group"
        user_openid = _required_string(d.get("author", {}), "member_openid")
        scene_id = _required_string(d, "group_openid")
        raw_content = _optional_string(d.get("content")) or ""
        content = _strip_at_mention(raw_content)
    else:
        raise ValueError(f"normalize_message_event does not support {event.category}")

    message_id = _optional_string(d.get("id")) or ""
    conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"
    turn_id = _stable_id("qqbot-turn", message_id or conversation_id)

    return AgentTurn(
        turn_id=turn_id,
        conversation_id=conversation_id,
        channel="qqbot",
        user_id=user_openid,
        message_type="text",
        received_at=received_at,
        content=content if content else None,
        metadata={
            "source_event": event.event_type or "qqbot_message",
            "source_status": "sanitized_callback",
            "scene": scene,
            "scene_id": scene_id,
            "message_id": message_id,
            "raw_payload_ref": payload_ref or event.raw_payload_ref,
            "content_source_status": "stripped" if event.category == QQBotEventCategory.GROUP_AT_MESSAGE else "direct",
        },
    )


def _strip_at_mention(content: str) -> str:
    """Strip @bot mention prefix from group message content."""
    import re
    stripped = re.sub(r"^@\S+\s*", "", content.strip())
    return stripped.strip()
```

### normalization.py — INTERACTION_CREATE → FeedbackEvent

```python
def normalize_interaction_event(
    event: QQBotEvent,
    *,
    created_at: str,
    payload_ref: str | None = None,
) -> FeedbackEvent:
    """Normalize INTERACTION_CREATE into FeedbackEvent with source='card_button'."""
    d = event.data
    chat_type = int(d.get("chat_type", -1))

    # Determine scene and user identity from chat_type
    if chat_type == 2:  # c2c
        scene = "c2c"
        user_openid = _optional_string(d.get("user_openid")) or ""
        scene_id = user_openid
    elif chat_type == 1:  # group
        scene = "group"
        user_openid = _optional_string(d.get("group_member_openid")) or ""
        scene_id = _optional_string(d.get("group_openid")) or ""
    else:
        # guild (chat_type=0) or unknown — minimal handling
        scene = "guild"
        user_openid = _optional_string(d.get("data", {}).get("resolved", {}).get("user_id")) or ""
        scene_id = _optional_string(d.get("channel_id")) or ""

    # Extract button_data (handle doc typo "resoloved" vs "resolved")
    data_obj = d.get("data", {})
    resolved = data_obj.get("resolved") or data_obj.get("resoloved") or {}
    button_data = _optional_string(resolved.get("button_data")) or ""
    button_id = _optional_string(resolved.get("button_id"))

    action = _feedback_action(button_data)
    event_type = _feedback_event_type(action)
    interaction_id = _optional_string(d.get("id")) or event.event_id or ""
    conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"
    feedback_id = _stable_id("qqbot-feedback", interaction_id or conversation_id)
    turn_id = _stable_id("qqbot-turn", interaction_id)

    fields_map: JsonObject = {
        "feedback_id": feedback_id,
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "user_id": user_openid,
        "source": "card_button",  # FeedbackSource.CARD_BUTTON (frozen enum)
        "event_type": event_type,
        "status": "pending",
        "created_at": created_at,
        "action": action,
        "feedback_target": _optional_string(resolved.get("message_id")) or interaction_id,
        "metadata": {
            "source_event": "INTERACTION_CREATE",
            "source_status": "sanitized_callback",
            "scene": scene,
            "interaction_id": interaction_id,
            "button_id": button_id,
            "button_data": button_data,
            "chat_type": chat_type,
            "raw_payload_ref": payload_ref or event.raw_payload_ref,
            "no_auto_modify": action == "route_wrong",
        },
    }

    if action == "up":
        fields_map["rating"] = 1.0
    if action == "route_wrong":
        fields_map["route_mismatch"] = True
        fields_map["skill_candidate"] = SkillCandidate(
            detected=True,
            source="route_mismatch",
            proposed_name="qqbot.route_review_candidate",
            risk_level="high",
            requires_human_review=True,
            evidence=[payload_ref or event.raw_payload_ref or "", interaction_id],
            metadata={"no_auto_modify": True},
        )

    return _dataclass_from_mapping(FeedbackEvent, fields_map)
```

### Fixture File Structure (NEW fixtures for Phase 60)

Create new fixture files for real QQ Bot gateway envelopes:

```
packages/channels/qqbot/fixtures/
├── qqbot_channel_loop.json          # existing (legacy fixture format)
├── qqbot_c2c_message.json           # NEW: real C2C_MESSAGE_CREATE envelope
├── qqbot_group_at_message.json      # NEW: real GROUP_AT_MESSAGE_CREATE envelope
├── qqbot_interaction_create.json    # NEW: real INTERACTION_CREATE envelope
└── qqbot_validation_challenge.json  # NEW: op=13 validation challenge envelope
```

`[ASSUMED — fixture file names inferred from SC-5 "Fixture files and tests cover all event categories"]`

**Fixture example (qqbot_c2c_message.json):**

```json
{
  "fixture_id": "phase60-qqbot-c2c-message-001",
  "description": "Sanitized Phase 60 fixture: real QQ Bot C2C_MESSAGE_CREATE gateway envelope.",
  "not_live_acceptance": true,
  "evidence_scope": "sanitized_fixture_only",
  "raw_payload_policy": "raw_payload_ref_and_hashes_only",
  "envelope": {
    "op": 0,
    "t": "C2C_MESSAGE_CREATE",
    "id": "evt-c2c-001",
    "d": {
      "author": {
        "user_openid": "FIXTURE_USER_OPENID_C2C_001"
      },
      "content": "请检索合同解除的裁判观点",
      "id": "ROBOT1.0_fixture_c2c_msg_001",
      "timestamp": "2026-07-07T12:00:00+08:00",
      "attachments": []
    }
  },
  "expected_agent_turn": {
    "conversation_id": "qqbot:c2c:FIXTURE_USER_OPENID_C2C_001:FIXTURE_USER_OPENID_C2C_001",
    "channel": "qqbot",
    "user_id": "FIXTURE_USER_OPENID_C2C_001",
    "message_type": "text",
    "content": "请检索合同解除的裁判观点",
    "metadata": {
      "scene": "c2c",
      "source_event": "C2C_MESSAGE_CREATE"
    }
  }
}
```

`[ASSUMED — fixture structure follows existing qqbot_channel_loop.json pattern + real QQ Bot envelope structure]`

## Validation Architecture

### Test Files

1. **`tests/test_normalization.py`** (NEW) — Unit tests for `normalization.py`:
   - `parse_envelope()` correctly categorizes all event types (C2C, GROUP_AT_MESSAGE, INTERACTION, VALIDATION_CHALLENGE, UNKNOWN)
   - `normalize_message_event()` for C2C: correct `conversation_id`, `user_id`, `content`, `channel="qqbot"`
   - `normalize_message_event()` for GROUP_AT_MESSAGE: @-bot prefix stripped, correct `conversation_id` with `group_openid` as scene_id
   - `normalize_interaction_event()` for c2c scene (chat_type=2): correct `source="card_button"`, `action` mapped from `button_data`
   - `normalize_interaction_event()` for group scene (chat_type=1): correct user identity from `group_member_openid`
   - All 4 feedback actions (up/down/needs_fix/route_wrong) mapped correctly
   - `route_wrong` action produces `route_mismatch=True` + `skill_candidate`
   - `up` action produces `rating=1.0`
   - Schema validation: `validate_event("agent_turn", ...)` and `validate_event("feedback_event", ...)` pass
   - Edge cases: empty content, missing fields, unknown event type, `data.resoloved` typo fallback

2. **`tests/test_normalization_fixtures.py`** (NEW) — Fixture-driven tests:
   - Load each new fixture file, parse envelope, normalize, verify against expected fields
   - Covers all event categories (C2C, GROUP_AT_MESSAGE, INTERACTION, VALIDATION_CHALLENGE)

3. **`tests/test_no_wecom_import.py`** (MODIFIED) — Add coverage for `normalization.py`:
   - New test method `test_normalization_does_not_import_wecom_service`

4. **Existing tests must remain green:**
   - `test_v1_8_safety_baseline.py` — `dependencies = []`, 6 Protocol methods, 4 FeedbackSource values
   - `test_contract_freeze_not_violated.py` — frozen contract surfaces unchanged
   - `test_feedback_source_mapping.py` — QQBot feedback maps to CARD_BUTTON
   - `test_qqbot_channel_loop.py` — existing fixture loop still works
   - `test_qqbot_channel_adapter.py` — adapter tests
   - `test_qqbot_idempotency.py` — idempotency tests
   - `test_feature_flag.py` — flag default-off
   - `test_signature.py` — Phase 59 signature tests
   - `test_ed25519_vectors.py` — Ed25519 known-answer tests

`[ASSUMED — test file structure follows Phase 59 pattern + SC-5 "Fixture files and tests cover all event categories"]`

### Schema Validation in Tests

Follow the WeCom normalization test pattern — validate every normalized event against the JSON Schema:

```python
from contract_test_suite.schema_validation import validate_event

def test_c2c_message_normalizes_to_schema_valid_agent_turn(self):
    event = parse_envelope(fixture["envelope"])
    turn = normalize_message_event(event, received_at="2026-07-07T04:00:00Z",
                                    payload_ref="fixture://qqbot/phase60/c2c-001")
    # Convert dataclass to dict for schema validation
    turn_dict = dataclass_to_dict(turn)
    validate_event("agent_turn", turn_dict, fixture_id="phase60-c2c")
```

`[VERIFIED: services/wecom-service/tests/test_normalization.py:14-31 — pattern for schema validation in tests]`

### V2 Gate Verification

Run `python3 scripts/run_v2_gates.py` to verify all 24+ V2 gates remain green (ADAPTER-04). Phase 59 Plan 02 confirmed 26 gates green. `[VERIFIED: .planning/phases/59-ed25519-signature-verification-validation-challenge/59-02-SUMMARY.md — 26/26 gates green]`

## Summary of Key Decisions for the Planner

1. **Create `normalization.py`** as a new module in `packages/channels/qqbot/src/inkstatute_channels_qqbot/`. Pure functions, no network IO, no wecom_service import. Contains: `QQBotEventCategory` enum, `QQBotEvent` dataclass, `parse_envelope()`, `normalize_message_event()`, `normalize_interaction_event()`.

2. **Parse gateway envelope `{op, t, d}`** into 5 typed categories: C2C_MESSAGE, GROUP_AT_MESSAGE, INTERACTION, VALIDATION_CHALLENGE, UNKNOWN. op=0 Dispatch with `t` field determines message/interaction type; op=13 is validation challenge.

3. **Scene-aware `conversation_id`** format: `qqbot:{scene}:{scene_id}:{user_openid}` where scene is `c2c` or `group`, scene_id is `user_openid` (C2C) or `group_openid` (group), user_openid is `user_openid` (C2C) or `member_openid` (group).

4. **@-bot prefix stripping** for GROUP_AT_MESSAGE_CREATE: use `re.sub(r"^@\S+\s*", "", content.strip())` to strip @-mention, then strip whitespace. C2C messages need no stripping.

5. **INTERACTION_CREATE → FeedbackEvent** with `source="card_button"` (frozen `FeedbackSource.CARD_BUTTON` enum, NO new enum values). `action` mapped from `data.resolved.button_data` via alias mapping (up/down/needs_fix/route_wrong). Handle `data.resoloved` typo defensively.

6. **Refactor `adapter.py` `normalize_inbound`** to delegate to `normalization.py` for real gateway envelopes while preserving backward compatibility with existing fixture format.

7. **Create 4 new fixture files** covering all event categories: C2C message, group @-message, interaction create, validation challenge. Use sanitized fixture values (no real openids, no raw payloads).

8. **Add `normalization.py` to `test_no_wecom_import.py`** coverage via AST inspection.

9. **Schema-validate** all normalized events in tests using `contract_test_suite.schema_validation.validate_event()`.

10. **No new dependencies** — stdlib only (`json`, `re`, `hashlib`, `dataclasses`, `typing`, `datetime`). `dependencies = []` invariant holds.
