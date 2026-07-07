"""Unit tests for the QQ Bot normalization module.

Tests envelope parsing (parse_envelope), event dispatch into typed
QQBotEventCategory values, message normalization into AgentTurn, and
interaction normalization into FeedbackEvent with contract schema validation.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Any

from contract_test_suite.schema_validation import validate_event
from platform_contract.events import AgentTurn, FeedbackEvent

from inkstatute_channels_qqbot.normalization import (
    QQBotEvent,
    QQBotEventCategory,
    normalize_interaction_event,
    normalize_message_event,
    parse_envelope,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file from the qqbot fixtures directory."""
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _strip_none(value: Any) -> Any:
    """Recursively remove None values from dicts/lists for schema validation.

    JSON Schema optional fields that are typed as object/array/string do not
    accept null — the field must be absent rather than null. asdict() on a
    frozen dataclass produces None for unset optional fields, so we strip
    them before passing to validate_event.
    """
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value if item is not None]
    return value


def _event_dict(event: Any) -> dict:
    """Convert a frozen dataclass event to a schema-valid dict (None stripped)."""
    return _strip_none(asdict(event))


class ParseEnvelopeTests(unittest.TestCase):
    """Tests for parse_envelope — envelope parsing and category dispatch."""

    def test_parse_envelope_c2c(self) -> None:
        fixture = _load_fixture("qqbot_c2c_message.json")
        event = parse_envelope(fixture["envelope"])
        self.assertEqual(event.category, QQBotEventCategory.C2C_MESSAGE)
        self.assertEqual(event.op, 0)
        self.assertEqual(event.event_type, "C2C_MESSAGE_CREATE")

    def test_parse_envelope_group(self) -> None:
        fixture = _load_fixture("qqbot_group_at_message.json")
        event = parse_envelope(fixture["envelope"])
        self.assertEqual(event.category, QQBotEventCategory.GROUP_AT_MESSAGE)
        self.assertEqual(event.op, 0)
        self.assertEqual(event.event_type, "GROUP_AT_MESSAGE_CREATE")

    def test_parse_envelope_interaction(self) -> None:
        fixture = _load_fixture("qqbot_interaction_create.json")
        event = parse_envelope(fixture["envelope"])
        self.assertEqual(event.category, QQBotEventCategory.INTERACTION)
        self.assertEqual(event.op, 0)
        self.assertEqual(event.event_type, "INTERACTION_CREATE")

    def test_parse_envelope_validation_challenge(self) -> None:
        fixture = _load_fixture("qqbot_validation_challenge.json")
        event = parse_envelope(fixture["envelope"])
        self.assertEqual(event.category, QQBotEventCategory.VALIDATION_CHALLENGE)
        self.assertEqual(event.op, 13)

    def test_parse_envelope_unknown_event_type(self) -> None:
        event = parse_envelope({"op": 0, "t": "FRIEND_ADD", "d": {}})
        self.assertEqual(event.category, QQBotEventCategory.UNKNOWN)

    def test_parse_envelope_unknown_opcode(self) -> None:
        event = parse_envelope({"op": 99, "d": {}})
        self.assertEqual(event.category, QQBotEventCategory.UNKNOWN)

    def test_parse_envelope_missing_fields(self) -> None:
        event = parse_envelope({})
        self.assertEqual(event.category, QQBotEventCategory.UNKNOWN)
        self.assertEqual(event.op, -1)
        self.assertIsNone(event.event_type)
        self.assertEqual(event.data, {})

    def test_parse_envelope_non_mapping_d(self) -> None:
        event = parse_envelope({"op": 0, "t": "C2C_MESSAGE_CREATE", "d": "string"})
        self.assertEqual(event.data, {})

    def test_qqbot_event_category_has_exactly_5_values(self) -> None:
        members = list(QQBotEventCategory)
        self.assertEqual(len(members), 5)
        values = {member.value for member in members}
        self.assertEqual(
            values,
            {"c2c_message", "group_at_message", "interaction", "validation_challenge", "unknown"},
        )

    def test_qqbot_event_is_frozen_dataclass_with_slots(self) -> None:
        event = QQBotEvent(
            category=QQBotEventCategory.UNKNOWN,
            op=-1,
            event_type=None,
            data={},
            event_id=None,
        )
        # frozen: should raise AttributeError on setattr
        with self.assertRaises(Exception):
            event.op = 0  # type: ignore[misc]
        # slots: should not have __dict__
        self.assertFalse(hasattr(event, "__dict__"))
        # fields: category, op, event_type, data, event_id, raw_payload_ref
        import dataclasses as dc

        field_names = {f.name for f in dc.fields(event)}
        self.assertEqual(
            field_names,
            {"category", "op", "event_type", "data", "event_id", "raw_payload_ref"},
        )


