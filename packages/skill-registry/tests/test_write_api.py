"""Unit tests for the Skill Registry Write API route handlers."""

from __future__ import annotations

import unittest

from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac.identity import Identity
from rbac.roles import Role

from inkstatute_skill_registry.write import WritableSkillRegistry
from inkstatute_skill_registry.write_api import handle_delete, handle_post, handle_put


def _admin_identity(tenant_id: str = "tenant_a") -> Identity:
    """Create an admin Identity for testing."""
    return Identity(role=Role.ADMIN, tenant_id=tenant_id)


def _operator_identity(tenant_id: str = "tenant_a") -> Identity:
    """Create an operator Identity for testing."""
    return Identity(role=Role.OPERATOR, tenant_id=tenant_id)


def _write_flags(enabled: bool = True) -> RuntimeFeatureFlags:
    """Create feature flags with skill_registry_write_enabled set."""
    return RuntimeFeatureFlags(skill_registry_write_enabled=enabled)


def _create_skill(
    registry: WritableSkillRegistry,
    tenant_id: str = "tenant_a",
    name: str = "my_skill",
    requester: str = "requester:tenant_a",
) -> str:
    """Create a skill and return its request_id (pending, not yet approved)."""
    req = registry.submit_create(
        tenant_id=tenant_id,
        name=name,
        requested_by=requester,
        requested_at="2026-07-06T12:00:00Z",
        description="A test skill",
    )
    return req.request_id


def _create_and_approve_skill(
    registry: WritableSkillRegistry,
    tenant_id: str = "tenant_a",
    name: str = "my_skill",
) -> None:
    """Create and approve a skill."""
    req_id = _create_skill(registry, tenant_id, name)
    registry.approve_write(
        req_id,
        reviewer="reviewer:tenant_a",
        reviewed_at="2026-07-06T12:01:00Z",
    )


class WriteApiFeatureFlagTests(unittest.TestCase):
    """Tests for feature flag gating."""

    def test_flag_disabled_returns_403(self) -> None:
        """When skill_registry_write_enabled=False, POST returns 403."""
        registry = WritableSkillRegistry()
        flags = RuntimeFeatureFlags()  # default: all flags False
        status, body = handle_post(
            "/skills-write/create",
            {"name": "my_skill"},
            registry,
            _admin_identity(),
            flags,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "skill_registry_write_disabled")

    def test_flag_disabled_returns_403_put(self) -> None:
        """When skill_registry_write_enabled=False, PUT returns 403."""
        registry = WritableSkillRegistry()
        flags = RuntimeFeatureFlags()
        status, body = handle_put(
            "/skills-write/approve",
            {"request_id": "x"},
            registry,
            _admin_identity(),
            flags,
        )
        self.assertEqual(status, 403)

    def test_flag_disabled_returns_403_delete(self) -> None:
        """When skill_registry_write_enabled=False, DELETE returns 403."""
        registry = WritableSkillRegistry()
        flags = RuntimeFeatureFlags()
        status, body = handle_delete(
            "/skills-write/deactivate?skill_id=x",
            registry,
            _admin_identity(),
            flags,
        )
        self.assertEqual(status, 403)


class WriteApiRbacTests(unittest.TestCase):
    """Tests for RBAC role gating."""

    def test_non_admin_role_returns_403(self) -> None:
        """Operator role receives 403 from write endpoints."""
        registry = WritableSkillRegistry()
        status, body = handle_post(
            "/skills-write/create",
            {"name": "my_skill"},
            registry,
            _operator_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "forbidden")
        self.assertEqual(body["error"]["role"], "operator")

    def test_lawyer_role_returns_403(self) -> None:
        """Lawyer role receives 403 from write endpoints."""
        registry = WritableSkillRegistry()
        identity = Identity(role=Role.LAWYER, tenant_id="tenant_a")
        status, body = handle_post(
            "/skills-write/create",
            {"name": "my_skill"},
            registry,
            identity,
            _write_flags(True),
        )
        self.assertEqual(status, 403)

    def test_viewer_role_returns_403(self) -> None:
        """Viewer role receives 403 from write endpoints."""
        registry = WritableSkillRegistry()
        identity = Identity(role=Role.VIEWER, tenant_id="tenant_a")
        status, body = handle_post(
            "/skills-write/create",
            {"name": "my_skill"},
            registry,
            identity,
            _write_flags(True),
        )
        self.assertEqual(status, 403)


