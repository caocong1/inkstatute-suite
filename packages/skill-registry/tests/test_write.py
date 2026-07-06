"""Unit tests for the WritableSkillRegistry (write.py)."""

from __future__ import annotations

import unittest

from inkstatute_skill_registry.write import (
    HumanReviewRecord,
    SkillRegistryWriteError,
    SkillRegistryWritePort,
    SkillVersion,
    WritableSkillRegistry,
    WriteRequest,
)


class WritableSkillRegistryCreateTests(unittest.TestCase):
    """Tests for submit_create + approve_write (create path)."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()

    def test_submit_create_returns_pending_request(self) -> None:
        """submit_create returns a WriteRequest with status=pending."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="A test skill",
        )
        self.assertEqual(req.operation, "create")
        self.assertEqual(req.status, "pending")
        self.assertEqual(req.tenant_id, "tenant_a")
        self.assertEqual(req.skill_id, "tenant_a/my_skill")

    def test_approve_create_commits_version_1(self) -> None:
        """approve_write on a create request creates version 1."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="A test skill",
        )
        version = self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        self.assertEqual(version.version, 1)
        self.assertEqual(version.status, "active")
        self.assertEqual(version.name, "my_skill")
        self.assertEqual(version.description, "A test skill")
        self.assertEqual(version.created_by, "admin:tenant_a")
        self.assertIsNotNone(version.review)
        self.assertEqual(version.review.reviewer, "reviewer:tenant_a")
        self.assertEqual(version.review.decision, "approved")

    def test_create_appears_in_list_skills_and_get_current(self) -> None:
        """After create+approve, skill appears in list_skills and get_current."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        skills = self.registry.list_skills("tenant_a")
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "my_skill")
        current = self.registry.get_current("tenant_a", "tenant_a/my_skill")
        self.assertIsNotNone(current)
        self.assertEqual(current.version, 1)

    def test_create_not_committed_before_approval(self) -> None:
        """Before approve_write, get_current returns None (no auto-apply)."""
        self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.assertIsNone(
            self.registry.get_current("tenant_a", "tenant_a/my_skill")
        )
        self.assertEqual(self.registry.list_skills("tenant_a"), [])

    def test_duplicate_create_raises_error(self) -> None:
        """submit_create for an existing active skill raises error."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_create(
                tenant_id="tenant_a",
                name="my_skill",
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:02:00Z",
            )


class WritableSkillRegistryUpdateTests(unittest.TestCase):
    """Tests for submit_update + approve_write (update path)."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()
        self._create_skill()

    def _create_skill(self) -> None:
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="Original",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )

    def test_approve_update_creates_version_2(self) -> None:
        """approve_write on an update request creates version 2."""
        req = self.registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        version = self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        self.assertEqual(version.version, 2)
        self.assertEqual(version.description, "Updated")
        self.assertEqual(version.status, "active")

    def test_get_current_returns_latest_after_update(self) -> None:
        """get_current returns v2 after update."""
        req = self.registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        current = self.registry.get_current("tenant_a", "tenant_a/my_skill")
        self.assertIsNotNone(current)
        self.assertEqual(current.version, 2)
        self.assertEqual(current.description, "Updated")

    def test_get_version_returns_old_version_unchanged(self) -> None:
        """get_version(1) returns the original v1, unchanged after update."""
        req = self.registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        v1 = self.registry.get_version("tenant_a", "tenant_a/my_skill", 1)
        self.assertIsNotNone(v1)
        self.assertEqual(v1.description, "Original")
        self.assertEqual(v1.version, 1)

    def test_update_nonexistent_skill_raises(self) -> None:
        """submit_update for a nonexistent skill raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_update(
                tenant_id="tenant_a",
                skill_id="tenant_a/nonexistent",
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:02:00Z",
            )

    def test_update_deactivated_skill_raises(self) -> None:
        """submit_update for a deactivated skill raises error."""
        dreq = self.registry.submit_deactivate(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
        )
        self.registry.approve_write(
            dreq.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_update(
                tenant_id="tenant_a",
                skill_id="tenant_a/my_skill",
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:04:00Z",
            )


class WritableSkillRegistryDeactivateTests(unittest.TestCase):
    """Tests for submit_deactivate + approve_write (deactivate path)."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )

    def test_approve_deactivate_creates_deactivated_version(self) -> None:
        """approve_write on deactivate creates a new version with status=deactivated."""
        req = self.registry.submit_deactivate(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
        )
        version = self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        self.assertEqual(version.status, "deactivated")
        self.assertEqual(version.version, 2)

    def test_deactivated_skill_not_in_list_skills(self) -> None:
        """After deactivation, skill is not in list_skills but is in list_versions."""
        req = self.registry.submit_deactivate(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        self.assertEqual(self.registry.list_skills("tenant_a"), [])
        versions = self.registry.list_versions("tenant_a", "tenant_a/my_skill")
        self.assertEqual(len(versions), 2)

    def test_deactivate_already_deactivated_raises(self) -> None:
        """submit_deactivate for an already-deactivated skill raises error."""
        req = self.registry.submit_deactivate(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_deactivate(
                tenant_id="tenant_a",
                skill_id="tenant_a/my_skill",
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:04:00Z",
            )


class WritableSkillRegistryRollbackTests(unittest.TestCase):
    """Tests for submit_rollback + approve_write (rollback path)."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()
        # Create v1 with description "Original"
        req1 = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="Original",
        )
        self.registry.approve_write(
            req1.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        # Update to v2 with description "Updated"
        req2 = self.registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        self.registry.approve_write(
            req2.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )

    def test_rollback_creates_new_version_with_old_content(self) -> None:
        """Rollback to v1 creates v3 with v1's content."""
        req = self.registry.submit_rollback(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            target_version=1,
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:04:00Z",
        )
        version = self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:05:00Z",
        )
        self.assertEqual(version.version, 3)
        self.assertEqual(version.description, "Original")
        self.assertEqual(version.status, "active")

    def test_rollback_preserves_history(self) -> None:
        """After rollback, all versions are still in list_versions."""
        req = self.registry.submit_rollback(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            target_version=1,
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:04:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:05:00Z",
        )
        versions = self.registry.list_versions("tenant_a", "tenant_a/my_skill")
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0].version, 1)
        self.assertEqual(versions[1].version, 2)
        self.assertEqual(versions[2].version, 3)

    def test_rollback_nonexistent_version_raises(self) -> None:
        """submit_rollback to a nonexistent version raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_rollback(
                tenant_id="tenant_a",
                skill_id="tenant_a/my_skill",
                target_version=99,
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:04:00Z",
            )

    def test_rollback_nonexistent_skill_raises(self) -> None:
        """submit_rollback for a nonexistent skill raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_rollback(
                tenant_id="tenant_a",
                skill_id="tenant_a/nonexistent",
                target_version=1,
                requested_by="admin:tenant_a",
                requested_at="2026-07-06T12:04:00Z",
            )


