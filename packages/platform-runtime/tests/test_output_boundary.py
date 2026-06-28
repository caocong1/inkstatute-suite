from __future__ import annotations

from pathlib import Path
import unittest

from platform_runtime import BoundaryAction, DefaultAssistantOutputBoundary


class DefaultAssistantOutputBoundaryTests(unittest.TestCase):
    def test_allows_business_answer_without_rewriting(self) -> None:
        text = "business answer"
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_allows_legal_conclusion_byte_for_byte(self) -> None:
        text = "Under the contract, the supplier must cure the breach before termination."

        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_blocks_or_rewrites_backend_and_operator_notices_without_original_audit_text(self) -> None:
        samples = {
            "Hermes gateway restarted for profile /home/example/.hermes/profiles/lawfirm": BoundaryAction.BLOCK,
            "Self-update available: run /update now": BoundaryAction.REWRITE,
            "/help /status /credits /insights": BoundaryAction.BLOCK,
            "ADMIN_NOTICE delivery debug stack trace token=secret": BoundaryAction.BLOCK,
            "Tool progress: calling internal retrieval step": BoundaryAction.REWRITE,
            "Dangerous command approval required before shell execution": BoundaryAction.REWRITE,
        }

        boundary = DefaultAssistantOutputBoundary()
        for sample, expected_action in samples.items():
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)

                self.assertEqual(decision.action, expected_action)
                self.assertNotIn(sample, repr(decision.audit_metadata))
                self.assertEqual(decision.audit_metadata["privacy"], "no_original_text_stored")
                self.assertRegex(decision.audit_metadata["input_hash_prefix"], r"^[0-9a-f]{16}$")
                self.assertEqual(decision.audit_metadata["input_length"], len(sample))
                if decision.visible_text is not None:
                    self.assertNotIn("Hermes", decision.visible_text)
                    self.assertNotIn("gateway", decision.visible_text.lower())
                    self.assertNotIn("token=secret", decision.visible_text)

    def test_trade_secret_business_answer_is_not_treated_as_credential(self) -> None:
        text = "A trade secret claim depends on secrecy measures and improper acquisition."

        decision = DefaultAssistantOutputBoundary().apply("ordinary_user", text=text)

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_runtime_source_does_not_embed_concrete_leak_examples(self) -> None:
        src_root = Path("packages/platform-runtime/src")
        source_text = "\n".join(path.read_text(encoding="utf-8") for path in src_root.rglob("*.py"))

        for forbidden in ("Hermes", "WeCom", "lawfirm", "gateway", ".hermes"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), source_text.lower())


if __name__ == "__main__":
    unittest.main()
