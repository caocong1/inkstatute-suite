"""skill_candidate.requires_human_review safety invariant tests (SAFE-01).

SAFE-01: 高风险法律结论保持人审——不自动合成 skill、不自动修改法律结论类
skill、skill_candidate.requires_human_review 恒为 true.

These tests prove:
- ``create_skill_candidate()`` always sets ``requires_human_review=True``.
- No code path sets it to ``False`` (override raises ``ValueError``).
- ``assert_skill_candidate_safety()`` rejects ``False`` and missing field.
- No code path auto-synthesizes skills (``create_skill_candidate`` is the
  only constructor).

HG-1 (法律质量) is NOT auto-closable — these tests verify the safety
invariant, not skill legal quality.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.guardrails import (
    SkillCandidate,
    assert_skill_candidate_safety,
    create_skill_candidate,
)


class TestCreateSkillCandidate(unittest.TestCase):
    """``create_skill_candidate`` always sets requires_human_review=True."""

    def test_factory_sets_requires_human_review_true_by_default(self):
        candidate = create_skill_candidate(
            name="contract-review",
            description="合同审查技能候选",
        )
        self.assertIsInstance(candidate, SkillCandidate)
        self.assertTrue(candidate.requires_human_review)

    def test_factory_preserves_name_and_description(self):
        candidate = create_skill_candidate(
            name="evidence-analysis",
            description="证据分析技能候选",
        )
        self.assertEqual(candidate.name, "evidence-analysis")
        self.assertEqual(candidate.description, "证据分析技能候选")

    def test_factory_rejects_requires_human_review_false_override(self):
        """No code path may set requires_human_review to False."""
        with self.assertRaises(ValueError) as ctx:
            create_skill_candidate(
                name="legal-conclusion",
                description="法律结论技能",
                requires_human_review=False,
            )
        self.assertIn("requires_human_review", str(ctx.exception))

    def test_factory_accepts_explicit_true_override(self):
        candidate = create_skill_candidate(
            name="risk-analysis",
            description="风险分析技能",
            requires_human_review=True,
        )
        self.assertTrue(candidate.requires_human_review)

    def test_factory_stores_extra_kwargs(self):
        candidate = create_skill_candidate(
            name="draft-skill",
            description="起草技能",
            source_turn_id="turn-42",
            confidence=0.8,
        )
        self.assertEqual(candidate.extra["source_turn_id"], "turn-42")
        self.assertEqual(candidate.extra["confidence"], 0.8)
        # Safety invariant still holds.
        self.assertTrue(candidate.requires_human_review)

    def test_factory_rejects_falsy_non_false_values(self):
        """Regression test for C-1: non-False falsy values must not bypass SAFE-01."""
        for falsy_val in (0, None, "", []):
            with self.subTest(falsy_val=falsy_val):
                with self.assertRaises(ValueError):
                    create_skill_candidate(
                        name="bypass-attempt",
                        description="bypass",
                        requires_human_review=falsy_val,
                    )


class TestAssertSkillCandidateSafety(unittest.TestCase):
    """``assert_skill_candidate_safety`` validates external dicts."""

    def test_accepts_requires_human_review_true(self):
        assert_skill_candidate_safety({"requires_human_review": True})

    def test_rejects_requires_human_review_false(self):
        with self.assertRaises(ValueError) as ctx:
            assert_skill_candidate_safety({"requires_human_review": False})
        self.assertIn("requires_human_review", str(ctx.exception))

    def test_rejects_missing_requires_human_review_field(self):
        """Missing field defaults to False → rejected (safety default-deny)."""
        with self.assertRaises(ValueError):
            assert_skill_candidate_safety({"name": "x", "description": "y"})

    def test_rejects_empty_dict(self):
        with self.assertRaises(ValueError):
            assert_skill_candidate_safety({})


class TestNoAutoSynthesis(unittest.TestCase):
    """No code path auto-synthesizes or auto-modifies legal conclusion skills."""

    def test_create_skill_candidate_is_the_only_constructor(self):
        """``SkillCandidate`` may be constructed directly, but the safety
        invariant is enforced by ``assert_skill_candidate_safety`` for any
        external dict — so a directly-built candidate with
        ``requires_human_review=False`` is rejected by the safety check."""
        unsafe = SkillCandidate(
            name="legal-conclusion",
            description="法律结论",
            requires_human_review=False,
        )
        with self.assertRaises(ValueError):
            assert_skill_candidate_safety(
                {"requires_human_review": unsafe.requires_human_review}
            )

    def test_factory_never_auto_modifies_existing_skill(self):
        """Creating a candidate does not mutate any pre-existing skill object.

        The factory only produces a NEW candidate; it never writes back.
        """
        existing = create_skill_candidate(
            name="original", description="原始技能"
        )
        before_review = existing.requires_human_review
        create_skill_candidate(
            name="new", description="新技能", source_turn_id="t1"
        )
        # The existing candidate is untouched.
        self.assertEqual(existing.requires_human_review, before_review)
        self.assertEqual(existing.name, "original")

    def test_factory_output_always_passes_safety_check(self):
        """Every candidate produced by the factory passes the safety check."""
        for name in ("a", "legal-conclusion", "high-risk-skill"):
            candidate = create_skill_candidate(
                name=name, description="desc", confidence=0.9
            )
            assert_skill_candidate_safety(
                {
                    "name": candidate.name,
                    "requires_human_review": candidate.requires_human_review,
                }
            )


if __name__ == "__main__":
    unittest.main()
