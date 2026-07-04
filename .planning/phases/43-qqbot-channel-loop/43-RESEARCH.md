# Phase 43: QQBot Channel Loop — Technical Research

**Phase:** 43 — QQBot Channel Loop
**Requirements:** QQBOT-01, QQBOT-02, QQBOT-03, QQBOT-04
**Researched:** 2026-07-04
**Status:** Complete

## 1. Existing wecom-service Channel Logic

The channel-generic logic named in QQBOT-01 lives in four modules inside `services/wecom-service/src/wecom_service/`:

### 1.1 idempotency.py (44 lines)

- **Public function:** `wecom_idempotency_key(callback: Mapping[str, Any]) -> str`
- **Logic:** Derives a stable SHA-256 digest from the first available stable field (message_id, callback_id, feedback_id), falling back to a composite digest of channel/user/conversation/time/event fields.
- **WeCom-specific aspects:** The function name (`wecom_idempotency_key`), the `wecom:` key prefix, and the WeCom-specific field aliases (`msg_id`, `MsgId`, `FromUserName`, `ChatId`, `CreateTime`, `MsgType`, `Event`).
- **Generic aspects:** The `_digest()` and `_string()` helpers and the stable-fields-then-fallback pattern are channel-neutral.
- **Dependencies:** None (stdlib only — `hashlib`).

### 1.2 delivery_guard.py (90 lines)

- **Public types:** `DeliveryCompletionAssessment` (frozen dataclass), `assess_delivery_completion(*, user_text, answer_text, media_count, file_count)`.
- **Logic:** Fails closed when a file-delivery task returns only a progress sentence without an artifact. Uses regex patterns for file-request detection, delivery markers, progress-only sentences, and final-failure markers.
- **WeCom-specific aspects:** None — the function signature and logic are entirely channel-neutral. The patterns reference Chinese legal document terms (docx, word, 修订稿) but these are task-domain terms, not channel terms.
- **Dependencies:** `re`, `dataclasses` (stdlib only).

### 1.3 active_task_router.py (195 lines)

- **Public types:** `ActiveTaskRoute` (StrEnum), `AdapterTaskCapabilities` (frozen dataclass), `ActiveTaskRoutingDecision` (frozen dataclass), `route_active_task_turn(*, text, active_task, capabilities, raw_payload_ref)`.
- **Logic:** Classifies a follow-up turn during an active task into STATUS_REQUEST, CANCEL_REQUEST, TASK_UPDATE, NEW_PARALLEL_TASK, or UNSUPPORTED_UPDATE_ACK based on intent classification (regex) and adapter capabilities.
- **WeCom-specific aspects:** The `as_event()` method hardcodes `"event": "wecom_active_task_route"`. Everything else is channel-neutral.
- **Dependencies:** `hashlib`, `re`, `dataclasses`, `enum` (stdlib only).

### 1.4 output_policy.py (102 lines)

- **Public types:** `OutputPolicyDecision` (frozen dataclass), `apply_output_policy(message: str)`.
- **Logic:** Classifies backend output as block/rewrite/allow before user-facing delivery. Blocks internal/secret-bearing notices, rewrites backend-lifecycle notices to InkStatute-owned notices, allows business output.
- **WeCom-specific aspects:** The audit metadata uses `"policy": "inkstatute_wecom_output_boundary"`. The block/rewrite patterns are channel-neutral (they filter backend noise, not channel-specific content).
- **Dependencies:** Imports `build_owned_notice` from `.owned_notices`.

### 1.5 owned_notices.py (129 lines) — dependency of output_policy

- **Public types:** `NoticeKind` (Literal), `OWNED_NOTICE_TEMPLATES` (dict), `build_owned_notice(kind, *, seed)`.
- **Logic:** InkStatute-owned short Chinese user notices for various notice kinds (processing, blocked, failed, timeout, backend_lifecycle, etc.).
- **WeCom-specific aspects:** The notices are user-facing text in Chinese — they are InkStatute-owned, not WeCom-specific. They apply to any channel serving ordinary users.
- **Dependencies:** `hashlib`, `secrets` (stdlib only).

### 1.6 WeCom-specific modules that stay in wecom-service