class WriteApiCreateTests(unittest.TestCase):
    """Tests for POST /skills-write/create."""

    def test_admin_create_returns_201(self) -> None:
        """Admin can submit a create request; returns 201 with request dict."""
        registry = WritableSkillRegistry()
        status, body = handle_post(
            "/skills-write/create",
            {
                "name": "my_skill",
                "description": "A test skill",
                "requested_at": "2026-07-06T12:00:00Z",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["operation"], "create")
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["skill_id"], "tenant_a/my_skill")

    def test_create_duplicate_returns_400(self) -> None:
        """Creating a duplicate active skill returns 400."""
        registry = WritableSkillRegistry()
        _create_and_approve_skill(registry)
        status, body = handle_post(
            "/skills-write/create",
            {"name": "my_skill", "requested_at": "2026-07-06T12:02:00Z"},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "write_error")

    def test_create_missing_name_returns_400(self) -> None:
        """Create without name field returns 400."""
        registry = WritableSkillRegistry()
        status, body = handle_post(
            "/skills-write/create",
            {"description": "no name"},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "missing_field")


class WriteApiUpdateTests(unittest.TestCase):
    """Tests for PUT /skills-write/update."""

    def test_admin_update_returns_201(self) -> None:
        """Admin can submit an update request; returns 201."""
        registry = WritableSkillRegistry()
        _create_and_approve_skill(registry)
        status, body = handle_put(
            "/skills-write/update",
            {
                "skill_id": "tenant_a/my_skill",
                "description": "Updated description",
                "requested_at": "2026-07-06T12:02:00Z",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["operation"], "update")
        self.assertEqual(body["status"], "pending")

    def test_update_nonexistent_returns_400(self) -> None:
        """Updating a nonexistent skill returns 400."""
        registry = WritableSkillRegistry()
        status, body = handle_put(
            "/skills-write/update",
            {"skill_id": "tenant_a/nonexistent", "requested_at": "2026-07-06T12:00:00Z"},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)


class WriteApiDeactivateTests(unittest.TestCase):
    """Tests for DELETE /skills-write/deactivate."""

    def test_admin_deactivate_returns_201(self) -> None:
        """Admin can submit a deactivate request; returns 201."""
        registry = WritableSkillRegistry()
        _create_and_approve_skill(registry)
        status, body = handle_delete(
            "/skills-write/deactivate?skill_id=tenant_a/my_skill&requested_at=2026-07-06T12:02:00Z",
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["operation"], "deactivate")

    def test_deactivate_missing_skill_id_returns_400(self) -> None:
        """Deactivate without skill_id query param returns 400."""
        registry = WritableSkillRegistry()
        status, body = handle_delete(
            "/skills-write/deactivate",
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "missing_field")


class WriteApiApproveTests(unittest.TestCase):
    """Tests for PUT /skills-write/approve (two-person rule)."""

    def test_admin_approve_returns_200(self) -> None:
        """Admin (as reviewer) can approve a pending request; returns 200 with version."""
        registry = WritableSkillRegistry()
        req_id = _create_skill(registry)
        status, body = handle_put(
            "/skills-write/approve",
            {
                "request_id": req_id,
                "reviewed_at": "2026-07-06T12:01:00Z",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["status"], "active")
        self.assertIsNotNone(body["review"])
        self.assertEqual(body["review"]["decision"], "approved")

    def test_self_approval_returns_400(self) -> None:
        """Self-approval (reviewer == requester) returns 400."""
        registry = WritableSkillRegistry()
        # The requester identity is admin:tenant_a (from _admin_identity)
        req_id = _create_skill(registry, requester="admin:tenant_a")
        # The approver identity is also admin:tenant_a
        status, body = handle_put(
            "/skills-write/approve",
            {
                "request_id": req_id,
                "reviewed_at": "2026-07-06T12:01:00Z",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "write_error")
        self.assertIn("two-person rule", body["error"]["message"])

    def test_approve_nonexistent_returns_400(self) -> None:
        """Approving a nonexistent request returns 400."""
        registry = WritableSkillRegistry()
        status, body = handle_put(
            "/skills-write/approve",
            {"request_id": "nonexistent"},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)

    def test_approve_missing_request_id_returns_400(self) -> None:
        """Approve without request_id returns 400."""
        registry = WritableSkillRegistry()
        status, body = handle_put(
            "/skills-write/approve",
            {},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "missing_field")


class WriteApiRejectTests(unittest.TestCase):
    """Tests for PUT /skills-write/reject."""

    def test_admin_reject_returns_200(self) -> None:
        """Admin can reject a pending request; returns 200."""
        registry = WritableSkillRegistry()
        req_id = _create_skill(registry)
        status, body = handle_put(
            "/skills-write/reject",
            {
                "request_id": req_id,
                "reviewed_at": "2026-07-06T12:01:00Z",
                "comment": "Not needed",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "rejected")
        self.assertIsNotNone(body["review"])
        self.assertEqual(body["review"]["decision"], "rejected")


class WriteApiRollbackTests(unittest.TestCase):
    """Tests for POST /skills-write/rollback."""

    def test_admin_rollback_returns_201(self) -> None:
        """Admin can submit a rollback request; returns 201."""
        registry = WritableSkillRegistry()
        _create_and_approve_skill(registry)
        # Update to v2
        update_req = registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        registry.approve_write(
            update_req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        # Now rollback to v1
        status, body = handle_post(
            "/skills-write/rollback",
            {
                "skill_id": "tenant_a/my_skill",
                "target_version": 1,
                "requested_at": "2026-07-06T12:04:00Z",
            },
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["operation"], "rollback")
        self.assertEqual(body["target_version"], 1)


class WriteApiUnknownRouteTests(unittest.TestCase):
    """Tests for unknown routes."""

    def test_unknown_post_route_returns_404(self) -> None:
        """Unknown POST route returns 404."""
        registry = WritableSkillRegistry()
        status, body = handle_post(
            "/skills-write/unknown",
            {},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 404)

    def test_unknown_put_route_returns_404(self) -> None:
        """Unknown PUT route returns 404."""
        registry = WritableSkillRegistry()
        status, body = handle_put(
            "/skills-write/unknown",
            {},
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 404)

    def test_unknown_delete_route_returns_404(self) -> None:
        """Unknown DELETE route returns 404."""
        registry = WritableSkillRegistry()
        status, body = handle_delete(
            "/skills-write/unknown",
            registry,
            _admin_identity(),
            _write_flags(True),
        )
        self.assertEqual(status, 404)


class WriteApiCrossTenantTests(unittest.TestCase):
    """Tests for cross-tenant rejection via API."""

    def test_cross_tenant_update_returns_400(self) -> None:
        """Admin from tenant_b cannot update tenant_a's skill."""
        registry = WritableSkillRegistry()
        _create_and_approve_skill(registry, tenant_id="tenant_a")
        status, body = handle_put(
            "/skills-write/update",
            {
                "skill_id": "tenant_a/my_skill",
                "requested_at": "2026-07-06T12:02:00Z",
            },
            registry,
            _admin_identity("tenant_b"),
            _write_flags(True),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "write_error")


if __name__ == "__main__":
    unittest.main()
