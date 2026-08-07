"""Tests for the file_read tool — read-only, path-sandboxed file reading.

Covers: valid text file read, truncation at max_chars, binary file
rejection, path traversal rejection, outside-root rejection, nested
subdirectory access, missing file error, UTF-8 and latin-1 encoding.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_agent_core.tools.file_read import (
    DEFAULT_MAX_CHARS,
    FILE_READ_TOOL_DEFINITION,
    create_file_read_tool,
)
from inkstatute_agent_core.tools.path_sandbox import PathSandbox
from inkstatute_agent_core.turn_loop import ToolResult


class TestFileReadTool(unittest.TestCase):
    """Tests for the file_read tool handler."""

    def setUp(self) -> None:
        """Create a temporary directory with test files."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

        # Create sample text files
        (self.root / "sample.txt").write_text(
            "Hello, this is a sample text file.\nLine 2: 欢迎来到墨律.\n",
            encoding="utf-8",
        )

        # Nested subdirectory
        subdir = self.root / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text(
            "This is a nested file.\n",
            encoding="utf-8",
        )

        # Latin-1 encoded file (invalid UTF-8)
        # Use bytes that are valid latin-1 but invalid UTF-8
        latin1_content = b"Caf\xe9 r\xe9sum\xe9 latin-1 encoded\n\xe9\xe8\xea"
        (self.root / "latin1.txt").write_bytes(latin1_content)

        # Binary file (contains null bytes)
        (self.root / "binary.dat").write_bytes(b"BIN\x00\x01\x02\x00NUL")

        # Large file for truncation test
        large_text = "A" * (DEFAULT_MAX_CHARS + 100)
        (self.root / "large.txt").write_text(large_text, encoding="utf-8")

        # Directory outside the root
        self.outside = Path(self.tmpdir.name) / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("secret", encoding="utf-8")

        self.sandbox = PathSandbox([self.root])
        self.handler = create_file_read_tool(self.sandbox)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _run(self, coro):
        """Run an async coroutine in a fresh event loop."""
        return asyncio.new_event_loop().run_until_complete(coro)

    # ------------------------------------------------------------------
    # Valid reads
    # ------------------------------------------------------------------

    def test_valid_text_file_read(self) -> None:
        """A valid text file within the root should be read successfully."""
        result = self._run(self.handler({"path": str(self.root / "sample.txt")}))
        self.assertIsNone(result.error)
        self.assertIn("Hello, this is a sample text file", result.content)
        self.assertIn("欢迎来到墨律", result.content)

    def test_nested_subdirectory_access(self) -> None:
        """A file in a nested subdirectory should be readable."""
        result = self._run(
            self.handler({"path": str(self.root / "subdir" / "nested.txt")})
        )
        self.assertIsNone(result.error)
        self.assertIn("This is a nested file", result.content)

    def test_utf8_encoding(self) -> None:
        """UTF-8 encoded files with Chinese characters should be read correctly."""
        result = self._run(self.handler({"path": str(self.root / "sample.txt")}))
        self.assertIsNone(result.error)
        self.assertIn("欢迎来到墨律", result.content)

    def test_latin1_fallback(self) -> None:
        """Files with invalid UTF-8 should fall back to latin-1 encoding."""
        result = self._run(self.handler({"path": str(self.root / "latin1.txt")}))
        self.assertIsNone(result.error)
        # The content should be readable (latin-1 never fails)
        self.assertIn("Caf", result.content)

    # ------------------------------------------------------------------
    # Truncation
    # ------------------------------------------------------------------

    def test_truncation_at_max_chars(self) -> None:
        """Files exceeding max_chars should be truncated with indicator."""
        result = self._run(
            self.handler({"path": str(self.root / "large.txt"), "max_chars": 100})
        )
        self.assertIsNone(result.error)
        self.assertTrue(result.content.endswith("...[truncated]"))
        self.assertEqual(len(result.content), 100 + len("...[truncated]"))

    def test_default_max_chars_not_exceeded(self) -> None:
        """Files under the default max_chars should not be truncated."""
        result = self._run(self.handler({"path": str(self.root / "sample.txt")}))
        self.assertIsNone(result.error)
        self.assertNotIn("[truncated]", result.content)

    def test_large_file_default_truncation(self) -> None:
        """A file larger than DEFAULT_MAX_CHARS should be truncated by default."""
        result = self._run(self.handler({"path": str(self.root / "large.txt")}))
        self.assertIsNone(result.error)
        self.assertTrue(result.content.endswith("...[truncated]"))

    # ------------------------------------------------------------------
    # Binary file rejection
    # ------------------------------------------------------------------

    def test_binary_file_rejected(self) -> None:
        """Binary files (null bytes) should be rejected with an error."""
        result = self._run(self.handler({"path": str(self.root / "binary.dat")}))
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "binary_file")
        self.assertIn("binary", result.content.lower())

    # ------------------------------------------------------------------
    # Path traversal rejection
    # ------------------------------------------------------------------

    def test_path_traversal_rejected(self) -> None:
        """Paths with ``..`` should be rejected via PathSandbox."""
        result = self._run(
            self.handler(
                {"path": str(self.root / ".." / "outside" / "secret.txt")}
            )
        )
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "path_traversal")

    # ------------------------------------------------------------------
    # Outside-root rejection
    # ------------------------------------------------------------------

    def test_outside_root_rejected(self) -> None:
        """Files outside allowed roots should be rejected."""
        result = self._run(
            self.handler({"path": str(self.outside / "secret.txt")})
        )
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "access_denied")

    # ------------------------------------------------------------------
    # Missing file
    # ------------------------------------------------------------------

    def test_missing_file_error(self) -> None:
        """A nonexistent file should return an error ToolResult."""
        result = self._run(
            self.handler({"path": str(self.root / "nonexistent.txt")})
        )
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "file_not_found")

    # ------------------------------------------------------------------
    # Missing path argument
    # ------------------------------------------------------------------

    def test_missing_path_argument(self) -> None:
        """Missing path argument should return an error."""
        result = self._run(self.handler({}))
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "missing_path")

    # ------------------------------------------------------------------
    # Tool definition
    # ------------------------------------------------------------------

    def test_tool_definition_format(self) -> None:
        """FILE_READ_TOOL_DEFINITION should be valid OpenAI function-calling format."""
        self.assertEqual(FILE_READ_TOOL_DEFINITION["type"], "function")
        func = FILE_READ_TOOL_DEFINITION["function"]
        self.assertEqual(func["name"], "read_file")
        self.assertIn("description", func)
        self.assertIn("parameters", func)
        params = func["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("path", params["properties"])
        self.assertIn("max_chars", params["properties"])
        self.assertIn("path", params["required"])

    # ------------------------------------------------------------------
    # Read-only verification
    # ------------------------------------------------------------------

    def test_no_write_access(self) -> None:
        """Reading a file should not modify it."""
        filepath = self.root / "sample.txt"
        original = filepath.read_text(encoding="utf-8")
        self._run(self.handler({"path": str(filepath)}))
        after = filepath.read_text(encoding="utf-8")
        self.assertEqual(original, after)

    # ------------------------------------------------------------------
    # Factory returns callable
    # ------------------------------------------------------------------

    def test_factory_returns_callable(self) -> None:
        """create_file_read_tool should return a callable."""
        handler = create_file_read_tool(self.sandbox)
        self.assertTrue(callable(handler))


if __name__ == "__main__":
    unittest.main()
