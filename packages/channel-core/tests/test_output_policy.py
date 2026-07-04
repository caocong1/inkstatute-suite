from __future__ import annotations

import unittest

from channel_core.output_policy import OutputPolicyDecision, apply_output_policy
from channel_core.owned_notices import OWNED_NOTICE_TEMPLATES, NoticeKind, build_owned_notice


class OutputPolicyTests(unittest.TestCase):
    def test_blocks_internal_notice(self) -> None:
        decision = apply_output_policy("ADMIN_NOTICE: delivery debug stack trace token=secret")
        self.assertEqual(decision.action, "block")
        self.assertIsNone(decision.visible_text)
        self.assertNotIn("token=secret", str(decision.audit_metadata))

    def test_rewrites_backend_lifecycle_notice(self) -> None:
        decision = apply_output_policy("gateway online after restart")
        self.assertEqual(decision.action, "rewrite")
        self.assertIn(decision.visible_text, OWNED_NOTICE_TEMPLATES["backend_lifecycle"])
        self.assertNotIn("gateway online", str(decision.audit_metadata))

    def test_allows_business_output(self) -> None:
        answer = "根据《民法典》第五百六十三条，若对方根本违约，你方通常可以主张解除合同。"
        decision = apply_output_policy(answer)
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.visible_text, answer)

    def test_policy_name_changes_audit_metadata(self) -> None:
        decision = apply_output_policy("hello", policy_name="custom_policy")
        self.assertEqual(decision.audit_metadata["policy"], "custom_policy")

    def test_default_policy_name_is_channel(self) -> None:
        decision = apply_output_policy("hello")
        self.assertEqual(decision.audit_metadata["policy"], "inkstatute_channel_output_boundary")


class OwnedNoticesTests(unittest.TestCase):
    def test_build_owned_notice_returns_non_empty_for_each_kind(self) -> None:
        for kind in OWNED_NOTICE_TEMPLATES:
            notice = build_owned_notice(kind, seed="test-seed")
            self.assertIsInstance(notice, str)
            self.assertGreater(len(notice), 0)

    def test_seed_is_stable(self) -> None:
        first = build_owned_notice("failed", seed="msg-1")
        second = build_owned_notice("failed", seed="msg-1")
        self.assertEqual(first, second)

    def test_owned_notice_in_templates(self) -> None:
        notice = build_owned_notice("processing", seed="msg-1")
        self.assertIn(notice, OWNED_NOTICE_TEMPLATES["processing"])


if __name__ == "__main__":
    unittest.main()