class WritableSkillRegistryImmutableVersioningTests(unittest.TestCase):
    """Tests enforcing immutable versioning — existing versions never mutate."""

    def test_existing_version_object_not_mutated_after_update(self) -> None:
        """The v1 SkillVersion object is not mutated after an update creates v2."""
        registry = WritableSkillRegistry()
        req1 = registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="Original",
        )
        registry.approve_write(
            req1.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        v1_before = registry.get_version("tenant_a", "tenant_a/my_skill", 1)
        self.assertIsNotNone(v1_before)

        req2 = registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
            description="Updated",
        )
        registry.approve_write(
            req2.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        v1_after = registry.get_version("tenant_a", "tenant_a/my_skill", 1)
        self.assertIsNotNone(v1_after)
        self.assertEqual(v1_after.description, "Original")
        self.assertEqual(v1_after.version, 1)
        # The v1 object should be the same immutable object (identity check)
        self.assertIs(v1_before, v1_after)


class WritableSkillRegistryTwoPersonRuleTests(unittest.TestCase):
    """Tests for the human-review two-person rule."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()

    def test_self_approval_rejected(self) -> None:
        """approve_write with reviewer == requested_by raises error."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        with self.assertRaises(SkillRegistryWriteError) as ctx:
            self.registry.approve_write(
                req.request_id,
                reviewer="admin:tenant_a",
                reviewed_at="2026-07-06T12:01:00Z",
            )
        self.assertIn("two-person rule", str(ctx.exception))

    def test_no_auto_apply_before_approval(self) -> None:
        """Write is not committed until approve_write is called."""
        self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.assertIsNone(
            self.registry.get_current("tenant_a", "tenant_a/my_skill")
        )

    def test_approve_nonexistent_request_raises(self) -> None:
        """approve_write for a nonexistent request raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.approve_write(
                "nonexistent-id",
                reviewer="reviewer:tenant_a",
                reviewed_at="2026-07-06T12:01:00Z",
            )

    def test_approve_already_approved_request_raises(self) -> None:
        """approve_write on an already-approved request raises error."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.approve_write(
                req.request_id,
                reviewer="reviewer:tenant_a",
                reviewed_at="2026-07-06T12:02:00Z",
            )

    def test_reject_write_creates_no_version(self) -> None:
        """reject_write marks request as rejected; no new version created."""
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        rejected = self.registry.reject_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
            comment="Not needed",
        )
        self.assertEqual(rejected.status, "rejected")
        self.assertIsNotNone(rejected.review)
        self.assertEqual(rejected.review.decision, "rejected")
        self.assertIsNone(
            self.registry.get_current("tenant_a", "tenant_a/my_skill")
        )


