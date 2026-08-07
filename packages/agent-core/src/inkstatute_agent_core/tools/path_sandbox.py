"""PathSandbox — path sandboxing for safe file reading.

A Python port of the Rust ``PathSandbox`` from
``lawyer-desktop/src-tauri/src/security/path_sandbox.rs``.

The sandbox validates file paths against an allowlist of root directories:

1. **Reject ``..`` components** — path traversal prevention.  Any path
   containing a ``ParentDir`` component (``".."``) is rejected before
   canonicalization, preventing symlink-based escapes.
2. **Canonicalize** — resolve symlinks via ``pathlib.Path.resolve()``.
3. **Allowlist check** — the canonical path must start with at least one
   allowed root (also canonicalized).  If not, ``PermissionError`` is raised.

This is a **read-only** security primitive — it does not grant write
access, does not execute shell commands, and does not follow symlinks
outside the allowed roots.
"""

from __future__ import annotations

from pathlib import Path


class PathSandbox:
    """Validate file paths against an allowlist of canonicalized root directories.

    Attributes:
        _roots: List of canonicalized (resolved) root ``Path`` objects.
    """

    def __init__(self, allowed_roots: list[str | Path]) -> None:
        """Initialize the sandbox with a list of allowed root paths.

        Each root is canonicalized (resolved) at construction time so
        that symlink resolution happens once, not on every ``validate()``
        call.

        Args:
            allowed_roots: List of directory paths that are allowed
                for file access.  Each is resolved to its canonical
                form via ``Path.resolve()``.
        """
        self._roots: list[Path] = [Path(root).resolve() for root in allowed_roots]

    def validate(self, path: str | Path) -> Path:
        """Validate a path and return its canonical form.

        Steps:
        1. Reject paths containing ``..`` components (path traversal).
        2. Canonicalize the path via ``Path.resolve()`` (resolves symlinks).
        3. Check the canonical path starts with at least one allowed root.
        4. If not within any root, raise ``PermissionError``.

        Args:
            path: The file path to validate (relative or absolute).

        Returns:
            The canonical (resolved) ``Path`` if validation passes.

        Raises:
            ValueError: If the path contains ``..`` components.
            PermissionError: If the canonical path is outside all
                allowed roots.
        """
        p = Path(path)

        # 1. Reject path traversal — check parts for ".." components
        if ".." in p.parts:
            raise ValueError(f"path traversal not allowed: {path}")

        # 2. Canonicalize (resolve symlinks)
        canonical = p.resolve()

        # 3. Check canonical path starts with at least one allowed root
        for root in self._roots:
            if root in canonical.parents or canonical == root:
                return canonical

        # 4. Not within any root
        raise PermissionError("access denied: outside allowed directories")

    def is_allowed(self, path: str | Path) -> bool:
        """Check if a path is allowed without raising an exception.

        Args:
            path: The file path to check.

        Returns:
            ``True`` if the path is valid and within an allowed root,
            ``False`` otherwise (including traversal attempts and
            paths outside roots).
        """
        try:
            self.validate(path)
            return True
        except (ValueError, PermissionError):
            return False


__all__ = ["PathSandbox"]
