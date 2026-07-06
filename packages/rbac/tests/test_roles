"""Tests for the Role enum."""

from __future__ import annotations

import unittest

from rbac.roles import Role


class RoleTests(unittest.TestCase):
    def test_role_count_is_four(self) -> None:
        self.assertEqual(len(Role), 4)

    def test_role_values(self) -> None:
        self.assertEqual(Role.ADMIN.value, "admin")
        self.assertEqual(Role.OPERATOR.value, "operator")
        self.assertEqual(Role.LAWYER.value, "lawyer")
        self.assertEqual(Role.VIEWER.value, "viewer")

    def test_role_is_str_enum(self) -> None:
        for role in Role:
            self.assertIsInstance(role, str)

    def test_role_lookup_by_value(self) -> None:
        self.assertIs(Role("admin"), Role.ADMIN)
        self.assertIs(Role("viewer"), Role.VIEWER)


if __name__ == "__main__":
    unittest.main()
