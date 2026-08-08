"""Meta-test: assert every packages/*/src and services/*/src directory is covered by a V2
gate. A directory is covered if it appears in any gate's PYTHONPATH tuple or in the
compileall gate's command path arguments. Uses runtime inspection of
scripts/run_v2_gates._gates() — no static parsing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _gates():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from run_v2_gates import _gates as _build_gates

    return _build_gates(REPO_ROOT)


class TestGateCoverage(unittest.TestCase):
    def _all_covered_src_paths(self):
        """Return a set of resolved Path objects covered by any gate."""
        covered = set()
        for gate in _gates():
            for p in gate.pythonpath:
                covered.add(Path(p).resolve())
            if "compileall" in gate.command:
                for arg in gate.command:
                    if isinstance(arg, str) and arg.endswith("/src"):
                        covered.add((REPO_ROOT / arg).resolve())
        return covered

    def test_all_packages_src_covered(self):
        """Every packages/*/src directory is covered by at least one gate."""
        on_disk = {p.resolve() for p in (REPO_ROOT / "packages").glob("*/src")}
        covered = self._all_covered_src_paths()
        uncovered = on_disk - covered
        self.assertEqual(
            uncovered,
            set(),
            f"Uncovered packages/*/src: {sorted(str(p) for p in uncovered)}",
        )

    def test_all_services_src_covered(self):
        """Every services/*/src directory is covered by at least one gate."""
        on_disk = {p.resolve() for p in (REPO_ROOT / "services").glob("*/src")}
        covered = self._all_covered_src_paths()
        uncovered = on_disk - covered
        self.assertEqual(
            uncovered,
            set(),
            f"Uncovered services/*/src: {sorted(str(p) for p in uncovered)}",
        )

    def test_gate_count_meets_baseline(self):
        """Gate count meets the Phase 106 baseline (35 gates: 34 existing + fs-sandbox-escape)."""
        self.assertGreaterEqual(len(_gates()), 35)


if __name__ == "__main__":
    unittest.main()
