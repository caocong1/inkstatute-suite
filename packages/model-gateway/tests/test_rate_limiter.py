"""Tests for RateLimiter (RPM/TPM/concurrency per tenant per provider)."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_model_gateway.rate_limiter import RateLimitConfig, RateLimiter


class TestRpmLimiting(unittest.IsolatedAsyncioTestCase):
    """RPM (requests per minute) sliding-window tests."""

    async def test_rpm_under_limit_allows(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=60)}
        limiter = RateLimiter(cfg)
        result = await limiter.check_rpm("tenant-1", "provider-a", now=0.0)
        self.assertTrue(result)

    async def test_rpm_over_limit_rejects(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=2)}
        limiter = RateLimiter(cfg)
        # Record 2 requests at t=0
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        await limiter.record_request("tenant-1", "provider-a", now=0.1)
        # 3rd request should be rejected
        result = await limiter.check_rpm("tenant-1", "provider-a", now=0.2)
        self.assertFalse(result)

    async def test_rpm_window_evicts_old_entries(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=2)}
        limiter = RateLimiter(cfg)
        # Record 2 requests at t=0
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        await limiter.record_request("tenant-1", "provider-a", now=0.1)
        # At t=61, old entries should be evicted
        result = await limiter.check_rpm("tenant-1", "provider-a", now=61.0)
        self.assertTrue(result)

    async def test_rpm_per_tenant_isolated(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=1)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        # tenant-2 should not be affected by tenant-1's usage
        result_t2 = await limiter.check_rpm("tenant-2", "provider-a", now=0.1)
        self.assertTrue(result_t2)
        # tenant-1 should be at limit
        result_t1 = await limiter.check_rpm("tenant-1", "provider-a", now=0.1)
        self.assertFalse(result_t1)

    async def test_rpm_per_provider_isolated(self) -> None:
        cfg = {
            "provider-a": RateLimitConfig(rpm=1),
            "provider-b": RateLimitConfig(rpm=1),
        }
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        # provider-b should not be affected by provider-a's usage
        result_b = await limiter.check_rpm("tenant-1", "provider-b", now=0.1)
        self.assertTrue(result_b)


class TestTpmLimiting(unittest.IsolatedAsyncioTestCase):
    """TPM (tokens per minute) sliding-window tests."""

    async def test_tpm_under_limit_allows(self) -> None:
        cfg = {"provider-a": RateLimitConfig(tpm=1000)}
        limiter = RateLimiter(cfg)
        result = await limiter.check_tpm("tenant-1", "provider-a", tokens=500, now=0.0)
        self.assertTrue(result)

    async def test_tpm_over_limit_rejects(self) -> None:
        cfg = {"provider-a": RateLimitConfig(tpm=100)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", tokens=60, now=0.0)
        # 60 + 50 = 110 > 100
        result = await limiter.check_tpm("tenant-1", "provider-a", tokens=50, now=0.1)
        self.assertFalse(result)

    async def test_tpm_window_evicts_old_entries(self) -> None:
        cfg = {"provider-a": RateLimitConfig(tpm=100)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", tokens=80, now=0.0)
        # At t=61, old entries evicted
        result = await limiter.check_tpm("tenant-1", "provider-a", tokens=50, now=61.0)
        self.assertTrue(result)

    async def test_tpm_zero_tokens_allowed(self) -> None:
        cfg = {"provider-a": RateLimitConfig(tpm=100)}
        limiter = RateLimiter(cfg)
        result = await limiter.check_tpm("tenant-1", "provider-a", tokens=0, now=0.0)
        self.assertTrue(result)


class TestConcurrencyLimiting(unittest.IsolatedAsyncioTestCase):
    """Concurrency limit tests using asyncio.Semaphore."""

    async def test_concurrency_limit(self) -> None:
        cfg = {"provider-a": RateLimitConfig(max_concurrency=1)}
        limiter = RateLimiter(cfg)
        sem = await limiter.acquire_concurrency("tenant-1", "provider-a")
        self.assertIsNotNone(sem)
        await sem.acquire()
        # Second acquire should block — test with timeout
        try:
            await asyncio.wait_for(sem.acquire(), timeout=0.1)
            self.fail("Should have timed out")
        except asyncio.TimeoutError:
            pass
        sem.release()

    async def test_no_concurrency_limit_returns_none(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=100)}
        limiter = RateLimiter(cfg)
        sem = await limiter.acquire_concurrency("tenant-1", "provider-a")
        self.assertIsNone(sem)


class TestNoConfigSkipsRateLimiting(unittest.IsolatedAsyncioTestCase):
    """When no config exists for a provider, rate limiting is skipped."""

    async def test_no_config_skips_rpm(self) -> None:
        limiter = RateLimiter({})
        result = await limiter.check_rpm("tenant-1", "unknown-provider", now=0.0)
        self.assertTrue(result)

    async def test_no_config_skips_tpm(self) -> None:
        limiter = RateLimiter({})
        result = await limiter.check_tpm("tenant-1", "unknown-provider", tokens=999999, now=0.0)
        self.assertTrue(result)

    async def test_no_config_skips_concurrency(self) -> None:
        limiter = RateLimiter({})
        sem = await limiter.acquire_concurrency("tenant-1", "unknown-provider")
        self.assertIsNone(sem)

    async def test_no_config_record_request_noop(self) -> None:
        limiter = RateLimiter({})
        # Should not raise
        await limiter.record_request("tenant-1", "unknown-provider", tokens=100, now=0.0)


class TestRecordRequest(unittest.IsolatedAsyncioTestCase):
    """record_request adds entries to sliding windows."""

    async def test_record_request_adds_to_rpm_window(self) -> None:
        cfg = {"provider-a": RateLimitConfig(rpm=10)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", now=0.0)
        result = await limiter.check_rpm("tenant-1", "provider-a", now=0.1)
        self.assertTrue(result)  # 1 < 10

    async def test_record_request_adds_to_tpm_window(self) -> None:
        cfg = {"provider-a": RateLimitConfig(tpm=1000)}
        limiter = RateLimiter(cfg)
        await limiter.record_request("tenant-1", "provider-a", tokens=500, now=0.0)
        result = await limiter.check_tpm("tenant-1", "provider-a", tokens=400, now=0.1)
        self.assertTrue(result)  # 500 + 400 = 900 <= 1000


if __name__ == "__main__":
    unittest.main()
