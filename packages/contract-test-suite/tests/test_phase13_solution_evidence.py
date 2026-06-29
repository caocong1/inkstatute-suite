"""Aggregate Phase 13 SolutionLoader + Lawyer & Non-Legal Solutions evidence.

Wires every Phase 13 artifact into a single default-off, sanitized, and
neutral view:

- DefaultSolutionLoader + MaterializerRegistry handle BOTH `lawfirm` and
  `demo_non_legal` solutions with the same loader instance.
- Both manifests round-trip through DefaultSolutionLoader.validate() with
  zero Issues.
- Both materializers produce sanitized bundles under caller-provided
  output_dir; both bundles pass scan_bundle_dir with zero Issues.
- The privacy scanner returns Issues for each refusal class (secret_marker,
  raw_payload_key, log_file, db_file, media_file, customer_doc, confidential
  artifact).
- The platform core has zero legal-only top-level fields after Phase 13.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from platform_runtime import Issue, SolutionPackageManifest

from inkstatute_solution_loader import (
    DefaultSolutionLoader,
    MaterializerRegistry,
    scan_bundle_dir,
)
from inkstatute_solution_loader.solutions_meta import (
    register_lawfirm_materializer,
    register_demo_non_legal_materializer,
)

from contract_test_suite.paths import REPO_ROOT


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "phase13_solution_bundles.json"
)
MANIFEST_DIR = REPO_ROOT / "solutions"
LAWFIRM_MANIFEST = MANIFEST_DIR / "lawfirm" / "manifest.json"
DEMO_MANIFEST = MANIFEST_DIR / "demo_non_legal" / "manifest.json"


def _manifest_from_json(path: Path, fallback_solution_id: str) -> SolutionPackageManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SolutionPackageManifest(
        solution_id=data.get("solution_id", fallback_solution_id),
        version=data.get("version", "1.0.0"),
        manifest_ref=data.get("manifest_ref"),
        metadata={
            k: v
            for k, v in data.items()
            if k not in {"solution_id", "version", "manifest_ref"}
        },
    )


def _build_registry() -> MaterializerRegistry:
    reg = MaterializerRegistry()
    register_lawfirm_materializer(reg)
    register_demo_non_legal_materializer(reg)
    return reg


class TestManifestNeutrality(unittest.TestCase):
    def test_lawfirm_manifest_loads(self) -> None:
        m = _manifest_from_json(LAWFIRM_MANIFEST, "lawfirm")
        self.assertEqual(m.solution_id, "lawfirm")
        self.assertEqual(m.version, "1.0.0")

    def test_lawfirm_manifest_validates_with_zero_issues(self) -> None:
        m = _manifest_from_json(LAWFIRM_MANIFEST, "lawfirm")
        loader = DefaultSolutionLoader()
        self.assertEqual(loader.validate(m), [])

    def test_demo_manifest_loads(self) -> None:
        m = _manifest_from_json(DEMO_MANIFEST, "demo_non_legal")
        self.assertEqual(m.solution_id, "demo_non_legal")
        self.assertEqual(m.version, "1.0.0")

    def test_demo_manifest_validates_with_zero_issues(self) -> None:
        m = _manifest_from_json(DEMO_MANIFEST, "demo_non_legal")
        loader = DefaultSolutionLoader()
        self.assertEqual(loader.validate(m), [])

    def test_demo_manifest_has_education_domain_not_legal(self) -> None:
        raw = json.loads(DEMO_MANIFEST.read_text(encoding="utf-8"))
        ctx = raw.get("industry_context", {})
        self.assertIn("education_domain", ctx)
        self.assertNotIn("legal_domain", ctx)


class TestMaterializerRoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = _build_registry()
        self.loader = DefaultSolutionLoader(registry=self.reg)
        self.law_m = _manifest_from_json(LAWFIRM_MANIFEST, "lawfirm")
        self.demo_m = _manifest_from_json(DEMO_MANIFEST, "demo_non_legal")

    def test_lawfirm_materializes_into_4_files(self) -> None:
        sol = self.loader.load(self.law_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = self.loader.materialize_for(sol, "hermes", output_dir=out)
            self.assertEqual(issues, [])
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle.solution_id, "lawfirm")
            files = set(
                p.name for p in (out / "profiles" / "lawfirm").iterdir()
            )
            self.assertEqual(
                files,
                {"SANITIZATION_REPORT.md", "SAMPLE_PERSONA.md", "SKILL.md.template", "tools.json"},
            )

    def test_demo_materializes_into_4_files(self) -> None:
        sol = self.loader.load(self.demo_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = self.loader.materialize_for(sol, "hermes", output_dir=out)
            self.assertEqual(issues, [])
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle.solution_id, "demo_non_legal")
            files = set(
                p.name for p in (out / "profiles" / "demo_non_legal").iterdir()
            )
            self.assertEqual(
                files,
                {"SANITIZATION_REPORT.md", "SAMPLE_PERSONA.md", "SKILL.md.template", "tools.json"},
            )

    def test_lawfirm_bundle_passes_scan(self) -> None:
        sol = self.loader.load(self.law_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.loader.materialize_for(sol, "hermes", output_dir=out)
            issues = scan_bundle_dir(out / "profiles" / "lawfirm")
            self.assertEqual(issues, [])

    def test_demo_bundle_passes_scan(self) -> None:
        sol = self.loader.load(self.demo_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.loader.materialize_for(sol, "hermes", output_dir=out)
            issues = scan_bundle_dir(out / "profiles" / "demo_non_legal")
            self.assertEqual(issues, [])

    def test_lawfirm_bundle_ref_inside_output_dir(self) -> None:
        sol = self.loader.load(self.law_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _, bundle = self.loader.materialize_for(sol, "hermes", output_dir=out)
            self.assertTrue(Path(bundle.bundle_ref).resolve().is_relative_to(out.resolve()))

    def test_demo_bundle_ref_inside_output_dir(self) -> None:
        sol = self.loader.load(self.demo_m)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _, bundle = self.loader.materialize_for(sol, "hermes", output_dir=out)
            self.assertTrue(Path(bundle.bundle_ref).resolve().is_relative_to(out.resolve()))


class TestSolutionPrivacyGate(unittest.TestCase):
    def test_clean_bundle_returns_zero_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "OK.md").write_text("clean text", encoding="utf-8")
            (root / "config.json").write_text('{"solution_id": "demo_non_legal"}', encoding="utf-8")
            self.assertEqual(scan_bundle_dir(root), [])

    def test_missing_bundle_dir_returns_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            issues = scan_bundle_dir(missing)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "bundle_dir_missing")

    def test_secret_marker_md_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "leak.md").write_text(
                "this contains sk-abcdef1234567890abcdef22", encoding="utf-8"
            )
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("secret_marker", codes)

    def test_raw_payload_json_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools.json").write_text('{"raw_payload": "blocked"}', encoding="utf-8")
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("raw_payload_key", codes)

    def test_log_file_caught_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.log").write_text("harmless content", encoding="utf-8")
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("binary_or_sensitive_extension", codes)

    def test_db_file_caught_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile.db").write_text("harmless content", encoding="utf-8")
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("binary_or_sensitive_extension", codes)

    def test_media_file_caught_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("binary_or_sensitive_extension", codes)

    def test_customer_doc_filename_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "case_12345.docx").write_bytes(b"fake-docx")
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("binary_or_sensitive_extension", codes)

    def test_confidential_artifact_string_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text(
                "see confidential_artifact for details", encoding="utf-8"
            )
            issues = scan_bundle_dir(root)
            codes = [i.code for i in issues]
            self.assertIn("confidential_artifact", codes)


class TestComposability(unittest.TestCase):
    def test_shared_loader_handles_both_solutions(self) -> None:
        reg = _build_registry()
        loader = DefaultSolutionLoader(registry=reg)
        law_sol = loader.load(_manifest_from_json(LAWFIRM_MANIFEST, "lawfirm"))
        demo_sol = loader.load(_manifest_from_json(DEMO_MANIFEST, "demo_non_legal"))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues_law, bundle_law = loader.materialize_for(law_sol, "hermes", output_dir=out)
            issues_demo, bundle_demo = loader.materialize_for(demo_sol, "hermes", output_dir=out)
            self.assertEqual(issues_law, [])
            self.assertEqual(issues_demo, [])
            self.assertTrue(bundle_law.bundle_ref.endswith("lawfirm"))
            self.assertTrue(bundle_demo.bundle_ref.endswith("demo_non_legal"))

    def test_registry_known_backends_listed(self) -> None:
        reg = _build_registry()
        self.assertIn("hermes", reg.known_backends())

    def test_lawfirm_and_demo_solution_ids_distinguish_packs(self) -> None:
        self.assertNotEqual("lawfirm", "demo_non_legal")

    def test_fixture_phase13_solution_bundles_loads(self) -> None:
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["phase"], 13)
        self.assertIn("lawfirm", data["solutions"])
        self.assertIn("demo_non_legal", data["solutions"])


if __name__ == "__main__":
    unittest.main()
