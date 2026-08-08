"""Tests for StaggeredStartupSemaphore (SVC-08).

Covers semaphore construction, concurrent acquire limiting, entry/exit
tracking, wrap_initialize, run_staggered, exception safety, and
non-blocking of unrelated operations.
"""

from __future__ import annotations

import asyncio
import unittest

from arena_service.staggered_startup import StaggeredStartupSemaphore


class StaggeredStartupTests(unittest.IsolatedAsyncioTestCase):
    """Tests 1-9: StaggeredStartupSemaphore behaviours."""

    # -- Test 1: construction with max_concurrent ------------------------

    def test_construction_default_max_concurrent(self):
        # Test 1: default max_concurrent = 2.
        sem = StaggeredStartupSemaphore()
        self.assertEqual(sem.max_concurrent, 2)
        self.assertEqual(sem.current_concurrent, 0)

    def test_construction_custom_max_concurrent(self):
        sem = StaggeredStartupSemaphore(max_concurrent=4)
        self.assertEqual(sem.max_concurrent, 4)

    # -- Test 2: up to max_concurrent proceed without blocking -----------

    async def test_two_acquires_proceed_without_blocking(self):
        # Test 2: max_concurrent=2 → 2 acquires proceed; 3rd blocks.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        acquired = []

        async def hold(idx: int, delay: float) -> None:
            async with sem.acquire():
                acquired.append(idx)
                await asyncio.sleep(delay)

        # Launch 2 — both should proceed immediately.
        t1 = asyncio.create_task(hold(1, 0.05))
        t2 = asyncio.create_task(hold(2, 0.05))
        await asyncio.sleep(0.01)
        # Both should have entered by now.
        self.assertEqual(sem.current_concurrent, 2)
        self.assertEqual(set(acquired), {1, 2})
        await asyncio.gather(t1, t2)
        self.assertEqual(sem.current_concurrent, 0)

    # -- Test 3: 3rd acquire blocks until one releases -------------------

    async def test_third_acquire_blocks_until_release(self):
        # Test 3: with max_concurrent=2, 3rd blocks.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        entered: list[int] = []

        async def hold(idx: int, delay: float) -> None:
            async with sem:
                entered.append(idx)
                await asyncio.sleep(delay)

        t1 = asyncio.create_task(hold(1, 0.1))
        t2 = asyncio.create_task(hold(2, 0.1))
        t3 = asyncio.create_task(hold(3, 0.05))
        await asyncio.sleep(0.02)
        # Only 1 and 2 should have entered.
        self.assertEqual(set(entered), {1, 2})
        self.assertEqual(sem.current_concurrent, 2)
        # 3 is still waiting.
        self.assertNotIn(3, entered)
        await asyncio.gather(t1, t2, t3)
        # All 3 eventually entered.
        self.assertEqual(set(entered), {1, 2, 3})
        self.assertEqual(sem.current_concurrent, 0)

    # -- Test 4: entry/exit order after release --------------------------

    async def test_third_proceeds_after_first_releases(self):
        # Test 4: after one of the first 2 releases, 3rd proceeds.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        order: list[str] = []

        async def hold(idx: int, delay: float) -> None:
            async with sem:
                order.append(f"enter-{idx}")
                await asyncio.sleep(delay)
                order.append(f"exit-{idx}")

        t1 = asyncio.create_task(hold(1, 0.05))
        t2 = asyncio.create_task(hold(2, 0.1))
        t3 = asyncio.create_task(hold(3, 0.02))
        await asyncio.gather(t1, t2, t3)
        # 3 must enter after 1 exits.
        exit1_idx = order.index("exit-1")
        enter3_idx = order.index("enter-3")
        self.assertGreater(enter3_idx, exit1_idx)

    # -- Test 5: current_concurrent tracks held permits ------------------

    async def test_current_concurrent_tracks_permits(self):
        # Test 5: 0 when idle, 2 when both held.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        self.assertEqual(sem.current_concurrent, 0)

        async with sem:
            self.assertEqual(sem.current_concurrent, 1)
            async with sem:
                self.assertEqual(sem.current_concurrent, 2)
            self.assertEqual(sem.current_concurrent, 1)
        self.assertEqual(sem.current_concurrent, 0)

    # -- Test 6: wrap_initialize protects submit_run ---------------------

    async def test_wrap_initialize_acquires_semaphore(self):
        # Test 6: wrapped fn acquires semaphore before calling.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        call_log: list[int] = []

        async def fake_submit_run(req: int) -> int:
            call_log.append(sem.current_concurrent)
            await asyncio.sleep(0.02)
            return req * 10

        wrapped = sem.wrap_initialize(fake_submit_run)
        result = await wrapped(5)
        self.assertEqual(result, 50)
        # While inside, current_concurrent was 1.
        self.assertEqual(call_log, [1])
        # After, back to 0.
        self.assertEqual(sem.current_concurrent, 0)

    # -- Test 7: 4 agents, at most 2 concurrent --------------------------

    async def test_four_agents_at_most_two_concurrent(self):
        # Test 7: 4 agents, max_concurrent=2 → at most 2 simultaneous.
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        max_concurrent_observed = 0
        current = 0
        lock = asyncio.Lock()

        async def fake_init(agent_id: int) -> int:
            nonlocal current, max_concurrent_observed
            async with sem:
                async with lock:
                    current += 1
                    if current > max_concurrent_observed:
                        max_concurrent_observed = current
                await asyncio.sleep(0.05)
                async with lock:
                    current -= 1
            return agent_id

        results = await asyncio.gather(*[fake_init(i) for i in range(4)])
        self.assertEqual(sorted(results), [0, 1, 2, 3])
        self.assertLessEqual(max_concurrent_observed, 2)
        self.assertGreaterEqual(max_concurrent_observed, 1)

    # -- Test 8: semaphore does not block unrelated operations ------------

    async def test_semaphore_does_not_block_unrelated_operations(self):
        # Test 8: non-wrapped operations are not affected.
        sem = StaggeredStartupSemaphore(max_concurrent=1)

        # Hold the semaphore.
        await sem._semaphore.acquire()
        sem._current += 1

        # An unrelated coroutine should complete immediately.
        async def unrelated() -> str:
            await asyncio.sleep(0.01)
            return "unrelated-done"

        result = await asyncio.wait_for(unrelated(), timeout=1.0)
        self.assertEqual(result, "unrelated-done")

        # Release.
        sem._current -= 1
        sem._semaphore.release()

    # -- Test 9: semaphore released on exception -------------------------

    async def test_semaphore_released_on_exception(self):
        # Test 9: wrapped fn raises → semaphore still released.
        sem = StaggeredStartupSemaphore(max_concurrent=2)

        async def failing_fn() -> None:
            raise RuntimeError("init failed")

        wrapped = sem.wrap_initialize(failing_fn)
        with self.assertRaises(RuntimeError):
            await wrapped()
        # Semaphore must be released.
        self.assertEqual(sem.current_concurrent, 0)
        # Should be able to acquire again immediately.
        async with sem:
            self.assertEqual(sem.current_concurrent, 1)

    # -- Test 9b: run_staggered completes all requests -------------------

    async def test_run_staggered_completes_all(self):
        # run_staggered with 4 requests, max_concurrent=2.
        # run_staggered already wraps with the semaphore, so fake_submit
        # must NOT acquire the semaphore itself (no double-wrap).
        sem = StaggeredStartupSemaphore(max_concurrent=2)
        max_concurrent_observed = 0
        current = 0
        lock = asyncio.Lock()

        async def fake_submit(req: int) -> int:
            nonlocal current, max_concurrent_observed
            async with lock:
                current += 1
                if current > max_concurrent_observed:
                    max_concurrent_observed = current
            await asyncio.sleep(0.02)
            async with lock:
                current -= 1
            return req + 100

        results = await sem.run_staggered(fake_submit, [0, 1, 2, 3])
        self.assertEqual(sorted(results), [100, 101, 102, 103])
        self.assertLessEqual(max_concurrent_observed, 2)


if __name__ == "__main__":
    unittest.main()
