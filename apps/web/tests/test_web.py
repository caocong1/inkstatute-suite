"""Gate tests for @inkstatute/web package structure.

These tests run as part of the V2 gate system (python -m unittest discover).
They verify the web app scaffold exists and that the TypeScript source files
contain the expected structure. When bun/vitest is available, the actual TS
test suite is also executed via subprocess.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PKG_ROOT / "src"


class WebScaffoldTests(unittest.TestCase):
    """Assert the web app scaffold exists with required files."""

    def test_package_json_exists(self) -> None:
        pkg = PKG_ROOT / "package.json"
        self.assertTrue(pkg.exists(), f"package.json not found at {pkg}")
        text = pkg.read_text(encoding="utf-8")
        self.assertIn("@inkstatute/web", text)
        self.assertIn('"private": true', text)
        self.assertIn("@inkstatute/ui-core", text)
        self.assertIn("@inkstatute/platform-sdk-ts", text)
        self.assertIn("@solidjs/router", text)
        self.assertIn("workspace:*", text)

    def test_tsconfig_exists(self) -> None:
        tsconfig = PKG_ROOT / "tsconfig.json"
        self.assertTrue(tsconfig.exists(), f"tsconfig.json not found at {tsconfig}")
        text = tsconfig.read_text(encoding="utf-8")
        self.assertIn('"strict": true', text)
        self.assertIn('"jsx": "preserve"', text)
        self.assertIn("solid-js", text)

    def test_vite_config_exists(self) -> None:
        vite = PKG_ROOT / "vite.config.ts"
        self.assertTrue(vite.exists(), f"vite.config.ts not found at {vite}")
        text = vite.read_text(encoding="utf-8")
        self.assertIn("vite-plugin-solid", text)
        self.assertIn("debug", text)
        self.assertIn("proxy", text)

    def test_index_html_exists(self) -> None:
        html = PKG_ROOT / "index.html"
        self.assertTrue(html.exists(), f"index.html not found at {html}")
        text = html.read_text(encoding="utf-8")
        self.assertIn("viewport-fit=cover", text)

    def test_main_tsx_exists(self) -> None:
        main = SRC_DIR / "main.tsx"
        self.assertTrue(main.exists(), f"main.tsx not found at {main}")
        text = main.read_text(encoding="utf-8")
        self.assertIn("@inkstatute/ui-core/themes", text)

    def test_shim_debug_exists(self) -> None:
        shim = SRC_DIR / "shims" / "debug.ts"
        self.assertTrue(shim.exists(), f"debug shim not found at {shim}")

    def test_no_tauri_deps(self) -> None:
        """web app must not depend on any @tauri-apps/* package."""
        for ts_file in SRC_DIR.rglob("*.ts"):
            text = ts_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "@tauri-apps",
                text,
                f"@tauri-apps found in {ts_file}",
            )
        for tsx_file in SRC_DIR.rglob("*.tsx"):
            text = tsx_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "@tauri-apps",
                text,
                f"@tauri-apps found in {tsx_file}",
            )


class WebVitestTests(unittest.TestCase):
    """Run the vitest suite if bun is available; skip otherwise."""

    def test_vitest_suite(self) -> None:
        bun = shutil.which("bun")
        if bun is None:
            self.skipTest("bun not available — skipping vitest run")
        node_modules = PKG_ROOT / "node_modules" / ".bin" / "vitest"
        if not node_modules.exists():
            self.skipTest("vitest not installed — skipping TS test run")
        env = os.environ.copy()
        env["INKSTATUTE_GATE_RUNNING"] = "1"
        result = subprocess.run(
            [bun, "run", "test"],
            cwd=str(PKG_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            self.fail(
                f"vitest failed (exit {result.returncode})\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )


if __name__ == "__main__":
    unittest.main()
