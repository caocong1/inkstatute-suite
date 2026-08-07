"""Tests for three-separation enforcement in the body injection path.

Verifies that the metadata/body/tools separation principle is enforced:
- Routing manifest (produced by produce_routing_manifest) contains only metadata
- Skill bodies are read on-demand from source repos, not from routing artifacts
- Tool dependencies are listed in the index but not resolved by the injector
- The full flow: index → routing manifest (metadata only) → on-demand body read
  (from source) → budget-trimmed injection
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.body_injector import (
    SkillBodyInjectionResult,
    SkillBodyInjector,
    read_skill_body,
)
from inkstatute_skill_materializer.three_separation import produce_routing_manifest

from .fixtures.body_injector_fixtures import build_medium_skill


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _build_full_fixture(base_dir: Path) -> tuple[Path, Path, Path]:
    """Build a fixture with index, source SKILL.md, and routing manifest.

    Returns:
        A tuple of (index_path, skill_md_path, routing_manifest_path).
    """
    # Create source repo structure
    repo_dir = base_dir / "test-repo"
    skill_dir = repo_dir / "plugin" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)

    # Write a SKILL.md with realistic content
    skill_text = build_medium_skill()
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_text, encoding="utf-8")

    # Build index
    skills = [
        {
            "skill_id": "test-repo:test-skill",
            "name": "test-skill",
            "source_repo": "test-repo",
            "plugin": "plugin",
            "relative_path": "plugin/skills/test-skill/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": None,
            "child_skills": [],
            "description": "A test skill for three-separation verification.",
            "frontmatter": {"name": "test-skill", "description": "A test skill."},
            "token_estimate": 5000,
            "declared_gates": ["research-gate"],
            "referenced_resources": [],
            "practice_profile_dependency": False,
            "host_assumptions": ["/plugin:test-skill"],
            "required_scripts": ["scripts/analyze.py", "scripts/format.py"],
            "license": "MIT",
            "version": "1.0.0",
            "content_hash": "abc123",
            "has_local_modification": False,
            "warnings": [],
        },
    ]

    repos_meta = {
        "test-repo": {"path": str(repo_dir), "commit": None, "skill_count": 1},
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

    # Produce routing manifest
    routing_manifest_path = base_dir / "routing-manifest.json"
    produce_routing_manifest(index_path, routing_manifest_path)

    return index_path, skill_md_path, routing_manifest_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThreeSeparationBodyPath(unittest.TestCase):
    """Verify three-separation principle in the body injection path."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path, self.skill_md_path, self.routing_manifest_path = (
            _build_full_fixture(self.base_dir)
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # -----------------------------------------------------------------------
    # Test 1: Routing manifest does NOT contain skill body text
    # -----------------------------------------------------------------------

    def test_routing_manifest_has_no_body_text(self) -> None:
        """Routing manifest does NOT contain skill body text."""
        manifest_text = self.routing_manifest_path.read_text(encoding="utf-8")
        manifest_data = json.loads(manifest_text)

        # The manifest should not have body, content, raw_text, or frontmatter fields
        excluded_fields = {"frontmatter", "raw_text", "body", "content", "content_hash"}
        for record in manifest_data["skills"]:
            for field in excluded_fields:
                self.assertNotIn(
                    field, record,
                    f"Excluded field '{field}' found in routing manifest record",
                )

    def test_routing_manifest_does_not_contain_skill_body_content(self) -> None:
        """Routing manifest text does not contain actual skill body content."""
        manifest_text = self.routing_manifest_path.read_text(encoding="utf-8")
        skill_body = self.skill_md_path.read_text(encoding="utf-8")

        # Extract a unique substring from the skill body that would only
        # appear if the body was copied into the manifest
        # Use the first ## section header content as a probe
        body_probe = "Core Instructions"
        # The manifest description is "A test skill for three-separation verification."
        # which is different from the body content
        # Check that the body's section content is NOT in the manifest
        # (the description field is metadata, not body content)
        manifest_data = json.loads(manifest_text)
        for record in manifest_data["skills"]:
            # The description in the manifest comes from the index, not the body
            # It should be the short frontmatter description, not the body text
            self.assertNotIn("## Core Instructions", json.dumps(record))
            self.assertNotIn("### Step 1: Input Analysis", json.dumps(record))

    # -----------------------------------------------------------------------
    # Test 2: read_skill_body reads from source_path, NOT from routing manifest
    # -----------------------------------------------------------------------

    def test_read_skill_body_reads_from_source_path(self) -> None:
        """read_skill_body() reads from the source_path field in the index,
        NOT from the routing manifest."""
        # Read the skill body via the API
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=100000,
        )

        # The injected text should contain the actual SKILL.md content
        original_body = self.skill_md_path.read_text(encoding="utf-8")
        # With a large budget, no trimming occurs, so injected == original
        self.assertEqual(result.injected_text, original_body)

    def test_read_skill_body_does_not_read_from_manifest(self) -> None:
        """read_skill_body() does not read from the routing manifest.

        Verify by checking that the routing manifest does not contain
        the body text that read_skill_body returns.
        """
        manifest_text = self.routing_manifest_path.read_text(encoding="utf-8")

        # Read the skill body
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=100000,
        )

        # The injected text should be the full SKILL.md body
        # The manifest should NOT contain this body
        # Check that a distinctive body section is in the result but not in the manifest
        self.assertIn("## Core Instructions", result.injected_text)
        self.assertNotIn("## Core Instructions", manifest_text)

    # -----------------------------------------------------------------------
    # Test 3: Body injector does NOT resolve tool dependencies
    # -----------------------------------------------------------------------

    def test_body_injector_does_not_resolve_tools(self) -> None:
        """The body injector does NOT resolve tool dependencies.

        It only handles body text — it does not look at required_scripts
        or attempt to load/resolve any scripts.
        """
        # The injector only takes text input — it has no tool resolution API
        body = self.skill_md_path.read_text(encoding="utf-8")
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)

        # The result contains only text fields — no tool-related fields
        self.assertIsInstance(result, SkillBodyInjectionResult)
        self.assertFalse(hasattr(result, "resolved_tools"))
        self.assertFalse(hasattr(result, "tool_dependencies"))
        self.assertFalse(hasattr(result, "required_scripts"))

    def test_read_skill_body_does_not_resolve_tools(self) -> None:
        """read_skill_body() does not resolve tool dependencies.

        The function reads the body and applies trimming — it does not
        touch the required_scripts field or attempt to load scripts.
        """
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=100000,
        )

        # The result is purely a SkillBodyInjectionResult — no tool info
        self.assertIsInstance(result, SkillBodyInjectionResult)
        # No tool-related attributes
        self.assertFalse(hasattr(result, "resolved_tools"))
        self.assertFalse(hasattr(result, "tool_dependencies"))

    # -----------------------------------------------------------------------
    # Test 4: required_scripts in routing manifest is metadata-only
    # -----------------------------------------------------------------------

    def test_required_scripts_is_metadata_only(self) -> None:
        """required_scripts in the routing manifest is metadata-only
        (a list of script names), not the script contents."""
        manifest_data = json.loads(
            self.routing_manifest_path.read_text(encoding="utf-8")
        )

        for record in manifest_data["skills"]:
            if "required_scripts" in record:
                scripts = record["required_scripts"]
                # It should be a list of strings (paths/names), not dict/file contents
                self.assertIsInstance(scripts, list)
                for script in scripts:
                    self.assertIsInstance(script, str)
                    # Script entries are paths/names, not file contents
                    # They should not contain Python code or multi-line content
                    self.assertNotIn("def ", script)
                    self.assertNotIn("import ", script)

    # -----------------------------------------------------------------------
    # Test 5: Full flow — index → routing manifest → on-demand body read → trim
    # -----------------------------------------------------------------------

    def test_full_flow_index_to_trimmed_injection(self) -> None:
        """Full flow: index → routing manifest (metadata only) →
        on-demand body read (from source) → budget-trimmed injection."""
        # Step 1: Routing manifest was already produced in setUp
        manifest_data = json.loads(
            self.routing_manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(manifest_data["manifest_type"], "routing")
        self.assertEqual(manifest_data["skill_count"], 1)

        # Step 2: Routing manifest contains source_path for on-demand reading
        record = manifest_data["skills"][0]
        self.assertIn("source_path", record)
        source_path = record["source_path"]
        self.assertTrue(source_path.endswith("SKILL.md"))
        self.assertTrue(Path(source_path).exists())

        # Step 3: On-demand body read from source path
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=2000,  # Strict budget to force trimming
        )

        # Step 4: Budget-trimmed injection
        self.assertIsInstance(result, SkillBodyInjectionResult)
        self.assertGreater(len(result.injected_text), 0)
        self.assertLessEqual(result.injected_token_estimate, 2000)

        # The trimmed result should still contain protected sections
        # (frontmatter + description + first section)
        self.assertIn("---", result.injected_text)
        self.assertIn("# Test Skill", result.injected_text)

    def test_full_flow_manifest_has_no_body_but_source_has_body(self) -> None:
        """The routing manifest has no body text, but the source SKILL.md
        (read on-demand) has the full body."""
        manifest_text = self.routing_manifest_path.read_text(encoding="utf-8")
        source_text = self.skill_md_path.read_text(encoding="utf-8")

        # Manifest should be much smaller than the source (metadata only)
        self.assertLess(len(manifest_text), len(source_text))

        # Manifest should not contain body section markers
        import re
        header_matches = re.findall(r"^##\s", manifest_text, re.MULTILINE)
        self.assertEqual(len(header_matches), 0)

        # Source should contain body section markers
        source_headers = re.findall(r"^##\s", source_text, re.MULTILINE)
        self.assertGreater(len(source_headers), 0)


if __name__ == "__main__":
    unittest.main()
