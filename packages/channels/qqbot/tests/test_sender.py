"""Unit tests for QQ egress envelope builders, passive-reply window, and send retry."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from inkstatute_channels_qqbot.sender import (
    FEEDBACK_ACTIONS,
    FakeMessageTransport,
    SendError,
    _rich_media_evidence,
    build_feedback_keyboard_envelope,
    build_markdown_envelope,
    build_media_envelope,
    build_text_envelope,
    check_passive_reply_window,
    send_message,
    send_rich_media,
    strip_for_wire,
    upload_rich_media,
    wire_files_url_for_scene,
    wire_url_for_scene,
)
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenError, TokenManager

LEGAL_CONTENT = "根据《民法典》……"
BLOCKED_NOTICE = "ADMIN_NOTICE: delivery debug stack trace token=secret"
FIXTURE_APP_ID = "fixture-app-id-001"
FIXTURE_CLIENT_SECRET = "fixture-client-secret-001"
ISSUE_WINDOW_EXPIRED = "qqbot_passive_reply_window_expired"
SECRET_TOKEN = "secret-token-value-xyz"


def _fixed_clock(now: datetime):
    return lambda: now


async def _noop_sleep(_seconds: float) -> None:
    return None


class SenderEnvelopeTests(unittest.TestCase):
    def test_feedback_actions_canonical_order(self) -> None:
        self.assertEqual(
            tuple(FEEDBACK_ACTIONS),
            ("up", "down", "needs_fix", "route_wrong"),
        )

    def test_build_text_envelope_msg_type_0_with_msg_id_seq(self) -> None:
        envelope = build_text_envelope(
            content=LEGAL_CONTENT,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 0)
        self.assertEqual(envelope["content"], LEGAL_CONTENT)
        self.assertEqual(envelope["msg_id"], "inbound-1")
        self.assertEqual(envelope["msg_seq"], 1)
        self.assertEqual(envelope["policy"]["action"], "allow")

    def test_build_markdown_envelope_msg_type_2(self) -> None:
        envelope = build_markdown_envelope(
            content=LEGAL_CONTENT,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 2)
        self.assertEqual(envelope["markdown"], {"content": LEGAL_CONTENT})
        self.assertEqual(envelope["msg_id"], "inbound-1")
        self.assertEqual(envelope["msg_seq"], 1)
        self.assertEqual(envelope["policy"]["action"], "allow")

    def test_build_feedback_keyboard_envelope_four_callbacks(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 2)
        self.assertIn("content", envelope["markdown"])
        self.assertTrue(envelope["markdown"]["content"])
        self.assertNotIn("template_card", envelope)

        buttons = envelope["keyboard"]["content"]["rows"][0]["buttons"]
        self.assertEqual(len(buttons), 4)
        action_data = {button["action"]["data"] for button in buttons}
        self.assertEqual(
            action_data,
            {"up", "down", "needs_fix", "route_wrong"},
        )
        for button in buttons:
            self.assertEqual(button["action"]["type"], 1)
            self.assertEqual(button["action"]["permission"]["type"], 2)

    def test_text_blocks_gateway_notice(self) -> None:
        envelope = build_text_envelope(
            content=BLOCKED_NOTICE,
            msg_id="inbound-1",
            msg_seq=1,
        )

        self.assertEqual(envelope["policy"]["action"], "block")
        self.assertNotIn("content", envelope)
        wire = strip_for_wire(envelope)
        self.assertNotIn("content", wire)
        self.assertNotIn("policy", wire)

    def test_strip_for_wire_removes_policy_and_inkstatute(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )
        wire = strip_for_wire(envelope)

        self.assertNotIn("policy", wire)
        self.assertNotIn("inkstatute", wire)
        self.assertIn("msg_type", wire)
        self.assertIn("markdown", wire)
        self.assertIn("keyboard", wire)
        self.assertIn("msg_id", wire)
        self.assertIn("msg_seq", wire)
        # Audit envelope must remain intact (strip is a copy).
        self.assertIn("policy", envelope)
        self.assertIn("inkstatute", envelope)

    def test_keyboard_rows_nested_under_content(self) -> None:
        envelope = build_feedback_keyboard_envelope(
            title="请评价本次回复",
            feedback_target="result-1",
            msg_id="inbound-1",
            msg_seq=1,
        )
        keyboard = envelope["keyboard"]

        self.assertNotIn("rows", keyboard)
        self.assertIn("rows", keyboard["content"])
        self.assertIsInstance(keyboard["content"]["rows"], list)

    def test_build_media_envelope_msg_type_7(self) -> None:
        envelope = build_media_envelope(
            file_info="fixture-file-info-token",
            msg_id="inbound-1",
            msg_seq=2,
        )

        self.assertIsInstance(envelope["msg_type"], int)
        self.assertEqual(envelope["msg_type"], 7)
        self.assertEqual(envelope["media"], {"file_info": "fixture-file-info-token"})
        self.assertEqual(envelope["content"], "")
        self.assertEqual(envelope["msg_id"], "inbound-1")
        self.assertEqual(envelope["msg_seq"], 2)

        # Optional audit key must be stripped for wire.
        envelope_with_policy = dict(envelope)
        envelope_with_policy["policy"] = {"action": "allow", "reason": "n/a"}
        wire = strip_for_wire(envelope_with_policy)
        self.assertEqual(wire["msg_type"], 7)
        self.assertEqual(wire["media"], {"file_info": "fixture-file-info-token"})
        self.assertEqual(wire["content"], "")
        self.assertIn("msg_id", wire)
        self.assertIn("msg_seq", wire)
        self.assertNotIn("policy", wire)


class PassiveReplyWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)

    def test_c2c_within_window_allows(self) -> None:
        received_at = (self.now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = check_passive_reply_window(
            scene="c2c",
            received_at=received_at,
            reply_count=0,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        self.assertTrue(result.ok)
        self.assertIsNone(result.issue_code)
        self.assertIsNone(result.interim_notice)

    def test_c2c_reply_count_4_expires(self) -> None:
        received_at = (self.now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = check_passive_reply_window(
            scene="c2c",
            received_at=received_at,
            reply_count=4,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.issue_code, ISSUE_WINDOW_EXPIRED)
        self.assertIsInstance(result.interim_notice, str)
        self.assertTrue(result.interim_notice)

    def test_group_age_over_5min_expires(self) -> None:
        received_at = (self.now - timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = check_passive_reply_window(
            scene="group",
            received_at=received_at,
            reply_count=0,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.issue_code, ISSUE_WINDOW_EXPIRED)
        self.assertIsInstance(result.interim_notice, str)
        self.assertTrue(result.interim_notice)

    def test_group_reply_count_5_expires(self) -> None:
        received_at = (self.now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = check_passive_reply_window(
            scene="group",
            received_at=received_at,
            reply_count=5,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.issue_code, ISSUE_WINDOW_EXPIRED)
        self.assertTrue(result.interim_notice)

    def test_c2c_max_replies_is_4_not_5(self) -> None:
        received_at = (self.now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        allowed = check_passive_reply_window(
            scene="c2c",
            received_at=received_at,
            reply_count=3,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        denied = check_passive_reply_window(
            scene="c2c",
            received_at=received_at,
            reply_count=4,
            clock=_fixed_clock(self.now),
            msg_id="inbound-1",
        )
        self.assertTrue(allowed.ok)
        self.assertFalse(denied.ok)
        self.assertEqual(denied.issue_code, ISSUE_WINDOW_EXPIRED)

    def test_missing_received_at_fails_closed(self) -> None:
        for received_at in (None, ""):
            with self.subTest(received_at=received_at):
                result = check_passive_reply_window(
                    scene="c2c",
                    received_at=received_at,
                    reply_count=0,
                    clock=_fixed_clock(self.now),
                    msg_id="inbound-1",
                )
                self.assertFalse(result.ok)
                self.assertEqual(result.issue_code, ISSUE_WINDOW_EXPIRED)
                self.assertIsInstance(result.interim_notice, str)
                self.assertTrue(result.interim_notice)

    def test_unknown_scene_fails_closed(self) -> None:
        received_at = (self.now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for scene in ("", "guild", "unknown"):
            with self.subTest(scene=scene):
                result = check_passive_reply_window(
                    scene=scene,
                    received_at=received_at,
                    reply_count=0,
                    clock=_fixed_clock(self.now),
                    msg_id="inbound-1",
                )
                self.assertFalse(result.ok)
                self.assertEqual(result.issue_code, ISSUE_WINDOW_EXPIRED)


class SendRetryTests(unittest.IsolatedAsyncioTestCase):
    def _token_manager(self, token: str = "fixture-token") -> TokenManager:
        return TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=FakeTokenTransport(
                response={"access_token": token, "expires_in": 7200}
            ),
        )

    async def test_transient_500_retries_then_succeeds(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                SendError("transient server error", status_code=500),
                {"id": "msg-ok", "status": 200},
            ]
        )
        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        result = await send_message(
            envelope=envelope,
            scene="c2c",
            token_manager=self._token_manager(),
            transport=transport,
            user_openid="user-openid-1",
            sleep=_noop_sleep,
        )
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(result.get("id"), "msg-ok")
        self.assertTrue(
            transport.calls[0]["authorization"].startswith("QQBot "),
        )

    async def test_401_invalidates_token_and_retries_once(self) -> None:
        token_transport = FakeTokenTransport(
            response={"access_token": "token-v1", "expires_in": 7200}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=token_transport,
        )
        message_transport = FakeMessageTransport(
            responses=[
                SendError("unauthorized", status_code=401),
                {"id": "msg-after-refresh", "status": 200},
            ]
        )
        # Seed cache so invalidate forces a second fetch_token.
        await manager.get_token()
        self.assertEqual(token_transport.call_count, 1)
        token_transport.response = {
            "access_token": "token-v2",
            "expires_in": 7200,
        }

        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        result = await send_message(
            envelope=envelope,
            scene="c2c",
            token_manager=manager,
            transport=message_transport,
            user_openid="user-openid-1",
            sleep=_noop_sleep,
        )

        self.assertEqual(result.get("id"), "msg-after-refresh")
        self.assertEqual(message_transport.call_count, 2)
        self.assertGreaterEqual(token_transport.call_count, 2)
        self.assertTrue(
            message_transport.calls[-1]["authorization"].startswith("QQBot "),
        )

    async def test_terminal_304027_no_retry(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                SendError("message expired", status_code=400, qq_code=304027),
            ]
        )
        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        with self.assertRaises(SendError) as ctx:
            await send_message(
                envelope=envelope,
                scene="c2c",
                token_manager=self._token_manager(),
                transport=transport,
                user_openid="user-openid-1",
                sleep=_noop_sleep,
            )
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(ctx.exception.qq_code, 304027)

    async def test_send_error_message_has_no_token(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                SendError("message expired", status_code=400, qq_code=304027),
            ]
        )
        manager = self._token_manager(token=SECRET_TOKEN)
        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        with self.assertRaises(SendError) as ctx:
            await send_message(
                envelope=envelope,
                scene="c2c",
                token_manager=manager,
                transport=transport,
                user_openid="user-openid-1",
                sleep=_noop_sleep,
            )
        self.assertNotIn(SECRET_TOKEN, str(ctx.exception))
        self.assertNotIn(SECRET_TOKEN, repr(ctx.exception))
        for call in transport.calls:
            # Authorization is recorded for assertions, but SendError must not leak it.
            self.assertNotIn(SECRET_TOKEN, str(ctx.exception.__dict__))

    async def test_wire_url_c2c_and_group(self) -> None:
        self.assertEqual(
            wire_url_for_scene("c2c", user_openid="u-openid"),
            "https://api.sgroup.qq.com/v2/users/u-openid/messages",
        )
        self.assertEqual(
            wire_url_for_scene("group", group_openid="g-openid"),
            "https://api.sgroup.qq.com/v2/groups/g-openid/messages",
        )

    async def test_wire_url_rejects_openid_path_injection(self) -> None:
        for bad in ("../evil", "u?q=1", "u#frag", "u/extra", "a" * 129):
            with self.subTest(openid=bad):
                with self.assertRaises(SendError) as ctx:
                    wire_url_for_scene("c2c", user_openid=bad)
                self.assertIn("invalid user_openid", str(ctx.exception))
        with self.assertRaises(SendError) as ctx:
            wire_url_for_scene("group", group_openid="../evil")
        self.assertIn("invalid group_openid", str(ctx.exception))

    async def test_token_error_on_initial_fetch_maps_to_send_error(self) -> None:
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=FakeTokenTransport(error=TokenError("boom", status_code=503)),
        )
        transport = FakeMessageTransport(response={"id": "should-not-send"})
        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        with self.assertRaises(SendError) as ctx:
            await send_message(
                envelope=envelope,
                scene="c2c",
                token_manager=manager,
                transport=transport,
                user_openid="user-openid-1",
                sleep=_noop_sleep,
            )
        self.assertEqual(str(ctx.exception), "QQ Bot token unavailable")
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertNotIn("boom", str(ctx.exception))
        self.assertEqual(transport.call_count, 0)

    async def test_token_error_on_401_refresh_maps_to_send_error(self) -> None:
        token_transport = FakeTokenTransport(
            response={"access_token": "token-v1", "expires_in": 7200}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=token_transport,
        )
        await manager.get_token()
        message_transport = FakeMessageTransport(
            responses=[SendError("unauthorized", status_code=401)]
        )
        token_transport.error = TokenError("refresh-fail", status_code=500)
        token_transport.response = None
        envelope = build_text_envelope(
            content=LEGAL_CONTENT, msg_id="inbound-1", msg_seq=1
        )
        with self.assertRaises(SendError) as ctx:
            await send_message(
                envelope=envelope,
                scene="c2c",
                token_manager=manager,
                transport=message_transport,
                user_openid="user-openid-1",
                sleep=_noop_sleep,
            )
        self.assertEqual(str(ctx.exception), "QQ Bot token unavailable")
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertNotIn("refresh-fail", str(ctx.exception))
        self.assertEqual(message_transport.call_count, 1)


class RichMediaUploadTests(unittest.IsolatedAsyncioTestCase):
    FIXTURE_FILE_URL = "https://example.invalid/artifact.docx"
    FIXTURE_USER = "user-openid-1"
    FIXTURE_GROUP = "group-openid-1"

    def _token_manager(self, token: str = "fixture-token") -> TokenManager:
        return TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=FakeTokenTransport(
                response={"access_token": token, "expires_in": 7200}
            ),
        )

    def test_wire_files_url_c2c_and_group(self) -> None:
        self.assertEqual(
            wire_files_url_for_scene("c2c", user_openid=self.FIXTURE_USER),
            f"https://api.sgroup.qq.com/v2/users/{self.FIXTURE_USER}/files",
        )
        self.assertEqual(
            wire_files_url_for_scene("group", group_openid=self.FIXTURE_GROUP),
            f"https://api.sgroup.qq.com/v2/groups/{self.FIXTURE_GROUP}/files",
        )
        with self.assertRaises(SendError):
            wire_files_url_for_scene("c2c", user_openid="../evil")
        with self.assertRaises(SendError):
            wire_files_url_for_scene("group", group_openid="u?q=1")

    async def test_upload_rich_media_posts_file_type_4_with_url(self) -> None:
        transport = FakeMessageTransport(
            response={
                "file_uuid": "uuid-fixture-001",
                "file_info": "file-info-token-001",
                "ttl": 3600,
            }
        )
        result = await upload_rich_media(
            scene="c2c",
            token_manager=self._token_manager(),
            transport=transport,
            file_type=4,
            file_url=self.FIXTURE_FILE_URL,
            user_openid=self.FIXTURE_USER,
            sleep=_noop_sleep,
        )
        self.assertEqual(transport.call_count, 1)
        body = transport.calls[0]["body"]
        self.assertEqual(body["file_type"], 4)
        self.assertEqual(body["url"], self.FIXTURE_FILE_URL)
        self.assertTrue(
            transport.calls[0]["url"].endswith(f"/v2/users/{self.FIXTURE_USER}/files")
        )
        self.assertEqual(result["file_info"], "file-info-token-001")
        self.assertEqual(result["file_uuid"], "uuid-fixture-001")
        self.assertEqual(result["ttl"], 3600)

    async def test_upload_rejects_non_https_file_url(self) -> None:
        transport = FakeMessageTransport(response={"file_info": "should-not-upload"})
        for bad_url in ("http://example.invalid/a.docx", "", "ftp://example.invalid/a"):
            with self.subTest(file_url=bad_url):
                with self.assertRaises(SendError) as ctx:
                    await upload_rich_media(
                        scene="c2c",
                        token_manager=self._token_manager(),
                        transport=transport,
                        file_url=bad_url or None,
                        user_openid=self.FIXTURE_USER,
                        sleep=_noop_sleep,
                    )
                self.assertEqual(transport.call_count, 0)
                err = str(ctx.exception).lower()
                self.assertNotIn("authorization", err)
                self.assertNotIn("access_token", err)

    async def test_send_rich_media_two_step(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                {
                    "file_uuid": "uuid-two-step",
                    "file_info": "file-info-two-step",
                    "ttl": 7200,
                },
                {"id": "msg-media-ok", "status": 200},
            ]
        )
        result = await send_rich_media(
            scene="c2c",
            token_manager=self._token_manager(),
            transport=transport,
            file_url=self.FIXTURE_FILE_URL,
            user_openid=self.FIXTURE_USER,
            msg_id="inbound-media-1",
            msg_seq=1,
            sleep=_noop_sleep,
        )
        self.assertEqual(transport.call_count, 2)
        upload_call, send_call = transport.calls
        self.assertTrue(upload_call["url"].endswith("/files"))
        self.assertEqual(upload_call["body"]["file_type"], 4)
        self.assertTrue(send_call["url"].endswith("/messages"))
        self.assertEqual(send_call["body"]["msg_type"], 7)
        self.assertEqual(
            send_call["body"]["media"],
            {"file_info": "file-info-two-step"},
        )
        self.assertEqual(send_call["body"]["content"], "")
        self.assertEqual(send_call["body"]["msg_id"], "inbound-media-1")
        self.assertNotIn("policy", send_call["body"])
        self.assertEqual(result.get("id"), "msg-media-ok")

    async def test_upload_terminal_failure_records_actual_attempts(self) -> None:
        """WR-01: terminal first-attempt failure must not report attempts=max_attempts."""
        transport = FakeMessageTransport(
            responses=[
                SendError("message expired", status_code=400, qq_code=304027),
            ]
        )
        with self.assertRaises(SendError) as ctx:
            await upload_rich_media(
                scene="c2c",
                token_manager=self._token_manager(),
                transport=transport,
                file_url=self.FIXTURE_FILE_URL,
                user_openid=self.FIXTURE_USER,
                max_attempts=3,
                sleep=_noop_sleep,
            )
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(ctx.exception.attempts, 1)
        evidence = getattr(ctx.exception, "evidence", None)
        self.assertIsInstance(evidence, dict)
        self.assertEqual(evidence["attempts"], 1)
        self.assertEqual(evidence["rich_media_stage"], "upload")
        self.assertEqual(evidence["issue_code"], "qqbot_rich_media_upload_failed")


class RichMediaRetryTests(unittest.IsolatedAsyncioTestCase):
    FIXTURE_FILE_URL = "https://example.invalid/artifact.docx"
    FIXTURE_USER = "user-openid-1"

    def _token_manager(self, token: str = "fixture-token") -> TokenManager:
        return TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=FakeTokenTransport(
                response={"access_token": token, "expires_in": 7200}
            ),
        )

    async def test_retry_304082_then_success(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                SendError("media convert fail", status_code=400, qq_code=304082),
                {
                    "file_uuid": "uuid-after-304082",
                    "file_info": "file-info-after-304082",
                    "ttl": 3600,
                },
            ]
        )
        result = await upload_rich_media(
            scene="c2c",
            token_manager=self._token_manager(),
            transport=transport,
            file_url=self.FIXTURE_FILE_URL,
            user_openid=self.FIXTURE_USER,
            sleep=_noop_sleep,
        )
        self.assertGreaterEqual(transport.call_count, 2)
        self.assertEqual(result["file_info"], "file-info-after-304082")

    async def test_retry_304083_then_success(self) -> None:
        transport = FakeMessageTransport(
            responses=[
                SendError("media pull fail", status_code=400, qq_code=304083),
                {
                    "file_uuid": "uuid-after-304083",
                    "file_info": "file-info-after-304083",
                    "ttl": 3600,
                },
            ]
        )
        result = await upload_rich_media(
            scene="c2c",
            token_manager=self._token_manager(),
            transport=transport,
            file_url=self.FIXTURE_FILE_URL,
            user_openid=self.FIXTURE_USER,
            sleep=_noop_sleep,
        )
        self.assertGreaterEqual(transport.call_count, 2)
        self.assertEqual(result["file_info"], "file-info-after-304083")

    async def test_401_invalidate_once_on_upload(self) -> None:
        token_transport = FakeTokenTransport(
            response={"access_token": "token-v1", "expires_in": 7200}
        )
        manager = TokenManager(
            app_id=FIXTURE_APP_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            transport=token_transport,
        )
        message_transport = FakeMessageTransport(
            responses=[
                SendError("unauthorized", status_code=401),
                {
                    "file_uuid": "uuid-after-401",
                    "file_info": "file-info-after-401",
                    "ttl": 3600,
                },
            ]
        )
        await manager.get_token()
        self.assertEqual(token_transport.call_count, 1)
        token_transport.response = {
            "access_token": "token-v2",
            "expires_in": 7200,
        }

        result = await upload_rich_media(
            scene="c2c",
            token_manager=manager,
            transport=message_transport,
            file_url=self.FIXTURE_FILE_URL,
            user_openid=self.FIXTURE_USER,
            sleep=_noop_sleep,
        )

        self.assertEqual(result["file_info"], "file-info-after-401")
        self.assertEqual(message_transport.call_count, 2)
        self.assertGreaterEqual(token_transport.call_count, 2)
        self.assertTrue(
            message_transport.calls[-1]["authorization"].startswith("QQBot "),
        )

    def test_rich_media_evidence_sanitized(self) -> None:
        evidence = _rich_media_evidence(
            stage="upload",
            attempts=2,
            status_code=400,
            qq_code=304082,
            file_uuid="uuid-sensitive-fixture",
            ttl=3600,
            issue_code="qqbot_rich_media_upload_failed",
        )
        forbidden = {
            "Authorization",
            "authorization",
            "access_token",
            "file_data",
            "url",
            "file_url",
        }
        for key in forbidden:
            self.assertNotIn(key, evidence)
        serialized = str(evidence)
        self.assertNotIn("https://", serialized)
        self.assertNotIn("http://", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("file_data", serialized)
        self.assertIn("file_uuid_hash", evidence)
        self.assertEqual(len(evidence["file_uuid_hash"]), 16)
        self.assertNotEqual(evidence["file_uuid_hash"], "uuid-sensitive-fixture")
        self.assertEqual(evidence["rich_media_stage"], "upload")
        self.assertEqual(evidence["attempts"], 2)
        self.assertEqual(evidence["ttl"], 3600)
        self.assertEqual(evidence["issue_code"], "qqbot_rich_media_upload_failed")


if __name__ == "__main__":
    unittest.main()
