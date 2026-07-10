"""HOST-02: ACK-first pure webhook handler proofs (Phase 70 Plan 01).

Uses Fake transports only — no live QQ network, no port bind.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from typing import Any, Callable

from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.signature import derive_keypair
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_wired_runtime

# Planned public API — RED until webhook.py exists.
from qqbot_service.webhook import (  # noqa: F401
    build_raw_inbound_from_http,
    handle_qqbot_webhook_request,
    map_ack_to_http_response,
)

DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SIG_TIMESTAMP = "1725442341"
CALLBACK_PATH = "/qqbot/callback"
FIXTURES_DIR = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "channels"
    / "qqbot"
    / "fixtures"
)
SECRET_ENV = {
    "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
    "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
    "INKSTATUTE_QQBOT_BOT_SECRET": DEMO_BOT_SECRET,
}


def run(coro):
    return asyncio.run(coro)


def _load_envelope(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)["envelope"]


def _sign_body(body: bytes, *, bot_secret: str = DEMO_BOT_SECRET) -> str:
    _public_key, seed = derive_keypair(bot_secret)
    msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + body
    return ed25519_sign(seed, msg).hex()


def _signed_http(
    payload: dict[str, Any],
    *,
    bot_secret: str = DEMO_BOT_SECRET,
) -> tuple[dict[str, str], bytes]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = _sign_body(body, bot_secret=bot_secret)
    headers = {
        "Content-Type": "application/json",
        "X-Signature-Ed25519": sig,
        "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
    }
    return headers, body


def _enabled_wired(
    *,
    message_transport: FakeMessageTransport | None = None,
) -> tuple[Any, FakeMessageTransport]:
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    transport = message_transport or FakeMessageTransport(
        response={"id": "msg-ack-ok", "status": 200}
    )
    wired = build_qqbot_wired_runtime(
        backend=FakeBackendAdapter(),
        flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
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
    return wired, transport


class RecordingScheduler:
    """Captures scheduled thunks without executing them."""

    def __init__(self) -> None:
        self.thunks: list[Callable[[], Any]] = []
        self.invoked = 0

    def __call__(self, thunk: Callable[[], Any]) -> None:
        self.invoked += 1
        self.thunks.append(thunk)


class WebhookAckFirstTests(unittest.TestCase):
    """HOST-02: challenge / op=12 / refuse / raw-body / scheduler ordering."""

    def test_op13_challenge_returns_promptly_without_scheduler(self) -> None:
        wired, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_validation_challenge.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()

        status, resp_body, _resp_headers = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
            )
        )

        self.assertEqual(status, 200)
        payload = json.loads(resp_body)
        self.assertIn("plain_token", payload)
        self.assertIn("signature", payload)
        self.assertEqual(payload["plain_token"], envelope["d"]["plain_token"])
        self.assertEqual(scheduler.invoked, 0)
        self.assertEqual(len(scheduler.thunks), 0)
        self.assertEqual(transport.call_count, 0)

    def test_verified_message_returns_op12_then_schedules_without_running(self) -> None:
        wired, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()
        executed: list[bool] = []

        def tracking_scheduler(thunk: Callable[[], Any]) -> None:
            scheduler(thunk)

            def wrapped() -> Any:
                executed.append(True)
                return thunk()

            # Replace stored thunk with wrapped so later runs still track.
            scheduler.thunks[-1] = wrapped

        status, resp_body, _resp_headers = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=tracking_scheduler,
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp_body), {"op": 12})
        self.assertEqual(scheduler.invoked, 1)
        self.assertEqual(len(scheduler.thunks), 1)
        self.assertEqual(executed, [], "thunk must not run before handler returns")
        self.assertEqual(transport.call_count, 0)

    def test_disabled_runtime_returns_503_without_scheduler(self) -> None:
        transport = FakeMessageTransport(response={"id": "x", "status": 200})
        token_transport = FakeTokenTransport(
            response={"access_token": "fixture-token", "expires_in": 7200}
        )
        token_manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-client-secret",
            transport=token_transport,
        )
        # Flag OFF → transports stripped; channel disabled → 503
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=False),
            host_config=QQBotHostConfig(
                enabled=True,
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            env=SECRET_ENV,
            token_manager=token_manager,
            transport=transport,
        )
        self.assertFalse(wired.live_io_ready)
        self.assertIsNone(wired.adapter._transport)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()

        status, _resp_body, _resp_headers = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
            )
        )

        self.assertEqual(status, 503)
        self.assertEqual(scheduler.invoked, 0)
        self.assertEqual(transport.call_count, 0)

    def test_invalid_signature_returns_401_without_scheduler(self) -> None:
        wired, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        headers["X-Signature-Ed25519"] = "00" * 64
        scheduler = RecordingScheduler()

        status, resp_body, _resp_headers = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
            )
        )

        self.assertEqual(status, 401)
        self.assertEqual(scheduler.invoked, 0)
        self.assertEqual(transport.call_count, 0)
        # Refuse bodies must not leak secrets.
        combined = str(resp_body)
        self.assertNotIn(DEMO_BOT_SECRET, combined)
        self.assertNotIn("fixture-token", combined)

    def test_request_body_identity_preserved_in_raw_inbound(self) -> None:
        body = b'{"op":0,"t":"C2C_MESSAGE_CREATE","d":{"id":"x"}}'
        headers = {
            "X-Signature-Ed25519": "ab" * 64,
            "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
        }
        raw = build_raw_inbound_from_http(
            headers,
            body,
            bot_secret=DEMO_BOT_SECRET,
            payload_ref="fixture://qqbot/inbound/body-identity",
            received_at="2026-07-10T00:00:00Z",
        )
        self.assertIs(raw.metadata["request_body"], body)
        self.assertEqual(raw.metadata["request_body"], body)

    def test_non_post_returns_405(self) -> None:
        wired, _transport = _enabled_wired()
        status, _body, _headers = run(
            handle_qqbot_webhook_request(
                "GET",
                CALLBACK_PATH,
                {},
                b"",
                wired=wired,
                env=SECRET_ENV,
            )
        )
        self.assertEqual(status, 405)

    def test_unknown_path_returns_404(self) -> None:
        wired, _transport = _enabled_wired()
        status, _body, _headers = run(
            handle_qqbot_webhook_request(
                "POST",
                "/other",
                {},
                b"{}",
                wired=wired,
                env=SECRET_ENV,
            )
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
