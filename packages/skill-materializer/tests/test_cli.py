"""CLI smoke tests for inkstatute-skill-materializer.

Tests the CLI entry point with fixture index files.  Verifies that
all three subcommands (materialize, inject-body, routing-manifest)
work via the command-line interface.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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


def _build_fixture_index(base_dir: Path) -> Path:
    """Build a minimal skill-index.json with 3 skills."""
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # Skill 1: ai-for-china-legal, no scripts, no host assumptions
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

    # Skill 3: legal-skills, with host assumptions
    _write_skill_md(
        ls / "skills" / "de-ai-polish",
        "de-ai-polish",
        "De-AI polish for legal text.",
        extra_body="Use /commercial-legal:contract-review for trigger. ask_user when needed.",
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
            "child_skills": ["risk-identification"],
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
            "host_assumptions": ["/commercial-legal:contract-review"],
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


def _get_pythonpath() -> str:
    """Get the PYTHONPATH needed to run the CLI as a module."""
    # The tests run with the skill-materializer src already on PYTHONPATH
    # (via the gate runner).  For direct invocation, we need to set it.
    repo_root = Path(__file__).resolve().parents[3]
    paths = [
        str(repo_root / "packages" / "skill-materializer" / "src"),
        str(repo_root / "packages" / "skill-index" / "src"),
        str(repo_root / "packages" / "platform-contract" / "src"),
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCLIHelp(unittest.TestCase):
    """Tests for CLI --help and no-command behavior."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_no_command_prints_help_and_returns_1(self) -> None:
        """Running with no subcommand prints help and returns exit code 1."""
        result = self._run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage:", result.stdout.lower() + result.stderr.lower())

    def test_help_shows_subcommands(self) -> None:
        """--help shows all three subcommands."""
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0)
        output = result.stdout.lower() + result.stderr.lower()
        self.assertIn("materialize", output)
        self.assertIn("inject-body", output)
        self.assertIn("routing-manifest", output)

    def test_materialize_help(self) -> None:
        """materialize --help shows usage."""
        result = self._run_cli("materialize", "--help")
        self.assertEqual(result.returncode, 0)
        output = result.stdout.lower() + result.stderr.lower()
        self.assertIn("--target", output)
        self.assertIn("--index", output)
        self.assertIn("--output", output)

    def test_inject_body_help(self) -> None:
        """inject-body --help shows usage."""
        result = self._run_cli("inject-body", "--help")
        self.assertEqual(result.returncode, 0)
        output = result.stdout.lower() + result.stderr.lower()
        self.assertIn("--skill-id", output)
        self.assertIn("--budget", output)

    def test_routing_manifest_help(self) -> None:
        """routing-manifest --help shows usage."""
        result = self._run_cli("routing-manifest", "--help")
        self.assertEqual(result.returncode, 0)
        output = result.stdout.lower() + result.stderr.lower()
        self.assertIn("--index", output)
        self.assertIn("--output", output)

    def test_invalid_target_returns_error(self) -> None:
        """Invalid --target value produces a clear error and non-zero exit."""
        result = self._run_cli("materialize", "--target", "invalid", "--index", "/tmp/x", "--output", "/tmp/y")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_required_args_returns_error(self) -> None:
        """Missing required arguments produces a non-zero exit code."""
        result = self._run_cli("materialize")
        self.assertNotEqual(result.returncode, 0)


