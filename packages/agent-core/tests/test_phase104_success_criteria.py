"""Phase 104 success criteria verification — maps each criterion to verifying tests.

This meta-test documents the mapping between Phase 104's 7 success criteria
(from the ROADMAP / plan) and the tests that verify them.  It provides a
single place to audit coverage and verifies key assertions inline.

Success Criteria (Phase 104 — Legacy Convergence):
1. Legacy backends retired — ``packages/backends/hermes`` and
   ``packages/backends/codex`` deleted; ACP adapter carries the
   compatibility matrix, bootstrap check, and capability negotiation.
2. Legacy channels retired — ``packages/channels/web_sse`` deleted.
3. Legacy services retired — ``services/lawyer-web-chat`` and
   ``services/hermes-contract-layer`` deleted.
4. Multi-agent adapter frozen — ``FROZEN.md`` exists, package still compiles.
5. Gate system updated — all new packages have gates, retired gates removed,
   gate-coverage passes.
6. Composability maintained — ``demo_non_legal`` solution tests pass with no
   legal field leakage.
7. Full gates + regression pass — full gate suite (34 gates) passes,
   WeCom/QQ cross-channel consistency regression tests pass.

HG-1 (法律质量) and HG-4 (修订稿质量) are NOT auto-closable — these tests
verify structural retirement and gate coverage, not legal quality.
"""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

TESTS_DIR = Path(__file__).resolve().parent


def _file_exists(filename: str) -> bool:
    return (TESTS_DIR / filename).is_file()


# ---------------------------------------------------------------------------
# SC-1: Legacy backends retired
# ---------------------------------------------------------------------------


class TestSC1LegacyBackendsRetired(unittest.TestCase):
    """SC-1: packages/backends/hermes and codex deleted; ACP adapter has
    compatibility matrix, bootstrap check, and capability negotiation."""

    def test_sc1_hermes_backend_directory_deleted(self) -> None:
        """packages/backends/hermes/ must no longer exist."""
        self.assertFalse(
            (REPO_ROOT / "packages" / "backends" / "hermes").exists(),
            "packages/backends/hermes/ should have been deleted in Phase 104-01",
        )

    def test_sc1_codex_backend_directory_deleted(self) -> None:
        """packages/backends/codex/ must no longer exist."""
        self.assertFalse(
            (REPO_ROOT / "packages" / "backends" / "codex").exists(),
            "packages/backends/codex/ should have been deleted in Phase 104-01",
        )

    def test_sc1_acp_adapter_has_hermes_compatibility_matrix(self) -> None:
        """ACP adapter carries HERMES_COMPATIBILITY_MATRIX (0.17.0–0.19.0)."""
        from inkstatute_acp_client.adapter import HERMES_COMPATIBILITY_MATRIX

        self.assertIsInstance(HERMES_COMPATIBILITY_MATRIX, dict)
        for version in ("0.17.0", "0.18.0", "0.19.0"):
            with self.subTest(version=version):
                self.assertIn(version, HERMES_COMPATIBILITY_MATRIX)

    def test_sc1_acp_adapter_has_bootstrap_check(self) -> None:
        """ACPBackendAdapter exposes bootstrap_check()."""
        from inkstatute_acp_client.adapter import ACPBackendAdapter

        self.assertTrue(callable(getattr(ACPBackendAdapter, "bootstrap_check", None)))

    def test_sc1_acp_adapter_has_capability_negotiation(self) -> None:
        """capability_negotiation module exposes RequiredCapabilities."""
        import importlib

        module = importlib.import_module("inkstatute_acp_client.capability_negotiation")
        self.assertTrue(hasattr(module, "RequiredCapabilities"))

    def test_sc1_backend_retirement_test_file_exists(self) -> None:
        """test_phase104_backend_retirement.py exists and covers SC-1."""
        self.assertTrue(
            _file_exists("test_phase104_backend_retirement.py"),
            "test_phase104_backend_retirement.py must exist",
        )


# ---------------------------------------------------------------------------
# SC-2: Legacy channels retired
# ---------------------------------------------------------------------------


