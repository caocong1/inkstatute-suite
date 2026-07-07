# Phase 60: QQ Event Normalization — Pattern Mapping

**Phase:** 60 — QQ Event Normalization
**Output:** Concrete code excerpts and analog mappings for the planner.
**Status:** Complete

## Files To Create / Modify

| # | File | Role | Action |
|---|------|------|--------|
| 1 | `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` | Envelope parser + event normalizer (pure functions) | NEW |
| 2 | `packages/channels/qqbot/tests/test_normalization.py` | Unit tests for `normalization.py` | NEW |
| 3 | `packages/channels/qqbot/tests/test_adapter_normalize.py` | Adapter delegation tests (`normalize_inbound` → `normalization.py`) | NEW |
| 4 | `packages/channels/qqbot/fixtures/qqbot_c2c_message.json` | C2C_MESSAGE_CREATE envelope fixture | NEW |
| 5 | `packages/channels/qqbot/fixtures/qqbot_group_at_message.json` | GROUP_AT_MESSAGE_CREATE envelope fixture | NEW |
| 6 | `packages/channels/qqbot/fixtures/qqbot_interaction_create.json` | INTERACTION_CREATE envelope fixture | NEW |
| 7 | `packages/channels/qqbot/fixtures/qqbot_validation_challenge.json` | op=13 validation challenge envelope fixture | NEW |
| 8 | `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` | Delegate `normalize_inbound` to `normalization.py` | MODIFY |
| 9 | `packages/channels/qqbot/tests/test_no_wecom_import.py` | Add `normalization.py` AST import-isolation coverage | MODIFY |

> **Fixture location note:** The VALIDATION.md front matter references `tests/fixtures/`, but the existing codebase convention is `packages/channels/qqbot/fixtures/` (package root, NOT under `tests/`). The existing `qqbot_channel_loop.json` lives there and `test_qqbot_channel_loop.py` resolves it via `Path(__file__).resolve().parents[1] / "fixtures"`. New fixtures MUST follow the existing convention (`packages/channels/qqbot/fixtures/`) to stay consistent.

---

## File 1: `normalization.py` (NEW)

### Closest Analog: `services/wecom-service/src/wecom_service/normalization.py` (REFERENCE ONLY — must NOT import)

The WeCom `normalization.py` is the structural template. The QQBot `normalization.py` must **re-implement** the same patterns (not import them) because `test_no_wecom_import.py` uses AST inspection to reject any `wecom_service` import.

**Key differences from the WeCom analog:**
- WeCom returns **dict-shaped** events; QQBot must return **`AgentTurn`/`FeedbackEvent` dataclass instances** (matching the existing `adapter.py` pattern).
- WeCom parses via `parse_callback_envelope()`; QQBot parses the gateway envelope `{op, t, d}` directly.
- QQBot adds envelope-category dispatch (`QQBotEventCategory` enum) — no WeCom equivalent.

### Pattern: Module Header + Imports (stdlib + platform_contract only)

**Source:** `services/wecom-service/src/wecom_service/normalization.py:1-10`
```python
"""Normalize sanitized WeCom callbacks into platform contract event dictionaries."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .idempotency import wecom_idempotency_key
from .protocol import parse_callback_envelope
```

**QQBot adaptation** — use `platform_contract` imports (NOT `wecom_service`), no relative `wecom_service` imports:
```python
"""QQ Bot gateway envelope parser and event normalizer.

Parses the QQ Bot gateway envelope {op, t, d} into typed event categories
and normalizes C2C/group messages into AgentTurn and INTERACTION_CREATE
into FeedbackEvent. Pure functions — no network IO, no wecom_service import.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from platform_contract.events import AgentTurn, FeedbackEvent, SkillCandidate
```

> **Constraint:** `dependencies = []` in `pyproject.toml` — stdlib only (`hashlib`, `re`, `dataclasses`, `enum`, `typing`). `[VERIFIED: packages/channels/qqbot/pyproject.toml:15, test_v1_8_safety_baseline.py:58-61]`

### Pattern: `_stable_id()` helper (SHA-256 truncated to 16 chars)

**Source:** `services/wecom-service/src/wecom_service/normalization.py:205-207` and `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:413-415`
```python
def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"
```

> The QQBot `adapter.py` already has this exact helper at line 413-415. The new `normalization.py` should replicate it (or import from a shared internal helper — but since `adapter.py` is in the same package, `normalization.py` could import it from `.adapter` if desired; however, to keep `normalization.py` standalone and avoid circular imports, re-declare the helper locally).

### Pattern: `_required()` / `_optional_string()` helpers

**Source:** `services/wecom-service/src/wecom_service/normalization.py:198-202, 214-218` and `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:401-411`
```python
# adapter.py:401-411 (existing QQBot helpers)
def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = _optional_string(values.get(key))
    if value is None:
        raise ValueError(f"QQBot payload requires {key}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None
```

