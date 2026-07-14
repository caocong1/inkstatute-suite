"""Tests for the ROUTE_PREFIXES route table."""

from __future__ import annotations

import unittest

from admin_console_api.routes import ROUTE_PREFIXES


class RoutePrefixesTests(unittest.TestCase):
    def test_route_prefixes_contains_expected_count(self) -> None:
        self.assertEqual(len(ROUTE_PREFIXES), 9)

    def test_route_prefixes_values(self) -> None:
        self.assertEqual(
            set(ROUTE_PREFIXES),
            {"/sessions", "/tasks", "/feedback", "/health", "/gates", "/config", "/reports", "/logs", "/audit"},
        )

    def test_route_prefixes_is_tuple_of_strings(self) -> None:
        self.assertIsInstance(ROUTE_PREFIXES, tuple)
        for prefix in ROUTE_PREFIXES:
            self.assertIsInstance(prefix, str)


if __name__ == "__main__":
    unittest.main()
