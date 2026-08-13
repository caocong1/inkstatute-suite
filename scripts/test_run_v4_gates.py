#!/usr/bin/env python3
"""Self-tests for the V4 gate runner (scripts/run_v4_gates.py).

Tests cover:
  - Meta-test logic (lib/ dir coverage detection) with temp directories
  - Engine manifest validation (pin file, cordis config, manifest JSON)
  - --check subcommand parsing
  - Non-existent engine-manifest.json -> SKIP (not FAIL)
  - Integration: run_v4_gates.py --check meta-test exits 0 on current codebase
  - Integration: run_v4_gates.py --check engine-manifest exits 0
  - Negative: meta-test exits 1 when a lib/ dir without tests is temporarily created
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts/ to path for importing run_v4_gates
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import run_v4_gates  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests: find_lib_dirs
# ---------------------------------------------------------------------------

class TestFindLibDirs(unittest.TestCase):
    """Unit tests for find_lib_dirs -- locates (lib_dir, test_dir) pairs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.flutter_app = Path(self.tmp.name) / "flutter_app"

    def tearDown(self):
        self.tmp.cleanup()

    def _create_dart_file(self, path: str):
        p = self.flutter_app / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// stub\n")

    def test_finds_root_lib_dir(self):
        """lib/ at flutter_app root with .dart files is found."""
        self._create_dart_file("lib/main.dart")
        pairs = run_v4_gates.find_lib_dirs(self.flutter_app)
        lib_dirs = [str(p[0].relative_to(self.flutter_app)) for p in pairs]
        self.assertIn("lib", lib_dirs)

    def test_finds_subdirectory_lib_dirs(self):
        """lib/engine/ with .dart files is found as a separate entry."""
        self._create_dart_file("lib/engine/dsh_config.dart")
        pairs = run_v4_gates.find_lib_dirs(self.flutter_app)
        lib_dirs = [str(p[0].relative_to(self.flutter_app)) for p in pairs]
        self.assertIn("lib/engine", lib_dirs)

    def test_finds_package_lib_dirs(self):
        """packages/acp_client/lib/ with .dart files is found."""
        self._create_dart_file("packages/acp_client/lib/acp_client.dart")
        pairs = run_v4_gates.find_lib_dirs(self.flutter_app)
        lib_dirs = [str(p[0].relative_to(self.flutter_app)) for p in pairs]
        self.assertIn("packages/acp_client/lib", lib_dirs)

    def test_ignores_empty_lib_dirs(self):
        """A lib/ subdirectory with no .dart files is not listed."""
        self._create_dart_file("lib/main.dart")
        (self.flutter_app / "lib" / "empty").mkdir(parents=True)
        pairs = run_v4_gates.find_lib_dirs(self.flutter_app)
        lib_dirs = [str(p[0].relative_to(self.flutter_app)) for p in pairs]
        self.assertIn("lib", lib_dirs)
        self.assertNotIn("lib/empty", lib_dirs)

    def test_maps_lib_dir_to_test_dir(self):
        """lib/engine/ maps to test/engine/."""
        self._create_dart_file("lib/engine/dsh_config.dart")
        pairs = run_v4_gates.find_lib_dirs(self.flutter_app)
        for lib_dir, test_dir in pairs:
            if lib_dir.name == "engine" and lib_dir.parent.name == "lib":
                expected_test = self.flutter_app / "test" / "engine"
                self.assertEqual(test_dir, expected_test)
                return
        self.fail("lib/engine not found in pairs")


# ---------------------------------------------------------------------------
# Unit tests: run_meta_test
# ---------------------------------------------------------------------------

