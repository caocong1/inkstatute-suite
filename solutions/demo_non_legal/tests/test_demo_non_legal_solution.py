"""Tests for the inkstatute-solutions-demo_non_legal pack."""

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
)

from inkstatute_solutions_demo_non_legal import (
    DEMO_NON_LEGAL_SOLUTION_ID,
    DemoNonLegalHermesMaterializer,
)
from inkstatute_solutions_lawfirm import LawfirmHermesMaterializer


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"
LAWFIRM_MANIFEST_PATH = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"


def _manifest_from_json(path: Path) -> SolutionPackageManifest:
    data = json.loads(path.read_text())
    return SolutionPackageManifest(
        solution_id=data["solution_id"],
        version=data["version"],
        manifest_ref=data.get("manifest_ref"),
        metadata={k: v for k, v in data.items() if k not in {"solution_id", "version", "manifest_ref"}},
    )


def _build_loader() -> tuple[DefaultSolutionLoader, MaterializerRegistry]:
    reg = MaterializerRegistry()
    law = LawfirmHermesMaterializer()
    demo = DemoNonLegalHermesMaterializer()
    reg.register("hermes", law.materialize, law.side_effects(), solution_id="lawfirm")
    reg.register(
        "hermes", demo.materialize, demo.side_effects(), solution_id="demo_non_legal"
    )
    return DefaultSolutionLoader(registry=reg), reg


class TestNeutralManifest(unittest.TestCase):
    def test_manifest_loads(self) -> None:
        m = _manifest_from_json(MANIFEST_PATH)
        self.assertEqual(m.solution_id, "demo_non_legal")
        self.assertEqual(m.version, "1.0.0")

    def test_manifest_validates_with_zero_issues(self) -> None:
        m = _manifest_from_json(MANIFEST_PATH)
        loader = DefaultSolutionLoader()
        self.assertEqual(loader.validate(m), [])

    def test_industry_context_is_education_domain_not_legal(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        ctx = raw.get("industry_context", {})
        self.assertIn("education_domain", ctx)
        self.assertNotIn("legal_domain", ctx)

    def test_output_policy_disallows_legal_conclusions(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        self.assertFalse(raw["output_policy"]["allow_legal_conclusions"])

    def test_no_legal_only_fields_at_any_level(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text())
        # Quick recursive check
        def _walk(prefix: str, value: object) -> list[str]:
            hits: list[str] = []
            if isinstance(value, dict):
                for k, v in value.items():
                    if k.lower() in {"lawyer", "legal", "lawfirm", "attorney", "counsel"}:
                        hits.append(f"{prefix}.{k}" if prefix else k)
                    hits.extend(_walk(f"{prefix}.{k}" if prefix else str(k), v))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    hits.extend(_walk(f"{prefix}[{i}]", v))
            return hits

        self.assertEqual(_walk("", raw), [])


class TestHermesMaterializer(unittest.TestCase):
    def test_side_effects_declared(self) -> None:
        se = DemoNonLegalHermesMaterializer().side_effects()
        self.assertEqual(se.backend_id, "hermes")
        self.assertIn("write_dir", se.side_effect_kinds)

    def test_happy_path_writes_four_files(self) -> None:
        loader, _reg = _build_loader()
        solution = loader.load(_manifest_from_json(MANIFEST_PATH))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = loader.materialize_for(solution, "hermes", output_dir=out)
            self.assertEqual(issues, [])
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle.solution_id, "demo_non_legal")
            files = set(p.name for p in (out / "profiles" / "demo_non_legal").iterdir())
            self.assertEqual(files, {"SANITIZATION_REPORT.md", "SAMPLE_PERSONA.md", "SKILL.md.template", "tools.json"})

    def test_secret_in_manifest_aborts(self) -> None:
        bad = SolutionPackageManifest(
            solution_id="demo_non_legal",
            version="1.0.0",
            metadata={
                "materialize_targets": ["hermes"],
                "notes": "this contains sk-abcdef1234567890abcdef12",
            },
        )
        loader, _reg = _build_loader()
        bad_sol = loader.load(bad)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues, bundle = loader.materialize_for(bad_sol, "hermes", output_dir=out)
            self.assertTrue(len(issues) > 0)
            self.assertIsNone(bundle)
            self.assertFalse((out / "profiles").exists())


class TestComposabilityWithLawfirm(unittest.TestCase):
    """Same DefaultSolutionLoader handles both solutions sequentially."""

    def test_both_solutions_share_loader(self) -> None:
        loader, reg = _build_loader()
        self.assertIn("hermes", reg.known_backends())

        law_sol = loader.load(_manifest_from_json(LAWFIRM_MANIFEST_PATH))
        demo_sol = loader.load(_manifest_from_json(MANIFEST_PATH))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            issues_law, bundle_law = loader.materialize_for(law_sol, "hermes", output_dir=out)
            issues_demo, bundle_demo = loader.materialize_for(demo_sol, "hermes", output_dir=out)
            self.assertEqual(issues_law, [])
            self.assertEqual(issues_demo, [])
            self.assertTrue(bundle_law.bundle_ref.endswith("lawfirm"))
            self.assertTrue(bundle_demo.bundle_ref.endswith("demo_non_legal"))
            self.assertTrue(Path(bundle_law.bundle_ref).exists())
            self.assertTrue(Path(bundle_demo.bundle_ref).exists())

    def test_solution_id_distinguishes_packs(self) -> None:
        law_sol = SolutionPackageManifest(solution_id="lawfirm", version="1.0.0")
        demo_sol = SolutionPackageManifest(solution_id="demo_non_legal", version="1.0.0")
        self.assertNotEqual(law_sol.solution_id, demo_sol.solution_id)


if __name__ == "__main__":
    unittest.main()