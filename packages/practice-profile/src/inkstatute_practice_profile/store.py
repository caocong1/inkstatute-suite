"""PracticeProfileStore Protocol + InMemoryPracticeProfileStore.

Follows the ``SessionStore`` / ``InMemorySessionStore`` pattern from
``packages/rbac/src/rbac/session.py``: a Protocol-based interface with
an in-memory, thread-safe implementation.

Profiles are keyed by ``(tenant_id, plugin)`` — a profile is per-plugin
per-tenant.  The store trusts the caller has already verified tenant
access; cross-tenant enforcement happens at the Gateway layer
(Plan 99-03).
"""

from __future__ import annotations

import threading
from typing import Protocol

from .model import PracticeProfile
from .secret_guard import validate_no_secrets


class PracticeProfileStore(Protocol):
    """Extensible practice profile store interface.

    MVP: :class:`InMemoryPracticeProfileStore` (dict + lock).
    Future: Redis, DB.
    """

    def get(self, tenant_id: str, plugin: str) -> PracticeProfile | None:
        """Return the profile for *(tenant_id, plugin)*, or ``None``."""
        ...

    def upsert(self, tenant_id: str, profile: PracticeProfile) -> None:
        """Insert or update the profile for *(tenant_id, profile.plugin)*.

        Validates no secrets before storing.  Raises :class:`ValueError`
        if ``profile.tenant_id != tenant_id``.
        """
        ...

    def delete(self, tenant_id: str, plugin: str) -> None:
        """Delete the profile for *(tenant_id, plugin)*."""
        ...

    def list_plugins(self, tenant_id: str) -> list[str]:
        """Return plugin names that have profiles for *tenant_id*."""
        ...


class InMemoryPracticeProfileStore:
    """In-memory dict-backed practice profile store (MVP).

    Thread-safe via a ``threading.Lock`` — safe for
    ``ThreadingHTTPServer``.
    """

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], PracticeProfile] = {}
        self._lock = threading.Lock()

    def get(self, tenant_id: str, plugin: str) -> PracticeProfile | None:
        with self._lock:
            return self._profiles.get((tenant_id, plugin))

    def upsert(self, tenant_id: str, profile: PracticeProfile) -> None:
        if profile.tenant_id != tenant_id:
            raise ValueError(
                f"tenant_id mismatch: expected '{tenant_id}', "
                f"got '{profile.tenant_id}'"
            )
        # Validate no secrets before storing.
        validate_no_secrets(profile.to_json())
        with self._lock:
            self._profiles[(tenant_id, profile.plugin)] = profile

    def delete(self, tenant_id: str, plugin: str) -> None:
        with self._lock:
            self._profiles.pop((tenant_id, plugin), None)

    def list_plugins(self, tenant_id: str) -> list[str]:
        with self._lock:
            return [
                plugin
                for (tid, plugin) in self._profiles
                if tid == tenant_id
            ]


__all__ = [
    "PracticeProfileStore",
    "InMemoryPracticeProfileStore",
]
