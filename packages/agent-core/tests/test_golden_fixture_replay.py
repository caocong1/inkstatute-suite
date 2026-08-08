"""Golden fixture replay tests — same-input same-output across all ported modules.

This test file is the cross-module golden fixture comparison set (SC-6).
It verifies that the ported Python modules produce deterministic, correct
outputs for fixed inputs derived from the Rust source test cases.

Modules verified:
- **tool_leak** (102-01): ``contains_tool_leakage()``, ``sanitize_assistant_content()``,
  ``parse_embedded_tool_calls()`` — using ``REAL_DSML_LEAK`` from ``tool_leak.rs:295``.
- **prompt_assembler** (102-02): ``build_system_prompt()`` — three modes,
  research-gate, citation spec, skill descriptions.
- **citations/extract** (102-03): ``extract_citations()`` — law article extraction.
- **Full pipeline** — prompt assembly → model response → leak detection →
  citation audit → de-AI polish produces deterministic output for fixed input.

Per AGENTS.md: "When porting logic from lawyer-desktop (Rust), use the
Rust-side test cases as the Python-side golden fixture set."
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.citations.extract import (
    CitationKind,
    extract_citations,
)
from inkstatute_agent_core.guardrails import de_ai_polish
from inkstatute_agent_core.prompt_assembler import (
    AgentMode,
    SkillMetadata,
    build_system_prompt,
)
from inkstatute_agent_core.tool_leak import (
    contains_tool_leakage,
    normalize_marker_chars,
    parse_embedded_tool_calls,
    sanitize_assistant_content,
)


# ---------------------------------------------------------------------------
# Golden fixture constants — verbatim from Rust source
# ---------------------------------------------------------------------------

# REAL_DSML_LEAK — verbatim from tool_leak.rs:295
# Uses fullwidth ｜ U+FF5C. Captured from a real failed conversation.
REAL_DSML_LEAK: str = (
    "<｜｜DSML｜｜tool_c>\n"
    '<｜｜DSML｜｜invoke="search_">\n'
    '<｜｜DSML｜｜parameter namek" stringfalse">13｜｜DSML｜｜parameter>\n'
    '<｜｜DSML｜｜ name="query" stringtrue">保 投标见即付不可</｜｜DSML｜｜parameter>\n'
    "</invoke>\n"
    "</｜｜DSML｜｜_calls>"
)

# Golden law citation text — from router.rs citation writing spec
LAW_CITATION_TEXT = "《中华人民共和国民法典》第五百八十五条"


# ---------------------------------------------------------------------------
# tool_leak golden fixtures (102-01)
# ---------------------------------------------------------------------------


class TestToolLeakGoldenFixtures(unittest.TestCase):
    """Golden fixture replay for tool_leak module (ported from tool_leak.rs)."""

    def test_real_dsml_leak_detected(self) -> None:
        """REAL_DSML_LEAK is detected as leaked content."""
        self.assertTrue(contains_tool_leakage(REAL_DSML_LEAK))

    def test_real_dsml_leak_sanitized_to_empty(self) -> None:
        """REAL_DSML_LEAK sanitizes to empty string (all lines are leak markers)."""
        result = sanitize_assistant_content(REAL_DSML_LEAK)
        self.assertEqual(result, "")

    def test_real_dsml_leak_parses_one_tool_call(self) -> None:
        """REAL_DSML_LEAK parses to exactly 1 embedded tool call (search_workspace)."""
        calls = parse_embedded_tool_calls(REAL_DSML_LEAK)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["type"], "function")
        self.assertEqual(calls[0]["function"]["name"], "search_workspace")

    def test_clean_text_not_detected(self) -> None:
        """Clean legal text is not flagged as leaked."""
        clean = "根据《民法典》第五百八十五条，违约金可以约定。"
        self.assertFalse(contains_tool_leakage(clean))

    def test_normalize_marker_chars_fullwidth_pipe(self) -> None:
        """Fullwidth ｜ U+FF5C is normalized to ASCII |."""
        self.assertEqual(normalize_marker_chars("｜"), "|")

    def test_normalize_marker_chars_lower_block(self) -> None:
        """Lower one eighth block ▁ U+2581 is normalized to ASCII _."""
        self.assertEqual(normalize_marker_chars("▁"), "_")

    def test_deterministic_repeated_calls(self) -> None:
        """Same input produces same output across repeated calls (determinism)."""
        results1 = [contains_tool_leakage(REAL_DSML_LEAK) for _ in range(5)]
        results2 = [sanitize_assistant_content(REAL_DSML_LEAK) for _ in range(5)]
        results3 = [parse_embedded_tool_calls(REAL_DSML_LEAK) for _ in range(5)]
        self.assertTrue(all(r == results1[0] for r in results1))
        self.assertTrue(all(r == results2[0] for r in results2))
        # parse results have UUIDs so compare count + names
        self.assertTrue(all(len(r) == 1 and r[0]["function"]["name"] == "search_workspace"
                            for r in results3))


# ---------------------------------------------------------------------------
# prompt_assembler golden fixtures (102-02)
# ---------------------------------------------------------------------------


class TestPromptAssemblerGoldenFixtures(unittest.TestCase):
    """Golden fixture replay for prompt_assembler module (ported from router.rs)."""

    def test_chat_mode_prompt_contains_required_sections(self) -> None:
        """Chat mode prompt contains research-gate, citation spec, and Q&A mode."""
        prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.CHAT,
            retrieval_tools=[],
        )
        self.assertIn("research-gate", prompt)
        self.assertIn("引用书写规范", prompt)
        self.assertIn("法律问答", prompt)
        self.assertIn("可用法律技能", prompt)

    def test_draft_mode_prompt_contains_required_sections(self) -> None:
        """Draft mode prompt contains research-gate, ask_user, and drafting format."""
        prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.DRAFT,
            retrieval_tools=[],
        )
        self.assertIn("research-gate", prompt)
        self.assertIn("ask_user", prompt)
        self.assertIn("引用书写规范", prompt)

    def test_evidence_mode_prompt_contains_required_sections(self) -> None:
        """Evidence mode prompt contains research-gate, ask_user, and evidence workflow."""
        prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.EVIDENCE,
            retrieval_tools=[],
        )
        self.assertIn("research-gate", prompt)
        self.assertIn("ask_user", prompt)
        self.assertIn("Evidence", prompt)

    def test_retrieval_tool_mapping_included(self) -> None:
        """Prompt includes retrieval tool mapping for available tools."""
        prompt = build_system_prompt(
            skills=[],
            research_gate_content=None,
            active_skill=None,
            mode=AgentMode.CHAT,
            retrieval_tools=["legal_search", "fetch_url"],
        )
        self.assertIn("检索工具映射", prompt)
        self.assertIn("legal_search", prompt)
        self.assertIn("fetch_url", prompt)

    def test_active_skill_body_injected(self) -> None:
        """Active skill body is injected into the prompt."""
        skill = SkillMetadata(
            name="contract-review",
            plugin_name="legal-skills",
            description="合同审查技能",
            full_content="## 合同审查步骤\n1. 检查主体资格\n2. 审查条款合法性",
        )
        prompt = build_system_prompt(
            skills=[skill],
            research_gate_content=None,
            active_skill=skill,
            mode=AgentMode.CHAT,
            retrieval_tools=[],
        )
        self.assertIn("当前激活技能: contract-review", prompt)
        self.assertIn("合同审查步骤", prompt)

    def test_deterministic_prompt_assembly(self) -> None:
        """Same inputs produce same prompt across repeated calls (determinism)."""
        skill = SkillMetadata(
            name="test-skill",
            plugin_name="test-plugin",
            description="测试技能",
            full_content="测试内容",
        )
        prompts = [
            build_system_prompt(
                skills=[skill],
                research_gate_content=None,
                active_skill=skill,
                mode=AgentMode.CHAT,
                retrieval_tools=["legal_search"],
            )
            for _ in range(3)
        ]
        self.assertTrue(all(p == prompts[0] for p in prompts))


# ---------------------------------------------------------------------------
# citations/extract golden fixtures (102-03)
# ---------------------------------------------------------------------------


class TestCitationExtractGoldenFixtures(unittest.TestCase):
    """Golden fixture replay for citations/extract module (ported from extract.rs)."""

    def test_law_article_extraction(self) -> None:
        """《中华人民共和国民法典》第五百八十五条 extracts to 1 law citation."""
        citations = extract_citations(LAW_CITATION_TEXT)
        self.assertEqual(len(citations), 1)
        c = citations[0]
        self.assertEqual(c.kind, CitationKind.LAW)
        self.assertEqual(c.source, "中华人民共和国民法典")
        self.assertEqual(c.reference, "第五百八十五条")

    def test_multiple_law_articles_extraction(self) -> None:
        """Multiple law articles in one law reference are extracted individually."""
        text = "《民法典》第五百八十五条和第五百八十六条"
        citations = extract_citations(text)
        # Should extract at least 2 articles (第五百八十五条, 第五百八十六条)
        refs = [c.reference for c in citations if c.kind == CitationKind.LAW]
        self.assertIn("第五百八十五条", refs)
        self.assertIn("第五百八十六条", refs)

    def test_case_number_extraction(self) -> None:
        """Full court case number is extracted as a case citation."""
        text = "参见（2024）渝01民初1234号判决书"
        citations = extract_citations(text)
        case_cits = [c for c in citations if c.kind == CitationKind.CASE]
        self.assertGreaterEqual(len(case_cits), 1)
        self.assertIn("1234", case_cits[0].reference)

    def test_deterministic_extraction(self) -> None:
        """Same input produces same output across repeated calls (determinism)."""
        results = [extract_citations(LAW_CITATION_TEXT) for _ in range(3)]
        for r in results:
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0].source, results[0][0].source)
            self.assertEqual(r[0].reference, results[0][0].reference)
            self.assertEqual(r[0].kind, results[0][0].kind)

    def test_empty_text_no_citations(self) -> None:
        """Empty or plain text produces no citations."""
        self.assertEqual(extract_citations(""), [])
        self.assertEqual(extract_citations("你好，请问有什么可以帮助？"), [])


# ---------------------------------------------------------------------------
# Full pipeline golden fixture — deterministic end-to-end
# ---------------------------------------------------------------------------


class TestFullPipelineGoldenFixture(unittest.TestCase):
    """Golden fixture replay for the full guardrail pipeline.

    Verifies that the pipeline (leak detection → citation audit → de-AI polish)
    produces deterministic output for a fixed input.
    """

    def test_pipeline_deterministic_output(self) -> None:
        """Same input through the pipeline produces same output every time."""
        input_text = (
            "作为一个AI助手，根据《中华人民共和国民法典》第五百八十五条，"
            "违约金可以约定。以上分析仅供参考。"
        )

        results = []
        for _ in range(3):
            # Step 1: Leak detection (no leak in this input)
            is_leaked = contains_tool_leakage(input_text)
            self.assertFalse(is_leaked)

            # Step 2: Citation extraction
            citations = extract_citations(input_text)
            self.assertEqual(len(citations), 1)
            self.assertEqual(citations[0].source, "中华人民共和国民法典")

            # Step 3: De-AI polish
            polished = de_ai_polish(input_text)

            results.append({
                "leaked": is_leaked,
                "citation_count": len(citations),
                "citation_source": citations[0].source,
                "polished": polished,
            })

        # All runs produce identical results
        self.assertTrue(all(r["polished"] == results[0]["polished"] for r in results))
        self.assertTrue(all(r["citation_count"] == 1 for r in results))
        self.assertTrue(all(not r["leaked"] for r in results))

    def test_pipeline_polish_removes_ai_disclaimer_preserves_citation(self) -> None:
        """De-AI polish removes AI disclaimer but preserves legal citation."""
        input_text = "作为一个AI助手，根据《民法典》第五百八十五条，违约金可以约定。"
        polished = de_ai_polish(input_text)
        self.assertNotIn("作为一个AI助手", polished)
        self.assertIn("民法典", polished)
        self.assertIn("第五百八十五条", polished)
        self.assertIn("违约金", polished)

    def test_pipeline_leaked_input_sanitized_then_citation_extracted(self) -> None:
        """Leaked input is sanitized, then citations extracted from clean text."""
        # Simulate the pipeline: sanitize leaked content, then extract citations
        sanitized = sanitize_assistant_content(REAL_DSML_LEAK)
        self.assertEqual(sanitized, "")  # All leak markers removed

        # No citations in empty sanitized content
        citations = extract_citations(sanitized)
        self.assertEqual(len(citations), 0)


if __name__ == "__main__":
    unittest.main()
