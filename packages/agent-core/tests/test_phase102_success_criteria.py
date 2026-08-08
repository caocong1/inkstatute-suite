"""Phase 102 success criteria verification — maps each criterion to verifying tests.

This meta-test documents the mapping between Phase 102's 6 success criteria
(from ROADMAP.md) and the tests that verify them. It does not re-run the
full test suite (that is done by the gate runner), but it provides a single
place to audit coverage and verifies key assertions inline.

Success Criteria (from ROADMAP.md):
1. ``skills/router.rs`` prompt assembly ported: three-mode base prompts,
   research-gate injection, retrieval tool mapping, citation writing spec,
   skill descriptions, active skill body injection.
2. ``llm/tool_leak.rs`` leak detection + parsing ported with golden fixtures:
   DSML/XML variant detection, fullwidth char normalization, leak retry;
   Rust-side test cases used as Python-side golden fixture set.
3. Citation audit ported: citation extraction, verification against local
   law library and retrieval evidence, verified/retrieved/unverified labels,
   ``citation.recorded`` event output.
4. Four legal guardrails code-level enforced with tests: research-gate
   (search before concluding), ask-user-enforcement (block drafting when
   key facts missing), citation audit, de-AI polish.
5. High-risk legal safety maintained: no auto-synthesize skill, no auto-modify
   legal conclusion skills, ``skill_candidate.requires_human_review`` always
   True, with test assertions.
6. Golden fixture comparison set established — same input produces comparable
   output across ported modules, differences explicitly explained.

HG-1 (法律质量) is NOT auto-closable — these tests verify structural
guardrail presence and code-level enforcement, not prompt legal quality.
"""

from __future__ import annotations

import os
import unittest

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.citations.extract import (
    CitationKind,
    extract_citations,
)
from inkstatute_agent_core.citations.verify import CitationAuditItem
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.guardrails import (
    GuardrailResult,
    SkillCandidate,
    create_skill_candidate,
    de_ai_polish,
    enforce_ask_user_mandate,
    enforce_citation_audit,
    enforce_research_gate,
    verify_guardrails,
)
from inkstatute_agent_core.prompt_assembler import (
    AgentMode,
    SkillMetadata,
    build_system_prompt,
)
from inkstatute_agent_core.tool_leak import (
    contains_tool_leakage,
    parse_embedded_tool_calls,
    sanitize_assistant_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TESTS_DIR = os.path.dirname(__file__)


def _file_exists(filename: str) -> bool:
    return os.path.isfile(os.path.join(TESTS_DIR, filename))


# ---------------------------------------------------------------------------
# SC-1: router.rs prompt assembly ported
# ---------------------------------------------------------------------------


class TestSC1PromptAssemblyPorted(unittest.TestCase):
    """SC-1: router.rs prompt assembly ported with all required sections."""

    def test_build_system_prompt_exists_and_works(self) -> None:
        """build_system_prompt() exists and produces a non-empty prompt."""
        prompt = build_system_prompt(
            skills=[], research_gate_content=None, active_skill=None,
            mode=AgentMode.CHAT, retrieval_tools=[],
        )
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)

    def test_three_mode_prompts(self) -> None:
        """All three modes (Chat, Draft, Evidence) produce distinct prompts."""
        chat = build_system_prompt([], None, None, AgentMode.CHAT, [])
        draft = build_system_prompt([], None, None, AgentMode.DRAFT, [])
        evidence = build_system_prompt([], None, None, AgentMode.EVIDENCE, [])
        self.assertIn("法律问答", chat)
        self.assertIn("起草", draft)
        self.assertIn("Evidence", evidence)
        self.assertNotEqual(chat, draft)
        self.assertNotEqual(chat, evidence)

    def test_research_gate_injected_in_all_modes(self) -> None:
        """research-gate section is present in all three modes."""
        for mode in AgentMode:
            prompt = build_system_prompt([], None, None, mode, [])
            self.assertIn("research-gate", prompt, f"research-gate missing in {mode.value}")

    def test_retrieval_tool_mapping(self) -> None:
        """Retrieval tool mapping is included when tools are available."""
        prompt = build_system_prompt(
            [], None, None, AgentMode.CHAT, ["legal_search"],
        )
        self.assertIn("检索工具映射", prompt)
        self.assertIn("legal_search", prompt)

    def test_citation_writing_spec(self) -> None:
        """Citation writing spec (引用书写规范) is included in all modes."""
        for mode in AgentMode:
            prompt = build_system_prompt([], None, None, mode, [])
            self.assertIn("引用书写规范", prompt, f"citation spec missing in {mode.value}")

    def test_skill_descriptions_and_active_skill(self) -> None:
        """Skill descriptions and active skill body are injected."""
        skill = SkillMetadata(
            name="contract-review", plugin_name="legal-skills",
            description="合同审查", full_content="审查步骤",
        )
        prompt = build_system_prompt(
            [skill], None, skill, AgentMode.CHAT, [],
        )
        self.assertIn("可用法律技能", prompt)
        self.assertIn("contract-review", prompt)
        self.assertIn("当前激活技能", prompt)
        self.assertIn("审查步骤", prompt)

    def test_verifying_test_file_exists(self) -> None:
        """test_prompt_assembler.py exists (the dedicated test file)."""
        self.assertTrue(_file_exists("test_prompt_assembler.py"))


