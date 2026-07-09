"""Wave 0 / Plan 01: INGRESS-06 two-tier ACK coverage.

Tier 1: verified dispatch AckResponse.metadata.http_callback_ack_body={"op": 12}
Tier 2: INTERACTION_CREATE live PUT /interactions/{id} with {"code": 0}
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.signature import derive_keypair
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.protocols import RawInbound

from packages.channels.qqbot.tests.test_signature import DEMO_BOT_SECRET, DEMO_SIG_TIMESTAMP

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
INTERACTION_ID = "FIXTURE_INTERACTION_ID_001"


def run(coro):
    return asyncio.run(coro)


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def make_signed_raw(
    *,
    payload: dict,
    bot_secret: str = DEMO_BOT_SECRET,
    idempotency_key: str | None = "qqbot-ack-idem-1",
) -> RawInbound:
    """Sign payload JSON bytes with Ed25519 (reuse Phase 59 demo secret)."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _public_key, seed = derive_keypair(bot_secret)
    msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + body
    sig_hex = ed25519_sign(seed, msg).hex()
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/two-tier-ack",
        received_at="2026-07-09T00:00:00Z",
        idempotency_key=idempotency_key,
        metadata={
            "x_signature_ed25519": sig_hex,
            "x_signature_timestamp": DEMO_SIG_TIMESTAMP,
            "request_body": body,
            "bot_secret": bot_secret,
            "payload": payload,
        },
    )


def _put_calls(transport: FakeMessageTransport) -> list[dict]:
    """Return recorded PUT calls (method tag or URL path heuristic)."""
    puts: list[dict] = []
    for call in transport.calls:
        method = call.get("method")
        url = str(call.get("url") or "")
        if method == "PUT" or "/interactions/" in url:
            puts.append(call)
    return puts


class TwoTierAckTests(unittest.TestCase):
    """INGRESS-06: op=12 webhook body + interaction PUT behind live gate."""

    def test_verified_message_ack_includes_op12_body(self) -> None:
        """Signed C2C dispatch → 200 with http_callback_ack_body op=12."""
        envelope = _load_fixture("qqbot_c2c_message.json")["envelope"]
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True, bot_secret_ref="ref://qqbot/bot-secret")
        )
        ack = run(adapter.verify_and_ack(make_signed_raw(payload=envelope)))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata.get("http_callback_ack_body"), {"op": 12})
        ack_tier = str(ack.metadata.get("ack_tier") or "")
        self.assertIn("webhook_op12", ack_tier)
        self.assertFalse(ack.metadata.get("network_io"))

    def test_interaction_live_put_ack(self) -> None:
        """Live INTERACTION_CREATE performs PUT /interactions/{id} {"code":0}."""
        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        transport = FakeMessageTransport(response={"code": 0})
        token_manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-client-secret",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True, bot_secret_ref="ref://qqbot/bot-secret"),
            token_manager=token_manager,
            transport=transport,
        )
        ack = run(adapter.verify_and_ack(make_signed_raw(payload=envelope)))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata.get("http_callback_ack_body"), {"op": 12})
        self.assertTrue(ack.metadata.get("interaction_ack_required"))
        self.assertEqual(ack.metadata.get("interaction_ack_status"), "sent")
        self.assertEqual(ack.metadata.get("interaction_id"), INTERACTION_ID)
        self.assertNotIn("Authorization", ack.metadata)
        self.assertNotIn("access_token", ack.metadata)
        meta_blob = json.dumps(ack.metadata, default=str)
        self.assertNotIn("fixture-token", meta_blob)

        puts = _put_calls(transport)
        self.assertEqual(len(puts), 1)
        put = puts[0]
        self.assertTrue(str(put["url"]).endswith(f"/interactions/{INTERACTION_ID}"))
        self.assertEqual(put["body"], {"code": 0})

    def test_flag_off_skips_interaction_put(self) -> None:
        """enabled=False → 503 and zero PUT calls on Fake transport."""
        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        transport = FakeMessageTransport(response={"code": 0})
        token_manager = TokenManager(
            app_id="fixture-app-id",
            client_secret="fixture-client-secret",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=False, bot_secret_ref="ref://qqbot/bot-secret"),
            token_manager=token_manager,
            transport=transport,
        )
        ack = run(adapter.verify_and_ack(make_signed_raw(payload=envelope)))
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)
        self.assertEqual(len(_put_calls(transport)), 0)
        self.assertEqual(transport.call_count, 0)

    def test_enabled_without_transport_skips_put_but_emits_metadata(self) -> None:
        """Verified interaction without transport: op=12 + pending/skipped, no PUT."""
        envelope = _load_fixture("qqbot_interaction_create.json")["envelope"]
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True, bot_secret_ref="ref://qqbot/bot-secret")
        )
        ack = run(adapter.verify_and_ack(make_signed_raw(payload=envelope)))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata.get("http_callback_ack_body"), {"op": 12})
        self.assertTrue(ack.metadata.get("interaction_ack_required"))
        self.assertIn(
            ack.metadata.get("interaction_ack_status"),
            {"pending_host", "skipped_fixture"},
        )
        self.assertFalse(ack.metadata.get("network_io"))


if __name__ == "__main__":
    unittest.main()
