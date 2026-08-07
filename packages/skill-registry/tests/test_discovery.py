"""Unit tests for the discovery index builder (Cloudflare RFC v0.2.0)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from inkstatute_skill_registry.discovery import (
    SCHEMA_URI,
    build_discovery_index,
)
from inkstatute_skill_registry.mapper import load_skills_from_manifests

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWFIRM_MANIFEST = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"
DEMO_MANIFEST = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _load_skills():
    """Load skills from both solution-pack manifests (4 total, demo_non_legal only).

    After SKILL-09, lawfirm manifest no longer has a 'skills' key, so
    only demo_non_legal contributes skills (4).
    """
    return load_skills_from_manifests([LAWFIRM_MANIFEST, DEMO_MANIFEST])


class DiscoveryIndexTests(unittest.TestCase):
    """Tests for ``build_discovery_index`` following Cloudflare RFC v0.2.0."""

    def setUp(self) -> None:
        self.skills = _load_skills()
        self.index = build_discovery_index(self.skills)

    # ------------------------------------------------------------------
    # Top-level structure
    # ------------------------------------------------------------------

    def test_discovery_index_has_schema_field(self) -> None:
        self.assertIn("$schema", self.index)
        self.assertEqual(
            self.index["$schema"],
            "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
        )
        self.assertEqual(SCHEMA_URI, self.index["$schema"])

    def test_discovery_index_has_skills_array(self) -> None:
        self.assertIn("skills", self.index)
        self.assertIsInstance(self.index["skills"], list)
        self.assertEqual(len(self.index["skills"]), 4)

    # ------------------------------------------------------------------
    # Per-entry field requirements
    # ------------------------------------------------------------------

    def test_discovery_skill_entry_has_required_fields(self) -> None:
        for entry in self.index["skills"]:
            self.assertEqual(
                set(entry.keys()),
                {"name", "type", "description", "url", "digest"},
            )

    def test_discovery_skill_name_is_normalized(self) -> None:
        names = [entry["name"] for entry in self.index["skills"]]
        self.assertIn("lesson-qa", names)
        self.assertNotIn("lesson_qa", names)
        # All names should be lowercase with hyphens (no underscores)
        for name in names:
            self.assertNotIn("_", name)
            self.assertEqual(name, name.lower())

    def test_discovery_skill_type_is_skill_md(self) -> None:
        for entry in self.index["skills"]:
            self.assertEqual(entry["type"], "skill-md")

    def test_discovery_skill_url_follows_convention(self) -> None:
        for entry in self.index["skills"]:
            expected_url = (
                f"/.well-known/agent-skills/{entry['name']}/SKILL.md"
            )
            self.assertEqual(entry["url"], expected_url)

    def test_discovery_skill_digest_is_sha256_format(self) -> None:
        for entry in self.index["skills"]:
            self.assertRegex(entry["digest"], _DIGEST_RE)

    def test_discovery_description_max_1024_chars(self) -> None:
        for entry in self.index["skills"]:
            self.assertLessEqual(len(entry["description"]), 1024)

    # ------------------------------------------------------------------
    # Determinism
    # ------------------------------------------------------------------

    def test_discovery_digest_is_deterministic(self) -> None:
        index2 = build_discovery_index(self.skills)
        digests1 = [e["digest"] for e in self.index["skills"]]
        digests2 = [e["digest"] for e in index2["skills"]]
        self.assertEqual(digests1, digests2)


if __name__ == "__main__":
    unittest.main()