The following modules are WeCom-specific and remain in `wecom-service`:
- `protocol.py` — WeCom callback signature verification, XML parsing, WeCom field aliases
- `normalization.py` — WeCom callback → AgentTurn/FeedbackEvent normalization (uses idempotency + protocol)
- `sender.py` — WeCom send envelope builders (text/file/card) using output_policy
- `session_runtime.py` — WeCom session lifecycle
- `ingress_runtime.py` — WeCom callback-to-runtime orchestration
- `task_flow.py` — WeCom task flow stages
- `agent_backend.py` — agent backend selection
- `runtime_audit.py` — runtime audit helpers
- `memory_factory.py`, `memory_integration.py` — memory wiring

## 2. ChannelAdapter Protocol (6 methods — frozen)

Defined in `packages/platform-runtime/src/platform_runtime/protocols.py:208-219`:

```python
class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...
    def capabilities(self) -> ChannelCapabilitySet: ...
    async def verify_and_ack(self, raw: RawInbound) -> AckResponse: ...
    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized: ...
    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult: ...
    async def health(self) -> ComponentHealth: ...
```

**Method count:** 6 — frozen by `test_contract_count_freeze.py` (`CHANNEL_ADAPTER_METHOD_COUNT = 6`).

**Supporting dataclasses** (also in protocols.py, not frozen by count test but must not be modified during contract freeze):
- `RawInbound` — channel_id, payload_ref, received_at, idempotency_key, metadata
- `AckResponse` — accepted, status_code, idempotency_key, metadata
- `InboundNormalized` — message (AgentTurn | None), feedback (FeedbackEvent | None), metadata
- `ChannelCapabilitySet` — supports_text, supports_files, supports_cards, supports_images, supports_voice, supports_streaming, ack_deadline_ms, idempotency_strategy, metadata
- `ChannelDelivery` — delivery_id, channel_id, run_id, result, content, artifact_refs, metadata
- `DeliveryResult` — delivery_id, accepted, delivered_at, idempotency_key, metadata
- `ComponentHealth` — ok, component_id, checked_at, detail, metadata

## 3. Existing ChannelAdapter Implementations

### 3.1 packages/channels/wecom/ (WeComChannelAdapter)

- **Location:** `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py`
- **Config:** `WeComChannelConfig` — channel_id="wecom", enabled=False, token/aes/corp secret refs
- **Imports from wecom_service:** `normalize_wecom_turn`, `normalize_wecom_feedback_callback`, `parse_callback_envelope`, `ack_response`, `build_text_send_envelope`, `build_file_send_envelope`, `build_template_card_envelope`
- **Pattern:** `_callback_from_raw()` extracts callback dict from `RawInbound.metadata`, then delegates to wecom_service normalization/sender functions.
- **Note:** The WeCom channel adapter imports from wecom_service — this is acceptable for the WeCom channel. QQBot must NOT follow this pattern.

### 3.2 packages/channels/web_sse/ (WebSseChannelAdapter)

- **Location:** `packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py`
- **Config:** `WebSseChannelConfig` — channel_id="web", enabled=False, session_secret_ref
- **Imports from wecom_service:** None — fully self-contained. Uses `platform_contract` and `platform_runtime` only.
- **Pattern:** Self-contained payload parsing, feedback normalization, delivery recording. No wecom_service dependency.
- **Fixture:** `packages/channels/web_sse/fixtures/multichannel_web_sse.json` — full end-to-end fixture with inbound, run lifecycle, SSE frames, delivery, feedback callback, feedback event, capabilities, health.
- **This is the closest reference pattern for QQBot** — a self-contained channel adapter that does NOT import from wecom_service.

### 3.3 Gate coverage gap

`packages/channels/` is NOT registered in `scripts/run_v2_gates.py`. The existing wecom and web_sse channel tests run only via the `contract-test-suite` gate (which includes their src in PYTHONPATH for cross-package tests) and via `test_phase12_channel_client_surface.py` (which loads fixtures and checks config). Phase 43 Wave 3 adds a dedicated `qqbot-channel` gate.

## 4. FeedbackEvent.source Enum Values (existing — must not add new)

Defined in `packages/platform-contract/src/platform_contract/enums.py:132-136`:

```python
class FeedbackSource(StrEnum):
    CARD_BUTTON = "card_button"
    TEXT_COMMAND = "text_command"
    WEB_FORM = "web_form"
    ADMIN_ANNOTATION = "admin_annotation"
```

**QQBot feedback mapping (no new enum values):**
- QQBot card button clicks (thumbs up/down, needs_fix, route_wrong) → `FeedbackSource.CARD_BUTTON` ("card_button") — same as WeCom card button feedback.
- QQBot text-command feedback (if any) → `FeedbackSource.TEXT_COMMAND` ("text_command").
- The web_sse adapter uses `WEB_FORM` ("web_form") for its feedback — QQBot does NOT use this value.

