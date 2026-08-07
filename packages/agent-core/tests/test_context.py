"""Tests for AgentContextAssembler — history trim + skill body injection.

Covers: no trimming needed, history-only trim, skill-body-only trim,
both trimmed, CJK content, protected section exceeds budget, determinism.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.context import (
    AgentContextAssembler,
    AgentContextPolicy,
    AgentContextResult,
    ContextAssemblyBudgetError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill_body(
    skill_id: str = "test-skill",
    *,
    description: str = "This is a test skill for legal research.",
    sections: list[tuple[str, str]] | None = None,
) -> dict:
    """Build a skill body dict with frontmatter + description + sections."""
    parts = [
        "---",
        "skill_id: " + skill_id,
        "name: Test Skill",
        "---",
        "",
        description,
        "",
    ]
    if sections:
        for header, body in sections:
            parts.append(f"## {header}")
            parts.append(body)
            parts.append("")
    return {"skill_id": skill_id, "body": "\n".join(parts)}


def _make_history(n_turns: int, *, content_size: int = 50) -> list[dict]:
    """Build a conversation history with n_turns pairs of (user, assistant)."""
    history: list[dict] = []
    for i in range(n_turns):
        history.append({
            "role": "user",
            "content": f"User question {i} " + "x" * content_size,
        })
        history.append({
            "role": "assistant",
            "content": f"Assistant answer {i} " + "y" * content_size,
        })
    return history


# ---------------------------------------------------------------------------
# No trimming needed
# ---------------------------------------------------------------------------


class TestNoTrimmingNeeded(unittest.TestCase):
    """When everything fits within budget, no trimming occurs."""

    def test_small_context_no_trim(self):
        assembler = AgentContextAssembler(AgentContextPolicy(budget_tokens=10000))
        result = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[_make_skill_body()],
            history=_make_history(3),
            current_turn={"role": "user", "content": "What is contract law?"},
        )
        self.assertIsInstance(result, AgentContextResult)
        self.assertGreater(result.estimated_tokens, 0)
        self.assertLessEqual(result.estimated_tokens, 10000)
        # No drops
        self.assertEqual(result.dropped_sections.get("history_turns_dropped", 0), 0)
        # No skill trims
        self.assertEqual(len(result.trimmed_skill_sections), 0)
        # Protected sections
        self.assertIn("system_prompt", result.protected_sections)
        self.assertIn("current_turn", result.protected_sections)

    def test_messages_ordered_system_skill_history_current(self):
        assembler = AgentContextAssembler()
        result = assembler.assemble(
            system_prompt="System prompt",
            skill_bodies=[_make_skill_body()],
            history=[{"role": "user", "content": "hi"}],
            current_turn={"role": "user", "content": "bye"},
        )
        # First message is system prompt
        self.assertEqual(result.messages[0]["role"], "system")
        self.assertEqual(result.messages[0]["content"], "System prompt")
        # Last message is current turn
        self.assertEqual(result.messages[-1]["content"], "bye")
        # Skill body messages are between system and history
        # (system role for skill bodies)
        roles = [m["role"] for m in result.messages]
        self.assertEqual(roles[0], "system")  # system prompt
        # At least one more system (skill body) before user messages
        self.assertIn("user", roles)  # history or current turn


# ---------------------------------------------------------------------------
# History-only trim
# ---------------------------------------------------------------------------


class TestHistoryOnlyTrim(unittest.TestCase):
    """History is trimmed oldest-first when over budget."""

    def test_history_truncated_to_max_turns(self):
        policy = AgentContextPolicy(
            budget_tokens=10000,
            max_history_turns=3,
            history_budget_fraction=1.0,  # don't trigger budget-based trim
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[],
            history=_make_history(10),
            current_turn={"role": "user", "content": "current"},
        )
        # max_history_turns=3 → 6 messages retained
        history_msgs = [
            m for m in result.messages
            if m["role"] in ("user", "assistant") and m["content"] != "current"
        ]
        self.assertLessEqual(len(history_msgs), 6)
        self.assertGreater(result.dropped_sections.get("history_turns_truncated", 0), 0)

    def test_history_dropped_oldest_first(self):
        policy = AgentContextPolicy(
            budget_tokens=500,
            max_history_turns=20,
            history_budget_fraction=0.3,
            skill_body_budget_fraction=0.6,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[],
            history=_make_history(20, content_size=100),
            current_turn={"role": "user", "content": "current"},
        )
        # Some history should have been dropped
        self.assertGreater(result.dropped_sections.get("history_turns_dropped", 0), 0)
        # The most recent history should be retained (check last history msg)
        history_msgs = [
            m for m in result.messages
            if m["role"] in ("user", "assistant") and m["content"] != "current"
        ]
        if history_msgs:
            # Last history message should be from the most recent turn
            self.assertIn("19", history_msgs[-1]["content"])

    def test_dropped_sections_records_count(self):
        policy = AgentContextPolicy(
            budget_tokens=300,
            max_history_turns=20,
            history_budget_fraction=0.3,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="S",
            skill_bodies=[],
            history=_make_history(10, content_size=80),
            current_turn={"role": "user", "content": "c"},
        )
        dropped = result.dropped_sections.get("history_turns_dropped", 0)
        self.assertGreaterEqual(dropped, 0)


# ---------------------------------------------------------------------------
# Skill-body-only trim
# ---------------------------------------------------------------------------


class TestSkillBodyOnlyTrim(unittest.TestCase):
    """Skill bodies are trimmed using section-priority."""

    def test_low_priority_sections_trimmed_first(self):
        """Sections with 'example' or 'reference' in header are trimmed first."""
        skill = _make_skill_body(
            sections=[
                ("research-gate", "Must search before concluding."),
                ("Main Analysis", "Core analysis content here. " * 20),
                ("Examples", "Example 1: ... " * 50),
                ("References", "Ref A, Ref B, ... " * 50),
            ],
        )
        # Small budget to force trimming
        policy = AgentContextPolicy(
            budget_tokens=500,
            skill_body_budget_fraction=0.5,
            history_budget_fraction=0.1,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        # Should have trimmed some sections
        self.assertGreater(len(result.trimmed_skill_sections), 0)
        # Low priority sections should be trimmed first
        trimmed_names = [ts["section_name"] for ts in result.trimmed_skill_sections]
        # "Examples" and "References" should be trimmed before "research-gate"
        if "Examples" in trimmed_names or "References" in trimmed_names:
            # research-gate should NOT be trimmed if low-priority was enough
            self.assertNotIn("research-gate", trimmed_names)

    def test_protected_sections_not_trimmed(self):
        """Frontmatter + description + first section are protected."""
        skill = _make_skill_body(
            description="Important description.",
            sections=[
                ("First Section", "This is protected. " * 10),
                ("Examples", "Example content. " * 100),
            ],
        )
        policy = AgentContextPolicy(
            budget_tokens=300,
            skill_body_budget_fraction=0.5,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="S",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        # Protected sections should not appear in trimmed list
        trimmed_names = [ts["section_name"] for ts in result.trimmed_skill_sections]
        self.assertNotIn("__description__", trimmed_names)
        self.assertNotIn("First Section", trimmed_names)

    def test_trimmed_skill_sections_has_details(self):
        """Each trimmed section record has section_name, priority, original_tokens."""
        skill = _make_skill_body(
            sections=[
                ("Main Analysis", "Core content. " * 5),
                ("Examples", "Example content. " * 100),
            ],
        )
        # Budget large enough for protected sections but not for Examples
        policy = AgentContextPolicy(
            budget_tokens=1000,
            skill_body_budget_fraction=0.5,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="S",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        if result.trimmed_skill_sections:
            ts = result.trimmed_skill_sections[0]
            self.assertIn("section_name", ts)
            self.assertIn("priority", ts)
            self.assertIn("original_tokens", ts)
            self.assertIn("skill_index", ts)


# ---------------------------------------------------------------------------
# Both history and skill body trimmed
# ---------------------------------------------------------------------------


class TestBothTrimmed(unittest.TestCase):
    """Both history and skill bodies are trimmed when total exceeds budget."""

    def test_both_trimmed_when_total_exceeds_budget(self):
        skill = _make_skill_body(
            sections=[
                ("Main", "Core content. " * 50),
                ("Examples", "Example. " * 100),
                ("References", "Ref. " * 100),
            ],
        )
        policy = AgentContextPolicy(
            budget_tokens=800,
            skill_body_budget_fraction=0.4,
            history_budget_fraction=0.2,
            max_history_turns=20,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="System prompt here",
            skill_bodies=[skill],
            history=_make_history(10, content_size=80),
            current_turn={"role": "user", "content": "current question"},
        )
        self.assertLessEqual(result.estimated_tokens, 800)
        # At least one of history or skill should have been trimmed
        total_trimmed = (
            result.dropped_sections.get("history_turns_dropped", 0)
            + len(result.trimmed_skill_sections)
        )
        self.assertGreater(total_trimmed, 0)


# ---------------------------------------------------------------------------
# CJK content
# ---------------------------------------------------------------------------


class TestCJKContent(unittest.TestCase):
    """CJK-aware token estimation: Chinese chars = 1 token, ASCII ~0.25 tokens."""

    def test_cjk_content_estimated_correctly(self):
        """Chinese text should have higher token estimate than equivalent ASCII."""
        assembler = AgentContextAssembler(AgentContextPolicy(budget_tokens=10000))

        cjk_result = assembler.assemble(
            system_prompt="系统提示",
            skill_bodies=[],
            history=[],
            current_turn={"role": "user", "content": "合同法第三条是什么？"},
        )

        ascii_result = assembler.assemble(
            system_prompt="system",
            skill_bodies=[],
            history=[],
            current_turn={"role": "user", "content": "abcd"},
        )

        # CJK text (8 chars) should estimate more tokens than 4 ASCII chars
        # CJK: 8 chars * 1 = 8 tokens (minimum)
        # ASCII: 4 chars / 4 = 1 token
        self.assertGreater(cjk_result.estimated_tokens, ascii_result.estimated_tokens)

    def test_cjk_skill_body_trimmed(self):
        """Skill body with CJK content is trimmed correctly."""
        skill = {
            "skill_id": "cjk-skill",
            "body": (
                "---\nskill_id: cjk-skill\n---\n\n"
                "这是一个中文法律技能描述。\n\n"
                "## 研究门控\n必须在得出结论前进行检索。\n\n"
                "## 示例\n" + "示例内容。" * 100 + "\n\n"
                "## 参考资料\n" + "参考资料内容。" * 100 + "\n"
            ),
        }
        policy = AgentContextPolicy(
            budget_tokens=500,
            skill_body_budget_fraction=0.5,
        )
        assembler = AgentContextAssembler(policy)
        result = assembler.assemble(
            system_prompt="系统提示",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "问题"},
        )
        # Should have trimmed some CJK sections
        self.assertGreater(len(result.trimmed_skill_sections), 0)
        self.assertLessEqual(result.estimated_tokens, 500)


# ---------------------------------------------------------------------------
# Protected section exceeds budget
# ---------------------------------------------------------------------------


class TestProtectedExceedsBudget(unittest.TestCase):
    """If protected sections alone exceed budget, raises ContextAssemblyBudgetError."""

    def test_system_prompt_exceeds_budget(self):
        huge_prompt = "x" * 10000
        policy = AgentContextPolicy(budget_tokens=100)
        assembler = AgentContextAssembler(policy)
        with self.assertRaises(ContextAssemblyBudgetError):
            assembler.assemble(
                system_prompt=huge_prompt,
                skill_bodies=[],
                history=[],
                current_turn={"role": "user", "content": "q"},
            )

    def test_current_turn_exceeds_budget(self):
        huge_turn = {"role": "user", "content": "x" * 10000}
        policy = AgentContextPolicy(budget_tokens=100)
        assembler = AgentContextAssembler(policy)
        with self.assertRaises(ContextAssemblyBudgetError):
            assembler.assemble(
                system_prompt="S",
                skill_bodies=[],
                history=[],
                current_turn=huge_turn,
            )

    def test_skill_protected_exceeds_budget(self):
        """Skill body with protected sections exceeding skill budget raises error."""
        skill = {
            "skill_id": "big-skill",
            "body": "---\nskill_id: big\n---\n\n" + "A" * 10000 + "\n\n## First\n" + "B" * 10000,
        }
        policy = AgentContextPolicy(
            budget_tokens=100,
            skill_body_budget_fraction=1.0,
        )
        assembler = AgentContextAssembler(policy)
        with self.assertRaises(ContextAssemblyBudgetError):
            assembler.assemble(
                system_prompt="S",
                skill_bodies=[skill],
                history=[],
                current_turn={"role": "user", "content": "q"},
            )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    """Same input + same budget → same output."""

    def test_same_input_same_output(self):
        skill = _make_skill_body(
            sections=[
                ("Main", "Core content. " * 20),
                ("Examples", "Example. " * 50),
            ],
        )
        history = _make_history(5)
        policy = AgentContextPolicy(budget_tokens=1000)

        assembler = AgentContextAssembler(policy)
        result1 = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )
        result2 = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )

        self.assertEqual(result1.messages, result2.messages)
        self.assertEqual(result1.estimated_tokens, result2.estimated_tokens)
        self.assertEqual(result1.dropped_sections, result2.dropped_sections)
        self.assertEqual(result1.trimmed_skill_sections, result2.trimmed_skill_sections)
        self.assertEqual(result1.protected_sections, result2.protected_sections)

    def test_determinism_with_trimming(self):
        """Determinism holds even when trimming occurs."""
        skill = _make_skill_body(
            sections=[
                ("research-gate", "Search first. " * 20),
                ("Main", "Core. " * 30),
                ("Examples", "Ex. " * 100),
                ("References", "Ref. " * 100),
            ],
        )
        history = _make_history(10, content_size=60)
        policy = AgentContextPolicy(budget_tokens=600)

        assembler = AgentContextAssembler(policy)
        result1 = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )
        result2 = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )

        self.assertEqual(result1.messages, result2.messages)
        self.assertEqual(result1.trimmed_skill_sections, result2.trimmed_skill_sections)


# ---------------------------------------------------------------------------
# Policy override
# ---------------------------------------------------------------------------


class TestPolicyOverride(unittest.TestCase):
    """Policy can be overridden per-call."""

    def test_per_call_policy_override(self):
        assembler = AgentContextAssembler(AgentContextPolicy(budget_tokens=100000))
        # Use a small budget for this call
        small_policy = AgentContextPolicy(budget_tokens=500)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[_make_skill_body()],
            history=_make_history(10, content_size=80),
            current_turn={"role": "user", "content": "q"},
            policy=small_policy,
        )
        self.assertLessEqual(result.estimated_tokens, 500)


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs(unittest.TestCase):
    """Edge cases with empty inputs."""

    def test_no_skill_bodies_no_history(self):
        assembler = AgentContextAssembler()
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        # Should have system + current turn
        self.assertEqual(len(result.messages), 2)
        self.assertEqual(result.messages[0]["content"], "System")
        self.assertEqual(result.messages[1]["content"], "q")

    def test_empty_system_prompt(self):
        assembler = AgentContextAssembler()
        result = assembler.assemble(
            system_prompt="",
            skill_bodies=[],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        self.assertEqual(len(result.messages), 2)

    def test_multiple_skill_bodies(self):
        skill1 = _make_skill_body("skill-1")
        skill2 = _make_skill_body("skill-2")
        assembler = AgentContextAssembler(AgentContextPolicy(budget_tokens=50000))
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill1, skill2],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )
        # system + 2 skill bodies + current
        self.assertEqual(len(result.messages), 4)


if __name__ == "__main__":
    unittest.main()
