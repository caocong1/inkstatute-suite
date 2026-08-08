"""Four-guardrail code-level enforcement tests (CORE-08, SAFE-04).

These tests prove that each of the four legal guardrails is enforced at code
level — there is no code path that bypasses them:

1. **research-gate** — ``build_system_prompt()`` always includes research-gate
   text; ``enforce_research_gate()`` raises when it is missing.
2. **ask-user-enforcement** — Draft/Evidence prompts always include the
   ask-user mandate; ``enforce_ask_user_mandate()`` raises when absent.
3. **citation audit** — ``enforce_citation_audit()`` always runs and labels
   unverified citations with ``[待律师复核]``.
4. **de-AI polish** — ``de_ai_polish()`` removes AI patterns (detailed in
   ``test_de_ai_polish.py``); here we verify it runs as a post-processing
   guardrail after the citation audit.

HG-1 (法律质量) is NOT auto-closable — these tests verify structural
enforcement, not prompt legal quality.
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_agent_core.guardrails import (
    CitationAudit,
    GuardrailResult,
    apply_de_ai_polish,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(
    name: str = "test-skill",
    *,
    plugin_name: str = "test-plugin",
    description: str = "A test legal skill.",
    full_content: str = "## Test Skill\n\nBody.\n",
) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        plugin_name=plugin_name,
        description=description,
        full_content=full_content,
    )


# ---------------------------------------------------------------------------
# Guardrail 1 — research-gate enforcement (SAFE-04)
# ---------------------------------------------------------------------------


class TestEnforceResearchGate(unittest.TestCase):
    """Guardrail 1: research-gate is non-bypassable."""

    def test_passes_when_research_gate_present(self):
        prompt = "## research-gate（强制前置）\n\n检索先行。\n"
        # No exception expected.
        enforce_research_gate(prompt)

    def test_raises_when_research_gate_missing(self):
        prompt = "你是一位法律助手。请回答问题。"
        with self.assertRaises(ValueError) as ctx:
            enforce_research_gate(prompt)
        self.assertIn("research-gate", str(ctx.exception))

    def test_build_system_prompt_always_includes_research_gate(self):
        """No code path produces a legal prompt without research-gate.

        Verified across all three modes, with and without a loaded
        research-gate skill, and with empty/non-empty retrieval tools.
        """
        for mode in (AgentMode.CHAT, AgentMode.DRAFT, AgentMode.EVIDENCE):
            for gate in (None, "## research-gate（自定义）\n\n自定义内容。\n"):
                for tools in ([], ["legal_search", "fetch_url"]):
                    with self.subTest(mode=mode, gate=gate, tools=tools):
                        prompt = build_system_prompt(
                            [_make_skill()], gate, None, mode, tools
                        )
                        # The guardrail enforcement must pass — proving the
                        # assembler never bypasses it.
                        enforce_research_gate(prompt)
                        self.assertIn("research-gate", prompt)

    def test_bypass_attempt_via_empty_prompt_raises(self):
        """A hand-crafted empty prompt cannot bypass the guardrail."""
        with self.assertRaises(ValueError):
            enforce_research_gate("")


# ---------------------------------------------------------------------------
# Guardrail 2 — ask-user-enforcement (CORE-08)
# ---------------------------------------------------------------------------


class TestEnforceAskUserMandate(unittest.TestCase):
    """Guardrail 2: Draft/Evidence prompts mandate ask_user; Chat exempt."""

    def test_raises_for_draft_mode_without_ask_user(self):
        prompt = "你是一位法律助手。起草文书。"  # no ask_user
        with self.assertRaises(ValueError) as ctx:
            enforce_ask_user_mandate(prompt, AgentMode.DRAFT)
        self.assertIn("ask_user", str(ctx.exception))

    def test_raises_for_evidence_mode_without_ask_user(self):
        prompt = "证据驱动分析。"  # no ask_user
        with self.assertRaises(ValueError) as ctx:
            enforce_ask_user_mandate(prompt, AgentMode.EVIDENCE)
        self.assertIn("ask_user", str(ctx.exception))

    def test_passes_for_chat_mode_without_ask_user(self):
        """Chat (Q&A) mode does not mandate ask_user by design."""
        prompt = "法律问答模式。直接作答。"  # no ask_user
        # No exception expected.
        enforce_ask_user_mandate(prompt, AgentMode.CHAT)

    def test_passes_for_draft_mode_with_ask_user(self):
        prompt = "起草模式。必须调用 ask_user 提出问题。"
        enforce_ask_user_mandate(prompt, AgentMode.DRAFT)

    def test_passes_for_evidence_mode_with_ask_user(self):
        prompt = "证据模式。首轮强制 ask_user。"
        enforce_ask_user_mandate(prompt, AgentMode.EVIDENCE)

    def test_build_system_prompt_always_includes_ask_user_for_draft_evidence(self):
        """No code path produces a Draft/Evidence prompt without ask_user."""
        for mode in (AgentMode.DRAFT, AgentMode.EVIDENCE):
            for gate in (None, "## research-gate\n\n内容\n"):
                for tools in ([], ["legal_search"]):
                    with self.subTest(mode=mode, gate=gate, tools=tools):
                        prompt = build_system_prompt(
                            [_make_skill()], gate, None, mode, tools
                        )
                        enforce_ask_user_mandate(prompt, mode)
                        self.assertIn("ask_user", prompt)

    def test_chat_prompt_does_not_require_ask_user(self):
        """Chat prompts legitimately omit the ask_user mandate."""
        prompt = build_system_prompt([], None, None, AgentMode.CHAT, [])
        # Must not raise — Chat is exempt.
        enforce_ask_user_mandate(prompt, AgentMode.CHAT)


# ---------------------------------------------------------------------------
# Guardrail 3 — citation audit (SAFE-04, CORE-08)
# ---------------------------------------------------------------------------


class TestEnforceCitationAudit(unittest.TestCase):
    """Guardrail 3: citation audit always runs and labels unverified citations."""

    def test_audit_runs_and_returns_citation_audit(self):
        text = "依据《中华人民共和国民法典》第五百八十五条，违约方应承担责任。"
        result = asyncio.run(enforce_citation_audit(text, retrievals=[]))
        self.assertIsInstance(result, CitationAudit)

    def test_unverified_citations_are_labelled(self):
        """Citations not found in retrievals get 待律师复核 note."""
        text = "依据《中华人民共和国民法典》第五百八十五条。"
        result = asyncio.run(enforce_citation_audit(text, retrievals=[]))
        self.assertGreaterEqual(result.unverified, 1)
        unverified = [i for i in result.items if i.status == "unverified"]
        for item in unverified:
            self.assertIn("待律师复核", item.note or "")

    def test_retrieved_citations_are_not_labelled_unverified(self):
        """Citations found in retrievals are labelled retrieved, not unverified."""
        citation = "《中华人民共和国民法典》第五百八十五条"
        text = f"依据{citation}。"
        retrievals = [("法规库", citation + " 当事人可以约定违约金。")]
        result = asyncio.run(enforce_citation_audit(text, retrievals=retrievals))
        # At least one item should be retrieved (not unverified).
        statuses = {i.status for i in result.items}
        self.assertIn("retrieved", statuses)
        for item in result.items:
            if item.status == "retrieved":
                self.assertNotIn("待律师复核", item.note or "")

    def test_audit_never_blocks_output(self):
        """The audit is annotation-style — it always returns a result, never raises."""
        text = "这段文字没有任何法条引用。"
        result = asyncio.run(enforce_citation_audit(text, retrievals=[]))
        self.assertIsInstance(result, CitationAudit)
        # No citations → all counts zero.
        self.assertEqual(result.verified, 0)
        self.assertEqual(result.unverified, 0)

    def test_audit_always_executes_for_empty_text(self):
        """Even empty input must produce a CitationAudit, never raise."""
        result = asyncio.run(enforce_citation_audit("", retrievals=None))
        self.assertIsInstance(result, CitationAudit)


# ---------------------------------------------------------------------------
# Guardrail 4 — de-AI polish runs as post-processing (CORE-08)
# ---------------------------------------------------------------------------


class TestDeAiPolishGuardrail(unittest.TestCase):
    """Guardrail 4: de-AI polish runs after citation audit (post-processing)."""

    def test_de_ai_polish_runs_after_citation_audit(self):
        """The pipeline: citation audit → de-AI polish. Polish runs on the
        original final text (the audit labels items separately) and still
        removes AI patterns while preserving legal citations."""
        text = (
            "作为一个AI助手，依据《中华人民共和国民法典》第五百八十五条。"
            "以上分析仅供参考，不构成法律建议。"
        )
        audit = asyncio.run(enforce_citation_audit(text, retrievals=[]))
        # The audit ran (Guardrail 3) and labelled unverified citations.
        self.assertIsInstance(audit, CitationAudit)
        # De-AI polish (Guardrail 4) runs as post-processing on the text.
        polished = de_ai_polish(text)
        # AI patterns removed.
        self.assertNotIn("作为一个AI助手", polished)
        self.assertNotIn("以上分析仅供参考，不构成法律建议", polished)
        # Legal citation preserved.
        self.assertIn("《中华人民共和国民法典》第五百八十五条", polished)

    def test_apply_de_ai_polish_alias_works(self):
        """The public alias ``apply_de_ai_polish`` is the same function."""
        self.assertIs(apply_de_ai_polish, de_ai_polish)
        self.assertEqual(
            apply_de_ai_polish("作为一个AI助手，结论。"),
            de_ai_polish("作为一个AI助手，结论。"),
        )


# ---------------------------------------------------------------------------
# verify_guardrails — all four guardrails verification
# ---------------------------------------------------------------------------


class TestVerifyGuardrails(unittest.TestCase):
    """``verify_guardrails`` checks prompt-level guards (1 and 2)."""

    def test_passes_when_all_prompt_guards_present_for_draft(self):
        prompt = "## research-gate\n\n必须调用 ask_user。\n"
        result = verify_guardrails(prompt, AgentMode.DRAFT)
        self.assertIsInstance(result, GuardrailResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.missing_guardrails, [])

    def test_reports_missing_research_gate(self):
        prompt = "必须调用 ask_user。\n"
        result = verify_guardrails(prompt, AgentMode.DRAFT)
        self.assertFalse(result.passed)
        self.assertIn("research-gate", result.missing_guardrails)

    def test_reports_missing_ask_user_for_evidence(self):
        prompt = "## research-gate\n\n内容\n"
        result = verify_guardrails(prompt, AgentMode.EVIDENCE)
        self.assertFalse(result.passed)
        self.assertIn("ask-user-enforcement", result.missing_guardrails)

    def test_chat_mode_does_not_require_ask_user(self):
        prompt = "## research-gate\n\n法律问答。\n"
        result = verify_guardrails(prompt, AgentMode.CHAT)
        self.assertTrue(result.passed)

    def test_build_system_prompt_passes_verification_for_all_modes(self):
        """Every assembled prompt passes guardrail verification."""
        for mode in (AgentMode.CHAT, AgentMode.DRAFT, AgentMode.EVIDENCE):
            with self.subTest(mode=mode):
                prompt = build_system_prompt(
                    [_make_skill()], None, None, mode, ["legal_search"]
                )
                result = verify_guardrails(prompt, mode)
                self.assertTrue(
                    result.passed,
                    f"mode={mode} missing {result.missing_guardrails}",
                )


if __name__ == "__main__":
    unittest.main()
