"""Read-only enforcement tests (SAFE-05).

Asserts that scanning never modifies source repo files.
Uses mtime (nanosecond precision) + SHA-256 content hash comparison
before and after scanning.

Also includes a static analysis test that verifies the scanner module
source code contains no write operations.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.scanner import scan_repo

AI_FOR_CHINA_LEGAL = Path("/home/sorawatcher/workspace/ai-for-china-legal")
LEGAL_SKILLS = Path("/home/sorawatcher/workspace/legal-skills")


def _record_file_states(root: Path) -> dict[str, tuple[int, str]]:
    """Walk *root* recursively and record (mtime_ns, sha256_hex) for each file.

    Excludes __pycache__ directories.
    """
    states: dict[str, tuple[int, str]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(root))
        mtime = path.stat().st_mtime_ns
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        states[rel] = (mtime, digest)
    return states


class TestReadOnly(unittest.TestCase):
    """Enforce SAFE-05: scanning must not modify source repo files."""

    def setUp(self) -> None:
        self._tmpdirs: list[Path] = []

    def tearDown(self) -> None:
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_tmp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self._tmpdirs.append(d)
        return d

    def test_scan_does_not_modify_files(self) -> None:
        """All file mtimes and SHA-256 hashes unchanged after scan."""
        root = self._make_tmp_dir()
        # Create a realistic mini repo
        (root / "commercial-legal" / "skills" / "contract-review").mkdir(parents=True)
        (root / "commercial-legal" / ".claude-plugin").mkdir(parents=True)
        (root / "commercial-legal").mkdir(exist_ok=True)

        skill_md = root / "commercial-legal" / "skills" / "contract-review" / "SKILL.md"
        skill_md.write_text(
            "---\nname: contract-review\ndescription: test\n---\n# Body\n",
            encoding="utf-8",
        )
        plugin_json = root / "commercial-legal" / ".claude-plugin" / "plugin.json"
        plugin_json.write_text('{"name": "commercial-legal"}', encoding="utf-8")
        claude_md = root / "commercial-legal" / "CLAUDE.md"
        claude_md.write_text("# Practice Profile", encoding="utf-8")
        refs = root / "commercial-legal" / "skills" / "_shared" / "refs.md"
        refs.parent.mkdir(parents=True, exist_ok=True)
        refs.write_text("# References", encoding="utf-8")
        scripts_dir = root / "commercial-legal" / "skills" / "contract-review" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "script.py").write_text("print('hello')", encoding="utf-8")

        before = _record_file_states(root)
        scan_repo(root, "ai-for-china-legal")
        after = _record_file_states(root)
        self.assertEqual(before, after, "File states changed after scan")

    def test_scan_does_not_create_temp_files(self) -> None:
        """No new files appear in the source repo after scanning."""
        root = self._make_tmp_dir()
        (root / "skills" / "court-sms").mkdir(parents=True)
        (root / "skills" / "court-sms" / "SKILL.md").write_text(
            "---\nname: court-sms\ndescription: test\n---\n# Body\n",
            encoding="utf-8",
        )

        before = _record_file_states(root)
        scan_repo(root, "legal-skills")
        after = _record_file_states(root)
        self.assertEqual(set(before.keys()), set(after.keys()),
                         "File set changed after scan — new files created")

    def test_scan_does_not_touch_git_dir(self) -> None:
        """.git/ contents unchanged after scan."""
        root = self._make_tmp_dir()
        (root / "skills" / "real").mkdir(parents=True)
        (root / "skills" / "real" / "SKILL.md").write_text(
            "---\nname: real\ndescription: test\n---\n# Body\n",
            encoding="utf-8",
        )
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "config").write_text("[core]\n  repositoryformatversion = 0\n", encoding="utf-8")

        before = _record_file_states(root)
        scan_repo(root, "ai-for-china-legal")
        after = _record_file_states(root)
        self.assertEqual(before, after, ".git/ or other files changed after scan")

    @unittest.skipUnless(
        AI_FOR_CHINA_LEGAL.exists(),
        "ai-for-china-legal repo not present",
    )
    def test_scan_real_ai_for_china_legal_read_only(self) -> None:
        """Scan a sample of ai-for-china-legal files — mtime + hash unchanged."""
        # Sample: first 20 SKILL.md files + all plugin.json files
        skill_files = sorted(AI_FOR_CHINA_LEGAL.rglob("SKILL.md"))[:20]
        plugin_jsons = sorted(AI_FOR_CHINA_LEGAL.rglob("plugin.json"))

        sample_paths = skill_files + plugin_jsons
        before: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            rel = str(p.relative_to(AI_FOR_CHINA_LEGAL))
            before[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        scan_repo(AI_FOR_CHINA_LEGAL, "ai-for-china-legal")

        after: dict[str, tuple[int, str]] = {}
        for p in sample_paths:
            rel = str(p.relative_to(AI_FOR_CHINA_LEGAL))
            after[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        self.assertEqual(before, after,
                         "ai-for-china-legal files were modified during scan")

    @unittest.skipUnless(
        LEGAL_SKILLS.exists(),
        "legal-skills repo not present",
    )
    def test_scan_real_legal_skills_read_only(self) -> None:
        """Scan a sample of legal-skills files — mtime + hash unchanged."""
        skill_files = sorted(LEGAL_SKILLS.rglob("SKILL.md"))[:20]

        before: dict[str, tuple[int, str]] = {}
        for p in skill_files:
            rel = str(p.relative_to(LEGAL_SKILLS))
            before[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        scan_repo(LEGAL_SKILLS, "legal-skills")

        after: dict[str, tuple[int, str]] = {}
        for p in skill_files:
            rel = str(p.relative_to(LEGAL_SKILLS))
            after[rel] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())

        self.assertEqual(before, after,
                         "legal-skills files were modified during scan")

    def test_scanner_module_has_no_write_calls(self) -> None:
        """Static analysis: scanner.py source contains no write operations."""
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "inkstatute_skill_index"
            / "scanner.py"
        )
        text = source.read_text(encoding="utf-8")
        forbidden = [
            "write_text",
            "write_bytes",
            ".touch(",
            ".unlink(",
            ".rmdir(",
            ".mkdir(",
            "os.rename",
            "shutil",
        ]
        for token in forbidden:
            self.assertNotIn(
                token,
                text,
                f"Scanner source contains forbidden write operation: {token}",
            )


if __name__ == "__main__":
    unittest.main()
