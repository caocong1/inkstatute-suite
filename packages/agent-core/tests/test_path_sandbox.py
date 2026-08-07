"""Tests for PathSandbox — path sandboxing for file reading security.

Covers: file inside root allowed, file outside roots rejected,
``..`` traversal rejected, symlink resolution, nested subdirectory
allowed, absolute path within root, relative path resolution.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_agent_core.tools.path_sandbox import PathSandbox


class TestPathSandbox(unittest.TestCase):
    """Tests for PathSandbox validation logic."""

    def setUp(self) -> None:
        """Create a temporary directory tree for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

        # Create sample files
        (self.root / "file.txt").write_text("hello", encoding="utf-8")
        subdir = self.root / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        # Create a second root for multi-root tests
        self.root2 = Path(self.tmpdir.name) / "uploads"
        self.root2.mkdir()
        (self.root2 / "upload.txt").write_text("upload", encoding="utf-8")

        # Create a directory outside all roots
        self.outside = Path(self.tmpdir.name) / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("secret", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Basic validation
    # ------------------------------------------------------------------

    def test_file_inside_root_allowed(self) -> None:
        """A file directly inside an allowed root should be validated."""
        sandbox = PathSandbox([self.root])
        result = sandbox.validate(self.root / "file.txt")
        self.assertEqual(result, (self.root / "file.txt").resolve())

    def test_nested_subdirectory_allowed(self) -> None:
        """A file in a nested subdirectory of an allowed root should pass."""
        sandbox = PathSandbox([self.root])
        result = sandbox.validate(self.root / "subdir" / "nested.txt")
        self.assertEqual(result, (self.root / "subdir" / "nested.txt").resolve())

    def test_absolute_path_within_root(self) -> None:
        """An absolute path within an allowed root should be validated."""
        sandbox = PathSandbox([self.root])
        abs_path = str((self.root / "file.txt").resolve())
        result = sandbox.validate(abs_path)
        self.assertEqual(result, Path(abs_path))

    def test_relative_path_resolution(self) -> None:
        """A relative path should be resolved and validated against roots."""
        sandbox = PathSandbox([self.root])
        # Change to the root directory and use a relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(self.root)
            result = sandbox.validate("file.txt")
            self.assertEqual(result, (self.root / "file.txt").resolve())
        finally:
            os.chdir(original_cwd)

    # ------------------------------------------------------------------
    # Rejection cases
    # ------------------------------------------------------------------

    def test_file_outside_roots_rejected(self) -> None:
        """A file outside all allowed roots should raise PermissionError."""
        sandbox = PathSandbox([self.root])
        with self.assertRaises(PermissionError):
            sandbox.validate(self.outside / "secret.txt")

    def test_parent_dir_traversal_rejected(self) -> None:
        """Paths containing ``..`` should raise ValueError."""
        sandbox = PathSandbox([self.root])
        with self.assertRaises(ValueError):
            sandbox.validate(self.root / ".." / "outside" / "secret.txt")

    def test_parent_dir_traversal_rejected_with_is_allowed(self) -> None:
        """is_allowed should return False for ``..`` traversal paths."""
        sandbox = PathSandbox([self.root])
        self.assertFalse(sandbox.is_allowed(self.root / ".." / "outside" / "secret.txt"))

    # ------------------------------------------------------------------
    # is_allowed
    # ------------------------------------------------------------------

    def test_is_allowed_true_for_valid_path(self) -> None:
        """is_allowed should return True for a path within a root."""
        sandbox = PathSandbox([self.root])
        self.assertTrue(sandbox.is_allowed(self.root / "file.txt"))

    def test_is_allowed_false_for_outside_path(self) -> None:
        """is_allowed should return False for a path outside all roots."""
        sandbox = PathSandbox([self.root])
        self.assertFalse(sandbox.is_allowed(self.outside / "secret.txt"))

    def test_is_allowed_no_exception(self) -> None:
        """is_allowed should never raise, even for invalid paths."""
        sandbox = PathSandbox([self.root])
        # Should not raise
        sandbox.is_allowed("/nonexistent/path")
        sandbox.is_allowed(self.root / ".." / "escape")

    # ------------------------------------------------------------------
    # Multiple roots
    # ------------------------------------------------------------------

    def test_multiple_roots_both_allowed(self) -> None:
        """Files in either of two allowed roots should be validated."""
        sandbox = PathSandbox([self.root, self.root2])
        self.assertEqual(
            sandbox.validate(self.root / "file.txt"),
            (self.root / "file.txt").resolve(),
        )
        self.assertEqual(
            sandbox.validate(self.root2 / "upload.txt"),
            (self.root2 / "upload.txt").resolve(),
        )

    def test_multiple_roots_outside_still_rejected(self) -> None:
        """A file outside both roots should still be rejected."""
        sandbox = PathSandbox([self.root, self.root2])
        with self.assertRaises(PermissionError):
            sandbox.validate(self.outside / "secret.txt")

    # ------------------------------------------------------------------
    # Symlink resolution
    # ------------------------------------------------------------------

    def test_symlink_resolution_within_root(self) -> None:
        """A symlink pointing within an allowed root should be validated."""
        if os.name == "nt":
            self.skipTest("symlink test skipped on Windows")
        link = self.root / "link_to_file.txt"
        target = self.root / "file.txt"
        os.symlink(target, link)
        sandbox = PathSandbox([self.root])
        result = sandbox.validate(link)
        # The canonical path should resolve to the target
        self.assertEqual(result, target.resolve())

    def test_symlink_escape_rejected(self) -> None:
        """A symlink pointing outside the root should be rejected."""
        if os.name == "nt":
            self.skipTest("symlink test skipped on Windows")
        link = self.root / "escape_link.txt"
        target = self.outside / "secret.txt"
        os.symlink(target, link)
        sandbox = PathSandbox([self.root])
        # The symlink resolves to the outside path, which is not within root
        with self.assertRaises(PermissionError):
            sandbox.validate(link)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_root_itself_is_allowed(self) -> None:
        """The root directory itself should be within the allowed roots."""
        sandbox = PathSandbox([self.root])
        result = sandbox.validate(self.root)
        self.assertEqual(result, self.root.resolve())

    def test_canonicalized_roots(self) -> None:
        """Roots should be canonicalized at construction time."""
        # Pass a non-canonical path (with redundant components)
        non_canonical = self.root / "." / "."
        sandbox = PathSandbox([non_canonical])
        # Should still validate files within root
        result = sandbox.validate(self.root / "file.txt")
        self.assertEqual(result, (self.root / "file.txt").resolve())

    def test_nonexistent_file_within_root_allowed(self) -> None:
        """A nonexistent file within a root should still pass validation
        (the path is valid; the file doesn't need to exist for path checking)."""
        sandbox = PathSandbox([self.root])
        # Path.resolve() on a nonexistent path still works in Python
        # (it resolves the path components without requiring existence)
        result = sandbox.validate(self.root / "nonexistent.txt")
        self.assertEqual(result, (self.root / "nonexistent.txt").resolve())

    def test_empty_roots_rejects_everything(self) -> None:
        """A sandbox with no roots should reject all paths."""
        sandbox = PathSandbox([])
        with self.assertRaises(PermissionError):
            sandbox.validate(self.root / "file.txt")

    def test_string_path_accepted(self) -> None:
        """String paths (not just Path objects) should be accepted."""
        sandbox = PathSandbox([str(self.root)])
        result = sandbox.validate(str(self.root / "file.txt"))
        self.assertEqual(result, (self.root / "file.txt").resolve())


if __name__ == "__main__":
    unittest.main()
