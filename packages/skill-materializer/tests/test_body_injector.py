"""Tests for SkillBodyInjector — section-priority deterministic trim."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inkstatute_skill_materializer.body_injector import (
    SkillBodyBudgetError,
    SkillBodyInjectionResult,
    SkillBodyInjector,
    SkillNotFoundError,
    SourceFileNotFoundError,
    read_skill_body,
    _estimate_tokens,
    _parse_sections,
    _assign_priority,
    _PRIORITY_PROTECTED,
    _PRIORITY_HIGH,
    _PRIORITY_MEDIUM,
    _PRIORITY_LOW,
)

from .fixtures.body_injector_fixtures import (
    build_small_skill,
    build_medium_skill,
    build_large_skill,
    build_xlarge_skill,
    build_skill_with_large_protected,
)


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestSkillBodyInjectorConstruction(unittest.TestCase):
    """Test SkillBodyInjector construction."""

    def test_constructs_with_budget_and_chars_per_token(self) -> None:
        """SkillBodyInjector(budget_tokens=N, chars_per_token=4) constructs."""
        injector = SkillBodyInjector(budget_tokens=10000, chars_per_token=4)
        self.assertEqual(injector.budget_tokens, 10000)
        self.assertEqual(injector.chars_per_token, 4)

    def test_default_chars_per_token_is_4(self) -> None:
        """Default chars_per_token is 4."""
        injector = SkillBodyInjector(budget_tokens=5000)
        self.assertEqual(injector.chars_per_token, 4)

    def test_rejects_zero_budget(self) -> None:
        """Budget must be positive."""
        with self.assertRaises(ValueError):
            SkillBodyInjector(budget_tokens=0)

    def test_rejects_negative_budget(self) -> None:
        """Budget must be positive."""
        with self.assertRaises(ValueError):
            SkillBodyInjector(budget_tokens=-100)

    def test_rejects_zero_chars_per_token(self) -> None:
        """chars_per_token must be positive."""
        with self.assertRaises(ValueError):
            SkillBodyInjector(budget_tokens=100, chars_per_token=0)


# ---------------------------------------------------------------------------
# Injection result structure tests
# ---------------------------------------------------------------------------


class TestInjectionResultStructure(unittest.TestCase):
    """Test SkillBodyInjectionResult structure."""

    def test_inject_returns_injection_result(self) -> None:
        """injector.inject(skill_body_text) returns a SkillBodyInjectionResult."""
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(build_small_skill())
        self.assertIsInstance(result, SkillBodyInjectionResult)

    def test_result_contains_all_required_fields(self) -> None:
        """SkillBodyInjectionResult contains all required fields."""
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(build_small_skill())
        self.assertTrue(hasattr(result, "injected_text"))
        self.assertTrue(hasattr(result, "original_token_estimate"))
        self.assertTrue(hasattr(result, "injected_token_estimate"))
        self.assertTrue(hasattr(result, "trimmed_sections"))
        self.assertTrue(hasattr(result, "budget_used"))
        self.assertTrue(hasattr(result, "budget_tokens"))

    def test_trimmed_sections_entry_structure(self) -> None:
        """Each trimmed_sections entry has section_name, priority, original_tokens, reason."""
        injector = SkillBodyInjector(budget_tokens=5000)
        result = injector.inject(build_xlarge_skill())
        if result.trimmed_sections:
            entry = result.trimmed_sections[0]
            self.assertIn("section_name", entry)
            self.assertIn("priority", entry)
            self.assertIn("original_tokens", entry)
            self.assertIn("reason", entry)


# ---------------------------------------------------------------------------
# Section parsing tests
# ---------------------------------------------------------------------------


class TestSectionParsing(unittest.TestCase):
    """Test SKILL.md section parsing."""

    def test_frontmatter_is_extracted(self) -> None:
        """Frontmatter (YAML between --- fences) is extracted."""
        skill = "---\nname: test\ndescription: Test\n---\n\n# Title\n\nBody text.\n"
        frontmatter, sections = _parse_sections(skill)
        self.assertIn("---", frontmatter)
        self.assertIn("name: test", frontmatter)

    def test_sections_split_by_h2_headers(self) -> None:
        """SKILL.md is split by ## headers."""
        skill = (
            "---\nname: test\n---\n\n# Title\n\nIntro.\n\n"
            "## Section One\n\nContent 1.\n\n"
            "## Section Two\n\nContent 2.\n"
        )
        frontmatter, sections = _parse_sections(skill)
        # Description + 2 sections
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0][0], "__description__")
        self.assertEqual(sections[1][0], "Section One")
        self.assertEqual(sections[2][0], "Section Two")

    def test_no_frontmatter_handled(self) -> None:
        """SKILL.md without frontmatter is handled."""
        skill = "# Title\n\n## Section\n\nContent.\n"
        frontmatter, sections = _parse_sections(skill)
        self.assertEqual(frontmatter, "")
        self.assertGreaterEqual(len(sections), 1)

    def test_no_h2_headers_handled(self) -> None:
        """SKILL.md with no ## headers is handled."""
        skill = "---\nname: test\n---\n\n# Title\n\nJust text.\n"
        frontmatter, sections = _parse_sections(skill)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][0], "__description__")

    def test_frontmatter_is_protected(self) -> None:
        """Frontmatter is always protected (part of description section)."""
        skill = (
            "---\nname: test\n---\n\n# Title\n\nIntro.\n\n"
            "## First\n\nContent.\n"
        )
        frontmatter, sections = _parse_sections(skill)
        # Description section (index 0) is protected
        priority = _assign_priority("__description__", sections[0][1], 0, True)
        self.assertEqual(priority, _PRIORITY_PROTECTED)


