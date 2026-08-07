"""Unit tests for the Skill Registry API route handler."""

from __future__ import annotations

import unittest
from pathlib import Path

from platform_runtime import RuntimeFeatureDisabledError, RuntimeFeatureFlags

from inkstatute_skill_registry import api as api_module
from inkstatute_skill_registry.api import handle_get
from inkstatute_skill_registry.mapper import load_skills_from_manifests
from inkstatute_skill_registry.registry import SkillRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWFIRM_MANIFEST = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"
DEMO_MANIFEST = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"


def _build_registry() -> SkillRegistry:
    """Build a SkillRegistry loaded from both solution-pack manifests.

    After SKILL-09, lawfirm manifest no longer has a 'skills' key, so
    only demo_non_legal contributes skills (4).
    """
    skills = load_skills_from_manifests([LAWFIRM_MANIFEST, DEMO_MANIFEST])
    return SkillRegistry(skills)


class SkillRegistryApiTests(unittest.TestCase):
    """Tests for ``handle_get`` route handler."""

    def setUp(self) -> None:
        self.registry = _build_registry()

    # ------------------------------------------------------------------
    # /skills — list
    # ------------------------------------------------------------------

    def test_get_skills_list_returns_200(self) -> None:
        status, body = handle_get("/skills", "", self.registry)

        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)
        self.assertIsInstance(body["items"], list)
        self.assertEqual(body["count"], 4)
        self.assertEqual(len(body["items"]), 4)
        self.assertTrue(body["metadata"]["read_only"])

    # ------------------------------------------------------------------
    # /skills/{skill_id} — get single
    # ------------------------------------------------------------------

    def test_get_skill_by_id_returns_200(self) -> None:
        status, body = handle_get("/skills/demo_non_legal/lesson_qa", "", self.registry)

        self.assertEqual(status, 200)
        self.assertEqual(body["skill_id"], "demo_non_legal/lesson_qa")
        self.assertEqual(body["name"], "lesson_qa")

    def test_get_skill_unknown_id_returns_404(self) -> None:
        status, body = handle_get("/skills/unknown", "", self.registry)

        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["resource"], "skill")

    # ------------------------------------------------------------------
    # /skills/search — search with filters
    # ------------------------------------------------------------------

    def test_search_skills_returns_200(self) -> None:
        status, body = handle_get("/skills/search?tag=low", "", self.registry)

        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)
        for item in body["items"]:
            self.assertEqual(item["metadata"]["risk_level"], "low")

    def test_search_skills_with_category_filter(self) -> None:
        status, body = handle_get(
            "/skills/search?category=factual_qa", "", self.registry
        )

        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)
        for item in body["items"]:
            self.assertEqual(item["metadata"]["intent"], "factual_qa")

    def test_search_skills_with_name_filter(self) -> None:
        status, body = handle_get("/skills/search?name=lesson", "", self.registry)

        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)
        for item in body["items"]:
            self.assertIn("lesson", item["name"].lower())

    # ------------------------------------------------------------------
    # /.well-known/agent-skills/index.json — discovery endpoint
    # ------------------------------------------------------------------

    def test_well_known_endpoint_returns_index(self) -> None:
        status, body = handle_get(
            "/.well-known/agent-skills/index.json", "", self.registry
        )

        self.assertEqual(status, 200)
        self.assertIn("$schema", body)
        self.assertIn("skills", body)
        self.assertEqual(
            body["$schema"],
            "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
        )
        self.assertEqual(len(body["skills"]), 4)

    # ------------------------------------------------------------------
    # Unknown route
    # ------------------------------------------------------------------

    def test_unknown_route_returns_404(self) -> None:
        status, body = handle_get("/unknown", "", self.registry)

        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["resource"], "route")

    # ------------------------------------------------------------------
    # Feature flag integration
    # ------------------------------------------------------------------

    def test_feature_flag_disabled_rejects_request(self) -> None:
        flags = RuntimeFeatureFlags()  # default: skill_registry_enabled=False
        with self.assertRaises(RuntimeFeatureDisabledError):
            handle_get("/skills", "", self.registry, flags=flags)

    def test_feature_flag_enabled_allows_request(self) -> None:
        flags = RuntimeFeatureFlags(skill_registry_enabled=True)
        status, body = handle_get("/skills", "", self.registry, flags=flags)

        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 4)

    def test_no_flags_allows_request(self) -> None:
        status, body = handle_get("/skills", "", self.registry, flags=None)

        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 4)

    # ------------------------------------------------------------------
    # Read-only enforcement
    # ------------------------------------------------------------------

    def test_no_write_endpoints_exist(self) -> None:
        module_names = dir(api_module)
        for write_handler in (
            "handle_post",
            "handle_put",
            "handle_delete",
            "handle_patch",
        ):
            self.assertNotIn(write_handler, module_names)


if __name__ == "__main__":
    unittest.main()
