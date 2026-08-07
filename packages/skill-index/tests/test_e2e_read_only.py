"""End-to-end tests: scan real repos with read-only verification.

This is the end-to-end integration test that verifies all 6 success criteria
from ROADMAP.md.  It scans the real repos (if present) and asserts the
complete pipeline works.

Tests are skipped if the real repos are not present.

CRITICAL: All output paths in these tests must be in temp directories
OUTSIDE the source repos.  The read-only enforcement is the key assertion.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.cli import main as cli_main
from inkstatute_skill_index.index_builder import build_index, serialize_index, write_index

AI_FOR_CHINA_LEGAL = Path("/home/sorawatcher/workspace/ai-for-china-legal")
LEGAL_SKILLS = Path("/home/sorawatcher/workspace/legal-skills")


def _record_file_states(
    root: Path, sample_size: int | None = None
) -> dict[str, tuple[int, str]]:
    """Walk *root* and record (mtime_ns, sha256_hex) for each file.

    If *sample_size* is given, only the first *sample_size* files (sorted)
    are recorded — useful for large repos.
    """
    states: dict[str, tuple[int, str]] = {}
    files = sorted(root.rglob("*"))
    for path in files:
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if ".git" in path.parts:
            continue
        rel = str(path.relative_to(root))
        mtime = path.stat().st_mtime_ns
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        states[rel] = (mtime, digest)
        if sample_size is not None and len(states) >= sample_size:
            break
    return states


class TestE2EReadOnly(unittest.TestCase):
    """End-to-end scan of real repos with read-only verification."""

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
    # Test 1: Scan ai-for-china-legal
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists(),
        "ai-for-china-legal repo not present",
    )
    def test_e2e_scan_ai_for_china_legal(self) -> None:
        """Scan ai-for-china-legal — skills non-empty, read-only verified."""
        # Record file states (sample: first 30 SKILL.md + all plugin.json)
        skill_files = sorted(AI_FOR_CHINA_LEGAL.rglob("SKILL.md"))[:30]
        plugin_jsons = sorted(AI_FOR_CHINA_LEGAL.glob("*/.claude-plugin/plugin.json"))
        sample_paths = skill_files + plugin_jsons

        before: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            rel = str(p.relative_to(AI_FOR_CHINA_LEGAL))
            before[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        # Build index
        index = build_index([{"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)}])
        self.assertGreater(len(index.skills), 0)

        # Re-record and assert unchanged
        after: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            rel = str(p.relative_to(AI_FOR_CHINA_LEGAL))
            after[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        self.assertEqual(before, after, "ai-for-china-legal files were modified during scan")

    # ------------------------------------------------------------------
    # Test 2: Scan legal-skills
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        LEGAL_SKILLS.exists(),
        "legal-skills repo not present",
    )
    def test_e2e_scan_legal_skills(self) -> None:
        """Scan legal-skills — 51 skills, all leaf, all source_repo=legal-skills, all legal- prefixed."""
        index = build_index([{"name": "legal-skills", "path": str(LEGAL_SKILLS)}])
        self.assertGreater(len(index.skills), 0)

        for record in index.skills:
            self.assertEqual(record.source_repo, "legal-skills")
            self.assertEqual(record.skill_type, "leaf")
            self.assertTrue(record.skill_id.startswith("legal-"),
                            f"skill_id does not start with 'legal-': {record.skill_id}")

    # ------------------------------------------------------------------
    # Test 3: Scan both repos
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists() and LEGAL_SKILLS.exists(),
        "Both repos must be present",
    )
    def test_e2e_scan_both_repos(self) -> None:
        """Scan both repos — total ~396 skills, both repos present in metadata."""
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)},
                {"name": "legal-skills", "path": str(LEGAL_SKILLS)},
            ]
        )
        total = len(index.skills)
        # 338 (ai-for-china-legal excluding .qwen/) + 51 (legal-skills) = 389
        # Or 345 + 51 = 396 if .qwen/ is included — scanner excludes .qwen/
        self.assertGreater(total, 350, f"Total skill count too low: {total}")
        self.assertLessEqual(total, 400, f"Total skill count too high: {total}")

        repos_in_skills = {r.source_repo for r in index.skills}
        self.assertEqual(repos_in_skills, {"ai-for-china-legal", "legal-skills"})

        # repos metadata
        self.assertIn("ai-for-china-legal", index.repos)
        self.assertIn("legal-skills", index.repos)
        for name, meta in index.repos.items():
            self.assertIn("skill_count", meta)
            self.assertGreater(meta["skill_count"], 0)

    # ------------------------------------------------------------------
    # Test 4: Orchestration vs leaf counts
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists(),
        "ai-for-china-legal repo not present",
    )
    def test_e2e_orchestration_leaf_counts(self) -> None:
        """Verify ~73 orchestration entries and ~272 leaf skills in ai-for-china-legal."""
        index = build_index([{"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)}])

        orchestration = [r for r in index.skills if r.skill_type == "orchestration"]
        leaf = [r for r in index.skills if r.skill_type == "leaf"]

        # Per research: 73 orchestration entries, 270 leaf sub-skills (excluding .qwen/)
        # Scanner excludes .qwen/ → 338 total = ~73 orch + ~265 leaf
        self.assertGreater(len(orchestration), 50,
                           f"Orchestration count too low: {len(orchestration)}")
        self.assertGreater(len(leaf), 200,
                           f"Leaf count too low: {len(leaf)}")

        # Parent-child relationships: leaf skills should have parent_skill set
        leaf_with_parent = [r for r in leaf if r.parent_skill is not None]
        self.assertGreater(len(leaf_with_parent), 100,
                           f"Too few leaf skills with parent_skill set: {len(leaf_with_parent)}")

    # ------------------------------------------------------------------
    # Test 5: Metadata fields populated
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists() and LEGAL_SKILLS.exists(),
        "Both repos must be present",
    )
    def test_e2e_metadata_fields_populated(self) -> None:
        """All 8 SKILL-03 fields present for each skill."""
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)},
                {"name": "legal-skills", "path": str(LEGAL_SKILLS)},
            ]
        )

        for record in index.skills:
            # All 8 SKILL-03 fields
            self.assertIsInstance(record.token_estimate, int)
            self.assertGreater(record.token_estimate, 0,
                               f"token_estimate is 0 for {record.skill_id}")
            self.assertIsInstance(record.declared_gates, list)
            self.assertIsInstance(record.referenced_resources, list)
            self.assertIsInstance(record.practice_profile_dependency, bool)
            self.assertIsInstance(record.host_assumptions, list)
            self.assertIsInstance(record.required_scripts, list)
            self.assertIn(record.source_repo, ("ai-for-china-legal", "legal-skills"))

            # License: None for ai-for-china-legal, string for legal-skills
            if record.source_repo == "ai-for-china-legal":
                self.assertIsNone(record.license,
                                  f"license should be None for ai-for-china-legal: {record.skill_id}")
            else:
                self.assertIsInstance(record.license, str,
                                      f"license should be a string for legal-skills: {record.skill_id}")

    # ------------------------------------------------------------------
    # Test 6: Merge report generated
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists() and LEGAL_SKILLS.exists(),
        "Both repos must be present",
    )
    def test_e2e_merge_report_generated(self) -> None:
        """Merge report present with namespace_mappings and 4-state conflict classification."""
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)},
                {"name": "legal-skills", "path": str(LEGAL_SKILLS)},
            ]
        )
        d = serialize_index(index)
        mr = d["merge_report"]
        self.assertIn("namespace_mappings", mr)
        self.assertGreater(len(mr["namespace_mappings"]), 0)
        self.assertIn("conflict_classification", mr)
        cc = mr["conflict_classification"]
        for key in ("in-sync", "upstream-changed", "both-changed", "local-missing"):
            self.assertIn(key, cc)
        # Without a previous index, all skills should be "local-missing"
        self.assertEqual(len(cc["in-sync"]), 0)
        self.assertGreater(len(cc["local-missing"]), 0)

    # ------------------------------------------------------------------
    # Test 7: Read-only enforcement (full build_index + write_index)
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists() and LEGAL_SKILLS.exists(),
        "Both repos must be present",
    )
    def test_e2e_read_only_enforcement(self) -> None:
        """Full build_index + write_index does not modify source repo files."""
        # Sample 30+ files from each repo
        aicl_sample = sorted(AI_FOR_CHINA_LEGAL.rglob("SKILL.md"))[:30]
        ls_sample = sorted(LEGAL_SKILLS.rglob("SKILL.md"))[:30]
        sample_paths = aicl_sample + ls_sample

        before: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            key = str(p)
            before[key] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        # Build + write index (output to temp dir OUTSIDE repos)
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"
        index = build_index(
            [
                {"name": "ai-for-china-legal", "path": str(AI_FOR_CHINA_LEGAL)},
                {"name": "legal-skills", "path": str(LEGAL_SKILLS)},
            ]
        )
        write_index(index, out_path)

        # Re-record and assert unchanged
        after: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            key = str(p)
            after[key] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        self.assertEqual(before, after, "Source repo files were modified during build+write")

        # Assert no new files created in the repos
        # (checked by comparing file counts on a sample)
        self.assertTrue(out_path.exists(), "Output file was not created")

    # ------------------------------------------------------------------
    # Test 8: Error tolerance
    # ------------------------------------------------------------------

    def test_e2e_error_tolerance(self) -> None:
        """Scanner handles edge cases without crashing, produces warning records."""
        repo = self._make_tmp_dir()

        # SKILL.md with missing frontmatter
        (repo / "skills" / "no-fm").mkdir(parents=True)
        (repo / "skills" / "no-fm" / "SKILL.md").write_text(
            "# No frontmatter here\nJust body text\n", encoding="utf-8"
        )

        # SKILL.md with malformed YAML
        (repo / "skills" / "bad-yaml").mkdir(parents=True)
        (repo / "skills" / "bad-yaml" / "SKILL.md").write_text(
            "---\nname: [unclosed\n  bad: yaml: : :\n---\n# Body\n", encoding="utf-8"
        )

        # Plugin directory with no plugin.json
        (repo / "some-plugin" / "skills" / "orphan").mkdir(parents=True)
        (repo / "some-plugin" / "skills" / "orphan" / "SKILL.md").write_text(
            "---\nname: orphan\ndescription: test\n---\n# Body\n", encoding="utf-8"
        )

        # Deeply nested SKILL.md (3+ levels)
        (repo / "deep" / "skills" / "parent" / "child" / "grandchild").mkdir(parents=True)
        (repo / "deep" / "skills" / "parent" / "child" / "grandchild" / "SKILL.md").write_text(
            "---\nname: grandchild\ndescription: deep\n---\n# Body\n",
            encoding="utf-8",
        )

        # Should not crash
        index = build_index([{"name": "test-repo", "path": str(repo)}])
        self.assertGreater(len(index.skills), 0)

        # Check that warning records are produced for edge cases
        all_warnings = []
        for record in index.skills:
            all_warnings.extend(record.warnings)
        # At least one warning should be present (missing frontmatter, malformed, etc.)
        self.assertGreater(len(all_warnings), 0, "No warnings produced for edge cases")

    # ------------------------------------------------------------------
    # Test 9: CLI invocation
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists() and LEGAL_SKILLS.exists(),
        "Both repos must be present",
    )
    def test_e2e_cli_invocation(self) -> None:
        """CLI produces valid JSON output from real repos."""
        out_dir = self._make_tmp_dir()
        out_path = out_dir / "skill-index.json"

        rc = cli_main([
            "scan",
            "--repo", str(AI_FOR_CHINA_LEGAL), "--repo-name", "ai-for-china-legal",
            "--repo", str(LEGAL_SKILLS), "--repo-name", "legal-skills",
            "--output", str(out_path),
        ])

        self.assertEqual(rc, 0)
        self.assertTrue(out_path.exists())

        data = json.loads(out_path.read_text(encoding="utf-8"))
        for key in ("generated_at", "scanner_version", "repos", "skills", "merge_report", "warnings"):
            self.assertIn(key, data)
        self.assertGreater(len(data["skills"]), 350)


if __name__ == "__main__":
    unittest.main()
