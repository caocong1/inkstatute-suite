"""Phase 104-01: Legacy backend retirement verification.

Verifies that the legacy ``packages/backends/hermes`` and
``packages/backends/codex`` packages have been retired and that the
``ACPBackendAdapter`` in ``packages/acp-client`` is a functional superset
carrying the compatibility matrix, bootstrap check, and capability
negotiation logic formerly implemented in the per-backend adapters.
"""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestACPAdapterParity(unittest.TestCase):
    """The ACP adapter must carry all capabilities from the legacy backends."""

    def test_acp_adapter_has_hermes_compatibility_matrix(self) -> None:
        """HERMES_COMPATIBILITY_MATRIX must exist with versions 0.17.0–0.19.0."""
        from inkstatute_acp_client.adapter import HERMES_COMPATIBILITY_MATRIX

        self.assertIsInstance(HERMES_COMPATIBILITY_MATRIX, dict)
        for version in ("0.17.0", "0.18.0", "0.19.0"):
            with self.subTest(version=version):
                self.assertIn(version, HERMES_COMPATIBILITY_MATRIX)

    def test_acp_adapter_has_bootstrap_check(self) -> None:
        """ACPBackendAdapter must expose a bootstrap_check() method."""
        from inkstatute_acp_client.adapter import ACPBackendAdapter

        self.assertTrue(callable(getattr(ACPBackendAdapter, "bootstrap_check", None)))

    def test_acp_adapter_has_capability_negotiation(self) -> None:
        """The capability_negotiation module must be importable."""
        module = importlib.import_module("inkstatute_acp_client.capability_negotiation")
        self.assertTrue(hasattr(module, "RequiredCapabilities"))


class TestLegacyBackendDeletion(unittest.TestCase):
    """The legacy backend package directories must no longer exist."""

    def test_no_backends_hermes_directory_exists(self) -> None:
        self.assertFalse(
            (REPO_ROOT / "packages" / "backends" / "hermes").exists(),
            "packages/backends/hermes/ should have been deleted",
        )

    def test_no_backends_codex_directory_exists(self) -> None:
        self.assertFalse(
            (REPO_ROOT / "packages" / "backends" / "codex").exists(),
            "packages/backends/codex/ should have been deleted",
        )


class TestGateSystemUpdated(unittest.TestCase):
    """The codex-backend gate must be removed from run_v2_gates.py."""

    def test_codex_backend_gate_removed(self) -> None:
        import sys

        scripts_dir = str(REPO_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from run_v2_gates import _gates

        gate_names = [gate.name for gate in _gates(REPO_ROOT)]
        self.assertNotIn("codex-backend", gate_names)


class TestNoLegacyBackendImports(unittest.TestCase):
    """No Python file in the repository may import from the legacy backends."""

    def test_no_imports_from_legacy_backends(self) -> None:
        """No Python file may import from inkstatute_backends_hermes/codex.

        String references (e.g. in boundary-check forbidden lists) are allowed;
        only actual ``import`` / ``from … import`` statements are flagged.
        """
        import re

        legacy_modules = ("inkstatute_backends_hermes", "inkstatute_backends_codex")
        # Match actual import statements, not string literals in forbidden lists.
        import_pattern = re.compile(
            r"^\s*(?:from\s+({mods})\b|import\s+({mods})\b)".format(
                mods="|".join(legacy_modules)
            ),
            re.MULTILINE,
        )

        offenders: list[str] = []

        for py_file in REPO_ROOT.rglob("*.py"):
            # Skip files inside .planning (documentation, not code).
            if ".planning" in py_file.parts:
                continue
            # Skip __pycache__ bytecode caches.
            if "__pycache__" in py_file.parts:
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if import_pattern.search(text):
                offenders.append(str(py_file))

        self.assertEqual(
            offenders,
            [],
            f"Python files still import from legacy backend modules: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
