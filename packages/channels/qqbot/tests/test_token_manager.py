"""Lifecycle and import-safety unit tests for TokenManager.

Uses FakeTokenTransport and an injectable monotonic clock — no network I/O.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from inkstatute_channels_qqbot.token_manager import (
    FakeTokenTransport,
    TokenError,
    TokenManager,
)

FIXTURE_APP_ID = "fixture-app-id-001"
FIXTURE_CLIENT_SECRET = "fixture-client-secret-001"


class TokenManagerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_call_acquires_token(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            clock=lambda: now,
        )

        token = await manager.get_token()

        self.assertEqual(token, "token-001")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(transport.last_app_id, FIXTURE_APP_ID)
        self.assertEqual(transport.last_client_secret, FIXTURE_CLIENT_SECRET)

    async def test_cached_token_reused_within_validity(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0

        def clock() -> float:
            return now

        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            clock=clock,
        )

        first = await manager.get_token()
        now = 5000.0
        second = await manager.get_token()

        self.assertEqual(first, "token-001")
        self.assertEqual(second, "token-001")
        self.assertEqual(transport.call_count, 1)

    async def test_auto_refresh_60s_before_expiry(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0

        def clock() -> float:
            return now

        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            clock=clock,
        )

        first = await manager.get_token()
        self.assertEqual(first, "token-001")
        self.assertEqual(transport.call_count, 1)

        transport.response = {"access_token": "token-002", "expires_in": 7200}
        now = 1000.0 + 7141.0
        second = await manager.get_token()

        self.assertEqual(second, "token-002")
        self.assertEqual(transport.call_count, 2)

    async def test_uses_response_expires_in_not_hardcoded_7200(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-short", "expires_in": 100}
        )
        now = 1000.0

        def clock() -> float:
            return now

        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            clock=clock,
        )

        first = await manager.get_token()
        self.assertEqual(first, "token-short")
        self.assertEqual(transport.call_count, 1)

        # At 1000+39: still within 100-60=40 margin → cache reused
        now = 1000.0 + 39.0
        cached = await manager.get_token()
        self.assertEqual(cached, "token-short")
        self.assertEqual(transport.call_count, 1)

        # At 1000+41: past margin → refresh
        transport.response = {"access_token": "token-refreshed", "expires_in": 100}
        now = 1000.0 + 41.0
        refreshed = await manager.get_token()
        self.assertEqual(refreshed, "token-refreshed")
        self.assertEqual(transport.call_count, 2)

    async def test_invalidate_forces_refresh(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 7200}
        )
        now = 1000.0

        def clock() -> float:
            return now

        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            clock=clock,
        )

        await manager.get_token()
        self.assertEqual(transport.call_count, 1)

        transport.response = {"access_token": "token-002", "expires_in": 7200}
        manager.invalidate()
        token = await manager.get_token()

        self.assertEqual(token, "token-002")
        self.assertEqual(transport.call_count, 2)


class TokenManagerImportSafetyTests(unittest.TestCase):
    def test_no_top_level_urllib_import(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "inkstatute_channels_qqbot"
            / "token_manager.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if line.startswith(" ") or line.startswith("\t"):
                continue
            self.assertFalse(
                stripped.startswith("import urllib"),
                f"top-level 'import urllib' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from urllib"),
                f"top-level 'from urllib' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("import httpx"),
                f"top-level 'import httpx' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from httpx"),
                f"top-level 'from httpx' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("import aiohttp"),
                f"top-level 'import aiohttp' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from aiohttp"),
                f"top-level 'from aiohttp' forbidden: {line!r}",
            )


if __name__ == "__main__":
    unittest.main()