**Contract freeze constraint (SAFETY-02, SAFETY-06):** The `FeedbackSource` enum is in `packages/platform-contract/src/platform_contract/enums.py` — a frozen contract file. Phase 43 must NOT add, remove, or modify any enum values.

## 5. Channel Enum (QQBOT already exists)

Defined in `packages/platform-contract/src/platform_contract/enums.py:33-37`:

```python
class Channel(StrEnum):
    WECOM = "wecom"
    QQBOT = "qqbot"
    WEB = "web"
    DESKTOP = "desktop"
```

`Channel.QQBOT = "qqbot"` already exists — no enum changes needed. The QQBot adapter uses `channel_id="qqbot"`.

## 6. Feature Flag (qqbot_channel_enabled — already exists, defaults False)

Defined in `packages/platform-runtime/src/platform_runtime/feature_flags.py:23`:

```python
qqbot_channel_enabled: bool = False
```

The flag already exists with default `False`. Phase 43 does NOT modify `feature_flags.py` (contract freeze). Wave 3 verifies the default-off behavior and that the QQBot adapter refuses requests when the flag is off.

## 7. Shared Package Extraction Strategy

### 7.1 New package: packages/channel-core/

Create `packages/channel-core/` with the channel-generic logic extracted from wecom-service:

```
packages/channel-core/
  pyproject.toml          (name: inkstatute-channel-core, dependencies = [])
  README.md
  src/channel_core/
    __init__.py           (public API surface)
    idempotency.py        (generic idempotency key helpers)
    delivery_guard.py     (DeliveryCompletionAssessment, assess_delivery_completion)
    active_task_router.py (ActiveTaskRoute, AdapterTaskCapabilities, ActiveTaskRoutingDecision, route_active_task_turn)
    output_policy.py      (OutputPolicyDecision, apply_output_policy)
    owned_notices.py      (NoticeKind, OWNED_NOTICE_TEMPLATES, build_owned_notice)
  tests/
    __init__.py
    test_idempotency.py
    test_delivery_guard.py
    test_active_task_router.py
    test_output_policy.py
```

### 7.2 What gets extracted (channel-generic)

| Module | Extracted to channel-core | WeCom-specific aspects to handle |
|--------|--------------------------|--------------------------------|
| `idempotency.py` | `_digest()`, `_string()`, generic `channel_idempotency_key(callback, *, channel_prefix, field_aliases)` | WeCom keeps `wecom_idempotency_key` as a thin wrapper calling channel-core with WeCom field aliases and `channel_prefix="wecom"` |
| `delivery_guard.py` | Pure extraction — no WeCom-specific aspects | None — move verbatim |
| `active_task_router.py` | Core logic + parameterized event name | `as_event()` gets an `event_name` parameter (default `"channel_active_task_route"`); WeCom passes `"wecom_active_task_route"` for backward compat |
| `output_policy.py` | `apply_output_policy()` + block/rewrite patterns | Audit metadata `policy` field parameterized (default `"inkstatute_channel_output_boundary"`); WeCom passes `"inkstatute_wecom_output_boundary"` |
| `owned_notices.py` | Pure extraction — notices are InkStatute-owned, not WeCom-specific | None — move verbatim |

### 7.3 Backward compatibility strategy for wecom-service

After extraction, wecom-service modules become thin re-export shims:

- `wecom_service/idempotency.py` → imports `channel_core.idempotency` helpers, defines `wecom_idempotency_key` as a wrapper, re-exports.
- `wecom_service/delivery_guard.py` → `from channel_core.delivery_guard import DeliveryCompletionAssessment, assess_delivery_completion`.
- `wecom_service/active_task_router.py` → imports from `channel_core.active_task_router`, re-exports with WeCom event name default.
- `wecom_service/output_policy.py` → imports from `channel_core.output_policy`, re-exports with WeCom policy name default.
- `wecom_service/owned_notices.py` → `from channel_core.owned_notices import *`.
- `wecom_service/__init__.py` → unchanged public API surface (all existing symbols still importable from `wecom_service`).

**Existing wecom-service tests must pass unchanged** — the public API surface is identical; only internal import paths change.

### 7.4 What stays in wecom-service

- `protocol.py` — WeCom callback signature verification, XML parsing
- `normalization.py` — WeCom callback normalization (uses channel-core idempotency + wecom protocol)
- `sender.py` — WeCom send envelopes (uses channel-core output_policy)
- `session_runtime.py`, `ingress_runtime.py`, `task_flow.py`, `agent_backend.py`, `runtime_audit.py`, `memory_*.py`

