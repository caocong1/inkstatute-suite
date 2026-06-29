"""Tests for the inkstatute-solution-loader package."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from platform_runtime import (
    BackendSolutionBundle,
    Issue,
    Solution,
    SolutionPackageManifest,
)

from inkstatute_solution_loader import (
    DefaultSolutionLoader,
    DefaultSolutionLoaderConfig,
    MaterializerRegistry,
    MaterializerSideEffects,
    SolutionLoaderFeatureFlags,
    load_solution_loader_feature_flags,
)


def _manifest(**overrides) -> SolutionPackageManifest:
    base = dict(
        solution_id="lawfirm",
        version="1.0.0",
        manifest_ref="solutions/lawfirm/manifest.json",
        metadata={"materialize_targets": ["hermes"]},
    )
    base.update(overrides)
    return SolutionPackageManifest(**base)


def _stub_materializer(solution: Solution, output_dir):
    """Trivial materializer that writes no files and returns a fake bundle_ref."""
    if output_dir is None:
        return [], BackendSolutionBundle(
            backend_id="hermes", solution_id=solution.solution_id, bundle_ref="/tmp/nowhere"
        )
    target = Path(output_dir) / "profiles" / solution.solution_id
    return [], BackendSolutionBundle(
        backend_id="hermes",
        solution_id=solution.solution_id,
        bundle_ref=str(target),
    )


class TestFeatureFlags(unittest.TestCase):
    def test_default_disabled(self) -> None:
        env = {"INKSTATUTE_SOLUTION_LOADER_ENABLED": ""}
        self.assertFalse(load_solution_loader_feature_flags(env).enabled)
        self.assertFalse(load_solution_loader_feature_flags(env).require_enabled())

    def test_truthy_values_enable(self) -> None:
        for truthy in ("1", "true", "TRUE", "yes", "on", "  True  "):
            flags = load_solution_loader_feature_flags({"INKSTATUTE_SOLUTION_LOADER_ENABLED": truthy})
            self.assertTrue(flags.enabled, f"expected enabled for {truthy!r}")
            self.assertTrue(flags.require_enabled())

    def test_malformed_value_disables(self) -> None:
        for bogus in ("maybe", "2", "off", " "):
            flags = load_solution_loader_feature_flags(
                {"INKSTATUTE_SOLUTION_LOADER_ENABLED": bogus}
            )
            self.assertFalse(flags.enabled, f"expected disabled for {bogus!r}")

    def test_absent_env_disables(self) -> None:
        flags = load_solution_loader_feature_flags({})
        self.assertFalse(flags.enabled)


class TestManifestValidator(unittest.TestCase):
    def test_neutral_manifest_passes(self) -> None:
        m = _manifest()
        loader = DefaultSolutionLoader()
        self.assertEqual(loader.validate(m), [])

    def test_legal_only_metadata_key_rejected(self) -> None:
        m = _manifest(metadata={"materialize_targets": ["hermes"], "lawyer": True})
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "legal_only_top_level_forbidden" for i in issues))

    def test_raw_payload_metadata_key_rejected(self) -> None:
        m = _manifest(metadata={"materialize_targets": ["hermes"], "raw_payload": "x"})
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(
            any(i.code == "raw_payload_or_secret_top_level_forbidden" for i in issues)
        )

    def test_secret_marker_in_field_rejected(self) -> None:
        m = _manifest(manifest_ref="sk-12345678901234567890")
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "secret_marker_in_field" for i in issues))

    def test_hex_blob_in_field_rejected(self) -> None:
        m = _manifest(manifest_ref="abcdef0123456789abcdef0123456789")
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "hex_blob_in_field" for i in issues))

    def test_solution_id_format_rejected(self) -> None:
        m = _manifest(solution_id="bad id with spaces")
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "solution_id_invalid_format" for i in issues))

    def test_version_format_rejected(self) -> None:
        m = _manifest(version="not-semver")
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "version_invalid_format" for i in issues))

    def test_undeclared_materialize_target_rejected(self) -> None:
        m = _manifest(metadata={"materialize_targets": ["bogus_backend"]})
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "undeclared_materialize_target" for i in issues))

    def test_secret_marker_in_metadata_description_rejected(self) -> None:
        # CR-02: secret markers in metadata string values must be rejected.
        m = _manifest(
            metadata={
                "materialize_targets": ["hermes"],
                "description": "leaked token sk-12345678901234567890",
            }
        )
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "secret_marker_in_field" for i in issues))

    def test_secret_marker_in_nested_metadata_rejected(self) -> None:
        # CR-02: recursive scan over nested dicts/lists in metadata.
        m = _manifest(
            metadata={
                "materialize_targets": ["hermes"],
                "persona_ref": {"notes": "bearer abcdef1234567890abcdef12"},
            }
        )
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "secret_marker_in_field" for i in issues))

    def test_empty_solution_id_rejected(self) -> None:
        # WR-07: empty solution_id must be rejected (falsy short-circuit fix).
        m = _manifest(solution_id="")
        loader = DefaultSolutionLoader()
        issues = loader.validate(m)
        self.assertTrue(any(i.code == "solution_id_invalid_format" for i in issues))

    def test_neutral_dict_validator(self) -> None:
        from inkstatute_solution_loader.manifest_validator import validate_manifest_dict

        clean = {"solution_id": "lawfirm", "version": "1.0.0", "metadata": {}}
        self.assertEqual(validate_manifest_dict(clean), [])

        bad = {"lawyer": True, "raw_payload": "x"}
        issues = validate_manifest_dict(bad)
        self.assertTrue(any(i.code == "legal_only_top_level_forbidden" for i in issues))
        self.assertTrue(any(i.code == "raw_payload_top_level_forbidden" for i in issues))


class TestMaterializerRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = MaterializerRegistry()
        self.se = MaterializerSideEffects(
            backend_id="hermes",
            declared_output_dir_relative="profiles/<solution_id>",
            side_effect_kinds=("write_dir",),
        )

    def test_register_get_roundtrip(self) -> None:
        self.reg.register("hermes", _stub_materializer, self.se, solution_id="lawfirm")
        self.assertIs(self.reg.get("hermes", "lawfirm"), _stub_materializer)

    def test_get_unknown_returns_none(self) -> None:
        self.assertIsNone(self.reg.get("codex", "lawfirm"))

    def test_side_effects_for_returns_declared(self) -> None:
        self.reg.register("hermes", _stub_materializer, self.se, solution_id="lawfirm")
        self.assertEqual(self.reg.side_effects_for("hermes", "lawfirm"), self.se)

    def test_known_backends_sorted(self) -> None:
        self.reg.register("hermes", _stub_materializer, self.se, solution_id="lawfirm")
        self.reg.register(
            "codex",
            _stub_materializer,
            MaterializerSideEffects(
                backend_id="codex", declared_output_dir_relative=None, side_effect_kinds=()
            ),
            solution_id="lawfirm",
        )
        self.assertEqual(self.reg.known_backends(), ("codex", "hermes"))

    def test_two_solutions_same_backend_both_retrievable(self) -> None:
        # CR-01: both materializers must be retrievable from the same registry
        # when they share backend_id but differ by solution_id.
        def lawfirm_mat(solution, output_dir):
            return [], BackendSolutionBundle(
                backend_id="hermes", solution_id="lawfirm", bundle_ref="/tmp/law"
            )

        def demo_mat(solution, output_dir):
            return [], BackendSolutionBundle(
                backend_id="hermes", solution_id="demo_non_legal", bundle_ref="/tmp/demo"
            )

        self.reg.register("hermes", lawfirm_mat, self.se, solution_id="lawfirm")
        self.reg.register("hermes", demo_mat, self.se, solution_id="demo_non_legal")
        self.assertIs(self.reg.get("hermes", "lawfirm"), lawfirm_mat)
        self.assertIs(self.reg.get("hermes", "demo_non_legal"), demo_mat)
        self.assertEqual(self.reg.known_solutions("hermes"), ("demo_non_legal", "lawfirm"))
        self.assertEqual(self.reg.known_backends(), ("hermes",))

    def test_invalid_side_effect_kind_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MaterializerSideEffects(
                backend_id="hermes",
                declared_output_dir_relative=None,
                side_effect_kinds=("delete_database",),
            )


class TestDefaultSolutionLoader(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = MaterializerRegistry()
        self.reg.register(
            "hermes",
            _stub_materializer,
            MaterializerSideEffects(
                backend_id="hermes",
                declared_output_dir_relative="profiles/<solution_id>",
                side_effect_kinds=("write_dir",),
            ),
            solution_id="lawfirm",
        )
        self.loader = DefaultSolutionLoader(registry=self.reg)
        self.m = _manifest()

    def test_validate_delegates(self) -> None:
        self.assertEqual(self.loader.validate(self.m), [])

    def test_load_wraps(self) -> None:
        sol = self.loader.load(self.m)
        self.assertEqual(sol.solution_id, "lawfirm")
        self.assertEqual(sol.version, "1.0.0")

    def test_materialize_for_dispatches(self) -> None:
        sol = self.loader.load(self.m)
        with self._tmpdir() as out:
            issues, bundle = self.loader.materialize_for(sol, "hermes", output_dir=Path(out))
            self.assertEqual(issues, [])
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle.backend_id, "hermes")
            self.assertEqual(bundle.solution_id, "lawfirm")
            self.assertTrue(Path(bundle.bundle_ref).is_relative_to(Path(out).resolve()))

    def test_materialize_for_unknown_backend_returns_issue(self) -> None:
        sol = self.loader.load(self.m)
        issues, bundle = self.loader.materialize_for(sol, "codex", output_dir=Path("/tmp/anywhere"))
        self.assertTrue(any(i.code == "no_materializer_registered" for i in issues))
        self.assertIsNone(bundle)

    def test_allow_unknown_backends_returns_empty_issues_and_none(self) -> None:
        # WR-05: when allow_unknown_backends=True, unknown backend returns
        # empty issues + None instead of a no_materializer_registered Issue.
        config = DefaultSolutionLoaderConfig(allow_unknown_backends=True)
        loader = DefaultSolutionLoader(config=config, registry=self.reg)
        sol = loader.load(self.m)
        issues, bundle = loader.materialize_for(sol, "codex", output_dir=Path("/tmp/anywhere"))
        self.assertEqual(issues, [])
        self.assertIsNone(bundle)

    def test_classify_side_effects(self) -> None:
        se = self.loader.classify_side_effects("hermes", "lawfirm")
        self.assertIsNotNone(se)
        self.assertEqual(se.backend_id, "hermes")
        self.assertIsNone(self.loader.classify_side_effects("codex", "lawfirm"))

    def test_path_traversal_guard(self) -> None:
        def bad_materializer(solution, output_dir):
            return [], BackendSolutionBundle(
                backend_id="hermes",
                solution_id=solution.solution_id,
                bundle_ref="/etc/passwd",
            )

        self.reg.register(
            "hermes",
            bad_materializer,
            MaterializerSideEffects(
                backend_id="hermes",
                declared_output_dir_relative=None,
                side_effect_kinds=("write_dir",),
            ),
            solution_id="lawfirm",
        )
        sol = self.loader.load(self.m)
        with self._tmpdir() as out:
            issues, bundle = self.loader.materialize_for(sol, "hermes", output_dir=Path(out))
            self.assertTrue(any(i.code == "bundle_ref_outside_output_dir" for i in issues))
            self.assertIsNone(bundle)

    def test_conformance_with_protocol(self) -> None:
        # Assert the three required Protocol methods exist.
        loader = self.loader
        self.assertTrue(callable(getattr(loader, "validate", None)))
        self.assertTrue(callable(getattr(loader, "load", None)))
        self.assertTrue(callable(getattr(loader, "materialize_for", None)))

    @staticmethod
    def _tmpdir():
        import tempfile
        return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()