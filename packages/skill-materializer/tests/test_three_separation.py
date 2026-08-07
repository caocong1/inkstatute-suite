"""Tests for three-separation routing manifest producer."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.three_separation import produce_routing_manifest


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_fixture_index(base_dir: Path) -> Path:
    """Build a minimal skill-index.json with metadata and body-like fields."""
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # Create minimal source dirs so source_path resolution works
    (acl / "commercial-legal" / "skills" / "contract-review").mkdir(parents=True)
    (ls / "skills" / "de-ai-polish").mkdir(parents=True)

    skills = [
        {
            "skill_id": "commercial-legal:contract-review",
            "name": "contract-review",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
            "skill_type": "orchestration",
            "parent_skill": None,
            "child_skills": ["risk-identification"],
            "description": "Review a contract for risks.",
            "frontmatter": {"name": "contract-review", "description": "Review a contract for risks."},
            "token_estimate": 500,
            "declared_gates": ["research-gate", "ask-user-enforcement"],
            "referenced_resources": ["shared/references/contract-template.md"],
            "practice_profile_dependency": True,
            "host_assumptions": ["/commercial-legal:risk-identification"],
            "required_scripts": [],
            "license": None,
            "version": "1.0.0",
            "content_hash": "abc123",
            "has_local_modification": False,
            "warnings": [],
        },
        {
            "skill_id": "legal-de-ai-polish",
            "name": "de-ai-polish",
            "source_repo": "legal-skills",
            "plugin": None,
            "relative_path": "skills/de-ai-polish/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": None,
            "child_skills": [],
            "description": "De-AI polish for legal text.",
            "frontmatter": {"name": "de-ai-polish", "description": "De-AI polish for legal text."},
            "token_estimate": 800,
            "declared_gates": ["de-ai-polish"],
            "referenced_resources": [],
            "practice_profile_dependency": False,
            "host_assumptions": [],
            "required_scripts": ["scripts/polish.py"],
            "license": "MIT",
            "version": "2.0.0",
            "content_hash": "def456",
            "has_local_modification": False,
            "warnings": [],
        },
    ]

    repos_meta = {
        "ai-for-china-legal": {"path": str(acl), "commit": None, "skill_count": 1},
        "legal-skills": {"path": str(ls), "commit": None, "skill_count": 1},
    }

    index_data = {
        "generated_at": "2026-08-09T00:00:00Z",
        "scanner_version": "1.0.0",
        "repos": repos_meta,
        "skills": skills,
        "merge_report": {},
        "warnings": [],
    }

    index_path = base_dir / "skill-index.json"
    index_path.write_text(
        json.dumps(index_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return index_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThreeSeparation(unittest.TestCase):
    """Tests for the three-separation routing manifest producer."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index(self.base_dir)
        self.output_path = self.base_dir / "routing-manifest.json"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_produces_json_file(self) -> None:
        """produce_routing_manifest writes a JSON file."""
        produce_routing_manifest(self.index_path, self.output_path)
        self.assertTrue(self.output_path.exists())
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_contains_required_fields(self) -> None:
        """Each record contains required metadata fields."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        skills = data["skills"]
        self.assertEqual(len(skills), 2)

        required_fields = {
            "skill_id", "name", "description", "token_estimate",
            "declared_gates", "host_assumptions", "required_scripts",
            "source_path", "skill_type", "parent_skill",
        }
        for record in skills:
            for field_name in required_fields:
                self.assertIn(
                    field_name, record,
                    f"Missing field '{field_name}' in routing record",
                )

    def test_no_body_content_fields(self) -> None:
        """No record contains body text, raw_text, frontmatter, or content."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))

        excluded_fields = {"frontmatter", "raw_text", "body", "content", "content_hash"}
        for record in data["skills"]:
            for excluded in excluded_fields:
                self.assertNotIn(
                    excluded, record,
                    f"Excluded field '{excluded}' found in routing record",
                )

    def test_no_body_markers_in_manifest(self) -> None:
        """Routing manifest does not contain body content markers.

        Grep for common markdown body markers (##, | , **) in the manifest
        JSON text. The description field may contain short text but should
        not contain markdown headers or table rows.
        """
        produce_routing_manifest(self.index_path, self.output_path)
        manifest_text = self.output_path.read_text(encoding="utf-8")

        # Check for markdown header patterns (## at start of line)
        header_matches = re.findall(r"^##\s", manifest_text, re.MULTILINE)
        self.assertEqual(
            len(header_matches), 0,
            f"Found {len(header_matches)} markdown headers in routing manifest",
        )

        # Check for table row patterns (| text |)
        table_matches = re.findall(r"\|[^|]+\|[^|]+\|", manifest_text)
        self.assertEqual(
            len(table_matches), 0,
            f"Found {len(table_matches)} table rows in routing manifest",
        )

    def test_source_path_is_absolute(self) -> None:
        """The source_path field is the absolute path to the SKILL.md."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))

        for record in data["skills"]:
            source_path = record["source_path"]
            self.assertTrue(
                source_path.startswith("/"),
                f"source_path is not absolute: {source_path}",
            )
            self.assertTrue(
                source_path.endswith("SKILL.md"),
                f"source_path does not end with SKILL.md: {source_path}",
            )

    def test_manifest_has_metadata(self) -> None:
        """The manifest has top-level metadata fields."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["manifest_type"], "routing")
        self.assertIn("version", data)
        self.assertIn("generated_at", data)
        self.assertEqual(data["skill_count"], 2)

    def test_skill_count_matches(self) -> None:
        """skill_count matches the number of skill records."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["skill_count"], len(data["skills"]))

    def test_lists_are_copied_not_referenced(self) -> None:
        """List fields in routing records are copies, not references to index."""
        produce_routing_manifest(self.index_path, self.output_path)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))

        # Modify a list in the routing manifest and verify the index is unchanged
        index_data = json.loads(self.index_path.read_text(encoding="utf-8"))
        original_gates = index_data["skills"][0]["declared_gates"]

        routing_gates = data["skills"][0]["declared_gates"]
        routing_gates.append("new-gate")

        # Index should be unchanged
        self.assertEqual(index_data["skills"][0]["declared_gates"], original_gates)


if __name__ == "__main__":
    unittest.main()