## 8. QQBot Channel Adapter Design

### 8.1 Package structure

```
packages/channels/qqbot/
  pyproject.toml          (name: inkstatute-channels-qqbot, dependencies = [])
  README.md
  src/inkstatute_channels_qqbot/
    __init__.py           (QQBotChannelAdapter, QQBotChannelConfig)
    adapter.py            (QQBotChannelAdapter — 6 ChannelAdapter methods)
    config.py             (QQBotChannelConfig — channel_id="qqbot", enabled=False)
  tests/
    __init__.py
    test_qqbot_channel_adapter.py
  fixtures/
    qqbot_channel_loop.json
```

### 8.2 QQBotChannelConfig

```python
@dataclass(frozen=True, slots=True)
class QQBotChannelConfig:
    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None        # secret ref only
    app_secret_ref: str | None = None    # secret ref only
    token_secret_ref: str | None = None  # secret ref only
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "QQBotChannelConfig": ...
```

- Defaults to `enabled=False`.
- Carries only secret references — no raw secrets.

### 8.3 QQBotChannelAdapter — 6 methods

1. **`channel_id()` → "qqbot"**
2. **`capabilities()` → ChannelCapabilitySet** — supports_text=True, supports_files=False, supports_cards=True, supports_streaming=False, ack_deadline_ms=3000, idempotency_strategy="qqbot_callback_metadata"
3. **`verify_and_ack(raw)` → AckResponse** — QQBot callback verification (single mode / webhook). Returns accepted=True when enabled, status_code=200, idempotency_key from raw. No network IO.
4. **`normalize_inbound(raw)` → InboundNormalized** — Parses QQBot callback payload from `raw.metadata`. If feedback payload → FeedbackEvent (source=CARD_BUTTON). If message payload → AgentTurn (channel="qqbot"). Uses channel-core idempotency for key derivation. Does NOT import from wecom_service.
5. **`deliver(delivery)` → DeliveryResult** — Builds QQBot text send envelope. Applies channel-core output_policy. Supports text delivery (single mode). Card delivery for feedback cards.
6. **`health()` → ComponentHealth** — Returns ok=enabled, component_id="qqbot-channel".

### 8.4 Import constraints

QQBot adapter imports:
- `platform_contract.events` — AgentTurn, FeedbackEvent, SkillCandidate, etc.
- `platform_runtime.protocols` — RawInbound, AckResponse, InboundNormalized, ChannelCapabilitySet, ChannelDelivery, DeliveryResult, ComponentHealth
- `channel_core.idempotency` — generic idempotency key helper
- `channel_core.output_policy` — apply_output_policy for delivery boundary

QQBot adapter does NOT import:
- `wecom_service.*` — forbidden by QQBOT-01
- `wecom_service.normalization` — forbidden
- `wecom_service.protocol` — forbidden
- `wecom_service.sender` — forbidden

## 9. Fixture-Driven Loop Proof Design (QQBOT-03)

### 9.1 Fixture: packages/channels/qqbot/fixtures/qqbot_channel_loop.json

A self-contained JSON fixture proving the full receive → ACK → adapter → reply → card → feedback loop:

```
qqbot_inbound (message callback)
  → verify_and_ack (ACK)
  → normalize_inbound (AgentTurn)
  → deliver (text reply)
  → deliver (feedback card)
  → qqbot_feedback_callback (card button callback)
  → normalize_inbound (FeedbackEvent, source=card_button)
```

Fixture fields:
- `fixture_id`, `description`, `not_live_acceptance: true`, `evidence_scope: "sanitized_fixture_only"`
- `qqbot_inbound` — RawInbound-shaped message callback with payload metadata
- `ack` — expected AckResponse (accepted, status_code, idempotency_key)
- `agent_turn` — expected AgentTurn after normalization (channel="qqbot")
- `text_delivery` — ChannelDelivery for text reply
- `text_delivery_result` — expected DeliveryResult
- `card_delivery` — ChannelDelivery for feedback card
- `card_delivery_result` — expected DeliveryResult
- `qqbot_feedback_callback` — RawInbound-shaped feedback callback
- `feedback_event` — expected FeedbackEvent (source="card_button", event_type, action, status="pending")
- `channel_capabilities` — expected ChannelCapabilitySet
- `channel_health` — expected ComponentHealth

### 9.2 Loop proof test: test_qqbot_channel_loop.py

