"""Tests for package invariants (dependencies = [], stdlib-only imports)."""

from __future__ import annotations

import pathlib
import unittest

import rbac
import rbac.guard
import rbac.matrix
import rbac.roles

PYPROJECT = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"


class PackageInvariantTests(unittest.TestCase):
    def test_pyproject_dependencies_empty(self) -> None:
        text = PYPROJECT.read_text()
        self.assertIn("dependencies = []", text)

    def test_package_imports_cleanly(self) -> None:
        # If any import failed, the top-level imports above would have raised.
        self.assertIsNotNone(rbac)
        self.assertIsNotNone(rbac.guard)
        self.assertIsNotNone(rbac.matrix)
        self.assertIsNotNone(rbac.roles)

    def test_no_external_runtime_imports(self) -> None:
        # roles.py and matrix.py and guard.py should only import stdlib + relative.
        import inspect

        for module in (rbac.roles, rbac.matrix, rbac.guard):
            source = inspect.getsource(module)
            # No third-party top-level imports — only stdlib (enum, typing) and relative (.roles, .matrix).
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    if stripped.startswith("from ."):
                        continue
                    if stripped.startswith("from __future__"):
                        continue
                    # Allowed stdlib modules.
                    allowed = ("enum", "typing", "dataclasses")
                    self.assertTrue(
                        any(stripped.startswith(f"import {a}") or stripped.startswith(f"from {a}") for a in allowed)
                        or stripped.startswith("from __future__"),
                        f"Unexpected import in {module.__name__}: {stripped}",
                    )


if __name__ == "__main__":
    unittest.main()
