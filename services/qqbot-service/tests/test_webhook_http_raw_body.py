"""HOST-02/raw-body: stdlib HTTP wrapper proofs (Phase 70 Plan 03).

No TCP bind required — mocked rfile/wfile exercise Content-Length once-read.
"""

from __future__ import annotations

import asyncio
import io
import json
import unittest
from http.server import BaseHTTPRequestHandler
from typing import Any
from unittest.mock import MagicMock

from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.signature import derive_keypair
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig
from qqbot_service.http_server import QQBotWebhookServer, read_request_body_once
from qqbot_service.wiring import build_qqbot_wired_runtime

DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SIG_TIMESTAMP = "1725442341"
SECRET_ENV = {
    "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
    "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
    "INKSTATUTE_QQBOT_BOT_SECRET": DEMO_BOT_SECRET,
}


def _sign_body(body: bytes) -> str:
    _public_key, seed = derive_keypair(DEMO_BOT_SECRET)
    msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + body
    return ed25519_sign(seed, msg).hex()


def _enabled_wired() -> Any:
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    transport = FakeMessageTransport(response={"id": "msg-http-ok", "status": 200})
    return build_qqbot_wired_runtime(
        backend=FakeBackendAdapter(),
        flags=RuntimeFeatureFlags(
            qqbot_channel_enabled=True,
            run_runtime_enabled=True,
        ),
        host_config=QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            bot_secret_ref="secret://qqbot/bot-secret",
        ),
        env=SECRET_ENV,
        token_manager=token_manager,
        transport=transport,
        token_transport=token_transport,
    )


class CountingRfile(io.BytesIO):
    """BytesIO that counts read() calls for once-read proofs."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_calls = 0

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        self.read_calls += 1
        return super().read(size)


class WebhookHttpRawBodyTests(unittest.TestCase):
    def test_read_request_body_once_honors_content_length(self) -> None:
        payload = b'{"op":0}'
        rfile = CountingRfile(payload + b"TRAILING")
        headers = {"Content-Length": str(len(payload))}
        body = read_request_body_once(rfile, headers, max_body_bytes=1_048_576)
        self.assertEqual(body, payload)
        self.assertEqual(rfile.read_calls, 1)

    def test_read_request_body_zero_length(self) -> None:
        rfile = CountingRfile(b"")
        body = read_request_body_once(rfile, {"Content-Length": "0"}, max_body_bytes=1024)
        self.assertEqual(body, b"")
        self.assertEqual(rfile.read_calls, 0)

    def test_read_request_body_rejects_oversized(self) -> None:
        with self.assertRaises(ValueError):
            read_request_body_once(
                CountingRfile(b"x" * 10),
                {"Content-Length": "10"},
                max_body_bytes=5,
            )

    def test_handler_do_post_delegates_signed_op12(self) -> None:
        envelope = {
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "id": "evt-http-001",
            "d": {
                "author": {"user_openid": "FIXTURE_USER_OPENID_C2C_001"},
                "content": "ping",
                "id": "ROBOT1.0_fixture_http_001",
                "timestamp": "2026-07-10T12:00:00+08:00",
                "attachments": [],
            },
        }
        body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        sig = _sign_body(body)
        scheduled: list[Any] = []

        def recording_scheduler(thunk: Any) -> None:
            scheduled.append(thunk)

        wired = _enabled_wired()
        rfile = CountingRfile(body)
        wfile = io.BytesIO()

        # Build a minimal handler instance without binding a TCP socket.
        handler = QQBotWebhookServer.__new__(QQBotWebhookServer)
        handler.rfile = rfile  # type: ignore[assignment]
        handler.wfile = wfile  # type: ignore[assignment]
        handler.headers = {  # type: ignore[assignment]
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "X-Signature-Ed25519": sig,
            "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
        }
        handler.path = "/qqbot/callback"
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = MagicMock()  # type: ignore[assignment]
        handler.server.wired = wired
        handler.server.env = SECRET_ENV
        handler.server.post_ack_scheduler = recording_scheduler
        handler.server.max_body_bytes = 1_048_576

        # Capture response via BaseHTTPRequestHandler helpers by stubbing.
        sent: dict[str, Any] = {"status": None, "headers": {}, "body": b""}

        def send_response(code: int, message: str | None = None) -> None:
            sent["status"] = code

        def send_header(keyword: str, value: str) -> None:
            sent["headers"][keyword] = value

        def end_headers() -> None:
            return None

        handler.send_response = send_response  # type: ignore[method-assign]
        handler.send_header = send_header  # type: ignore[method-assign]
        handler.end_headers = end_headers  # type: ignore[method-assign]

        handler.do_POST()

        self.assertEqual(rfile.read_calls, 1)
        self.assertEqual(sent["status"], 200)
        resp = json.loads(wfile.getvalue().decode("utf-8") or sent.get("raw", "{}"))
        # Body was written to wfile
        raw_out = wfile.getvalue()
        self.assertTrue(raw_out)
        self.assertEqual(json.loads(raw_out), {"op": 12})
        self.assertEqual(len(scheduled), 1)
        self.assertIn("X-Signature-Ed25519", handler.headers)

    def test_handler_op13_challenge_without_scheduler(self) -> None:
        envelope = {
            "op": 13,
            "d": {"plain_token": "FIXTURE_PLAIN_TOKEN_001", "event_ts": "FIXTURE_EVENT_TS_001"},
        }
        body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        sig = _sign_body(body)
        scheduled: list[Any] = []
        wired = _enabled_wired()
        rfile = CountingRfile(body)
        wfile = io.BytesIO()

        handler = QQBotWebhookServer.__new__(QQBotWebhookServer)
        handler.rfile = rfile  # type: ignore[assignment]
        handler.wfile = wfile  # type: ignore[assignment]
        handler.headers = {  # type: ignore[assignment]
            "Content-Length": str(len(body)),
            "X-Signature-Ed25519": sig,
            "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
        }
        handler.path = "/qqbot/callback"
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = MagicMock()  # type: ignore[assignment]
        handler.server.wired = wired
        handler.server.env = SECRET_ENV
        handler.server.post_ack_scheduler = scheduled.append
        handler.server.max_body_bytes = 1_048_576

        def send_response(code: int, message: str | None = None) -> None:
            handler._status = code  # type: ignore[attr-defined]

        handler.send_response = send_response  # type: ignore[method-assign]
        handler.send_header = lambda *a, **k: None  # type: ignore[method-assign]
        handler.end_headers = lambda: None  # type: ignore[method-assign]

        handler.do_POST()
        self.assertEqual(handler._status, 200)  # type: ignore[attr-defined]
        payload = json.loads(wfile.getvalue())
        self.assertIn("plain_token", payload)
        self.assertEqual(scheduled, [])


if __name__ == "__main__":
    unittest.main()
