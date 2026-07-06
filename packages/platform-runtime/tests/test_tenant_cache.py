from __future__ import annotations

import unittest

from platform_runtime import (
    RuntimeFeatureFlags,
    TenantNamespacedCache,
    TenantScope,
    TenantScopeError,
)


class TenantNamespacedCacheDisabledTests(unittest.TestCase):
    def _cache(self) -> TenantNamespacedCache:
        return TenantNamespacedCache(feature_flags=RuntimeFeatureFlags())

    def test_disabled_get_set_no_namespacing(self) -> None:
        cache = self._cache()
        cache.set(TenantScope.NONE, "foo", 1)
        self.assertEqual(cache.get(TenantScope.NONE, "foo"), 1)
        self.assertIn("foo", cache.keys())

    def test_disabled_delete(self) -> None:
        cache = self._cache()
        cache.set(TenantScope.NONE, "foo", 1)
        self.assertTrue(cache.delete(TenantScope.NONE, "foo"))
        self.assertIsNone(cache.get(TenantScope.NONE, "foo"))

    def test_disabled_clear(self) -> None:
        cache = self._cache()
        cache.set(TenantScope.NONE, "a", 1)
        cache.set(TenantScope.NONE, "b", 2)
        cache.clear()
        self.assertEqual(len(cache.keys()), 0)

    def test_disabled_no_tenant_prefix(self) -> None:
        cache = self._cache()
        cache.set(TenantScope.NONE, "key-1", "val")
        for key in cache.keys():
            self.assertFalse(key.startswith("tenant:"))


class TenantNamespacedCacheEnabledTests(unittest.TestCase):
    def _cache(self) -> TenantNamespacedCache:
        return TenantNamespacedCache(
            feature_flags=RuntimeFeatureFlags(multi_tenant_enabled=True),
        )

    def test_enabled_set_namespaces_key(self) -> None:
        cache = self._cache()
        cache.set(TenantScope(tenant_id="firm-a"), "foo", 1)
        self.assertIn("tenant:firm-a:foo", cache.keys())

    def test_enabled_get_returns_value(self) -> None:
        cache = self._cache()
        scope = TenantScope(tenant_id="firm-a")
        cache.set(scope, "foo", 42)
        self.assertEqual(cache.get(scope, "foo"), 42)

    def test_enabled_get_returns_none_for_wrong_tenant(self) -> None:
        cache = self._cache()
        cache.set(TenantScope(tenant_id="firm-a"), "foo", 1)
        self.assertIsNone(cache.get(TenantScope(tenant_id="firm-b"), "foo"))

    def test_enabled_no_cross_tenant_leakage(self) -> None:
        cache = self._cache()
        scope_a = TenantScope(tenant_id="firm-a")
        scope_b = TenantScope(tenant_id="firm-b")
        cache.set(scope_a, "shared", "a")
        cache.set(scope_b, "shared", "b")
        self.assertEqual(cache.get(scope_a, "shared"), "a")
        self.assertEqual(cache.get(scope_b, "shared"), "b")

    def test_enabled_delete(self) -> None:
        cache = self._cache()
        scope = TenantScope(tenant_id="firm-a")
        cache.set(scope, "foo", 1)
        self.assertTrue(cache.delete(scope, "foo"))
        self.assertIsNone(cache.get(scope, "foo"))

    def test_enabled_delete_returns_false_for_missing_key(self) -> None:
        cache = self._cache()
        scope = TenantScope(tenant_id="firm-a")
        self.assertFalse(cache.delete(scope, "nonexistent"))

    def test_enabled_get_without_scope_raises(self) -> None:
        cache = self._cache()
        with self.assertRaises(TenantScopeError):
            cache.get(TenantScope.NONE, "foo")

    def test_enabled_set_without_scope_raises(self) -> None:
        cache = self._cache()
        with self.assertRaises(TenantScopeError):
            cache.set(TenantScope.NONE, "foo", 1)

    def test_enabled_delete_without_scope_raises(self) -> None:
        cache = self._cache()
        with self.assertRaises(TenantScopeError):
            cache.delete(TenantScope.NONE, "foo")

    def test_enabled_all_keys_have_tenant_prefix(self) -> None:
        cache = self._cache()
        cache.set(TenantScope(tenant_id="firm-a"), "k1", 1)
        cache.set(TenantScope(tenant_id="firm-b"), "k2", 2)
        for key in cache.keys():
            self.assertTrue(key.startswith("tenant:"))


if __name__ == "__main__":
    unittest.main()
