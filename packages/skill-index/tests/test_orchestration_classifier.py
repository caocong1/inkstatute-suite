"""Unit tests for the three-way cross-validation orchestration/leaf classifier.

Covers orchestration entries (depth=0 with children), leaf sub-skills
(depth=1 with parent), legal-skills flat skills, standalone skills,
plugin.json signals, name collisions, and orchestration-takes-precedence.
"""

from __future__ import annotations

import unittest

from inkstatute_skill_index.orchestration_classifier import (
    ClassificationResult,
    classify_all_skills,
    classify_skill,
)
from inkstatute_skill_index.scanner import ScannedSkill


def _make_skill(
    skill_id: str,
    relative_path: str,
    *,
    body: str = "",
    depth: int = 0,
    plugin: str | None = "commercial-legal",
    source_repo: str = "ai-for-china-legal",
) -> ScannedSkill:
    """Build a minimal ScannedSkill for testing."""
    name = skill_id.split(":")[-1] if ":" in skill_id else skill_id
    return ScannedSkill(
        skill_id=skill_id,
        name=name,
        source_repo=source_repo,
        plugin=plugin,
        relative_path=relative_path,
        absolute_path=f"/abs/{relative_path}",
        frontmatter={},
        body=body,
        raw_text=body,
        token_estimate=10,
        depth=depth,
    )


