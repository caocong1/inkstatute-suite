"""Security verification — no shell/code execution paths in Phase 101 tools.

Verifies that no Phase 101 tool has a `terminal` or `execute_code` permission
path, and that the security defaults from Phase 90 are upheld.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

from inkstatute_agent_core.tools.path_sandbox import PathSandbox


TOOLS_DIR = Path(__file__).parent.parent / "src" / "inkstatute_agent_core" / "tools"


class TestSecurityVerification(unittest.TestCase):
    """Security verification for Phase 101 tools."""

    def _read_all_tool_sources(self) -> dict[str, str]:
        """Read all .py files in the tools directory."""
        sources = {}
        for py_file in TOOLS_DIR.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            sources[py_file.name] = py_file.read_text(encoding="utf-8")
        return sources

    # ------------------------------------------------------------------
    # No shell execution
    # ------------------------------------------------------------------

    def test_no_subprocess_run_popen_call(self) -> None:
        """No tool source should contain subprocess.run/Popen/call (except mcp_client.py)."""
        sources = self._read_all_tool_sources()
        forbidden = ["subprocess.run", "subprocess.Popen", "subprocess.call"]
        for filename, content in sources.items():
            if filename == "mcp_client.py":
                continue  # mcp_client uses asyncio.create_subprocess_exec (controlled)
            for pattern in forbidden:
                self.assertNotIn(
                    pattern, content,
                    f"{filename} contains forbidden pattern: {pattern}",
                )

    def test_no_os_system_popen(self) -> None:
        """No tool source should contain os.system or os.popen."""
        sources = self._read_all_tool_sources()
        for filename, content in sources.items():
            self.assertNotIn("os.system(", content, f"{filename} contains os.system()")
            self.assertNotIn("os.popen(", content, f"{filename} contains os.popen()")

    def test_mcp_client_uses_controlled_subprocess(self) -> None:
        """mcp_client.py should use asyncio.create_subprocess_exec with a configured path."""
        mcp_source = (TOOLS_DIR / "mcp_client.py").read_text(encoding="utf-8")
        self.assertIn("asyncio.create_subprocess_exec", mcp_source)
        # The subprocess command should use the connector_path parameter, not user input
        self.assertIn("connector_path", mcp_source)

    # ------------------------------------------------------------------
    # No code execution
    # ------------------------------------------------------------------

    def test_no_exec_eval_with_user_input(self) -> None:
        """No tool source should contain exec() or eval() with user-supplied input."""
        sources = self._read_all_tool_sources()
        for filename, content in sources.items():
            # Check for exec( and eval( — these are dangerous with user input
            # Allow eval in safe contexts (e.g., literal_eval is fine)
            lines = content.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith("#"):
                    continue
                # Check for bare exec( or eval(
                if re.search(r'\bexec\s*\(', stripped) and "literal" not in stripped.lower():
                    self.fail(f"{filename}:{i+1} contains exec(): {stripped}")
                if re.search(r'\beval\s*\(', stripped) and "literal" not in stripped.lower():
                    self.fail(f"{filename}:{i+1} contains eval(): {stripped}")

    # ------------------------------------------------------------------
    # file_read is read-only
    # ------------------------------------------------------------------

    def test_file_read_is_read_only(self) -> None:
        """file_read.py should only open files in read mode."""
        file_read_source = (TOOLS_DIR / "file_read.py").read_text(encoding="utf-8")
        # Should not contain open(path, "w") or open(path, "a")
        self.assertNotIn('"w"', file_read_source)
        self.assertNotIn('"a"', file_read_source)
        self.assertNotIn("'w'", file_read_source)
        self.assertNotIn("'a'", file_read_source)

    # ------------------------------------------------------------------
    # document_generate only writes to output_path
    # ------------------------------------------------------------------

    def test_document_generate_writes_only_to_output_path(self) -> None:
        """document_generate.py should only write to the output_path argument."""
        doc_gen_source = (TOOLS_DIR / "document_generate.py").read_text(encoding="utf-8")
        # The save call should use the validated output path
        self.assertIn("builder.save(str(validated_output))", doc_gen_source)

    # ------------------------------------------------------------------
    # PathSandbox security
    # ------------------------------------------------------------------

    def test_path_sandbox_rejects_traversal(self) -> None:
        """PathSandbox should reject paths with .. components."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = PathSandbox([tmpdir])
            with self.assertRaises((ValueError, PermissionError)):
                sandbox.validate("../../etc/passwd")

    def test_path_sandbox_rejects_outside_roots(self) -> None:
        """PathSandbox should reject paths outside allowed roots."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = PathSandbox([tmpdir])
            with self.assertRaises(PermissionError):
                sandbox.validate("/etc/passwd")

    # ------------------------------------------------------------------
    # No terminal/execute_code permissions
    # ------------------------------------------------------------------

    def test_no_terminal_permission_requests(self) -> None:
        """No tool source should request terminal or execute_code permissions."""
        sources = self._read_all_tool_sources()
        forbidden_kinds = ["terminal", "execute_code"]
        for filename, content in sources.items():
            for kind in forbidden_kinds:
                self.assertNotIn(
                    f'"{kind}"', content,
                    f"{filename} references forbidden permission kind: {kind}",
                )
                self.assertNotIn(
                    f"'{kind}'", content,
                    f"{filename} references forbidden permission kind: {kind}",
                )

    # ------------------------------------------------------------------
    # No __import__ with user-supplied module names
    # ------------------------------------------------------------------

    def test_no_dangerous_import(self) -> None:
        """No tool should use __import__ with user-supplied module names."""
        sources = self._read_all_tool_sources()
        for filename, content in sources.items():
            # __import__ is dangerous with user input
            if "__import__" in content:
                # Check it's not using a variable as the module name
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "__import__" in line:
                        # If the argument is a variable (not a string literal), flag it
                        match = re.search(r'__import__\(([^)]+)\)', line)
                        if match:
                            arg = match.group(1).strip()
                            if not (arg.startswith('"') or arg.startswith("'")):
                                self.fail(
                                    f"{filename}:{i+1} uses __import__ with non-literal: {line.strip()}"
                                )


if __name__ == "__main__":
    unittest.main()
