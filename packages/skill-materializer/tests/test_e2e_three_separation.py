"""End-to-end three-separation verification test.

Verifies the metadata/body/tools three-separation principle across the
full materialization flow:

1. Loads a fixture skill-index.json with 3-5 skills (varying token
   estimates, some with scripts/, some with host assumptions)
2. Produces a routing manifest via ``produce_routing_manifest()``
3. Materializes to Hermes layout
4. Materializes to ACP layout
5. Injects a body with budget
6. Asserts:
   - Routing manifests contain no body text
   - Bodies are read on-demand from source
   - Tool dependencies are metadata-only
   - Symlinks/copies point to source repo paths (not routing manifest)
   - ACP rewritten SKILL.md files differ from source
   - Budget trimming works within constraints
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.acp_materializer import materialize_acp
from inkstatute_skill_materializer.body_injector import (
    SkillBodyInjector,
    read_skill_body,
)
from inkstatute_skill_materializer.hermes_materializer import materialize_hermes
from inkstatute_skill_materializer.three_separation import produce_routing_manifest


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
    """Build fixture repos and a skill-index.json with 5 skills.

    Skills vary in:
    - Token estimates (300, 500, 800, 1200, 2000)
    - Some with scripts/ directories
    - Some with host assumptions (trigger patterns, ask_user, CLAUDE.md)
    - Mix of orchestration and leaf types
    """
    acl = base_dir / "ai-for-china-legal"
    ls = base_dir / "legal-skills"

    # Skill 1: orchestration, no scripts, with host assumptions
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "contract-review",
        "contract-review",
        "Review a contract for risks.",
        extra_body="""This is the main orchestration skill.

## research-gate

Before concluding, search for relevant statutes.

## Orchestration Table

| Order | Sub-skill | Trigger |
|-------|-----------|---------|
| 1 | risk-identification | /commercial-legal:risk-identification |
| 2 | clause-revision | /commercial-legal:clause-revision |

## Examples

Some example usage here.

## Appendix A: Reference Tables

| Statute | Article |
|---------|---------|
| Civil Code | Art. 506 |
""",
    )

    # Skill 2: leaf, with scripts/
    _write_skill_md(
        acl / "ai-governance" / "skills" / "algorithm-filing",
        "algorithm-filing",
        "File an algorithm registration.",
        extra_body="File the algorithm registration form.",
    )
    scripts_dir = acl / "ai-governance" / "skills" / "algorithm-filing" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "filing_helper.py").write_text("# helper script\n", encoding="utf-8")

    # Skill 3: leaf, with host assumptions (trigger + ask_user + CLAUDE.md)
    _write_skill_md(
        acl / "commercial-legal" / "skills" / "risk-identification",
        "risk-identification",
        "Identify risks in a contract.",
        extra_body="""Use /commercial-legal:contract-review for context.