### Pattern: `_feedback_action()` with alias mapping (REUSE existing aliases)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:359-372`
```python
def _feedback_action(payload: Mapping[str, Any]) -> str:
    action = (_optional_string(payload.get("action")) or "needs_fix").split(":")[-1].lower()
    aliases = {
        "thumbs_up": "up",
        "like": "up",
        "thumbs_down": "down",
        "dislike": "down",
        "fix": "needs_fix",
        "route_mismatch": "route_wrong",
    }
    action = aliases.get(action, action)
    if action not in {"up", "down", "needs_fix", "route_wrong"}:
        raise ValueError(f"unsupported QQBot feedback action {action!r}")
    return action
```

> **Do NOT invent new aliases.** The QQBot `normalization.py` should accept a raw `button_data` string and apply the same alias dict. The WeCom version at `wecom_service/normalization.py:168-187` uses the same alias mapping.

### Pattern: `_feedback_event_type()` mapping

**Source:** `services/wecom-service/src/wecom_service/normalization.py:190-195` and `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:280`
```python
# wecom-service/normalization.py:190-195
def _feedback_event_type(action: str) -> str:
    if action == "up":
        return "rating"
    if action == "route_wrong":
        return "route_mismatch"
    return "correction"

# adapter.py:280 (inline version)
event_type = "rating" if action == "up" else "route_mismatch" if action == "route_wrong" else "correction"
```

### Pattern: `normalize_wecom_turn()` → `AgentTurn`-shaped dict (reference for structure)

**Source:** `services/wecom-service/src/wecom_service/normalization.py:15-58`
```python
def normalize_wecom_turn(callback: Mapping[str, Any], *, received_at: str) -> dict[str, Any]:
    """Return an AgentTurn-shaped dictionary for a sanitized WeCom callback."""
    parsed = parse_callback_envelope(callback)
    message_type = _message_type(parsed.get("message_type"))
    idempotency_key = wecom_idempotency_key({**dict(callback), **parsed, "channel": "wecom"})
    raw_payload_ref = _string(parsed.get("raw_payload_ref"))
    message_id = _string(parsed.get("message_id"))
    conversation_id = _required(parsed, "conversation_id")
    user_id = _required(parsed, "user_id")

    event: dict[str, Any] = {
        "turn_id": _string(callback.get("TurnId") or callback.get("turn_id"))
        or _stable_id("turn", message_id or idempotency_key, conversation_id, user_id),
        "conversation_id": conversation_id,
        "channel": "wecom",
        "user_id": user_id,
        "message_type": message_type,
        "received_at": received_at,
        "industry_context": _mapping_or_empty(callback.get("industry_context")),
        "metadata": {
            "idempotency_key": idempotency_key,
            "raw_payload_ref": raw_payload_ref,
            "source_event": "wecom_callback",
            "source_status": "sanitized_callback",
            "message_id": message_id,
            "content_source_status": "source_confirmed" if parsed.get("content") else "unavailable",
            # ...
        },
    }
    if message_type == "text" and parsed.get("content") is not None:
        event["content"] = parsed["content"]
    # ...
    return event
```

**QQBot adaptation** — return `AgentTurn` dataclass instance (not dict), construct `conversation_id` from scene-aware format:
```python
def normalize_message_event(
    event: QQBotEvent,
    *,
    received_at: str,
    payload_ref: str | None = None,
) -> AgentTurn:
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
        content = _strip_at_mention(_optional_string(d.get("content")) or "")
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
        },
    )
```

### Pattern: `normalize_wecom_feedback_callback()` → `FeedbackEvent`-shaped dict (reference)

**Source:** `services/wecom-service/src/wecom_service/normalization.py:61-129`
```python
def normalize_wecom_feedback_callback(callback: Mapping[str, Any], *, created_at: str) -> dict[str, Any]:
    parsed = parse_callback_envelope(callback)
    idempotency_key = wecom_idempotency_key({**dict(callback), **parsed, "event_type": "feedback"})
    action = _feedback_action(callback, parsed)
    feedback_target = _string(
        callback.get("feedback_target") or callback.get("FeedbackTarget")
        or parsed.get("message_id") or parsed.get("event_key")
    )
    # ...
    event: dict[str, Any] = {
        "feedback_id": ...,
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "source": "card_button",          # ← frozen FeedbackSource.CARD_BUTTON
        "event_type": _feedback_event_type(action),
        "status": "pending",
        "created_at": created_at,
        "feedback_target": feedback_target,
        "action": action,
        "raw_payload_ref": raw_payload_ref,
        "metadata": {
            "idempotency_key": idempotency_key,
            "source_event": "wecom_button_callback",
            "source_status": "sanitized_callback",
            "no_auto_modify": action == "route_wrong",
        },
    }
    if action == "up":
        event["rating"] = 1.0
    if action == "route_wrong":
        event["route_mismatch"] = True
        event["skill_candidate"] = {
            "detected": True,
            "source": "route_mismatch",
            "proposed_name": ... or "lawfirm.route_review_candidate",
            "risk_level": "high",
            "requires_human_review": True,
            "evidence": [...],
            "metadata": {"no_auto_modify": True, ...},
        }
    return event
```

