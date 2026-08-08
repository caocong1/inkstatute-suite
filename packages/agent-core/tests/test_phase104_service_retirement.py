"""Phase 104-02: Verify legacy channels and services are retired.

Tests that:
- packages/channels/web_sse/ directory is deleted
- services/lawyer-web-chat/ directory is deleted
- services/hermes-contract-layer/ directory is deleted
- web-sse-channel, lawyer-web-chat, hermes-contract-layer gates are removed
- No Python files import from retired services
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestPhase104ServiceRetirement(unittest.TestCase):
    """Verify legacy channels and services are fully retired."""

    def test_no_web_sse_channel_directory_exists(self) -> None:
        """packages/channels/web_sse/ is deleted."""
        self.assertFalse(
            (REPO_ROOT / "packages" / "channels" / "web_sse").exists(),
            "packages/channels/web_sse/ should be deleted (retired in Phase 104-02)",
        )

    def test_no_lawyer_web_chat_directory_exists(self) -> None:
        """services/lawyer-web-chat/ is deleted."""
        self.assertFalse(
            (REPO_ROOT / "services" / "lawyer-web-chat").exists(),
            "services/lawyer-web-chat/ should be deleted (retired in Phase 104-02)",
        )

    def test_no_hermes_contract_layer_directory_exists(self) -> None:
        """services/hermes-contract-layer/ is deleted."""
        self.assertFalse(
            (REPO_ROOT / "services" / "hermes-contract-layer").exists(),
            "services/hermes-contract-layer/ should be deleted (retired in Phase 104-02)",
        )

    def test_web_sse_channel_gate_removed(self) -> None:
        """web-sse-channel gate is not in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"web-sse-channel"',
            gates_text,
            "web-sse-channel gate should be removed from run_v2_gates.py",
        )

    def test_lawyer_web_chat_gate_removed(self) -> None:
        """lawyer-web-chat gate is not in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"lawyer-web-chat"',
            gates_text,
            "lawyer-web-chat gate should be removed from run_v2_gates.py",
        )

    def test_hermes_contract_layer_gate_removed(self) -> None:
        """hermes-contract-layer gate is not in run_v2_gates.py."""
        gates_text = (REPO_ROOT / "scripts" / "run_v2_gates.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"hermes-contract-layer"',
            gates_text,
            "hermes-contract-layer gate should be removed from run_v2_gates.py",
        )

    def test_no_imports_from_retired_services(self) -> None:
        """No Python files outside the retired directories import from
        inkstatute_channels_web_sse, lawyer_web_chat, or hermes_contract_layer.

        This scans all .py files in the repo (excluding the deleted directories
        which no longer exist) for import statements referencing the retired
        module names.
        """
        retired_module_roots = frozenset({
            "inkstatute_channels_web_sse",
            "lawyer_web_chat",
            "hermes_contract_layer",
        })

        # Directories that are allowed to reference retired services
        # (e.g., the planning docs, or the test file itself).
        # We exclude .planning/ and __pycache__ directories.
        exclude_dirs = {
            ".planning",
            ".git",
            "node_modules",
        }

        violations: list[str] = []

        for py_file in sorted(REPO_ROOT.rglob("*.py")):
            # Skip files in excluded directories
            relative = py_file.relative_to(REPO_ROOT)
            if any(part in exclude_dirs for part in relative.parts):
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                module_names: list[str] = []
                if isinstance(node, ast.Import):
                    module_names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module_names.append(node.module)

                for module_name in module_names:
                    root = module_name.split(".", 1)[0]
                    if root in retired_module_roots:
                        violations.append(
                            f"{relative}:{getattr(node, 'lineno', '?')} "
                            f"imports {module_name}"
                        )

        self.assertEqual(
            violations,
            [],
            f"Found imports from retired services:\n{chr(10).join(violations)}",
        )

    def test_gateway_sse_is_self_contained(self) -> None:
        """Gateway SSE encoding is self-contained (no web_sse dependency)."""
        sse_path = REPO_ROOT / "services" / "gateway" / "src" / "gateway" / "sse.py"
        self.assertTrue(sse_path.exists(), "gateway/sse.py should exist")
        content = sse_path.read_text(encoding="utf-8")
        self.assertNotIn(
            "inkstatute_channels_web_sse",
            content,
            "gateway/sse.py should not import from inkstatute_channels_web_sse",
        )
        self.assertIn(
            "def encode_sse_event",
            content,
            "gateway/sse.py should have an inlined encode_sse_event function",
        )

    def test_feature_flags_kept_but_deprecated(self) -> None:
        """web_sse_channel_enabled and lawyer_web_chat_enabled flags still exist
        but are marked deprecated."""
        flags_path = REPO_ROOT / "packages" / "platform-runtime" / "src" / "platform_runtime" / "feature_flags.py"
        content = flags_path.read_text(encoding="utf-8")
        self.assertIn("web_sse_channel_enabled", content)
        self.assertIn("lawyer_web_chat_enabled", content)
        self.assertIn("Deprecated", content)


if __name__ == "__main__":
    unittest.main()
