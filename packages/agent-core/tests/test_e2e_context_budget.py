"""E2E test: context budget — skill body injection + history trim.

Verifies the AgentContextAssembler handles skill bodies (2K-20K tokens)
+ conversation history under a token budget.  Tests:

1. Small budget, large skill body → skill body trimmed, report recorded
2. Large history, budget constraint → oldest turns dropped, report recorded
3. Protected section exceeds budget → ContextAssemblyBudgetError
4. Determinism: same input + same budget → identical output
5. CJK content → CJK-aware token estimation (1 token per CJK char)
6. Multiple skill bodies → all fit with some trimming of the largest

Success criterion 3: 上下文预算与裁剪策略生效——给定 token 预算与一组
skill 正文（2K–20K token）+ 历史，装配器产出确定性的上下文并记录被裁剪内容.
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


def _make_large_skill_body(
    skill_id: str = "large-skill",
    *,
    target_tokens: int = 20000,
    chars_per_token: int = 4,
) -> dict:
    """Build a skill body that is approximately target_tokens tokens.

    Generates a skill body with frontmatter + description + multiple sections
    of varying priority.  The total size is approximately target_tokens.
    """
    target_chars = target_tokens * chars_per_token
    parts = [
        "---",
        "skill_id: " + skill_id,
        "name: Large Legal Skill",
        "---",
        "",
        "This skill performs comprehensive legal analysis.",
        "",
    ]

    # Protected section (first ## section)
    section1_size = target_chars // 6
    parts.append("## Legal Framework")
    parts.append("x" * section1_size)
    parts.append("")

    # High priority section (research-gate)
    section2_size = target_chars // 6
    parts.append("## research-gate")
    parts.append("y" * section2_size)
    parts.append("")

    # Medium priority sections
    for i in range(3):
        section_size = target_chars // 6
        parts.append(f"## Analysis Step {i+1}")
        parts.append("z" * section_size)
        parts.append("")

    # Low priority sections (example, appendix, reference)
    for name in ("example", "appendix", "reference"):
        section_size = target_chars // 6
        parts.append(f"## {name}")
        parts.append("w" * section_size)
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


def _make_cjk_skill_body(skill_id: str = "cjk-skill") -> dict:
    """Build a skill body with Chinese (CJK) content."""
    parts = [
        "---",
        "skill_id: " + skill_id,
        "name: 中文法律技能",
        "---",
        "",
        "这是一个中文法律技能，用于合同法分析。",
        "",
        "## 法律框架",
        "合同法第三条规定当事人订立、履行合同应当遵循自愿原则。",
        "合同法第四条规定当事人依法享有自愿订立合同的权利。",
        "",
        "## research-gate",
        "在给出法律结论之前，必须先检索相关法规。",
        "",
        "## 示例",
        "甲方与乙方签订买卖合同，合同标的为一批货物。",
        "",
        "## 附录",
        "相关法规条文索引。",
        "",
    ]
    return {"skill_id": skill_id, "body": "\n".join(parts)}


# ---------------------------------------------------------------------------
# Scenario 1: Small budget, large skill body → skill body trimmed
# ---------------------------------------------------------------------------


class TestSmallBudgetLargeSkillBody(unittest.TestCase):
    """Skill body is 20K tokens, budget is 8K → skill body trimmed."""

    def test_skill_body_trimmed_with_report(self):
        """Large skill body is trimmed and trimmed_skill_sections records what was cut."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=8000,
            chars_per_token=4,
            skill_body_budget_fraction=0.6,  # 4800 tokens for skills
        ))

        skill = _make_large_skill_body(target_tokens=20000, chars_per_token=4)
        result = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "Analyze this contract."},
        )

        # trimmed_skill_sections should be non-empty
        self.assertGreater(len(result.trimmed_skill_sections), 0,
            "Expected trimmed_skill_sections to be non-empty for large skill body")

        # Each trimmed section should have required fields
        for ts in result.trimmed_skill_sections:
            self.assertIn("section_name", ts)
            self.assertIn("priority", ts)
            self.assertIn("original_tokens", ts)
            self.assertIn("reason", ts)

    def test_result_fits_budget_after_trimming(self):
        """After trimming, estimated_tokens <= budget_tokens."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=8000,
            chars_per_token=4,
        ))

        skill = _make_large_skill_body(target_tokens=20000, chars_per_token=4)
        result = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        self.assertLessEqual(
            result.estimated_tokens, 8000,
            f"Estimated tokens {result.estimated_tokens} should be <= budget 8000",
        )

    def test_low_priority_sections_trimmed_first(self):
        """Low-priority sections (example, appendix, reference) are trimmed before high-priority."""
        # Use a budget where protected sections fit but total skill body needs trimming
        # Protected sections ≈ frontmatter + description + first section ≈ 3364 tokens
        # So skill budget needs to be > 3364 but < total (20000)
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=10000,
            chars_per_token=4,
            skill_body_budget_fraction=0.6,  # 6000 tokens for skills
        ))

        skill = _make_large_skill_body(target_tokens=20000, chars_per_token=4)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        # Low-priority sections should be in trimmed_skill_sections
        trimmed_names = [ts["section_name"] for ts in result.trimmed_skill_sections]
        # At least one low-priority section should be trimmed
        low_priority_names = {"example", "appendix", "reference"}
        trimmed_low = low_priority_names.intersection(trimmed_names)
        self.assertGreater(len(trimmed_low), 0,
            f"Expected low-priority sections to be trimmed first. "
            f"Trimmed: {trimmed_names}")


# ---------------------------------------------------------------------------
# Scenario 2: Large history, budget constraint → oldest turns dropped
# ---------------------------------------------------------------------------


class TestLargeHistoryBudgetConstraint(unittest.TestCase):
    """50 turns of history + 5K skill body, budget 16K → oldest turns dropped."""

    def test_oldest_history_turns_dropped(self):
        """Oldest history turns are dropped when over budget."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=16000,
            chars_per_token=4,
            max_history_turns=20,
            history_budget_fraction=0.3,  # 4800 tokens for history
        ))

        skill = _make_large_skill_body(target_tokens=5000, chars_per_token=4)
        history = _make_history(50, content_size=100)

        result = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )

        # dropped_sections should record history turns dropped
        self.assertTrue(
            "history_turns_dropped" in result.dropped_sections or
            "history_turns_truncated" in result.dropped_sections,
            f"Expected history turns dropped in dropped_sections: {result.dropped_sections}",
        )

    def test_result_fits_budget_with_large_history(self):
        """After history trimming, estimated_tokens <= budget."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=16000,
            chars_per_token=4,
        ))

        skill = _make_large_skill_body(target_tokens=5000, chars_per_token=4)
        history = _make_history(50, content_size=100)

        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )

        self.assertLessEqual(
            result.estimated_tokens, 16000,
            f"Estimated tokens {result.estimated_tokens} should be <= budget 16000",
        )

    def test_max_history_turns_truncation(self):
        """History is truncated to max_history_turns."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=100000,  # large budget so no budget-driven trimming
            max_history_turns=5,
        ))

        history = _make_history(50, content_size=10)
        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[],
            history=history,
            current_turn={"role": "user", "content": "q"},
        )

        # History should be truncated to 5 turns = 10 messages
        # Count non-system, non-current messages
        history_msgs = [
            m for m in result.messages
            if m.get("role") in ("user", "assistant") and m != {"role": "user", "content": "q"}
        ]
        self.assertLessEqual(len(history_msgs), 10,
            f"History should be truncated to max_history_turns*2=10 messages, got {len(history_msgs)}")