# ---------------------------------------------------------------------------
# SC-2: tool_leak.rs ported with golden fixtures
# ---------------------------------------------------------------------------


class TestSC2ToolLeakPortedWithGoldenFixtures(unittest.TestCase):
    """SC-2: tool_leak.rs detection + sanitization + parsing ported."""

    def test_contains_tool_leakage_detects_dsml(self) -> None:
        """contains_tool_leakage() detects DSML-style leakage."""
        self.assertTrue(contains_tool_leakage("<tool_calls>"))
        self.assertTrue(contains_tool_leakage("<invoke name=\"search\">"))
        self.assertTrue(contains_tool_leakage("dsml"))

    def test_contains_tool_leakage_clean_text(self) -> None:
        """Clean text is not flagged as leaked."""
        self.assertFalse(contains_tool_leakage("根据《民法典》第五百八十五条，违约金可以约定。"))

    def test_sanitize_strips_leak_markup(self) -> None:
        """sanitize_assistant_content() strips tool-call markup."""
        leaked = "<tool_calls><invoke name=\"search\"></invoke></tool_calls>"
        self.assertEqual(sanitize_assistant_content(leaked), "")

    def test_parse_embedded_tool_calls(self) -> None:
        """parse_embedded_tool_calls() extracts structured tool calls."""
        content = '<invoke name="search_workspace"><parameter name="query">合同法</parameter></invoke>'
        calls = parse_embedded_tool_calls(content)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "search_workspace")

    def test_verifying_test_file_exists(self) -> None:
        """test_tool_leak.py exists (the dedicated golden fixture test file)."""
        self.assertTrue(_file_exists("test_tool_leak.py"))


# ---------------------------------------------------------------------------
# SC-3: citation audit ported
# ---------------------------------------------------------------------------


class TestSC3CitationAuditPorted(unittest.TestCase):
    """SC-3: citation audit extraction + verification + citation.recorded event."""

    def test_extract_citations_works(self) -> None:
        """extract_citations() extracts law article citations."""
        citations = extract_citations("《中华人民共和国民法典》第五百八十五条")
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].kind, CitationKind.LAW)
        self.assertEqual(citations[0].source, "中华人民共和国民法典")

    def test_audit_async_works(self) -> None:
        """enforce_citation_audit() (async) produces a CitationAudit result."""
        import asyncio
        result = asyncio.run(enforce_citation_audit(
            "《民法典》第五百八十五条", None, None,
        ))
        self.assertGreater(result.total, 0)
        self.assertEqual(result.unverified, result.total)  # no library/retrievals

    def test_emit_citation_recorded_works(self) -> None:
        """emit_citation_recorded() produces a citation.recorded event."""
        emitter = EventEmitter("run-test", AgentCoreConfig())
        item = CitationAuditItem(
            kind=CitationKind.LAW,
            source="中华人民共和国民法典",
            reference="第五百八十五条",
            status="unverified",
        )
        event = emitter.emit_citation_recorded([item])
        self.assertEqual(event.event_type, "citation.recorded")
        citations = event.payload["citations"]
        self.assertEqual(len(citations), 1)
        self.assertIn("民法典", citations[0]["source"])
        self.assertEqual(citations[0]["status"], "unverified")

    def test_verifying_test_files_exist(self) -> None:
        """Dedicated citation test files exist."""
        self.assertTrue(_file_exists("test_citation_extract.py"))
        self.assertTrue(_file_exists("test_citation_verify.py"))
        self.assertTrue(_file_exists("test_citation_event.py"))


