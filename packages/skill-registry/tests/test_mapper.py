"""Unit tests for the manifest-to-descriptor mapper and index-to-descriptor mapper."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from platform_contract import NeutralSkillDescriptor

from inkstatute_skill_registry.mapper import (
    index_to_descriptors,
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
            "demo_non_legal",
            {
                "name": "lesson_qa",
                "description": "Answer student questions about lesson material with citations.",
                "intent": "factual_qa",
                "required_tools": ["curriculum_db"],
                "risk_level": "low",
            },
        )
        self.assertIsInstance(descriptor, NeutralSkillDescriptor)
        self.assertEqual(descriptor.name, "lesson_qa")
        self.assertEqual(descriptor.description, "Answer student questions about lesson material with citations.")
        self.assertEqual(descriptor.required_tool_refs, ["curriculum_db"])
        self.assertEqual(descriptor.metadata["intent"], "factual_qa")
        self.assertEqual(descriptor.metadata["risk_level"], "low")
        self.assertEqual(descriptor.metadata["solution_id"], "demo_non_legal")

    def test_skill_id_includes_solution_id(self) -> None:
        """``skill_id`` must be ``{solution_id}/{name}``."""
        descriptor = manifest_skill_to_descriptor(
            "demo_non_legal",
            {"name": "lesson_qa", "description": "test", "intent": "factual_qa", "risk_level": "low"},
        )
        self.assertEqual(descriptor.skill_id, "demo_non_legal/lesson_qa")

    def test_load_skills_from_manifests_loads_all_packs(self) -> None:
        """Loading demo_non_legal manifest produces 4 descriptors.

        After SKILL-09, lawfirm manifest no longer has a 'skills' key, so
        only demo_non_legal contributes skills (4).  Loading both manifests
        still produces 4 (lawfirm contributes 0).
        """
        descriptors = load_skills_from_manifests([LAWFIRM_MANIFEST, DEMO_MANIFEST])
        self.assertEqual(len(descriptors), 4)
        # All descriptors come from demo_non_legal
        for d in descriptors:
            self.assertTrue(d.skill_id.startswith("demo_non_legal/"))

    def test_descriptor_input_output_schema_refs_are_none(self) -> None:
        """``input_schema_ref`` and ``output_schema_ref`` must be ``None``."""
        descriptor = manifest_skill_to_descriptor(
            "demo_non_legal",
            {"name": "lesson_qa", "description": "test", "intent": "factual_qa", "risk_level": "low"},
        )
        self.assertIsNone(descriptor.input_schema_ref)
        self.assertIsNone(descriptor.output_schema_ref)


def _make_skill_index_json(records: list[dict]) -> str:
    """Build a minimal skill-index.json string with the given skill records."""
    return json.dumps({
        "generated_at": "2026-08-09T12:00:00Z",
        "scanner_version": "1.0.0",
        "repos": {},
        "skills": records,
        "merge_report": {},
        "warnings": [],
    }, indent=2)


_SAMPLE_RECORD = {
    "skill_id": "ai-for-china-legal:commercial-legal:contract-review",
    "name": "contract-review",
    "source_repo": "ai-for-china-legal",
    "plugin": "commercial-legal",
    "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
    "skill_type": "orchestration",
    "parent_skill": None,
    "child_skills": ["risk-identification"],
    "description": "Review commercial contracts for risks.",
    "frontmatter": {"name": "contract-review", "description": "Review commercial contracts for risks."},
    "token_estimate": 8500,
    "declared_gates": ["research-gate", "ask-user-enforcement"],
    "referenced_resources": ["shared/legal-db"],
    "practice_profile_dependency": True,
    "host_assumptions": ["/commercial-legal:risk-identification"],
    "required_scripts": ["scripts/extract_clauses.py"],
    "license": "MIT",
    "version": "1.0.0",
    "content_hash": "abc123",
    "has_local_modification": False,
    "warnings": [],
}


class IndexToDescriptorsTests(unittest.TestCase):
    """Tests for ``index_to_descriptors`` (Phase 97 skill-index consumption)."""

    def test_reads_json_and_returns_descriptors(self) -> None:
        """``index_to_descriptors`` reads a JSON file and returns descriptors."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([_SAMPLE_RECORD]))
            descriptors = index_to_descriptors(idx_path)
        self.assertEqual(len(descriptors), 1)
        self.assertIsInstance(descriptors[0], NeutralSkillDescriptor)

    def test_field_mapping_skill_id_name_description(self) -> None:
        """Core fields map correctly: skill_id, name, description."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([_SAMPLE_RECORD]))
            descriptors = index_to_descriptors(idx_path)
        d = descriptors[0]
        self.assertEqual(d.skill_id, "ai-for-china-legal:commercial-legal:contract-review")
        self.assertEqual(d.name, "contract-review")
        self.assertEqual(d.description, "Review commercial contracts for risks.")

    def test_required_scripts_maps_to_required_tool_refs(self) -> None:
        """``required_scripts`` maps to ``required_tool_refs``."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([_SAMPLE_RECORD]))
            descriptors = index_to_descriptors(idx_path)
        d = descriptors[0]
        self.assertEqual(d.required_tool_refs, ["scripts/extract_clauses.py"])

    def test_metadata_includes_all_required_fields(self) -> None:
        """Metadata dict includes token_estimate, declared_gates, host_assumptions,
        skill_type, parent_skill, source_repo, plugin."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([_SAMPLE_RECORD]))
            descriptors = index_to_descriptors(idx_path)
        meta = descriptors[0].metadata
        self.assertEqual(meta["token_estimate"], 8500)
        self.assertEqual(meta["declared_gates"], ["research-gate", "ask-user-enforcement"])
        self.assertEqual(meta["host_assumptions"], ["/commercial-legal:risk-identification"])
        self.assertEqual(meta["skill_type"], "orchestration")
        self.assertIsNone(meta["parent_skill"])
        self.assertEqual(meta["source_repo"], "ai-for-china-legal")
        self.assertEqual(meta["plugin"], "commercial-legal")

    def test_no_body_text_or_frontmatter_in_descriptor(self) -> None:
        """Descriptor does NOT contain frontmatter raw content or body text."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([_SAMPLE_RECORD]))
            descriptors = index_to_descriptors(idx_path)
        d = descriptors[0]
        # No frontmatter, raw_text, content, or body fields in metadata
        self.assertNotIn("frontmatter", d.metadata)
        self.assertNotIn("raw_text", d.metadata)
        self.assertNotIn("content", d.metadata)
        self.assertNotIn("body", d.metadata)
        # input_schema_ref and output_schema_ref are None
        self.assertIsNone(d.input_schema_ref)
        self.assertIsNone(d.output_schema_ref)

    def test_handles_empty_index(self) -> None:
        """Empty index (skills=[]) returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json([]))
            descriptors = index_to_descriptors(idx_path)
        self.assertEqual(descriptors, [])

    def test_handles_missing_skills_key(self) -> None:
        """Missing 'skills' key returns empty list (with warning)."""
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(json.dumps({
                "generated_at": "2026-08-09T12:00:00Z",
                "scanner_version": "1.0.0",
                "repos": {},
                "merge_report": {},
                "warnings": [],
            }))
            descriptors = index_to_descriptors(idx_path)
        self.assertEqual(descriptors, [])

    def test_multiple_records_all_converted(self) -> None:
        """Multiple records are all converted."""
        records = [
            {**_SAMPLE_RECORD, "skill_id": "repo:plugin:skill-1", "name": "skill-1"},
            {**_SAMPLE_RECORD, "skill_id": "repo:plugin:skill-2", "name": "skill-2"},
            {**_SAMPLE_RECORD, "skill_id": "repo:plugin:skill-3", "name": "skill-3"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            idx_path = Path(tmp) / "skill-index.json"
            idx_path.write_text(_make_skill_index_json(records))
            descriptors = index_to_descriptors(idx_path)
        self.assertEqual(len(descriptors), 3)
        ids = {d.skill_id for d in descriptors}
        self.assertEqual(ids, {"repo:plugin:skill-1", "repo:plugin:skill-2", "repo:plugin:skill-3"})

    def test_existing_manifest_functions_unchanged(self) -> None:
        """``manifest_skill_to_descriptor`` and ``load_skills_from_manifests``
        remain unchanged (backward compat)."""
        descriptor = manifest_skill_to_descriptor(
            "demo_non_legal",
            {"name": "lesson_qa", "description": "test", "intent": "factual_qa", "risk_level": "low"},
        )
        self.assertEqual(descriptor.skill_id, "demo_non_legal/lesson_qa")
        self.assertEqual(descriptor.metadata["intent"], "factual_qa")


if __name__ == "__main__":
    unittest.main()