class NormalizeMessageEventTests(unittest.TestCase):
    """Tests for normalize_message_event — C2C and GROUP_AT_MESSAGE → AgentTurn."""

    def test_normalize_c2c_message(self) -> None:
        fixture = _load_fixture("qqbot_c2c_message.json")
        event = parse_envelope(fixture["envelope"])
        turn = normalize_message_event(event, received_at="2026-07-07T12:00:00Z")

        self.assertIsInstance(turn, AgentTurn)
        self.assertEqual(turn.conversation_id, "qqbot:c2c:FIXTURE_USER_OPENID_C2C_001:FIXTURE_USER_OPENID_C2C_001")
        self.assertEqual(turn.channel, "qqbot")
        self.assertEqual(turn.user_id, "FIXTURE_USER_OPENID_C2C_001")
        self.assertEqual(turn.message_type, "text")
        self.assertEqual(turn.content, "请检索合同解除的裁判观点")
        self.assertEqual(turn.metadata["scene"], "c2c")
        self.assertEqual(turn.metadata["source_event"], "C2C_MESSAGE_CREATE")
        validate_event("agent_turn", _event_dict(turn), fixture_id="phase60-c2c")

    def test_normalize_c2c_empty_content(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "d": {"author": {"user_openid": "FIXTURE_USER_C2C_EMPTY"}, "content": ""},
        })
        turn = normalize_message_event(event, received_at="2026-07-07T12:00:00Z")
        self.assertIsNone(turn.content)

    def test_normalize_group_message(self) -> None:
        fixture = _load_fixture("qqbot_group_at_message.json")
        event = parse_envelope(fixture["envelope"])
        turn = normalize_message_event(event, received_at="2026-07-07T12:00:00Z")

        self.assertIsInstance(turn, AgentTurn)
        self.assertEqual(turn.conversation_id, "qqbot:group:FIXTURE_GROUP_OPENID_001:FIXTURE_MEMBER_OPENID_001")
        self.assertEqual(turn.user_id, "FIXTURE_MEMBER_OPENID_001")
        self.assertEqual(turn.content, "123")
        self.assertEqual(turn.metadata["scene"], "group")
        self.assertEqual(turn.metadata["scene_id"], "FIXTURE_GROUP_OPENID_001")
        validate_event("agent_turn", _event_dict(turn), fixture_id="phase60-group")

    def test_normalize_group_at_mention_stripped(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {
                "author": {"member_openid": "FIXTURE_MEMBER_MENTION"},
                "content": "@botname 123",
                "group_openid": "FIXTURE_GROUP_MENTION",
                "id": "FIXTURE_GROUP_MSG_MENTION",
            },
        })
        turn = normalize_message_event(event, received_at="2026-07-07T12:00:00Z")
        self.assertEqual(turn.content, "123")

    def test_normalize_group_whitespace_only(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {
                "author": {"member_openid": "FIXTURE_MEMBER_WS"},
                "content": "  ",
                "group_openid": "FIXTURE_GROUP_WS",
                "id": "FIXTURE_GROUP_MSG_WS",
            },
        })
        turn = normalize_message_event(event, received_at="2026-07-07T12:00:00Z")
        self.assertIsNone(turn.content)

    def test_normalize_message_wrong_category_raises(self) -> None:
        event = parse_envelope({"op": 0, "t": "INTERACTION_CREATE", "d": {}})
        with self.assertRaises(ValueError):
            normalize_message_event(event, received_at="2026-07-07T12:00:00Z")

    def test_normalize_message_unknown_category_raises(self) -> None:
        event = parse_envelope({"op": 99, "d": {}})
        with self.assertRaises(ValueError):
            normalize_message_event(event, received_at="2026-07-07T12:00:00Z")

    def test_normalize_c2c_missing_user_openid_raises(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "d": {"author": {}, "content": "hello"},
        })
        with self.assertRaises(ValueError):
            normalize_message_event(event, received_at="2026-07-07T12:00:00Z")

    def test_normalize_group_missing_group_openid_raises(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {"author": {"member_openid": "FIXTURE_MEMBER_NO_GROUP"}, "content": "hello"},
        })
        with self.assertRaises(ValueError):
            normalize_message_event(event, received_at="2026-07-07T12:00:00Z")