# ---------------------------------------------------------------------------
# Scenario 3: Protected section exceeds budget → ContextAssemblyBudgetError
# ---------------------------------------------------------------------------


class TestProtectedSectionExceedsBudget(unittest.TestCase):
    """Protected sections (system prompt + current turn) > budget → error."""

    def test_system_prompt_exceeds_budget_raises(self):
        """System prompt alone exceeds budget → ContextAssemblyBudgetError."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=10,  # very small budget
            chars_per_token=4,
        ))

        large_system = "x" * 100  # 25 tokens, exceeds budget of 10

        with self.assertRaises(ContextAssemblyBudgetError):
            assembler.assemble(
                system_prompt=large_system,
                skill_bodies=[],
                history=[],
                current_turn={"role": "user", "content": "q"},
            )

    def test_protected_skill_sections_exceed_budget_raises(self):
        """Protected skill sections exceed skill budget → ContextAssemblyBudgetError."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=100,
            chars_per_token=4,
            skill_body_budget_fraction=0.6,  # 60 tokens for skills
        ))

        # Skill with very large protected sections (frontmatter + description + first section)
        skill = _make_skill_body(sections=[
            ("Protected Section", "x" * 1000),  # 250 tokens, exceeds 60
        ])

        with self.assertRaises(ContextAssemblyBudgetError):
            assembler.assemble(
                system_prompt="System",
                skill_bodies=[skill],
                history=[],
                current_turn={"role": "user", "content": "q"},
            )


