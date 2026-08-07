"""Tests for RBAC authorization helpers (rbac_check.py)."""

from __future__ import annotations

import unittest

from rbac.roles import Role

from inkstatute_practice_profile import (
    PROFILE_READ_ROLES,
    PROFILE_WRITE_ROLES,
    check_read_access,
    check_tenant_access,
    check_write_access,
)


class ProfileReadRolesTests(unittest.TestCase):
    def test_contains_all_four_roles(self) -> None:
        self.assertIn(Role.ADMIN, PROFILE_READ_ROLES)
        self.assertIn(Role.OPERATOR, PROFILE_READ_ROLES)
        self.assertIn(Role.LAWYER, PROFILE_READ_ROLES)
        self.assertIn(Role.VIEWER, PROFILE_READ_ROLES)

    def test_has_exactly_four_roles(self) -> None:
        self.assertEqual(len(PROFILE_READ_ROLES), 4)


class ProfileWriteRolesTests(unittest.TestCase):
    def test_contains_admin_and_operator(self) -> None:
        self.assertIn(Role.ADMIN, PROFILE_WRITE_ROLES)
        self.assertIn(Role.OPERATOR, PROFILE_WRITE_ROLES)

    def test_does_not_contain_lawyer_or_viewer(self) -> None:
        self.assertNotIn(Role.LAWYER, PROFILE_WRITE_ROLES)
        self.assertNotIn(Role.VIEWER, PROFILE_WRITE_ROLES)

    def test_has_exactly_two_roles(self) -> None:
        self.assertEqual(len(PROFILE_WRITE_ROLES), 2)


class CheckReadAccessTests(unittest.TestCase):
    def test_admin_can_read(self) -> None:
        self.assertTrue(check_read_access(Role.ADMIN))

    def test_operator_can_read(self) -> None:
        self.assertTrue(check_read_access(Role.OPERATOR))

    def test_lawyer_can_read(self) -> None:
        self.assertTrue(check_read_access(Role.LAWYER))

    def test_viewer_can_read(self) -> None:
        self.assertTrue(check_read_access(Role.VIEWER))


class CheckWriteAccessTests(unittest.TestCase):
    def test_admin_can_write(self) -> None:
        self.assertTrue(check_write_access(Role.ADMIN))

    def test_operator_can_write(self) -> None:
        self.assertTrue(check_write_access(Role.OPERATOR))

    def test_lawyer_cannot_write(self) -> None:
        self.assertFalse(check_write_access(Role.LAWYER))

    def test_viewer_cannot_write(self) -> None:
        self.assertFalse(check_write_access(Role.VIEWER))


class CheckTenantAccessTests(unittest.TestCase):
    def test_same_tenant_allowed(self) -> None:
        self.assertTrue(check_tenant_access("t1", "t1"))

    def test_cross_tenant_denied(self) -> None:
        self.assertFalse(check_tenant_access("t1", "t2"))

    def test_empty_tenant_ids_match(self) -> None:
        self.assertTrue(check_tenant_access("", ""))


if __name__ == "__main__":
    unittest.main()