class WritableSkillRegistryPerTenantTests(unittest.TestCase):
    """Tests for per-tenant namespace isolation."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
            description="Tenant A skill",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )

    def test_tenant_a_skill_not_visible_to_tenant_b(self) -> None:
        """list_skills(tenant_b) does not return tenant_a's skills."""
        self.assertEqual(self.registry.list_skills("tenant_b"), [])

    def test_get_current_tenant_b_returns_none(self) -> None:
        """get_current from tenant_b for tenant_a's skill returns None."""
        result = self.registry.get_current("tenant_b", "tenant_a/my_skill")
        self.assertIsNone(result)

    def test_cross_tenant_list_versions_raises(self) -> None:
        """list_versions from tenant_b for tenant_a's skill raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.list_versions("tenant_b", "tenant_a/my_skill")

    def test_cross_tenant_get_version_raises(self) -> None:
        """get_version from tenant_b for tenant_a's skill raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.get_version("tenant_b", "tenant_a/my_skill", 1)

    def test_cross_tenant_update_rejected(self) -> None:
        """submit_update with wrong tenant_id raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_update(
                tenant_id="tenant_b",
                skill_id="tenant_a/my_skill",
                requested_by="admin:tenant_b",
                requested_at="2026-07-06T12:02:00Z",
            )

    def test_cross_tenant_deactivate_rejected(self) -> None:
        """submit_deactivate with wrong tenant_id raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_deactivate(
                tenant_id="tenant_b",
                skill_id="tenant_a/my_skill",
                requested_by="admin:tenant_b",
                requested_at="2026-07-06T12:02:00Z",
            )

    def test_cross_tenant_rollback_rejected(self) -> None:
        """submit_rollback with wrong tenant_id raises error."""
        with self.assertRaises(SkillRegistryWriteError):
            self.registry.submit_rollback(
                tenant_id="tenant_b",
                skill_id="tenant_a/my_skill",
                target_version=1,
                requested_by="admin:tenant_b",
                requested_at="2026-07-06T12:02:00Z",
            )

    def test_each_tenant_has_own_skills(self) -> None:
        """Tenants can have skills with the same name without collision."""
        req = self.registry.submit_create(
            tenant_id="tenant_b",
            name="my_skill",
            requested_by="admin:tenant_b",
            requested_at="2026-07-06T12:02:00Z",
            description="Tenant B skill",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_b",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        a_skills = self.registry.list_skills("tenant_a")
        b_skills = self.registry.list_skills("tenant_b")
        self.assertEqual(len(a_skills), 1)
        self.assertEqual(len(b_skills), 1)
        self.assertEqual(a_skills[0].description, "Tenant A skill")
        self.assertEqual(b_skills[0].description, "Tenant B skill")
        self.assertEqual(a_skills[0].skill_id, "tenant_a/my_skill")
        self.assertEqual(b_skills[0].skill_id, "tenant_b/my_skill")


class WritableSkillRegistryReadTests(unittest.TestCase):
    """Tests for read operations on WritableSkillRegistry."""

    def setUp(self) -> None:
        self.registry = WritableSkillRegistry()
        req = self.registry.submit_create(
            tenant_id="tenant_a",
            name="my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
        )

    def test_list_versions_returns_all_in_order(self) -> None:
        """list_versions returns all versions ordered by version number."""
        versions = self.registry.list_versions("tenant_a", "tenant_a/my_skill")
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version, 1)

    def test_list_pending_writes_returns_pending_only(self) -> None:
        """list_pending_writes returns only pending requests for tenant."""
        req = self.registry.submit_update(
            tenant_id="tenant_a",
            skill_id="tenant_a/my_skill",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:02:00Z",
        )
        pending = self.registry.list_pending_writes("tenant_a")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].request_id, req.request_id)
        # After approval, it should no longer be pending
        self.registry.approve_write(
            req.request_id,
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:03:00Z",
        )
        self.assertEqual(self.registry.list_pending_writes("tenant_a"), [])

    def test_get_version_nonexistent_returns_none(self) -> None:
        """get_version for a nonexistent version returns None."""
        result = self.registry.get_version("tenant_a", "tenant_a/my_skill", 99)
        self.assertIsNone(result)

    def test_get_current_nonexistent_returns_none(self) -> None:
        """get_current for a nonexistent skill returns None."""
        result = self.registry.get_current("tenant_a", "tenant_a/nonexistent")
        self.assertIsNone(result)


