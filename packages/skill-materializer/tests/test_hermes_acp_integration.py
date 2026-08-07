"""Hermes ACP integration test — materialize to Hermes profile and verify loadability.

This test materializes a small set of fixture skills to a temporary Hermes
profile directory, sets ``HERMES_HOME`` to the temp directory, and runs
``hermes acp --check`` to verify the profile is loadable.

The test skips with a clear message if the ``hermes`` binary is not found
in PATH.  This ensures the test is reliable in CI environments where
Hermes may not be installed.

CRITICAL: The test does NOT modify any source repo files.  All
materialization output goes to a temporary directory that is cleaned up
after execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.hermes_materializer import materialize_hermes


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


def _build_fixture_repos_and_index(base_dir: Path) -> Path:
    """Build fixture repos and a skill-index.json with 3 skills."""
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # Skill 1: ai-for-china-legal, no scripts
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "contract-review",
        "contract-review",
        "Review a contract for risks.",
        extra_body="Some body text about contract review.",
    )

    # Skill 2: ai-for-china-legal, with scripts/
    _write_skill_md(
        acl / "ai-governance" / "skills" / "algorithm-filing",
        "algorithm-filing",
        "File an algorithm registration.",
    )
    scripts_dir = acl / "ai-governance" / "skills" / "algorithm-filing" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "filing_helper.py").write_text("# helper\n", encoding="utf-8")

    # Skill 3: legal-skills, no scripts
    _write_skill_md(
        ls / "skills" / "de-ai-polish",
        "de-ai-polish",
        "De-AI polish for legal text.",
    )

    skills = [
        {
            "skill_id": "commercial-legal:contract-review",
            "name": "contract-review",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
            "skill_type": "orchestration",
            "parent_skill": None,
            "child_skills": [],
            "description": "Review a contract for risks.",
            "frontmatter": {"name": "contract-review", "description": "Review a contract for risks."},
            "token_estimate": 500,
            "declared_gates": ["research-gate"],
            "referenced_resources": [],
            "practice_profile_dependency": False,
            "host_assumptions": [],
            "required_scripts": [],
            "license": None,
            "version": "1.0.0",
            "content_hash": "abc123",
            "has_local_modification": False,
            "warnings": [],
        },
        {
            "skill_id": "ai-governance:algorithm-filing",
            "name": "algorithm-filing",
            "source_repo": "ai-for-china-legal",
            "plugin": "ai-governance",
            "relative_path": "ai-governance/skills/algorithm-filing/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": "commercial-legal:contract-review",
            "child_skills": [],
            "description": "File an algorithm registration.",
            "frontmatter": {"name": "algorithm-filing", "description": "File an algorithm registration."},
            "token_estimate": 300,
            "declared_gates": [],
            "referenced_resources": [],
            "practice_profile_dependency": False,
            "host_assumptions": [],
            "required_scripts": ["scripts/filing_helper.py"],
            "license": None,
            "version": "1.0.0",
            "content_hash": "def456",
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
            "required_scripts": [],
            "license": "MIT",
            "version": "2.0.0",
            "content_hash": "ghi789",
            "has_local_modification": False,
            "warnings": [],
        },
    ]

    repos_meta = {
        "ai-for-china-legal": {"path": str(acl), "commit": None, "skill_count": 2},
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


def _hermes_available() -> bool:
    """Check if the hermes binary is available in PATH."""
    return shutil.which("hermes") is not None


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestHermesACPIntegration(unittest.TestCase):
    """Integration test: materialize to Hermes profile and verify with hermes acp --check."""

    def setUp(self) -> None:
        if not _hermes_available():
            raise unittest.SkipTest(
                "hermes binary not found in PATH — skipping Hermes ACP integration test"
            )
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_repos_and_index(self.base_dir)
        self.hermes_home = self.base_dir / "hermes-home"

    def tearDown(self) -> None:
        if hasattr(self, "_tmpdir"):
            self._tmpdir.cleanup()

    def test_materialized_profile_loadable_by_hermes(self) -> None:
        """Materialize fixture skills to a Hermes profile and verify hermes acp --check passes.

        This is the key integration test for success criterion 1:
        "物化器能把语料落到 Hermes profile 布局（symlink 优先、脚本类 copy），
        且 hermes acp 能加载物化产物中的 skill（实测验证，不是推断）"
        """
        # Step 1: Materialize to Hermes profile layout
        result = materialize_hermes(
            self.index_path,
            self.hermes_home,
            profile_name="test",
        )
        self.assertEqual(result.materialized_count, 3)
        self.assertEqual(len(result.errors), 0, f"Materialization errors: {result.errors}")

        # Verify profile directory structure
        skills_dir = self.hermes_home / "profiles" / "test" / "skills"
        self.assertTrue(skills_dir.exists(), f"Skills dir not found: {skills_dir}")

        skill_dirs = sorted(
            d.name for d in skills_dir.iterdir()
            if d.is_symlink() or d.is_dir()
        )
        self.assertEqual(len(skill_dirs), 3, f"Expected 3 skills, got {skill_dirs}")

        # Step 2: Set HERMES_HOME and run hermes acp --check
        env = os.environ.copy()
        env["HERMES_HOME"] = str(self.hermes_home)

        check_result = subprocess.run(
            ["hermes", "acp", "--check"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        # Assert hermes acp --check exits 0 (profile is loadable)
        self.assertEqual(
            check_result.returncode, 0,
            f"hermes acp --check failed (exit {check_result.returncode})\n"
            f"stdout: {check_result.stdout}\n"
            f"stderr: {check_result.stderr}\n"
            f"HERMES_HOME: {self.hermes_home}",
        )

    def test_materialized_skills_have_skill_md(self) -> None:
        """Each materialized skill directory has a SKILL.md file."""
        result = materialize_hermes(
            self.index_path,
            self.hermes_home,
            profile_name="test",
        )
        self.assertEqual(result.materialized_count, 3)

        skills_dir = self.hermes_home / "profiles" / "test" / "skills"
        for entry in skills_dir.iterdir():
            skill_md = entry / "SKILL.md"
            self.assertTrue(
                skill_md.exists(),
                f"SKILL.md not found in materialized skill: {entry}",
            )

    def test_does_not_modify_source_repos(self) -> None:
        """Materialization is read-only on source repos."""
        acl = self.base_dir / "ai-for-china-legal"
        ls = self.base_dir / "legal-skills"

        # Compute hashes of source files before materialization
        source_files: list[Path] = []
        for root in (acl, ls):
            for f in root.rglob("SKILL.md"):
                source_files.append(f)
            for f in root.rglob("*.py"):
                source_files.append(f)

        before_hashes = {
            str(f): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in source_files
        }

        # Run materialization
        materialize_hermes(self.index_path, self.hermes_home, profile_name="test")

        # Verify hashes unchanged
        for f in source_files:
            after_hash = hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(
                before_hashes[str(f)],
                after_hash,
                f"Source file modified: {f}",
            )


if __name__ == "__main__":
    unittest.main()
