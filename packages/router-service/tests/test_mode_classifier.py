"""Tests for the mode classifier — ported 1:1 from agent_classifier.rs (lines 468-691).

Per AGENTS.md: "When porting logic from lawyer-desktop (Rust), use the
Rust-side test cases as the Python-side golden fixture set."

14 test cases covering:
- JSON parsing with no committed task → action pinned to "continue"
- Chat mode for risk analysis question
- Draft mode for formal document request
- Retry: fast fails → primary succeeds
- Double failure → fallback keeps current_mode
- Switch action when task is committed
- Aside action for mid-draft question
- Unknown action → continue (safe default)
- Chinese mode aliases (问答, 法律问答, 文书起草, 案情分析)
- Chinese mode label "文书起草" → Draft
- Fallback → Chat when no active document
- Fallback does NOT infer from user text keywords (safety property)
- Fallback keeps diagnostic for invalid JSON
- Fallback keeps diagnostic for invalid mode
"""

from __future__ import annotations

import unittest

from inkstatute_router_service.mode_classifier import (
    AgentMode,
    ClassifyContext,
    ClassifyResult,
    LLMModeClassifier,
    classify_with_retry,
    fallback_classify,
    parse_classifier_response,
    parse_mode_str,
)


def _ctx_with(
    message: str,
    current_mode: str | None = None,
    has_doc: bool = False,
) -> ClassifyContext:
    """Helper mirroring Rust ``ctx_with`` (agent_classifier.rs lines 489-499)."""
    return ClassifyContext(
        user_message=message,
        has_directory_ref=False,
        has_file_ref=False,
        directory_aliases=[],
        current_mode=current_mode,
        current_task_label="股权转让协议起草" if current_mode is not None else None,
        has_active_document=has_doc,
    )


class _MockLLM:
    """Mock LLM callable for LLMModeClassifier tests.

    Mirrors Rust ``MockClassifierProvider`` (agent_classifier.rs lines 391-466).
    """

    def __init__(self, reply: str | None, error: str | None = None) -> None:
        self._reply = reply
        self._error = error
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self._error is not None:
            raise Exception(self._error)
        assert self._reply is not None
        return self._reply


class _MockClassifier:
    """Mock ModeClassifierPort for retry tests.

    Mirrors the Rust test pattern of wrapping a MockClassifierProvider
    in the classify flow.
    """

    def __init__(self, result: ClassifyResult) -> None:
        self.result = result
        self.calls = 0

    def classify(self, context: ClassifyContext) -> ClassifyResult:
        self.calls += 1
        return self.result


