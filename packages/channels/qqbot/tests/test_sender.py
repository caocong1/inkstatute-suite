"""Unit tests for QQ egress envelope builders (text, markdown, keyboard) and output policy."""

from __future__ import annotations

import unittest

from inkstatute_channels_qqbot.sender import (
    FEEDBACK_ACTIONS,
    build_feedback_keyboard_envelope,
    build_markdown_envelope,
    build_text_envelope,
    strip_for_wire,
)

LEGAL_CONTENT = "根据《民法典》……"
BLOCKED_NOTICE = "ADMIN_NOTICE: delivery debug stack trace token=secret"


class SenderEnvelopeTests(unittest.TestCase):
    def test_feedback_actions_canonical_order(self) -> None:
        self.assertEqual(
            tuple(FEEDBACK_ACTIONS),
            ("up", "down", "needs_fix", "route_wrong"),
        )

    def test_build_text_envelope_msg_type_0_with_msg_id_seq(self) -> None:
        envelope = build_text_envelope(
            content=LEGAL_CONTENT,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 0)
        self.assertEqual(envelope["content"], LEGAL_CONTENT)
        self.assertEqual(envelope["msg_id"], "inbound-1")
        self.assertEqual(envelope["msg_seq"], 1)
        self.assertEqual(envelope["policy"]["action"], "allow")

    def test_build_markdown_envelope_msg_type_2(self) -> None:
        envelope = build_markdown_envelope(
            content=LEGAL_CONTENT,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 2)
        self.assertEqual(envelope["markdown"], {"content": LEGAL_CONTENT})
        self.assertEqual(envelope["msg_id"], "inbound-1")
        self.assertEqual(envelope["msg_seq"], 1)
        self.assertEqual(envelope["policy"]["action"], "allow")

    def test_build_feedback_keyboard_envelope_four_callbacks(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 2)
        self.assertIn("content", envelope["markdown"])
        self.assertTrue(envelope["markdown"]["content"])
        self.assertNotIn("template_card", envelope)

        buttons = envelope["keyboard"]["content"]["rows"][0]["buttons"]
        self.assertEqual(len(buttons), 4)
        action_data = {button["action"]["data"] for button in buttons}
        self.assertEqual(
            action_data,
            {"up", "down", "needs_fix", "route_wrong"},
        )
        for button in buttons:
            self.assertEqual(button["action"]["type"], 1)
            self.assertEqual(button["action"]["permission"]["type"], 2)

    def test_text_blocks_gateway_notice(self) -> None:
        envelope = build_text_envelope(
            content=BLOCKED_NOTICE,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertEqual(envelope["policy"]["action"], "block")
        self.assertNotIn("content", envelope)
        wire = strip_for_wire(envelope)
        self.assertNotIn("content", wire)
        self.assertNotIn("policy", wire)

    def test_strip_for_wire_removes_policy_and_inkstatute(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )
        wire = strip_for_wire(envelope)

        self.assertNotIn("policy", wire)
        self.assertNotIn("inkstatute", wire)
        self.assertIn("msg_type", wire)
        self.assertIn("markdown", wire)
        self.assertIn("keyboard", wire)
        self.assertIn("msg_id", wire)
        self.assertIn("msg_seq", wire)
        # Audit envelope must remain intact (strip is a copy).
        self.assertIn("policy", envelope)
        self.assertIn("inkstatute", envelope)

    def test_keyboard_rows_nested_under_content(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )
        keyboard = envelope["keyboard"]

        self.assertNotIn("rows", keyboard)
        self.assertIn("rows", keyboard["content"])
        self.assertIsInstance(keyboard["content"]["rows"], list)


if __name__ == "__main__":
    unittest.main()
