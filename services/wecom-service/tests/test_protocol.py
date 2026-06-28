from __future__ import annotations

import hashlib
import unittest

from wecom_service.idempotency import wecom_idempotency_key
from wecom_service.protocol import (
    RawPayloadForbiddenError,
    ack_response,
    parse_callback_envelope,
    verify_callback_signature,
)


class WeComProtocolTests(unittest.TestCase):
    def test_verify_callback_signature_uses_sorted_sha1_fixture(self) -> None:
        token = "fixture-token"
        timestamp = "1719300000"
        nonce = "nonce-7"
        encrypted_payload = "encrypted-fixture"
        expected = hashlib.sha1(
            "".join(sorted([token, timestamp, nonce, encrypted_payload])).encode("utf-8")
        ).hexdigest()

        self.assertTrue(
            verify_callback_signature(token, timestamp, nonce, expected, encrypted_payload)
        )
        self.assertFalse(
            verify_callback_signature(token, timestamp, nonce, "not-the-signature", encrypted_payload)
        )

    def test_ack_response_is_success_string(self) -> None:
        self.assertEqual(ack_response(), "success")

    def test_parse_callback_envelope_rejects_raw_payload_and_keeps_reference(self) -> None:
        parsed = parse_callback_envelope(
            {
                "MsgId": "msg-123",
                "FromUserName": "lawyer-1",
                "ConversationId": "conv-1",
                "MsgType": "text",
                "CreateTime": "1719300000",
                "Content": "sanitized text",
                "raw_payload_ref": "fixture://wecom/callback/msg-123",
                "nested": {
                    "ignored": "value",
                    "raw_payload_ref": "fixture://wecom/callback/nested",
                },
            }
        )

        self.assertEqual(parsed["message_id"], "msg-123")
        self.assertEqual(parsed["user_id"], "lawyer-1")
        self.assertEqual(parsed["conversation_id"], "conv-1")
        self.assertEqual(parsed["message_type"], "text")
        self.assertEqual(parsed["raw_payload_ref"], "fixture://wecom/callback/msg-123")
        self.assertNotIn("raw_payload", parsed)
        self.assertNotIn("nested", parsed)

        with self.assertRaises(RawPayloadForbiddenError):
            parse_callback_envelope(
                {
                    "MsgId": "msg-raw",
                    "raw_payload": "<xml>must-not-be-committed</xml>",
                }
            )

    def test_idempotency_key_is_stable_for_duplicate_sanitized_callbacks(self) -> None:
        callback = {
            "channel": "wecom",
            "message_id": "msg-456",
            "user_id": "lawyer-2",
            "conversation_id": "conv-2",
            "created_at": "2026-06-28T04:00:00Z",
            "event_type": "message",
            "raw_payload_ref": "fixture://wecom/callback/msg-456",
        }

        duplicate = dict(callback)

        self.assertEqual(wecom_idempotency_key(callback), wecom_idempotency_key(duplicate))


if __name__ == "__main__":
    unittest.main()
