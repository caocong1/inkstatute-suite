"""Tests for RbacGuard default-deny enforcement and longest-prefix match."""

from __future__ import annotations

import unittest

from rbac.guard import RbacGuard
from rbac.roles import Role


class RbacGuardTests(unittest.TestCase):
    def test_admin_accesses_sessions(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/sessions"), True)

    def test_viewer_accesses_sessions(self) -> None:
        self.assertIs(RbacGuard().check(Role.VIEWER, "/sessions"), True)

    def test_viewer_denied_feedback(self) -> None:
        self.assertIs(RbacGuard().check(Role.VIEWER, "/feedback"), False)

    def test_operator_accesses_feedback(self) -> None:
        self.assertIs(RbacGuard().check(Role.OPERATOR, "/feedback"), True)

    def test_lawyer_denied_gates(self) -> None:
        self.assertIs(RbacGuard().check(Role.LAWYER, "/gates"), False)

    def test_admin_accesses_gates(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/gates"), True)

    def test_unannotated_endpoint_denied(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/unknown"), False)

    def test_longest_prefix_match(self) -> None:
        custom = {
            "/sessions": frozenset({Role.ADMIN}),
            "/sessions/special": frozenset({Role.VIEWER}),
        }
        guard = RbacGuard(custom)
        self.assertIs(guard.check(Role.VIEWER, "/sessions/special"), True)
        self.assertIs(guard.check(Role.ADMIN, "/sessions/special"), False)
        self.assertIs(guard.check(Role.ADMIN, "/sessions/other"), True)

    def test_exact_match(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/sessions"), True)

    def test_query_string_suffix_match(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/sessions?limit=10"), True)

    def test_subpath_match(self) -> None:
        self.assertIs(
            RbacGuard().check(Role.VIEWER, "/sessions/conv-001"),
            True,
        )

    def test_custom_matrix_used(self) -> None:
        guard = RbacGuard({"/x": frozenset({Role.VIEWER})})
        self.assertIs(guard.check(Role.VIEWER, "/x"), True)
        self.assertIs(guard.check(Role.ADMIN, "/x"), False)

    def test_default_matrix_used_when_none(self) -> None:
        self.assertIs(RbacGuard().check(Role.ADMIN, "/gates"), True)

    def test_operator_denied_gates(self) -> None:
        self.assertIs(RbacGuard().check(Role.OPERATOR, "/gates"), False)

    def test_lawyer_accesses_tasks(self) -> None:
        self.assertIs(RbacGuard().check(Role.LAWYER, "/tasks"), True)


if __name__ == "__main__":
    unittest.main()