# ---------------------------------------------------------------------------
# SC-4: four guardrails code-level enforced
# ---------------------------------------------------------------------------


class TestSC4FourGuardrailsEnforced(unittest.TestCase):
    """SC-4: four legal guardrails enforced at code level with tests."""

    def test_research_gate_enforcement(self) -> None:
        """enforce_research_gate() raises when the gate section is missing."""
        with self.assertRaises(ValueError):
            enforce_research_gate("这是一个普通的法律 prompt，没有任何护栏内容")

        # Should not raise when the gate section is present
        enforce_research_gate("## research-gate\n内容")

    def test_ask_user_enforcement(self) -> None:
        """enforce_ask_user_mandate() raises for Draft/Evidence without the mandate."""
        with self.assertRaises(ValueError):
            enforce_ask_user_mandate("这是一个起草模式 prompt，缺少澄清指令", AgentMode.DRAFT)
        with self.assertRaises(ValueError):
            enforce_ask_user_mandate("这是一个证据模式 prompt，缺少澄清指令", AgentMode.EVIDENCE)
        # Chat mode is exempt
        enforce_ask_user_mandate("这是一个问答模式 prompt，缺少澄清指令", AgentMode.CHAT)
        # With the mandate present, no raise
        enforce_ask_user_mandate("包含 ask_user 指令的 draft prompt", AgentMode.DRAFT)

    def test_citation_audit_enforcement(self) -> None:
        """enforce_citation_audit() is callable and returns a result."""
        import asyncio
        result = asyncio.run(enforce_citation_audit("test text", None, None))
        self.assertIsNotNone(result)
        # Even with no citations, the audit runs (total=0)
        self.assertEqual(result.total, 0)

    def test_de_ai_polish_enforcement(self) -> None:
        """de_ai_polish() removes AI disclaimers while preserving legal content."""
        text = "作为一个AI助手，根据《民法典》第五百八十五条，违约金可以约定。"
        polished = de_ai_polish(text)
        self.assertNotIn("作为一个AI助手", polished)
        self.assertIn("民法典", polished)

    def test_verify_guardrails_passes_for_valid_prompt(self) -> None:
        """verify_guardrails() passes for a prompt with all guardrails."""
        prompt = build_system_prompt(
            [], None, None, AgentMode.DRAFT, [],
        )
        result = verify_guardrails(prompt, AgentMode.DRAFT)
        self.assertIsInstance(result, GuardrailResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.missing_guardrails, [])

    def test_verify_guardrails_fails_for_missing_research_gate(self) -> None:
        """verify_guardrails() fails when the gate section is missing."""
        result = verify_guardrails("一个没有任何护栏内容的普通 prompt", AgentMode.CHAT)
        self.assertFalse(result.passed)
        self.assertIn("research-gate", result.missing_guardrails)

    def test_verifying_test_files_exist(self) -> None:
        """Dedicated guardrail test files exist."""
        self.assertTrue(_file_exists("test_guardrails.py"))
        self.assertTrue(_file_exists("test_de_ai_polish.py"))


# ---------------------------------------------------------------------------
# SC-5: skill_candidate.requires_human_review safety
# ---------------------------------------------------------------------------


