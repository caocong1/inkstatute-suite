"""Unit tests for the read-only SkillRegistry."""

from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract import NeutralSkillDescriptor

from inkstatute_skill_registry.mapper import load_skills_from_manifests
from inkstatute_skill_registry.registry import SkillRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWFIRM_MANIFEST = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"
DEMO_MANIFEST = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"

# Prefixes that indicate a mutating (write) method.
_WRITE_PREFIXES = ("add_", "create_", "update_", "delete_", "remove_", "put_", "post_")


def _build_registry() -> SkillRegistry:
    """Build a SkillRegistry loaded from both solution-pack manifests.

    After SKILL-09, lawfirm manifest no longer has a 'skills' key, so
    only demo_non_legal contributes skills (4).
    """
    skills = load_skills_from_manifests([LAWFIRM_MANIFEST, DEMO_MANIFEST])
    return SkillRegistry(skills)


class SkillRegistryListGetTests(unittest.TestCase):
    """Tests for ``list_skills`` and ``get_skill``."""

    def test_list_skills_returns_all_descriptors(self) -> None:
        """``list_skills()`` must return all 4 descriptors (demo_non_legal only)."""
        registry = _build_registry()
        skills = registry.list_skills()
        self.assertEqual(len(skills), 4)

    def test_get_skill_returns_descriptor_by_id(self) -> None:
        """``get_skill("demo_non_legal/lesson_qa")`` must return the correct descriptor."""
        registry = _build_registry()
        skill = registry.get_skill("demo_non_legal/lesson_qa")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "lesson_qa")

    def test_get_skill_returns_none_for_unknown_id(self) -> None:
        """``get_skill`` must return ``None`` for an unknown skill id."""
        registry = _build_registry()
        self.assertIsNone(registry.get_skill("unknown/skill"))


class SkillRegistrySearchTests(unittest.TestCase):
    """Tests for ``search`` with tag, category, and name_substring filters."""

    def test_search_by_tag_risk_level(self) -> None:
        """``search(tag="low")`` returns skills with ``risk_level == "low"``."""
        registry = _build_registry()
        results = registry.search(tag="low")
        names = {s.name for s in results}
        self.assertEqual(names, {"lesson_qa", "homework_review", "syllabus_lookup"})

    def test_search_by_category_intent(self) -> None:
        """``search(category="factual_qa")`` returns skills with ``intent == "factual_qa"``."""
        registry = _build_registry()
        results = registry.search(category="factual_qa")
        names = {s.name for s in results}
        self.assertEqual(names, {"lesson_qa"})

    def test_search_by_name_substring(self) -> None:
        """``search(name_substring="lesson")`` returns skills containing "lesson" in name."""
        registry = _build_registry()
        results = registry.search(name_substring="lesson")
        self.assertTrue(len(results) >= 1)
        for s in results:
            self.assertIn("lesson", s.name.lower())

    def test_search_with_no_filters_returns_all(self) -> None:
        """``search()`` with no filters must return all 4 skills."""
        registry = _build_registry()
        results = registry.search()
        self.assertEqual(len(results), 4)

    def test_search_with_multiple_filters(self) -> None:
        """``search(tag="medium", category="generation")`` applies AND logic."""
        registry = _build_registry()
        results = registry.search(tag="medium", category="generation")
        names = {s.name for s in results}
        self.assertEqual(names, {"quiz_generator"})


class SkillRegistryReadOnlyTests(unittest.TestCase):
    """Tests enforcing read-only behavior of the SkillRegistry."""

    def test_registry_is_read_only(self) -> None:
        """No non-dunder method on SkillRegistry may start with a write prefix."""
        mutating = [
            attr
            for attr in dir(SkillRegistry)
            if not attr.startswith("__")
            and any(attr.startswith(prefix) for prefix in _WRITE_PREFIXES)
        ]
        self.assertEqual(mutating, [], f"Found mutating methods: {mutating}")

    def test_registry_does_not_mutate_internal_list(self) -> None:
        """Modifying the list returned by ``list_skills()`` must not affect the registry."""
        registry = _build_registry()
        first = registry.list_skills()
        first.append(
            NeutralSkillDescriptor(skill_id="fake/skill", name="fake")
        )
        second = registry.list_skills()
        self.assertEqual(len(second), 4)


if __name__ == "__main__":
    unittest.main()
