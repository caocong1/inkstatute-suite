"""Unit tests for the manifest-to-descriptor mapper."""

from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract import NeutralSkillDescriptor

from inkstatute_skill_registry.mapper import (
    load_skills_from_manifests,
    manifest_skill_to_descriptor,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWFIRM_MANIFEST = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"
DEMO_MANIFEST = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"


class ManifestSkillToDescriptorTests(unittest.TestCase):
    """Tests for ``manifest_skill_to_descriptor``."""

    def test_manifest_skill_to_descriptor_maps_fields(self) -> None:
        """Verify all manifest fields map to the correct descriptor fields."""
        descriptor = manifest_skill_to_descriptor(
            "lawfirm",
            {
                "name": "case_qa",
                "description": "Answer factual legal questions with citations.",
                "intent": "factual_qa",
                "required_tools": ["law_search"],
                "risk_level": "medium",
            },
        )
        self.assertIsInstance(descriptor, NeutralSkillDescriptor)
        self.assertEqual(descriptor.name, "case_qa")
        self.assertEqual(descriptor.description, "Answer factual legal questions with citations.")
        self.assertEqual(descriptor.required_tool_refs, ["law_search"])
        self.assertEqual(descriptor.metadata["intent"], "factual_qa")
        self.assertEqual(descriptor.metadata["risk_level"], "medium")
        self.assertEqual(descriptor.metadata["solution_id"], "lawfirm")

    def test_skill_id_includes_solution_id(self) -> None:
        """``skill_id`` must be ``{solution_id}/{name}``."""
        descriptor = manifest_skill_to_descriptor(
            "lawfirm",
            {"name": "case_qa", "description": "test", "intent": "factual_qa", "risk_level": "medium"},
        )
        self.assertEqual(descriptor.skill_id, "lawfirm/case_qa")

    def test_load_skills_from_manifests_loads_all_packs(self) -> None:
        """Loading both manifests must produce 8 descriptors (4 + 4)."""
        descriptors = load_skills_from_manifests([LAWFIRM_MANIFEST, DEMO_MANIFEST])
        self.assertEqual(len(descriptors), 8)

    def test_descriptor_input_output_schema_refs_are_none(self) -> None:
        """``input_schema_ref`` and ``output_schema_ref`` must be ``None``."""
        descriptor = manifest_skill_to_descriptor(
            "lawfirm",
            {"name": "case_qa", "description": "test", "intent": "factual_qa", "risk_level": "medium"},
        )
        self.assertIsNone(descriptor.input_schema_ref)
        self.assertIsNone(descriptor.output_schema_ref)


if __name__ == "__main__":
    unittest.main()
