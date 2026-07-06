"""Tests for the declarative permissions matrix."""

from __future__ import annotations

import unittest

from rbac.matrix import PERMISSIONS_MATRIX
from rbac.roles import Role

ADMIN_API_ROUTE_PREFIXES = ("/sessions", "/tasks", "/feedback", "/health", "/gates")


class PermissionsMatrixTests(unittest.TestCase):
    def test_all_admin_routes_annotated(self) -> None:
        for prefix in ADMIN_API_ROUTE_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertIn(prefix, PERMISSIONS_MATRIX)

    def test_gates_admin_only(self) -> None:
        self.assertEqual(PERMISSIONS_MATRIX["/gates"], frozenset({Role.ADMIN}))

    def test_feedback_admin_operator(self) -> None:
        self.assertEqual(
            PERMISSIONS_MATRIX["/feedback"],
            frozenset({Role.ADMIN, Role.OPERATOR}),
        )

    def test_sessions_all_roles(self) -> None:
        self.assertEqual(
            PERMISSIONS_MATRIX["/sessions"],
            frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
        )

    def test_tasks_all_roles(self) -> None:
        self.assertEqual(
            PERMISSIONS_MATRIX["/tasks"],
            frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
        )

    def test_health_admin_operator(self) -> None:
        self.assertEqual(
            PERMISSIONS_MATRIX["/health"],
            frozenset({Role.ADMIN, Role.OPERATOR}),
        )

    def test_matrix_values_are_frozensets(self) -> None:
        for prefix, roles in PERMISSIONS_MATRIX.items():
            with self.subTest(prefix=prefix):
                self.assertIsInstance(roles, frozenset)


if __name__ == "__main__":
    unittest.main()
