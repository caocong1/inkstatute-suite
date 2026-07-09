"""Wave 0 / Plan 01→03: RECALL-01 is_wakeup period gate + mutual exclusion.

Plan 01 scaffolds RED coverage. Plan 03 greens TestWakeupEnvelope /
TestWakeupPeriodGate (Task 1) and TestWakeupAdapterDeliver (Task 2).
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any


def run(coro):
    return asyncio.run(coro)


def _assert_no_privacy_leak(self: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        self.assertNotIn("raw_payload", value)
        self.assertNotIn("Authorization", value)
        for key, child in value.items():
            key_l = str(key).lower()
            self.assertNotIn("token", key_l)
            self.assertNotIn("authorization", key_l)
            _assert_no_privacy_leak(self, child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_privacy_leak(self, child)


class TestWakeupEnvelope(unittest.TestCase):
    """RECALL-01: wakeup wire body has is_wakeup and omits msg_id/event_id."""

    def test_recall01_wakeup_text_envelope_mutual_exclusion(self) -> None:
        try:
            from inkstatute_channels_qqbot.sender import build_wakeup_text_envelope
        except ImportError:
            self.fail("RECALL-01: build_wakeup_text_envelope not implemented (Plan 03)")

        envelope = build_wakeup_text_envelope(content="long task complete")
        self.assertTrue(envelope.get("is_wakeup"))
        self.assertNotIn("msg_id", envelope)
        self.assertNotIn("event_id", envelope)
        self.assertNotIn("msg_seq", envelope)
        _assert_no_privacy_leak(self, envelope)

    def test_recall01_wakeup_strip_for_wire_keeps_mutual_exclusion(self) -> None:
        try:
            from inkstatute_channels_qqbot.sender import (
                build_wakeup_text_envelope,
                strip_for_wire,
            )
        except ImportError:
            self.fail("RECALL-01: wakeup strip helpers not implemented (Plan 03)")

        envelope = build_wakeup_text_envelope(content="long task complete")
        wire = strip_for_wire(envelope)
        self.assertTrue(wire.get("is_wakeup"))
        self.assertNotIn("msg_id", wire)
        self.assertNotIn("event_id", wire)


class TestWakeupPeriodGate(unittest.TestCase):
    """RECALL-01: 30-day periods, 1 send per (openid, period); C2C-only helper."""

    def test_recall01_second_send_same_period_fails(self) -> None:
        try:
            from inkstatute_channels_qqbot.sender import (
                InMemoryWakeupPeriodStore,
                check_wakeup_quota,
            )
        except ImportError:
            self.fail("RECALL-01: wakeup period gate not implemented (Plan 03)")

        clock = {"now": datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)}

        def now_fn() -> datetime:
            return clock["now"]

        store = InMemoryWakeupPeriodStore()
        openid = "FIXTURE_USER_WAKEUP_001"
        t0 = datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc)
        store.note_user_message(openid, t0)

        first = check_wakeup_quota(openid, store=store, now=now_fn)
        self.assertTrue(first.ok, msg=getattr(first, "issue_code", first))
        store.record_send(openid, first.period_id)

        second = check_wakeup_quota(openid, store=store, now=now_fn)
        self.assertFalse(second.ok)
        self.assertIn("quota", str(second.issue_code).lower())

    def test_recall01_group_wakeup_unsupported_helper(self) -> None:
        try:
            from inkstatute_channels_qqbot.sender import wakeup_scene_supported
        except ImportError:
            self.fail(
                "RECALL-01: wakeup_scene_supported helper not implemented (Plan 03)"
            )

        self.assertFalse(wakeup_scene_supported("group"))
        self.assertTrue(wakeup_scene_supported("c2c"))


class TestWakeupAdapterDeliver(unittest.TestCase):
    """RECALL-01: adapter.deliver Fake transport wakeup path (Plan 03 Task 2)."""

    def test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire(self) -> None:
        from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
        from platform_runtime.protocols import ChannelDelivery

        transport = FakeMessageTransport(response={"id": "wakeup-msg-001"})
        token_manager = TokenManager(
            app_id="fixture-app",
            client_secret="fixture-secret",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-access-token", "expires_in": 7200}
            ),
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=token_manager,
            transport=transport,
        )

        # Over-window: msg_id present but passive window expired; allow_wakeup set.
        # Plan 03 wires the wakeup deliver branch — until then this stays RED.
        delivery = ChannelDelivery(
            delivery_id="delivery-wakeup-001",
            channel_id="qqbot",
            run_id="run-wakeup-001",
            content="long task complete",
            metadata={
                "scene": "c2c",
                "user_openid": "FIXTURE_USER_WAKEUP_001",
                "msg_id": "FIXTURE_EXPIRED_MSG_ID",
                "received_at": "2026-01-01T00:00:00Z",
                "reply_count": 0,
                "allow_wakeup": True,
                "is_wakeup": True,
            },
        )

        result = run(adapter.deliver(delivery))
        posts = [
            c
            for c in transport.calls
            if "/messages" in str(c.get("url") or "")
            and c.get("method") in (None, "POST")
        ]
        self.assertTrue(
            posts,
            msg="RECALL-01: expected wakeup POST to /messages (Plan 03 Task 2)",
        )
        body: dict[str, Any] = posts[0].get("json") or posts[0].get("body") or {}
        if not isinstance(body, dict):
            self.fail("RECALL-01: wakeup body must be structured JSON dict")
        self.assertTrue(body.get("is_wakeup"))
        self.assertNotIn("msg_id", body)
        self.assertNotIn("event_id", body)
        _assert_no_privacy_leak(self, result.metadata or {})

    def test_recall01_group_wakeup_unsupported_scene(self) -> None:
        from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
        from platform_runtime.protocols import ChannelDelivery

        transport = FakeMessageTransport(response={"id": "should-not-send"})
        token_manager = TokenManager(
            app_id="fixture-app",
            client_secret="fixture-secret",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-access-token", "expires_in": 7200}
            ),
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=token_manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-wakeup-group-001",
            channel_id="qqbot",
            run_id="run-wakeup-group-001",
            content="long task complete",
            metadata={
                "scene": "group",
                "group_openid": "FIXTURE_GROUP_001",
                "msg_id": "FIXTURE_EXPIRED_MSG_ID",
                "received_at": "2026-01-01T00:00:00Z",
                "reply_count": 0,
                "allow_wakeup": True,
            },
        )
        result = run(adapter.deliver(delivery))
        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata.get("issue_code"), "qqbot_wakeup_unsupported_scene"
        )
        self.assertTrue(result.metadata.get("interim_notice"))
        self.assertEqual(transport.call_count, 0)

    def test_recall01_passive_expiry_without_wakeup_unchanged(self) -> None:
        from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
        from platform_runtime.protocols import ChannelDelivery

        transport = FakeMessageTransport(response={"id": "should-not-send"})
        token_manager = TokenManager(
            app_id="fixture-app",
            client_secret="fixture-secret",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-access-token", "expires_in": 7200}
            ),
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=token_manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-expired-001",
            channel_id="qqbot",
            run_id="run-expired-001",
            content="late reply",
            metadata={
                "scene": "c2c",
                "user_openid": "FIXTURE_USER_001",
                "msg_id": "FIXTURE_EXPIRED_MSG_ID",
                "received_at": "2026-01-01T00:00:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))
        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata.get("issue_code"), "qqbot_passive_reply_window_expired"
        )
        self.assertTrue(result.metadata.get("interim_notice"))
        self.assertEqual(transport.call_count, 0)


if __name__ == "__main__":
    unittest.main()
