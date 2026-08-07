"""Unit tests for the 8-field metadata extractor.

Covers declared_gates (4 guardrails), referenced_resources,
practice_profile_dependency, host_assumptions, required_scripts,
license, full extract_metadata, and read-only static analysis.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_index.metadata_extractor import (
    SkillMetadata,
    _check_practice_profile_dependency,
    _extract_declared_gates,
    _extract_host_assumptions,
    _extract_license,
    _extract_referenced_resources,
    _extract_required_scripts,
    extract_metadata,
)
from inkstatute_skill_index.scanner import ScannedSkill


def _make_skill(
    *,
    body: str = "",
    frontmatter: dict | None = None,
    source_repo: str = "ai-for-china-legal",
    token_estimate: int = 100,
) -> ScannedSkill:
    """Build a minimal ScannedSkill for metadata testing."""
    return ScannedSkill(
        skill_id="test:test-skill",
        name="test-skill",
        source_repo=source_repo,
        plugin="test",
        relative_path="test/skills/test-skill/SKILL.md",
        absolute_path="/abs/test/skills/test-skill/SKILL.md",
        frontmatter=frontmatter or {},
        body=body,
        raw_text=body,
        token_estimate=token_estimate,
        depth=0,
    )


class TestMetadataExtractor(unittest.TestCase):
    """Verify all 8 SKILL-03 metadata fields are correctly extracted."""

    # ------------------------------------------------------------------
    # 1-6: declared_gates
    # ------------------------------------------------------------------
    def test_extract_declared_gates_research_gate(self) -> None:
        result = _extract_declared_gates("This skill uses research-gate for validation.")
        self.assertIn("research-gate", result)

    def test_extract_declared_gates_ask_user(self) -> None:
        result = _extract_declared_gates("Trigger ask-user when facts are missing.")
        self.assertIn("ask-user-enforcement", result)

    def test_extract_declared_gates_citation(self) -> None:
        result = _extract_declared_gates("Every claim needs citation to a statute.")
        self.assertIn("citation-audit", result)

    def test_extract_declared_gates_de_ai_polish(self) -> None:
        result = _extract_declared_gates("Apply de-ai-polish to remove AI tone.")
        self.assertIn("de-ai-polish", result)

    def test_extract_declared_gates_multiple(self) -> None:
        body = "research-gate and ask-user and citation and de-ai-polish all apply."
        result = _extract_declared_gates(body)
        self.assertIn("research-gate", result)
        self.assertIn("ask-user-enforcement", result)
        self.assertIn("citation-audit", result)
        self.assertIn("de-ai-polish", result)
        # No duplicates
        self.assertEqual(len(result), len(set(result)))

    def test_extract_declared_gates_none(self) -> None:
        result = _extract_declared_gates("A skill with no guardrail references.")
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # 7-9: referenced_resources
    # ------------------------------------------------------------------
    def test_extract_referenced_resources_shared(self) -> None:
        body = "See shared/references/document-structures.md for templates."
        result = _extract_referenced_resources(body)
        self.assertIn("shared/references/document-structures.md", result)

    def test_extract_referenced_resources_underscore_shared(self) -> None:
        body = "Follow _shared/legal-basis-conventions.md for citation format."
        result = _extract_referenced_resources(body)
        self.assertIn("_shared/legal-basis-conventions.md", result)

    def test_extract_referenced_resources_none(self) -> None:
        result = _extract_referenced_resources("No resource paths here.")
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # 10-11: practice_profile_dependency
    # ------------------------------------------------------------------
    def test_practice_profile_dependency_true(self) -> None:
        result = _check_practice_profile_dependency("Read CLAUDE.md for practice config.")
        self.assertTrue(result)

    def test_practice_profile_dependency_false(self) -> None:
        result = _check_practice_profile_dependency("no practice profile reference")
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # 12-13: host_assumptions
    # ------------------------------------------------------------------
    def test_extract_host_assumptions_trigger(self) -> None:
        body = "Triggered by /commercial-legal:contract-review when a contract is detected."
        result = _extract_host_assumptions(body, {})
        self.assertIn("/commercial-legal:contract-review", result)

    def test_extract_host_assumptions_argument_hint(self) -> None:
        result = _extract_host_assumptions("body text", {"argument-hint": "[合同]"})
        self.assertIn("[合同]", result)

    # ------------------------------------------------------------------
    # 14-15: required_scripts
    # ------------------------------------------------------------------
    def test_extract_required_scripts_from_body(self) -> None:
        body = "Run scripts/parse_contract.py to extract clauses."
        result = _extract_required_scripts(body, "/abs/SKILL.md", skill_dir=None)
        self.assertIn("scripts/parse_contract.py", result)

    def test_extract_required_scripts_from_dir(self) -> None:
        tmpdir = tempfile.mkdtemp()
        try:
            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "test.py").write_text("# test\n", encoding="utf-8")
            result = _extract_required_scripts("", str(tmpdir), skill_dir=Path(tmpdir))
            self.assertIn("scripts/test.py", result)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 16-17: license
    # ------------------------------------------------------------------
    def test_extract_license_from_frontmatter(self) -> None:
        result = _extract_license({"license": "MIT"}, "legal-skills")
        self.assertEqual(result, "MIT")

    def test_extract_license_missing_ai_for_china(self) -> None:
        result = _extract_license({}, "ai-for-china-legal")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # 18: extract_metadata full
    # ------------------------------------------------------------------
    def test_extract_metadata_full(self) -> None:
        body = (
            "Read CLAUDE.md for practice config. "
            "Uses research-gate and ask-user guardrails. "
            "See shared/references/document-structures.md. "
            "Triggered by /commercial-legal:contract-review. "
            "Run scripts/parse.py for processing."
        )
        frontmatter = {"argument-hint": "[合同文件]", "name": "contract-review"}
        skill = _make_skill(
            body=body,
            frontmatter=frontmatter,
            source_repo="ai-for-china-legal",
            token_estimate=3500,
        )
        md = extract_metadata(skill)
        self.assertIsInstance(md, SkillMetadata)
        self.assertEqual(md.token_estimate, 3500)
        self.assertIn("research-gate", md.declared_gates)
        self.assertIn("ask-user-enforcement", md.declared_gates)
        self.assertIn("shared/references/document-structures.md", md.referenced_resources)
        self.assertTrue(md.practice_profile_dependency)
        self.assertIn("/commercial-legal:contract-review", md.host_assumptions)
        self.assertIn("[合同文件]", md.host_assumptions)
        self.assertIn("scripts/parse.py", md.required_scripts)
        self.assertEqual(md.source_repo, "ai-for-china-legal")
        self.assertIsNone(md.license)

    # ------------------------------------------------------------------
    # 19: No write operations (read-only static analysis)
    # ------------------------------------------------------------------
    def test_no_write_operations(self) -> None:
        src_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "inkstatute_skill_index"
            / "metadata_extractor.py"
        )
        source = src_path.read_text(encoding="utf-8")
        forbidden = [
            "write_text",
            "write_bytes",
            ".touch(",
            ".unlink(",
            ".rmdir(",
            "os.rename",
            "shutil",
        ]
        for token in forbidden:
            self.assertNotIn(token, source, f"Forbidden write operation found: {token}")


if __name__ == "__main__":
    unittest.main()
