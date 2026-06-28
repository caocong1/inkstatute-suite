from __future__ import annotations

import unittest

from wecom_service.output_policy import OutputPolicyDecision, apply_output_policy
from wecom_service.sender import (
    build_file_send_envelope,
    build_template_card_envelope,
    build_text_send_envelope,
)


class OutputPolicyTests(unittest.TestCase):
    def test_blocks_or_rewrites_backend_meta_notices(self) -> None:
        samples = [
            "Hermes gateway restarted for profile /home/sorawatcher/.hermes/profiles/lawfirm",
            "Self-update available: run /update now",
            "/help /status /credits /insights",
            "ADMIN_NOTICE: delivery debug stack trace token=secret",
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                decision = apply_output_policy(sample)
                self.assertIn(decision.action, {"block", "rewrite"})
                self.assertNotIn(sample, str(decision.audit_metadata))
                if decision.visible_text:
                    self.assertNotRegex(decision.visible_text.lower(), r"hermes|gateway|/help|token|stack trace")

    def test_allows_legal_business_answer_without_rewriting_conclusion(self) -> None:
        answer = "根据《民法典》第五百六十三条，若对方根本违约，你方通常可以主张解除合同。"

        decision = apply_output_policy(answer)

        self.assertEqual(decision, OutputPolicyDecision("allow", "business_output", answer, decision.audit_metadata))
        self.assertEqual(decision.visible_text, answer)

    def test_text_envelope_has_no_visible_text_when_policy_blocks(self) -> None:
        envelope = build_text_send_envelope(
            to_user="lawyer-1",
            text="Hermes gateway disconnected: token=abc",
        )

        self.assertEqual(envelope["policy"]["action"], "block")
        self.assertNotIn("text", envelope)
        self.assertNotIn("Hermes", str(envelope))
        self.assertNotIn("token=abc", str(envelope))

    def test_rewrite_uses_inkstatute_owned_service_wording(self) -> None:
        decision = apply_output_policy("gateway online after restart")

        self.assertEqual(decision.action, "rewrite")
        self.assertEqual(decision.visible_text, "服务正在维护，请稍后再试。")
        self.assertEqual(decision.audit_metadata["replacement_owner"], "inkstatute_wecom_service")
        self.assertNotIn("gateway online", str(decision.audit_metadata))

    def test_allowed_file_and_card_envelopes_apply_policy(self) -> None:
        file_envelope = build_file_send_envelope(
            to_user="lawyer-1",
            media_id="media-1",
            description="合同修订稿已生成。",
        )
        card_envelope = build_template_card_envelope(
            to_user="lawyer-1",
            card_id="card-1",
            title="请评价本次回复",
            feedback_target="result-1",
        )

        self.assertEqual(file_envelope["msgtype"], "file")
        self.assertEqual(file_envelope["policy"]["action"], "allow")
        self.assertEqual(card_envelope["msgtype"], "template_card")
        self.assertEqual(card_envelope["policy"]["action"], "allow")


if __name__ == "__main__":
    unittest.main()
