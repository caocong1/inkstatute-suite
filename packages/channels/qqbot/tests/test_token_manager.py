"""Lifecycle, concurrent, error-handling, and import-safety unit tests for TokenManager.

Uses FakeTokenTransport and an injectable monotonic clock — no network I/O.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from inkstatute_channels_qqbot.token_manager import (
    FakeTokenTransport,
    TokenError,
    TokenManager,
    UrllibTokenTransport,
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


class TokenManagerConcurrentRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_refresh_is_single_flight(self) -> None:
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

        results = await asyncio.gather(*[manager.get_token() for _ in range(10)])

        self.assertEqual(transport.call_count, 2)
        self.assertTrue(all(token == "token-002" for token in results))


class TokenManagerErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_error_raises_token_error(self) -> None:
        transport = FakeTokenTransport(
            error=TokenError("QQ Bot token request failed", status_code=401)
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError) as ctx:
            await manager.get_token()

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_missing_access_token_in_response(self) -> None:
        transport = FakeTokenTransport(response={"expires_in": 7200})
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_missing_expires_in_in_response(self) -> None:
        transport = FakeTokenTransport(response={"access_token": "token-001"})
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_invalid_expires_in_zero(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 0}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_invalid_expires_in_negative(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": -1}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_invalid_expires_in_bool_rejected(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": True}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError) as ctx:
            await manager.get_token()

        self.assertIn("expires_in", str(ctx.exception))

    async def test_invalid_expires_in_nan_rejected(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": float("nan")}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_invalid_expires_in_inf_rejected(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": float("inf")}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError):
            await manager.get_token()

    async def test_expires_in_too_short_for_refresh_margin(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "token-001", "expires_in": 30}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
            refresh_margin=60.0,
        )

        with self.assertRaises(TokenError) as ctx:
            await manager.get_token()

        self.assertIn("refresh margin", str(ctx.exception))
        self.assertIsNone(manager._token)

    async def test_error_message_does_not_leak_token_value(self) -> None:
        transport = FakeTokenTransport(
            response={"access_token": "secret-token-leak", "expires_in": "bad"}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=transport,
        )

        with self.assertRaises(TokenError) as ctx:
            await manager.get_token()

        message = str(ctx.exception)
        self.assertNotIn("secret-token-leak", message)
        self.assertNotIn(FIXTURE_CLIENT_SECRET, message)
        self.assertNotIn(FIXTURE_APP_ID, message)

    async def test_failed_expiry_extract_does_not_corrupt_cache(self) -> None:
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
        previous_expires_at = manager._expires_at

        transport.response = {"access_token": "new-token", "expires_in": "bad"}
        now = 1000.0 + 7141.0
        with self.assertRaises(TokenError):
            await manager.get_token()

        # Cache must remain the previous successful token+expiry pair.
        self.assertEqual(manager._token, "token-001")
        self.assertEqual(manager._expires_at, previous_expires_at)


class UrllibTokenTransportErrorTests(unittest.TestCase):
    def test_invalid_utf8_body_raises_token_error(self) -> None:
        transport = UrllibTokenTransport()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\xff\xfe"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(TokenError) as ctx:
                transport._blocking_fetch(FIXTURE_APP_ID, FIXTURE_CLIENT_SECRET)

        self.assertEqual(str(ctx.exception), "QQ Bot token response invalid")
        self.assertIsNone(ctx.exception.__cause__)

    def test_invalid_json_body_raises_token_error_without_leak(self) -> None:
        transport = UrllibTokenTransport()
        raw = b'{"access_token":"secret-token-in-body", NOT JSON'
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(TokenError) as ctx:
                transport._blocking_fetch(FIXTURE_APP_ID, FIXTURE_CLIENT_SECRET)

        message = str(ctx.exception)
        self.assertEqual(message, "QQ Bot token response invalid")
        self.assertNotIn("secret-token-in-body", message)
        self.assertIsNone(ctx.exception.__cause__)

    def test_non_dict_json_body_raises_token_error(self) -> None:
        transport = UrllibTokenTransport()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(["not", "a", "dict"]).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(TokenError) as ctx:
                transport._blocking_fetch(FIXTURE_APP_ID, FIXTURE_CLIENT_SECRET)

        self.assertEqual(str(ctx.exception), "QQ Bot token response invalid")
        self.assertIsNone(ctx.exception.__cause__)


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
