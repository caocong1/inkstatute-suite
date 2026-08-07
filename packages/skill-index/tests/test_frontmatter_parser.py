"""Unit tests for YAML frontmatter parsing and edge cases.

Tests cover both ai-for-china-legal (minimal) and legal-skills (rich) schemas,
graceful degradation for missing/malformed frontmatter, BOM handling, and
extract helper functions.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from inkstatute_skill_index.frontmatter_parser import (
    FrontmatterResult,
    extract_description,
    extract_license,
    extract_name,
    extract_version,
    parse_frontmatter,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestFrontmatterParser(unittest.TestCase):
    """Verify YAML frontmatter parsing with graceful degradation."""

    def test_parse_standard_frontmatter(self) -> None:
        """Parse orchestration_entry.md fixture — name, body, no warnings."""
        text = (FIXTURES / "orchestration_entry.md").read_text(encoding="utf-8")
        result = parse_frontmatter(text)
        self.assertEqual(result.frontmatter["name"], "contract-review")
        self.assertTrue(result.body.lstrip().startswith("# 合同审查"))
        self.assertEqual(result.warnings, [])

    def test_parse_legal_skills_frontmatter(self) -> None:
        """Parse legal_skill.md fixture — rich schema with version, license, author."""
        text = (FIXTURES / "legal_skill.md").read_text(encoding="utf-8")
        result = parse_frontmatter(text)
        self.assertEqual(result.frontmatter["name"], "court-sms")
        self.assertEqual(result.frontmatter["version"], "1.5.0")
        self.assertEqual(result.frontmatter["license"], "MIT")
        self.assertIn("author", result.frontmatter)

    def test_parse_folded_scalar_description(self) -> None:
        """Folded scalar > produces a single string with newlines."""
        text = "---\nname: test\ndescription: >\n  multi\n  line\n---\nbody"
        result = parse_frontmatter(text)
        desc = result.frontmatter["description"]
        self.assertIsInstance(desc, str)
        self.assertIn("multi", desc)
        self.assertIn("line", desc)

    def test_missing_frontmatter(self) -> None:
        """No frontmatter → empty dict, missing_frontmatter warning."""
        text = (FIXTURES / "no_frontmatter.md").read_text(encoding="utf-8")
        result = parse_frontmatter(text)
        self.assertEqual(result.frontmatter, {})
        self.assertIn("missing_frontmatter", result.warnings)

    def test_malformed_frontmatter(self) -> None:
        """Malformed YAML → malformed_frontmatter warning, no exception."""
        text = (FIXTURES / "malformed_frontmatter.md").read_text(encoding="utf-8")
        result = parse_frontmatter(text)
        self.assertIn("malformed_frontmatter", result.warnings)

    def test_empty_string(self) -> None:
        """Empty string → empty dict, missing_frontmatter warning."""
        result = parse_frontmatter("")
        self.assertEqual(result.frontmatter, {})
        self.assertIn("missing_frontmatter", result.warnings)

    def test_bom_handling(self) -> None:
        """BOM prefix is stripped before parsing."""
        text = "\ufeff---\nname: test\n---\nbody"
        result = parse_frontmatter(text)
        self.assertEqual(result.frontmatter["name"], "test")

    def test_extract_name_with_fallback(self) -> None:
        """Missing name falls back to provided fallback."""
        self.assertEqual(extract_name({}, fallback="dir-name"), "dir-name")

    def test_extract_name_from_frontmatter(self) -> None:
        """Name present in frontmatter takes priority over fallback."""
        self.assertEqual(extract_name({"name": "test"}, fallback="dir"), "test")

    def test_extract_version_quoted_string(self) -> None:
        """Version is returned as string (not float)."""
        self.assertEqual(extract_version({"version": "1.5.0"}), "1.5.0")

    def test_extract_version_missing(self) -> None:
        """Missing version returns None."""
        self.assertIsNone(extract_version({}))

    def test_extract_license_missing(self) -> None:
        """Missing license returns None."""
        self.assertIsNone(extract_license({}))

    def test_extract_description_missing(self) -> None:
        """Missing description returns None."""
        self.assertIsNone(extract_description({}))

    def test_nested_triple_dashes_in_body(self) -> None:
        """Body containing --- lines does not confuse the parser."""
        text = "---\nname: test\n---\n---\nsome content\n---"
        result = parse_frontmatter(text)
        self.assertEqual(result.frontmatter["name"], "test")
        self.assertIn("---", result.body)

    def test_frontmatter_with_argument_hint(self) -> None:
        """argument-hint field is preserved in parsed frontmatter."""
        text = (FIXTURES / "orchestration_entry.md").read_text(encoding="utf-8")
        result = parse_frontmatter(text)
        self.assertIn("argument-hint", result.frontmatter)


if __name__ == "__main__":
    unittest.main()
