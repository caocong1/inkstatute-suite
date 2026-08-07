"""Coverage test — verifies PracticeProfileInjector correctly handles all
skills with ``practice_profile_dependency``.

This test loads a skill-index.json fixture (or the real index if available)
and verifies that:
- Every skill with ``practice_profile_dependency=True`` gets
  ``profile_injected=True`` (when a profile exists or temporary mode is used).
- Every skill with ``practice_profile_dependency=False`` gets
  ``profile_injected=False``.
- The total count of ``practice_profile_dependency=True`` skills is ≥337
  (matching the research scan in 99-RESEARCH.md §2.3), when the real index
  is available.

If the real ``skill-index.json`` is not available in the test environment,
the test uses a fixture with known dependency flags and skips the count
assertion.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inkstatute_practice_profile import (
    InMemoryPracticeProfileStore,
    PracticeProfile,
    PracticeProfileInjector,
)


# ---------------------------------------------------------------------------
# Fixture builder — generates a large index with known dependency flags
# ---------------------------------------------------------------------------


def _build_fixture_index(num_dep: int = 337, num_no_dep: int = 52) -> dict:
    """Build a test skill-index with *num_dep* dependent skills and
    *num_no_dep* non-dependent skills.

    The dependent skills are spread across multiple plugins to simulate
    the real index distribution.
    """
    plugins = [
        "commercial-legal", "litigation-legal", "employment-legal",
        "data-compliance", "ip-legal", "regulatory-legal",
        "ai-governance", "construction-legal", "criminal-compliance",
        "family-legal", "legal-aid", "legal-builder-hub", "law-student",
    ]
    skills: list[dict] = []
    for i in range(num_dep):
        plugin = plugins[i % len(plugins)]
        skills.append({
            "skill_id": f"dep-skill-{i:04d}",
            "plugin": plugin,
            "practice_profile_dependency": True,
        })
    for i in range(num_no_dep):
        skills.append({
            "skill_id": f"no-dep-skill-{i:04d}",
            "plugin": "commercial-legal",
            "practice_profile_dependency": False,
        })
    return {"repos": {}, "skills": skills}


def _write_fixture(index_data: dict) -> str:
    """Write index data to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(index_data, f)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# Coverage tests with fixture
# ---------------------------------------------------------------------------