class TestRunMetaTest(unittest.TestCase):
    """Unit tests for run_meta_test -- checks test coverage for lib/ dirs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.flutter_app = Path(self.tmp.name) / "flutter_app"

    def tearDown(self):
        self.tmp.cleanup()

    def _create_dart_file(self, path: str, content: str = "// stub\n"):
        p = self.flutter_app / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def _create_test_file(self, path: str):
        p = self.flutter_app / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("import 'package:test/test.dart';\n\nvoid main() {}\n")

    def test_covered_lib_dir_passes(self):
        """A lib/ dir with a matching test/ dir and _test.dart file passes."""
        self._create_dart_file("lib/main.dart")
        self._create_test_file("test/widget_test.dart")
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertEqual(uncovered, [])

    def test_uncovered_lib_dir_fails(self):
        """A lib/ dir without a matching test/ dir is reported as uncovered."""
        self._create_dart_file("lib/main.dart")
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertEqual(len(uncovered), 1)
        self.assertIn("lib", uncovered[0])

    def test_empty_test_dir_fails(self):
        """A lib/ dir with a test/ dir but no _test.dart files is uncovered."""
        self._create_dart_file("lib/main.dart")
        (self.flutter_app / "test").mkdir(parents=True)
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertEqual(len(uncovered), 1)

    def test_subdirectory_coverage(self):
        """lib/engine/ requires test/engine/ with _test.dart files."""
        self._create_dart_file("lib/engine/dsh_config.dart")
        self._create_test_file("test/engine/dsh_config_test.dart")
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertEqual(uncovered, [])

    def test_subdirectory_missing_coverage(self):
        """lib/engine/ without test/engine/ is uncovered."""
        self._create_dart_file("lib/engine/dsh_config.dart")
        self._create_test_file("test/widget_test.dart")
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertTrue(any("engine" in d for d in uncovered))

    def test_package_lib_coverage(self):
        """packages/acp_client/lib/ requires packages/acp_client/test/ with _test.dart."""
        self._create_dart_file("packages/acp_client/lib/acp_client.dart")
        self._create_test_file("packages/acp_client/test/acp_client_test.dart")
        uncovered = run_v4_gates.run_meta_test(self.flutter_app)
        self.assertEqual(uncovered, [])


# ---------------------------------------------------------------------------
# Unit tests: validate_pin_file
# ---------------------------------------------------------------------------

class TestValidatePinFile(unittest.TestCase):
    """Unit tests for validate_pin_file -- validates engines/dsh-pin.txt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_pin_file(self):
        """A pin file with dsh_commit and node_version fields passes."""
        pin = self.tmp_path / "dsh-pin.txt"
        pin.write_text("dsh_commit=47f943859b\nnode_version=^22.19.0\n")
        passed, msg = run_v4_gates.validate_pin_file(pin)
        self.assertTrue(passed, msg)

    def test_missing_dsh_commit(self):
        """A pin file without dsh_commit fails."""
        pin = self.tmp_path / "dsh-pin.txt"
        pin.write_text("node_version=^22.19.0\n")
        passed, msg = run_v4_gates.validate_pin_file(pin)
        self.assertFalse(passed)
        self.assertIn("dsh_commit", msg)

    def test_missing_node_version(self):
        """A pin file without node_version fails."""
        pin = self.tmp_path / "dsh-pin.txt"
        pin.write_text("dsh_commit=47f943859b\n")
        passed, msg = run_v4_gates.validate_pin_file(pin)
        self.assertFalse(passed)
        self.assertIn("node_version", msg)

    def test_nonexistent_pin_file(self):
        """A non-existent pin file fails."""
        pin = self.tmp_path / "nonexistent.txt"
        passed, msg = run_v4_gates.validate_pin_file(pin)
        self.assertFalse(passed)


# ---------------------------------------------------------------------------
# Unit tests: validate_cordis_config
# ---------------------------------------------------------------------------

class TestValidateCordisConfig(unittest.TestCase):
    """Unit tests for validate_cordis_config -- validates engines/acp.cordis.yml."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_cordis(self):
        """A cordis config with 'policy: ask' passes."""
        cordis = self.tmp_path / "acp.cordis.yml"
        cordis.write_text("approval:\n  policy: ask\n")
        passed, msg = run_v4_gates.validate_cordis_config(cordis)
        self.assertTrue(passed, msg)

    def test_missing_policy_ask(self):
        """A cordis config without 'policy: ask' fails."""
        cordis = self.tmp_path / "acp.cordis.yml"
        cordis.write_text("approval:\n  policy: never\n")
        passed, msg = run_v4_gates.validate_cordis_config(cordis)
        self.assertFalse(passed)

    def test_nonexistent_cordis(self):
        """A non-existent cordis config fails."""
        cordis = self.tmp_path / "nonexistent.yml"
        passed, msg = run_v4_gates.validate_cordis_config(cordis)
        self.assertFalse(passed)


# ---------------------------------------------------------------------------
# Unit tests: validate_manifest_json
# ---------------------------------------------------------------------------

class TestValidateManifestJson(unittest.TestCase):
    """Unit tests for validate_manifest_json -- validates engine-manifest.json."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_manifest(self):
        """A manifest with all 5 required fields passes."""
        manifest = self.tmp_path / "engine-manifest.json"
        manifest.write_text(json.dumps({
            "engine_version": "1.0.0",
            "dsh_commit": "47f943859b",
            "node_version": "^22.19.0",
            "sha256": "abc123",
            "built_at": "2026-08-13T12:00:00Z",
        }))
        passed, msg = run_v4_gates.validate_manifest_json(manifest)
        self.assertTrue(passed, msg)

    def test_missing_field(self):
        """A manifest missing a required field fails."""
        manifest = self.tmp_path / "engine-manifest.json"
        manifest.write_text(json.dumps({
            "engine_version": "1.0.0",
            "dsh_commit": "47f943859b",
        }))
        passed, msg = run_v4_gates.validate_manifest_json(manifest)
        self.assertFalse(passed)

    def test_empty_field(self):
        """A manifest with an empty required field fails."""
        manifest = self.tmp_path / "engine-manifest.json"
        manifest.write_text(json.dumps({
            "engine_version": "1.0.0",
            "dsh_commit": "47f943859b",
            "node_version": "",
            "sha256": "abc123",
            "built_at": "2026-08-13T12:00:00Z",
        }))
        passed, msg = run_v4_gates.validate_manifest_json(manifest)
        self.assertFalse(passed)

    def test_nonexistent_manifest(self):
        """A non-existent manifest returns (False, skip_message)."""
        manifest = self.tmp_path / "nonexistent.json"
        passed, msg = run_v4_gates.validate_manifest_json(manifest)
        self.assertFalse(passed)
        self.assertIn("not found", msg.lower())


