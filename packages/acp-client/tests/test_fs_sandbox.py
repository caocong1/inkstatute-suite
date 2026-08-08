"""Unit tests for FSSandbox — five-layer path validation.

Each of the five attack vectors has a dedicated test, plus positive
read tests, case-insensitive extension handling, intermediate-symlink
defense-in-depth, and an exact size-boundary test.

All tests use ``tempfile.TemporaryDirectory()`` for isolation so no
real filesystem state leaks between tests.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_acp_client.fs_sandbox import (
    DEFAULT_MAX_FILE_SIZE,
    FSSandbox,
    FSSandboxConfig,
    FSSandboxError,
)


class FSSandboxEscapeTests(unittest.TestCase):
    """Tests covering all five sandbox escape vectors and positive cases."""

    def setUp(self) -> None:
        """Create an isolated temp directory as the allowed root."""
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sandbox = FSSandbox(
            FSSandboxConfig(allowed_root=self.root)
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- Attack vectors ---------------------------------------------------

    def test_path_traversal_rejected(self) -> None:
        """Test 1: ``..`` in path parts raises FSSandboxError(traversal)."""
        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.validate_path("../../etc/passwd")
        self.assertEqual(ctx.exception.reason, "traversal")

    def test_symlink_escape_rejected(self) -> None:
        """Test 2: a symlink inside root pointing outside is rejected."""
        # Create a target file outside the root.
        outside = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        )
        outside.write(b"secret")
        outside.close()
        self.addCleanup(os.unlink, outside.name)

        link_path = self.root / "escape.md"
        os.symlink(outside.name, link_path)

        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.validate_path(link_path)
        self.assertEqual(ctx.exception.reason, "symlink")
        self.assertIn("symlink", str(ctx.exception))

    def test_absolute_path_outside_root_rejected(self) -> None:
        """Test 3: an absolute path outside the root is rejected."""
        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.validate_path("/etc/passwd")
        self.assertEqual(ctx.exception.reason, "outside_root")

    def test_non_allowlist_extension_rejected(self) -> None:
        """Test 4: a non-allowlisted extension (``.exe``) is rejected."""
        target = self.root / "malware.exe"
        target.write_text("payload")
        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.validate_path(target)
        self.assertEqual(ctx.exception.reason, "bad_extension")

    def test_oversized_file_rejected(self) -> None:
        """Test 5: a file larger than max_file_size is rejected on read."""
        big = self.root / "big.txt"
        big.write_bytes(b"\x00" * (DEFAULT_MAX_FILE_SIZE + 1))
        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.read_text_file(big)
        self.assertEqual(ctx.exception.reason, "oversized")

    # -- Positive reads ---------------------------------------------------

    def test_valid_md_file_read(self) -> None:
        """Test 6: a ``.md`` file under root is read and content returned."""
        f = self.root / "hello.md"
        f.write_text("hello")
        self.assertEqual(self.sandbox.read_text_file(f), "hello")

    def test_valid_py_file_read(self) -> None:
        """Test 7: a ``.py`` file under root is read successfully."""
        f = self.root / "script.py"
        f.write_text("print('hi')")
        self.assertEqual(self.sandbox.read_text_file(f), "print('hi')")

    def test_valid_json_file_read(self) -> None:
        """Test 8: a ``.json`` file under root is read successfully."""
        f = self.root / "data.json"
        f.write_text('{"k": 1}')
        self.assertEqual(self.sandbox.read_text_file(f), '{"k": 1}')

    def test_extension_case_insensitive(self) -> None:
        """Test 9: an uppercase ``.MD`` extension is accepted."""
        f = self.root / "upper.MD"
        f.write_text("# Title")
        self.assertEqual(self.sandbox.read_text_file(f), "# Title")

    # -- Defense-in-depth -------------------------------------------------

    def test_intermediate_symlink_escape_rejected(self) -> None:
        """Test 10: a symlink on an intermediate component is rejected.

        Creates ``root/subdir_link`` → ``/etc`` and validates
        ``subdir_link/passwd``.  The symlink is on an intermediate
        directory, not the final file, verifying defense-in-depth at
        every path component.
        """
        link_path = self.root / "subdir_link"
        # Point at a directory that exists outside the root.
        os.symlink("/etc", link_path)

        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.validate_path(self.root / "subdir_link" / "passwd")
        self.assertEqual(ctx.exception.reason, "symlink")

    # -- Size boundary ----------------------------------------------------

    def test_size_boundary_exact_limit_accepted(self) -> None:
        """Test 11a: a file of exactly DEFAULT_MAX_FILE_SIZE bytes is OK."""
        f = self.root / "exact.txt"
        f.write_bytes(b"\x00" * DEFAULT_MAX_FILE_SIZE)
        # Should not raise.
        self.sandbox.read_text_file(f)

    def test_size_boundary_limit_plus_one_rejected(self) -> None:
        """Test 11b: a file of DEFAULT_MAX_FILE_SIZE + 1 bytes is rejected."""
        f = self.root / "over.txt"
        f.write_bytes(b"\x00" * (DEFAULT_MAX_FILE_SIZE + 1))
        with self.assertRaises(FSSandboxError) as ctx:
            self.sandbox.read_text_file(f)
        self.assertEqual(ctx.exception.reason, "oversized")


if __name__ == "__main__":
    unittest.main()
