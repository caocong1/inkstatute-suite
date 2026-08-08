"""Golden fixture tests for prompt_assembler — ports all 10 Rust test cases
from ``router.rs:507-627``.

Each test replicates the exact Rust test inputs and expected assertions.
These are golden fixture comparison tests: the Python implementation MUST
produce equivalent results to the Rust source.

HG-1 (法律质量) is NOT auto-closable — these tests verify structural
port completeness, not prompt legal quality.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.prompt_assembler import (
    AgentMode,
    RESEARCH_GATE_FALLBACK,
    RETRIEVAL_TOOL_MAP,
    SkillMetadata,
    build_retrieval_tool_mapping,
    build_skill_descriptions,
    build_system_prompt,
    is_public_web_tool_text,
    is_retrieval_tool,
    is_retrieval_tool_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(
    name: str = "test-skill",
    *,
    plugin_name: str = "test-plugin",
    description: str = "A test skill for legal research.",
    full_content: str = "## Test Skill\n\nThis is the skill body.\n",
) -> SkillMetadata:
    """Build a minimal SkillMetadata fixture."""
    return SkillMetadata(
        name=name,
        plugin_name=plugin_name,
        description=description,
        full_content=full_content,
    )


# ---------------------------------------------------------------------------
# Golden fixture tests — 1:1 port of router.rs:507-627
# ---------------------------------------------------------------------------


class TestEvidencePrompt(unittest.TestCase):
    """Rust test: evidence_prompt_mandates_clarify_research_and_review_markers"""

    def test_evidence_prompt_mandates_clarify_research_and_review_markers(self):
        prompt = build_system_prompt([], None, None, AgentMode.EVIDENCE, [])
        self.assertIn("Clarify（首轮强制）", prompt)
        self.assertIn("ask_user", prompt)
        self.assertIn("Research（法律检索）", prompt)
        self.assertIn("[待律师复核]", prompt)
        self.assertIn(
            "research-gate",
            prompt,
            "evidence mode must include the research gate",
        )


class TestDraftPrompt(unittest.TestCase):
    """Rust test: draft_prompt_mandates_first_turn_clarification_and_gate"""

    def test_draft_prompt_mandates_first_turn_clarification_and_gate(self):
        prompt = build_system_prompt([], None, None, AgentMode.DRAFT, [])
        self.assertIn("必须调用一次 ask_user", prompt)
        self.assertIn("research-gate", prompt)
        self.assertIn("引用书写规范", prompt)


class TestQAPrompt(unittest.TestCase):
    """Rust test: qa_prompt_keeps_gate_but_drops_drafting_mandates"""

    def test_qa_prompt_keeps_gate_but_drops_drafting_mandates(self):
        prompt = build_system_prompt([], None, None, AgentMode.CHAT, [])
        # Research discipline still applies to Q&A citations.
        self.assertIn("research-gate", prompt)
        self.assertIn("引用书写规范", prompt)
        self.assertIn("法律问答", prompt)
        # But none of the drafting-only mandates leak into Q&A.
        self.assertNotIn("文书输出格式（起草时强制）", prompt)
        self.assertNotIn("必须输出一个 JSON 对象", prompt)
        self.assertNotIn("必须调用一次 ask_user", prompt)


class TestToolMappingListsOnlyAvailableTools(unittest.TestCase):
    """Rust test: tool_mapping_lists_only_available_tools"""

    def test_tool_mapping_lists_only_available_tools(self):
        tools = ["search_law", "mcp__law-database__search_laws"]
        mapping = build_retrieval_tool_mapping(tools)
        self.assertIn("`search_law`", mapping)
        self.assertIn("`mcp__law-database__search_laws`", mapping)
        self.assertNotIn("`mcp__wenshu__search_cases`", mapping)
        self.assertIn("清单之外的检索工具不存在", mapping)

    def test_tool_mapping_appears_in_evidence_prompt(self):
        """Rust test: tool_mapping_appears_in_evidence_prompt (router.rs:556-559)"""
        tools = ["mcp__law-database__search_laws"]
        prompt = build_system_prompt([], None, None, AgentMode.EVIDENCE, tools)
        self.assertIn("`mcp__law-database__search_laws`", prompt)


class TestEmptyToolListDegradesHonestly(unittest.TestCase):
    """Rust test: empty_tool_list_degrades_honestly"""

    def test_empty_tool_list_degrades_honestly(self):
        mapping = build_retrieval_tool_mapping([])
        self.assertIn("未接入任何法律检索工具", mapping)
        self.assertIn("[待律师复核]", mapping)


class TestPublicWebToolsAreRetrievalTools(unittest.TestCase):
    """Rust test: public_web_tools_are_retrieval_tools (router.rs:594-612)"""

    def test_fetch_url_with_chinese_desc_is_retrieval_tool(self):
        self.assertTrue(
            is_retrieval_tool("fetch_url", "读取用户本轮明确提供的网页链接")
        )

    def test_mcp_browser_fetch_with_english_desc_is_retrieval_tool(self):
        self.assertTrue(
            is_retrieval_tool(
                "mcp__browser__fetch",
                "Fetch a public URL and return readable content",
            )
        )

    def test_mcp_web_search_is_retrieval_tool(self):
        self.assertTrue(
            is_retrieval_tool(
                "mcp__web-search__search",
                "Search the public web for current information",
            )
        )

    def test_mcp_settings_update_config_is_not_retrieval_tool(self):
        self.assertFalse(
            is_retrieval_tool("mcp__settings__update_config", "Update local settings")
        )


class TestRetrievalToolNameDetection(unittest.TestCase):
    """Rust test: retrieval_tool_name_detection (router.rs:614-626)"""

    def test_legal_search_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("legal_search"))

    def test_search_law_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("search_law"))

    def test_get_law_article_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("get_law_article"))

    def test_fetch_url_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("fetch_url"))

    def test_search_workspace_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("search_workspace"))

    def test_mcp_law_database_search_laws_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("mcp__law-database__search_laws"))

    def test_mcp_wenshu_get_case_detail_is_retrieval_tool_name(self):
        self.assertTrue(is_retrieval_tool_name("mcp__wenshu__get_case_detail"))

    def test_generate_docx_is_not_retrieval_tool_name(self):
        self.assertFalse(is_retrieval_tool_name("generate_docx"))

    def test_ask_user_is_not_retrieval_tool_name(self):
        self.assertFalse(is_retrieval_tool_name("ask_user"))

    def test_mcp_gsxt_query_company_is_not_retrieval_tool_name(self):
        self.assertFalse(is_retrieval_tool_name("mcp__gsxt__query_company"))


# ---------------------------------------------------------------------------
# Additional tests — skill descriptions, active skill, custom research-gate
# (from plan 102-02 behavior spec)
# ---------------------------------------------------------------------------


class TestBuildSkillDescriptions(unittest.TestCase):
    """build_skill_descriptions skips research-gate and lists other skills."""

    def test_skips_research_gate_and_lists_others(self):
        skills = [
            _make_skill("research-gate", description="Research gate skill"),
            _make_skill("contract-drafting", description="Contract drafting skill"),
            _make_skill("evidence-analysis", description="Evidence analysis skill"),
        ]
        desc = build_skill_descriptions(skills)
        self.assertIn("## 可用法律技能", desc)
        self.assertIn("**contract-drafting**", desc)
        self.assertIn("**evidence-analysis**", desc)
        self.assertNotIn("research-gate", desc)

    def test_empty_skills_produces_header_only(self):
        desc = build_skill_descriptions([])
        self.assertIn("## 可用法律技能", desc)
        # No skill lines (only the header + intro text)
        self.assertNotIn("- **", desc)


class TestActiveSkillInjection(unittest.TestCase):
    """Active skill body is injected when provided."""

    def test_active_skill_body_is_injected(self):
        skill = _make_skill(
            "contract-drafting",
            full_content="## Contract Drafting\n\nDraft contracts with precision.\n",
        )
        prompt = build_system_prompt(
            [], None, skill, AgentMode.DRAFT, []
        )
        self.assertIn("当前激活技能", prompt)
        self.assertIn("contract-drafting", prompt)
        self.assertIn("Draft contracts with precision.", prompt)

    def test_no_active_skill_means_no_injection(self):
        prompt = build_system_prompt([], None, None, AgentMode.CHAT, [])
        self.assertNotIn("当前激活技能", prompt)


class TestCustomResearchGateContent(unittest.TestCase):
    """Custom research_gate_content replaces fallback when provided."""

    def test_custom_content_replaces_fallback(self):
        custom_gate = "## research-gate（自定义版本）\n\n这是自定义的 research-gate 内容。\n"
        prompt = build_system_prompt(
            [], custom_gate, None, AgentMode.DRAFT, []
        )
        self.assertIn("自定义版本", prompt)
        self.assertIn("这是自定义的 research-gate 内容", prompt)

    def test_fallback_used_when_none(self):
        prompt = build_system_prompt([], None, None, AgentMode.DRAFT, [])
        self.assertIn(RESEARCH_GATE_FALLBACK, prompt)


class TestRetrievalToolMapStructure(unittest.TestCase):
    """Verify the RETRIEVAL_TOOL_MAP has exactly 10 entries."""

    def test_has_ten_entries(self):
        self.assertEqual(len(RETRIEVAL_TOOL_MAP), 10)

    def test_all_entries_are_tuples(self):
        for entry in RETRIEVAL_TOOL_MAP:
            self.assertIsInstance(entry, tuple)
            self.assertEqual(len(entry), 2)
            self.assertIsInstance(entry[0], str)
            self.assertIsInstance(entry[1], str)


class TestUnknownToolGenericDescription(unittest.TestCase):
    """Unknown retrieval tools get a generic description based on name."""

    def test_unknown_web_tool_gets_web_description(self):
        tools = ["mcp__custom-web-search"]
        mapping = build_retrieval_tool_mapping(tools)
        self.assertIn("公开网页资料检索/抓取", mapping)

    def test_unknown_non_web_tool_gets_legal_description(self):
        tools = ["mcp__custom-legal-db"]
        mapping = build_retrieval_tool_mapping(tools)
        self.assertIn("外部法律数据源检索", mapping)


class TestIsPublicWebToolText(unittest.TestCase):
    """is_public_web_tool_text detects web/search/fetch fragments."""

    def test_english_fragments(self):
        self.assertTrue(is_public_web_tool_text("web search"))
        self.assertTrue(is_public_web_tool_text("fetch URL"))
        self.assertTrue(is_public_web_tool_text("Browser crawl"))

    def test_chinese_fragments(self):
        self.assertTrue(is_public_web_tool_text("网页搜索"))
        self.assertTrue(is_public_web_tool_text("抓取链接"))

    def test_no_match(self):
        self.assertFalse(is_public_web_tool_text("update config"))


if __name__ == "__main__":
    unittest.main()
