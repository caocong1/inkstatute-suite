"""Tests for ACPMaterializer — Claude Code plugin format + host assumption rewriting."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.acp_materializer import (
    ACPMaterializationResult,
    ACPMaterializer,
    materialize_acp,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_skill_md(
    skill_dir: Path,
    name: str,
    description: str = "A test skill.",
    body: str = "",
) -> None:
    """Write a SKILL.md file in *skill_dir*."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
name: {name}
description: {description}
---

# {name}

{body}
"""
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _build_fixture_repos(base_dir: Path) -> dict[str, Path]:
    """Build fixture repos with skills that have host assumptions."""
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # Skill with /plugin:skill trigger pattern (needs rewriting)
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "contract-review",
        "contract-review",
        "Review a contract for risks.",
        body="Use /commercial-legal:risk-identification when a contract is detected.",
    )

    # Skill with ask_user pattern (needs rewriting)
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "risk-identification",
        "risk-identification",
        "Identify risks in a contract.",
        body="Use ask_user to clarify missing facts before proceeding.",
    )

    # Skill with CLAUDE.md reference (flag only, no text change → symlink)
    _write_skill_md(
        acl / "ai-governance" / "skills" / "algorithm-filing",
        "algorithm-filing",
        "File an algorithm registration.",
        body="Read `ai-governance/CLAUDE.md` for practice config.",
    )

    # Clean skill (no patterns → symlink)
    _write_skill_md(
        ls / "skills" / "de-ai-polish",
        "de-ai-polish",
        "De-AI polish for legal text.",
        body="Polish text to remove AI artifacts.",
    )

    # Skill with scripts/ and trigger pattern (copy + rewrite)
    _write_skill_md(
        ls / "skills" / "court-sms",
        "court-sms",
        "Generate court SMS notifications.",
        body="Trigger /commercial-legal:risk-identification if needed.",
    )
    scripts_dir = ls / "skills" / "court-sms" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "sms_gen.py").write_text("# SMS generator\n", encoding="utf-8")

    return {
        "ai-for-china-legal": acl,
        "legal-skills": ls,
    }


def _build_fixture_index(
    base_dir: Path,
    repos: dict[str, Path],
) -> Path:
    """Build a skill-index.json fixture matching the repos."""
    skills = [
        {
            "skill_id": "commercial-legal:contract-review",
            "name": "contract-review",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
            "required_scripts": [],
            "content_hash": "abc123",
            "token_estimate": 500,
            "description": "Review a contract for risks.",
        },
        {
            "skill_id": "commercial-legal:risk-identification",
            "name": "risk-identification",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/risk-identification/SKILL.md",
            "required_scripts": [],
            "content_hash": "def456",
            "token_estimate": 300,
            "description": "Identify risks in a contract.",
        },
        {
            "skill_id": "ai-governance:algorithm-filing",
            "name": "algorithm-filing",
            "source_repo": "ai-for-china-legal",
            "plugin": "ai-governance",
            "relative_path": "ai-governance/skills/algorithm-filing/SKILL.md",
            "required_scripts": [],
            "content_hash": "ghi789",
            "token_estimate": 1000,
            "description": "File an algorithm registration.",
        },
        {
            "skill_id": "legal-de-ai-polish",
            "name": "de-ai-polish",
            "source_repo": "legal-skills",
            "plugin": None,
            "relative_path": "skills/de-ai-polish/SKILL.md",
            "required_scripts": [],
            "content_hash": "jkl012",
            "token_estimate": 800,
            "description": "De-AI polish for legal text.",
        },
        {
            "skill_id": "legal-court-sms",
            "name": "court-sms",
            "source_repo": "legal-skills",
            "plugin": None,
            "relative_path": "skills/court-sms/SKILL.md",
            "required_scripts": ["scripts/sms_gen.py"],
            "content_hash": "mno345",
            "token_estimate": 2000,
            "description": "Generate court SMS notifications.",
        },
    ]

    repos_meta = {
        name: {"path": str(path), "commit": None, "skill_count": 0}
        for name, path in repos.items()
    }
    repos_meta["ai-for-china-legal"]["skill_count"] = 3
    repos_meta["legal-skills"]["skill_count"] = 2

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


class TestACPMaterializer(unittest.TestCase):
    """Fixture-based unit tests for the ACP materializer."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.repos = _build_fixture_repos(self.base_dir)
        self.index_path = _build_fixture_index(self.base_dir, self.repos)
        self.output_dir = self.base_dir / "output"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_produces_plugin_json_and_skill_dirs(self) -> None:
        """materialize_acp produces .claude-plugin/plugin.json and skill directories."""
        result = materialize_acp(self.index_path, self.output_dir)
        plugin_json = self.output_dir / ".claude-plugin" / "plugin.json"
        self.assertTrue(plugin_json.exists(), "plugin.json not found")
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        self.assertIn("name", data)
        self.assertIn("skills", data)
        self.assertEqual(len(data["skills"]), 5)

        skills_dir = self.output_dir / "skills"
        self.assertTrue(skills_dir.exists())

    def test_skills_without_host_assumptions_are_symlinked(self) -> None:
        """Skills with no host assumptions to rewrite are symlinked."""
        result = materialize_acp(self.index_path, self.output_dir)
        # de-ai-polish has no patterns → symlink
        # algorithm-filing has CLAUDE.md only (flag, no text change) → symlink
        self.assertGreater(result.symlinked_count, 0)

        skills_dir = self.output_dir / "skills"
        # de-ai-polish: clean text → symlink
        self.assertTrue(
            (skills_dir / "legal-de-ai-polish").is_symlink(),
            "legal-de-ai-polish should be symlinked",
        )
        # algorithm-filing: CLAUDE.md flag only (no text change) → symlink
        self.assertTrue(
            (skills_dir / "ai-governance-algorithm-filing").is_symlink(),
            "ai-governance-algorithm-filing should be symlinked (flag only)",
        )

    def test_skills_with_host_assumptions_are_rewritten(self) -> None:
        """Skills with host assumptions to rewrite: rewritten SKILL.md as file."""
        result = materialize_acp(self.index_path, self.output_dir)
        # contract-review has /plugin:skill → rewrite
        # risk-identification has ask_user → rewrite
        # court-sms has /plugin:skill + scripts/ → copy + rewrite
        self.assertGreater(result.rewritten_count, 0)

        skills_dir = self.output_dir / "skills"

        # contract-review: rewritten (not symlink)
        cr_path = skills_dir / "commercial-legal-contract-review"
        self.assertFalse(cr_path.is_symlink(), "rewritten skill should not be symlink")
        cr_skill = cr_path / "SKILL.md"
        self.assertTrue(cr_skill.exists())
        cr_text = cr_skill.read_text(encoding="utf-8")
        self.assertNotIn("/commercial-legal:risk-identification", cr_text)
        self.assertIn("When the user asks about risk-identification...", cr_text)

        # risk-identification: rewritten (not symlink)
        ri_path = skills_dir / "commercial-legal-risk-identification"
        self.assertFalse(ri_path.is_symlink())
        ri_text = (ri_path / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("ask_user", ri_text)
        self.assertIn("elicitation", ri_text)

    def test_skills_with_scripts_are_copied(self) -> None:
        """Skills with scripts/ are copied via shutil.copytree."""
        result = materialize_acp(self.index_path, self.output_dir)
        skills_dir = self.output_dir / "skills"

        # court-sms has scripts/ + trigger pattern → copy + rewrite
        cs_path = skills_dir / "legal-court-sms"
        self.assertFalse(cs_path.is_symlink())
        # scripts/ should be copied
        self.assertTrue((cs_path / "scripts" / "sms_gen.py").exists())
        # .sync_source marker should exist
        self.assertTrue((cs_path / ".sync_source").exists())
        # SKILL.md should be rewritten
        cs_text = (cs_path / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("/commercial-legal:risk-identification", cs_text)

    def test_returns_materialization_result(self) -> None:
        """Returns ACPMaterializationResult with required fields."""
        result = materialize_acp(self.index_path, self.output_dir)
        self.assertIsInstance(result, ACPMaterializationResult)
        self.assertEqual(result.materialized_count, 5)
        self.assertGreater(result.rewritten_count, 0)
        self.assertGreater(result.symlinked_count, 0)
        self.assertEqual(len(result.errors), 0)
        # rewrite_report should have entries
        self.assertGreater(result.rewrite_report.total_rewrites, 0)

    def test_read_only_on_source_repos(self) -> None:
        """Source repo files are unchanged after materialization."""
        source_files: list[Path] = []
        for repo_path in self.repos.values():
            for skill_md in repo_path.rglob("SKILL.md"):
                source_files.append(skill_md)

        before = {}
        for f in source_files:
            content = f.read_bytes()
            before[f] = (
                hashlib.sha256(content).hexdigest(),
                f.stat().st_mtime_ns,
            )

        materialize_acp(self.index_path, self.output_dir)

        for f in source_files:
            content = f.read_bytes()
            after_hash = hashlib.sha256(content).hexdigest()
            after_mtime = f.stat().st_mtime_ns
            self.assertEqual(before[f][0], after_hash, f"Content changed: {f}")
            self.assertEqual(
                before[f][1],
                after_mtime,
                f"mtime changed: {f}",
            )

    def test_rewrite_report_written_to_output(self) -> None:
        """The rewrite report is written to output_dir/rewrite-report.json."""
        materialize_acp(self.index_path, self.output_dir)
        report_path = self.output_dir / "rewrite-report.json"
        self.assertTrue(report_path.exists(), "rewrite-report.json not found")
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("total_rewrites", report_data)
        self.assertIn("entries", report_data)
        self.assertGreater(report_data["total_rewrites"], 0)

        # Check entry structure
        for entry in report_data["entries"]:
            self.assertIn("original_text", entry)
            self.assertIn("rewritten_text", entry)
            self.assertIn("rule_applied", entry)
            self.assertIn("location", entry)
            self.assertIn("line_number", entry)

    def test_class_based_api(self) -> None:
        """ACPMaterializer class produces same results as function API."""
        materializer = ACPMaterializer()
        result = materializer.materialize(self.index_path, self.output_dir)
        self.assertEqual(result.materialized_count, 5)


if __name__ == "__main__":
    unittest.main()
