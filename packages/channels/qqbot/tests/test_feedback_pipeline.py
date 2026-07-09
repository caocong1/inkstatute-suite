"""Wave 0 / Plan 01→02: FEEDBACK-01/02 E2E normalize→queue + ACK no-op-if-sent.

Plan 01 scaffolds RED coverage. Plan 02 greens TestEnsureInteractionAck and
full queue/parity composition. Prefer handle_feedback_callback for ingress.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
RECEIVED_AT = "2026-07-09T00:00:00Z"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


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


class TestEnsureInteractionAck(unittest.TestCase):
    """FEEDBACK-02: post-normalize ACK no-op-if-sent (Plan 02 greens)."""

    def test_feedback02_ack_noop_when_interaction_ack_status_sent(self) -> None:
        try:
            from inkstatute_channels_qqbot.feedback_ingress import ensure_interaction_ack
        except ImportError:
            self.fail(
                "FEEDBACK-02: ensure_interaction_ack not implemented (Plan 02 Task 1)"
            )

        result = ensure_interaction_ack(
            interaction_id="FIXTURE_INTERACTION_ID_001",
            prior_ack_metadata={"interaction_ack_status": "sent"},
            message_transport=None,
            access_token="unused",
        )
        self.assertEqual(result.get("status"), "noop")
        self.assertEqual(result.get("interaction_ack_status"), "sent")

    def test_feedback02_ack_put_when_pending_host(self) -> None:
        try:
            from inkstatute_channels_qqbot.feedback_ingress import ensure_interaction_ack
            from inkstatute_channels_qqbot.sender import FakeMessageTransport
        except ImportError:
            self.fail(
                "FEEDBACK-02: ensure_interaction_ack not implemented (Plan 02 Task 1)"
            )

        transport = FakeMessageTransport(response={"code": 0})
        result = ensure_interaction_ack(
            interaction_id="FIXTURE_INTERACTION_ID_001",
            prior_ack_metadata={"interaction_ack_status": "pending_host"},
            message_transport=transport,
            access_token="fixture-token",
        )
        self.assertEqual(result.get("interaction_ack_status"), "sent")
        puts = [
            c
            for c in transport.calls
            if c.get("method") == "PUT" or "/interactions/" in str(c.get("url") or "")
        ]
        self.assertEqual(len(puts), 1)

    def test_feedback02_ack_skipped_fixture_no_put(self) -> None:
        try:
            from inkstatute_channels_qqbot.feedback_ingress import ensure_interaction_ack
            from inkstatute_channels_qqbot.sender import FakeMessageTransport
        except ImportError:
            self.fail(
                "FEEDBACK-02: ensure_interaction_ack not implemented (Plan 02 Task 1)"
            )

        transport = FakeMessageTransport(response={"code": 0})
        result = ensure_interaction_ack(
            interaction_id="FIXTURE_INTERACTION_ID_001",
            prior_ack_metadata={"interaction_ack_status": "skipped_fixture"},
            message_transport=transport,
            access_token="fixture-token",
        )
        self.assertIn(result.get("status"), {"noop", "skipped"})
        puts = [
            c
            for c in transport.calls
            if c.get("method") == "PUT" or "/interactions/" in str(c.get("url") or "")
        ]
        self.assertEqual(len(puts), 0)


class TestFeedbackPipelineE2E(unittest.TestCase):
    """FEEDBACK-01: handle_feedback_callback → queue composition."""

    def test_feedback01_handle_feedback_callback_normalizes_interaction(self) -> None:
        from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback

        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        result = handle_feedback_callback(envelope, received_at=RECEIVED_AT)

        self.assertEqual(result["status"], "normalized")
        self.assertEqual(result["idempotency_key"], "FIXTURE_CARD_MSG_ID_001:21")
        self.assertIn("feedback_dict", result)
        self.assertEqual(result["feedback_dict"]["source"], "card_button")
        self.assertEqual(result["feedback_dict"]["action"], "up")
        _assert_no_privacy_leak(self, result["feedback_dict"])

    def test_feedback01_skipped_for_non_interaction_category(self) -> None:
        from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback

        result = handle_feedback_callback(
            {"op": 0, "t": "C2C_MESSAGE_CREATE", "d": {}},
            received_at=RECEIVED_AT,
        )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["category"], "c2c_message")

    def test_feedback01_e2e_normalize_to_pending_queue(self) -> None:
        from feedback_service.queue import (
            build_pending_feedback_queue,
            normalize_feedback_inputs,
        )
        from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback

        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        result = handle_feedback_callback(
            envelope,
            received_at=RECEIVED_AT,
            payload_ref="fixture://qqbot/interaction/pipeline-e2e",
        )
        self.assertEqual(result["status"], "normalized")

        events = normalize_feedback_inputs(
            contract_feedback_events=[result["feedback_dict"]]
        )
        self.assertEqual(len(events), 1)
        queue = build_pending_feedback_queue(events)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["action"], "up")
        self.assertEqual(queue[0]["idempotency_key"], "FIXTURE_CARD_MSG_ID_001:21")
        _assert_no_privacy_leak(self, queue[0])

    def test_feedback01_route_wrong_keeps_no_auto_modify(self) -> None:
        from feedback_service.queue import (
            build_pending_feedback_queue,
            normalize_feedback_inputs,
        )
        from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback

        envelope = {
            "op": 0,
            "t": "INTERACTION_CREATE",
            "id": "evt-route-wrong",
            "d": {
                "chat_type": 2,
                "user_openid": "FIXTURE_USER_ROUTE_WRONG",
                "data": {
                    "resolved": {
                        "button_data": "route_wrong",
                        "button_id": "24",
                        "message_id": "FIXTURE_CARD_MSG_ROUTE",
                    }
                },
                "id": "FIXTURE_INTERACTION_ROUTE_WRONG",
            },
        }
        result = handle_feedback_callback(
            envelope,
            received_at=RECEIVED_AT,
            payload_ref="fixture://qqbot/interaction/route-wrong",
        )
        events = normalize_feedback_inputs(
            contract_feedback_events=[result["feedback_dict"]]
        )
        item = build_pending_feedback_queue(events)[0]
        self.assertTrue(item["no_auto_modify"])
        self.assertTrue(item["requires_human_review"])
        self.assertIsNotNone(item.get("skill_candidate"))

    def test_feedback01_keyboard_button_data_maps_to_ingress_action(self) -> None:
        """Plan 02: keyboard builder button_data ↔ normalize action mapping."""
        from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback
        from inkstatute_channels_qqbot.sender import build_feedback_keyboard_envelope

        keyboard = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="FIXTURE_CARD_MSG_ID_001",
            msg_id="FIXTURE_CARD_MSG_ID_001",
        )
        buttons = keyboard["keyboard"]["content"]["rows"][0]["buttons"]
        button_datas = {button["action"]["data"] for button in buttons}
        self.assertIn("up", button_datas)

        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        result = handle_feedback_callback(envelope, received_at=RECEIVED_AT)
        self.assertEqual(result["feedback_dict"]["action"], "up")
        self.assertIn(result["feedback_dict"]["action"], button_datas)


if __name__ == "__main__":
    unittest.main()
