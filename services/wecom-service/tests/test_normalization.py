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

    def test_text_callback_with_output_constraints(self) -> None:
        event = normalize_wecom_turn(
            {
                "MsgId": "msg-constraints",
                "FromUserName": "lawyer-4",
                "ConversationId": "conv-4",
                "MsgType": "text",
                "Content": "Analyze clause.",
                "raw_payload_ref": "fixture://wecom/callback/msg-constraints",
                "output_constraints": {"max_length": 500, "format": "markdown"},
            },
            received_at="2026-06-28T04:00:03Z",
        )

        self.assertEqual(event["output_constraints"]["max_length"], 500)

    def test_unsupported_message_type_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_wecom_turn(
                {
                    "MsgId": "msg-bad-type",
                    "FromUserName": "lawyer-5",
                    "ConversationId": "conv-5",
                    "MsgType": "video",
                    "raw_payload_ref": "fixture://wecom/callback/msg-bad-type",
                },
                received_at="2026-06-28T04:00:04Z",
            )

        self.assertIn("unsupported", str(ctx.exception))

    def test_feedback_callback_missing_target_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_wecom_feedback_callback(
                {
                    "FromUserName": "lawyer-6",
                    "ConversationId": "conv-6",
                    "action": "down",
                },
                created_at="2026-06-28T04:00:05Z",
            )

        self.assertIn("feedback_target", str(ctx.exception))

    def test_feedback_callback_with_result_id_and_message(self) -> None:
        event = normalize_wecom_feedback_callback(
            {
                "FromUserName": "lawyer-7",
                "ConversationId": "conv-7",
                "Event": "click",
                "EventKey": "feedback:up",
                "feedback_target": "result-msg-7",
                "result_id": "result-007",
                "message": "Good response",
                "raw_payload_ref": "fixture://wecom/callback/feedback-7",
            },
            created_at="2026-06-28T04:00:06Z",
        )

        self.assertEqual(event["result_id"], "result-007")
        self.assertEqual(event["message"], "Good response")
        self.assertEqual(event["rating"], 1.0)

    def test_feedback_route_wrong_produces_skill_candidate(self) -> None:
        event = normalize_wecom_feedback_callback(
            {
                "FromUserName": "lawyer-8",
                "ConversationId": "conv-8",
                "Event": "click",
                "EventKey": "feedback:route_wrong",
                "feedback_target": "result-msg-8",
                "raw_payload_ref": "fixture://wecom/callback/feedback-8",
            },
            created_at="2026-06-28T04:00:07Z",
        )

        self.assertTrue(event["route_mismatch"])
        self.assertEqual(event["skill_candidate"]["source"], "route_mismatch")
        self.assertTrue(event["skill_candidate"]["requires_human_review"])
        self.assertTrue(event["metadata"]["no_auto_modify"])

    def test_feedback_action_aliases(self) -> None:
        aliases = {
            "thumbs_up": "up",
            "like": "up",
            "thumbs_down": "down",
            "dislike": "down",
            "fix": "needs_fix",
            "route_mismatch": "route_wrong",
        }

        for alias, expected in aliases.items():
            with self.subTest(alias=alias):
                event = normalize_wecom_feedback_callback(
                    {
                        "FromUserName": "lawyer-alias",
                        "ConversationId": "conv-alias",
                        "action": alias,
                        "feedback_target": "result-alias",
                        "raw_payload_ref": "fixture://wecom/callback/alias",
                    },
                    created_at="2026-06-28T04:00:08Z",
                )

                self.assertEqual(event["action"], expected)

    def test_unsupported_feedback_action_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_wecom_feedback_callback(
                {
                    "FromUserName": "lawyer-9",
                    "ConversationId": "conv-9",
                    "action": "unknown_action",
                    "feedback_target": "result-msg-9",
                    "raw_payload_ref": "fixture://wecom/callback/feedback-9",
                },
                created_at="2026-06-28T04:00:09Z",
            )

        self.assertIn("unsupported", str(ctx.exception))

    def test_file_attachment_with_mime_type(self) -> None:
        event = normalize_wecom_turn(
            {
                "MsgId": "msg-mime",
                "FromUserName": "lawyer-10",
                "ConversationId": "conv-10",
                "MsgType": "file",
                "MediaId": "media-mime",
                "FileName": "contract.pdf",
                "mime_type": "application/pdf",
                "raw_payload_ref": "fixture://wecom/callback/msg-mime",
            },
            received_at="2026-06-28T04:00:10Z",
        )

        self.assertEqual(event["attachments"][0]["mime_type"], "application/pdf")

    def test_media_callback_without_media_ref_has_no_attachments(self) -> None:
        event = normalize_wecom_turn(
            {
                "MsgId": "msg-no-media",
                "FromUserName": "lawyer-11",
                "ConversationId": "conv-11",
                "MsgType": "image",
                "raw_payload_ref": "fixture://wecom/callback/msg-no-media",
            },
            received_at="2026-06-28T04:00:11Z",
        )

        self.assertNotIn("attachments", event)

    def test_missing_conversation_id_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_wecom_turn(
                {
                    "MsgId": "msg-no-conv",
                    "FromUserName": "lawyer-12",
                    "MsgType": "text",
                    "raw_payload_ref": "fixture://wecom/callback/msg-no-conv",
                },
                received_at="2026-06-28T04:00:12Z",
            )

        self.assertIn("conversation_id", str(ctx.exception))

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
