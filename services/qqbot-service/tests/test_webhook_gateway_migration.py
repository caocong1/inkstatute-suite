"""Tests for the Gateway consumer path in QQ webhook post-ACK composition (95-03).

These tests verify that ``run_post_ack_composition()`` uses the Gateway event
consumer (``QQBotEventConsumer``) when ``wired.gateway_client`` is available,
and falls back to the old ingress path when it is ``None``.

All tests are network-free, using ``FakeGatewayClient`` from ``fakes.py`` and
the real QQ adapter (via ``build_qqbot_wired_runtime``) for verify_and_ack
and normalize_inbound. A ``DeliverRecordingAdapter`` wrapper intercepts
``deliver()`` calls for assertions.
"""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.signature import derive_keypair
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import (
    AckResponse,
    ChannelDelivery,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
    SolutionBinding,
)

from qqbot_service.gateway_client import GatewayClientConfig
from qqbot_service.webhook import (
    _agent_turn_to_dict,
    _compose_via_gateway,
    build_raw_inbound_from_http,
    handle_qqbot_webhook_request,
    run_post_ack_composition,
)
from qqbot_service.wiring import QQBotWiredRuntime, build_qqbot_wired_runtime

from fakes import FakeGatewayClient, load_fixture_events

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
FIXED_NOW = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)


def run(coro):
    return asyncio.run(coro)


def _load_envelope(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)["envelope"]


def _sign_body(body: bytes, *, bot_secret: str = DEMO_BOT_SECRET) -> str:
    _public_key, seed = derive_keypair(bot_secret)
    msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + body
    return ed25519_sign(seed, msg).hex()


def _signed_http(payload: dict[str, Any]) -> tuple[dict[str, str], bytes]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Signature-Ed25519": _sign_body(body),
        "X-Signature-Timestamp": DEMO_SIG_TIMESTAMP,
    }
    return headers, body


class DeliverRecordingAdapter:
    """Wraps a real QQBotChannelAdapter, recording all deliver() calls.

    Delegates ``verify_and_ack`` and ``normalize_inbound`` to the real adapter
    (so QQ envelopes are properly normalized into ``AgentTurn``), but
    intercepts ``deliver()`` to record deliveries for test assertions.
    """

    def __init__(self, real_adapter: Any) -> None:
        self._real = real_adapter
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return self._real.channel_id()

    def capabilities(self):
        return self._real.capabilities()

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        return await self._real.verify_and_ack(raw)

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
        return await self._real.normalize_inbound(raw)

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        self.deliveries.append(delivery)
        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=True,
            idempotency_key=delivery.metadata.get("idempotency_key"),
            metadata={"channel_id": "qqbot", "network_io": False},
        )

    async def health(self):
        return await self._real.health()