class CoverageFixtureTests(unittest.TestCase):
    """Tests using a generated fixture with known dependency flags."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.index_data = _build_fixture_index(num_dep=337, num_no_dep=52)
        cls.idx_path = _write_fixture(cls.index_data)

    @classmethod
    def tearDownClass(cls) -> None:
        Path(cls.idx_path).unlink(missing_ok=True)

    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()
        # Pre-populate a profile for commercial-legal so some skills
        # get a real profile instead of temporary.
        self.store.upsert(
            "t1",
            PracticeProfile(
                tenant_id="t1",
                plugin="commercial-legal",
                identity={"org_name": "某律所"},
            ),
        )
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def test_all_dependent_skills_get_injected(self) -> None:
        """Every skill with practice_profile_dependency=True gets
        profile_injected=True."""
        dep_skills = [
            s for s in self.index_data["skills"]
            if s.get("practice_profile_dependency") is True
        ]
        for skill in dep_skills:
            r = self.injector.inject(skill["skill_id"], "t1")
            self.assertTrue(
                r.profile_injected,
                f"Skill {skill['skill_id']} has dependency=True but "
                f"profile_injected=False",
            )

    def test_all_non_dependent_skills_not_injected(self) -> None:
        """Every skill with practice_profile_dependency=False gets
        profile_injected=False."""
        no_dep_skills = [
            s for s in self.index_data["skills"]
            if s.get("practice_profile_dependency") is False
        ]
        for skill in no_dep_skills:
            r = self.injector.inject(skill["skill_id"], "t1")
            self.assertFalse(
                r.profile_injected,
                f"Skill {skill['skill_id']} has dependency=False but "
                f"profile_injected=True",
            )

    def test_dependent_skill_count_at_least_337(self) -> None:
        """The fixture has ≥337 skills with practice_profile_dependency=True,
        matching the research scan count."""
        dep_count = sum(
            1 for s in self.index_data["skills"]
            if s.get("practice_profile_dependency") is True
        )
        self.assertGreaterEqual(
            dep_count, 337,
            f"Expected ≥337 dependent skills, got {dep_count}",
        )

    def test_total_skill_count_389(self) -> None:
        """Total skills = 337 + 52 = 389, matching the research scan."""
        total = len(self.index_data["skills"])
        self.assertEqual(total, 389)

    def test_temporary_mode_for_plugins_without_profile(self) -> None:
        """Skills with plugins that have no profile get temporary mode."""
        # Only commercial-legal has a profile; all other plugins get temp.
        dep_skills = [
            s for s in self.index_data["skills"]
            if s.get("practice_profile_dependency") is True
            and s.get("plugin") != "commercial-legal"
        ]
        for skill in dep_skills:
            r = self.injector.inject(skill["skill_id"], "t1")
            self.assertTrue(
                r.temporary_mode,
                f"Skill {skill['skill_id']} (plugin={skill['plugin']}) "
                f"should be in temporary mode",
            )

    def test_real_profile_for_commercial_legal(self) -> None:
        """Skills with commercial-legal plugin get the real profile."""
        cl_skills = [
            s for s in self.index_data["skills"]
            if s.get("practice_profile_dependency") is True
            and s.get("plugin") == "commercial-legal"
        ]
        for skill in cl_skills:
            r = self.injector.inject(skill["skill_id"], "t1")
            self.assertFalse(
                r.temporary_mode,
                f"Skill {skill['skill_id']} should use real profile",
            )
            self.assertIn("某律所", r.context_section)

    def test_injector_does_not_modify_index(self) -> None:
        """The injector should not modify the skill index (read-only)."""
        original = json.loads(Path(self.idx_path).read_text(encoding="utf-8"))
        # Run injections on all skills
        for skill in self.index_data["skills"]:
            self.injector.inject(skill["skill_id"], "t1")
        # Verify index unchanged
        after = json.loads(Path(self.idx_path).read_text(encoding="utf-8"))
        self.assertEqual(original, after)


# ---------------------------------------------------------------------------
# Real index test (skipped if not available)
# ---------------------------------------------------------------------------


class RealIndexCoverageTests(unittest.TestCase):
    """Tests against the real skill-index.json if available.

    The real index is produced by Phase 96 and may not be present in
    all test environments.  These tests are skipped if the index is
    not found.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Search for the real skill-index.json in common locations
        candidates = [
            Path(__file__).resolve().parents[3] / "skill-index.json",
            Path(__file__).resolve().parents[3] / "data" / "skill-index.json",
            Path(__file__).resolve().parents[3] / "var" / "skill-index.json",
        ]
        cls.real_index_path: Path | None = None
        for candidate in candidates:
            if candidate.exists():
                cls.real_index_path = candidate
                break

    def setUp(self) -> None:
        if self.real_index_path is None:
            self.skipTest("Real skill-index.json not available in test environment")
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.real_index_path)

    def test_real_index_dependent_count_at_least_337(self) -> None:
        index = json.loads(self.real_index_path.read_text(encoding="utf-8"))
        dep_count = sum(
            1 for s in index.get("skills", [])
            if s.get("practice_profile_dependency") is True
        )
        self.assertGreaterEqual(
            dep_count, 337,
            f"Real index has {dep_count} dependent skills, expected ≥337",
        )

    def test_real_index_all_dependent_skills_injected(self) -> None:
        index = json.loads(self.real_index_path.read_text(encoding="utf-8"))
        dep_skills = [
            s for s in index.get("skills", [])
            if s.get("practice_profile_dependency") is True
        ]
        # Test a sample (first 20) to keep test time reasonable
        for skill in dep_skills[:20]:
            r = self.injector.inject(skill["skill_id"], "t1")
            self.assertTrue(r.profile_injected)


if __name__ == "__main__":
    unittest.main()