### Pattern: `_feedback_from_payload()` → `FeedbackEvent` dataclass (existing QQBot adapter)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:278-312`
```python
def _feedback_from_payload(raw: RawInbound, payload: Mapping[str, Any]) -> FeedbackEvent:
    action = _feedback_action(payload)
    event_type = "rating" if action == "up" else "route_mismatch" if action == "route_wrong" else "correction"
    fields_map: JsonObject = {
        "feedback_id": _optional_string(payload.get("feedback_id"))
        or _stable_id("qqbot-feedback", raw.payload_ref),
        "turn_id": _optional_string(payload.get("turn_id")) or _stable_id("qqbot-turn", raw.payload_ref),
        "conversation_id": _required_string(payload, "conversation_id"),
        "user_id": _required_string(payload, "user_id"),
        "source": "card_button",
        "event_type": event_type,
        "status": "pending",
        "created_at": raw.received_at,
        "feedback_target": _required_string(payload, "feedback_target"),
        "action": action,
        "message": _optional_string(payload.get("message")),
        "industry_context": _mapping_or_empty(payload.get("industry_context")),
        "metadata": _metadata(payload, raw),
    }
    if action == "up":
        fields_map["rating"] = 1.0
    if action == "route_wrong":
        fields_map["route_mismatch"] = True
        fields_map["skill_candidate"] = SkillCandidate(
            detected=True,
            source="route_mismatch",
            proposed_name=_optional_string(payload.get("proposed_skill"))
            or "qqbot.route_review_candidate",
            risk_level="high",
            requires_human_review=True,
            evidence=[raw.payload_ref, _required_string(payload, "feedback_target")],
            metadata={"fixture_only": True, "no_auto_modify": True},
        )
    return _dataclass_from_mapping(FeedbackEvent, fields_map)
```

### Pattern: `_dataclass_from_mapping()` helper (filter to allowed fields)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:393-397`
```python
def _dataclass_from_mapping(cls: type[Any], values: Mapping[str, Any]) -> Any:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in values.items() if key in allowed})
```

> The QQBot `normalization.py` should reuse this pattern for `FeedbackEvent` construction (since `FeedbackEvent` has many optional fields and `fields_map` may contain keys not in the dataclass).

### Pattern: `@-bot` prefix stripping (NEW — no existing QQBot analog)

**Source:** Hermes QQ Bot adapter (cited in RESEARCH.md:289-292)
```python
def _strip_at_mention(content: str) -> str:
    """Strip @bot mention prefix from group message content."""
    stripped = re.sub(r"^@\S+\s*", "", content.strip())
    return stripped.strip()
```

> Handles: `" 123"` → `"123"`, `"@botname 123"` → `"123"`, `""` → `""`. C2C messages need no stripping.

### Pattern: Envelope category dispatch (NEW — no existing analog)

The `QQBotEventCategory` enum and `QQBotEvent` dataclass are new. Use `StrEnum` (matching `platform_contract/enums.py` convention) and `@dataclass(frozen=True, slots=True)` (matching `platform_contract/events.py` convention):

```python
class QQBotEventCategory(StrEnum):
    C2C_MESSAGE = "c2c_message"
    GROUP_AT_MESSAGE = "group_at_message"
    INTERACTION = "interaction"
    VALIDATION_CHALLENGE = "validation_challenge"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QQBotEvent:
    category: QQBotEventCategory
    op: int
    event_type: str | None
    data: Mapping[str, Any]
    event_id: str | None
    raw_payload_ref: str | None = None
```

> `StrEnum` is used throughout `packages/platform-contract/src/platform_contract/enums.py`. `@dataclass(frozen=True, slots=True)` is used for all `platform_contract.events` dataclasses (`AgentTurn` at events.py:125-137, `FeedbackEvent` at events.py:158-180).

### Pattern: `data.resoloved` typo fallback (defensive)

The official QQ docs have a typo (`resoloved` vs `resolved`). The normalizer should check both:
```python
data_obj = d.get("data", {})
resolved = data_obj.get("resolved") or data_obj.get("resoloved") or {}
button_data = _optional_string(resolved.get("button_data")) or ""
```

`[CITED: RESEARCH.md:220-221, bot.qq.com — msg-btn.html]`

---

## File 2: `test_normalization.py` (NEW)

### Closest Analog: `services/wecom-service/tests/test_normalization.py`