# ---------------------------------------------------------------------------
# Scenario 4: Determinism — same input + same budget → identical output
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    """Same input + same budget → identical output across two calls."""

    def test_deterministic_output(self):
        """Two calls with same input produce identical results."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=8000,
            chars_per_token=4,
        ))

        skill = _make_large_skill_body(target_tokens=10000, chars_per_token=4)
        history = _make_history(10, content_size=50)

        result1 = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "Analyze this."},
        )

        result2 = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=[skill],
            history=history,
            current_turn={"role": "user", "content": "Analyze this."},
        )

        # Messages should be identical
        self.assertEqual(result1.messages, result2.messages,
            "Same input should produce identical messages")

        # estimated_tokens should be identical
        self.assertEqual(result1.estimated_tokens, result2.estimated_tokens)

        # Trim reports should be identical
        self.assertEqual(result1.trimmed_skill_sections, result2.trimmed_skill_sections)
        self.assertEqual(result1.dropped_sections, result2.dropped_sections)

    def test_deterministic_with_cjk(self):
        """Determinism holds with CJK content."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=500,
            chars_per_token=4,
        ))

        skill = _make_cjk_skill_body()

        result1 = assembler.assemble(
            system_prompt="你是一个法律助手。",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "分析合同法"},
        )

        result2 = assembler.assemble(
            system_prompt="你是一个法律助手。",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "分析合同法"},
        )

        self.assertEqual(result1.messages, result2.messages)
        self.assertEqual(result1.estimated_tokens, result2.estimated_tokens)


# ---------------------------------------------------------------------------
# Scenario 5: CJK content → CJK-aware token estimation
# ---------------------------------------------------------------------------