# ---------------------------------------------------------------------------
# Unit tests: gate_engine_manifest (full gate)
# ---------------------------------------------------------------------------

class TestGateEngineManifest(unittest.TestCase):
    """Unit tests for gate_engine_manifest -- full gate with pin + cordis + manifest."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        engines = self.repo_root / "engines"
        engines.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_pin(self, content: str = "dsh_commit=47f943859b\nnode_version=^22.19.0\n"):
        (self.repo_root / "engines" / "dsh-pin.txt").write_text(content)

    def _write_cordis(self, content: str = "approval:\n  policy: ask\n"):
        (self.repo_root / "engines" / "acp.cordis.yml").write_text(content)

    def test_all_present_no_manifest_json(self):
        """Pin + cordis present, no engine-manifest.json -> PASS with SKIP note."""
        self._write_pin()
        self._write_cordis()
        result = run_v4_gates.gate_engine_manifest(self.repo_root)
        self.assertTrue(result.passed)
        self.assertTrue(result.skipped)

    def test_all_present_with_valid_manifest(self):
        """Pin + cordis + valid manifest.json -> PASS."""
        self._write_pin()
        self._write_cordis()
        manifest = self.repo_root / "engines" / "engine-manifest.json"
        manifest.write_text(json.dumps({
            "engine_version": "1.0.0",
            "dsh_commit": "47f943859b",
            "node_version": "^22.19.0",
            "sha256": "abc123",
            "built_at": "2026-08-13T12:00:00Z",
        }))
        result = run_v4_gates.gate_engine_manifest(self.repo_root)
        self.assertTrue(result.passed)
        self.assertFalse(result.skipped)

    def test_missing_pin_fails(self):
        """Missing pin file -> FAIL."""
        self._write_cordis()
        result = run_v4_gates.gate_engine_manifest(self.repo_root)
        self.assertFalse(result.passed)

    def test_missing_cordis_fails(self):
        """Missing cordis config -> FAIL."""
        self._write_pin()
        result = run_v4_gates.gate_engine_manifest(self.repo_root)
        self.assertFalse(result.passed)


# ---------------------------------------------------------------------------
# Unit tests: --check subcommand parsing
# ---------------------------------------------------------------------------

class TestCheckSubcommandParsing(unittest.TestCase):
    """Unit tests for --check subcommand argument parsing."""

    def test_no_check_runs_all(self):
        """No --check argument means run all gates."""
        parser = run_v4_gates._build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.check)

    def test_check_dart_analyze(self):
        parser = run_v4_gates._build_parser()
        args = parser.parse_args(["--check", "dart-analyze"])
        self.assertEqual(args.check, "dart-analyze")

    def test_check_flutter_test(self):
        parser = run_v4_gates._build_parser()
        args = parser.parse_args(["--check", "flutter-test"])
        self.assertEqual(args.check, "flutter-test")

    def test_check_engine_manifest(self):
        parser = run_v4_gates._build_parser()
        args = parser.parse_args(["--check", "engine-manifest"])
        self.assertEqual(args.check, "engine-manifest")

    def test_check_mock_e2e(self):
        parser = run_v4_gates._build_parser()
        args = parser.parse_args(["--check", "mock-e2e"])
        self.assertEqual(args.check, "mock-e2e")

    def test_check_meta_test(self):
        parser = run_v4_gates._build_parser()
        args = parser.parse_args(["--check", "meta-test"])
        self.assertEqual(args.check, "meta-test")

    def test_invalid_check_choice(self):
        """An invalid --check choice raises SystemExit."""
        parser = run_v4_gates._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--check", "invalid-gate"])


# ---------------------------------------------------------------------------
# Integration tests: run the actual script against the real codebase
# ---------------------------------------------------------------------------

class TestIntegrationMetaTest(unittest.TestCase):
    """Integration tests: run the actual script against the real codebase."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]

    def test_meta_test_exits_0(self):
        """run_v4_gates.py --check meta-test exits 0 on current codebase."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "run_v4_gates.py"), "--check", "meta-test"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"meta-test failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_engine_manifest_exits_0(self):
        """run_v4_gates.py --check engine-manifest exits 0."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "run_v4_gates.py"), "--check", "engine-manifest"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"engine-manifest failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_negative_meta_test_fails(self):
        """run_v4_gates.py --check meta-test exits 1 when a lib/ dir without tests is created."""
        tmp_lib = self.repo_root / "apps" / "flutter_app" / "lib" / "_tmp_negative_test"
        tmp_lib.mkdir(parents=True, exist_ok=True)
        (tmp_lib / "stub.dart").write_text("// temporary stub for negative test\n")
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "run_v4_gates.py"), "--check", "meta-test"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode, 1,
                f"meta-test should have failed for uncovered dir:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
        finally:
            shutil.rmtree(tmp_lib, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
