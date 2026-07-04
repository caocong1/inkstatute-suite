from __future__ import annotations

import unittest

from channel_core.idempotency import channel_idempotency_key, digest_short, string_or_none


class IdempotencyKeyTests(unittest.TestCase):
    def test_message_id_stable_field(self) -> None:
        key = channel_idempotency_key({"message_id": "msg-001"})
        self.assertTrue(key.startswith("channel:message:"))
        self.assertEqual(len(key), len("channel:message:") + 24)

    def test_callback_id_stable_field(self) -> None:
        key = channel_idempotency_key({"callback_id": "cb-001"})
        self.assertTrue(key.startswith("channel:callback:"))

    def test_feedback_id_stable_field(self) -> None:
        key = channel_idempotency_key({"feedback_id": "fb-001"})
        self.assertTrue(key.startswith("channel:feedback:"))

    def test_fallback_when_no_stable_field(self) -> None:
        key = channel_idempotency_key(
            {"channel": "wecom", "user_id": "user-1", "conversation_id": "conv-1", "created_at": "2026-01-01", "event_type": "text"}
        )
        self.assertTrue(key.startswith("channel:fallback:"))

    def test_channel_prefix_changes_prefix(self) -> None:
        key = channel_idempotency_key({"message_id": "msg-001"}, channel_prefix="wecom")
        self.assertTrue(key.startswith("wecom:message:"))

    def test_deterministic_same_callback_same_key(self) -> None:
        callback = {"message_id": "msg-001", "user_id": "user-1"}
        key1 = channel_idempotency_key(callback)
        key2 = channel_idempotency_key(callback)
        self.assertEqual(key1, key2)

    def test_wecom_alias_fields(self) -> None:
        key_msgid = channel_idempotency_key({"MsgId": "msg-002"}, channel_prefix="wecom")
        key_msgid2 = channel_idempotency_key({"msg_id": "msg-002"}, channel_prefix="wecom")
        self.assertEqual(key_msgid, key_msgid2)

    def test_fallback_uses_wecom_aliases(self) -> None:
        key = channel_idempotency_key(
            {"FromUserName": "user-1", "ChatId": "conv-1", "CreateTime": "2026-01-01", "MsgType": "text"},
            channel_prefix="wecom",
        )
        self.assertTrue(key.startswith("wecom:fallback:"))


class HelperTests(unittest.TestCase):
    def test_digest_short_is_24_chars(self) -> None:
        self.assertEqual(len(digest_short("hello")), 24)

    def test_digest_short_is_deterministic(self) -> None:
        self.assertEqual(digest_short("test"), digest_short("test"))

    def test_string_or_none_returns_stripped(self) -> None:
        self.assertEqual(string_or_none("  hi  "), "hi")

    def test_string_or_none_returns_none_for_empty(self) -> None:
        self.assertIsNone(string_or_none(""))
        self.assertIsNone(string_or_none("   "))
        self.assertIsNone(string_or_none(None))


if __name__ == "__main__":
    unittest.main()