**Source:** `services/wecom-service/tests/test_normalization.py:1-98`
```python
from __future__ import annotations

import unittest

from contract_test_suite.schema_validation import validate_event

from wecom_service.normalization import (
    normalize_wecom_feedback_callback,
    normalize_wecom_turn,
)


class WeComNormalizationTests(unittest.TestCase):
    def test_text_callback_normalizes_to_schema_valid_agent_turn(self) -> None:
        event = normalize_wecom_turn(
            {
                "MsgId": "msg-text-1",
                "FromUserName": "lawyer-1",
                "ConversationId": "conv-1",
                "MsgType": "text",
                "CreateTime": "1782628800",
                "Content": "请检索合同解除的裁判观点。",
                "raw_payload_ref": "fixture://wecom/callback/msg-text-1",
            },
            received_at="2026-06-28T04:00:00Z",
        )

        validate_event("agent_turn", event, fixture_id="phase55-text")
        self.assertEqual(event["channel"], "wecom")
        self.assertEqual(event["message_type"], "text")
        self.assertEqual(event["metadata"]["raw_payload_ref"], "fixture://wecom/callback/msg-text-1")
        self.assert_no_raw_payload(event)

    def test_button_callback_normalizes_to_schema_valid_feedback_event(self) -> None:
        event = normalize_wecom_feedback_callback(
            {
                "CallbackId": "callback-1",
                "FromUserName": "lawyer-3",
                "ConversationId": "conv-3",
                "Event": "click",
                "EventKey": "feedback:down",
                "TurnId": "turn-3",
                "feedback_target": "result-msg-3",
                "raw_payload_ref": "fixture://wecom/callback/feedback-1",
            },
            created_at="2026-06-28T04:00:02Z",
        )

        validate_event("feedback_event", event, fixture_id="phase55-feedback")
        self.assertEqual(event["source"], "card_button")
        self.assertEqual(event["status"], "pending")
        self.assertEqual(event["action"], "down")

    def assert_no_raw_payload(self, value: object) -> None:
        if isinstance(value, dict):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_raw_payload(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_raw_payload(child)


if __name__ == "__main__":
    unittest.main()
```

**Key adaptation for QQBot:**
- WeCom `validate_event()` receives a **dict**; QQBot must convert the `AgentTurn`/`FeedbackEvent` **dataclass** to a dict before schema validation. Use `dataclasses.asdict()` or a custom `dataclass_to_dict()` helper.
- Import from `inkstatute_channels_qqbot.normalization` (NOT `wecom_service`).
- Test framework: `unittest.TestCase` (matches all existing qqbot tests — no pytest-specific features).

**QQBot test skeleton:**
```python
from __future__ import annotations

import unittest
from dataclasses import asdict

from contract_test_suite.schema_validation import validate_event

from inkstatute_channels_qqbot.normalization import (
    QQBotEvent,
    QQBotEventCategory,
    normalize_interaction_event,
    normalize_message_event,
    parse_envelope,
)


class QQBotNormalizationTests(unittest.TestCase):
    def test_c2c_message_normalizes_to_schema_valid_agent_turn(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "id": "evt-c2c-001",
            "d": {
                "author": {"user_openid": "FIXTURE_USER_OPENID_C2C_001"},
                "content": "请检索合同解除的裁判观点",
                "id": "ROBOT1.0_fixture_c2c_msg_001",
                "timestamp": "2026-07-07T12:00:00+08:00",
                "attachments": [],
            },
        })
        turn = normalize_message_event(
            event,
            received_at="2026-07-07T04:00:00Z",
            payload_ref="fixture://qqbot/phase60/c2c-001",
        )

        validate_event("agent_turn", asdict(turn), fixture_id="phase60-c2c")
        self.assertEqual(turn.channel, "qqbot")
        self.assertEqual(turn.conversation_id, "qqbot:c2c:FIXTURE_USER_OPENID_C2C_001:FIXTURE_USER_OPENID_C2C_001")
        # ...
```

> **Note on `asdict()` with nested dataclasses:** `FeedbackEvent` contains `SkillCandidate` (a frozen dataclass). `asdict()` recurses into nested dataclasses, producing plain dicts — which is what `validate_event()` expects. This matches how `test_qqbot_channel_adapter.py:140` uses `asdict()` for assertions.

### Test cases required (from VALIDATION.md task map)

| Test keyword | Requirement | Coverage |
|-------------|-------------|----------|
| `envelope` | INGRESS-03 | `parse_envelope()` categorizes all 5 event types |
| `dispatch` | INGRESS-03 | Reject malformed envelope (op missing) |
| `c2c` | INGRESS-04 | C2C → `AgentTurn`, scene-aware `conversation_id` |
| `group` | INGRESS-04 | Group → `AgentTurn`, @-bot prefix stripped, `group_openid` as scene_id |
| `interaction` | INGRESS-05 | INTERACTION_CREATE → `FeedbackEvent`, `source="card_button"`, all 4 actions |
| `validation` | INGRESS-03 | op=13 → `VALIDATION_CHALLENGE` category |

---

## File 3: `test_adapter_normalize.py` (NEW)

### Closest Analog: `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`

**Source:** `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py:1-53, 127-152`
```python
from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.protocols import ChannelDelivery, RawInbound


def run(coro):
    return asyncio.run(coro)


def text_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/msg-text-1",
        received_at="2026-07-04T00:00:00Z",
        idempotency_key="qqbot-idem-1",
        metadata={
            "payload": {
                "type": "message",
                "conversation_id": "conv-qqbot-1",
                "user_id": "lawyer-1",
                "message_type": "text",
                "turn_id": "turn-qqbot-1",
                "content_ref": "fixture://qqbot/content/msg-text-1",
                "content_hash": "a" * 64,
            }
        },
    )


class QQBotChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_text_message_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(text_raw()))

        self.assertIsNone(normalized.feedback)
        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertEqual(normalized.message.channel, "qqbot")
        self.assertEqual(normalized.message.message_type, "text")
```

