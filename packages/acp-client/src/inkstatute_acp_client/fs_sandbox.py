"""FSSandbox — five-layer path validation for safe file reading.

A security-critical primitive that validates file paths before any
``fs/read_text_file`` request is fulfilled.  Five attack vectors are
blocked, in order:

1. **Path traversal** — any path containing a ``..`` component is
   rejected before canonicalization, preventing ``../../etc/passwd``
   style escapes.
2. **Symlink rejection** — every path component is checked with
   :func:`os.path.islink`.  A symlink at *any* level of the path
   (intermediate directory or final file) is rejected.  This is
   defense-in-depth: ``realpath`` is deliberately NOT used
   because it follows symlinks and would silently resolve an escape
   back inside the root, defeating the protection.
3. **Resolve normalization** — :meth:`Path.resolve` canonicalizes the
   path so that ``root/../etc`` style inputs are compared on their
   true filesystem location.
4. **Prefix-check root constraint** — the resolved path must be the
   allowed root itself or a direct descendant of it.
5. **Extension allowlist** — only text-based extensions
   (``.txt``, ``.md``, ``.json``, …) are permitted; binary formats
   are deferred to a future phase.

A sixth guard — **size cap** — is applied at read time by
:meth:`FSSandbox.read_text_file`.

This is a **read-only** security primitive — it does not grant write
access, does not execute shell commands, and does not follow symlinks
outside the allowed root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Text-only extension allowlist for v1.  Binary formats (``.docx``,
#: ``.pdf``) are deferred to a future phase.
DEFAULT_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".html",
        ".xml",
        ".log",
        ".py",
        ".js",
        ".ts",
    }
)

#: Default maximum file size: 1 MB (1_048_576 bytes).
DEFAULT_MAX_FILE_SIZE: int = 1_048_576


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FSSandboxError(Exception):
    """Raised when a path or file violates the sandbox constraints.

    Attributes:
        message: Human-readable description of the violation.
        reason: Short machine-readable code identifying the violated
            layer (``"traversal"``, ``"symlink"``, ``"outside_root"``,
            ``"bad_extension"``, ``"oversized"``).
    """

    def __init__(self, message: str, reason: str = "") -> None:
        self.message = message
        self.reason = reason
        super().__init__(message)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FSSandboxConfig:
    """Configuration for :class:`FSSandbox`.

    Attributes:
        allowed_root: The single root directory inside which all file
            reads must remain.
        allowed_extensions: Frozenset of lowercased extensions
            (including the leading dot) that are permitted.
        max_file_size: Maximum file size in bytes.  Files at or below
            this size are accepted; files exceeding it are rejected.
    """

    allowed_root: Path
    allowed_extensions: frozenset[str] = DEFAULT_ALLOWED_EXTENSIONS
    max_file_size: int = DEFAULT_MAX_FILE_SIZE


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


class FSSandbox:
    """Validate file paths against a single allowed root with five layers.

    The sandbox is constructed once with a :class:`FSSandboxConfig` and
    the allowed root is resolved (canonicalized) at construction time.
    Each call to :meth:`validate_path` re-runs all five checks.
    """

    def __init__(self, config: FSSandboxConfig) -> None:
        """Initialize the sandbox, resolving the allowed root once.

        Args:
            config: The sandbox configuration.
        """
        self.config = config
        # Resolve the root once so prefix-checks compare canonical paths.
        self._root: Path = Path(config.allowed_root).resolve()

    # -- public API -------------------------------------------------------

    def validate_path(self, path: str | Path) -> Path:
        """Run all five validation layers and return the resolved path.

        Layers (in order):

        a. Reject ``..`` components (path traversal).
        b. Reject symlinks at *any* path component (defense-in-depth).
        c. Resolve (canonicalize) the path.
        d. Prefix-check the resolved path against the allowed root.
        e. Extension allowlist (case-insensitive).

        Args:
            path: The file path to validate (relative or absolute).

        Returns:
            The resolved (canonical) ``Path`` if validation passes.

        Raises:
            FSSandboxError: If any layer rejects the path.  The
                ``reason`` attribute identifies the violating layer.
        """
        p = Path(path)

        # a. Reject path traversal — check parts for ".." components.
        if ".." in p.parts:
            raise FSSandboxError(
                f"path traversal not allowed: {path}",
                reason="traversal",
            )

        # b. Symlink rejection — walk every component from the anchor
        #    upward, checking os.path.islink at each step.  This catches
        #    both intermediate-directory symlinks and final-file
        #    symlinks.  ``realpath`` is deliberately NOT used: it
        #    follows symlinks and would hide an escape.
        abs_path = p.absolute()
        anchor = abs_path.anchor
        current = Path(anchor)
        for part in abs_path.parts[1:]:  # skip the anchor ("/" or "C:\\")
            current = current / part
            if os.path.islink(current):
                raise FSSandboxError(
                    f"symlink rejected: {current}",
                    reason="symlink",
                )

        # c. Resolve normalization.
        resolved = p.resolve()

        # d. Prefix-check root constraint — resolved must be the root
        #    itself or a descendant of it.
        if self._root not in resolved.parents and resolved != self._root:
            raise FSSandboxError(
                f"path outside allowed root: {resolved}",
                reason="outside_root",
            )

        # e. Extension allowlist (case-insensitive).
        suffix = resolved.suffix.lower()
        if suffix not in self.config.allowed_extensions:
            raise FSSandboxError(
                f"extension not allowed: {suffix}",
                reason="bad_extension",
            )

        return resolved

    def read_text_file(self, path: str | Path) -> str:
        """Validate ``path`` then read and return its text content.

        Runs :meth:`validate_path` first, then enforces the size cap
        before reading.  The file is read as UTF-8.

        Args:
            path: The file path to read.

        Returns:
            The file contents as a ``str``.

        Raises:
            FSSandboxError: If path validation fails or the file
                exceeds ``config.max_file_size``.
        """
        resolved = self.validate_path(path)

        size = resolved.stat().st_size
        if size > self.config.max_file_size:
            raise FSSandboxError(
                f"file too large: {size} > {self.config.max_file_size}",
                reason="oversized",
            )

        return resolved.read_text(encoding="utf-8")


__all__ = [
    "DEFAULT_ALLOWED_EXTENSIONS",
    "DEFAULT_MAX_FILE_SIZE",
    "FSSandbox",
    "FSSandboxConfig",
    "FSSandboxError",
]