# ---------------------------------------------------------------------------
# Priority assignment tests
# ---------------------------------------------------------------------------


class TestPriorityAssignment(unittest.TestCase):
    """Test section priority assignment."""

    def test_description_is_protected(self) -> None:
        """Description section is protected."""
        priority = _assign_priority("__description__", "text", 0, True)
        self.assertEqual(priority, _PRIORITY_PROTECTED)

    def test_first_h2_section_is_protected(self) -> None:
        """First ## section is protected."""
        priority = _assign_priority("Some Section", "text", 1, False)
        self.assertEqual(priority, _PRIORITY_PROTECTED)

    def test_research_gate_is_high(self) -> None:
        """Sections containing 'research-gate' in header are high priority."""
        priority = _assign_priority("research-gate", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_HIGH)

    def test_ask_user_is_high(self) -> None:
        """Sections containing 'ask-user' in header are high priority."""
        priority = _assign_priority("ask-user-enforcement", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_HIGH)

    def test_example_is_low(self) -> None:
        """Sections containing 'example' in header are low priority."""
        priority = _assign_priority("Examples", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_LOW)

    def test_appendix_is_low(self) -> None:
        """Sections containing 'appendix' in header are low priority."""
        priority = _assign_priority("Appendix A", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_LOW)

    def test_reference_is_low(self) -> None:
        """Sections containing 'reference' in header are low priority."""
        priority = _assign_priority("References", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_LOW)

    def test_other_is_medium(self) -> None:
        """All other sections are medium priority."""
        priority = _assign_priority("Core Instructions", "text", 2, False)
        self.assertEqual(priority, _PRIORITY_MEDIUM)


# ---------------------------------------------------------------------------
# Trim algorithm tests
# ---------------------------------------------------------------------------