class TestCLIMaterializeHermes(unittest.TestCase):
    """Tests for the materialize --target hermes subcommand."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index(self.base_dir)
        self.output_dir = self.base_dir / "hermes-output"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_materialize_hermes_produces_profile(self) -> None:
        """materialize --target hermes produces a Hermes profile layout."""
        result = self._run_cli(
            "materialize",
            "--target", "hermes",
            "--index", str(self.index_path),
            "--output", str(self.output_dir),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Hermes materialization complete", result.stdout)
        # Verify profile directory exists
        skills_dir = self.output_dir / "profiles" / "lawfirm" / "skills"
        self.assertTrue(skills_dir.exists())
        # Should have 3 skill directories
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() or d.is_symlink()]
        self.assertEqual(len(skill_dirs), 3)

    def test_materialize_hermes_custom_profile(self) -> None:
        """materialize --target hermes --profile test produces correct profile name."""
        result = self._run_cli(
            "materialize",
            "--target", "hermes",
            "--index", str(self.index_path),
            "--output", str(self.output_dir),
            "--profile", "test",
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Profile: test", result.stdout)
        skills_dir = self.output_dir / "profiles" / "test" / "skills"
        self.assertTrue(skills_dir.exists())


class TestCLIMaterializeACP(unittest.TestCase):
    """Tests for the materialize --target acp subcommand."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index(self.base_dir)
        self.output_dir = self.base_dir / "acp-output"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_materialize_acp_produces_plugin_layout(self) -> None:
        """materialize --target acp produces a Claude Code plugin layout."""
        result = self._run_cli(
            "materialize",
            "--target", "acp",
            "--index", str(self.index_path),
            "--output", str(self.output_dir),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("ACP materialization complete", result.stdout)
        # Verify plugin.json exists
        plugin_json = self.output_dir / ".claude-plugin" / "plugin.json"
        self.assertTrue(plugin_json.exists())
        # Verify rewrite-report.json exists
        rewrite_report = self.output_dir / "rewrite-report.json"
        self.assertTrue(rewrite_report.exists())
        # Verify skills directory exists
        skills_dir = self.output_dir / "skills"
        self.assertTrue(skills_dir.exists())


class TestCLIInjectBody(unittest.TestCase):
    """Tests for the inject-body subcommand."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index(self.base_dir)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_inject_body_returns_json_summary(self) -> None:
        """inject-body prints a JSON summary with token estimates."""
        result = self._run_cli(
            "inject-body",
            "--skill-id", "commercial-legal:contract-review",
            "--index", str(self.index_path),
            "--budget", "5000",
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # Output should be valid JSON
        summary = json.loads(result.stdout)
        self.assertEqual(summary["skill_id"], "commercial-legal:contract-review")
        self.assertIn("original_token_estimate", summary)
        self.assertIn("injected_token_estimate", summary)
        self.assertIn("budget_tokens", summary)
        self.assertEqual(summary["budget_tokens"], 5000)

    def test_inject_body_skill_not_found(self) -> None:
        """inject-body with unknown skill_id returns error."""
        result = self._run_cli(
            "inject-body",
            "--skill-id", "nonexistent:skill",
            "--index", str(self.index_path),
            "--budget", "5000",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr.lower())


class TestCLIRoutingManifest(unittest.TestCase):
    """Tests for the routing-manifest subcommand."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index(self.base_dir)
        self.output_path = self.base_dir / "routing-manifest.json"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_routing_manifest_produces_json(self) -> None:
        """routing-manifest produces a metadata-only JSON manifest."""
        result = self._run_cli(
            "routing-manifest",
            "--index", str(self.index_path),
            "--output", str(self.output_path),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Routing manifest written to", result.stdout)
        self.assertTrue(self.output_path.exists())
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["manifest_type"], "routing")
        self.assertEqual(data["skill_count"], 3)

    def test_routing_manifest_no_body_fields(self) -> None:
        """routing-manifest output has no body/content fields."""
        result = self._run_cli(
            "routing-manifest",
            "--index", str(self.index_path),
            "--output", str(self.output_path),
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(self.output_path.read_text(encoding="utf-8"))
        excluded = {"frontmatter", "raw_text", "body", "content", "content_hash"}
        for record in data["skills"]:
            for field_name in excluded:
                self.assertNotIn(field_name, record)


class TestCLIIndexNotFound(unittest.TestCase):
    """Tests for error handling when index file is missing."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env["PYTHONPATH"] = _get_pythonpath()
        return subprocess.run(
            [sys.executable, "-m", "inkstatute_skill_materializer", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=30,
        )

    def test_materialize_missing_index(self) -> None:
        """materialize with missing index returns error."""
        result = self._run_cli(
            "materialize",
            "--target", "hermes",
            "--index", "/nonexistent/path.json",
            "--output", "/tmp/out",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr.lower())

    def test_inject_body_missing_index(self) -> None:
        """inject-body with missing index returns error."""
        result = self._run_cli(
            "inject-body",
            "--skill-id", "test",
            "--index", "/nonexistent/path.json",
            "--budget", "5000",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr.lower())

    def test_routing_manifest_missing_index(self) -> None:
        """routing-manifest with missing index returns error."""
        result = self._run_cli(
            "routing-manifest",
            "--index", "/nonexistent/path.json",
            "--output", "/tmp/out.json",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
