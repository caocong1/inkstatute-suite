from __future__ import annotations

import unittest

from channel_core.delivery_guard import DeliveryCompletionAssessment, assess_delivery_completion


class DeliveryGuardTests(unittest.TestCase):
    def test_rejects_progress_only_docx_output_when_user_requested_artifact(self) -> None:
        decision = assess_delivery_completion(
            user_text="请从乙方立场审查合同，生成带修订痕迹的 DOCX。",
            answer_text="合同全文已解析完毕。现在从乙方立场进行分层审查，编制审查修订项并生成带修订痕迹的 DOCX。",
            media_count=1,
            file_count=0,
        )

        self.assertFalse(decision.completed)
        self.assertEqual(decision.issue_code, "agent_backend_incomplete_output")
        self.assertTrue(decision.requested_file_delivery)
        self.assertTrue(decision.progress_only)

    def test_allows_file_delivery_marker_for_requested_docx(self) -> None:
        decision = assess_delivery_completion(
            user_text="生成带修订痕迹的 DOCX。",
            answer_text="审查修订稿已生成。\nMEDIA:/tmp/contract_review/final.docx",
            media_count=1,
            file_count=1,
        )

        self.assertTrue(decision.completed)
        self.assertEqual(decision.reason, "delivery_contract_satisfied")

    def test_allows_plain_business_answer_for_summary_request(self) -> None:
        decision = assess_delivery_completion(
            user_text="概括这份合同的主要风险。",
            answer_text="主要风险包括付款节点、知识产权归属和验收标准不清。",
            media_count=1,
            file_count=0,
        )

        self.assertTrue(decision.completed)

    def test_as_metadata_returns_expected_dict(self) -> None:
        decision = DeliveryCompletionAssessment(
            completed=False,
            reason="test_reason",
            issue_code="test_code",
            requested_file_delivery=True,
            progress_only=True,
        )
        meta = decision.as_metadata()
        self.assertEqual(meta["completed"], False)
        self.assertEqual(meta["reason"], "test_reason")
        self.assertEqual(meta["issue_code"], "test_code")
        self.assertEqual(meta["requested_file_delivery"], True)
        self.assertEqual(meta["progress_only"], True)


if __name__ == "__main__":
    unittest.main()