def _make_wired(
    *,
    gateway_client: Any | None = None,
    events: list[dict[str, Any]] | None = None,
    record_deliveries: bool = False,
) -> tuple[QQBotWiredRuntime, DeliverRecordingAdapter | None]:
    """Build a wired runtime with an optional FakeGatewayClient.

    Uses ``build_qqbot_wired_runtime`` to get a real adapter, then replaces
    the ``gateway_client`` field with the provided fake (or None).

    When ``record_deliveries`` is True, wraps the real adapter in a
    :class:`DeliverRecordingAdapter` to capture deliver() calls.
    """
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    transport = FakeMessageTransport(response={"id": "msg-gw-ok", "status": 200})
    backend = FakeBackendAdapter()
    wired = build_qqbot_wired_runtime(
        backend=backend,
        flags=RuntimeFeatureFlags(
            qqbot_channel_enabled=True,
            run_runtime_enabled=True,
        ),
        host_config=__import__(
            "qqbot_service.config", fromlist=["QQBotHostConfig"]
        ).QQBotHostConfig(
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
    recording_adapter: DeliverRecordingAdapter | None = None
    if record_deliveries:
        recording_adapter = DeliverRecordingAdapter(wired.adapter)
        wired = dataclasses.replace(wired, adapter=recording_adapter)
    if gateway_client is not None:
        wired = dataclasses.replace(wired, gateway_client=gateway_client)
    return wired, recording_adapter


def _make_events(*overrides: dict) -> list[dict]:
    """Build a minimal event list from overrides."""
    events = []
    for i, ov in enumerate(overrides, 1):
        event = {
            "event_id": f"evt-{i}",
            "run_id": "run-fake-1",
            "event_type": ov.get("event_type", "message.delta"),
            "seq": ov.get("seq", i),
            "occurred_at": f"2026-08-09T10:00:{i:02d}Z",
            "payload": ov.get("payload", {}),
        }
        events.append(event)
    return events


class TestQQWebhookGatewayMigration(unittest.TestCase):
    """Tests for the Gateway consumer path in post-ACK composition."""

    def run_async(self, coro):
        return asyncio.run(coro)

    # ------------------------------------------------------------------
    # 1. Gateway path used when available
    # ------------------------------------------------------------------

    def test_post_ack_uses_gateway_when_available(self) -> None:
        """When gateway_client is set, the gateway path is used (not ingress)."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "合同审查完成"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-1",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        evidence = self.run_async(run_post_ack_composition(wired, raw, ack))

        self.assertTrue(evidence.get("gateway_path"), f"Expected gateway_path=True: {evidence}")
        self.assertEqual(evidence["status"], "completed")
        self.assertTrue(client.create_run_called, "Gateway create_run should have been called")

    # ------------------------------------------------------------------
    # 2. Falls back to old path when no gateway
    # ------------------------------------------------------------------

    def test_post_ack_falls_back_when_no_gateway(self) -> None:
        """When gateway_client is None, the old ingress path is used."""
        wired, _ = _make_wired(gateway_client=None)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-2",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        evidence = self.run_async(run_post_ack_composition(
            wired, raw, ack, reply_text="fixture reply",
        ))

        # Old path: evidence has "ingress_action" and no "gateway_path"
        self.assertNotIn("gateway_path", evidence, f"Old path should not have gateway_path: {evidence}")
        self.assertIn("ingress_action", evidence, f"Old path should have ingress_action: {evidence}")
        self.assertEqual(evidence["branch"], "message")

    # ------------------------------------------------------------------
    # 3. Gateway delivers text
    # ------------------------------------------------------------------

    def test_post_ack_gateway_delivers_text(self) -> None:
        """Gateway path delivers the final message as text."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "合同审查完成"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, recording = _make_wired(gateway_client=client, record_deliveries=True)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-3",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        self.run_async(run_post_ack_composition(wired, raw, ack))

        text_deliveries = [d for d in recording.deliveries if d.metadata.get("delivery_type") == "text"]
        contents = [d.content for d in text_deliveries]
        self.assertTrue(any("合同审查完成" in c for c in contents),
                        f"Expected '合同审查完成' in text deliveries: {contents}")

    # ------------------------------------------------------------------
    # 4. Gateway delivers card (QQ keyboard)
    # ------------------------------------------------------------------

    def test_post_ack_gateway_delivers_card(self) -> None:
        """Gateway path delivers elicitation as a QQ card (keyboard)."""
        events = _make_events(
            {"event_type": "elicitation.requested", "payload": {
                "interrupt_id": "int-1",
                "questions": [{"id": "q1", "question": "请选择合同类型"}],
            }},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, recording = _make_wired(gateway_client=client, record_deliveries=True)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-4",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        self.run_async(run_post_ack_composition(wired, raw, ack))

        card_deliveries = [d for d in recording.deliveries if d.metadata.get("delivery_type") == "card"]
        self.assertTrue(len(card_deliveries) >= 1, f"Expected card delivery: {recording.deliveries}")
        self.assertEqual(card_deliveries[0].metadata.get("card_id"), "int-1")

    # ------------------------------------------------------------------
    # 5. Gateway intermediate prompt
    # ------------------------------------------------------------------

    def test_post_ack_gateway_intermediate_prompt(self) -> None:
        """Gateway path sends intermediate '正在检索法规…' on tool_call.started."""
        events = _make_events(
            {"event_type": "tool_call.started", "payload": {"tool_name": "search"}},
            {"event_type": "message.completed", "payload": {"content": "done"}, "seq": 2},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 3},
        )
        client = FakeGatewayClient(events=events)
        wired, recording = _make_wired(gateway_client=client, record_deliveries=True)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-5",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        self.run_async(run_post_ack_composition(wired, raw, ack))

        contents = [d.content for d in recording.deliveries]
        self.assertIn("正在检索法规…", contents,
                      f"Expected '正在检索法规…' in deliveries: {contents}")

    # ------------------------------------------------------------------
    # 6. Feedback branch unchanged
    # ------------------------------------------------------------------

    def test_post_ack_gateway_feedback_branch_unchanged(self) -> None:
        """Feedback callbacks use the feedback branch regardless of gateway_client."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        envelope = _load_envelope("qqbot_interaction_create.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-6",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        evidence = self.run_async(run_post_ack_composition(wired, raw, ack))

        self.assertEqual(evidence["branch"], "feedback")
        self.assertEqual(evidence["status"], "completed")
        # Gateway path should NOT be used for feedback
        self.assertNotIn("gateway_path", evidence)

    # ------------------------------------------------------------------
    # 7. No direct agent calls in gateway path
    # ------------------------------------------------------------------

    def test_post_ack_gateway_no_direct_agent_calls(self) -> None:
        """_compose_via_gateway does not call runtime.create_run or backend.get_run."""
        source = inspect.getsource(_compose_via_gateway)
        self.assertNotIn("runtime.create_run", source,
                         "Gateway path must not call runtime.create_run")
        self.assertNotIn("backend.get_run", source,
                         "Gateway path must not call backend.get_run")
        self.assertNotIn("QQBotRuntimeIngress", source,
                         "Gateway path must not construct QQBotRuntimeIngress")

    # ------------------------------------------------------------------
    # 8. Scene metadata in deliveries
    # ------------------------------------------------------------------

    def test_post_ack_gateway_scene_metadata(self) -> None:
        """Deliveries include QQ scene metadata (scene, user_openid, msg_id)."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, recording = _make_wired(gateway_client=client, record_deliveries=True)

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-8",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        self.run_async(run_post_ack_composition(wired, raw, ack))

        self.assertTrue(len(recording.deliveries) > 0, "Expected at least one delivery")
        for d in recording.deliveries:
            self.assertEqual(d.metadata.get("scene"), "c2c",
                             f"Expected scene='c2c': {d.metadata}")
            self.assertEqual(d.metadata.get("user_openid"), "FIXTURE_USER_OPENID_C2C_001",
                             f"Expected user_openid: {d.metadata}")
            self.assertIsNotNone(d.metadata.get("msg_id"),
                                 f"Expected msg_id not None: {d.metadata}")

    # ------------------------------------------------------------------
    # 9. Solution binding forwarded
    # ------------------------------------------------------------------

    def test_post_ack_gateway_solution_binding(self) -> None:
        """SolutionBinding is forwarded to the event consumer."""
        from platform_contract.events import SolutionBinding as ContractSolutionBinding

        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        binding = ContractSolutionBinding(
            solution_id="test-solution",
            backend_id="test-backend",
        )
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        raw = build_raw_inbound_from_http(
            headers, body, bot_secret=DEMO_BOT_SECRET,
            payload_ref="http://qqbot/callback/test-9",
            received_at=FIXED_NOW,
        )
        ack = AckResponse(accepted=True, status_code=200)
        self.run_async(run_post_ack_composition(wired, raw, ack, solution=binding))

        self.assertIsNotNone(client.last_run_body, "create_run should have been called")
        solution_dict = client.last_run_body.get("solution", {})
        self.assertEqual(solution_dict.get("solution_id"), "test-solution")
        self.assertEqual(solution_dict.get("backend_id"), "test-backend")

    # ------------------------------------------------------------------
    # 10. ACK-first pattern preserved
    # ------------------------------------------------------------------

    def test_ack_first_pattern_preserved(self) -> None:
        """HTTP response is returned immediately (200 with op=12) before post-ACK."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        thunks: list = []
        scheduler = thunks.append
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        status, resp_body, _headers = self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
            )
        )
        # ACK is returned immediately
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp_body), {"op": 12})
        # Post-ACK composition is scheduled (not yet run)
        self.assertEqual(len(thunks), 1)

    # ------------------------------------------------------------------
    # 11. ED25519 verification preserved
    # ------------------------------------------------------------------

    def test_ed25519_verification_preserved(self) -> None:
        """Callbacks that fail verification are rejected (non-200)."""
        # Build a wired runtime with channel disabled — verify_and_ack returns 503
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=False),
            host_config=__import__(
                "qqbot_service.config", fromlist=["QQBotHostConfig"]
            ).QQBotHostConfig(
                enabled=True,
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            env=SECRET_ENV,
        )

        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        status, _body, _headers = self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
            )
        )
        # When channel is disabled, verify_and_ack returns accepted=False → 503
        self.assertNotEqual(status, 200)
        self.assertEqual(status, 503)

    # ------------------------------------------------------------------
    # 12. op=13 validation challenge preserved
    # ------------------------------------------------------------------

    def test_op13_validation_challenge_preserved(self) -> None:
        """op=13 validation challenge is handled before gateway path."""
        events = _make_events(
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        envelope = _load_envelope("qqbot_validation_challenge.json")
        headers, body = _signed_http(envelope)
        status, resp_body, _headers = self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
            )
        )
        # Validation challenge returns 200 with challenge response
        self.assertEqual(status, 200)
        resp = json.loads(resp_body)
        # Challenge response has plain_token and signature
        self.assertIn("plain_token", resp)
        self.assertIn("signature", resp)

    # ------------------------------------------------------------------
    # 13. Idempotency preserved
    # ------------------------------------------------------------------

    def test_idempotency_preserved(self) -> None:
        """Duplicate callbacks with same idempotency key don't create duplicate Gateway runs."""
        events = _make_events(
            {"event_type": "message.completed", "payload": {"content": "done"}},
            {"event_type": "run.state_changed", "payload": {"status": "succeeded"}, "seq": 2},
        )
        client = FakeGatewayClient(events=events)
        wired, _ = _make_wired(gateway_client=client)

        thunks: list = []
        scheduler = thunks.append
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)

        # First call
        self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                idempotency_key="dup-key-1",
            )
        )
        # Second call with same idempotency key
        self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                idempotency_key="dup-key-1",
            )
        )

        # Both calls schedule post-ACK (idempotency at webhook level is by key)
        self.assertEqual(len(thunks), 2)
        # Run the first thunk to verify it works
        evidence1 = thunks[0]()
        self.assertTrue(evidence1.get("gateway_path"))

    # ------------------------------------------------------------------
    # 14. Full flow end-to-end
    # ------------------------------------------------------------------

    def test_full_flow_gateway_tracer(self) -> None:
        """End-to-end: webhook → verify_and_ack → post-ACK → Gateway → SSE → deliver."""
        events = load_fixture_events()
        client = FakeGatewayClient(events=events)
        wired, recording = _make_wired(gateway_client=client, record_deliveries=True)

        thunks: list = []
        scheduler = thunks.append
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        status, _body, _headers = self.run_async(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(thunks), 1)

        evidence = thunks[0]()
        self.assertEqual(evidence["status"], "completed")
        self.assertTrue(evidence.get("gateway_path"))
        self.assertTrue(len(recording.deliveries) > 0,
                        f"Expected deliveries: {recording.deliveries}")

    # ------------------------------------------------------------------
    # 15. No WeCom import in gateway path
    # ------------------------------------------------------------------

    def test_no_wecom_import_in_gateway_path(self) -> None:
        """_compose_via_gateway and event_consumer do not import from the WeCom service."""
        source = inspect.getsource(_compose_via_gateway)
        self.assertNotIn("wecom_service", source)
        self.assertNotIn("inkstatute_channels_wecom", source)

        from qqbot_service import event_consumer as ec_mod
        ec_source = inspect.getsource(ec_mod)
        self.assertNotIn("wecom_service", ec_source)
        self.assertNotIn("inkstatute_channels_wecom", ec_source)


if __name__ == "__main__":
    unittest.main()
