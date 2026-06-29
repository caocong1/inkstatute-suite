"""Tests for the inkstatute-solutions-lawfirm pack."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from platform_runtime import SolutionPackageManifest

from inkstatute_solution_loader import (
    DefaultSolutionLoader,
    DefaultSolutionLoaderConfig,
    MaterializerRegistry,
    MaterializerSideEffects,
)

from inkstatute_solutions_lawfirm import (
    LAWFIRM_SOLUTION_ID,
    LAWFIRM_VERSION,
    LawfirmHermesMaterializer,
    register_into,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"


def _manifest_from_json() -> SolutionPackageManifest:
    data = json.loads(MANIFEST_PATH.read_text())
    # Extract SolutionPackageManifest-known fields; everything else goes to metadata.
    return SolutionPackageManifest(
        solution_id=data["solution_id"],
        version=data["version"],
        manifest_ref=data.get("manifest_ref"),
        metadata={k: v for k, v in data.items() if k not in {"solution_id", "version", "manifest_ref"}},
    )


class TestNeutralManifest(unittest.TestCase):
    def test_manifest_loads(self) -> None:
        m = _manifest_from_json()
        self.assertEqual(m.solution_id, "lawfirm")
        self.assertEqual(m.version, "1.0.0")

    def test_manifest_validates_with_zero_issues(self) -> None:
        m = _manifest_from_json()
        loader = DefaultSolutionLoader()
        self.assertEqual(loader.validate(m), [])

    def test_no_legal_only_top_level_keys(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        forbidden = {
            "lawyer", "legal", "lawfirm", "attorney", "counsel", "law_firm", "attorneys_at_law",
        }
        for k in raw.keys():
            self.assertNotIn(k.lower(), forbidden, f"top-level key {k!r} is legal-only")

    def test_skills_use_neutral_descriptors(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        allowed_keys = {"name", "description", "intent", "required_tools", "risk_level"}
        for skill in raw["skills"]:
            self.assertTrue(set(skill.keys()) <= allowed_keys, f"non-neutral skill keys: {set(skill.keys()) - allowed_keys}")
            self.assertIn("name", skill)
            self.assertIn("description", skill)

    def test_mcp_uses_secret_ref_only(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        for tool in raw["mcp"]:
            self.assertIn("secret_ref", tool)
            # secret_ref should be a NAME, not a value
            self.assertNotIn("=", tool["secret_ref"])

    def test_secret_templates_names_only(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        for tmpl in raw["secret_templates"]:
            self.assertIsInstance(tmpl, str)
            # Templates are names (uppercase, no '=' or value)
            self.assertNotIn("=", tmpl)


class TestSanitize(unittest.TestCase):
    def test_clean_text_passes(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertEqual(scan_text("clean manifest text"), [])

    def test_secret_marker_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("secret_marker", scan_text("sk-1234567890123456"))

    def test_bearer_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("secret_marker", scan_text("Authorization: bearer abcdef0123456789ABCD"))

    def test_raw_payload_key_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("raw_payload_key", scan_text("contains raw_payload text"))

    def test_log_file_ref_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("log_file_ref", scan_text("/tmp/app.log"))

    def test_db_file_ref_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("db_file_ref", scan_text("/var/lib/profile.db"))

    def test_customer_doc_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("customer_doc", scan_text("case_12345.docx"))

    def test_confidential_artifact_caught(self) -> None:
        from inkstatute_solutions_lawfirm.sanitize import scan_text
        self.assertIn("confidential_artifact", scan_text("see confidential_artifact for details"))


class TestHermesMaterializer(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = MaterializerRegistry()
        self.materializer = LawfirmHermesMaterializer()
        self.reg.register(
            "hermes",
            self.materializer.materialize,
            self.materializer.side_effects(),
            solution_id=LAWFIRM_SOLUTION_ID,
        )
        self.loader = DefaultSolutionLoader(registry=self.reg)
        self.solution = self.loader.load(_manifest_from_json())

    def test_side_effects_declared(self) -> None:
        se = self.materializer.side_effects()
        self.assertEqual(se.backend_id, "hermes")
        self.assertIn("write_dir", se.side_effect_kinds)

    def test_happy_path_writes_four_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = self.loader.materialize_for(self.solution, "hermes", output_dir=out)
            self.assertEqual(issues, [])
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle.backend_id, "hermes")
            self.assertEqual(bundle.solution_id, "lawfirm")
            files = set(p.name for p in (out / "profiles" / "lawfirm").iterdir())
            self.assertEqual(files, {"SANITIZATION_REPORT.md", "SAMPLE_PERSONA.md", "SKILL.md.template", "tools.json"})
            self.assertTrue(Path(bundle.bundle_ref).is_relative_to(out.resolve()))

    def test_secret_in_manifest_aborts(self) -> None:
        bad = SolutionPackageManifest(
            solution_id="lawfirm",
            version="1.0.0",
            metadata={
                "materialize_targets": ["hermes"],
                "description": "this contains sk-abcdef1234567890abcdef12",
            },
        )
        bad_solution = self.loader.load(bad)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = self.loader.materialize_for(bad_solution, "hermes", output_dir=out)
            self.assertTrue(len(issues) > 0)
            self.assertIsNone(bundle)
            # No files written
            self.assertFalse((out / "profiles").exists())

    def test_sanitization_report_records_zero_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.loader.materialize_for(self.solution, "hermes", output_dir=out)
            report = (out / "profiles" / "lawfirm" / "SANITIZATION_REPORT.md").read_text()
            self.assertIn("refused_items: []", report)
            self.assertIn("backend_id: hermes", report)

    def test_register_into_wires_materializer_into_registry(self) -> None:
        fresh_reg = MaterializerRegistry()
        self.assertNotIn("hermes", fresh_reg.known_backends())
        register_into(fresh_reg)
        self.assertIn("hermes", fresh_reg.known_backends())
        se = fresh_reg.side_effects_for("hermes", LAWFIRM_SOLUTION_ID)
        self.assertIsNotNone(se)
        self.assertEqual(se.backend_id, "hermes")
        self.assertIn("write_dir", se.side_effect_kinds)

    def test_register_into_output_dir_anchor_accepted_but_unused(self) -> None:
        fresh_reg = MaterializerRegistry()
        register_into(fresh_reg, output_dir_anchor=Path("/tmp/anchor"))
        self.assertIn("hermes", fresh_reg.known_backends())


if __name__ == "__main__":
    unittest.main()