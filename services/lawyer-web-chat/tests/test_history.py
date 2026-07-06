"""Tests for MessageHistory — in-memory store with output boundary filtering."""

from __future__ import annotations

import unittest

from lawyer_web_chat.boundary import ChatBoundary
from lawyer_web_chat.history import MessageHistory
from platform_runtime.tenant_scope import ScopedQueryFilter


class MessageHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.history = MessageHistory()

    def test_add_message_returns_message_with_id(self) -> None:
        msg = self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="What are the requirements?",
            payload_ref="ref://conv-1/msg-1",
        )
        self.assertIsNotNone(msg.message_id)
        self.assertEqual(msg.conversation_id, "conv-1")
        self.assertEqual(msg.sender, "lawyer")
        self.assertIn("requirements", msg.content)

    def test_add_message_filters_backend_noise(self) -> None:
        msg = self.history.add_message(
            conversation_id="conv-1",
            sender="assistant",
            content="model: gpt-4 processing your request",
            payload_ref="ref://conv-1/msg-1",
        )
        self.assertEqual(msg.content, "[content filtered]")

    def test_add_message_rewrites_backend_lifecycle(self) -> None:
        msg = self.history.add_message(
            conversation_id="conv-1",
            sender="assistant",
            content="self-update in progress, restarting",
            payload_ref="ref://conv-1/msg-1",
        )
        self.assertIn("InkStatute", msg.content)
        self.assertNotIn("restarting", msg.content)

    def test_add_message_escapes_html(self) -> None:
        msg = self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Hello <script>alert(1)</script>",
            payload_ref="ref://conv-1/msg-1",
        )
        self.assertIn("&lt;script&gt;", msg.content)
        self.assertNotIn("<script>alert(1)</script>", msg.content)

    def test_get_history_returns_messages(self) -> None:
        for i in range(5):
            self.history.add_message(
                conversation_id="conv-1",
                sender="lawyer" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                payload_ref=f"ref://conv-1/msg-{i}",
            )
        result = self.history.get_history("conv-1")
        self.assertEqual(result["count"], 5)
        self.assertEqual(len(result["items"]), 5)
        self.assertFalse(result["has_more"])

    def test_get_history_with_limit_and_cursor(self) -> None:
        for i in range(10):
            self.history.add_message(
                conversation_id="conv-1",
                sender="lawyer",
                content=f"Message {i}",
                payload_ref=f"ref://conv-1/msg-{i}",
            )
        page1 = self.history.get_history("conv-1", limit=3)
        self.assertEqual(page1["count"], 3)
        self.assertTrue(page1["has_more"])
        self.assertIsNotNone(page1["next_cursor"])

        page2 = self.history.get_history("conv-1", limit=3, cursor=page1["next_cursor"])
        self.assertEqual(page2["count"], 3)
        self.assertTrue(page2["has_more"])

    def test_get_history_empty_conversation(self) -> None:
        result = self.history.get_history("nonexistent")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["items"], [])

    def test_get_history_does_not_return_raw_payload(self) -> None:
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Hello",
            payload_ref="ref://conv-1/msg-1",
        )
        result = self.history.get_history("conv-1")
        for item in result["items"]:
            self.assertIn("payload_ref", item)
            self.assertNotIn("raw_payload", item)
            self.assertNotIn("raw_body", item)

    def test_clear_history(self) -> None:
        for i in range(3):
            self.history.add_message(
                conversation_id="conv-1",
                sender="lawyer",
                content=f"Message {i}",
                payload_ref=f"ref://conv-1/msg-{i}",
            )
        removed = self.history.clear("conv-1")
        self.assertEqual(removed, 3)
        result = self.history.get_history("conv-1")
        self.assertEqual(result["count"], 0)

    def test_get_history_with_active_tenant_filter(self) -> None:
        """Active filter → only messages with matching tenant_id in metadata."""
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Message from tenant-1",
            payload_ref="ref://1",
            metadata={"tenant_id": "tenant-1"},
        )
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Message from tenant-2",
            payload_ref="ref://2",
            metadata={"tenant_id": "tenant-2"},
        )
        active = ScopedQueryFilter(tenant_id="tenant-1", active=True)
        result = self.history.get_history("conv-1", tenant_filter=active)
        self.assertEqual(result["count"], 1)
        self.assertIn("tenant-1", result["items"][0]["content"])

    def test_get_history_with_disabled_filter_returns_all(self) -> None:
        """Disabled filter → all messages returned (no regression)."""
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Message from tenant-1",
            payload_ref="ref://1",
            metadata={"tenant_id": "tenant-1"},
        )
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Message from tenant-2",
            payload_ref="ref://2",
            metadata={"tenant_id": "tenant-2"},
        )
        disabled = ScopedQueryFilter.disabled()
        result = self.history.get_history("conv-1", tenant_filter=disabled)
        self.assertEqual(result["count"], 2)

    def test_get_history_with_no_filter_returns_all(self) -> None:
        """No filter → all messages returned (backward compat)."""
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Message",
            payload_ref="ref://1",
            metadata={"tenant_id": "tenant-1"},
        )
        result = self.history.get_history("conv-1", tenant_filter=None)
        self.assertEqual(result["count"], 1)

    def test_get_history_active_filter_excludes_messages_without_tenant_id(self) -> None:
        """Active filter → messages without tenant_id in metadata are excluded (fail-safe)."""
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="No tenant metadata",
            payload_ref="ref://1",
        )
        self.history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Has tenant metadata",
            payload_ref="ref://2",
            metadata={"tenant_id": "tenant-1"},
        )
        active = ScopedQueryFilter(tenant_id="tenant-1", active=True)
        result = self.history.get_history("conv-1", tenant_filter=active)
        self.assertEqual(result["count"], 1)
        self.assertIn("Has tenant metadata", result["items"][0]["content"])


if __name__ == "__main__":
    unittest.main()
