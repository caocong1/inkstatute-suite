"""Tests for Hindsight bank isolation enforcement via TenantGuard.

When ``multi_tenant_enabled=True``, ``HindsightMemory._enforce_tenant_scope``
raises ``TenantScopeError`` before any client call if tenant_id is unresolved.
When ``False``, it is a no-op (v1.6 behavior).
"""

from __future__ import annotations

from dataclasses import dataclass
import unittest

from platform_runtime import RuntimeFeatureFlags, TenantScopeError
from platform_runtime.hindsight_memory import HindsightMemory
from platform_runtime.long_term_memory import (
    MemoryRecallInput,
    MemoryReflectInput,
    MemoryRetainInput,
)


class _FakeHindsightClient:
    """Fake client that raises on any method call — ensures enforcement
    happens BEFORE the client is contacted."""

    base_url = "http://localhost:8888"

    async def acreate_bank(self, bank_id: str) -> None:
        # _ensure_bank swallows "already exists" errors; raise a different
        # error so the caller sees HindsightMemoryError, proving enforcement
        # passed and the client was reached.
        raise RuntimeError("fake client: bank creation not supported")

    async def aretain(self, **kwargs: object) -> None:
        raise AssertionError("aretain should not be called")

    async def arecall(self, **kwargs: object) -> None:
        raise AssertionError("arecall should not be called")

    async def areflect(self, **kwargs: object) -> None:
        raise AssertionError("areflect should not be called")


class HindsightTenantEnforceDirectTests(unittest.TestCase):
    """Unit tests for _enforce_tenant_scope in isolation."""

    def _memory(self, *, enabled: bool) -> HindsightMemory:
        flags = RuntimeFeatureFlags(multi_tenant_enabled=enabled)
        return HindsightMemory(client=_FakeHindsightClient(), feature_flags=flags)

    def test_disabled_does_not_raise_for_null_tenant_id(self) -> None:
        memory = self._memory(enabled=False)
        # No exception — v1.6 behavior, enforcement is a no-op
        memory._enforce_tenant_scope(None, None, None)

    def test_disabled_does_not_raise_for_empty_tenant_id(self) -> None:
        memory = self._memory(enabled=False)
        memory._enforce_tenant_scope("", "", "")

    def test_disabled_does_not_raise_for_valid_tenant_id(self) -> None:
        memory = self._memory(enabled=False)
        memory._enforce_tenant_scope("firm-a", "ws-1", "user-1")

    def test_enabled_raises_for_none_tenant_id(self) -> None:
        memory = self._memory(enabled=True)
        with self.assertRaises(TenantScopeError):
            memory._enforce_tenant_scope(None, "ws-1", "user-1")

    def test_enabled_raises_for_empty_tenant_id(self) -> None:
        memory = self._memory(enabled=True)
        with self.assertRaises(TenantScopeError):
            memory._enforce_tenant_scope("", "ws-1", "user-1")

    def test_enabled_accepts_valid_tenant_id(self) -> None:
        memory = self._memory(enabled=True)
        # No exception — valid tenant_id passes enforcement
        memory._enforce_tenant_scope("firm-a", "ws-1", "user-1")


class HindsightTenantEnforceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Integration tests verifying enforcement runs before client calls."""

    def _memory(self, *, enabled: bool) -> HindsightMemory:
        flags = RuntimeFeatureFlags(multi_tenant_enabled=enabled)
        return HindsightMemory(client=_FakeHindsightClient(), feature_flags=flags)

    def _retain_input(self, tenant_id: str = "firm-a") -> MemoryRetainInput:
        return MemoryRetainInput(
            tenant_id=tenant_id,
            workspace_id="ws-1",
            user_id="user-1",
            bank_id="ink-firm-a:ws-1:user-1",
            content="some safe content",
        )

    def _recall_input(self, tenant_id: str = "firm-a") -> MemoryRecallInput:
        return MemoryRecallInput(
            tenant_id=tenant_id,
            workspace_id="ws-1",
            user_id="user-1",
            bank_id="ink-firm-a:ws-1:user-1",
            query="some query",
        )

    def _reflect_input(self, tenant_id: str = "firm-a") -> MemoryReflectInput:
        return MemoryReflectInput(
            tenant_id=tenant_id,
            workspace_id="ws-1",
            user_id="user-1",
            bank_id="ink-firm-a:ws-1:user-1",
            query="some query",
        )

    async def test_enabled_aretain_enforces_before_client(self) -> None:
        """When enabled and tenant_id is valid, enforcement passes and
        the client is reached — proving enforcement did NOT block."""
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=True)
        with self.assertRaises(HindsightMemoryError):
            await memory.aretain(self._retain_input("firm-a"))

    async def test_enabled_arecall_enforces_before_client(self) -> None:
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=True)
        with self.assertRaises(HindsightMemoryError):
            await memory.arecall(self._recall_input("firm-a"))

    async def test_enabled_areflect_enforces_before_client(self) -> None:
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=True)
        with self.assertRaises(HindsightMemoryError):
            await memory.areflect(self._reflect_input("firm-a"))

    async def test_disabled_aretain_does_not_raise_tenant_scope_error(self) -> None:
        """When disabled, no TenantScopeError is raised (v1.6 behavior).

        The fake client will raise HindsightMemoryError, but NOT TenantScopeError.
        """
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=False)
        with self.assertRaises(HindsightMemoryError):
            await memory.aretain(self._retain_input("firm-a"))

    async def test_disabled_arecall_does_not_raise_tenant_scope_error(self) -> None:
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=False)
        with self.assertRaises(HindsightMemoryError):
            await memory.arecall(self._recall_input("firm-a"))

    async def test_disabled_areflect_does_not_raise_tenant_scope_error(self) -> None:
        from platform_runtime.hindsight_memory import HindsightMemoryError
        memory = self._memory(enabled=False)
        with self.assertRaises(HindsightMemoryError):
            await memory.areflect(self._reflect_input("firm-a"))


if __name__ == "__main__":
    unittest.main()
