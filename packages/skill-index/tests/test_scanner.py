"""Unit tests for directory walking and SKILL.md discovery.

Creates temporary directory structures mimicking the real repos and verifies
the scanner discovers SKILL.md files correctly with proper exclusions,
skill IDs, depth, and graceful degradation.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.scanner import (
    EXCLUDED_DIRS,
    ScannedSkill,
    ScanResult,
    _compute_depth,
    _compute_skill_id,
    _determine_plugin,
    scan_repo,
)


class TestScanner(unittest.TestCase):
    """Verify directory walking, SKILL.md discovery, and exclusions."""

    def setUp(self) -> None:
        self._tmpdirs: list[Path] = []

    def tearDown(self) -> None:
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_tmp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self._tmpdirs.append(d)
        return d

    def _write_skill(self, root: Path, rel_path: str, content: str) -> Path:
        """Write a SKILL.md at root / rel_path with content."""
        p = root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    # ------------------------------------------------------------------
    # Discovery + exclusions
    # ------------------------------------------------------------------

    def test_scan_discovers_skill_md_files(self) -> None:
        """Scanner discovers SKILL.md in a plugin/skills/ structure."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "commercial-legal/skills/contract-review/SKILL.md",
            "---\nname: contract-review\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)
        skill = result.skills[0]
        self.assertEqual(skill.skill_id, "commercial-legal:contract-review")
        self.assertEqual(skill.name, "contract-review")
        self.assertEqual(skill.relative_path, "commercial-legal/skills/contract-review/SKILL.md")

    def test_scan_excludes_qwen_dir(self) -> None:
        """Scanner excludes .qwen/ directory."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "plugin/skills/real/SKILL.md",
            "---\nname: real\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            ".qwen/skills/fake/SKILL.md",
            "---\nname: fake\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)
        self.assertEqual(result.skills[0].name, "real")

    def test_scan_excludes_node_modules(self) -> None:
        """Scanner excludes node_modules/ directory."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/real/SKILL.md",
            "---\nname: real\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            "node_modules/pkg/SKILL.md",
            "---\nname: pkg\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)

    def test_scan_excludes_git_dir(self) -> None:
        """Scanner excludes .git/ directory."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/real/SKILL.md",
            "---\nname: real\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            ".git/SKILL.md",
            "---\nname: git\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)

    def test_scan_excludes_claude_plugin_dir(self) -> None:
        """Scanner excludes .claude-plugin/ directory."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/real/SKILL.md",
            "---\nname: real\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            ".claude-plugin/SKILL.md",
            "---\nname: plugin-meta\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)

    # ------------------------------------------------------------------
    # legal-skills flat structure
    # ------------------------------------------------------------------

    def test_scan_legal_skills_flat_structure(self) -> None:
        """legal-skills flat structure: skills/<name>/SKILL.md, legal- prefix."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/court-sms/SKILL.md",
            "---\nname: court-sms\nversion: \"1.5.0\"\nlicense: MIT\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            "skills/de-ai-polish/SKILL.md",
            "---\nname: de-ai-polish\nversion: \"1.0.0\"\nlicense: MIT\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "legal-skills")
        self.assertEqual(len(result.skills), 2)
        ids = {s.skill_id for s in result.skills}
        self.assertIn("legal-court-sms", ids)
        self.assertIn("legal-de-ai-polish", ids)

    # ------------------------------------------------------------------
    # ai-for-china-legal nested structure
    # ------------------------------------------------------------------

    def test_scan_ai_for_china_legal_nested(self) -> None:
        """ai-for-china-legal: orchestration (depth=0) + leaf (depth=1)."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "commercial-legal/skills/contract-review/SKILL.md",
            "---\nname: contract-review\ndescription: test\n---\n# Body\n",
        )
        self._write_skill(
            root,
            "commercial-legal/skills/contract-review/risk-identification/SKILL.md",
            "---\nname: risk-identification\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 2)
        by_name = {s.name: s for s in result.skills}
        self.assertEqual(by_name["contract-review"].depth, 0)
        self.assertEqual(by_name["risk-identification"].depth, 1)
        self.assertEqual(by_name["contract-review"].plugin, "commercial-legal")
        self.assertEqual(by_name["risk-identification"].plugin, "commercial-legal")

    # ------------------------------------------------------------------
    # shared skills
    # ------------------------------------------------------------------

    def test_scan_shared_skills(self) -> None:
        """shared/ skills get plugin='shared' and skill_id='shared:<name>'."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "shared/research-gate/SKILL.md",
            "---\nname: cn-law-research-gate\ndescription: test\n---\n# Body\n",
        )
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(len(result.skills), 1)
        skill = result.skills[0]
        self.assertEqual(skill.plugin, "shared")
        self.assertEqual(skill.skill_id, "shared:cn-law-research-gate")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_scan_empty_dir(self) -> None:
        """Empty directory → empty skills list, no crash."""
        root = self._make_tmp_dir()
        result = scan_repo(root, "ai-for-china-legal")
        self.assertEqual(result.skills, [])
        self.assertIsInstance(result, ScanResult)

    def test_scan_missing_frontmatter(self) -> None:
        """SKILL.md with no frontmatter → warning, name from directory."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/no-fm/SKILL.md",
            "# No frontmatter here\n\nJust body text.\n",
        )
        result = scan_repo(root, "legal-skills")
        self.assertEqual(len(result.skills), 1)
        skill = result.skills[0]
        self.assertIn("missing_frontmatter", skill.warnings)
        self.assertEqual(skill.name, "no-fm")

    def test_scan_malformed_frontmatter(self) -> None:
        """SKILL.md with broken YAML → warning, no crash."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/broken/SKILL.md",
            "---\nname: broken\n  bad: yaml: here: extra\n---\n# Body\n",
        )
        result = scan_repo(root, "legal-skills")
        self.assertEqual(len(result.skills), 1)
        skill = result.skills[0]
        self.assertIn("malformed_frontmatter", skill.warnings)

    def test_scan_token_estimate_populated(self) -> None:
        """Each ScannedSkill has token_estimate > 0 for non-empty files."""
        root = self._make_tmp_dir()
        self._write_skill(
            root,
            "skills/test-skill/SKILL.md",
            "---\nname: test-skill\ndescription: test\n---\n# Test Skill\n\nSome content here.\n",
        )
        result = scan_repo(root, "legal-skills")
        self.assertEqual(len(result.skills), 1)
        self.assertGreater(result.skills[0].token_estimate, 0)

    # ------------------------------------------------------------------
    # Helper function tests
    # ------------------------------------------------------------------

    def test_compute_depth_direct_child(self) -> None:
        """skills/<name>/SKILL.md → depth 0."""
        self.assertEqual(_compute_depth("plugin/skills/name/SKILL.md"), 0)

    def test_compute_depth_nested(self) -> None:
        """skills/<parent>/<child>/SKILL.md → depth 1."""
        self.assertEqual(_compute_depth("plugin/skills/parent/child/SKILL.md"), 1)

    def test_compute_depth_shared(self) -> None:
        """shared/research-gate/SKILL.md → depth 0 (no 'skills' component)."""
        self.assertEqual(_compute_depth("shared/research-gate/SKILL.md"), 0)

    def test_determine_plugin_ai_for_china_legal(self) -> None:
        """ai-for-china-legal: first path component is plugin name."""
        self.assertEqual(
            _determine_plugin("commercial-legal/skills/x/SKILL.md", "ai-for-china-legal"),
            "commercial-legal",
        )

    def test_determine_plugin_legal_skills(self) -> None:
        """legal-skills: plugin is always None."""
        self.assertIsNone(_determine_plugin("skills/x/SKILL.md", "legal-skills"))

    def test_compute_skill_id_patterns(self) -> None:
        """All three skill ID patterns: legal- prefix, plugin: prefix, shared: prefix."""
        self.assertEqual(
            _compute_skill_id("court-sms", None, "legal-skills"),
            "legal-court-sms",
        )
        self.assertEqual(
            _compute_skill_id("contract-review", "commercial-legal", "ai-for-china-legal"),
            "commercial-legal:contract-review",
        )
        self.assertEqual(
            _compute_skill_id("cn-law-research-gate", "shared", "ai-for-china-legal"),
            "shared:cn-law-research-gate",
        )


if __name__ == "__main__":
    unittest.main()
