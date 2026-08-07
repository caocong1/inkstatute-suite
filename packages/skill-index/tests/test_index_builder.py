"""Tests for the index builder — full index assembly + schema validation.

Tests cover:
- build_index with two repos
- serialize_index schema compliance
- write_index produces valid JSON
- IndexRecord has all required fields
- Plugin.json loading and commit detection helpers
- Previous index support for conflict classification
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.index_builder import (
    IndexRecord,
    SkillIndex,
    _get_repo_commit,
    _load_plugin_json_skills,
    build_index,
    serialize_index,
    write_index,
)


def _make_ai_for_china_legal_repo(root: Path) -> None:
    """Create a minimal ai-for-china-legal-like repo structure."""
    # Plugin with orchestration entry + leaf sub-skill
    plugin_dir = root / "commercial-legal"
    skills_dir = plugin_dir / "skills" / "contract-review"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: contract-review\ndescription: 合同审查编排入口\n"
        "argument-hint: \"[合同文件路径]\"\n---\n"
        "# 合同审查\n\n编排入口\n\n"
        "## 子技能编排顺序\n\n| 顺序 | 子技能 |\n| 1 | risk-identification |\n"
        "CLAUDE.md\n",
        encoding="utf-8",
    )
    leaf_dir = skills_dir / "risk-identification"
    leaf_dir.mkdir()
    (leaf_dir / "SKILL.md").write_text(
        "---\nname: risk-identification\ndescription: 风险识别\n---\n"
        "# 风险识别\n\n迁移说明\n",
        encoding="utf-8",
    )
    # plugin.json
    plugin_json_dir = plugin_dir / ".claude-plugin"
    plugin_json_dir.mkdir()
    (plugin_json_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "commercial-legal",
                "version": "0.3.0",
                "skills": [
                    {
                        "name": "contract-review",
                        "path": "skills/contract-review/SKILL.md",
                        "description": "编排入口",
                    },
                    {
                        "name": "risk-identification",
                        "path": "skills/contract-review/risk-identification/SKILL.md",
                        "description": "子技能",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _make_legal_skills_repo(root: Path) -> None:
    """Create a minimal legal-skills-like repo structure."""
    skills_dir = root / "skills" / "court-sms"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: court-sms\nversion: \"1.5.0\"\nlicense: MIT\n"
        "description: 法院短信处理\n---\n# Body\n",
        encoding="utf-8",
    )


class TestIndexBuilder(unittest.TestCase):
    """Full index assembly + schema validation tests."""

    def setUp(self) -> None:
        self._tmpdirs: list[Path] = []

    def tearDown(self) -> None:
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_tmp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self._tmpdirs.append(d)
        return d

    def _make_two_repos(self) -> tuple[Path, Path]:
        repo1 = self._make_tmp_dir()
        _make_ai_for_china_legal_repo(repo1)
        repo2 = self._make_tmp_dir()
        _make_legal_skills_repo(repo2)
        return repo1, repo2

    # ------------------------------------------------------------------
    # Test 1
    # ------------------------------------------------------------------

    def test_build_index_two_repos(self) -> None:
        """build_index with two repo configs produces a SkillIndex with skills from both repos."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        self.assertIsInstance(index, SkillIndex)
        self.assertGreaterEqual(len(index.skills), 3)  # 2 + 1
        repos = {s.source_repo for s in index.skills}
        self.assertEqual(repos, {"ai-for-china-legal", "legal-skills"})

    # ------------------------------------------------------------------
    # Test 2
    # ------------------------------------------------------------------

    def test_serialize_index_schema(self) -> None:
        """serialize_index returns dict with all top-level keys."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        d = serialize_index(index)
        self.assertIsInstance(d, dict)
        for key in ("generated_at", "scanner_version", "repos", "skills", "merge_report", "warnings"):
            self.assertIn(key, d, f"Missing top-level key: {key}")

    # ------------------------------------------------------------------
    # Test 3
    # ------------------------------------------------------------------

    def test_serialize_index_repos_metadata(self) -> None:
        """repos dict has entries for both repos with path, commit, skill_count."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        d = serialize_index(index)
        repos = d["repos"]
        self.assertIn("ai-for-china-legal", repos)
        self.assertIn("legal-skills", repos)
        for name, meta in repos.items():
            self.assertIn("path", meta)
            self.assertIn("commit", meta)
            self.assertIn("skill_count", meta)

    # ------------------------------------------------------------------
    # Test 4
    # ------------------------------------------------------------------

    def test_serialize_index_skills_array(self) -> None:
        """skills is a list of dicts, each with all IndexRecord fields."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        d = serialize_index(index)
        skills = d["skills"]
        self.assertIsInstance(skills, list)
        self.assertGreater(len(skills), 0)
        expected_fields = {
            "skill_id", "name", "source_repo", "plugin", "relative_path",
            "skill_type", "parent_skill", "child_skills", "description",
            "frontmatter", "token_estimate", "declared_gates",
            "referenced_resources", "practice_profile_dependency",
            "host_assumptions", "required_scripts", "license", "version",
            "content_hash", "has_local_modification", "warnings",
        }
        for skill_dict in skills:
            self.assertIsInstance(skill_dict, dict)
            self.assertEqual(set(skill_dict.keys()), expected_fields)

    # ------------------------------------------------------------------
    # Test 5
    # ------------------------------------------------------------------

    def test_serialize_index_merge_report(self) -> None:
        """merge_report has namespace_mappings and conflict_classification with 4 keys."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        d = serialize_index(index)
        mr = d["merge_report"]
        self.assertIn("namespace_mappings", mr)
        self.assertIn("conflict_classification", mr)
        cc = mr["conflict_classification"]
        for key in ("in-sync", "upstream-changed", "both-changed", "local-missing"):
            self.assertIn(key, cc)

    # ------------------------------------------------------------------
    # Test 6
    # ------------------------------------------------------------------

    def test_write_index_creates_valid_json(self) -> None:
        """write_index writes valid JSON with the correct schema."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"
        write_index(index, out_path)
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        for key in ("generated_at", "scanner_version", "repos", "skills", "merge_report", "warnings"):
            self.assertIn(key, data)

    # ------------------------------------------------------------------
    # Test 7
    # ------------------------------------------------------------------

    def test_write_index_outside_source_repos(self) -> None:
        """write_index writes to a temp dir, NOT inside the source repo dirs."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"
        write_index(index, out_path)
        # Assert the file is NOT inside either source repo
        out_resolved = out_path.resolve()
        self.assertFalse(
            str(out_resolved).startswith(str(repo1.resolve())),
            "Output file is inside source repo 1",
        )
        self.assertFalse(
            str(out_resolved).startswith(str(repo2.resolve())),
            "Output file is inside source repo 2",
        )

    # ------------------------------------------------------------------
    # Test 8
    # ------------------------------------------------------------------

    def test_index_record_has_all_fields(self) -> None:
        """Each IndexRecord in the index has all required fields."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        expected = {
            "skill_id", "name", "source_repo", "plugin", "relative_path",
            "skill_type", "parent_skill", "child_skills", "description",
            "frontmatter", "token_estimate", "declared_gates",
            "referenced_resources", "practice_profile_dependency",
            "host_assumptions", "required_scripts", "license", "version",
            "content_hash", "has_local_modification", "warnings",
        }
        for record in index.skills:
            actual = {f.name for f in __import__("dataclasses").fields(record)}
            self.assertEqual(actual, expected)

    # ------------------------------------------------------------------
    # Test 9
    # ------------------------------------------------------------------

    def test_skill_type_classified(self) -> None:
        """Skills in the index have skill_type of either 'orchestration' or 'leaf'."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        for record in index.skills:
            self.assertIn(record.skill_type, ("orchestration", "leaf"),
                          f"Invalid skill_type for {record.skill_id}: {record.skill_type}")

    # ------------------------------------------------------------------
    # Test 10
    # ------------------------------------------------------------------

    def test_token_estimate_populated(self) -> None:
        """All skills have token_estimate > 0 for non-empty SKILL.md files."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        for record in index.skills:
            self.assertGreater(record.token_estimate, 0,
                               f"token_estimate is 0 for {record.skill_id}")

    # ------------------------------------------------------------------
    # Test 11
    # ------------------------------------------------------------------

    def test_content_hash_populated(self) -> None:
        """All skills have a 64-character hex content_hash."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        for record in index.skills:
            self.assertEqual(len(record.content_hash), 64,
                             f"content_hash not 64 chars for {record.skill_id}")
            int(record.content_hash, 16)  # raises if not hex

    # ------------------------------------------------------------------
    # Test 12
    # ------------------------------------------------------------------

    def test_warnings_collected(self) -> None:
        """The index has a warnings list (may be empty if no warnings)."""
        repo1, repo2 = self._make_two_repos()
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        self.assertIsInstance(index.warnings, list)

    # ------------------------------------------------------------------
    # Test 13
    # ------------------------------------------------------------------

    def test_load_plugin_json_skills(self) -> None:
        """_load_plugin_json_skills reads plugin.json and returns a dict."""
        repo = self._make_tmp_dir()
        _make_ai_for_china_legal_repo(repo)
        result = _load_plugin_json_skills(repo, "ai-for-china-legal")
        self.assertIsNotNone(result)
        self.assertIn("commercial-legal", result)
        self.assertIsInstance(result["commercial-legal"], list)
        self.assertGreater(len(result["commercial-legal"]), 0)

    # ------------------------------------------------------------------
    # Test 14
    # ------------------------------------------------------------------

    def test_load_plugin_json_missing(self) -> None:
        """_load_plugin_json_skills on a repo with no plugin.json returns None without crashing."""
        repo = self._make_tmp_dir()
        (repo / "skills" / "test").mkdir(parents=True)
        (repo / "skills" / "test" / "SKILL.md").write_text(
            "---\nname: test\ndescription: test\n---\n# Body\n",
            encoding="utf-8",
        )
        # For ai-for-china-legal with no plugin.json → None
        result = _load_plugin_json_skills(repo, "ai-for-china-legal")
        self.assertIsNone(result)
        # For legal-skills → always None
        result2 = _load_plugin_json_skills(repo, "legal-skills")
        self.assertIsNone(result2)

    # ------------------------------------------------------------------
    # Test 15
    # ------------------------------------------------------------------

    def test_get_repo_commit(self) -> None:
        """_get_repo_commit on a temp dir (not a git repo) returns None."""
        repo = self._make_tmp_dir()
        commit = _get_repo_commit(repo)
        self.assertIsNone(commit)

    # ------------------------------------------------------------------
    # Test 16
    # ------------------------------------------------------------------

    def test_build_index_with_previous_index(self) -> None:
        """build_index with a previous index produces merge_report with conflict classification."""
        repo1, repo2 = self._make_two_repos()
        # First, build an index without previous
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ]
        )
        # Write it as a "previous" index
        prev_dir = self._make_tmp_dir()
        prev_path = prev_dir / "prev-index.json"
        write_index(index, prev_path)

        # Now build again with the previous index
        index2 = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(repo1)},
                {"name": "legal-skills", "path": str(repo2)},
            ],
            previous_index_path=prev_path,
        )
        mr = index2.merge_report
        self.assertIn("conflict_classification", mr)
        cc = mr["conflict_classification"]
        # Since content hasn't changed, all should be in-sync
        self.assertGreater(len(cc["in-sync"]), 0)
        self.assertEqual(len(cc["local-missing"]), 0)


if __name__ == "__main__":
    unittest.main()
