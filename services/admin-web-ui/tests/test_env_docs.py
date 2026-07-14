"""Tests for .env.example documentation of Phase 85 auth env vars (POLISH-05).

Verifies that ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_TTL_SECONDS, and
ADMIN_WEB_UI_SECURE_COOKIE are documented with inline comments and a
section header.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"

_AUTH_VARS = (
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "SESSION_TTL_SECONDS",
    "ADMIN_WEB_UI_SECURE_COOKIE",
)


class TestEnvDocs(unittest.TestCase):
    """Validate .env.example documents Phase 85 auth env vars."""

    def setUp(self) -> None:
        self.assertTrue(_ENV_EXAMPLE.is_file(), f"Missing file: {_ENV_EXAMPLE}")
        self.content = _ENV_EXAMPLE.read_text(encoding="utf-8")
        self.lines = self.content.splitlines()

    def test_auth_vars_documented(self) -> None:
        """All four Phase 85 auth env vars must appear in .env.example."""
        for var in _AUTH_VARS:
            self.assertIn(var, self.content, f"{var} not found in .env.example")

    def test_inline_comments_present(self) -> None:
        """Each auth var must have a # comment on its line or the line above."""
        for var in _AUTH_VARS:
            line_idx = None
            for idx, line in enumerate(self.lines):
                if var in line:
                    line_idx = idx
                    break
            self.assertIsNotNone(line_idx, f"{var} not found in .env.example lines")
            # Check the line itself has a comment, or the line above does.
            current_has_comment = "#" in self.lines[line_idx]
            above_has_comment = (
                line_idx > 0 and "#" in self.lines[line_idx - 1]
            )
            self.assertTrue(
                current_has_comment or above_has_comment,
                f"{var} has no inline comment on its line or the line above",
            )

    def test_section_header_exists(self) -> None:
        """The '# --- Session auth (Phase 85) ---' section header must exist."""
        self.assertIn("# --- Session auth", self.content)


if __name__ == "__main__":
    unittest.main()