class NormalizeInteractionEventTests(unittest.TestCase):
    """Tests for normalize_interaction_event — INTERACTION_CREATE → FeedbackEvent."""

    def test_normalize_interaction_c2c_up(self) -> None:
        fixture = _load_fixture("qqbot_interaction_create.json")
        event = parse_envelope(fixture["envelope"])
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")

        self.assertIsInstance(feedback, FeedbackEvent)
        self.assertEqual(feedback.source, "card_button")
        self.assertEqual(feedback.action, "up")
        self.assertEqual(feedback.event_type, "rating")
        self.assertEqual(feedback.rating, 1.0)
        self.assertEqual(feedback.status, "pending")
        self.assertEqual(
            feedback.conversation_id,
            "qqbot:c2c:FIXTURE_USER_OPENID_INTERACTION_001:FIXTURE_USER_OPENID_INTERACTION_001",
        )
        validate_event("feedback_event", _event_dict(feedback), fixture_id="phase60-interaction")

    def test_normalize_interaction_group(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 1,
                "group_openid": "FIXTURE_GROUP_INTERACTION_001",
                "group_member_openid": "FIXTURE_GROUP_MEMBER_001",
                "data": {"resolved": {"button_data": "down", "button_id": "22"}},
                "id": "FIXTURE_INTERACTION_GROUP_ID_001",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.user_id, "FIXTURE_GROUP_MEMBER_001")
        self.assertEqual(feedback.action, "down")
        self.assertEqual(feedback.event_type, "correction")
        self.assertEqual(feedback.conversation_id, "qqbot:group:FIXTURE_GROUP_INTERACTION_001:FIXTURE_GROUP_MEMBER_001")

    def test_normalize_interaction_guild(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 0,
                "channel_id": "FIXTURE_GUILD_CHANNEL_001",
                "data": {
                    "resolved": {
                        "button_data": "up",
                        "button_id": "21",
                        "user_id": "FIXTURE_GUILD_USER_001",
                    },
                    "type": 11,
                },
                "id": "FIXTURE_INTERACTION_GUILD_ID_001",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")

        self.assertIsInstance(feedback, FeedbackEvent)
        self.assertEqual(feedback.source, "card_button")
        self.assertEqual(feedback.action, "up")
        self.assertEqual(feedback.event_type, "rating")
        self.assertEqual(feedback.rating, 1.0)
        self.assertEqual(feedback.status, "pending")
        self.assertEqual(feedback.user_id, "FIXTURE_GUILD_USER_001")
        self.assertEqual(feedback.metadata["scene"], "guild")
        self.assertEqual(feedback.metadata["chat_type"], 0)
        self.assertEqual(
            feedback.conversation_id,
            "qqbot:guild:FIXTURE_GUILD_CHANNEL_001:FIXTURE_GUILD_USER_001",
        )
        validate_event("feedback_event", _event_dict(feedback), fixture_id="phase60-guild")

    def test_normalize_interaction_down(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_DOWN",
                "data": {"resolved": {"button_data": "down"}},
                "id": "FIXTURE_INTERACTION_DOWN_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "down")
        self.assertEqual(feedback.event_type, "correction")

    def test_normalize_interaction_needs_fix(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_NEEDS_FIX",
                "data": {"resolved": {"button_data": "needs_fix"}},
                "id": "FIXTURE_INTERACTION_NEEDS_FIX_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "needs_fix")
        self.assertEqual(feedback.event_type, "correction")

    def test_normalize_interaction_route_wrong(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_ROUTE_WRONG",
                "data": {"resolved": {"button_data": "route_wrong"}},
                "id": "FIXTURE_INTERACTION_ROUTE_WRONG_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "route_wrong")
        self.assertEqual(feedback.event_type, "route_mismatch")
        self.assertTrue(feedback.route_mismatch)
        self.assertIsNotNone(feedback.skill_candidate)
        self.assertTrue(feedback.skill_candidate.detected)
        self.assertTrue(feedback.skill_candidate.requires_human_review)
        self.assertEqual(feedback.skill_candidate.risk_level, "high")
        self.assertTrue(feedback.metadata["no_auto_modify"])
        validate_event("feedback_event", _event_dict(feedback), fixture_id="phase60-route-wrong")

    def test_normalize_interaction_alias_thumbs_up(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_ALIAS",
                "data": {"resolved": {"button_data": "thumbs_up"}},
                "id": "FIXTURE_INTERACTION_ALIAS_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "up")

    def test_normalize_interaction_alias_like(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_LIKE",
                "data": {"resolved": {"button_data": "like"}},
                "id": "FIXTURE_INTERACTION_LIKE_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "up")

    def test_normalize_interaction_resoloved_typo(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_TYPO",
                "data": {"resoloved": {"button_data": "up"}},
                "id": "FIXTURE_INTERACTION_TYPO_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.action, "up")
        self.assertEqual(feedback.event_type, "rating")

    def test_normalize_interaction_unsupported_action_raises(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_UNSUPPORTED",
                "data": {"resolved": {"button_data": "unknown_action"}},
                "id": "FIXTURE_INTERACTION_UNSUPPORTED_ID",
            },
        })
        with self.assertRaises(ValueError):
            normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")

    def test_normalize_interaction_status_pending(self) -> None:
        event = parse_envelope({
            "op": 0,
            "t": "INTERACTION_CREATE",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_STATUS",
                "data": {"resolved": {"button_data": "up"}},
                "id": "FIXTURE_INTERACTION_STATUS_ID",
            },
        })
        feedback = normalize_interaction_event(event, created_at="2026-07-07T12:00:00Z")
        self.assertEqual(feedback.status, "pending")


if __name__ == "__main__":
    unittest.main()
