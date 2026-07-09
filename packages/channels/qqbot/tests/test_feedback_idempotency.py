"""Wave 0 / Plan 01: FEEDBACK-03 msg_id + button_identity idempotency.

Stamps metadata.idempotency_key = "{msg_id}:{button_identity}" on INTERACTION
FeedbackEvents so feedback-service dedupe collapses duplicate clicks.
"""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Any

from inkstatute_channels_qqbot.normalization import (
    normalize_interaction_event,
    parse_envelope,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
RECEIVED_AT = "2026-07-09T00:00:00Z"
EXPECTED_KEY = "FIXTURE_CARD_MSG_ID_001:21"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value if item is not None]
    return value


def _assert_no_privacy_leak(self: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        self.assertNotIn("raw_payload", value)
        self.assertNotIn("Authorization", value)
        for key, child in value.items():
            key_l = str(key).lower()
            self.assertNotIn("token", key_l)
            self.assertNotIn("authorization", key_l)
            _assert_no_privacy_leak(self, child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_privacy_leak(self, child)


class TestFeedbackIdempotencyKey(unittest.TestCase):
    """FEEDBACK-03: normalize stamps msg_id + button_identity key."""

    def test_feedback03_idempotency_key_from_message_id_and_button_id(self) -> None:
        fixture = _load_fixture("qqbot_interaction_create.json")
        event = parse_envelope(fixture["envelope"])
        feedback = normalize_interaction_event(event, created_at=RECEIVED_AT)

        self.assertEqual(feedback.metadata.get("idempotency_key"), EXPECTED_KEY)
        self.assertEqual(feedback.metadata.get("dedupe_strategy"), "msg_id + button_identity")
        self.assertEqual(feedback.metadata.get("msg_id"), "FIXTURE_CARD_MSG_ID_001")
        self.assertEqual(feedback.feedback_target, "FIXTURE_CARD_MSG_ID_001")
        _assert_no_privacy_leak(self, asdict(feedback))

    def test_feedback03_button_identity_falls_back_to_button_data(self) -> None:
        envelope = {
            "op": 0,
            "t": "INTERACTION_CREATE",
            "id": "evt-fallback-button-data",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_FALLBACK_001",
                "data": {
                    "resolved": {
                        "button_data": "down",
                        "message_id": "FIXTURE_CARD_MSG_ID_FALLBACK",
                    }
                },
                "id": "FIXTURE_INTERACTION_FALLBACK_001",
            },
        }
        feedback = normalize_interaction_event(
            parse_envelope(envelope), created_at=RECEIVED_AT
        )
        self.assertEqual(
            feedback.metadata.get("idempotency_key"),
            "FIXTURE_CARD_MSG_ID_FALLBACK:down",
        )

    def test_feedback03_msg_id_falls_back_to_interaction_id(self) -> None:
        envelope = {
            "op": 0,
            "t": "INTERACTION_CREATE",
            "id": "evt-fallback-interaction",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_NO_MSG_001",
                "data": {"resolved": {"button_data": "up", "button_id": "21"}},
                "id": "FIXTURE_INTERACTION_NO_MSG_001",
            },
        }
        feedback = normalize_interaction_event(
            parse_envelope(envelope), created_at=RECEIVED_AT
        )
        self.assertEqual(
            feedback.metadata.get("idempotency_key"),
            "FIXTURE_INTERACTION_NO_MSG_001:21",
        )
        self.assertEqual(feedback.feedback_target, "FIXTURE_INTERACTION_NO_MSG_001")


class TestFeedbackIdempotencyDedupe(unittest.TestCase):
    """FEEDBACK-03: duplicate payloads collapse via feedback-service dedupe."""

    def test_feedback03_duplicate_clicks_collapse_via_normalize_feedback_inputs(self) -> None:
        from feedback_service.queue import normalize_feedback_inputs

        fixture = _load_fixture("qqbot_interaction_create.json")
        event = parse_envelope(fixture["envelope"])
        feedback = normalize_interaction_event(event, created_at=RECEIVED_AT)
        event_dict = _strip_none(asdict(feedback))

        self.assertEqual(event_dict["metadata"]["idempotency_key"], EXPECTED_KEY)

        events = normalize_feedback_inputs(
            contract_feedback_events=[event_dict, copy.deepcopy(event_dict)]
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metadata"]["idempotency_key"], EXPECTED_KEY)
        self.assertEqual(events[0]["metadata"]["duplicate_count"], 2)
        _assert_no_privacy_leak(self, events[0])


if __name__ == "__main__":
    unittest.main()
