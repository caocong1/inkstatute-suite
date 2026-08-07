"""Gate tests for @inkstatute/desktop package structure.

These tests run as part of the V2 gate system (python -m unittest discover).
They verify the desktop app scaffold exists and that the TypeScript source
files contain the expected structure. When bun/vitest is available, the
actual TS test suite is also executed via subprocess.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PKG_ROOT / "src"


class DesktopScaffoldTests(unittest.TestCase):
    """Assert the desktop app scaffold exists with required files."""

    def test_package_json_exists(self) -> None:
        pkg = PKG_ROOT / "package.json"
        self.assertTrue(pkg.exists(), f"package.json not found at {pkg}")
        text = pkg.read_text(encoding="utf-8")
        self.assertIn("@inkstatute/desktop", text)
        self.assertIn('"private": true', text)
        self.assertIn("@inkstatute/ui-core", text)
        self.assertIn("@inkstatute/platform-sdk-ts", text)
        self.assertIn("@tauri-apps/api", text)
        self.assertIn("@tauri-apps/plugin-dialog", text)
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
        self.assertIn("1420", text)

    def test_index_html_exists(self) -> None:
        html = PKG_ROOT / "index.html"
        self.assertTrue(html.exists(), f"index.html not found at {html}")

    def test_main_tsx_exists(self) -> None:
        main = SRC_DIR / "main.tsx"
        self.assertTrue(main.exists(), f"main.tsx not found at {main}")
        text = main.read_text(encoding="utf-8")
        self.assertIn("@inkstatute/ui-core/themes", text)

    def test_shim_debug_exists(self) -> None:
        shim = SRC_DIR / "shims" / "debug.ts"
        self.assertTrue(shim.exists(), f"debug shim not found at {shim}")

    def test_tauri_src_dir_exists(self) -> None:
        """Tauri shell directory must exist."""
        tauri_dir = PKG_ROOT / "src-tauri"
        self.assertTrue(tauri_dir.exists(), f"src-tauri not found at {tauri_dir}")

    def test_no_router_dep(self) -> None:
        """Desktop app must not depend on @solidjs/router (signal-based nav)."""
        pkg = PKG_ROOT / "package.json"
        text = pkg.read_text(encoding="utf-8")
        self.assertNotIn("@solidjs/router", text)

    def test_adapters_exist(self) -> None:
        """All 6 desktop adapter files must exist."""
        adapters_dir = SRC_DIR / "adapters"
        expected = [
            "desktopFileAdapter.ts",
            "desktopDropAdapter.ts",
            "desktopAppInfoAdapter.ts",
            "desktopWorkspaceAdapter.ts",
            "desktopDocumentParser.ts",
            "desktopWindowAdapter.ts",
            "desktopAdapters.ts",
        ]
        for name in expected:
            f = adapters_dir / name
            self.assertTrue(f.exists(), f"adapter not found: {f}")

    def test_window_adapter_defined(self) -> None:
        """desktopAdapters.ts must define `window` (KEY difference from web)."""
        barrel = SRC_DIR / "adapters" / "desktopAdapters.ts"
        text = barrel.read_text(encoding="utf-8")
        self.assertIn("window", text)
        self.assertIn("desktopWindowAdapter", text)

    def test_gateway_config_exists(self) -> None:
        """Gateway config must exist and use PlatformApiClient."""
        gw = SRC_DIR / "config" / "gateway.ts"
        self.assertTrue(gw.exists(), f"gateway config not found at {gw}")
        text = gw.read_text(encoding="utf-8")
        self.assertIn("PlatformApiClient", text)
        self.assertIn("127.0.0.1:8000", text)

    def test_auth_context_exists(self) -> None:
        """AuthContext must exist with login/logout."""
        auth = SRC_DIR / "contexts" / "AuthContext.tsx"
        self.assertTrue(auth.exists(), f"AuthContext not found at {auth}")
        text = auth.read_text(encoding="utf-8")
        self.assertIn("AuthProvider", text)
        self.assertIn("useAuth", text)
        self.assertIn("login", text)
        self.assertIn("logout", text)

    def test_conversation_context_exists(self) -> None:
        """ConversationContext must exist with createConversation."""
        conv = SRC_DIR / "contexts" / "ConversationContext.tsx"
        self.assertTrue(conv.exists(), f"ConversationContext not found at {conv}")
        text = conv.read_text(encoding="utf-8")
        self.assertIn("ConversationProvider", text)
        self.assertIn("useConversations", text)
        self.assertIn("createConversation", text)

    def test_app_tsx_exists(self) -> None:
        """App.tsx must exist with signal-based screen switching (no router)."""
        app = SRC_DIR / "App.tsx"
        self.assertTrue(app.exists(), f"App.tsx not found at {app}")
        text = app.read_text(encoding="utf-8")
        self.assertIn("AuthProvider", text)
        self.assertIn("AdapterContext", text)
        self.assertIn("ConversationProvider", text)
        self.assertIn("ConnectionProvider", text)
        self.assertIn("TitleBar", text)
        self.assertIn("ConversationDrawer", text)
        self.assertIn("OfflineBanner", text)
        self.assertIn("createSignal", text)
        self.assertNotIn("@solidjs/router", text)

    def test_pages_exist(self) -> None:
        """HomePage and WorkspacePage must exist."""
        home = SRC_DIR / "pages" / "HomePage.tsx"
        ws = SRC_DIR / "pages" / "WorkspacePage.tsx"
        self.assertTrue(home.exists(), f"HomePage not found at {home}")
        self.assertTrue(ws.exists(), f"WorkspacePage not found at {ws}")

    def test_tauri_shell_files(self) -> None:
        """Tauri shell must have required files."""
        tauri = PKG_ROOT / "src-tauri"
        self.assertTrue((tauri / "tauri.conf.json").exists())
        self.assertTrue((tauri / "Cargo.toml").exists())
        self.assertTrue((tauri / "src" / "lib.rs").exists())
        self.assertTrue((tauri / "src" / "main.rs").exists())
        self.assertTrue((tauri / "src" / "commands" / "files.rs").exists())
        self.assertTrue((tauri / "src" / "commands" / "offline_cache.rs").exists())
        self.assertTrue((tauri / "src" / "security" / "path_sandbox.rs").exists())
        self.assertTrue((tauri / "capabilities" / "default.json").exists())

    def test_offline_cache_files_exist(self) -> None:
        """Offline cache TypeScript and migration files must exist."""
        self.assertTrue((SRC_DIR / "contexts" / "ConnectionContext.tsx").exists())
        self.assertTrue((SRC_DIR / "components" / "OfflineBanner.tsx").exists())
        self.assertTrue((SRC_DIR / "lib" / "offlineCache.ts").exists())
        migration = PKG_ROOT / "src-tauri" / "migrations" / "002_offline_cache.sql"
        self.assertTrue(migration.exists(), f"migration not found: {migration}")

    def test_tauri_no_agent_logic(self) -> None:
        """Tauri commands must not contain agent logic (send_message, etc.)."""
        lib_rs = (PKG_ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
        for forbidden in [
            "send_message",
            "create_conversation",
            "classify_agent_mode",
            "get_active_provider",
            "reload_skills",
            "get_mcp_health",
        ]:
            self.assertNotIn(
                forbidden,
                lib_rs,
                f"agent logic '{forbidden}' found in lib.rs",
            )

    def test_tauri_excluded_deps(self) -> None:
        """Cargo.toml must not contain excluded dependencies."""
        cargo = (PKG_ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        for forbidden in [
            "tauri-plugin-mcp-bridge",
            "reqwest",
            "aes-gcm",
            "pdf-extract",
            "docx-rs",
        ]:
            self.assertNotIn(
                forbidden,
                cargo,
                f"excluded dependency '{forbidden}' found in Cargo.toml",
            )

    def test_tauri_command_count(self) -> None:
        """lib.rs must register all desktop-only commands (7 file + 9 offline cache)."""
        lib_rs = (PKG_ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
        file_commands = [
            "read_file_content",
            "list_directory",
            "prepare_attachment",
            "classify_dropped_paths",
            "grant_path_access",
            "get_allowed_file_dirs",
            "set_allowed_file_dirs",
        ]
        cache_commands = [
            "cache_session",
            "cache_run",
            "cache_event",
            "cache_artifact",
            "get_cached_sessions",
            "get_cached_runs",
            "get_cached_events",
            "get_cached_artifact",
            "get_cached_artifacts_by_session",
        ]
        for cmd in file_commands:
            self.assertIn(
                f"commands::files::{cmd}",
                lib_rs,
                f"file command '{cmd}' not registered in lib.rs",
            )
        for cmd in cache_commands:
            self.assertIn(
                f"commands::offline_cache::{cmd}",
                lib_rs,
                f"cache command '{cmd}' not registered in lib.rs",
            )


class DesktopVitestTests(unittest.TestCase):
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
        try:
            result = subprocess.run(
                [bun, "run", "test"],
                cwd=str(PKG_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                self.fail(
                    f"vitest failed (exit {result.returncode})\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            if "FAIL" in stdout or "×" in stdout or "failed" in stdout.lower():
                self.fail(
                    f"vitest had failures before timeout\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
            if "✓" in stdout or "passed" in stdout.lower() or "·" in stdout:
                pass
            else:
                self.fail(
                    f"vitest timed out with no test output\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )


if __name__ == "__main__":
    unittest.main()
