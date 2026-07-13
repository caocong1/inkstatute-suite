"""Tests for the QQBot runnable HTTP host entry point."""

from __future__ import annotations

import threading
import unittest
from urllib.request import Request, urlopen

from platform_runtime.feature_flags import RuntimeFeatureDisabledError, RuntimeFeatureFlags
from qqbot_service.__main__ import create_server


class QQBotMainTests(unittest.TestCase):
    """Smoke tests for ``python -m qqbot_service`` create_server."""

    def _start_server(self, httpd):
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.shutdown)

    def test_create_server_raises_when_channel_disabled(self) -> None:
        env = {
            "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "false",
            "QQBOT_HOST_PORT": "0",
        }
        with self.assertRaises(RuntimeFeatureDisabledError):
            create_server(env=env)

    def test_create_server_binds_and_serves_health(self) -> None:
        env = {
            "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true",
            "QQBOT_HOST_PORT": "0",
        }
        httpd = create_server(env=env)
        self._start_server(httpd)
        host, port = httpd.server_address

        req = Request(f"http://{host}:{port}/health", method="GET")
        with urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read()
        self.assertIn(b"ok", body)


if __name__ == "__main__":
    unittest.main()