class TestModeClassifier(unittest.TestCase):
    """Port the 14 unit tests from agent_classifier.rs (lines 468-691)."""

    # 1. parses_classifier_json
    def test_parses_classifier_json(self) -> None:
        """JSON parsing, no committed task → action pinned to continue."""
        ctx = ClassifyContext(
            user_message="生成诉讼方案",
            has_directory_ref=True,
            has_file_ref=False,
            directory_aliases=["案件资料"],
            current_mode=None,
            current_task_label=None,
            has_active_document=False,
        )
        r = parse_classifier_response(
            '{"mode":"evidence","label":"诉讼方案","reason":"需检索案卷"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.EVIDENCE)
        self.assertEqual(r.source, "llm")
        # No committed task → action pinned to continue regardless of model.
        self.assertEqual(r.action, "continue")

    # 2. aviation_regulatory_risk_question_is_chat_when_llm_classifies_it
    def test_aviation_regulatory_risk_question_is_chat(self) -> None:
        """Chat mode for risk analysis question."""
        ctx = _ctx_with(
            "ICAO technical instructions supplement applies to power bank carriage. Analyze enforcement legal risk.",
            None,
            False,
        )
        r = parse_classifier_response(
            '{"mode":"chat","action":"continue","label":"aviation regulatory risk","reason":"risk analysis answer, not a formal document"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.action, "continue")
        self.assertEqual(r.label, "aviation regulatory risk")

    # 3. formal_legal_opinion_document_is_draft_when_llm_classifies_it
    def test_formal_legal_opinion_document_is_draft(self) -> None:
        """Draft mode for formal document request."""
        ctx = _ctx_with(
            "Generate a formal legal opinion document for client submission.",
            None,
            False,
        )
        r = parse_classifier_response(
            '{"mode":"draft","action":"continue","label":"legal opinion drafting","reason":"the user asks for a formal document artifact"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.DRAFT)
        self.assertEqual(r.label, "legal opinion drafting")

    # 4. retry_uses_primary_when_fast_classifier_falls_back
    def test_retry_uses_primary_when_fast_falls_back(self) -> None:
        """Retry: fast fails → primary succeeds."""
        ctx = _ctx_with(
            "Analyze this regulatory requirement and risks.",
            None,
            False,
        )
        fast = _MockLLM("")  # empty → fallback
        primary = _MockLLM(
            '{"mode":"chat","label":"regulatory risk answer","reason":"answer in chat"}',
        )
        fast_clf = LLMModeClassifier(fast)
        primary_clf = LLMModeClassifier(primary)

        r = classify_with_retry(fast_clf, primary_clf, ctx)

        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.source, "llm")
        self.assertEqual(r.label, "regulatory risk answer")
        self.assertEqual(fast.calls, 1)
        self.assertEqual(primary.calls, 1)

    # 5. double_classifier_failure_degrades_to_current_committed_mode
    def test_double_failure_degrades_to_current_committed_mode(self) -> None:
        """Double failure → fallback keeps current_mode."""
        ctx = _ctx_with("Continue revising clause 3.", "draft", True)
        fast = _MockLLM(None, error="fast down")
        primary = _MockLLM(None, error="primary down")
        fast_clf = LLMModeClassifier(fast)
        primary_clf = LLMModeClassifier(primary)

        r = classify_with_retry(fast_clf, primary_clf, ctx)

        self.assertEqual(r.mode, AgentMode.DRAFT)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.action, "continue")
        self.assertTrue(r.label)  # not empty

    # 6. parses_switch_action_when_task_committed
    def test_parses_switch_action_when_task_committed(self) -> None:
        """Switch action when task is committed."""
        ctx = _ctx_with("改成起草一份房屋租赁合同", "draft", True)
        r = parse_classifier_response(
            '{"mode":"draft","action":"switch","label":"房屋租赁合同起草","reason":"换一种文书"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.DRAFT)
        self.assertEqual(r.action, "switch")

    # 7. parses_aside_action_for_mid_draft_question
    def test_parses_aside_action_for_mid_draft_question(self) -> None:
        """Aside action for mid-draft question."""
        ctx = _ctx_with("违约金一般怎么约定？", "draft", True)
        r = parse_classifier_response(
            '{"mode":"chat","action":"aside","label":"违约金咨询","reason":"顺带提问"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.action, "aside")

    # 8. unknown_action_degrades_to_continue
    def test_unknown_action_degrades_to_continue(self) -> None:
        """Unknown action → continue (safe default)."""
        ctx = _ctx_with("继续完善第三条", "draft", True)
        r = parse_classifier_response(
            '{"mode":"draft","action":"bogus","label":"协议修改"}',
            ctx,
        )
        self.assertEqual(r.action, "continue")

    # 9. parses_qa_mode_alias
    def test_parses_qa_mode_alias(self) -> None:
        """Chinese mode aliases (问答, 法律问答, 文书起草, 案情分析)."""
        self.assertEqual(parse_mode_str("问答"), AgentMode.CHAT)
        self.assertEqual(parse_mode_str("法律问答"), AgentMode.CHAT)
        self.assertEqual(parse_mode_str("文书起草"), AgentMode.DRAFT)
        self.assertEqual(parse_mode_str("案情分析"), AgentMode.EVIDENCE)

    # 10. parses_llm_chinese_mode_label_for_draft
    def test_parses_llm_chinese_mode_label_for_draft(self) -> None:
        """Chinese mode label "文书起草" → Draft."""
        ctx = _ctx_with("帮我起草一份劳动合同", None, False)
        r = parse_classifier_response(
            '{"mode":"文书起草","action":"continue","label":"劳动合同起草","reason":"用户要生成正式文书"}',
            ctx,
        )
        self.assertEqual(r.mode, AgentMode.DRAFT)
        self.assertEqual(r.label, "劳动合同起草")
        self.assertEqual(r.source, "llm")

    # 11. fallback_defaults_to_chat_without_current_artifact
    def test_fallback_defaults_to_chat_without_current_artifact(self) -> None:
        """Fallback → Chat when no active document."""
        ctx = ClassifyContext(
            user_message="生成诉讼方案",
            has_directory_ref=True,
            has_file_ref=False,
            directory_aliases=[],
            current_mode=None,
            current_task_label=None,
            has_active_document=False,
        )
        r = fallback_classify(ctx, "request_failed", "boom")
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.fallback_reason, "request_failed")

    # 12. fallback_does_not_infer_draft_from_user_text
    def test_fallback_does_not_infer_draft_from_user_text(self) -> None:
        """Fallback does NOT infer from user text keywords (safety property)."""
        ctx = ClassifyContext(
            user_message=(
                "帮我起草一份劳动合同：甲方杭州某科技有限公司招聘乙方王五担任高级软件工程师，"
                "月薪人民币25,000元，合同期限三年。"
            ),
            has_directory_ref=False,
            has_file_ref=False,
            directory_aliases=[],
            current_mode=None,
            current_task_label=None,
            has_active_document=False,
        )
        r = parse_classifier_response("不是 JSON", ctx)
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.label, "法律问答")
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.fallback_reason, "invalid_json")

    # 13. fallback_keeps_invalid_json_diagnostic
    def test_fallback_keeps_invalid_json_diagnostic(self) -> None:
        """Fallback keeps diagnostic for invalid JSON."""
        ctx = ClassifyContext(
            user_message="请解释合同解除",
            has_directory_ref=False,
            has_file_ref=False,
            directory_aliases=[],
            current_mode=None,
            current_task_label=None,
            has_active_document=False,
        )
        r = parse_classifier_response("不是 JSON", ctx)
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.fallback_reason, "invalid_json")
        self.assertIn("JSON", r.diagnostic or "")

    # 14. fallback_keeps_invalid_mode_diagnostic
    def test_fallback_keeps_invalid_mode_diagnostic(self) -> None:
        """Fallback keeps diagnostic for invalid mode."""
        ctx = ClassifyContext(
            user_message="请起草合同",
            has_directory_ref=False,
            has_file_ref=False,
            directory_aliases=[],
            current_mode=None,
            current_task_label=None,
            has_active_document=False,
        )
        r = parse_classifier_response('{"mode":"other"}', ctx)
        self.assertEqual(r.mode, AgentMode.CHAT)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.fallback_reason, "invalid_mode")


if __name__ == "__main__":
    unittest.main()
