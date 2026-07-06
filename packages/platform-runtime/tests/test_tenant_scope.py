from __future__ import annotations

from dataclasses import dataclass
import unittest

from platform_runtime import (
    RuntimeFeatureFlags,
    ScopedQueryFilter,
    TenantGuard,
    TenantScope,
    TenantScopeError,
    TenantScopeRequestContext,
    TenantScopeResolver,
)
from platform_runtime.session_resolver import SessionScope


# Lightweight stand-ins for RBAC Identity and RunRequest (avoid cross-package
# imports in platform-runtime tests).
@dataclass(frozen=True, slots=True)
class _FakeIdentity:
    tenant_id: str | None = None


@dataclass(frozen=True, slots=True)
class _FakeRequest:
    tenant_id: str | None = None
    workspace_id: str | None = None


class TenantScopeTests(unittest.TestCase):
    def test_none_sentinel_is_unresolved(self) -> None:
        scope = TenantScope.NONE
        self.assertIsNone(scope.tenant_id)
        self.assertIsNone(scope.workspace_id)
        self.assertFalse(scope.is_resolved)

    def test_is_resolved_true_when_tenant_id_present(self) -> None:
        scope = TenantScope(tenant_id="firm-a")
        self.assertTrue(scope.is_resolved)

    def test_is_resolved_false_when_tenant_id_empty(self) -> None:
        scope = TenantScope(tenant_id="")
        self.assertFalse(scope.is_resolved)

    def test_is_resolved_false_when_tenant_id_none(self) -> None:
        scope = TenantScope(tenant_id=None)
        self.assertFalse(scope.is_resolved)

    def test_partition_path_with_workspace(self) -> None:
        scope = TenantScope(tenant_id="firm-a", workspace_id="ws-1")
        self.assertEqual(scope.partition_path, "tenants/firm-a/workspaces/ws-1/")

    def test_partition_path_without_workspace(self) -> None:
        scope = TenantScope(tenant_id="firm-a")
        self.assertEqual(scope.partition_path, "tenants/firm-a/")

    def test_partition_path_unresolved(self) -> None:
        scope = TenantScope.NONE
        self.assertEqual(scope.partition_path, "")


class ScopedQueryFilterTests(unittest.TestCase):
    def test_disabled_returns_inactive_filter(self) -> None:
        f = ScopedQueryFilter.disabled()
        self.assertFalse(f.is_active)
        self.assertIsNone(f.tenant_id)

    def test_is_active_true_when_active(self) -> None:
        f = ScopedQueryFilter(tenant_id="firm-a", active=True)
        self.assertTrue(f.is_active)

    def test_is_active_false_when_disabled(self) -> None:
        f = ScopedQueryFilter.disabled()
        self.assertFalse(f.is_active)


class TenantScopeResolverTests(unittest.TestCase):
    def _enabled_flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags(multi_tenant_enabled=True)

    def _disabled_flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags()

    def test_disabled_returns_none_scope(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._disabled_flags())
        ctx = TenantScopeRequestContext(
            identity=_FakeIdentity(tenant_id="firm-a"),
        )
        scope = resolver.resolve(ctx)
        self.assertFalse(scope.is_resolved)

    def test_resolves_from_identity_first(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            identity=_FakeIdentity(tenant_id="firm-a"),
            scope=SessionScope(
                tenant_id="firm-b",
                workspace_id="ws-b",
                channel_id="ch",
                user_id="u",
                bot_instance_id="bot",
                conversation_id="conv",
            ),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-a")

    def test_resolves_from_scope_when_no_identity(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            scope=SessionScope(
                tenant_id="firm-b",
                workspace_id="ws-b",
                channel_id="ch",
                user_id="u",
                bot_instance_id="bot",
                conversation_id="conv",
            ),
            request=_FakeRequest(tenant_id="firm-c"),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-b")
        self.assertEqual(scope.workspace_id, "ws-b")

    def test_resolves_from_request_when_no_identity_or_scope(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            request=_FakeRequest(tenant_id="firm-c", workspace_id="ws-c"),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-c")
        self.assertEqual(scope.workspace_id, "ws-c")

    def test_resolves_from_header_when_no_identity_scope_or_request(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            headers={"X-Tenant-Id": "firm-d"},
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-d")
        self.assertIsNone(scope.workspace_id)

    def test_resolves_from_header_case_insensitive(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            headers={"x-tenant-id": "firm-e"},
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-e")

    def test_returns_none_when_no_source(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext()
        scope = resolver.resolve(ctx)
        self.assertFalse(scope.is_resolved)

    def test_workspace_id_from_scope(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            scope=SessionScope(
                tenant_id="firm-a",
                workspace_id="ws-1",
                channel_id="ch",
                user_id="u",
                bot_instance_id="bot",
                conversation_id="conv",
            ),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.workspace_id, "ws-1")

    def test_workspace_id_from_request(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            request=_FakeRequest(tenant_id="firm-a", workspace_id="ws-2"),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.workspace_id, "ws-2")

    def test_identity_with_empty_tenant_id_falls_through(self) -> None:
        resolver = TenantScopeResolver(feature_flags=self._enabled_flags())
        ctx = TenantScopeRequestContext(
            identity=_FakeIdentity(tenant_id=""),
            request=_FakeRequest(tenant_id="firm-c"),
        )
        scope = resolver.resolve(ctx)
        self.assertEqual(scope.tenant_id, "firm-c")


class TenantGuardTests(unittest.TestCase):
    def _enabled_flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags(multi_tenant_enabled=True)

    def _disabled_flags(self) -> RuntimeFeatureFlags:
        return RuntimeFeatureFlags()

    def test_disabled_returns_disabled_filter(self) -> None:
        guard = TenantGuard(feature_flags=self._disabled_flags())
        f = guard.enforce(TenantScope.NONE)
        self.assertFalse(f.is_active)

    def test_disabled_returns_disabled_filter_even_for_resolved_scope(self) -> None:
        guard = TenantGuard(feature_flags=self._disabled_flags())
        f = guard.enforce(TenantScope(tenant_id="firm-a"))
        self.assertFalse(f.is_active)

    def test_enabled_resolved_scope_returns_active_filter(self) -> None:
        guard = TenantGuard(feature_flags=self._enabled_flags())
        f = guard.enforce(TenantScope(tenant_id="firm-a", workspace_id="ws-1"))
        self.assertTrue(f.is_active)
        self.assertEqual(f.tenant_id, "firm-a")
        self.assertEqual(f.workspace_id, "ws-1")

    def test_enabled_unresolved_scope_raises(self) -> None:
        guard = TenantGuard(feature_flags=self._enabled_flags())
        with self.assertRaises(TenantScopeError):
            guard.enforce(TenantScope.NONE)

    def test_enabled_empty_tenant_id_raises(self) -> None:
        guard = TenantGuard(feature_flags=self._enabled_flags())
        with self.assertRaises(TenantScopeError):
            guard.enforce(TenantScope(tenant_id=""))


if __name__ == "__main__":
    unittest.main()