class TestCJKContentEstimation(unittest.TestCase):
    """CJK content is estimated at 1 token per CJK character."""

    def test_cjk_chars_one_token_each(self):
        """Chinese characters are estimated at 1 token each."""
        from inkstatute_agent_core.context import _estimate_tokens

        # 10 CJK characters → 10 tokens
        cjk_text = "合同法第三条规定"  # 8 CJK chars
        tokens = _estimate_tokens(cjk_text, chars_per_token=4)
        self.assertEqual(tokens, 8,
            f"8 CJK chars should be 8 tokens, got {tokens}")

    def test_mixed_cjk_non_cjk(self):
        """Mixed CJK + non-CJK content is estimated correctly."""
        from inkstatute_agent_core.context import _estimate_tokens

        # "合同法abc" = 3 CJK + 3 non-CJK → 3 + 3//4 = 3 + 0 = 3 tokens
        mixed_text = "合同法abc"
        tokens = _estimate_tokens(mixed_text, chars_per_token=4)
        # 3 CJK chars + 3 non-CJK chars → 3 + 0 = 3
        self.assertEqual(tokens, 3 + 3 // 4,
            f"Mixed CJK/non-CJK estimation incorrect: got {tokens}")

    def test_cjk_skill_body_assembled(self):
        """CJK skill body is assembled correctly with CJK-aware estimation."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=10000,
            chars_per_token=4,
        ))

        skill = _make_cjk_skill_body()
        result = assembler.assemble(
            system_prompt="你是一个法律助手。",
            skill_bodies=[skill],
            history=[],
            current_turn={"role": "user", "content": "分析合同法"},
        )

        # Result should contain CJK content
        all_content = " ".join(
            str(m.get("content", "")) for m in result.messages
        )
        self.assertIn("合同法", all_content,
            "Assembled context should contain CJK content")

        # Estimated tokens should be positive
        self.assertGreater(result.estimated_tokens, 0)


# ---------------------------------------------------------------------------
# Scenario 6: Multiple skill bodies → all fit with some trimming
# ---------------------------------------------------------------------------


class TestMultipleSkillBodies(unittest.TestCase):
    """3 skill bodies (5K, 10K, 20K tokens), budget 32K → all fit with trimming."""

    def test_three_skill_bodies_fit_with_trimming(self):
        """Multiple skill bodies are handled correctly under budget."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=32000,
            chars_per_token=4,
            skill_body_budget_fraction=0.6,  # 19200 tokens for skills
        ))

        skills = [
            _make_large_skill_body(skill_id="small", target_tokens=5000, chars_per_token=4),
            _make_large_skill_body(skill_id="medium", target_tokens=10000, chars_per_token=4),
            _make_large_skill_body(skill_id="large", target_tokens=20000, chars_per_token=4),
        ]

        result = assembler.assemble(
            system_prompt="You are a legal assistant.",
            skill_bodies=skills,
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        # Result fits budget
        self.assertLessEqual(
            result.estimated_tokens, 32000,
            f"Estimated tokens {result.estimated_tokens} should be <= budget 32000",
        )

        # At least the largest skill body should have trimmed sections
        self.assertGreater(len(result.trimmed_skill_sections), 0,
            "Expected trimmed sections for large skill body")

        # All three skill bodies should be present in the messages
        # (as system messages with their content)
        system_msgs = [m for m in result.messages if m.get("role") == "system"]
        # system_prompt + skill_bodies
        self.assertGreaterEqual(len(system_msgs), 3,
            f"Expected at least 3 system messages (1 system prompt + skill bodies), got {len(system_msgs)}")

    def test_multiple_skill_bodies_deterministic(self):
        """Multiple skill bodies produce deterministic results."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=32000,
            chars_per_token=4,
        ))

        skills = [
            _make_large_skill_body(skill_id="s1", target_tokens=5000, chars_per_token=4),
            _make_large_skill_body(skill_id="s2", target_tokens=10000, chars_per_token=4),
        ]

        result1 = assembler.assemble(
            system_prompt="System",
            skill_bodies=skills,
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        result2 = assembler.assemble(
            system_prompt="System",
            skill_bodies=skills,
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        self.assertEqual(result1.messages, result2.messages)
        self.assertEqual(result1.estimated_tokens, result2.estimated_tokens)


# ---------------------------------------------------------------------------
# Scenario 7: Protected sections recorded
# ---------------------------------------------------------------------------


class TestProtectedSectionsRecorded(unittest.TestCase):
    """Protected sections are recorded in the result."""

    def test_protected_sections_listed(self):
        """protected_sections includes system_prompt and current_turn."""
        assembler = AgentContextAssembler(AgentContextPolicy(
            budget_tokens=10000,
        ))

        result = assembler.assemble(
            system_prompt="System",
            skill_bodies=[_make_skill_body()],
            history=[],
            current_turn={"role": "user", "content": "q"},
        )

        self.assertIn("system_prompt", result.protected_sections)
        self.assertIn("current_turn", result.protected_sections)


if __name__ == "__main__":
    unittest.main()
