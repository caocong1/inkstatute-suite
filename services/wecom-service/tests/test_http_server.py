"""Tests for the WeCom HTTP host wrapper."""

from __future__ import annotations

import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from platform_runtime import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureDisabledError, RuntimeFeatureFlags
from wecom_service.__main__ import create_server
from wecom_service.wiring import WeComWiredRuntime, build_wecom_wired_runtime


class WeComHttpServerTests(unittest.TestCase):
    """Smoke tests for ``WeComWebhookServer`` and ``create_server``."""

    def _start_server(self, httpd):
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.shutdown)

    def test_create_server_raises_when_channel_disabled(self) -> None:
        env = {
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "false",
            "WECOM_HOST_PORT": "0",
        }
        with self.assertRaises(RuntimeFeatureDisabledError):
            create_server(env=env)

    def test_create_server_binds_and_serves_health(self) -> None:
        env = {
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
            "WECOM_HOST_PORT": "0",
        }
        httpd = create_server(env=env)
        self._start_server(httpd)
        host, port = httpd.server_address

        req = Request(f"http://{host}:{port}/health", method="GET")
        with urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read()
        self.assertIn(b"ok", body)

    def test_post_callback_returns_success(self) -> None:
        env = {
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
            "WECOM_HOST_PORT": "0",
        }
        httpd = create_server(env=env)
        # Avoid running post-ACK in the background; just verify the HTTP response.
        httpd.post_ack_scheduler = lambda _thunk: None  # type: ignore[attr-defined]
        self._start_server(httpd)
        host, port = httpd.server_address

        payload = b'{"conversation_id":"c1","user_id":"u1","content":"hello","message_type":"text"}'
        req = Request(
            f"http://{host}:{port}/wecom/callback",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read()
        self.assertEqual(body, b"success")

    def test_post_callback_rejects_unknown_path(self) -> None:
        env = {
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
            "WECOM_HOST_PORT": "0",
        }
        httpd = create_server(env=env)
        self._start_server(httpd)
        host, port = httpd.server_address

        req = Request(
            f"http://{host}:{port}/unknown",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 404)

    def test_post_callback_rejects_oversized_body(self) -> None:
        env = {
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
            "WECOM_HOST_PORT": "0",
        }
        httpd = create_server(env=env)
        self._start_server(httpd)
        host, port = httpd.server_address

        httpd.max_body_bytes = 16  # type: ignore[attr-defined]
        req = Request(
            f"http://{host}:{port}/wecom/callback",
            data=b'{"conversation_id":"c1","user_id":"u1"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
