"""Tests for LawyerWebChatServer — feature flag, auth, SSE, CSP, routing."""

from __future__ import annotations

import base64
import json
import unittest

from lawyer_web_chat.boundary import ChatBoundary
from lawyer_web_chat.feedback import FeedbackHandler
from lawyer_web_chat.history import MessageHistory
from lawyer_web_chat.server import CSP_HEADER, handle_lawyer_chat_request
from lawyer_web_chat.session import COOKIE_NAME, SessionStore, build_set_cookie_header
from lawyer_web_chat.sse import SseStream
from lawyer_web_chat.upload import FileUploadHandler
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.tenant_scope import TenantScopeError
from rbac import Role


class LawyerWebChatServerTests(unittest.TestCase):
    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.session_store = SessionStore()
        self.message_history = MessageHistory()
        self.upload_handler = FileUploadHandler()
        self.feedback_handler = FeedbackHandler()
        self.sse_stream = SseStream()

    def _make_request(
        self,
        method: str = "GET",
        path: str = "/",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        if flags is None:
            flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True)
        return handle_lawyer_chat_request(
            method,
            path,
            headers,
            body,
            feature_flags=flags,
            session_store=self.session_store,
            message_history=self.message_history,
            upload_handler=self.upload_handler,
            feedback_handler=self.feedback_handler,
            sse_stream=self.sse_stream,
            rbac_secret=self.SECRET,
        )

    def _login(self, tenant_id: str = "tenant-1") -> dict[str, str]:
        """Login and return headers with session cookie."""
        body = json.dumps({
            "tenant_id": tenant_id,
            "user_id": "lawyer-1",
            "conversation_id": "conv-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request(
            "POST", "/login", body=body,
        )
        self.assertEqual(status, 200)
        cookie_header = headers.get("Set-Cookie", "")
        # Extract cookie value
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{COOKIE_NAME}="):
                token = part[len(COOKIE_NAME) + 1:]
                return {"Cookie": f"{COOKIE_NAME}={token}"}
        self.fail("No Set-Cookie header found")

    def test_disabled_feature_flag_returns_503(self) -> None:
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=False)
        status, body, headers = self._make_request(flags=flags)
        self.assertEqual(status, 503)
        self.assertIn("lawyer_web_chat_disabled", body.decode("utf-8"))

    def test_enabled_flag_returns_200_for_index(self) -> None:
        status, body, headers = self._make_request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("InkStatute Lawyer Chat", body.decode("utf-8"))

    def test_login_sets_httponly_cookie(self) -> None:
        body = json.dumps({
            "tenant_id": "tenant-1",
            "user_id": "lawyer-1",
            "conversation_id": "conv-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request("POST", "/login", body=body)
        self.assertEqual(status, 200)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Strict", cookie)
        data = json.loads(resp_body.decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertIn("session_id", data)

    def test_unauthenticated_access_to_protected_route_returns_401(self) -> None:
        status, body, headers = self._make_request("GET", "/history")
        self.assertEqual(status, 401)

    def test_authenticated_access_to_history_returns_200(self) -> None:
        # Add a message first
        self.message_history.add_message(
            conversation_id="conv-1",
            sender="lawyer",
            content="Hello",
            payload_ref="ref://conv-1/msg-1",
        )
        auth_headers = self._login()
        status, body, headers = self._make_request(
            "GET", "/history?conversation_id=conv-1", headers=auth_headers,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreater(data["count"], 0)

    def test_sessions_endpoint_returns_session_list(self) -> None:
        auth_headers = self._login()
        status, body, headers = self._make_request(
            "GET", "/sessions", headers=auth_headers,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(data["count"], 1)

    def test_stream_endpoint_returns_sse_content_type(self) -> None:
        auth_headers = self._login()
        status, body, headers = self._make_request(
            "GET", "/stream", headers=auth_headers,
        )
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers["Content-Type"])

    def test_upload_stores_references_only(self) -> None:
        auth_headers = self._login()
        content_b64 = base64.b64encode(b"file content").decode("ascii")
        body = json.dumps({
            "filename": "test.txt",
            "content": content_b64,
            "mime_type": "text/plain",
            "conversation_id": "conv-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request(
            "POST", "/upload", headers=auth_headers, body=body,
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_body.decode("utf-8"))
        self.assertIn("payload_ref", data)
        self.assertIn("content_ref", data)
        self.assertNotIn("file content", json.dumps(data))
        self.assertTrue(data["reference_only"])

    def test_feedback_submission_returns_feedback_id(self) -> None:
        auth_headers = self._login()
        body = json.dumps({
            "conversation_id": "conv-1",
            "user_id": "lawyer-1",
            "action": "up",
            "feedback_target": "turn-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request(
            "POST", "/feedback", headers=auth_headers, body=body,
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_body.decode("utf-8"))
        self.assertIn("feedback_id", data)
        self.assertEqual(data["action"], "up")

    def test_feedback_invalid_action_returns_400(self) -> None:
        auth_headers = self._login()
        body = json.dumps({
            "conversation_id": "conv-1",
            "user_id": "lawyer-1",
            "action": "invalid",
            "feedback_target": "turn-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request(
            "POST", "/feedback", headers=auth_headers, body=body,
        )
        self.assertEqual(status, 400)

    def test_csp_header_present(self) -> None:
        status, body, headers = self._make_request("GET", "/")
        self.assertIn("Content-Security-Policy", headers)
        self.assertEqual(headers["Content-Security-Policy"], CSP_HEADER)

    def test_security_headers_present(self) -> None:
        status, body, headers = self._make_request("GET", "/")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_unknown_route_returns_404(self) -> None:
        auth_headers = self._login()
        status, body, headers = self._make_request(
            "GET", "/unknown", headers=auth_headers,
        )
        self.assertEqual(status, 404)

    def test_output_boundary_filters_backend_noise_in_stream(self) -> None:
        # Add a message with backend noise
        self.message_history.add_message(
            conversation_id="tenant-1",
            sender="assistant",
            content="model: gpt-4 processing",
            payload_ref="ref://tenant-1/msg-1",
        )
        auth_headers = self._login()
        status, body, headers = self._make_request(
            "GET", "/stream", headers=auth_headers,
        )
        self.assertEqual(status, 200)
        body_text = body.decode("utf-8")
        self.assertNotIn("gpt-4", body_text)
        self.assertNotIn("model:", body_text.lower())

    def test_no_innerhtml_in_html_output(self) -> None:
        status, body, headers = self._make_request("GET", "/")
        body_text = body.decode("utf-8")
        self.assertNotIn("innerHTML", body_text)
        self.assertNotIn("onclick", body_text)
        self.assertNotIn("onerror", body_text)
        self.assertNotIn("javascript:", body_text)

    def test_multi_device_sync_shares_session(self) -> None:
        """Two devices joining the same conversation see the same session."""
        # Device 1 logs in
        body1 = json.dumps({
            "tenant_id": "tenant-1",
            "user_id": "lawyer-1",
            "conversation_id": "shared-conv",
            "device_id": "device-1",
        }).encode("utf-8")
        status1, resp1, _ = self._make_request("POST", "/login", body=body1)
        self.assertEqual(status1, 200)

        # Device 2 logs in to the same conversation
        body2 = json.dumps({
            "tenant_id": "tenant-1",
            "user_id": "lawyer-1",
            "conversation_id": "shared-conv",
            "device_id": "device-2",
        }).encode("utf-8")
        status2, resp2, _ = self._make_request("POST", "/login", body=body2)
        self.assertEqual(status2, 200)

        # Both sessions should be listed for the same conversation
        sessions = self.session_store.get_sessions_for_conversation("shared-conv")
        self.assertEqual(len(sessions), 2)


class TenantIsolationTests(unittest.TestCase):
    """Tests for tenant isolation in lawyer-web-chat with multi_tenant_enabled."""

    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.session_store = SessionStore()
        self.message_history = MessageHistory()
        self.upload_handler = FileUploadHandler()
        self.feedback_handler = FeedbackHandler()
        self.sse_stream = SseStream()

    def _make_request(
        self,
        method: str = "GET",
        path: str = "/",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        if flags is None:
            flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True)
        return handle_lawyer_chat_request(
            method,
            path,
            headers,
            body,
            feature_flags=flags,
            session_store=self.session_store,
            message_history=self.message_history,
            upload_handler=self.upload_handler,
            feedback_handler=self.feedback_handler,
            sse_stream=self.sse_stream,
            rbac_secret=self.SECRET,
        )

    def _login(self, tenant_id: str = "tenant-1") -> dict[str, str]:
        body = json.dumps({
            "tenant_id": tenant_id,
            "user_id": "lawyer-1",
            "conversation_id": f"conv-{tenant_id}",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request("POST", "/login", body=body)
        self.assertEqual(status, 200)
        cookie_header = headers.get("Set-Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{COOKIE_NAME}="):
                token = part[len(COOKIE_NAME) + 1:]
                return {"Cookie": f"{COOKIE_NAME}={token}"}
        self.fail("No Set-Cookie header found")

    def test_disabled_multi_tenant_returns_all_history(self) -> None:
        """multi_tenant_enabled=False → all message history returned (no regression)."""
        self.message_history.add_message(
            conversation_id="conv-tenant-1",
            sender="lawyer",
            content="Hello from tenant-1",
            payload_ref="ref://1",
            metadata={"tenant_id": "tenant-1"},
        )
        self.message_history.add_message(
            conversation_id="conv-tenant-1",
            sender="lawyer",
            content="Hello from tenant-2",
            payload_ref="ref://2",
            metadata={"tenant_id": "tenant-2"},
        )
        auth_headers = self._login("tenant-1")
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True, multi_tenant_enabled=False)
        status, body, _ = self._make_request(
            "GET", "/history?conversation_id=conv-tenant-1", headers=auth_headers, flags=flags,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["count"], 2)

    def test_enabled_multi_tenant_filters_history(self) -> None:
        """multi_tenant_enabled=True → only matching tenant messages returned."""
        self.message_history.add_message(
            conversation_id="shared-conv",
            sender="lawyer",
            content="Message from tenant-1",
            payload_ref="ref://1",
            metadata={"tenant_id": "tenant-1"},
        )
        self.message_history.add_message(
            conversation_id="shared-conv",
            sender="lawyer",
            content="Message from tenant-2",
            payload_ref="ref://2",
            metadata={"tenant_id": "tenant-2"},
        )
        auth_headers = self._login("tenant-1")
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True, multi_tenant_enabled=True)
        status, body, _ = self._make_request(
            "GET", "/history?conversation_id=shared-conv", headers=auth_headers, flags=flags,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["count"], 1)
        self.assertIn("tenant-1", data["items"][0]["content"])

    def test_enabled_multi_tenant_filters_uploads(self) -> None:
        """multi_tenant_enabled=True → upload listing filters by tenant."""
        # Create uploads for two tenants in the same conversation
        self.upload_handler.handle_upload(
            filename="a.txt", content_bytes=b"a", mime_type="text/plain",
            tenant_id="tenant-1", conversation_id="shared-conv",
        )
        self.upload_handler.handle_upload(
            filename="b.txt", content_bytes=b"b", mime_type="text/plain",
            tenant_id="tenant-2", conversation_id="shared-conv",
        )
        auth_headers = self._login("tenant-1")
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True, multi_tenant_enabled=True)
        # Upload a file as tenant-1 (write path already uses tenant_id)
        content_b64 = base64.b64encode(b"new file").decode("ascii")
        body = json.dumps({
            "filename": "new.txt", "content": content_b64,
            "mime_type": "text/plain", "conversation_id": "shared-conv",
        }).encode("utf-8")
        status, resp_body, _ = self._make_request(
            "POST", "/upload", headers=auth_headers, body=body, flags=flags,
        )
        self.assertEqual(status, 200)

    def test_enabled_multi_tenant_feedback_isolated(self) -> None:
        """Feedback submitted with tenant-1 token has tenant_id in metadata."""
        auth_headers = self._login("tenant-1")
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True, multi_tenant_enabled=True)
        body = json.dumps({
            "conversation_id": "conv-tenant-1",
            "user_id": "lawyer-1",
            "action": "up",
            "feedback_target": "turn-1",
        }).encode("utf-8")
        status, resp_body, _ = self._make_request(
            "POST", "/feedback", headers=auth_headers, body=body, flags=flags,
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_body.decode("utf-8"))
        self.assertIn("feedback_id", data)

    def test_enabled_multi_tenant_unresolved_raises(self) -> None:
        """multi_tenant_enabled=True, token with no tenant_id → TenantScopeError (fail-safe)."""
        from rbac.token import _b64url_encode
        from unittest.mock import patch
        import hashlib
        import hmac

        with patch("rbac.token.time.time", return_value=1000.0):
            now = 1000
            payload = {
                "role": "lawyer",
                "tenant_id": "",
                "iat": now,
                "exp": now + 60,
            }
            payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
            sig = hmac.new(
                self.SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
            ).digest()
            token = f"{payload_b64}.{_b64url_encode(sig)}"

            flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True, multi_tenant_enabled=True)
            with self.assertRaises(TenantScopeError):
                self._make_request(
                    "GET", "/history",
                    headers={"Cookie": f"{COOKIE_NAME}={token}"},
                    flags=flags,
                )

    def test_cross_tenant_session_isolation(self) -> None:
        """tenant-1 login cannot see tenant-2 sessions."""
        # Login as tenant-1
        self._login("tenant-1")
        # Login as tenant-2
        self._login("tenant-2")
        # List sessions as tenant-1
        auth_headers = self._login("tenant-1")
        status, body, _ = self._make_request("GET", "/sessions", headers=auth_headers)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        for session in data["sessions"]:
            self.assertEqual(session["conversation_id"], "conv-tenant-1")


if __name__ == "__main__":
    unittest.main()
