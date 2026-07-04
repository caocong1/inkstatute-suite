"""Tests for static token authentication."""

from __future__ import annotations

import os
import unittest

from admin_console_api.auth import (
    ADMIN_API_TOKEN_ENV,
    check_auth_header,
    extract_auth_header,
    resolve_admin_token,
)


class AuthTests(unittest.TestCase):
    def test_resolve_admin_token_returns_token(self) -> None:
        self.assertEqual(resolve_admin_token({"ADMIN_API_TOKEN": "test-token"}), "test-token")

    def test_resolve_admin_token_returns_none_when_absent(self) -> None:
        self.assertIsNone(resolve_admin_token({}))

    def test_resolve_admin_token_returns_none_when_empty(self) -> None:
        self.assertIsNone(resolve_admin_token({"ADMIN_API_TOKEN": ""}))

    def test_resolve_admin_token_reads_os_environ_when_env_none(self) -> None:
        os.environ["ADMIN_API_TOKEN"] = "env-token"
        try:
            self.assertEqual(resolve_admin_token(None), "env-token")
        finally:
            del os.environ["ADMIN_API_TOKEN"]

    def test_check_auth_header_valid_bearer(self) -> None:
        self.assertIs(check_auth_header("Bearer test-token", "test-token"), True)

    def test_check_auth_header_invalid_token(self) -> None:
        self.assertIs(check_auth_header("Bearer wrong-token", "test-token"), False)

    def test_check_auth_header_missing_header(self) -> None:
        self.assertIs(check_auth_header(None, "test-token"), False)

    def test_check_auth_header_no_bearer_prefix(self) -> None:
        self.assertIs(check_auth_header("test-token", "test-token"), False)

    def test_check_auth_header_token_not_configured(self) -> None:
        self.assertIs(check_auth_header("Bearer test-token", None), False)

    def test_check_auth_header_constant_time(self) -> None:
        # Length mismatch must not raise — returns False gracefully.
        self.assertIs(check_auth_header("Bearer short", "test-token"), False)

    def test_extract_auth_header_case_insensitive(self) -> None:
        self.assertEqual(
            extract_auth_header({"authorization": "Bearer test-token"}),
            "Bearer test-token",
        )

    def test_extract_auth_header_missing(self) -> None:
        self.assertIsNone(extract_auth_header({}))

    def test_extract_auth_header_none_headers(self) -> None:
        self.assertIsNone(extract_auth_header(None))

    def test_admin_api_token_env_constant(self) -> None:
        self.assertEqual(ADMIN_API_TOKEN_ENV, "ADMIN_API_TOKEN")


if __name__ == "__main__":
    unittest.main()
