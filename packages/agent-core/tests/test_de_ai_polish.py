"""De-AI polish pattern detection + removal tests (CORE-08).

The de-AI polish guardrail has NO Rust implementation — it is designed fresh
in Python.  These tests verify:

- AI-characteristic language patterns (AI self-references, hedging, "not
  legal advice" boilerplate) are removed.
- Legal meaning is preserved: citations, article numbers, conclusions, and
  clean legal text are never altered.
- Multiple blank lines left by removals are collapsed.
- The pattern set is conservative — it does not over-aggressively alter
  legal text.

HG-1 (法律质量) is NOT auto-closable — these tests verify pattern mechanics,
not prompt legal quality.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.guardrails import de_ai_polish


class TestDeAiPolishRemoval(unittest.TestCase):
    """AI-characteristic patterns are removed."""

    def test_removes_ai_assistant_self_reference(self):
        text = "作为一个AI助手，我为您分析如下。"
        result = de_ai_polish(text)
        self.assertNotIn("作为一个AI助手", result)
        self.assertIn("我为您分析如下。", result)

    def test_removes_bare_ai_self_reference(self):
        text = "作为AI，我建议查阅相关法条。"
        result = de_ai_polish(text)
        self.assertNotIn("作为AI", result)
        self.assertIn("我建议查阅相关法条。", result)

    def test_removes_ai_ren_gong_zhi_neng_self_reference(self):
        text = "作为一个人工智能，本回答基于公开资料。"
        result = de_ai_polish(text)
        self.assertNotIn("作为一个人工智能", result)

    def test_removes_note_i_am_ai_disclaimer(self):
        text = "请注意，我是AI，无法保证准确性。结论如下。"
        result = de_ai_polish(text)
        self.assertNotIn("请注意，我是AI", result)
        self.assertIn("无法保证准确性。结论如下。", result)

    def test_removes_understanding_hedging(self):
        text = "根据我的理解，该条款适用于本案。"
        result = de_ai_polish(text)
        self.assertNotIn("根据我的理解", result)
        self.assertIn("该条款适用于本案。", result)

    def test_removes_as_far_as_i_know_hedging(self):
        text = "据我所知，此为常见做法。"
        result = de_ai_polish(text)
        self.assertNotIn("据我所知", result)
        self.assertIn("此为常见做法。", result)

    def test_removes_cannot_provide_legal_advice_disclaimer(self):
        text = "我无法提供法律建议。依据《民法典》第五百八十五条。"
        result = de_ai_polish(text)
        self.assertNotIn("我无法提供法律建议", result)
        self.assertIn("依据《民法典》第五百八十五条。", result)

    def test_removes_for_reference_not_legal_advice_boilerplate(self):
        text = "以上分析仅供参考，不构成法律建议。"
        result = de_ai_polish(text)
        self.assertNotIn("以上分析仅供参考", result)
        self.assertNotIn("不构成法律建议", result)

    def test_removes_standalone_for_reference_boilerplate(self):
        text = "以上建议仅供参考。"
        result = de_ai_polish(text)
        self.assertNotIn("以上建议仅供参考", result)

    def test_preserves_cannot_meaning_when_dropping_ai_self_ref(self):
        """``我作为一个AI，无法…`` → ``无法…`` (the "cannot" meaning stays)."""
        text = "我作为一个AI，无法访问外部数据库。"
        result = de_ai_polish(text)
        self.assertNotIn("我作为一个AI", result)
        self.assertIn("无法访问外部数据库。", result)

    def test_removes_ai_generated_trailing_disclaimer(self):
        text = "结论：合同有效。请注意，本回答由AI生成。"
        result = de_ai_polish(text)
        self.assertNotIn("本回答由AI生成", result)
        self.assertIn("结论：合同有效。", result)


class TestDeAiPolishPreservesLegalText(unittest.TestCase):
    """Legal meaning is preserved — clean legal text is unchanged."""

    def test_preserves_clean_legal_text_unchanged(self):
        text = (
            "依据《中华人民共和国民法典》第五百八十五条，当事人可以约定违约金。"
            "《公司法》第20条对股东责任作了规定。"
        )
        self.assertEqual(de_ai_polish(text), text)

    def test_preserves_legal_citations_and_article_numbers(self):
        text = (
            "作为一个AI助手，依据《中华人民共和国民法典》第五百八十五条，"
            "违约方应承担违约责任。"
        )
        result = de_ai_polish(text)
        self.assertIn("《中华人民共和国民法典》第五百八十五条", result)
        self.assertIn("违约方应承担违约责任。", result)

    def test_preserves_legal_conclusions(self):
        text = (
            "以上分析仅供参考，不构成法律建议。"
            "结论：本合同因缺乏意思表示一致而未成立。"
        )
        result = de_ai_polish(text)
        self.assertIn("结论：本合同因缺乏意思表示一致而未成立。", result)

    def test_preserves_case_numbers(self):
        text = (
            "作为一个AI，参考案例（2024）渝01民初1234号，"
            "法院认定该条款有效。"
        )
        result = de_ai_polish(text)
        self.assertIn("（2024）渝01民初1234号", result)
        self.assertIn("法院认定该条款有效。", result)

    def test_does_not_alter_legal_meaning_conservative(self):
        """The conservative pattern set must not alter substantive legal text.

        A paragraph with legal reasoning but no AI patterns should be
        returned verbatim (modulo trailing whitespace).
        """
        text = (
            "本条规定的违约金具有赔偿性，不以实际损失为前提。"
            "若约定金额过高，法院可依申请酌减。"
            "《民法典》第五百八十五条第二款为请求权基础。"
        )
        self.assertEqual(de_ai_polish(text), text)


class TestDeAiPolishFormatting(unittest.TestCase):
    """Post-removal formatting is cleaned up."""

    def test_collapses_multiple_blank_lines(self):
        text = "作为一个AI助手，\n\n\n\n结论：合同有效。"
        result = de_ai_polish(text)
        # 3+ newlines collapsed to at most 2.
        self.assertNotIn("\n\n\n", result)
        self.assertIn("结论：合同有效。", result)

    def test_strips_leading_trailing_whitespace(self):
        text = "  \n作为一个AI助手，结论。\n  "
        result = de_ai_polish(text)
        self.assertTrue(result.startswith("结论"))
        self.assertTrue(result.endswith("。"))

    def test_multiple_patterns_removed_in_one_pass(self):
        text = (
            "作为一个AI助手，根据我的理解，"
            "依据《民法典》第五百八十五条。"
            "以上分析仅供参考，不构成法律建议。"
        )
        result = de_ai_polish(text)
        self.assertNotIn("作为一个AI助手", result)
        self.assertNotIn("根据我的理解", result)
        self.assertNotIn("以上分析仅供参考", result)
        self.assertIn("依据《民法典》第五百八十五条。", result)


if __name__ == "__main__":
    unittest.main()
