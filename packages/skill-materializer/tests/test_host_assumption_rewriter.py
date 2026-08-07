"""Tests for HostAssumptionRewriter — pattern-based, deterministic, auditable."""

from __future__ import annotations

import unittest

from inkstatute_skill_materializer.host_assumption_rewriter import (
    HostAssumptionRewriter,
    RewriteEntry,
    RewriteReport,
)


# ---------------------------------------------------------------------------
# Fixture snippets with known patterns
# ---------------------------------------------------------------------------


# Rule 1: /plugin:skill trigger patterns
TRIGGER_SKILL_MD = """\
---
name: contract-review
description: Review a contract for risks.
---

# Contract Review

## Orchestration

| Step | Skill | Trigger |
|------|-------|---------|
| 1 | risk-identification | `/commercial-legal:risk-identification` |
| 2 | liability-analysis | `/commercial-legal:liability-analysis [合同]` |

Use `/commercial-legal:risk-identification` when a contract is detected.
"""

# Rule 2: ask_user / ask-user patterns
ASK_USER_SKILL_MD = """\
---
name: ask-user-enforcement
description: Global ask_user enforcement mode.
---

# Ask User Enforcement

When key facts are missing, use ask_user to collect them.
The ask-user protocol ensures clarification before drafting.
Always call ask_user before proceeding to conclusions.
"""

# Rule 3: CLAUDE.md references
CLAUDE_MD_SKILL_MD = """\
---
name: contract-review
description: Review a contract for risks.
---

# Contract Review

**在阅读合同之前，读取实践配置文件 `commercial-legal/CLAUDE.md`。**

The CLAUDE.md file contains practice-specific configuration.
"""

# Combined: all three rules in one document
COMBINED_SKILL_MD = """\
---
name: contract-review
description: Review a contract for risks.
---

# Contract Review

## Steps

1. `/commercial-legal:risk-identification` — identify risks
2. Use ask_user to clarify missing facts
3. Read `commercial-legal/CLAUDE.md` for practice config
"""

