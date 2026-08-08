"""Tests for GuardrailBoundary — post-hoc citation audit + de-AI polish + high-risk review.

Covers SAFE-01 (non-bypassable boundary), SAFE-02 (citation audit),
SAFE-03 (de-AI polish), SAFE-04 (high-risk review).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import unittest

from arena_engine.guardrail_boundary import (
    GuardrailResult,
    _HIGH_RISK_KEYWORDS,
    _is_high_risk_legal_conclusion,
    apply_post_hoc_guardrails,
)


class GuardrailBoundaryTests(unittest.IsolatedAsyncioTestCase):
    """Cover all 8 GuardrailBoundary behaviours from Plan 107-02 Task 2."""

    # Test 1 (SAFE-02) — citation audit populated for external agents
    async def test_citation_audit_populated_for_external(self) -> None:
        result = await apply_post_hoc_guardrails(
            content="根据《民法典》第143条的规定，民事法律行为有效。",
            retrievals=[],
            is_external=True,
        )
        self.assertIsInstance(result, GuardrailResult)
        self.assertIsNotNone(result.citation_audit)
        assert result.citation_audit is not None
        self.assertGreaterEqual(result.citation_audit.total, 0)
        # polished_content has been through de_ai_polish
        self.assertIsInstance(result.polished_content, str)

    # Test 2 (SAFE-03) — de-AI polish removes AI patterns
    async def test_de_ai_polish_removes_ai_patterns(self) -> None:
        result = await apply_post_hoc_guardrails(
            content="作为一个AI助手，以上分析仅供参考，不构成法律建议。",
            is_external=True,
        )
        self.assertNotIn("作为一个AI助手", result.polished_content)
        self.assertNotIn("以上分析仅供参考", result.polished_content)

    # Test 3 (SAFE-04) — high-risk keywords set requires_human_review=True
    async def test_high_risk_keywords_trigger_human_review(self) -> None:
        result = await apply_post_hoc_guardrails(
            content="该合同条款违法，应认定为无效",
            is_external=True,
        )
        self.assertTrue(result.requires_human_review)

    # Test 4 (SAFE-04) — no high-risk keywords → requires_human_review=False
    async def test_no_high_risk_keywords_no_human_review(self) -> None:
        result = await apply_post_hoc_guardrails(
            content="这是一般性分析，建议查阅相关法规。",
            is_external=True,
        )
        self.assertFalse(result.requires_human_review)

    # Test 5 (SAFE-01) — self-built agents skip post-hoc guardrails
    async def test_self_built_agent_skips_guardrails(self) -> None:
        result = await apply_post_hoc_guardrails(
            content="some content from self-built agent",
            is_external=False,
        )
        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "self_built_agent_guardrails_in_turn_loop")
        self.assertIsNone(result.citation_audit)
        self.assertFalse(result.requires_human_review)
        self.assertEqual(result.polished_content, "some content from self-built agent")

    # Test 6 (SAFE-04) — _is_high_risk_legal_conclusion direct tests
    def test_is_high_risk_legal_conclusion(self) -> None:
        self.assertTrue(
            _is_high_risk_legal_conclusion("该行为构成犯罪，应承担刑事责任")
        )
        self.assertFalse(_is_high_risk_legal_conclusion("建议查阅相关法规"))

    # Test 7 — GuardrailResult is frozen slotted dataclass
    def test_guardrail_result_is_frozen_slotted(self) -> None:
        # Verify it is a dataclass with slots
        self.assertTrue(dataclasses.is_dataclass(GuardrailResult))
        # Verify frozen
        result = GuardrailResult(
            polished_content="text",
            citation_audit=None,
            requires_human_review=False,
            skipped=False,
            reason=None,
        )
        with self.assertRaises((AttributeError, dataclasses.FrozenInstanceError)):
            result.polished_content = "mutated"  # type: ignore[misc]
        # Verify fields exist
        field_names = {f.name for f in dataclasses.fields(GuardrailResult)}
        self.assertEqual(
            field_names,
            {
                "polished_content",
                "citation_audit",
                "requires_human_review",
                "skipped",
                "reason",
                "metadata",
            },
        )

    # Test 8 (SAFE-01 non-bypassable) — static analysis of guardrail_boundary.py
    def test_non_bypassable_boundary_structure(self) -> None:
        """Verify apply_post_hoc_guardrails is the ONLY public function and
        that it always calls enforce_citation_audit + de_ai_polish when
        is_external=True. No skip/fast path for external agents."""
        from arena_engine import guardrail_boundary

        source = inspect.getsource(guardrail_boundary)
        tree = ast.parse(source)

        # (a) The only public function is apply_post_hoc_guardrails
        public_functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    public_functions.append(node.name)
        self.assertEqual(
            public_functions,
            ["apply_post_hoc_guardrails"],
            f"Expected only apply_post_hoc_guardrails as public function, "
            f"got: {public_functions}",
        )

        # (b) When is_external=True, always calls enforce_citation_audit + de_ai_polish
        # Find the apply_post_hoc_guardrails function definition
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "apply_post_hoc_guardrails":
                func_def = node
                break
        self.assertIsNotNone(func_def, "apply_post_hoc_guardrails not found")

        # Collect all function calls within the function body
        called_names: set[str] = set()
        for node in ast.walk(func_def):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called_names.add(func.attr)

        self.assertIn("enforce_citation_audit", called_names)
        self.assertIn("de_ai_polish", called_names)

        # (c) No skip or fast path for external agents — the only early
        # return is for is_external=False (the self-built skip).  Verify
        # that the source does not contain a skip for is_external=True.
        # The skip branch must check `not is_external` or `is_external is False`.
        # We check that there is no `return` before the enforce_citation_audit
        # call that is NOT guarded by `not is_external`.
        # Simpler: verify the function always reaches enforce_citation_audit
        # on the external path by checking the If branch.
        if_node = None
        for child in ast.iter_child_nodes(func_def):
            if isinstance(child, ast.If):
                if_node = child
                break

        # The skip return must be inside the `if not is_external` branch
        # and the external path (else / after if) must call the guardrails.
        self.assertIsNotNone(if_node, "Expected an if-branch for is_external check")

        # Check that enforce_citation_audit and de_ai_polish are called
        # OUTSIDE the if-body (i.e. in the external path)
        if_body_calls: set[str] = set()
        for node in ast.walk(if_node):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    if_body_calls.add(func.id)

        # The guardrail calls must NOT be inside the if-skip body
        self.assertNotIn("enforce_citation_audit", if_body_calls)
        self.assertNotIn("de_ai_polish", if_body_calls)

        # Verify _HIGH_RISK_KEYWORDS is a frozenset with expected keywords
        self.assertIsInstance(_HIGH_RISK_KEYWORDS, (frozenset, set))
        for kw in ("违法", "无效", "撤销", "刑事责任"):
            self.assertIn(kw, _HIGH_RISK_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
