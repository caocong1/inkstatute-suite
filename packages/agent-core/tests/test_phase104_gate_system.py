"""Phase 104-03: Freeze multi-agent-adapter + gate system verification.

Verifies that:
- ``packages/multi-agent-adapter/FROZEN.md`` exists with the experimental
  designation.
- The multi-agent-adapter package still compiles (frozen, not deleted).
- All 4 retired gates (codex-backend, hermes-contract-layer, lawyer-web-chat,
  web-sse-channel) are removed from ``run_v2_gates.py``.
- The compileall gate does not include retired package paths.
- All new packages (acp-client, skill-index, agent-core, ui-core, gateway)
  have gates in ``run_v2_gates.py``.
- The multi-agent-adapter gate still exists (frozen, not removed).
- The gate-coverage meta-test logic passes — every ``packages/*/src`` and
  ``services/*/src`` directory on disk is covered by at least one gate.
"""

from __future__ import annotations

import py_compile
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Retired gate names that must NOT appear in run_v2_gates.py.
RETIRED_GATE_NAMES = frozenset(
    {"codex-backend", "hermes-contract-layer", "lawyer-web-chat", "web-sse-channel"}
)

# Retired package/service src paths that must NOT appear in the compileall gate.
RETIRED_COMPILEALL_PATHS = frozenset(
    {
        "packages/backends/hermes/src",
        "packages/backends/codex/src",
        "services/hermes-contract-layer/src",
        "services/lawyer-web-chat/src",
        "services/web-sse-channel/src",
    }
)

# New packages that MUST have gates in run_v2_gates.py.
NEW_PACKAGE_GATE_NAMES = frozenset(
    {"acp-client", "skill-index", "agent-core", "ui-core", "gateway"}
)


def _gates():
    """Import and call run_v2_gates._gates() to get the current gate list."""
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from run_v2_gates import _gates as _build_gates

    return _build_gates(REPO_ROOT)


class TestMultiAgentAdapterFrozen(unittest.TestCase):
    """The multi-agent-adapter package must be frozen, not deleted."""

    def test_multi_agent_adapter_frozen_md_exists(self) -> None:
        """FROZEN.md must exist in packages/multi-agent-adapter/."""
        frozen_md = REPO_ROOT / "packages" / "multi-agent-adapter" / "FROZEN.md"
        self.assertTrue(
            frozen_md.exists(),
            "packages/multi-agent-adapter/FROZEN.md must exist",
        )
        text = frozen_md.read_text(encoding="utf-8")
        self.assertIn("frozen", text.lower())
        self.assertIn("experimental", text.lower())

    def test_multi_agent_adapter_still_compiles(self) -> None:
        """The package source must still compile via compileall."""
        src_dir = REPO_ROOT / "packages" / "multi-agent-adapter" / "src"
        self.assertTrue(src_dir.exists(), "multi-agent-adapter/src must still exist")
        # Compile every .py file in the src tree.
        py_files = sorted(src_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "multi-agent-adapter must have .py files")
        for py_file in py_files:
            with self.subTest(file=str(py_file.relative_to(REPO_ROOT))):
                py_compile.compile(str(py_file), doraise=True)


class TestRetiredGatesRemoved(unittest.TestCase):
    """Retired gates from Phase 104-01 and 104-02 must be removed."""

    def test_no_removed_gates_in_run_v2_gates(self) -> None:
        """None of the 4 retired gate names may appear in the gate list."""
        gate_names = [gate.name for gate in _gates()]
        for retired in RETIRED_GATE_NAMES:
            with self.subTest(gate=retired):
                self.assertNotIn(
                    retired,
                    gate_names,
                    f"Retired gate '{retired}' must not be in run_v2_gates.py",
                )


class TestCompileallPaths(unittest.TestCase):
    """The compileall gate must not include retired package paths."""

    def test_compileall_does_not_include_retired_paths(self) -> None:
        """No retired package/service src path may appear in compileall args."""
        compileall_gate = None
        for gate in _gates():
            if "compileall" in gate.command:
                compileall_gate = gate
                break
        self.assertIsNotNone(compileall_gate, "compileall gate must exist")
        command_args = [str(arg) for arg in compileall_gate.command]
        for retired_path in RETIRED_COMPILEALL_PATHS:
            with self.subTest(path=retired_path):
                self.assertNotIn(
                    retired_path,
                    command_args,
                    f"Retired path '{retired_path}' must not be in compileall",
                )


class TestNewPackageGates(unittest.TestCase):
    """All new V3 packages must have gates in run_v2_gates.py."""

    def test_new_packages_have_gates(self) -> None:
        """acp-client, skill-index, agent-core, ui-core, gateway must have gates."""
        gate_names = [gate.name for gate in _gates()]
        for pkg in NEW_PACKAGE_GATE_NAMES:
            with self.subTest(package=pkg):
                self.assertIn(
                    pkg,
                    gate_names,
                    f"New package '{pkg}' must have a gate in run_v2_gates.py",
                )

    def test_multi_agent_adapter_gate_exists(self) -> None:
        """The multi-agent-adapter gate must still exist (frozen, not removed)."""
        gate_names = [gate.name for gate in _gates()]
        self.assertIn(
            "multi-agent-adapter",
            gate_names,
            "multi-agent-adapter gate must still exist (frozen, not removed)",
        )


class TestGateCoverage(unittest.TestCase):
    """The gate-coverage meta-test logic must pass for all on-disk packages."""

    def test_all_remaining_packages_have_gates(self) -> None:
        """Every packages/*/src and services/*/src directory must be covered."""
        covered: set[Path] = set()
        for gate in _gates():
            for p in gate.pythonpath:
                covered.add(Path(p).resolve())
            if "compileall" in gate.command:
                for arg in gate.command:
                    if isinstance(arg, str) and arg.endswith("/src"):
                        covered.add((REPO_ROOT / arg).resolve())

        on_disk_packages = {p.resolve() for p in (REPO_ROOT / "packages").glob("*/src")}
        on_disk_services = {p.resolve() for p in (REPO_ROOT / "services").glob("*/src")}
        on_disk = on_disk_packages | on_disk_services

        uncovered = on_disk - covered
        self.assertEqual(
            uncovered,
            set(),
            f"Uncovered src directories: {sorted(str(p) for p in uncovered)}",
        )


if __name__ == "__main__":
    unittest.main()
