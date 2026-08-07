"""Tests for HermesMaterializer — symlink-first, copy for scripts/."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.hermes_materializer import (
    HermesMaterializer,
    MaterializationResult,
    materialize_hermes,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_skill_md(
    skill_dir: Path,
    name: str,
    description: str = "A test skill.",
    extra_body: str = "",
) -> None:
    """Write a minimal SKILL.md file in *skill_dir*."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
name: {name}
description: {description}
---

# {name}

{extra_body}
"""
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _build_fixture_repos(base_dir: Path) -> dict[str, Path]:
    """Build minimal fixture repos under *base_dir*."""
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # ai-for-china-legal: commercial-legal plugin
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "contract-review",
        "contract-review",
        "Review a contract for risks.",
        extra_body="Some body text about contract review.",
    )
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "risk-identification",
        "risk-identification",
        "Identify risks in a contract.",
    )
    # ai-for-china-legal: ai-governance plugin, skill with scripts/
    _write_skill_md(
        acl / "ai-governance" / "skills" / "algorithm-filing",
        "algorithm-filing",
        "File an algorithm registration.",
    )
    scripts_dir = acl / "ai-governance" / "skills" / "algorithm-filing" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "filing_helper.py").write_text(
        "# helper script\n", encoding="utf-8"
    )

    # legal-skills: skill without scripts
    _write_skill_md(
        ls / "skills" / "de-ai-polish",
        "de-ai-polish",
        "De-AI polish for legal text.",
    )
    # legal-skills: skill with scripts/
    _write_skill_md(
        ls / "skills" / "court-sms",
        "court-sms",
        "Generate court SMS notifications.",
    )
    ls_scripts = ls / "skills" / "court-sms" / "scripts"
    ls_scripts.mkdir(parents=True, exist_ok=True)
    (ls_scripts / "sms_gen.py").write_text(
        "# SMS generator\n", encoding="utf-8"
    )

    return {
        "ai-for-china-legal": acl,
        "legal-skills": ls,
    }


def _build_fixture_index(
    base_dir: Path,
    repos: dict[str, Path],
) -> Path:
    """Build a minimal skill-index.json fixture matching the repos."""
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
        },
        {
            "skill_id": "ai-governance:algorithm-filing",
            "name": "algorithm-filing",
            "source_repo": "ai-for-china-legal",
            "plugin": "ai-governance",
            "relative_path": "ai-governance/skills/algorithm-filing/SKILL.md",
            "required_scripts": ["scripts/filing_helper.py"],
            "content_hash": "ghi789",
            "token_estimate": 1000,
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


def _build_empty_index(base_dir: Path) -> Path:
    """Build a skill-index.json with zero skills."""
    repos_meta = {
        "ai-for-china-legal": {
            "path": str(base_dir / "ai-for-china-legal"),
            "commit": None,
            "skill_count": 0,
        },
        "legal-skills": {
            "path": str(base_dir / "legal-skills"),
            "commit": None,
            "skill_count": 0,
        },
    }
    index_data = {
        "generated_at": "2026-08-09T00:00:00Z",
        "scanner_version": "1.0.0",
        "repos": repos_meta,
        "skills": [],
        "merge_report": {},
        "warnings": [],
    }
    index_path = base_dir / "skill-index-empty.json"
    index_path.write_text(
        json.dumps(index_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return index_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHermesMaterializer(unittest.TestCase):
    """Fixture-based unit tests for the Hermes materializer."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.repos = _build_fixture_repos(self.base_dir)
        self.index_path = _build_fixture_index(self.base_dir, self.repos)
        self.output_dir = self.base_dir / "output"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_produces_profile_skills_layout(self) -> None:
        """materialize_hermes produces output_dir/profiles/<profile>/skills/<name>/SKILL.md."""
        result = materialize_hermes(
            self.index_path, self.output_dir, profile_name="lawfirm"
        )
        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
        self.assertTrue(skills_dir.exists(), f"skills dir not found: {skills_dir}")

        for entry in result.strategy_log:
            skill_md = Path(entry.target_path) / "SKILL.md"
            self.assertTrue(
                skill_md.exists(),
                f"SKILL.md not found at {skill_md}",
            )

    def test_skills_without_scripts_are_symlinked(self) -> None:
        """Skills without scripts/ directories are symlinked (zero-copy)."""
        result = materialize_hermes(self.index_path, self.output_dir)
        symlinked_names = {
            e.skill_name for e in result.strategy_log if e.strategy == "symlink"
        }
        self.assertIn("contract-review", symlinked_names)
        self.assertIn("risk-identification", symlinked_names)
        self.assertIn("de-ai-polish", symlinked_names)
        self.assertEqual(result.symlinked_count, 3)

        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
        self.assertTrue((skills_dir / "commercial-legal-contract-review").is_symlink())
        self.assertTrue(
            (skills_dir / "commercial-legal-risk-identification").is_symlink()
        )
        self.assertTrue((skills_dir / "legal-de-ai-polish").is_symlink())

    def test_skills_with_scripts_are_copied(self) -> None:
        """Skills with scripts/ directories are copied via shutil.copytree."""
        result = materialize_hermes(self.index_path, self.output_dir)
        copied_names = {
            e.skill_name for e in result.strategy_log if e.strategy == "copy"
        }
        self.assertIn("algorithm-filing", copied_names)
        self.assertIn("court-sms", copied_names)
        self.assertEqual(result.copied_count, 2)

        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
        self.assertFalse((skills_dir / "ai-governance-algorithm-filing").is_symlink())
        self.assertFalse((skills_dir / "legal-court-sms").is_symlink())

        for name in ("ai-governance-algorithm-filing", "legal-court-sms"):
            marker = skills_dir / name / ".sync_source"
            self.assertTrue(marker.exists(), f".sync_source missing for {name}")

    def test_symlink_naming_convention(self) -> None:
        """Symlink naming: <plugin>-<name> for ai-for-china-legal, legal-<name> for legal-skills."""
        materialize_hermes(self.index_path, self.output_dir)
        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"

        self.assertTrue((skills_dir / "commercial-legal-contract-review").exists())
        self.assertTrue((skills_dir / "ai-governance-algorithm-filing").exists())
        self.assertTrue((skills_dir / "legal-de-ai-polish").exists())
        self.assertTrue((skills_dir / "legal-court-sms").exists())

    def test_fallback_to_copy_on_symlink_failure(self) -> None:
        """Falls back to shutil.copytree if os.symlink raises OSError."""
        original_symlink = os.symlink

        def failing_symlink(src, dst, *args, **kwargs):
            raise OSError("Simulated cross-filesystem error")

        os.symlink = failing_symlink
        try:
            result = materialize_hermes(self.index_path, self.output_dir)
            self.assertGreater(result.fallback_count, 0)
            self.assertEqual(result.copied_count, 2)
            skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
            marker = skills_dir / "commercial-legal-contract-review" / ".sync_source"
            self.assertTrue(marker.exists())
        finally:
            os.symlink = original_symlink

    def test_returns_materialization_result(self) -> None:
        """Returns a MaterializationResult with required fields."""
        result = materialize_hermes(self.index_path, self.output_dir)
        self.assertIsInstance(result, MaterializationResult)
        self.assertEqual(result.materialized_count, 5)
        self.assertEqual(result.symlinked_count, 3)
        self.assertEqual(result.copied_count, 2)
        self.assertEqual(result.fallback_count, 0)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.strategy_log), 5)
        for entry in result.strategy_log:
            self.assertTrue(entry.skill_id)
            self.assertTrue(entry.skill_name)
            self.assertIn(entry.strategy, ("symlink", "copy", "fallback_copy"))
            self.assertTrue(entry.target_path)
            self.assertTrue(entry.source_path)

    def test_read_only_on_source_repos(self) -> None:
        """Source repo file mtimes and content hashes are unchanged after materialization."""
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

        materialize_hermes(self.index_path, self.output_dir)

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

    def test_empty_index_produces_empty_profile(self) -> None:
        """Empty index produces empty profile directory without error."""
        empty_index = _build_empty_index(self.base_dir)
        result = materialize_hermes(empty_index, self.output_dir)
        self.assertEqual(result.materialized_count, 0)
        self.assertEqual(result.symlinked_count, 0)
        self.assertEqual(result.copied_count, 0)
        self.assertEqual(len(result.errors), 0)
        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
        self.assertTrue(skills_dir.exists())
        children = list(skills_dir.iterdir())
        self.assertEqual(len(children), 0)

    def test_class_based_api(self) -> None:
        """HermesMaterializer class produces same results as function API."""
        materializer = HermesMaterializer()
        result = materializer.materialize(self.index_path, self.output_dir)
        self.assertEqual(result.materialized_count, 5)


if __name__ == "__main__":
    unittest.main()