When facts are missing, ask_user for clarification.
Read commercial-legal/CLAUDE.md for practice profile.
""",
    )

    # Skill 4: legal-skills, no scripts, no host assumptions
    _write_skill_md(
        ls / "skills" / "de-ai-polish",
        "de-ai-polish",
        "De-AI polish for legal text.",
        extra_body="Polish AI-generated text to sound more natural.",
    )

    # Skill 5: legal-skills, with scripts/
    _write_skill_md(
        ls / "skills" / "court-sms",
        "court-sms",
        "Send court SMS notifications.",
        extra_body="Send SMS notifications for court dates.",
    )
    scripts_dir2 = ls / "skills" / "court-sms" / "scripts"
    scripts_dir2.mkdir(parents=True, exist_ok=True)
    (scripts_dir2 / "sms_sender.py").write_text("# SMS sender\n", encoding="utf-8")

    skills = [
        {
            "skill_id": "commercial-legal:contract-review",
            "name": "contract-review",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/contract-review/SKILL.md",
            "skill_type": "orchestration",
            "parent_skill": None,
            "child_skills": ["risk-identification", "clause-revision"],
            "description": "Review a contract for risks.",
            "frontmatter": {"name": "contract-review", "description": "Review a contract for risks."},
            "token_estimate": 2000,
            "declared_gates": ["research-gate", "ask-user-enforcement"],
            "referenced_resources": [],
            "practice_profile_dependency": True,
            "host_assumptions": ["/commercial-legal:risk-identification"],
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
            "skill_id": "commercial-legal:risk-identification",
            "name": "risk-identification",
            "source_repo": "ai-for-china-legal",
            "plugin": "commercial-legal",
            "relative_path": "commercial-legal/skills/risk-identification/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": "commercial-legal:contract-review",
            "child_skills": [],
            "description": "Identify risks in a contract.",
            "frontmatter": {"name": "risk-identification", "description": "Identify risks in a contract."},
            "token_estimate": 500,
            "declared_gates": ["ask-user-enforcement"],
            "referenced_resources": [],
            "practice_profile_dependency": True,
            "host_assumptions": ["/commercial-legal:contract-review", "ask_user", "CLAUDE.md"],
            "required_scripts": [],
            "license": None,
            "version": "1.0.0",
            "content_hash": "ghi789",
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
            "content_hash": "jkl012",
            "has_local_modification": False,
            "warnings": [],
        },
        {
            "skill_id": "legal-court-sms",
            "name": "court-sms",
            "source_repo": "legal-skills",
            "plugin": None,
            "relative_path": "skills/court-sms/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": None,
            "child_skills": [],
            "description": "Send court SMS notifications.",
            "frontmatter": {"name": "court-sms", "description": "Send court SMS notifications."},
            "token_estimate": 1200,
            "declared_gates": [],
            "referenced_resources": [],
            "practice_profile_dependency": False,
            "host_assumptions": [],
            "required_scripts": ["scripts/sms_sender.py"],
            "license": "MIT",
            "version": "1.0.0",
            "content_hash": "mno345",
            "has_local_modification": False,
            "warnings": [],
        },
    ]

    repos_meta = {
        "ai-for-china-legal": {"path": str(acl), "commit": None, "skill_count": 3},
        "legal-skills": {"path": str(ls), "commit": None, "skill_count": 2},
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


# ---------------------------------------------------------------------------
# E2E Three-Separation Tests
# ---------------------------------------------------------------------------


class TestE2EThreeSeparation(unittest.TestCase):
    """End-to-end three-separation verification."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_repos_and_index(self.base_dir)
        self.routing_manifest_path = self.base_dir / "routing-manifest.json"
        self.hermes_output = self.base_dir / "hermes-output"
        self.acp_output = self.base_dir / "acp-output"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # 1. Routing manifest: no body text
    # ------------------------------------------------------------------

    def test_routing_manifest_no_body_fields(self) -> None:
        """Routing manifest has no body, content, raw_text, or frontmatter fields."""
        produce_routing_manifest(self.index_path, self.routing_manifest_path)
        data = json.loads(self.routing_manifest_path.read_text(encoding="utf-8"))

        excluded_fields = {"body", "content", "raw_text", "frontmatter", "content_hash"}
        for record in data["skills"]:
            for field_name in excluded_fields:
                self.assertNotIn(
                    field_name, record,
                    f"Excluded field '{field_name}' found in routing record "
                    f"for skill '{record.get('skill_id', '?')}'",
                )

    def test_routing_manifest_has_5_skills(self) -> None:
        """Routing manifest contains all 5 skills from the fixture index."""
        produce_routing_manifest(self.index_path, self.routing_manifest_path)
        data = json.loads(self.routing_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["skill_count"], 5)
        self.assertEqual(len(data["skills"]), 5)

    # ------------------------------------------------------------------
    # 2. Hermes materialization: symlinks/copies point to source repo
    # ------------------------------------------------------------------

    def test_hermes_symlinks_point_to_source(self) -> None:
        """Hermes symlinks/copies point to source repo paths, not routing manifest."""
        # First produce routing manifest
        produce_routing_manifest(self.index_path, self.routing_manifest_path)

        # Then materialize to Hermes
        result = materialize_hermes(self.index_path, self.hermes_output, profile_name="test")
        self.assertEqual(result.materialized_count, 5)
        self.assertEqual(len(result.errors), 0, f"Errors: {result.errors}")

        skills_dir = self.hermes_output / "profiles" / "test" / "skills"

        # Verify each skill directory points to source repo, not routing manifest
        for entry in skills_dir.iterdir():
            if entry.is_symlink():
                target = os.readlink(entry)
                # Symlink target should point to source repo, not routing manifest
                self.assertNotIn(
                    "routing-manifest", str(target),
                    f"Symlink {entry.name} points to routing manifest: {target}",
                )
                # Should point to a source repo path
                self.assertTrue(
                    "ai-for-china-legal" in str(target) or "legal-skills" in str(target),
                    f"Symlink {entry.name} does not point to source repo: {target}",
                )

    def test_hermes_skills_have_skill_md(self) -> None:
        """Each materialized Hermes skill has a loadable SKILL.md."""
        materialize_hermes(self.index_path, self.hermes_output, profile_name="test")
        skills_dir = self.hermes_output / "profiles" / "test" / "skills"
        for entry in skills_dir.iterdir():
            skill_md = entry / "SKILL.md"
            self.assertTrue(skill_md.exists(), f"SKILL.md missing in {entry}")

    # ------------------------------------------------------------------
    # 3. ACP materialization: host assumption rewriting
    # ------------------------------------------------------------------

    def test_acp_rewritten_skills_differ_from_source(self) -> None:
        """ACP rewritten SKILL.md files differ from source (host assumptions rewritten)."""
        result = materialize_acp(self.index_path, self.acp_output)
        self.assertEqual(result.materialized_count, 5)
        self.assertEqual(len(result.errors), 0, f"Errors: {result.errors}")

        # risk-identification has host assumptions → should be rewritten
        risk_skill = self.acp_output / "skills" / "commercial-legal-risk-identification"
        self.assertTrue(risk_skill.exists(), f"Rewritten skill dir not found: {risk_skill}")

        # It should be a real directory (not symlink) since content was rewritten
        self.assertFalse(
            risk_skill.is_symlink(),
            "Rewritten skill should not be a symlink",
        )

        # The rewritten SKILL.md should differ from source
        source_md = (
            self.base_dir / "ai-for-china-legal"
            / "commercial-legal" / "skills" / "risk-identification" / "SKILL.md"
        )
        rewritten_md = risk_skill / "SKILL.md"
        source_text = source_md.read_text(encoding="utf-8")
        rewritten_text = rewritten_md.read_text(encoding="utf-8")
        self.assertNotEqual(
            source_text, rewritten_text,
            "Rewritten SKILL.md should differ from source",
        )

        # Verify trigger pattern was rewritten
        self.assertNotIn("/commercial-legal:contract-review", rewritten_text)
        # Verify ask_user was rewritten to elicitation
        self.assertNotIn("ask_user", rewritten_text.lower())

    def test_acp_non_rewritten_skills_are_symlinked(self) -> None:
        """ACP skills without host assumptions are symlinked (zero-copy)."""
        materialize_acp(self.index_path, self.acp_output)
        skills_dir = self.acp_output / "skills"

        # de-ai-polish has no host assumptions → should be symlinked
        de_ai = skills_dir / "legal-de-ai-polish"
        self.assertTrue(de_ai.exists())
        # Should be a symlink (no host assumptions, no scripts)
        self.assertTrue(
            de_ai.is_symlink(),
            f"Non-rewritten skill should be symlinked: {de_ai}",
        )

    def test_acp_rewrite_report_exists(self) -> None:
        """ACP materialization produces a rewrite-report.json."""
        materialize_acp(self.index_path, self.acp_output)
        report_path = self.acp_output / "rewrite-report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("total_rewrites", report)
        self.assertIn("entries", report)
        # risk-identification has trigger + ask_user → at least some rewrites
        self.assertGreater(report["total_rewrites"], 0)

    # ------------------------------------------------------------------
    # 4. Body injection with budget
    # ------------------------------------------------------------------

    def test_body_injection_within_budget(self) -> None:
        """Injecting a body with budget_tokens=5000 stays within budget."""
        result = read_skill_body(
            skill_id="commercial-legal:contract-review",
            index_path=self.index_path,
            budget_tokens=5000,
        )
        self.assertLessEqual(
            result.injected_token_estimate, 5000,
            f"Injected tokens ({result.injected_token_estimate}) exceed budget (5000)",
        )

    def test_body_injection_trims_large_skills(self) -> None:
        """Skills larger than the budget have non-empty trimmed_sections."""
        # contract-review has token_estimate=2000 in index, but actual body
        # may be different. Use a small budget to force trimming.
        result = read_skill_body(
            skill_id="commercial-legal:contract-review",
            index_path=self.index_path,
            budget_tokens=200,
        )
        # If the body is larger than 200 tokens, trimmed_sections should be non-empty
        if result.original_token_estimate > 200:
            self.assertGreater(
                len(result.trimmed_sections), 0,
                "trimmed_sections should be non-empty for skills exceeding budget",
            )

    def test_body_injection_preserves_protected_sections(self) -> None:
        """Body injection preserves frontmatter and description (protected)."""
        result = read_skill_body(
            skill_id="commercial-legal:contract-review",
            index_path=self.index_path,
            budget_tokens=5000,
        )
        # The injected text should still contain frontmatter
        self.assertIn("---", result.injected_text)
        # Should contain the skill name
        self.assertIn("contract-review", result.injected_text)

    # ------------------------------------------------------------------
    # 5. Tool dependencies are metadata-only
    # ------------------------------------------------------------------

    def test_required_scripts_are_string_lists(self) -> None:
        """required_scripts in routing manifest is a list of script names (strings), not contents."""
        produce_routing_manifest(self.index_path, self.routing_manifest_path)
        data = json.loads(self.routing_manifest_path.read_text(encoding="utf-8"))

        for record in data["skills"]:
            scripts = record.get("required_scripts", [])
            for script in scripts:
                self.assertIsInstance(
                    script, str,
                    f"required_scripts entry is not a string: {script} "
                    f"(skill: {record.get('skill_id', '?')})",
                )
                # Should be a path/name, not file contents
                self.assertFalse(
                    "\n" in script,
                    f"required_scripts entry contains newlines (file contents?): {script[:50]}",
                )

    def test_routing_manifest_contains_no_body_text(self) -> None:
        """Routing manifest does not contain body text from any source SKILL.md.

        For real-world skills (2K-20K tokens), the metadata-only manifest is
        much smaller than the source bodies.  For tiny fixture skills, the
        JSON overhead may exceed the body size, so we verify the principle
        by checking that no body text appears in the manifest.
        """
        produce_routing_manifest(self.index_path, self.routing_manifest_path)
        manifest_text = self.routing_manifest_path.read_text(encoding="utf-8")

        # Read each source SKILL.md and verify its body text is NOT in the manifest
        for root in (self.base_dir / "ai-for-china-legal", self.base_dir / "legal-skills"):
            for f in root.rglob("SKILL.md"):
                body = f.read_text(encoding="utf-8")
                # Extract a distinctive body fragment (after frontmatter)
                # and verify it does not appear in the manifest
                lines = body.split("\n")
                # Skip frontmatter (--- ... ---) and find a body line
                body_fragments: list[str] = []
                in_frontmatter = False
                for line in lines:
                    if line.strip() == "---":
                        in_frontmatter = not in_frontmatter
                        continue
                    if in_frontmatter:
                        continue
                    if line.strip() and not line.startswith("#"):
                        body_fragments.append(line.strip())

                # Check at least one body fragment is NOT in the manifest
                if body_fragments:
                    # The manifest should not contain the full body text
                    # Check a distinctive fragment
                    fragment = body_fragments[0]
                    if len(fragment) > 10:
                        self.assertNotIn(
                            fragment, manifest_text,
                            f"Body text from {f} found in routing manifest: '{fragment}'",
                        )

    # ------------------------------------------------------------------
    # 6. Self-built core path: on-demand body read without materialization
    # ------------------------------------------------------------------

    def test_on_demand_body_read_without_materialization(self) -> None:
        """read_skill_body() reads directly from source path in index — no materialization needed."""
        # This is the self-built core path (success criterion 3):
        # "自研 core 路径不需物化——直接读索引 + 按需读正文"
        result = read_skill_body(
            skill_id="legal-de-ai-polish",
            index_path=self.index_path,
            budget_tokens=10000,
        )
        # Should successfully read the body
        self.assertGreater(len(result.injected_text), 0)
        self.assertGreater(result.original_token_estimate, 0)
        # No materialization step was needed — read_skill_body reads from index directly

    def test_on_demand_body_read_uses_source_path(self) -> None:
        """read_skill_body reads from the source_path in the index, not from any materialized output."""
        # Verify no Hermes or ACP output exists
        self.assertFalse(self.hermes_output.exists())
        self.assertFalse(self.acp_output.exists())

        # read_skill_body should still work (reads from source, not materialized output)
        result = read_skill_body(
            skill_id="ai-governance:algorithm-filing",
            index_path=self.index_path,
            budget_tokens=10000,
        )
        self.assertGreater(len(result.injected_text), 0)
        self.assertIn("algorithm-filing", result.injected_text)

    # ------------------------------------------------------------------
    # 7. Full flow integration
    # ------------------------------------------------------------------

    def test_full_flow_index_to_injection(self) -> None:
        """Full flow: index → routing manifest → on-demand body read → trimmed injection.

        This verifies the complete three-separation pipeline:
        1. Index contains metadata + source paths (no bodies in routing)
        2. Routing manifest is metadata-only
        3. Body is read on-demand from source when needed
        4. Budget trimming produces deterministic result
        """
        # Step 1: Produce routing manifest (metadata only)
        produce_routing_manifest(self.index_path, self.routing_manifest_path)
        manifest_data = json.loads(self.routing_manifest_path.read_text(encoding="utf-8"))

        # Step 2: Verify manifest has no body text
        for record in manifest_data["skills"]:
            self.assertNotIn("body", record)
            self.assertNotIn("content", record)
            self.assertNotIn("raw_text", record)

        # Step 3: Read body on-demand from source (self-built core path)
        result = read_skill_body(
            skill_id="commercial-legal:contract-review",
            index_path=self.index_path,
            budget_tokens=5000,
        )

        # Step 4: Verify trimmed injection
        self.assertLessEqual(result.injected_token_estimate, 5000)
        self.assertGreater(len(result.injected_text), 0)

        # Step 5: Verify determinism — same input + same budget → same output
        result2 = read_skill_body(
            skill_id="commercial-legal:contract-review",
            index_path=self.index_path,
            budget_tokens=5000,
        )
        self.assertEqual(result.injected_text, result2.injected_text)
        self.assertEqual(
            result.injected_token_estimate,
            result2.injected_token_estimate,
        )


if __name__ == "__main__":
    unittest.main()