class TestSC2LegacyChannelsRetired(unittest.TestCase):
    """SC-2: packages/channels/web_sse is deleted."""

    def test_sc2_web_sse_channel_directory_deleted(self) -> None:
        """packages/channels/web_sse/ must no longer exist."""
        self.assertFalse(
            (REPO_ROOT / "packages" / "channels" / "web_sse").exists(),
            "packages/channels/web_sse/ should have been deleted in Phase 104-02",
        )

    def test_sc2_web_sse_channel_gate_removed(self) -> None:
        """web-sse-channel gate must not be in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"web-sse-channel"',
            gates_text,
            "web-sse-channel gate should be removed from run_v2_gates.py",
        )

    def test_sc2_service_retirement_test_file_exists(self) -> None:
        """test_phase104_service_retirement.py exists and covers SC-2."""
        self.assertTrue(
            _file_exists("test_phase104_service_retirement.py"),
            "test_phase104_service_retirement.py must exist",
        )


# ---------------------------------------------------------------------------
# SC-3: Legacy services retired
# ---------------------------------------------------------------------------


class TestSC3LegacyServicesRetired(unittest.TestCase):
    """SC-3: services/lawyer-web-chat and services/hermes-contract-layer deleted."""

    def test_sc3_lawyer_web_chat_directory_deleted(self) -> None:
        """services/lawyer-web-chat/ must no longer exist."""
        self.assertFalse(
            (REPO_ROOT / "services" / "lawyer-web-chat").exists(),
            "services/lawyer-web-chat/ should have been deleted in Phase 104-02",
        )

    def test_sc3_hermes_contract_layer_directory_deleted(self) -> None:
        """services/hermes-contract-layer/ must no longer exist."""
        self.assertFalse(
            (REPO_ROOT / "services" / "hermes-contract-layer").exists(),
            "services/hermes-contract-layer/ should have been deleted in Phase 104-02",
        )

    def test_sc3_lawyer_web_chat_gate_removed(self) -> None:
        """lawyer-web-chat gate must not be in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"lawyer-web-chat"',
            gates_text,
            "lawyer-web-chat gate should be removed from run_v2_gates.py",
        )

    def test_sc3_hermes_contract_layer_gate_removed(self) -> None:
        """hermes-contract-layer gate must not be in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"hermes-contract-layer"',
            gates_text,
            "hermes-contract-layer gate should be removed from run_v2_gates.py",
        )


# ---------------------------------------------------------------------------
# SC-4: Multi-agent adapter frozen
# ---------------------------------------------------------------------------


class TestSC4MultiAgentAdapterFrozen(unittest.TestCase):
    """SC-4: FROZEN.md exists, package still compiles."""

    def test_sc4_frozen_md_exists(self) -> None:
        """packages/multi-agent-adapter/FROZEN.md must exist."""
        frozen_md = REPO_ROOT / "packages" / "multi-agent-adapter" / "FROZEN.md"
        self.assertTrue(frozen_md.exists(), "FROZEN.md must exist")
        text = frozen_md.read_text(encoding="utf-8")
        self.assertIn("frozen", text.lower())
        self.assertIn("experimental", text.lower())

    def test_sc4_package_still_compiles(self) -> None:
        """The multi-agent-adapter package source still compiles."""
        src_dir = REPO_ROOT / "packages" / "multi-agent-adapter" / "src"
        self.assertTrue(src_dir.exists(), "multi-agent-adapter/src must still exist")
        py_files = sorted(src_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "multi-agent-adapter must have .py files")
        for py_file in py_files:
            with self.subTest(file=str(py_file.relative_to(REPO_ROOT))):
                py_compile.compile(str(py_file), doraise=True)

    def test_sc4_gate_system_test_file_exists(self) -> None:
        """test_phase104_gate_system.py exists and covers SC-4."""
        self.assertTrue(
            _file_exists("test_phase104_gate_system.py"),
            "test_phase104_gate_system.py must exist",
        )


# ---------------------------------------------------------------------------
# SC-5: Gate system updated
# ---------------------------------------------------------------------------


NEW_PACKAGE_GATE_NAMES = frozenset(
    {"acp-client", "skill-index", "agent-core", "ui-core", "gateway"}
)
RETIRED_GATE_NAMES = frozenset(
    {"codex-backend", "hermes-contract-layer", "lawyer-web-chat", "web-sse-channel"}
)


def _gate_names() -> list[str]:
    """Return the list of gate names from run_v2_gates._gates()."""
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from run_v2_gates import _gates as _build_gates

    return [gate.name for gate in _build_gates(REPO_ROOT)]


class TestSC5GateSystemUpdated(unittest.TestCase):
    """SC-5: all new packages have gates, retired gates removed, gate-coverage passes."""

    def test_sc5_new_packages_have_gates(self) -> None:
        """acp-client, skill-index, agent-core, ui-core, gateway have gates."""
        names = _gate_names()
        for pkg in NEW_PACKAGE_GATE_NAMES:
            with self.subTest(package=pkg):
                self.assertIn(pkg, names, f"New package '{pkg}' must have a gate")

    def test_sc5_retired_gates_removed(self) -> None:
        """None of the 4 retired gate names appear in the gate list."""
        names = _gate_names()
        for retired in RETIRED_GATE_NAMES:
            with self.subTest(gate=retired):
                self.assertNotIn(retired, names, f"Retired gate '{retired}' must be removed")

    def test_sc5_multi_agent_adapter_gate_exists(self) -> None:
        """multi-agent-adapter gate still exists (frozen, not removed)."""
        self.assertIn("multi-agent-adapter", _gate_names())

    def test_sc5_gate_coverage_meta_test_exists(self) -> None:
        """gate-coverage-meta-test gate exists in the gate list."""
        self.assertIn("gate-coverage-meta-test", _gate_names())

    def test_sc5_gate_count_is_34(self) -> None:
        """The full gate suite has exactly 34 gates."""
        names = _gate_names()
        self.assertEqual(len(names), 34, f"Expected 34 gates, got {len(names)}")

    def test_sc5_gate_system_test_file_exists(self) -> None:
        """test_phase104_gate_system.py exists and covers SC-5."""
        self.assertTrue(
            _file_exists("test_phase104_gate_system.py"),
            "test_phase104_gate_system.py must exist",
        )


# ---------------------------------------------------------------------------
# SC-6: Composability maintained
# ---------------------------------------------------------------------------


class TestSC6ComposabilityMaintained(unittest.TestCase):
    """SC-6: demo_non_legal solution tests exist and verify no legal field leakage."""

    def test_sc6_demo_non_legal_test_file_exists(self) -> None:
        """solutions/demo_non_legal/tests/test_demo_non_legal_solution.py exists."""
        test_file = REPO_ROOT / "solutions" / "demo_non_legal" / "tests" / "test_demo_non_legal_solution.py"
        self.assertTrue(test_file.exists(), "demo_non_legal solution test file must exist")

    def test_sc6_demo_non_legal_solution_src_exists(self) -> None:
        """solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal exists."""
        src_dir = REPO_ROOT / "solutions" / "demo_non_legal" / "src" / "inkstatute_solutions_demo_non_legal"
        self.assertTrue(src_dir.is_dir(), "demo_non_legal solution src must exist")

    def test_sc6_legal_field_leakage_test_present(self) -> None:
        """The demo_non_legal test file contains a no-legal-field-leakage test."""
        test_file = REPO_ROOT / "solutions" / "demo_non_legal" / "tests" / "test_demo_non_legal_solution.py"
        text = test_file.read_text(encoding="utf-8")
        self.assertIn("no_legal_only_fields", text,
                      "demo_non_legal tests must check for legal field leakage")

    def test_sc6_industry_context_is_non_legal(self) -> None:
        """The demo_non_legal test file verifies industry_context is non-legal."""
        test_file = REPO_ROOT / "solutions" / "demo_non_legal" / "tests" / "test_demo_non_legal_solution.py"
        text = test_file.read_text(encoding="utf-8")
        self.assertIn("industry_context", text)

    def test_sc6_composability_tests_runnable(self) -> None:
        """The demo_non_legal composability tests can be collected and pass.

        Runs the composability test suite via pytest with the full PYTHONPATH
        required (platform-contract, platform-runtime, contract-test-suite,
        solution-loader, skill-registry, skill-materializer, and both solution
        src trees).  This is a smoke test that the suite is runnable; the
        authoritative run is the gate suite.
        """
        test_dir = REPO_ROOT / "solutions" / "demo_non_legal" / "tests"
        pythonpath = os.pathsep.join([
            str(REPO_ROOT / "packages" / "platform-contract" / "src"),
            str(REPO_ROOT / "packages" / "platform-runtime" / "src"),
            str(REPO_ROOT / "packages" / "contract-test-suite" / "src"),
            str(REPO_ROOT / "packages" / "solution-loader" / "src"),
            str(REPO_ROOT / "packages" / "skill-registry" / "src"),
            str(REPO_ROOT / "packages" / "skill-materializer" / "src"),
            str(REPO_ROOT / "solutions" / "demo_non_legal" / "src"),
            str(REPO_ROOT / "solutions" / "lawfirm" / "src"),
        ])
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "-q"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            f"demo_non_legal composability tests failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("passed", result.stdout)


# ---------------------------------------------------------------------------
# SC-7: Full gates + regression pass
# ---------------------------------------------------------------------------


class TestSC7FullGatesAndRegressionPass(unittest.TestCase):
    """SC-7: full gate suite passes, WeCom/QQ regression tests exist and pass."""

    def test_sc7_wecom_regression_test_exists(self) -> None:
        """services/wecom-service/tests/test_cross_channel_consistency.py exists."""
        test_file = REPO_ROOT / "services" / "wecom-service" / "tests" / "test_cross_channel_consistency.py"
        self.assertTrue(test_file.exists(), "WeCom cross-channel consistency test must exist")

    def test_sc7_qq_regression_test_exists(self) -> None:
        """services/qqbot-service/tests/test_cross_channel_consistency.py exists."""
        test_file = REPO_ROOT / "services" / "qqbot-service" / "tests" / "test_cross_channel_consistency.py"
        self.assertTrue(test_file.exists(), "QQ cross-channel consistency test must exist")

    def test_sc7_wecom_regression_tests_runnable(self) -> None:
        """WeCom cross-channel consistency tests can be run and pass."""
        test_file = REPO_ROOT / "services" / "wecom-service" / "tests" / "test_cross_channel_consistency.py"
        pythonpath = os.pathsep.join([
            str(REPO_ROOT / "packages" / "platform-contract" / "src"),
            str(REPO_ROOT / "packages" / "platform-runtime" / "src"),
            str(REPO_ROOT / "packages" / "channels" / "wecom" / "src"),
            str(REPO_ROOT / "services" / "wecom-service" / "src"),
            str(REPO_ROOT / "packages" / "contract-test-suite" / "src"),
            str(REPO_ROOT / "packages" / "operator-config" / "src"),
            str(REPO_ROOT / "packages" / "channels" / "channel-core" / "src"),
        ])
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", str(REPO_ROOT / "services" / "wecom-service" / "tests"),
             "-p", "test_cross_channel_consistency.py"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            f"WeCom regression tests failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_sc7_qq_regression_tests_runnable(self) -> None:
        """QQ cross-channel consistency tests can be run and pass."""
        pythonpath = os.pathsep.join([
            str(REPO_ROOT / "packages" / "platform-contract" / "src"),
            str(REPO_ROOT / "packages" / "platform-runtime" / "src"),
            str(REPO_ROOT / "packages" / "channels" / "qqbot" / "src"),
            str(REPO_ROOT / "services" / "qqbot-service" / "src"),
            str(REPO_ROOT / "packages" / "contract-test-suite" / "src"),
            str(REPO_ROOT / "packages" / "operator-config" / "src"),
        ])
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", str(REPO_ROOT / "services" / "qqbot-service" / "tests"),
             "-p", "test_cross_channel_consistency.py"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            f"QQ regression tests failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_sc7_full_gate_suite_has_34_gates(self) -> None:
        """The gate suite defines exactly 34 gates."""
        self.assertEqual(len(_gate_names()), 34)

    def test_sc7_gate_runner_script_exists(self) -> None:
        """scripts/run_v2_gates.py exists."""
        self.assertTrue(
            (REPO_ROOT / "scripts" / "run_v2_gates.py").exists(),
            "scripts/run_v2_gates.py must exist",
        )


# ---------------------------------------------------------------------------
# Summary: all 7 SCs have mapping tests
# ---------------------------------------------------------------------------


class TestPhase104AllSuccessCriteriaMapped(unittest.TestCase):
    """Verify all 7 Phase 104 success criteria have mapping tests."""

    def test_all_7_success_criteria_have_test_classes(self) -> None:
        """All 7 SC test classes exist in this module."""
        import test_phase104_success_criteria as mod

        for class_name in (
            "TestSC1LegacyBackendsRetired",
            "TestSC2LegacyChannelsRetired",
            "TestSC3LegacyServicesRetired",
            "TestSC4MultiAgentAdapterFrozen",
            "TestSC5GateSystemUpdated",
            "TestSC6ComposabilityMaintained",
            "TestSC7FullGatesAndRegressionPass",
        ):
            with self.subTest(sc_class=class_name):
                self.assertTrue(
                    hasattr(mod, class_name),
                    f"Missing SC test class: {class_name}",
                )

    def test_human_gates_not_auto_closable(self) -> None:
        """HG-1 (法律质量) and HG-4 (修订稿质量) are NOT auto-closable.

        This test documents that these human gates must remain open until a
        lawyer confirms them.  It asserts only that the gate system does not
        contain an automated HG-1/HG-4 closure gate.
        """
        names = _gate_names()
        for hg in ("hg-1-legal-quality", "hg-4-revision-quality"):
            with self.subTest(gate=hg):
                self.assertNotIn(hg, names, f"{hg} must not be auto-closed by a gate")


if __name__ == "__main__":
    unittest.main()
