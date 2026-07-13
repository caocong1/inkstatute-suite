"""Tests for the pure WeCom webhook handler."""

from __future__ import annotations

import asyncio
import unittest

from platform_runtime import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from wecom_service.webhook import handle_wecom_webhook_request
from wecom_service.wiring import build_wecom_wired_runtime


class WeComWebhookTests(unittest.TestCase):
    """Unit tests for ``handle_wecom_webhook_request`` and post-ACK composition."""

    def _wired(self) -> object:
        backend = FakeBackendAdapter()
        flags = RuntimeFeatureFlags(
            wecom_channel_enabled=True,
            run_runtime_enabled=True,
        )
        return build_wecom_wired_runtime(
            backend=backend,
            flags=flags,
            config_store=None,
            env={
                "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
                "INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "true",
            },
        )

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_message_callback_returns_ack_and_schedules_composition(self) -> None:
        wired = self._wired()
        thunks: list = []
        scheduler = thunks.append
        payload = b'{"conversation_id":"c1","user_id":"u1","content":"hello","message_type":"text"}'
        status, body, headers = self.run_async(
            handle_wecom_webhook_request(
                "POST",
                "/wecom/callback",
                {},
                payload,
                wired=wired,
                post_ack_scheduler=scheduler,
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b"success")
        self.assertEqual(headers.get("Content-Type"), "text/plain; charset=utf-8")
        self.assertEqual(len(thunks), 1)

        evidence = thunks[0]()
        self.assertEqual(evidence["branch"], "message")
        self.assertIn("run_id", evidence)
        self.assertEqual(evidence["status"], "completed_no_reply")

    def test_feedback_callback_returns_ack_and_schedules_feedback(self) -> None:
        wired = self._wired()
        thunks: list = []
        scheduler = thunks.append
        payload = (
            b'{"conversation_id":"c1","user_id":"u1","message_type":"button_callback",'
            b'"feedback_target":"msg-1","feedback_action":"up"}'
        )
        status, body, _headers = self.run_async(
            handle_wecom_webhook_request(
                "POST",
                "/wecom/callback",
                {},
                payload,
                wired=wired,
                post_ack_scheduler=scheduler,
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(thunks), 1)

        evidence = thunks[0]()
        self.assertEqual(evidence["branch"], "feedback")
        self.assertEqual(evidence["status"], "completed")

    def test_get_method_not_allowed(self) -> None:
        wired = self._wired()
        status, body, _headers = self.run_async(
            handle_wecom_webhook_request(
                "GET",
                "/wecom/callback",
                {},
                b"",
                wired=wired,
            )
        )
        self.assertEqual(status, 405)

    def test_unknown_path_returns_404(self) -> None:
        wired = self._wired()
        status, body, _headers = self.run_async(
            handle_wecom_webhook_request(
                "POST",
                "/other",
                {},
                b"{}",
                wired=wired,
            )
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
