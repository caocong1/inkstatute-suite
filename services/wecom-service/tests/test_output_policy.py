from __future__ import annotations

import unittest

from wecom_service.output_policy import OutputPolicyDecision, apply_output_policy
from wecom_service.owned_notices import OWNED_NOTICE_TEMPLATES, build_owned_notice
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

    def test_allows_trade_secret_legal_answer_without_treating_secret_as_credential(self) -> None:
        answer = "A trade secret claim usually turns on secrecy measures and improper acquisition."

        decision = apply_output_policy(answer)

        self.assertEqual(decision.action, "allow")
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
        self.assertIn(decision.visible_text, OWNED_NOTICE_TEMPLATES["backend_lifecycle"])
        self.assertEqual(decision.audit_metadata["replacement_owner"], "inkstatute_wecom_service")
        self.assertNotIn("gateway online", str(decision.audit_metadata))

    def test_owned_notice_can_vary_without_backend_terms(self) -> None:
        generated = {build_owned_notice("processing", seed=f"message-{index}") for index in range(20)}

        self.assertGreater(len(generated), 1)
        self.assertLessEqual(generated, set(OWNED_NOTICE_TEMPLATES["processing"]))
        for notice in generated:
            self.assertRegex(notice, r"^小律")
            self.assertNotRegex(notice.lower(), r"hermes|gateway|系统|安全边界|管理员")

    def test_owned_notice_seed_is_stable_for_replay(self) -> None:
        first = build_owned_notice("failed", seed="message-1")
        second = build_owned_notice("failed", seed="message-1")

        self.assertEqual(first, second)
        self.assertIn(first, OWNED_NOTICE_TEMPLATES["failed"])

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
