"""Unit tests for conflict_model.py — namespace isolation + 4-state classification + merge report.

Tests cover:
    - compute_content_hash determinism and uniqueness
    - build_namespace_mappings for legal-skills, ai-for-china-legal, shared, and the legal- prefix quirk
    - classify_conflicts for all 4 states (in-sync, upstream-changed, both-changed, local-missing)
    - local-meta-only collapsed into in-sync (4-state model, not 6-state)
    - build_merge_report structure and summary counts
    - _detect_local_modification read-only behavior (no marker creation)
    - _load_previous_index for missing and valid files
    - Static analysis: no write operations in conflict_model.py
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

from inkstatute_skill_index.conflict_model import (
    ConflictEntry,
    MergeReport,
    _detect_local_modification,
    _load_previous_index,
    build_merge_report,
    build_namespace_mappings,
    classify_conflicts,
    compute_content_hash,
)
from inkstatute_skill_index.scanner import ScannedSkill


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_skill(
    skill_id: str = "legal-test-skill",
    name: str = "test-skill",
    source_repo: str = "legal-skills",
    plugin: str | None = None,
    relative_path: str = "skills/test-skill/SKILL.md",
    absolute_path: str = "/tmp/test-skill/SKILL.md",
    frontmatter: dict | None = None,
    raw_text: str = "",
    token_estimate: int = 0,
    warnings: list[str] | None = None,
    depth: int = 0,
) -> ScannedSkill:
    """Create a minimal ScannedSkill for testing."""
    return ScannedSkill(
        skill_id=skill_id,
        name=name,
        source_repo=source_repo,
        plugin=plugin,
        relative_path=relative_path,
        absolute_path=absolute_path,
        frontmatter=frontmatter if frontmatter is not None else {},
        body="",
        raw_text=raw_text,
        token_estimate=token_estimate,
        warnings=warnings if warnings is not None else [],
        depth=depth,
    )


def _make_legal_skill(name: str = "court-sms", raw_text: str = "") -> ScannedSkill:
    """Create a legal-skills ScannedSkill."""
    return _make_skill(
        skill_id=f"legal-{name}",
        name=name,
        source_repo="legal-skills",
        plugin=None,
        relative_path=f"skills/{name}/SKILL.md",
        absolute_path=f"/tmp/{name}/SKILL.md",
        raw_text=raw_text,
    )


def _make_ai_skill(
    name: str = "contract-review",
    plugin: str = "commercial-legal",
    raw_text: str = "",
) -> ScannedSkill:
    """Create an ai-for-china-legal ScannedSkill."""
    return _make_skill(
        skill_id=f"{plugin}:{name}",
        name=name,
        source_repo="ai-for-china-legal",
        plugin=plugin,
        relative_path=f"{plugin}/skills/{name}/SKILL.md",
        absolute_path=f"/tmp/{name}/SKILL.md",
        raw_text=raw_text,
    )


def _make_shared_skill(name: str = "cn-law-research-gate", raw_text: str = "") -> ScannedSkill:
    """Create a shared ScannedSkill."""
    return _make_skill(
        skill_id=f"shared:{name}",
        name=name,
        source_repo="ai-for-china-legal",
        plugin="shared",
        relative_path=f"shared/research-gate/SKILL.md",
        absolute_path=f"/tmp/{name}/SKILL.md",
        raw_text=raw_text,
    )


class TestConflictModel(unittest.TestCase):
    """Tests for conflict_model.py."""

    # ------------------------------------------------------------------
    # 1. compute_content_hash
    # ------------------------------------------------------------------

    def test_compute_content_hash_deterministic(self) -> None:
        """Same input produces same hash."""
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_compute_content_hash_different_inputs(self) -> None:
        """Different inputs produce different hashes."""
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        self.assertNotEqual(h1, h2)

    # ------------------------------------------------------------------
    # 2-5. build_namespace_mappings
    # ------------------------------------------------------------------

    def test_namespace_mappings_legal_skills(self) -> None:
        """legal-skills skills get legal- prefix."""
        skills = [
            _make_legal_skill("court-sms"),
            _make_legal_skill("de-ai-polish"),
        ]
        mappings = build_namespace_mappings(skills)
        self.assertEqual(mappings["court-sms"], "legal-court-sms")
        self.assertEqual(mappings["de-ai-polish"], "legal-de-ai-polish")

    def test_namespace_mappings_ai_for_china_legal(self) -> None:
        """ai-for-china-legal skills get <plugin>: prefix."""
        skills = [
            _make_ai_skill("contract-review", "commercial-legal"),
            _make_ai_skill("risk-identification", "commercial-legal"),
        ]
        mappings = build_namespace_mappings(skills)
        self.assertEqual(mappings["contract-review"], "commercial-legal:contract-review")
        self.assertEqual(mappings["risk-identification"], "commercial-legal:risk-identification")

    def test_namespace_mappings_shared(self) -> None:
        """shared skills get shared: prefix."""
        skills = [_make_shared_skill("cn-law-research-gate")]
        mappings = build_namespace_mappings(skills)
        self.assertEqual(mappings["cn-law-research-gate"], "shared:cn-law-research-gate")

    def test_namespace_mappings_legal_prefix_quirk(self) -> None:
        """legal-skills skill whose name already starts with legal- gets doubled prefix.

        This matches sync_legal_skills.py's local_dir_name() quirk:
        'legal-qa-extractor' -> 'legal-legal-qa-extractor'.
        """
        skills = [_make_legal_skill("legal-qa-extractor")]
        mappings = build_namespace_mappings(skills)
        self.assertEqual(mappings["legal-qa-extractor"], "legal-legal-qa-extractor")

    # ------------------------------------------------------------------
    # 6-11. classify_conflicts
    # ------------------------------------------------------------------

    def test_classify_conflicts_no_previous_index(self) -> None:
        """previous_index=None -> all skills classified as local-missing."""
        skills = [_make_legal_skill("court-sms", raw_text="content")]
        entries = classify_conflicts(skills, previous_index=None)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].status, "local-missing")
        self.assertIsNone(entries[0].previous_hash)

    def test_classify_conflicts_in_sync(self) -> None:
        """Previous index with matching hash, no local modification -> in-sync."""
        content = "same content"
        hash_val = compute_content_hash(content)
        skill = _make_legal_skill("court-sms", raw_text=content)
        prev_index = {
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": hash_val,
                    "has_local_modification": False,
                }
            ]
        }
        entries = classify_conflicts([skill], previous_index=prev_index)
        self.assertEqual(entries[0].status, "in-sync")
        self.assertEqual(entries[0].previous_hash, hash_val)
        self.assertFalse(entries[0].has_local_modification)

    def test_classify_conflicts_upstream_changed(self) -> None:
        """Previous index with different hash, no local modification -> upstream-changed."""
        content = "new content"
        skill = _make_legal_skill("court-sms", raw_text=content)
        prev_index = {
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": "0" * 64,  # different hash
                    "has_local_modification": False,
                }
            ]
        }
        entries = classify_conflicts([skill], previous_index=prev_index)
        self.assertEqual(entries[0].status, "upstream-changed")
        self.assertFalse(entries[0].has_local_modification)

    def test_classify_conflicts_both_changed(self) -> None:
        """Previous index with different hash, local modification detected -> both-changed."""
        content = "modified content"
        skill = _make_legal_skill("court-sms", raw_text=content)
        prev_index = {
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": "0" * 64,  # different hash
                    "has_local_modification": True,
                }
            ]
        }
        entries = classify_conflicts([skill], previous_index=prev_index)
        self.assertEqual(entries[0].status, "both-changed")
        self.assertTrue(entries[0].has_local_modification)

    def test_classify_conflicts_local_meta_only_collapsed(self) -> None:
        """Previous index with matching hash but local modification -> in-sync.

        The local-meta-only state from sync_legal_skills.py is collapsed
        into in-sync in the 4-state model.
        """
        content = "same content"
        hash_val = compute_content_hash(content)
        skill = _make_legal_skill("court-sms", raw_text=content)
        prev_index = {
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": hash_val,
                    "has_local_modification": True,  # local meta-only
                }
            ]
        }
        entries = classify_conflicts([skill], previous_index=prev_index)
        self.assertEqual(entries[0].status, "in-sync")

    # ------------------------------------------------------------------
    # 12-13. build_merge_report
    # ------------------------------------------------------------------

    def test_build_merge_report_structure(self) -> None:
        """build_merge_report returns MergeReport with correct structure."""
        skills = [
            _make_legal_skill("court-sms", raw_text="content A"),
            _make_ai_skill("contract-review", raw_text="content B"),
        ]
        report = build_merge_report(skills, previous_index=None)
        self.assertIsInstance(report, MergeReport)
        self.assertIn("court-sms", report.namespace_mappings)
        self.assertIn("contract-review", report.namespace_mappings)
        # conflict_classification has exactly 4 keys
        expected_keys = {"in-sync", "upstream-changed", "both-changed", "local-missing"}
        self.assertEqual(set(report.conflict_classification.keys()), expected_keys)
        self.assertEqual(report.total_skills, 2)
        # summary has 4 keys
        self.assertEqual(set(report.summary.keys()), expected_keys)

    def test_build_merge_report_summary_counts(self) -> None:
        """Summary counts match the number of skills in each category."""
        content_a = "content A"
        hash_a = compute_content_hash(content_a)
        skills = [
            _make_legal_skill("court-sms", raw_text=content_a),       # in-sync
            _make_legal_skill("de-ai-polish", raw_text="changed"),    # upstream-changed
            _make_legal_skill("git-batch-commit", raw_text="new"),    # local-missing
        ]
        prev_index = {
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": hash_a,
                    "has_local_modification": False,
                },
                {
                    "skill_id": "legal-de-ai-polish",
                    "content_hash": "0" * 64,
                    "has_local_modification": False,
                },
                # git-batch-commit not in previous index -> local-missing
            ]
        }
        report = build_merge_report(skills, previous_index=prev_index)
        self.assertEqual(report.summary["in-sync"], 1)
        self.assertEqual(report.summary["upstream-changed"], 1)
        self.assertEqual(report.summary["local-missing"], 1)
        self.assertEqual(report.summary["both-changed"], 0)
        self.assertEqual(report.total_skills, 3)
        # Verify skill_ids in each category
        self.assertIn("legal-court-sms", report.conflict_classification["in-sync"])
        self.assertIn("legal-de-ai-polish", report.conflict_classification["upstream-changed"])
        self.assertIn("legal-git-batch-commit", report.conflict_classification["local-missing"])

    # ------------------------------------------------------------------
    # 14-16. _detect_local_modification
    # ------------------------------------------------------------------

    def test_detect_local_modification_no_marker(self) -> None:
        """No marker files -> False."""
        tmpdir = tempfile.mkdtemp()
        skill_md = os.path.join(tmpdir, "SKILL.md")
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write("test content")
        skill = _make_skill(
            skill_id="legal-test",
            name="test",
            source_repo="legal-skills",
            absolute_path=skill_md,
        )
        result = _detect_local_modification(skill)
        self.assertFalse(result)

    def test_detect_local_modification_with_changelog(self) -> None:
        """LOCAL_CHANGELOG.md present -> True."""
        tmpdir = tempfile.mkdtemp()
        skill_md = os.path.join(tmpdir, "SKILL.md")
        changelog = os.path.join(tmpdir, "LOCAL_CHANGELOG.md")
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write("test content")
        with open(changelog, "w", encoding="utf-8") as f:
            f.write("# Local changelog\n- modified prompt")
        skill = _make_skill(
            skill_id="legal-test",
            name="test",
            source_repo="legal-skills",
            absolute_path=skill_md,
        )
        result = _detect_local_modification(skill)
        self.assertTrue(result)

    def test_detect_local_modification_does_not_create_markers(self) -> None:
        """After calling _detect_local_modification, no new files are created."""
        tmpdir = tempfile.mkdtemp()
        skill_md = os.path.join(tmpdir, "SKILL.md")
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write("test content")
        files_before = set(os.listdir(tmpdir))
        skill = _make_skill(
            skill_id="legal-test",
            name="test",
            source_repo="legal-skills",
            absolute_path=skill_md,
        )
        _detect_local_modification(skill)
        files_after = set(os.listdir(tmpdir))
        self.assertEqual(files_before, files_after,
                         f"Files created: {files_after - files_before}")

    # ------------------------------------------------------------------
    # 17. Static analysis: no write operations
    # ------------------------------------------------------------------

    def test_no_write_operations(self) -> None:
        """Static analysis: conflict_model.py has no write operations."""
        source_path = pathlib.Path(__file__).parent.parent / "src" / "inkstatute_skill_index" / "conflict_model.py"
        source = source_path.read_text(encoding="utf-8")
        forbidden = [
            "write_text",
            "write_bytes",
            "shutil.copytree",
            "git checkout",
            ".touch(",
            ".unlink(",
        ]
        for op in forbidden:
            self.assertNotIn(op, source, f"Forbidden operation found in source: {op}")

    # ------------------------------------------------------------------
    # 18-19. _load_previous_index
    # ------------------------------------------------------------------

    def test_load_previous_index_missing_file(self) -> None:
        """_load_previous_index on non-existent path returns None."""
        result = _load_previous_index(pathlib.Path("/nonexistent/path/previous_index.json"))
        self.assertIsNone(result)

    def test_load_previous_index_valid_file(self) -> None:
        """_load_previous_index on a valid JSON file returns the parsed dict."""
        tmpdir = tempfile.mkdtemp()
        index_path = pathlib.Path(tmpdir) / "previous_index.json"
        prev_data = {
            "generated_at": "2026-08-01T00:00:00Z",
            "scanner_version": "1.0.0",
            "skills": [
                {
                    "skill_id": "legal-court-sms",
                    "content_hash": "abc123",
                    "has_local_modification": False,
                    "version": "1.5.0",
                },
            ],
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(prev_data, f)
        result = _load_previous_index(index_path)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn("skills", result)
        self.assertEqual(result["skills"][0]["skill_id"], "legal-court-sms")


if __name__ == "__main__":
    unittest.main()