class TestOrchestrationClassifier(unittest.TestCase):
    """Verify three-way cross-validation classification logic."""

    # ------------------------------------------------------------------
    # 1. Orchestration with children in directory
    # ------------------------------------------------------------------
    def test_orchestration_with_children_in_directory(self) -> None:
        parent = _make_skill(
            "commercial-legal:contract-review",
            "commercial-legal/skills/contract-review/SKILL.md",
            body="编排入口\n子技能编排顺序",
            depth=0,
        )
        child = _make_skill(
            "commercial-legal:risk-identification",
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            body="迁移说明",
            depth=1,
        )
        result = classify_skill(parent, [parent, child])
        self.assertEqual(result.skill_type, "orchestration")
        self.assertIn("commercial-legal:risk-identification", result.child_skills)
        self.assertIn("directory_has_children", result.classification_signals)

    # ------------------------------------------------------------------
    # 2. Leaf with parent
    # ------------------------------------------------------------------
    def test_leaf_with_parent(self) -> None:
        parent = _make_skill(
            "commercial-legal:contract-review",
            "commercial-legal/skills/contract-review/SKILL.md",
            body="编排入口",
            depth=0,
        )
        child = _make_skill(
            "commercial-legal:risk-identification",
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            body="迁移说明",
            depth=1,
        )
        result = classify_skill(child, [parent, child])
        self.assertEqual(result.skill_type, "leaf")
        self.assertEqual(result.parent_skill, "commercial-legal:contract-review")

    # ------------------------------------------------------------------
    # 3. Body text orchestration signal
    # ------------------------------------------------------------------
    def test_body_text_orchestration_signal(self) -> None:
        skill = _make_skill(
            "commercial-legal:solo",
            "commercial-legal/skills/solo/SKILL.md",
            body="这是一个编排入口。子技能编排顺序如下。",
            depth=0,
        )
        result = classify_skill(skill, [skill])
        self.assertEqual(result.skill_type, "orchestration")
        self.assertIn("body_text_orchestration", result.classification_signals)

    # ------------------------------------------------------------------
    # 4. Body text leaf signal
    # ------------------------------------------------------------------
    def test_body_text_leaf_signal(self) -> None:
        skill = _make_skill(
            "commercial-legal:sub",
            "commercial-legal/skills/parent/sub/SKILL.md",
            body="> **迁移说明**：本子技能包含原 parent/SKILL.md 中的内容。",
            depth=1,
        )
        parent = _make_skill(
            "commercial-legal:parent",
            "commercial-legal/skills/parent/SKILL.md",
            body="编排入口",
            depth=0,
        )
        result = classify_skill(skill, [parent, skill])
        self.assertEqual(result.skill_type, "leaf")
        self.assertIn("body_text_leaf", result.classification_signals)

    # ------------------------------------------------------------------
    # 5. legal-skills flat always leaf
    # ------------------------------------------------------------------
    def test_legal_skills_flat_always_leaf(self) -> None:
        skill = _make_skill(
            "legal-court-sms",
            "skills/court-sms/SKILL.md",
            body="处理法院短信的完整流程。",
            depth=0,
            plugin=None,
            source_repo="legal-skills",
        )
        result = classify_skill(skill, [skill])
        self.assertEqual(result.skill_type, "leaf")
        self.assertIsNone(result.parent_skill)

    # ------------------------------------------------------------------
    # 6. Standalone skill no children
    # ------------------------------------------------------------------
    def test_standalone_skill_no_children(self) -> None:
        skill = _make_skill(
            "commercial-legal:standalone",
            "commercial-legal/skills/standalone/SKILL.md",
            body="A standalone skill with no children.",
            depth=0,
        )
        result = classify_skill(skill, [skill])
        self.assertEqual(result.skill_type, "leaf")
        self.assertIsNone(result.parent_skill)

    # ------------------------------------------------------------------
    # 7. plugin.json signal
    # ------------------------------------------------------------------
    def test_plugin_json_signal(self) -> None:
        parent = _make_skill(
            "commercial-legal:contract-review",
            "commercial-legal/skills/contract-review/SKILL.md",
            body="",
            depth=0,
        )
        child = _make_skill(
            "commercial-legal:risk-identification",
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            body="",
            depth=1,
        )
        plugin_json_skills = {
            "commercial-legal": [
                {"name": "contract-review", "path": "skills/contract-review/SKILL.md"},
                {
                    "name": "risk-identification",
                    "path": "skills/contract-review/risk-identification/SKILL.md",
                },
            ]
        }
        result = classify_skill(parent, [parent, child], plugin_json_skills)
        self.assertEqual(result.skill_type, "orchestration")
        self.assertIn("plugin_json_parent", result.classification_signals)

    # ------------------------------------------------------------------
    # 8. plugin.json missing — no crash
    # ------------------------------------------------------------------
    def test_plugin_json_missing(self) -> None:
        parent = _make_skill(
            "commercial-legal:contract-review",
            "commercial-legal/skills/contract-review/SKILL.md",
            body="编排入口",
            depth=0,
        )
        child = _make_skill(
            "commercial-legal:risk-identification",
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            body="迁移说明",
            depth=1,
        )
        # plugin_json_skills=None — should not crash, still classifies via dir+body
        result = classify_skill(parent, [parent, child], plugin_json_skills=None)
        self.assertEqual(result.skill_type, "orchestration")
        result_child = classify_skill(child, [parent, child], plugin_json_skills=None)
        self.assertEqual(result_child.skill_type, "leaf")

    # ------------------------------------------------------------------
    # 9. classify_all_skills
    # ------------------------------------------------------------------
    def test_classify_all_skills(self) -> None:
        p1 = _make_skill(
            "commercial-legal:contract-review",
            "commercial-legal/skills/contract-review/SKILL.md",
            body="编排入口",
            depth=0,
        )
        c1 = _make_skill(
            "commercial-legal:risk-identification",
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            body="迁移说明",
            depth=1,
        )
        p2 = _make_skill(
            "commercial-legal:cold-start-interview",
            "commercial-legal/skills/cold-start-interview/SKILL.md",
            body="编排入口",
            depth=0,
        )
        c2 = _make_skill(
            "commercial-legal:identity-team",
            "commercial-legal/skills/cold-start-interview/identity-team/SKILL.md",
            body="迁移说明",
            depth=1,
        )
        flat = _make_skill(
            "commercial-legal:standalone",
            "commercial-legal/skills/standalone/SKILL.md",
            body="standalone",
            depth=0,
        )
        all_skills = [p1, c1, p2, c2, flat]
        results = classify_all_skills(all_skills)
        self.assertEqual(len(results), 5)
        self.assertEqual(results["commercial-legal:contract-review"].skill_type, "orchestration")
        self.assertEqual(results["commercial-legal:cold-start-interview"].skill_type, "orchestration")
        self.assertGreater(len(results["commercial-legal:contract-review"].child_skills), 0)
        self.assertEqual(results["commercial-legal:risk-identification"].skill_type, "leaf")
        self.assertEqual(results["commercial-legal:standalone"].skill_type, "leaf")

    # ------------------------------------------------------------------
    # 10. Name collision (ai-governance)
    # ------------------------------------------------------------------
    def test_name_collision_ai_governance(self) -> None:
        p1 = _make_skill(
            "ai-governance:algorithm-filing",
            "ai-governance/skills/algorithm-filing/SKILL.md",
            body="编排入口",
            depth=0,
            plugin="ai-governance",
        )
        c1 = _make_skill(
            "ai-governance:filing-material-preparation",
            "ai-governance/skills/algorithm-filing/filing-material-preparation/SKILL.md",
            body="迁移说明",
            depth=1,
            plugin="ai-governance",
        )
        p2 = _make_skill(
            "ai-governance:deep-synthesis-filing",
            "ai-governance/skills/deep-synthesis-filing/SKILL.md",
            body="编排入口",
            depth=0,
            plugin="ai-governance",
        )
        c2 = _make_skill(
            "ai-governance:filing-material-preparation-dup",
            "ai-governance/skills/deep-synthesis-filing/filing-material-preparation/SKILL.md",
            body="迁移说明",
            depth=1,
            plugin="ai-governance",
        )
        all_skills = [p1, c1, p2, c2]
        r1 = classify_skill(c1, all_skills)
        r2 = classify_skill(c2, all_skills)
        self.assertEqual(r1.skill_type, "leaf")
        self.assertEqual(r2.skill_type, "leaf")
        self.assertEqual(r1.parent_skill, "ai-governance:algorithm-filing")
        self.assertEqual(r2.parent_skill, "ai-governance:deep-synthesis-filing")
        self.assertNotEqual(r1.parent_skill, r2.parent_skill)

    # ------------------------------------------------------------------
    # 11. Shared skill classification
    # ------------------------------------------------------------------
    def test_shared_skill_classification(self) -> None:
        skill = _make_skill(
            "shared:cn-law-research-gate",
            "shared/research-gate/SKILL.md",
            body="研究闸门 skill",
            depth=0,
            plugin="shared",
        )
        result = classify_skill(skill, [skill])
        self.assertEqual(result.skill_type, "leaf")
        self.assertIsNone(result.parent_skill)

    # ------------------------------------------------------------------
    # 12. Orchestration takes precedence
    # ------------------------------------------------------------------
    def test_orchestration_takes_precedence(self) -> None:
        # A skill that is nested (depth=1, has a parent) AND has children.
        grandparent = _make_skill(
            "commercial-legal:grand",
            "commercial-legal/skills/grand/SKILL.md",
            body="编排入口",
            depth=0,
        )
        mid = _make_skill(
            "commercial-legal:mid",
            "commercial-legal/skills/grand/mid/SKILL.md",
            body="编排入口",
            depth=1,
        )
        leaf = _make_skill(
            "commercial-legal:leaf",
            "commercial-legal/skills/grand/mid/leaf/SKILL.md",
            body="迁移说明",
            depth=2,
        )
        all_skills = [grandparent, mid, leaf]
        result = classify_skill(mid, all_skills)
        # mid has children → orchestration takes precedence over being nested.
        self.assertEqual(result.skill_type, "orchestration")
        self.assertIn("commercial-legal:leaf", result.child_skills)
        # mid still has a parent (it is nested).
        self.assertEqual(result.parent_skill, "commercial-legal:grand")


if __name__ == "__main__":
    unittest.main()