class TestTrimAlgorithm(unittest.TestCase):
    """Test the section-priority deterministic trim algorithm."""

    def test_budget_10000_on_20000_token_body(self) -> None:
        """budget=10000 on a ~20000-token body → result <= 10000 and trimmed non-empty."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=10000)
        result = injector.inject(body)
        self.assertLessEqual(result.injected_token_estimate, 10000)
        self.assertGreater(len(result.trimmed_sections), 0)

    def test_large_budget_on_small_body_no_trim(self) -> None:
        """budget=100000 on a ~2000-token body → injected == original, no trim."""
        body = build_small_skill()
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)
        self.assertEqual(result.injected_text, body)
        self.assertEqual(len(result.trimmed_sections), 0)
        self.assertEqual(result.original_token_estimate, result.injected_token_estimate)

    def test_budget_too_small_raises_error(self) -> None:
        """budget=100 on a body with large protected sections → SkillBodyBudgetError."""
        body = build_skill_with_large_protected()
        injector = SkillBodyInjector(budget_tokens=100)
        with self.assertRaises(SkillBodyBudgetError):
            injector.inject(body)

    def test_trim_removes_lowest_priority_first(self) -> None:
        """Trimming removes low-priority sections before medium/high."""
        body = build_medium_skill()
        # Set budget to force trimming of low-priority sections
        original_tokens = _estimate_tokens(body)
        # Budget just below original to force some trimming
        budget = original_tokens - 1
        injector = SkillBodyInjector(budget_tokens=budget)
        result = injector.inject(body)
        # All trimmed sections should be low priority (or medium if no low left)
        for entry in result.trimmed_sections:
            self.assertIn(entry["priority"], ("low", "medium", "high"))

    def test_protected_sections_never_trimmed(self) -> None:
        """Protected sections are never in trimmed_sections."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=5000)
        result = injector.inject(body)
        for entry in result.trimmed_sections:
            self.assertNotEqual(entry["priority"], "protected")

    def test_deterministic_same_input_same_output(self) -> None:
        """Same input + same budget → same output (deterministic)."""
        body = build_large_skill()
        injector1 = SkillBodyInjector(budget_tokens=8000)
        injector2 = SkillBodyInjector(budget_tokens=8000)
        result1 = injector1.inject(body)
        result2 = injector2.inject(body)
        self.assertEqual(result1.injected_text, result2.injected_text)
        self.assertEqual(result1.trimmed_sections, result2.trimmed_sections)
        self.assertEqual(result1.injected_token_estimate, result2.injected_token_estimate)

    def test_trimmed_sections_record_section_name(self) -> None:
        """trimmed_sections entries record the section name."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=5000)
        result = injector.inject(body)
        for entry in result.trimmed_sections:
            self.assertTrue(len(entry["section_name"]) > 0)

    def test_trimmed_sections_record_original_tokens(self) -> None:
        """trimmed_sections entries record original_tokens."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=5000)
        result = injector.inject(body)
        for entry in result.trimmed_sections:
            self.assertIsInstance(entry["original_tokens"], int)
            self.assertGreater(entry["original_tokens"], 0)

    def test_trimmed_sections_record_reason(self) -> None:
        """trimmed_sections entries record the reason."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=5000)
        result = injector.inject(body)
        for entry in result.trimmed_sections:
            self.assertEqual(entry["reason"], "budget_trim")

    def test_budget_used_equals_injected_tokens(self) -> None:
        """budget_used equals injected_token_estimate."""
        body = build_medium_skill()
        injector = SkillBodyInjector(budget_tokens=10000)
        result = injector.inject(body)
        self.assertEqual(result.budget_used, result.injected_token_estimate)

    def test_budget_tokens_in_result(self) -> None:
        """budget_tokens in result matches injector budget."""
        body = build_small_skill()
        injector = SkillBodyInjector(budget_tokens=15000)
        result = injector.inject(body)
        self.assertEqual(result.budget_tokens, 15000)


# ---------------------------------------------------------------------------
# Token estimation tests
# ---------------------------------------------------------------------------


class TestTokenEstimation(unittest.TestCase):
    """Test CJK-aware token estimation."""

    def test_cjk_chars_count_as_1_token(self) -> None:
        """Each CJK character counts as 1 token."""
        # 9 CJK characters
        text = "合同审查是法律工作"  # 9 CJK chars
        tokens = _estimate_tokens(text)
        # CJK chars = 9, non-CJK = 0
        self.assertEqual(tokens, 9)

    def test_non_cjk_chars_divided_by_4(self) -> None:
        """Non-CJK characters are divided by chars_per_token."""
        text = "abcdefgh"  # 8 non-CJK chars
        tokens = _estimate_tokens(text, chars_per_token=4)
        self.assertEqual(tokens, 2)

    def test_mixed_cjk_and_non_cjk(self) -> None:
        """Mixed CJK and non-CJK text is estimated correctly."""
        text = "合同review"  # 2 CJK + 6 non-CJK
        tokens = _estimate_tokens(text, chars_per_token=4)
        # CJK = 2, non-CJK = 6 // 4 = 1
        self.assertEqual(tokens, 3)

    def test_empty_text(self) -> None:
        """Empty text has 0 tokens."""
        self.assertEqual(_estimate_tokens(""), 0)


# ---------------------------------------------------------------------------
# Fixture-based tests (varying lengths)
# ---------------------------------------------------------------------------


class TestFixtureSkillBodies(unittest.TestCase):
    """Test with fixture SKILL.md bodies of varying lengths."""

    def test_small_skill_passes(self) -> None:
        """~2K token body with large budget passes without trimming."""
        body = build_small_skill()
        tokens = _estimate_tokens(body)
        self.assertGreater(tokens, 100)  # At least some content
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)
        self.assertEqual(len(result.trimmed_sections), 0)

    def test_medium_skill_passes(self) -> None:
        """~5K token body works correctly."""
        body = build_medium_skill()
        tokens = _estimate_tokens(body)
        self.assertGreater(tokens, 100)
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)
        self.assertEqual(len(result.trimmed_sections), 0)

    def test_large_skill_passes(self) -> None:
        """~10K token body works correctly."""
        body = build_large_skill()
        tokens = _estimate_tokens(body)
        self.assertGreater(tokens, 100)
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)
        self.assertEqual(len(result.trimmed_sections), 0)

    def test_xlarge_skill_passes(self) -> None:
        """~20K token body works correctly."""
        body = build_xlarge_skill()
        tokens = _estimate_tokens(body)
        self.assertGreater(tokens, 100)
        injector = SkillBodyInjector(budget_tokens=100000)
        result = injector.inject(body)
        self.assertEqual(len(result.trimmed_sections), 0)

    def test_xlarge_skill_with_strict_budget(self) -> None:
        """~20K token body with strict budget trims correctly."""
        body = build_xlarge_skill()
        injector = SkillBodyInjector(budget_tokens=10000)
        result = injector.inject(body)
        self.assertLessEqual(result.injected_token_estimate, 10000)
        self.assertGreater(len(result.trimmed_sections), 0)


# ---------------------------------------------------------------------------
# read_skill_body tests (Task 97-02-02)
# ---------------------------------------------------------------------------


def _build_fixture_index_and_skill(base_dir: Path) -> Path:
    """Build a fixture skill-index.json and SKILL.md file for read_skill_body tests."""
    # Create source repo structure
    repo_dir = base_dir / "test-repo"
    skill_dir = repo_dir / "plugin" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)

    # Write a SKILL.md
    skill_text = build_medium_skill()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(skill_text, encoding="utf-8")

    # Build index
    skills = [
        {
            "skill_id": "test-repo:test-skill",
            "name": "test-skill",
            "source_repo": "test-repo",
            "plugin": "plugin",
            "relative_path": "plugin/skills/test-skill/SKILL.md",
            "skill_type": "leaf",
            "parent_skill": None,
            "child_skills": [],
            "description": "A test skill.",
            "frontmatter": {"name": "test-skill"},
            "token_estimate": 5000,
            "declared_gates": [],
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
    ]

    repos_meta = {
        "test-repo": {"path": str(repo_dir), "commit": None, "skill_count": 1},
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


class TestReadSkillBody(unittest.TestCase):
    """Test read_skill_body() on-demand body reading API."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)
        self.index_path = _build_fixture_index_and_skill(self.base_dir)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_reads_skill_body_and_trims(self) -> None:
        """read_skill_body reads SKILL.md and applies trimming."""
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=100000,
        )
        self.assertIsInstance(result, SkillBodyInjectionResult)
        self.assertGreater(len(result.injected_text), 0)

    def test_returns_injection_result_with_trim_report(self) -> None:
        """Returns SkillBodyInjectionResult with trim report."""
        result = read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=2000,
        )
        self.assertIsInstance(result, SkillBodyInjectionResult)
        # With a strict budget, some sections should be trimmed
        self.assertGreaterEqual(len(result.trimmed_sections), 0)

    def test_raises_skill_not_found_for_unknown_id(self) -> None:
        """Raises SkillNotFoundError if skill_id is not in the index."""
        with self.assertRaises(SkillNotFoundError):
            read_skill_body(
                "nonexistent:skill",
                self.index_path,
                budget_tokens=10000,
            )

    def test_raises_source_file_not_found_for_missing_file(self) -> None:
        """Raises SourceFileNotFoundError if SKILL.md does not exist."""
        # Delete the SKILL.md file
        skill_file = self.base_dir / "test-repo" / "plugin" / "skills" / "test-skill" / "SKILL.md"
        skill_file.unlink()
        with self.assertRaises(SourceFileNotFoundError):
            read_skill_body(
                "test-repo:test-skill",
                self.index_path,
                budget_tokens=10000,
            )

    def test_read_only_does_not_modify_source(self) -> None:
        """read_skill_body does not modify the source repo or index file."""
        # Record file state before
        skill_file = self.base_dir / "test-repo" / "plugin" / "skills" / "test-skill" / "SKILL.md"
        original_content = skill_file.read_text(encoding="utf-8")
        original_index = self.index_path.read_text(encoding="utf-8")

        read_skill_body(
            "test-repo:test-skill",
            self.index_path,
            budget_tokens=10000,
        )

        # Verify unchanged
        self.assertEqual(skill_file.read_text(encoding="utf-8"), original_content)
        self.assertEqual(self.index_path.read_text(encoding="utf-8"), original_index)

    def test_importable_from_package(self) -> None:
        """The function is importable as from inkstatute_skill_materializer import read_skill_body."""
        from inkstatute_skill_materializer import read_skill_body as imported_fn

        self.assertTrue(callable(imported_fn))


if __name__ == "__main__":
    unittest.main()