# No patterns (clean text)
CLEAN_SKILL_MD = """\
---
name: simple-skill
description: A simple skill with no host assumptions.
---

# Simple Skill

This skill has no trigger patterns, no clarification protocol references,
and no practice profile file references. It should produce zero rewrites.
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHostAssumptionRewriter(unittest.TestCase):
    """Unit tests for the host assumption rewriter."""

    def setUp(self) -> None:
        self.rewriter = HostAssumptionRewriter()

    # --- Rule 1: /plugin:skill → natural language ------------------------

    def test_rule1_trigger_to_natural_language(self) -> None:
        """Rule 1: /commercial-legal:risk-identification → natural language."""
        rewritten, report = self.rewriter.rewrite(
            TRIGGER_SKILL_MD, file_path="test/SKILL.md"
        )
        # The trigger pattern should be replaced
        self.assertNotIn("/commercial-legal:risk-identification", rewritten)
        self.assertNotIn("/commercial-legal:liability-analysis", rewritten)
        # Natural language should be present
        self.assertIn("When the user asks about risk-identification...", rewritten)
        self.assertIn("When the user asks about liability-analysis...", rewritten)

        # Check report entries
        trigger_entries = [
            e for e in report.entries
            if e.rule_applied == "trigger_to_natural_language"
        ]
        self.assertGreaterEqual(len(trigger_entries), 3)  # 3 occurrences in fixture
        for entry in trigger_entries:
            self.assertTrue(entry.original_text.startswith("/"))
            self.assertIn("When the user asks about", entry.rewritten_text)
            self.assertEqual(entry.rule_applied, "trigger_to_natural_language")
            self.assertTrue("test/SKILL.md" in entry.location)
            self.assertGreater(entry.line_number, 0)

    def test_rule1_deterministic(self) -> None:
        """Same input → same output (deterministic)."""
        r1 = self.rewriter.rewrite(TRIGGER_SKILL_MD, "test/SKILL.md")
        r2 = self.rewriter.rewrite(TRIGGER_SKILL_MD, "test/SKILL.md")
        self.assertEqual(r1[0], r2[0])
        self.assertEqual(r1[1].entries, r2[1].entries)

    # --- Rule 2: ask_user → elicitation ----------------------------------

    def test_rule2_ask_user_to_elicitation(self) -> None:
        """Rule 2: ask_user and ask-user → elicitation (case-insensitive)."""
        rewritten, report = self.rewriter.rewrite(
            ASK_USER_SKILL_MD, file_path="test/SKILL.md"
        )
        # ask_user and ask-user should be replaced
        self.assertNotIn("ask_user", rewritten)
        self.assertNotIn("ask-user", rewritten)
        self.assertNotIn("Ask_user", rewritten)
        self.assertNotIn("Ask-user", rewritten)
        # elicitation should be present
        self.assertIn("elicitation", rewritten)

        ask_user_entries = [
            e for e in report.entries
            if e.rule_applied == "ask_user_to_elicitation"
        ]
        self.assertGreaterEqual(len(ask_user_entries), 3)
        for entry in ask_user_entries:
            self.assertEqual(entry.rewritten_text, "elicitation")
            self.assertEqual(entry.rule_applied, "ask_user_to_elicitation")

    def test_rule2_case_insensitive(self) -> None:
        """ask_user, Ask_user, ASK_USER all → elicitation."""
        text = "Use ask_user, Ask_user, and ASK_USER to clarify."
        rewritten, report = self.rewriter.rewrite(text)
        self.assertNotIn("ask_user", rewritten.lower())
        # Count occurrences of elicitation
        self.assertEqual(rewritten.count("elicitation"), 3)

    # --- Rule 3: CLAUDE.md → flag only -----------------------------------

    def test_rule3_claude_md_flagged_not_rewritten(self) -> None:
        """Rule 3: CLAUDE.md references are flagged but NOT rewritten."""
        rewritten, report = self.rewriter.rewrite(
            CLAUDE_MD_SKILL_MD, file_path="test/SKILL.md"
        )
        # CLAUDE.md should still be in the text (not rewritten)
        self.assertIn("CLAUDE.md", rewritten)

        # But it should be flagged in the report
        claude_entries = [
            e for e in report.entries
            if e.rule_applied == "claude_md_flag"
        ]
        self.assertGreaterEqual(len(claude_entries), 2)  # 2 occurrences
        for entry in claude_entries:
            self.assertEqual(entry.original_text, "CLAUDE.md")
            self.assertEqual(entry.rewritten_text, "CLAUDE.md")  # unchanged
            self.assertEqual(entry.rule_applied, "claude_md_flag")

        # text_changed should be False (only flag-only rules triggered)
        self.assertFalse(report.text_changed)

    # --- Combined rules ---------------------------------------------------

    def test_combined_all_three_rules(self) -> None:
        """All three rules in one document."""
        rewritten, report = self.rewriter.rewrite(
            COMBINED_SKILL_MD, file_path="test/SKILL.md"
        )
        # Rule 1: trigger replaced
        self.assertNotIn("/commercial-legal:risk-identification", rewritten)
        self.assertIn("When the user asks about risk-identification...", rewritten)
        # Rule 2: ask_user replaced
        self.assertNotIn("ask_user", rewritten)
        self.assertIn("elicitation", rewritten)
        # Rule 3: CLAUDE.md still present (flagged only)
        self.assertIn("CLAUDE.md", rewritten)

        # Report should have entries from all three rules
        rules = {e.rule_applied for e in report.entries}
        self.assertIn("trigger_to_natural_language", rules)
        self.assertIn("ask_user_to_elicitation", rules)
        self.assertIn("claude_md_flag", rules)

        # text_changed should be True (rules 1 and 2 changed text)
        self.assertTrue(report.text_changed)

    # --- Edge cases -------------------------------------------------------

    def test_clean_text_no_rewrites(self) -> None:
        """Text with no patterns produces zero rewrites."""
        rewritten, report = self.rewriter.rewrite(CLEAN_SKILL_MD)
        self.assertEqual(rewritten, CLEAN_SKILL_MD)
        self.assertEqual(report.total_rewrites, 0)
        self.assertEqual(len(report.entries), 0)
        self.assertFalse(report.text_changed)

    def test_patterns_inside_code_blocks_still_rewritten(self) -> None:
        """Patterns inside code blocks are still rewritten (documented behavior)."""
        text = "```bash\n/commercial-legal:risk-identification\n```"
        rewritten, report = self.rewriter.rewrite(text)
        self.assertNotIn("/commercial-legal:risk-identification", rewritten)
        self.assertIn("When the user asks about risk-identification...", rewritten)

    def test_reversible_report_contains_original_text(self) -> None:
        """The report contains enough information to reconstruct the original."""
        text = "Use /commercial-legal:risk-identification and ask_user."
        rewritten, report = self.rewriter.rewrite(text, "test/SKILL.md")
        # Each entry has original_text and rewritten_text
        for entry in report.entries:
            self.assertTrue(entry.original_text)
            self.assertTrue(entry.rewritten_text)
            # The original text should be findable in the original
            self.assertIn(entry.original_text, text)
            # The rewritten text should be findable in the rewritten
            self.assertIn(entry.rewritten_text, rewritten)

    def test_location_includes_file_path_and_line_number(self) -> None:
        """RewriteReport entries have location with file path + line number."""
        text = "Line 1\n/commercial-legal:risk-identification\nLine 3"
        _rewritten, report = self.rewriter.rewrite(text, "path/to/SKILL.md")
        trigger_entry = [
            e for e in report.entries
            if e.rule_applied == "trigger_to_natural_language"
        ][0]
        self.assertIn("path/to/SKILL.md", trigger_entry.location)
        self.assertIn(":", trigger_entry.location)
        # Line number should be 2 (the trigger is on line 2)
        self.assertEqual(trigger_entry.line_number, 2)

    def test_returns_tuple_of_str_and_report(self) -> None:
        """rewrite() returns (rewritten_text, RewriteReport)."""
        result = self.rewriter.rewrite("test text")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], RewriteReport)


if __name__ == "__main__":
    unittest.main()
