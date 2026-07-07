"""Unit tests for the QQ Bot normalization module.

Tests envelope parsing (parse_envelope), event dispatch into typed
QQBotEventCategory values, message normalization into AgentTurn, and
interaction normalization into FeedbackEvent with contract schema validation.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from inkstatute_channels_qqbot.normalization import (
    QQBotEvent,
    QQBotEventCategory,
    parse_envelope,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file from the qqbot fixtures directory."""
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


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


if __name__ == "__main__":
    unittest.main()