class TestSC5SkillCandidateSafety(unittest.TestCase):
    """SC-5: skill_candidate.requires_human_review always True (SAFE-01)."""

    def test_create_skill_candidate_always_true(self) -> None:
        """create_skill_candidate() always sets requires_human_review=True."""
        candidate = create_skill_candidate("test", "description")
        self.assertTrue(candidate.requires_human_review)

    def test_create_skill_candidate_cannot_override_false(self) -> None:
        """Attempting to set requires_human_review=False raises ValueError."""
        with self.assertRaises(ValueError):
            create_skill_candidate("test", "desc", requires_human_review=False)

    def test_skill_candidate_dataclass_default_true(self) -> None:
        """SkillCandidate dataclass defaults requires_human_review to True."""
        candidate = SkillCandidate(name="test", description="desc")
        self.assertTrue(candidate.requires_human_review)

    def test_verifying_test_file_exists(self) -> None:
        """test_skill_candidate_safety.py exists."""
        self.assertTrue(_file_exists("test_skill_candidate_safety.py"))


# ---------------------------------------------------------------------------
# SC-6: golden fixture comparison set
# ---------------------------------------------------------------------------


class TestSC6GoldenFixtureComparisonSet(unittest.TestCase):
    """SC-6: golden fixture comparison set exists and passes."""

    def test_golden_fixture_replay_test_file_exists(self) -> None:
        """test_golden_fixture_replay.py exists (the golden fixture comparison set)."""
        self.assertTrue(_file_exists("test_golden_fixture_replay.py"))

    def test_e2e_guardrail_pipeline_test_file_exists(self) -> None:
        """test_e2e_guardrail_pipeline.py exists (integration tests)."""
        self.assertTrue(_file_exists("test_e2e_guardrail_pipeline.py"))

    def test_cross_module_determinism(self) -> None:
        """Same inputs produce same outputs across all ported modules (determinism)."""
        # tool_leak determinism
        leak_input = "<tool_calls><invoke name=\"search\"></invoke></tool_calls>"
        leak_results = [contains_tool_leakage(leak_input) for _ in range(3)]
        self.assertTrue(all(r == leak_results[0] for r in leak_results))

        # prompt_assembler determinism
        prompts = [
            build_system_prompt([], None, None, AgentMode.CHAT, [])
            for _ in range(3)
        ]
        self.assertTrue(all(p == prompts[0] for p in prompts))

        # citations/extract determinism
        cite_input = "《民法典》第五百八十五条"
        cite_results = [extract_citations(cite_input) for _ in range(3)]
        for r in cite_results:
            self.assertEqual(len(r), len(cite_results[0]))
            for i, c in enumerate(r):
                self.assertEqual(c.source, cite_results[0][i].source)
                self.assertEqual(c.reference, cite_results[0][i].reference)

    def test_config_max_leak_retries_default(self) -> None:
        """config.py has max_leak_retries field with default 3 (Rust MAX_LEAK_RETRIES)."""
        config = AgentCoreConfig()
        self.assertEqual(config.max_leak_retries, 3)

    def test_config_max_leak_retries_validation(self) -> None:
        """max_leak_retries rejects negative values."""
        with self.assertRaises(ValueError):
            AgentCoreConfig(max_leak_retries=-1)


# ---------------------------------------------------------------------------
# HG-1 reminder — NOT auto-closable
# ---------------------------------------------------------------------------


class TestHG1NotAutoClosable(unittest.TestCase):
    """HG-1 (法律质量) is NOT auto-closable — these tests do NOT claim it passes."""

    def test_hg1_remains_open(self) -> None:
        """HG-1 requires lawyer sampling — not claimed as passed by any test.

        This test exists to explicitly document that HG-1 remains open.
        The code-level guardrail tests verify structural enforcement, not
        prompt legal quality. A lawyer must sample and confirm output
        quality before HG-1 can be closed.
        """
        # This test always passes — it is a documentation anchor.
        # HG-1 is NOT closed by any automated test.
        self.assertTrue(True, "HG-1 remains open — requires lawyer sampling")


if __name__ == "__main__":
    unittest.main()
