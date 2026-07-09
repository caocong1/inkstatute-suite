"""QQ Bot access token manager — acquire, cache, auto-refresh, single-flight.

Uses asyncio.Lock and a transport protocol for token acquisition. Stdlib only;
dependencies = [] invariant preserved.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Any, Callable, Protocol


def _default_clock() -> float:
    return time.monotonic()


class TokenTransport(Protocol):
    """Transport abstraction for the QQ Bot getAppAccessToken endpoint.

    Tests inject a fake transport so no real HTTP client or network
    access is required.
    """

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        """Return the parsed JSON response from getAppAccessToken."""
        ...


class FakeTokenTransport:
    """Convenience fake transport for tests (no HTTP client required)."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.call_count = 0
        self.last_app_id: str | None = None
        self.last_client_secret: str | None = None

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        self.call_count += 1
        self.last_app_id = app_id
        self.last_client_secret = client_secret
        if self.error is not None:
            raise self.error
        return self.response or {"access_token": "fixture-token", "expires_in": 7200}


class TokenError(Exception):
    """Token acquisition failure with a sanitized message."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UrllibTokenTransport:
    """Production transport using lazy urllib.request + asyncio.to_thread.

    The HTTP client (urllib.request from stdlib) is imported inside
    _blocking_fetch only — never at module top level — so the package
    imports cleanly without any external HTTP library.
    """

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def fetch_token(self, app_id: str, client_secret: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._blocking_fetch, app_id, client_secret)

    def _blocking_fetch(self, app_id: str, client_secret: str) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        url = "https://bots.qq.com/app/getAppAccessToken"
        data = json.dumps({"appId": app_id, "clientSecret": client_secret}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise TokenError(
                "QQ Bot token request failed",
                status_code=exc.code,
            ) from None
        except urllib.error.URLError:
            raise TokenError("QQ Bot token endpoint unreachable") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise TokenError("QQ Bot token response invalid") from None
        if not isinstance(parsed, dict):
            raise TokenError("QQ Bot token response invalid")
        return parsed


class TokenManager:
    """QQ Bot access token manager with cache, auto-refresh, and single-flight.

    Acquires the access token via POST /getAppAccessToken using appId +
    clientSecret, caches it with the returned expires_in TTL, auto-refreshes
    60 seconds before expiry, and ensures concurrent refresh is single-flight
    via asyncio.Lock (no duplicate token requests).
    """

    def __init__(
        self,
        *,
        app_id: str,
        client_secret: str,
        transport: TokenTransport | None = None,
        clock: Callable[[], float] | None = None,
        refresh_margin: float = 60.0,
    ) -> None:
        self._app_id = app_id
        self._client_secret = client_secret
        self._transport = transport or UrllibTokenTransport()
        self._clock = clock or _default_clock
        self._refresh_margin = refresh_margin
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        """Return a valid access token, refreshing if needed.

        Fast path: return cached token if not near expiry (no lock).
        Slow path: acquire lock, re-check, refresh if still expired.
        """
        if self._token is not None and not self._is_near_expiry():
            return self._token

        async with self._lock:
            # Re-check: another coroutine may have refreshed while we waited.
            if self._token is not None and not self._is_near_expiry():
                return self._token

            response = await self._transport.fetch_token(
                self._app_id, self._client_secret
            )
            # Extract both values before mutating cache so a failed expiry
            # parse cannot leave _token updated without a matching _expires_at.
            token = self._extract_token(response)
            ttl = self._extract_expiry(response)
            self._token = token
            self._expires_at = self._clock() + ttl
            return self._token

    def _is_near_expiry(self) -> bool:
        """Return True if the token expires within the refresh margin."""
        return self._clock() >= (self._expires_at - self._refresh_margin)

    @staticmethod
    def _extract_token(response: dict[str, Any]) -> str:
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise TokenError("QQ Bot token response missing access_token")
        return token

    def _extract_expiry(self, response: dict[str, Any]) -> float:
        expires_in = response.get("expires_in")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise TokenError("QQ Bot token response missing or invalid expires_in")
        value = float(expires_in)
        if not math.isfinite(value) or value <= 0:
            raise TokenError("QQ Bot token response missing or invalid expires_in")
        if value <= self._refresh_margin:
            raise TokenError("QQ Bot token expires_in too short for refresh margin")
        return value

    def invalidate(self) -> None:
        """Force the next get_token() call to refresh (e.g., after a 401)."""
        self._token = None
        self._expires_at = 0.0


__all__ = [
    "TokenManager",
    "TokenTransport",
    "FakeTokenTransport",
    "UrllibTokenTransport",
    "TokenError",
]
