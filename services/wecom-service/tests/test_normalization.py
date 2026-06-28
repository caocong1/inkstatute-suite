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

    def test_media_callbacks_use_attachment_references_without_bytes(self) -> None:
        fixtures = [
            ("file", "file-1", "contract.docx"),
            ("image", "image-1", "photo.png"),
            ("voice", "voice-1", "voice.amr"),
        ]

        for message_type, media_id, name in fixtures:
            with self.subTest(message_type=message_type):
                event = normalize_wecom_turn(
                    {
                        "MsgId": f"msg-{message_type}",
                        "FromUserName": "lawyer-2",
                        "ConversationId": "conv-2",
                        "MsgType": message_type,
                        "MediaId": media_id,
                        "FileName": name,
                        "raw_payload_ref": f"fixture://wecom/callback/msg-{message_type}",
                    },
                    received_at="2026-06-28T04:00:01Z",
                )

                validate_event("agent_turn", event, fixture_id=f"phase55-{message_type}")
                self.assertEqual(event["message_type"], message_type)
                self.assertEqual(event["attachments"][0]["attachment_id"], media_id)
                self.assertEqual(event["attachments"][0]["uri"], f"wecom-media://{media_id}")
                self.assertNotIn("bytes", event["attachments"][0])
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
        self.assertEqual(event["feedback_target"], "result-msg-3")
        self.assertEqual(event["action"], "down")
        self.assertEqual(event["raw_payload_ref"], "fixture://wecom/callback/feedback-1")
        self.assertIn("idempotency_key", event["metadata"])
        self.assert_no_raw_payload(event)

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