class WritableSkillRegistryProtocolTests(unittest.TestCase):
    """Tests for SkillRegistryWritePort Protocol compliance."""

    def test_writable_registry_implements_protocol(self) -> None:
        """WritableSkillRegistry has all SkillRegistryWritePort methods."""
        expected_methods = {
            "submit_create",
            "submit_update",
            "submit_deactivate",
            "submit_rollback",
            "approve_write",
            "reject_write",
            "list_versions",
            "get_version",
            "get_current",
            "list_skills",
            "list_pending_writes",
        }
        actual_methods = {
            attr
            for attr in dir(WritableSkillRegistry)
            if not attr.startswith("_") and callable(getattr(WritableSkillRegistry, attr))
        }
        missing = expected_methods - actual_methods
        self.assertEqual(missing, set(), f"Missing methods: {missing}")


class SkillVersionImmutabilityTests(unittest.TestCase):
    """Tests for SkillVersion frozen dataclass immutability."""

    def test_skill_version_is_frozen(self) -> None:
        """SkillVersion is a frozen dataclass — assignment raises FrozenInstanceError."""
        version = SkillVersion(
            skill_id="tenant_a/my_skill",
            tenant_id="tenant_a",
            name="my_skill",
            version=1,
        )
        with self.assertRaises(AttributeError):
            version.version = 2  # type: ignore[misc]

    def test_human_review_record_is_frozen(self) -> None:
        """HumanReviewRecord is a frozen dataclass."""
        review = HumanReviewRecord(
            reviewer="reviewer:tenant_a",
            reviewed_at="2026-07-06T12:01:00Z",
            decision="approved",
        )
        with self.assertRaises(AttributeError):
            review.reviewer = "other"  # type: ignore[misc]

    def test_write_request_is_frozen(self) -> None:
        """WriteRequest is a frozen dataclass."""
        req = WriteRequest(
            request_id="test-id",
            skill_id="tenant_a/my_skill",
            tenant_id="tenant_a",
            operation="create",
            requested_by="admin:tenant_a",
            requested_at="2026-07-06T12:00:00Z",
        )
        with self.assertRaises(AttributeError):
            req.status = "approved"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
