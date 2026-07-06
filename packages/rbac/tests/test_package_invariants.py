"""Tests for package invariants (dependencies = [], stdlib-only imports)."""

from __future__ import annotations

import pathlib
import unittest

import rbac
import rbac.guard
import rbac.identity
import rbac.matrix
import rbac.roles
import rbac.token

PYPROJECT = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"


class PackageInvariantTests(unittest.TestCase):
    def test_pyproject_dependencies_empty(self) -> None:
        text = PYPROJECT.read_text()
        self.assertIn("dependencies = []", text)

    def test_package_imports_cleanly(self) -> None:
        # If any import failed, the top-level imports above would have raised.
        self.assertIsNotNone(rbac)
        self.assertIsNotNone(rbac.guard)
        self.assertIsNotNone(rbac.identity)
        self.assertIsNotNone(rbac.matrix)
        self.assertIsNotNone(rbac.roles)
        self.assertIsNotNone(rbac.token)

    def test_no_external_runtime_imports(self) -> None:
        # All rbac modules should only import stdlib + relative at top level.
        # identity.py has a lazy import of admin_console_api.auth INSIDE the
        # function body (indented) — that is allowed.  Only unindented
        # (top-level) imports are checked here.
        import inspect

        allowed_stdlib = ("enum", "typing", "dataclasses", "base64", "hashlib", "hmac", "json", "time", "pathlib")
        for module in (rbac.roles, rbac.matrix, rbac.guard, rbac.token, rbac.identity):
            source = inspect.getsource(module)
            for line in source.splitlines():
                # Only check top-level imports (no leading whitespace).
                if line.startswith(" ") or line.startswith("\t"):
                    continue
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    if stripped.startswith("from ."):
                        continue
                    if stripped.startswith("from __future__"):
                        continue
                    self.assertTrue(
                        any(
                            stripped.startswith(f"import {a}")
                            or stripped.startswith(f"from {a}")
                            for a in allowed_stdlib
                        ),
                        f"Unexpected top-level import in {module.__name__}: {stripped}",
                    )


if __name__ == "__main__":
    unittest.main()
