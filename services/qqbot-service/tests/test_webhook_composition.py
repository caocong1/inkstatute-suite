"""HOST-01: Fake composition path proofs (Phase 70 Plan 02).

verify_and_ack → ingress/feedback → output_boundary → deliver.
Fake transports only — zero live QQ network.
"""

from __future__ import annotations

import ast
import asyncio
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
from platform_runtime.output_boundary import BoundaryAction
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_wired_runtime
from qqbot_service.webhook import handle_qqbot_webhook_request

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
HOST_SRC = Path(__file__).resolve().parents[1] / "src" / "qqbot_service"
SECRET_ENV = {
    "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
    "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
    "INKSTATUTE_QQBOT_BOT_SECRET": DEMO_BOT_SECRET,
}
# Keep inside C2C (1h) and group (5m) passive-reply windows relative to wall clock.
FIXED_NOW = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)
FIXTURE_REPLY = "根据相关裁判观点，合同解除需审查约定解除与法定解除要件。"


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


def _enabled_wired(
    *,
    backend: FakeBackendAdapter | None = None,
    message_transport: FakeMessageTransport | None = None,
) -> tuple[Any, FakeBackendAdapter, FakeMessageTransport]:
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    transport = message_transport or FakeMessageTransport(
        response={"id": "msg-comp-ok", "status": 200}
    )
    backend = backend or FakeBackendAdapter()
    wired = build_qqbot_wired_runtime(
        backend=backend,
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
    return wired, backend, transport


class RecordingScheduler:
    def __init__(self) -> None:
        self.thunks: list[Callable[[], Any]] = []

    def __call__(self, thunk: Callable[[], Any]) -> None:
        self.thunks.append(thunk)

    def run_all(self) -> None:
        for thunk in list(self.thunks):
            result = thunk()
            if asyncio.iscoroutine(result):
                asyncio.run(result)


class WebhookCompositionTests(unittest.TestCase):
    """HOST-01 Fake composition: message + feedback + boundary + refuse."""

    def test_message_path_ack_then_ingress_and_deliver(self) -> None:
        wired, backend, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()
        feedback_sink: list[dict[str, Any]] = []

        status, resp_body, _ = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                reply_text=FIXTURE_REPLY,
                feedback_sink=feedback_sink,
                tenant_id="tenant-fixture",
                workspace_id="ws-fixture",
                bot_instance_id="bot-fixture",
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp_body), {"op": 12})
        self.assertEqual(len(scheduler.thunks), 1)
        self.assertEqual(len(backend.submitted_requests), 0)
        self.assertEqual(transport.call_count, 0)

        scheduler.run_all()

        self.assertGreaterEqual(len(backend.submitted_requests), 1)
        self.assertGreaterEqual(transport.call_count, 1)
        self.assertGreaterEqual(len(wired.adapter.deliveries), 1)
        delivery = wired.adapter.deliveries[-1]
        self.assertEqual(delivery.content, FIXTURE_REPLY)
        # Privacy: no secrets in delivery metadata
        meta_blob = json.dumps(delivery.metadata, ensure_ascii=False)
        self.assertNotIn(DEMO_BOT_SECRET, meta_blob)
        self.assertNotIn("fixture-token", meta_blob)
        self.assertNotIn("Authorization", meta_blob)

    def test_group_at_message_delivery_metadata_maps_openids(self) -> None:
        """CR-01: group scene_id → group_openid; member openid stays user_openid."""
        wired, backend, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_group_at_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()

        status, resp_body, _ = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                reply_text=FIXTURE_REPLY,
                tenant_id="tenant-fixture",
                workspace_id="ws-fixture",
                bot_instance_id="bot-fixture",
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp_body), {"op": 12})
        scheduler.run_all()

        self.assertGreaterEqual(len(backend.submitted_requests), 1)
        self.assertGreaterEqual(transport.call_count, 1)
        self.assertGreaterEqual(len(wired.adapter.deliveries), 1)
        delivery = wired.adapter.deliveries[-1]
        self.assertEqual(delivery.metadata.get("scene"), "group")
        self.assertEqual(
            delivery.metadata.get("group_openid"), "FIXTURE_GROUP_OPENID_001"
        )
        self.assertEqual(
            delivery.metadata.get("user_openid"), "FIXTURE_MEMBER_OPENID_001"
        )
        # Must not put group openid into the C2C user_openid slot.
        self.assertNotEqual(
            delivery.metadata.get("user_openid"),
            delivery.metadata.get("group_openid"),
        )
        # Wire URL must target the group endpoint, not the member as a C2C user.
        last_url = transport.calls[-1].get("url") or ""
        self.assertIn("/v2/groups/FIXTURE_GROUP_OPENID_001/messages", last_url)
        self.assertNotIn("/v2/users/FIXTURE_GROUP_OPENID_001/", last_url)

    def test_interaction_feedback_path_without_message_ingress(self) -> None:
        wired, backend, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_interaction_create.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()
        feedback_sink: list[dict[str, Any]] = []

        status, resp_body, _ = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                feedback_sink=feedback_sink,
                tenant_id="tenant-fixture",
                workspace_id="ws-fixture",
                bot_instance_id="bot-fixture",
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp_body), {"op": 12})
        scheduler.run_all()

        self.assertEqual(len(backend.submitted_requests), 0)
        self.assertTrue(feedback_sink)
        evidence = feedback_sink[-1]
        self.assertEqual(evidence.get("status"), "normalized")
        self.assertIn("feedback_dict", evidence)

    def test_output_boundary_blocks_meta_text_from_deliver(self) -> None:
        wired, backend, transport = _enabled_wired()
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()
        meta_text = "Hermes gateway reconnecting — tool progress: internal retrieval"

        status, _, _ = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                reply_text=meta_text,
                tenant_id="tenant-fixture",
                workspace_id="ws-fixture",
                bot_instance_id="bot-fixture",
            )
        )
        self.assertEqual(status, 200)
        scheduler.run_all()

        # Ingress still ran
        self.assertGreaterEqual(len(backend.submitted_requests), 1)
        # Boundary must not allow raw meta markers onto the wire
        for call in transport.calls:
            body_blob = json.dumps(call.get("body") or {}, ensure_ascii=False)
            self.assertNotIn("Hermes gateway", body_blob)
            self.assertNotIn("tool progress", body_blob)
            self.assertNotIn("internal retrieval", body_blob)
        for delivery in wired.adapter.deliveries:
            content = delivery.content or ""
            self.assertNotIn("Hermes gateway", content)
            self.assertNotIn("tool progress", content)
        # Decision must be block or rewrite (not allow raw)
        decision = wired.runtime.output_boundary.apply("ordinary_user", meta_text)
        self.assertIn(decision.action, {BoundaryAction.BLOCK, BoundaryAction.REWRITE})

    def test_host_modules_do_not_reimplement_package_crypto_or_normalize(self) -> None:
        forbidden = {
            "derive_keypair",
            "normalize_message_event",
            "strip_for_wire",
            "handle_validation_challenge",
        }
        offenders: list[str] = []
        for path in sorted(HOST_SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in forbidden:
                    offenders.append(f"{path.name}:{node.name}")
                if isinstance(node, ast.AsyncFunctionDef) and node.name in forbidden:
                    offenders.append(f"{path.name}:{node.name}")
        self.assertEqual(offenders, [])

    def test_disabled_path_still_503_never_delivers(self) -> None:
        transport = FakeMessageTransport(response={"id": "x", "status": 200})
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=False),
            host_config=QQBotHostConfig(
                enabled=True,
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            env=SECRET_ENV,
            transport=transport,
        )
        envelope = _load_envelope("qqbot_c2c_message.json")
        headers, body = _signed_http(envelope)
        scheduler = RecordingScheduler()

        status, _, _ = run(
            handle_qqbot_webhook_request(
                "POST",
                CALLBACK_PATH,
                headers,
                body,
                wired=wired,
                env=SECRET_ENV,
                post_ack_scheduler=scheduler,
                received_at=FIXED_NOW,
                reply_text=FIXTURE_REPLY,
            )
        )

        self.assertEqual(status, 503)
        self.assertEqual(scheduler.thunks, [])
        self.assertEqual(transport.call_count, 0)
        self.assertEqual(wired.adapter.deliveries, [])


if __name__ == "__main__":
    unittest.main()
