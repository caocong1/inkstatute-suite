from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.boundary_checks import (
    assert_feedback_human_review_safety,
    assert_industry_neutral_schemas,
    assert_neutral_boundary_allowlist,
    assert_platform_contract_import_boundary,
    assert_thin_layer_scope,
)
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT, PLATFORM_FIXTURE_ROOT, PLATFORM_SCHEMA_ROOT, REPO_ROOT


class ThinLayerBoundaryTests(unittest.TestCase):
    def test_platform_contract_import_boundary_fails_on_service_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_dir = root / "packages" / "platform-contract" / "src" / "platform_contract"
            package_dir.mkdir(parents=True)
            (package_dir / "bad.py").write_text("import wecom_service\n", encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "forbidden_platform_import"):
                assert_platform_contract_import_boundary(root)

    def test_current_platform_contract_import_boundary_passes(self) -> None:
        assert_platform_contract_import_boundary(REPO_ROOT)

    def test_schema_neutrality_fails_on_legal_top_level_property(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_root = Path(tmpdir)
            (schema_root / "bad.schema.json").write_text(
                json.dumps(
                    {
                        "title": "Bad",
                        "type": "object",
                        "properties": {"jurisdiction": {"type": "string"}},
                        "required": ["jurisdiction"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AssertionError, "jurisdiction"):
                assert_industry_neutral_schemas(schema_root)

    def test_current_schemas_are_industry_neutral(self) -> None:
        assert_industry_neutral_schemas(PLATFORM_SCHEMA_ROOT)

    def test_thin_layer_scope_passes_for_current_repo(self) -> None:
        assert_thin_layer_scope(REPO_ROOT)

    def test_neutral_boundary_allowlist_passes_for_current_repo(self) -> None:
        assert_neutral_boundary_allowlist(REPO_ROOT)

    def test_feedback_safety_fails_on_auto_modify_true(self) -> None:
        fixture = {
            "events": {
                "agent_result": {
                    "route_mismatch": True,
                    "skill_candidate": {
                        "detected": True,
                        "requires_human_review": True,
                        "metadata": {"auto_modify": True},
                    },
                }
            }
        }

        with self.assertRaisesRegex(AssertionError, "auto_modify_forbidden"):
            assert_feedback_human_review_safety([fixture])

    def test_current_route_mismatch_fixtures_remain_human_review_only(self) -> None:
        fixtures = [
            LOCAL_FIXTURE_ROOT / "phase3_route_error_contract_fixture.json",
            LOCAL_FIXTURE_ROOT / "phase55_wecom_service_agent_loop.json",
            LOCAL_FIXTURE_ROOT / "phase6_read_feedback_bundle.json",
            PLATFORM_FIXTURE_ROOT / "legal_wecom_contract_review.json",
        ]

        assert_feedback_human_review_safety(fixtures)


if __name__ == "__main__":
    unittest.main()
