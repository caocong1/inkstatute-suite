"""StaggeredStartupSemaphore — asyncio semaphore for concurrent init limiting.

Implements SVC-08 staggered startup: prevents N agents from calling
``initialize()`` simultaneously by wrapping the ``submit_run`` /
``initialize`` path in an :class:`asyncio.Semaphore`.

The default limit is ``2`` concurrent initializations (matching
``ArenaServiceConfig.max_concurrent_initializations``).  All agents
eventually complete — the semaphore limits concurrency, it does not
block indefinitely.  The semaphore is always released, even when the
wrapped function raises an exception.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

__all__ = ["StaggeredStartupSemaphore"]


class StaggeredStartupSemaphore:
    """Limit concurrent ``initialize`` calls via an asyncio semaphore.

    Parameters
    ----------
    max_concurrent
        Maximum number of concurrent initializations allowed.
        Default ``2``.
    """

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._current = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_concurrent(self) -> int:
        """Return the configured concurrency limit."""
        return self._max_concurrent

    @property
    def current_concurrent(self) -> int:
        """Return the number of currently held permits."""
        return self._current

    # ------------------------------------------------------------------
    # Acquire / release
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self):
        """Async context manager that acquires and releases the semaphore.

        Increments ``current_concurrent`` on entry and decrements on
        exit.  The semaphore is always released, even if the body raises.
        """
        await self._semaphore.acquire()
        self._current += 1
        try:
            yield
        finally:
            self._current -= 1
            self._semaphore.release()

    # ------------------------------------------------------------------
    # Convenience: use the semaphore directly as an async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "StaggeredStartupSemaphore":
        await self._semaphore.acquire()
        self._current += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._current -= 1
        self._semaphore.release()

    # ------------------------------------------------------------------
    # Wrap a submit_run / initialize function
    # ------------------------------------------------------------------

    def wrap_initialize(
        self,
        submit_run_fn: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        """Wrap *submit_run_fn* so it acquires the semaphore before running.

        The returned coroutine acquires the semaphore, calls the
        original function, and releases the semaphore in a ``finally``
        block — ensuring release even on exception.
        """

        async def wrapped(*args: Any, **kwargs: Any) -> T:
            async with self:
                return await submit_run_fn(*args, **kwargs)

        return wrapped

    # ------------------------------------------------------------------
    # Run multiple requests with staggered initialization
    # ------------------------------------------------------------------

    async def run_staggered(
        self,
        submit_run_fn: Callable[..., Awaitable[T]],
        requests: list[Any],
    ) -> list[T]:
        """Run *submit_run_fn* for each request with semaphore limiting.

        Uses :func:`asyncio.gather` with the wrapped function so all
        requests eventually complete, but at most ``max_concurrent``
        run simultaneously.
        """
        wrapped = self.wrap_initialize(submit_run_fn)
        coros = [wrapped(req) for req in requests]
        return await asyncio.gather(*coros)