**Key adaptation for `test_adapter_normalize.py`:**
- Construct `RawInbound` with real QQ Bot gateway envelope in `metadata["payload"]` (the `{op, t, d}` structure).
- Verify that `adapter.normalize_inbound()` delegates to `normalization.py` and produces the correct `AgentTurn`/`FeedbackEvent`.
- Must also verify backward compatibility: legacy fixture format (pre-normalized fields) still works.

**Envelope-detection test pattern:**
```python
def c2c_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/c2c-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 0,
                "t": "C2C_MESSAGE_CREATE",
                "id": "evt-c2c-001",
                "d": {
                    "author": {"user_openid": "FIXTURE_USER_OPENID_C2C_001"},
                    "content": "请检索合同解除的裁判观点",
                    "id": "ROBOT1.0_fixture_c2c_msg_001",
                    "timestamp": "2026-07-07T12:00:00+08:00",
                    "attachments": [],
                },
            }
        },
    )


class AdapterNormalizeDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_c2c_envelope_normalizes_via_normalization_module(self) -> None:
        normalized = run(self.adapter.normalize_inbound(c2c_envelope_raw()))

        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertEqual(normalized.message.conversation_id,
                         "qqbot:c2c:FIXTURE_USER_OPENID_C2C_001:FIXTURE_USER_OPENID_C2C_001")

    def test_legacy_fixture_format_still_works(self) -> None:
        """Backward compat: pre-normalized payload format (no op/t/d) still works."""
        normalized = run(self.adapter.normalize_inbound(text_raw()))  # existing helper

        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertEqual(normalized.message.conversation_id, "conv-qqbot-1")
```

> **Envelope detection strategy:** The refactored `normalize_inbound` should detect real gateway envelopes by checking for `op` and `t` keys in the payload. If present → delegate to `normalization.py`; otherwise → use the existing legacy path (`_turn_from_payload` / `_feedback_from_payload`).

---

## Files 4-7: Fixture Files (NEW)

### Closest Analog: `packages/channels/qqbot/fixtures/qqbot_channel_loop.json`

**Source:** `packages/channels/qqbot/fixtures/qqbot_channel_loop.json:1-33`
```json
{
  "fixture_id": "phase43-qqbot-channel-loop-001",
  "description": "Sanitized Phase 43 fixture evidence: QQBot ChannelAdapter end-to-end loop proof. ...",
  "not_live_acceptance": true,
  "evidence_scope": "sanitized_fixture_only",
  "raw_payload_policy": "raw_payload_ref_and_hashes_only",
  "tenant": {
    "tenant_id": "tenant-phase43-demo-001",
    "workspace_id": "workspace-phase43-demo-001",
    "channel_id": "qqbot",
    "session_id": "session-phase43-qqbot-001"
  },
  "qqbot_inbound": {
    "channel_id": "qqbot",
    "payload_ref": "fixture://qqbot/phase43/inbound/message-001",
    "received_at": "2026-07-04T00:00:00Z",
    "idempotency_key": "qqbot-idem-001",
    "metadata": {
      "payload": {
        "type": "message",
        "conversation_id": "conv-phase43-qqbot-001",
        "user_id": "user-phase43-qqbot-001",
        "message_type": "text",
        "turn_id": "turn-phase43-qqbot-001",
        "content_ref": "fixture://qqbot/phase43/content/message-001",
        "content_hash": "a1b2c3d4...",
        "industry_context": {
          "domain": "legal",
          "task_type": "legal_qa"
        }
      }
    }
  },
  ...
}
```

**Fixture convention (required fields):**
- `fixture_id`: `"phase60-qqbot-<category>-001"`
- `description`: sanitized description
- `not_live_acceptance`: `true`
- `evidence_scope`: `"sanitized_fixture_only"`
- `raw_payload_policy`: `"raw_payload_ref_and_hashes_only"`
- Use placeholder values (e.g., `FIXTURE_USER_OPENID_C2C_001`) — NO real openids, NO raw payloads.

**New fixture structure (envelope-based, from RESEARCH.md:686-716):**
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

**Fixture file list:**

| File | Envelope `t` / `op` | Expected event |
|------|---------------------|----------------|
| `qqbot_c2c_message.json` | `op=0, t=C2C_MESSAGE_CREATE` | `expected_agent_turn` |
| `qqbot_group_at_message.json` | `op=0, t=GROUP_AT_MESSAGE_CREATE` | `expected_agent_turn` (with stripped content) |
| `qqbot_interaction_create.json` | `op=0, t=INTERACTION_CREATE` | `expected_feedback_event` |
| `qqbot_validation_challenge.json` | `op=13` | `expected_category: "validation_challenge"` |

**GROUP_AT_MESSAGE_CREATE fixture** — content has leading space (residual after @-mention):
```json
{
  "envelope": {
    "op": 0,
    "t": "GROUP_AT_MESSAGE_CREATE",
    "id": "evt-group-001",
    "d": {
      "author": {"member_openid": "FIXTURE_MEMBER_OPENID_001"},
      "content": " 123",
      "group_openid": "FIXTURE_GROUP_OPENID_001",
      "id": "ROBOT1.0_fixture_group_msg_001",
      "timestamp": "2026-07-07T12:00:00+08:00",
      "attachments": []
    }
  },
  "expected_agent_turn": {
    "conversation_id": "qqbot:group:FIXTURE_GROUP_OPENID_001:FIXTURE_MEMBER_OPENID_001",
    "user_id": "FIXTURE_MEMBER_OPENID_001",
    "content": "123",
    "metadata": {
      "scene": "group",
      "scene_id": "FIXTURE_GROUP_OPENID_001"
    }
  }
}
```

