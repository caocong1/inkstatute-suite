"""Per-tenant/provider rate limiting (RPM/TPM/concurrency).

Pure-Python implementation using:
- ``collections.deque`` for sliding-window RPM/TPM tracking.
- ``asyncio.Semaphore`` for concurrency limits.
- ``asyncio.Lock`` for safe concurrent state updates.
- ``asyncio.monotonic()`` as the default time source (injectable for tests).

No external dependencies — ``dependencies = []`` invariant preserved.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

_WINDOW_SECONDS = 60.0


def _default_clock() -> float:
    return time.monotonic()


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Rate limit configuration for a single provider.

    All fields are optional — ``None`` means no limit for that dimension.
    """

    rpm: int | None = None
    tpm: int | None = None
    max_concurrency: int | None = None


class RateLimiter:
    """Per-tenant per-provider rate limiter with sliding windows.

    RPM and TPM use a 60-second sliding window (``collections.deque``
    of timestamps).  Concurrency uses ``asyncio.Semaphore``.

    If no config exists for a provider, all checks pass (no limit).
    """

    def __init__(
        self,
        configs: dict[str, RateLimitConfig] | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._configs = dict(configs or {})
        self._clock = clock or _default_clock
        self._rpm_windows: dict[tuple[str, str], deque[float]] = {}
        self._tpm_windows: dict[tuple[str, str], deque[tuple[float, int]]] = {}
        self._semaphores: dict[tuple[str, str], asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    def _config(self, provider_id: str) -> RateLimitConfig | None:
        return self._configs.get(provider_id)

    @staticmethod
    def _evict_old_timestamps(window: deque[float], now: float) -> None:
        """Remove timestamps older than the 60-second window."""
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()

    @staticmethod
    def _evict_old_token_entries(window: deque[tuple[float, int]], now: float) -> None:
        """Remove (timestamp, tokens) entries older than the 60-second window."""
        cutoff = now - _WINDOW_SECONDS
        while window and window[0][0] < cutoff:
            window.popleft()

    async def check_rpm(self, tenant_id: str, provider_id: str, now: float | None = None) -> bool:
        """Return True if a new request is within the RPM limit."""
        cfg = self._config(provider_id)
        if cfg is None or cfg.rpm is None:
            return True
        ts = now if now is not None else self._clock()
        key = (tenant_id, provider_id)
        async with self._lock:
            window = self._rpm_windows.setdefault(key, deque())
            self._evict_old_timestamps(window, ts)
            return len(window) < cfg.rpm

    async def check_tpm(self, tenant_id: str, provider_id: str, tokens: int, now: float | None = None) -> bool:
        """Return True if adding *tokens* would stay within the TPM limit."""
        cfg = self._config(provider_id)
        if cfg is None or cfg.tpm is None:
            return True
        ts = now if now is not None else self._clock()
        key = (tenant_id, provider_id)
        async with self._lock:
            window = self._tpm_windows.setdefault(key, deque())
            self._evict_old_token_entries(window, ts)
            current = sum(entry[1] for entry in window)
            return current + tokens <= cfg.tpm

    async def record_request(
        self,
        tenant_id: str,
        provider_id: str,
        tokens: int = 0,
        now: float | None = None,
    ) -> None:
        """Record a request in the RPM and TPM sliding windows."""
        cfg = self._config(provider_id)
        if cfg is None:
            return
        ts = now if now is not None else self._clock()
        key = (tenant_id, provider_id)
        async with self._lock:
            if cfg.rpm is not None:
                rpm_window = self._rpm_windows.setdefault(key, deque())
                rpm_window.append(ts)
            if cfg.tpm is not None and tokens > 0:
                tpm_window = self._tpm_windows.setdefault(key, deque())
                tpm_window.append((ts, tokens))

    async def acquire_concurrency(self, tenant_id: str, provider_id: str) -> asyncio.Semaphore | None:
        """Return the concurrency semaphore for this tenant+provider, or None if no limit."""
        cfg = self._config(provider_id)
        if cfg is None or cfg.max_concurrency is None:
            return None
        key = (tenant_id, provider_id)
        async with self._lock:
            sem = self._semaphores.get(key)
            if sem is None:
                sem = asyncio.Semaphore(cfg.max_concurrency)
                self._semaphores[key] = sem
            return sem

    async def release_concurrency(self, tenant_id: str, provider_id: str) -> None:
        """Release the concurrency semaphore (no-op if no limit configured)."""
        # Semaphore release is handled by the caller via `sem.release()`.
        # This method is provided for API symmetry but is a no-op because
        # asyncio.Semaphore manages its own count.
        pass

    def reset(self) -> None:
        """Clear all rate limit state (for testing)."""
        self._rpm_windows.clear()
        self._tpm_windows.clear()
        self._semaphores.clear()


__all__ = ["RateLimitConfig", "RateLimiter"]
