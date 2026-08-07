"""Tests for the CLI entry point.

Tests cover:
- Help output (--help, scan --help)
- Basic scan with one repo
- Scan with two repos
- Scan with previous index
- Output path validation (rejects source repo paths, accepts external)
- Summary printing
- Missing required args returns 1
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.cli import _validate_output_path, main


def _make_mini_repo(root: Path, name: str = "test-skill") -> None:
    """Create a minimal repo with one SKILL.md file."""
    skills_dir = root / "skills" / name
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n# Body\n",
        encoding="utf-8",
    )


class TestCLI(unittest.TestCase):
    """CLI invocation tests."""

    def setUp(self) -> None:
        self._tmpdirs: list[Path] = []

    def tearDown(self) -> None:
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_tmp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self._tmpdirs.append(d)
        return d

    # ------------------------------------------------------------------
    # Test 1
    # ------------------------------------------------------------------

    def test_cli_help(self) -> None:
        """main(['--help']) prints usage and raises SystemExit(0)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("scan", buf.getvalue())

    # ------------------------------------------------------------------
    # Test 2
    # ------------------------------------------------------------------

    def test_cli_scan_help(self) -> None:
        """main(['scan', '--help']) prints scan usage."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                main(["scan", "--help"])
        self.assertEqual(ctx.exception.code, 0)
        output = buf.getvalue()
        self.assertIn("--repo", output)
        self.assertIn("--repo-name", output)
        self.assertIn("--output", output)
        self.assertIn("--previous-index", output)

    # ------------------------------------------------------------------
    # Test 3
    # ------------------------------------------------------------------

    def test_cli_scan_basic(self) -> None:
        """main(['scan', ...]) with one repo returns 0 and produces valid JSON."""
        repo = self._make_tmp_dir()
        _make_mini_repo(repo)
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["scan", "--repo", str(repo), "--repo-name", "test-repo", "--output", str(out_path)])

        self.assertEqual(rc, 0)
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("skills", data)
        self.assertGreater(len(data["skills"]), 0)

    # ------------------------------------------------------------------
    # Test 4
    # ------------------------------------------------------------------

    def test_cli_scan_two_repos(self) -> None:
        """main with two --repo and --repo-name args produces output with skills from both."""
        repo1 = self._make_tmp_dir()
        _make_mini_repo(repo1, "skill-a")
        repo2 = self._make_tmp_dir()
        _make_mini_repo(repo2, "skill-b")
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([
                "scan",
                "--repo", str(repo1), "--repo-name", "repo-a",
                "--repo", str(repo2), "--repo-name", "repo-b",
                "--output", str(out_path),
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        repos = {s["source_repo"] for s in data["skills"]}
        self.assertEqual(repos, {"repo-a", "repo-b"})

    # ------------------------------------------------------------------
    # Test 5
    # ------------------------------------------------------------------

    def test_cli_scan_with_previous_index(self) -> None:
        """main with --previous-index produces a populated merge_report."""
        repo = self._make_tmp_dir()
        _make_mini_repo(repo)
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"

        # First run — no previous index
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["scan", "--repo", str(repo), "--repo-name", "test-repo", "--output", str(out_path)])
        self.assertEqual(rc, 0)

        # Second run — with previous index
        out_path2 = out_dir / "skill-index-v2.json"
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = main([
                "scan", "--repo", str(repo), "--repo-name", "test-repo",
                "--output", str(out_path2),
                "--previous-index", str(out_path),
            ])
        self.assertEqual(rc2, 0)
        data = json.loads(out_path2.read_text(encoding="utf-8"))
        mr = data["merge_report"]
        self.assertIn("conflict_classification", mr)
        # Content hasn't changed → in-sync
        self.assertGreater(len(mr["conflict_classification"]["in-sync"]), 0)

    # ------------------------------------------------------------------
    # Test 6
    # ------------------------------------------------------------------

    def test_cli_validate_output_path_rejects_source_repo(self) -> None:
        """_validate_output_path raises ValueError when output is inside a repo path."""
        with self.assertRaises(ValueError):
            _validate_output_path(
                "/home/sorawatcher/workspace/ai-for-china-legal/skill-index.json",
                ["/home/sorawatcher/workspace/ai-for-china-legal"],
            )

    # ------------------------------------------------------------------
    # Test 7
    # ------------------------------------------------------------------

    def test_cli_validate_output_path_accepts_external(self) -> None:
        """_validate_output_path does not raise when output is outside repo paths."""
        # Should not raise
        _validate_output_path("/tmp/output.json", ["/home/sorawatcher/workspace/ai-for-china-legal"])
        _validate_output_path("/tmp/sub/dir/output.json", ["/home/sorawatcher/repo1", "/home/sorawatcher/repo2"])

    # ------------------------------------------------------------------
    # Test 8
    # ------------------------------------------------------------------

    def test_cli_scan_prints_summary(self) -> None:
        """CLI prints a summary with total skills and per-repo counts."""
        repo = self._make_tmp_dir()
        _make_mini_repo(repo, "test-skill")
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["scan", "--repo", str(repo), "--repo-name", "test-repo", "--output", str(out_path)])

        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("Total skills:", output)
        self.assertIn("test-repo:", output)

    # ------------------------------------------------------------------
    # Test 9
    # ------------------------------------------------------------------

    def test_cli_scan_missing_repo_arg(self) -> None:
        """main(['scan', '--output', ...]) without --repo returns 1."""
        buf = io.StringIO()
        err_buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
            with self.assertRaises(SystemExit):
                main(["scan", "--output", "/tmp/x.json"])
        # argparse raises SystemExit(2) for missing required args

    # ------------------------------------------------------------------
    # Test 10
    # ------------------------------------------------------------------

    def test_cli_scan_missing_output_arg(self) -> None:
        """main(['scan', '--repo', ...]) without --output returns error."""
        buf = io.StringIO()
        err_buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
            with self.assertRaises(SystemExit):
                main(["scan", "--repo", "/tmp", "--repo-name", "test"])
        # argparse raises SystemExit(2) for missing required args


if __name__ == "__main__":
    unittest.main()