**INTERACTION_CREATE fixture** — `chat_type=2` (c2c), `button_data="up"`:
```json
{
  "envelope": {
    "op": 0,
    "t": "INTERACTION_CREATE",
    "id": "evt-interaction-001",
    "d": {
      "chat_type": 2,
      "user_openid": "FIXTURE_USER_OPENID_INTERACTION_001",
      "data": {
        "resolved": {
          "button_data": "up",
          "button_id": "21",
          "user_id": "FIXTURE_USER_OPENID_INTERACTION_001"
        },
        "type": 11
      },
      "id": "30540ff7-fixture-interaction-001",
      "type": 11,
      "version": 1
    }
  },
  "expected_feedback_event": {
    "source": "card_button",
    "action": "up",
    "event_type": "rating",
    "status": "pending",
    "rating": 1.0,
    "conversation_id": "qqbot:c2c:FIXTURE_USER_OPENID_INTERACTION_001:FIXTURE_USER_OPENID_INTERACTION_001"
  }
}
```

---

## File 8: `adapter.py` (MODIFY)

### Current `normalize_inbound` (lines 175-199)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:175-199`
```python
async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
    payload = self._payload_from_raw(raw)
    if _is_feedback_payload(payload):
        return InboundNormalized(
            feedback=_feedback_from_payload(raw, payload),
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "feedback_event",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )
    return InboundNormalized(
        message=_turn_from_payload(raw, payload),
        metadata={
            "channel_id": self._config.channel_id,
            "payload_ref": raw.payload_ref,
            "normalized_type": "agent_turn",
            "idempotency_key": raw.idempotency_key
            or channel_idempotency_key(payload, channel_prefix="qqbot"),
            "fixture_only": True,
        },
    )
```

### Current `_payload_from_raw` (lines 250-260)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:250-260`
```python
def _payload_from_raw(self, raw: RawInbound) -> JsonObject:
    payload = raw.metadata.get("payload")
    if isinstance(payload, Mapping):
        values: JsonObject = dict(payload)
    else:
        values = dict(raw.metadata)
        values.pop("payload", None)
    _assert_no_forbidden_payload_keys(values)
    values.setdefault("payload_ref", raw.payload_ref)
    return values
```

### Current `_is_feedback_payload` (lines 354-356)

**Source:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:354-356`
```python
def _is_feedback_payload(payload: Mapping[str, Any]) -> bool:
    kind = str(payload.get("type") or payload.get("kind") or "").lower()
    return kind == "feedback" or "feedback_target" in payload or "action" in payload
```

### Refactoring strategy

The refactored `normalize_inbound` must detect real gateway envelopes (`{op, t, d}` keys) and delegate to `normalization.py`, while preserving the legacy fixture path:

```python
async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
    payload = self._payload_from_raw(raw)

    # Real QQ Bot gateway envelope → delegate to normalization.py
    if _is_gateway_envelope(payload):
        return _normalize_gateway_envelope(raw, payload, self._config.channel_id)

    # Legacy fixture format (pre-normalized fields) → existing path
    if _is_feedback_payload(payload):
        return InboundNormalized(
            feedback=_feedback_from_payload(raw, payload),
            metadata={...},  # unchanged
        )
    return InboundNormalized(
        message=_turn_from_payload(raw, payload),
        metadata={...},  # unchanged
    )


def _is_gateway_envelope(payload: Mapping[str, Any]) -> bool:
    """Detect real QQ Bot gateway envelope {op, t, d}."""
    return "op" in payload and "t" in payload and "d" in payload


