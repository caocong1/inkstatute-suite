"""Tests for the RBAC annotation CI scan (``scripts/scan_rbac_annotations.py``)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.scan_rbac_annotations import find_unannotated

REPO_ROOT = Path(__file__).resolve().parents[3]


class FindUnannotatedTests(unittest.TestCase):
    def test_find_unannotated_returns_empty_when_all_annotated(self) -> None:
        matrix = {"/sessions": object(), "/tasks": object()}
        self.assertEqual(find_unannotated(["/sessions", "/tasks"], matrix), [])

    def test_find_unannotated_returns_missing(self) -> None:
        matrix = {"/sessions": object()}
        self.assertEqual(
            find_unannotated(["/sessions", "/unknown"], matrix),
            ["/unknown"],
        )

    def test_find_unannotated_empty_routes(self) -> None:
        self.assertEqual(find_unannotated([], {"/sessions": object()}), [])

    def test_find_unannotated_preserves_order(self) -> None:
        matrix = {"/a": object()}
        result = find_unannotated(["/z", "/a", "/y"], matrix)
        self.assertEqual(result, ["/z", "/y"])


class RealRoutesAnnotatedTests(unittest.TestCase):
    def test_all_real_routes_annotated(self) -> None:
        from admin_console_api.routes import ROUTE_PREFIXES
        from rbac.matrix import PERMISSIONS_MATRIX

        self.assertEqual(find_unannotated(ROUTE_PREFIXES, PERMISSIONS_MATRIX), [])


class ScanScriptExitCodeTests(unittest.TestCase):
    def _scan_env(self) -> dict[str, str]:
        env = os.environ.copy()
        rbac_src = str(REPO_ROOT / "packages" / "rbac" / "src")
        admin_src = str(REPO_ROOT / "services" / "admin-console-api" / "src")
        platform_src = str(REPO_ROOT / "packages" / "platform-contract" / "src")
        platform_runtime_src = str(
            REPO_ROOT / "packages" / "platform-runtime" / "src"
        )
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(
            [rbac_src, admin_src, platform_src, platform_runtime_src, existing]
            if existing
            else [rbac_src, admin_src, platform_src, platform_runtime_src]
        )
        return env

    def test_scan_script_exits_zero_when_annotated(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/scan_rbac_annotations.py"],
            cwd=REPO_ROOT,
            env=self._scan_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"scan failed: {completed.stderr}",
        )
        self.assertIn("OK: all", completed.stdout)


if __name__ == "__main__":
    unittest.main()