Test class `QQBotChannelLoopTests`:
1. **receive → ACK:** `verify_and_ack(qqbot_inbound_raw)` → assert accepted=True, idempotency_key matches, status_code=200
2. **ACK → adapter (normalize):** `normalize_inbound(qqbot_inbound_raw)` → assert AgentTurn with channel="qqbot", conversation_id, user_id, message_type="text"
3. **adapter → reply (text deliver):** `deliver(text_delivery)` → assert DeliveryResult accepted=True, message_type="text", output_policy action="allow"
4. **reply → card (card deliver):** `deliver(card_delivery)` → assert DeliveryResult accepted=True, message_type="card"
5. **card → feedback (normalize feedback):** `normalize_inbound(feedback_raw)` → assert FeedbackEvent with source="card_button", event_type, action, status="pending"
6. **idempotency:** Repeat `verify_and_ack` with same raw → same idempotency_key (idempotent). Repeat `normalize_inbound` with same raw → same AgentTurn turn_id (idempotent).
7. **No wecom_service import:** Assert `inkstatute_channels_qqbot` module source does not contain `wecom_service` import.
8. **FeedbackEvent.source mapping:** Assert feedback_event.source == "card_button" (existing enum value, no new values).

## 10. V2 Gate Integration Approach

### 10.1 Current gate count: 14

Phase 42 added the `admin-console-api` gate (gate #14). Phase 43 adds:
- A new `qqbot-channel` gate (gate #15) running `unittest discover` on `packages/channels/qqbot/tests`
- `channel_core_src` added to PYTHONPATH for `wecom-service` gate, `contract-test-suite` gate, and the new `qqbot-channel` gate
- `packages/channel-core/src` and `packages/channels/qqbot/src` added to `compileall`

### 10.2 Gate PYTHONPATH dependencies

- `qqbot-channel` gate: `qqbot_src, channel_core_src, platform_src, platform_runtime_src`
- `wecom-service` gate: add `channel_core_src` (wecom-service now imports from channel-core)
- `contract-test-suite` gate: add `channel_core_src, qqbot_src` (cross-package contract tests)

### 10.3 Contract freeze verification (SAFETY-02, SAFETY-06)

Wave 3 adds/extends tests verifying:
- `CHANNEL_ADAPTER_METHOD_COUNT = 6` — unchanged
- `BACKEND_ADAPTER_METHOD_COUNT = 9` — unchanged
- `ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14` — unchanged
- `FeedbackSource` enum values unchanged (4 values: card_button, text_command, web_form, admin_annotation)
- `Channel` enum includes QQBOT="qqbot" (already exists)
- No files in `packages/platform-contract/src/` modified during Phase 43
- `packages/platform-runtime/src/platform_runtime/protocols.py` not modified
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` not modified

## 11. QQBOT-04 Requirement Mapping

QQBOT-04 is not a formal entry in `REQUIREMENTS.md` (which lists QQBOT-01, QQBOT-02, QQBOT-03). It corresponds to success criterion #4: "Operator can verify that `qqbot_channel_enabled` defaults to `False` and that QQ Bot feedback maps to existing `FeedbackEvent.source` enum values without adding new enum values."

This maps to existing formal requirements:
- **SAFETY-04** — all M2 feature flags default to False (includes `qqbot_channel_enabled`)
- **SAFETY-02** — contract-count freeze (ChannelAdapter 6 methods)
- **SAFETY-06** — contract freeze baseline hash (no platform-contract modifications)

Wave 3 verifies QQBOT-04 through feature-flag default tests and FeedbackEvent.source enum assertion tests.

## 12. Key Constraints Summary

1. **Contract freeze:** No edits to `packages/platform-contract/` or `packages/platform-runtime/protocols.py` or `packages/platform-runtime/src/platform_runtime/feature_flags.py`.
2. **No wecom_service imports in QQBot:** `packages/channels/qqbot/` must not import from `wecom_service`. It imports from `channel_core`, `platform_contract`, and `platform_runtime` only.
3. **Backward compatibility:** wecom-service public API surface unchanged — existing tests pass.
4. **Feature flag:** `qqbot_channel_enabled` defaults to `False` (already exists, not modified).
5. **FeedbackEvent.source:** QQBot maps to `CARD_BUTTON` (existing) — no new enum values.
6. **Privacy:** No literal secrets in plan files. Use `REDACTED` or short placeholders (< 12 chars).
7. **ChannelAdapter 6 methods:** QQBot implements all 6 — channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health.