def _normalize_gateway_envelope(
    raw: RawInbound, payload: Mapping[str, Any], channel_id: str
) -> InboundNormalized:
    from .normalization import (
        QQBotEventCategory,
        normalize_interaction_event,
        normalize_message_event,
        parse_envelope,
    )

    event = parse_envelope(payload)

    if event.category == QQBotEventCategory.INTERACTION:
        feedback = normalize_interaction_event(
            event, created_at=raw.received_at, payload_ref=raw.payload_ref
        )
        return InboundNormalized(
            feedback=feedback,
            metadata={
                "channel_id": channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "feedback_event",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )

    if event.category in (QQBotEventCategory.C2C_MESSAGE, QQBotEventCategory.GROUP_AT_MESSAGE):
        turn = normalize_message_event(
            event, received_at=raw.received_at, payload_ref=raw.payload_ref
        )
        return InboundNormalized(
            message=turn,
            metadata={
                "channel_id": channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "agent_turn",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )

    # VALIDATION_CHALLENGE or UNKNOWN → return empty InboundNormalized
    return InboundNormalized(
        metadata={
            "channel_id": channel_id,
            "payload_ref": raw.payload_ref,
            "normalized_type": event.category.value,
            "idempotency_key": raw.idempotency_key
            or channel_idempotency_key(payload, channel_prefix="qqbot"),
            "fixture_only": True,
        },
    )
```

> **Important:** The existing `_assert_no_forbidden_payload_keys()` (adapter.py:375-385) rejects keys containing `rawpayload`, `rawbody`, `callbackbody`. The new envelope payloads contain `d`, `t`, `op` — none of these trigger the forbidden-key check. However, the `d` field contains nested data that must also pass the recursive check. The fixtures use placeholder values (no raw payloads), so this is safe.

> **Backward compatibility:** The existing `qqbot_channel_loop.json` fixture uses pre-normalized payloads (no `op`/`t`/`d` keys), so `_is_gateway_envelope()` returns `False` and the legacy path is taken. `test_qqbot_channel_loop.py` and `test_qqbot_channel_adapter.py` remain green.

### Existing helpers to preserve (do NOT remove)

| Helper | Lines | Purpose |
|--------|-------|---------|
| `_turn_from_payload()` | 262-275 | Legacy fixture → `AgentTurn` |
| `_feedback_from_payload()` | 278-312 | Legacy fixture → `FeedbackEvent` |
| `_feedback_action()` | 359-372 | Alias mapping (reused by `normalization.py` logic) |
| `_assert_no_forbidden_payload_keys()` | 375-385 | Raw payload privacy guard |
| `_dataclass_from_mapping()` | 393-397 | `FeedbackEvent` construction from mapping |
| `_required_string()` | 401-406 | Required field extraction |
| `_optional_string()` | 408-411 | Optional field extraction |
| `_mapping_or_empty()` | 413-414 | Mapping coercion |
| `_stable_id()` | 416-418 | SHA-256 truncated ID generation |
| `_metadata()` | 340-352 | Legacy metadata construction |

---

## File 9: `test_no_wecom_import.py` (MODIFY)

### Current pattern (lines 30-74)

**Source:** `packages/channels/qqbot/tests/test_no_wecom_import.py:1-94`
```python
PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src" / "inkstatute_channels_qqbot"


def _imported_modules(source: str) -> list[str]:
    """Return all module names referenced in import statements."""
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


class NoWecomImportTests(unittest.TestCase):
    def test_adapter_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "adapter.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"adapter.py imports from wecom_service: {module}",
            )

    def test_signature_does_not_import_wecom_service(self) -> None:
        source = (PACKAGE_SRC / "signature.py").read_text(encoding="utf-8")
        modules = _imported_modules(source)
        for module in modules:
            self.assertFalse(
                module.startswith("wecom_service"),
                f"signature.py imports from wecom_service: {module}",
            )
```

### Addition: `normalization.py` coverage

Add a new test method following the exact same pattern:

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

> Insert after `test_signature_does_not_import_wecom_service` (line 74). The pattern is identical — read source, AST-parse, assert no module starts with `wecom_service`.

---

## Platform Contract References (do NOT modify — frozen)

### `AgentTurn` dataclass

**Source:** `packages/platform-contract/src/platform_contract/events.py:125-137`
```python
@dataclass(frozen=True, slots=True)
class AgentTurn:
    turn_id: str
    conversation_id: str
    channel: Channel | str
    user_id: str
    message_type: MessageType | str
    received_at: str
    content: str | None = None
    attachments: list[AttachmentRef] = field(default_factory=list)
    output_constraints: OutputConstraints | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

### `FeedbackEvent` dataclass

**Source:** `packages/platform-contract/src/platform_contract/events.py:158-180`
```python
@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    feedback_id: str
    turn_id: str
    conversation_id: str
    user_id: str
    source: FeedbackSource | str
    event_type: FeedbackEventType | str
    status: FeedbackStatus | str
    created_at: str
    result_id: str | None = None
    feedback_target: str | None = None
    rating: float | None = None
    action: FeedbackAction | str | None = None
    message: str | None = None
    route_mismatch: bool | None = None
    skill_candidate: SkillCandidate | None = None
    labels: list[str] = field(default_factory=list)
    related_skill: str | None = None
    related_route_decision: str | None = None
    raw_payload_ref: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

### `SkillCandidate` dataclass

**Source:** `packages/platform-contract/src/platform_contract/events.py:73-81`
```python
@dataclass(frozen=True, slots=True)
class SkillCandidate:
    detected: bool
    source: SkillCandidateSource | str
    proposed_name: str | None = None
    risk_level: RiskLevel | str | None = None
    requires_human_review: bool = True
    evidence: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

### Frozen enums (do NOT add values)

**Source:** `packages/platform-contract/src/platform_contract/enums.py:132-161`
```python
class FeedbackSource(StrEnum):
    CARD_BUTTON = "card_button"
    TEXT_COMMAND = "text_command"
    WEB_FORM = "web_form"
    ADMIN_ANNOTATION = "admin_annotation"

class FeedbackAction(StrEnum):
    UP = "up"
    DOWN = "down"
    NEEDS_FIX = "needs_fix"
    ROUTE_WRONG = "route_wrong"

class FeedbackEventType(StrEnum):
    RATING = "rating"
    CORRECTION = "correction"
    # ... (8 total values)

class FeedbackStatus(StrEnum):
    PENDING = "pending"
    # ... (4 total values)

class Channel(StrEnum):
    WECOM = "wecom"
    QQBOT = "qqbot"
    # ...
```

> **Frozen invariant:** `FeedbackSource` has exactly 4 values. Enforced by `test_v1_8_safety_baseline.py:48-52`, `test_contract_freeze_not_violated.py:44-48`, `test_feedback_source_mapping.py:100-122`. Use `FeedbackSource.CARD_BUTTON` (value `"card_button"`) — do NOT add `QQBOT_BUTTON`.

---

## Shared Infrastructure References

### `channel_idempotency_key()`

**Source:** `packages/channel-core/src/channel_core/idempotency.py:9-53`
```python
def channel_idempotency_key(
    callback: Mapping[str, Any],
    *,
    channel_prefix: str = "channel",
    stable_fields: Sequence[tuple[str, Sequence[str]]] | None = None,
    fallback_field_aliases: Mapping[str, Sequence[str]] | None = None,
) -> str:
    # Tries stable fields (message_id, callback_id, feedback_id) first,
    # then falls back to composite digest.
```

> Used in `adapter.py:185,196,344` with `channel_prefix="qqbot"`. The refactored `normalize_inbound` should continue using this for the `idempotency_key` in `InboundNormalized.metadata`.

### `validate_event()`

**Source:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py:96-116`
```python
def validate_event(
    event_key: str,
    event: Any,
    schemas: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    fixture_id: str = "<unknown-fixture>",
) -> None:
    # Validates event dict against JSON Schema.
    # event_key must be in EVENT_SCHEMA_BY_KEY: "agent_turn", "feedback_event", etc.
```

> Accepts a **dict** (not dataclass). QQBot tests must convert `AgentTurn`/`FeedbackEvent` to dict via `dataclasses.asdict()` before calling. `[VERIFIED: services/wecom-service/tests/test_normalization.py:28,78]`

### `RawInbound` / `InboundNormalized` data shapes

**Source:** `packages/platform-runtime/src/platform_runtime/protocols.py:32-53`
```python
@dataclass(frozen=True, slots=True)
class RawInbound:
    channel_id: ChannelId
    payload_ref: str
    received_at: str
    idempotency_key: str | None = None
    metadata: JsonObject = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class InboundNormalized:
    message: AgentTurn | None = None
    feedback: FeedbackEvent | None = None
    metadata: JsonObject = field(default_factory=dict)
```

> The verified payload is available in `raw.metadata["payload"]` (a dict). The refactored `normalize_inbound` reads this via `_payload_from_raw()` (existing helper at adapter.py:250-260).

---

## Safety Invariants (must remain green)

| Test file | Invariant | Source |
|-----------|-----------|--------|
| `test_v1_8_safety_baseline.py` | `dependencies = []`, 6 Protocol methods, 4 `FeedbackSource` values | lines 35-61 |
| `test_contract_freeze_not_violated.py` | Frozen contract surfaces unchanged | lines 31-87 |
| `test_feedback_source_mapping.py` | QQBot feedback → `CARD_BUTTON`, enum frozen at 4 | lines 57-122 |
| `test_no_wecom_import.py` | No `wecom_service` imports (AST inspection) | lines 30-90 |
| `test_qqbot_channel_loop.py` | Existing fixture loop still works (legacy format) | lines 83-205 |
| `test_qqbot_channel_adapter.py` | Adapter tests (legacy format) | lines 110-236 |
| `test_qqbot_idempotency.py` | Idempotency tests | — |
| `test_feature_flag.py` | Flag default-off | — |
| `test_signature.py` | Phase 59 signature tests | — |
| `test_ed25519_vectors.py` | Ed25519 known-answer tests | — |

---

## Summary Of Key Pattern Decisions

1. **`normalization.py`** mirrors the WeCom `normalization.py` structure (pure functions, `_stable_id`, `_feedback_action` aliases, `_feedback_event_type` mapping) but returns **dataclass instances** (`AgentTurn`/`FeedbackEvent`) instead of dicts, and adds envelope-category dispatch (`QQBotEventCategory` enum + `QQBotEvent` dataclass + `parse_envelope()`).

2. **`adapter.py` refactor** uses envelope detection (`_is_gateway_envelope` checks for `op`/`t`/`d` keys) to route real QQ Bot gateway envelopes to `normalization.py` while preserving the legacy fixture path for backward compatibility.

3. **Fixtures** follow the existing `qqbot_channel_loop.json` convention (`fixture_id`, `not_live_acceptance`, `evidence_scope`, `raw_payload_policy`) but use real QQ Bot envelope structure (`{op, t, d}`) with sanitized placeholder values.

4. **Tests** use `unittest.TestCase` (stdlib, matching all existing qqbot tests) and `contract_test_suite.schema_validation.validate_event()` for schema validation (converting dataclasses to dicts via `asdict()` first).

5. **`test_no_wecom_import.py`** gets one new test method (`test_normalization_does_not_import_wecom_service`) following the exact existing AST-inspection pattern.

6. **No new dependencies** — stdlib only. `dependencies = []` invariant holds.
