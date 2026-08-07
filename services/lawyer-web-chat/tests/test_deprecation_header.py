"""Tests for lawyer-web-chat deprecation headers (GW-05).

Verifies that all lawyer-web-chat responses include:
- Deprecation: true header
- Sunset header with a future HTTP-date
- Link header pointing to the Gateway successor (/v1/sessions)
- HTML pages include a deprecation notice element
- JSON response bodies are unchanged (only headers are added)
"""

from __future__ import annotations

import json
import unittest

from lawyer_web_chat.feedback import FeedbackHandler
from lawyer_web_chat.history import MessageHistory
from lawyer_web_chat.server import handle_lawyer_chat_request
from lawyer_web_chat.session import COOKIE_NAME, SessionStore
from lawyer_web_chat.sse import SseStream
from lawyer_web_chat.upload import FileUploadHandler
from platform_runtime.feature_flags import RuntimeFeatureFlags


class TestDeprecationHeader(unittest.TestCase):
    """Tests for deprecation headers on lawyer-web-chat responses."""

    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.session_store = SessionStore()
        self.message_history = MessageHistory()
        self.upload_handler = FileUploadHandler()
        self.feedback_handler = FeedbackHandler()
        self.sse_stream = SseStream()
        self.flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=True)

    def _make_request(
        self,
        method: str = "GET",
        path: str = "/",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        return handle_lawyer_chat_request(
            method,
            path,
            headers,
            body,
            feature_flags=self.flags,
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
        status, resp_body, headers = self._make_request("POST", "/login", body=body)
        self.assertEqual(status, 200)
        cookie_header = headers.get("Set-Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{COOKIE_NAME}="):
                token = part[len(COOKIE_NAME) + 1:]
                return {"Cookie": f"{COOKIE_NAME}={token}"}
        self.fail("No Set-Cookie header found")

    def test_index_page_has_deprecation_header(self) -> None:
        """Index page (GET /) includes Deprecation and Sunset headers."""
        status, body, headers = self._make_request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Deprecation"), "true")
        self.assertIn("Sunset", headers)

    def test_login_has_deprecation_header(self) -> None:
        """Login (POST /login) includes deprecation headers."""
        body = json.dumps({
            "tenant_id": "tenant-1",
            "user_id": "lawyer-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request("POST", "/login", body=body)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Deprecation"), "true")
        self.assertIn("Sunset", headers)

    def test_all_routes_have_deprecation_header(self) -> None:
        """All routes include Deprecation: true header."""
        auth_headers = self._login()

        routes = [
            ("GET", "/", None),
            ("POST", "/login", json.dumps({"tenant_id": "t", "user_id": "u"}).encode()),
            ("GET", "/sessions", None),
            ("GET", "/history", None),
            ("GET", "/stream", None),
            ("POST", "/upload", json.dumps({"filename": "test.txt", "content": ""}).encode()),
            ("POST", "/feedback", json.dumps({"conversation_id": "c", "action": "up", "feedback_target": "t"}).encode()),
        ]

        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                # Use auth headers for routes that require it
                req_headers = auth_headers if path not in ("/", "/login") else None
                status, resp_body, headers = self._make_request(method, path, req_headers, body)
                self.assertEqual(
                    headers.get("Deprecation"), "true",
                    f"Route {method} {path} missing Deprecation header",
                )

    def test_deprecation_notice_in_html(self) -> None:
        """HTML response body contains a deprecation notice element."""
        status, body, headers = self._make_request("GET", "/")
        self.assertEqual(status, 200)
        body_str = body.decode("utf-8")
        self.assertIn("deprecation-notice", body_str)
        self.assertIn("deprecated", body_str.lower())

    def test_link_header_points_to_gateway(self) -> None:
        """Link header points to /v1/sessions as the successor."""
        status, body, headers = self._make_request("GET", "/")
        link_header = headers.get("Link", "")
        self.assertIn("/v1/sessions", link_header)
        self.assertIn("successor-version", link_header)

    def test_json_responses_unchanged(self) -> None:
        """JSON response bodies are unchanged from pre-deprecation behavior.

        Only headers are added — the JSON body should not contain any
        deprecation-related fields.
        """
        # Login response body
        body = json.dumps({
            "tenant_id": "tenant-1",
            "user_id": "lawyer-1",
        }).encode("utf-8")
        status, resp_body, headers = self._make_request("POST", "/login", body=body)
        self.assertEqual(status, 200)
        resp_json = json.loads(resp_body.decode("utf-8"))
        # Standard fields, no deprecation fields in body
        self.assertEqual(resp_json["status"], "ok")
        self.assertIn("session_id", resp_json)
        self.assertIn("tenant_id", resp_json)
        self.assertNotIn("deprecation", resp_json)
        self.assertNotIn("sunset", resp_json)

    def test_sunset_header_is_future_date(self) -> None:
        """Sunset header is a valid HTTP-date in the future."""
        status, body, headers = self._make_request("GET", "/")
        sunset = headers.get("Sunset", "")
        self.assertTrue(sunset, "Sunset header must be present")
        # Should contain a day name and GMT (HTTP-date format)
        self.assertIn("GMT", sunset)
        # Should contain a year (2026 or later)
        self.assertIn("2026", sunset)

    def test_error_page_has_deprecation_notice(self) -> None:
        """Error pages also include the deprecation notice."""
        # Trigger a 404 by hitting an unknown route (with auth)
        auth_headers = self._login()
        status, body, headers = self._make_request("GET", "/unknown-route", auth_headers)
        self.assertEqual(status, 404)
        body_str = body.decode("utf-8")
        self.assertIn("deprecation-notice", body_str)
        self.assertEqual(headers.get("Deprecation"), "true")

    def test_disabled_flag_response_has_deprecation_header(self) -> None:
        """Even the 503 disabled response has deprecation headers."""
        flags = RuntimeFeatureFlags(lawyer_web_chat_enabled=False)
        status, body, headers = handle_lawyer_chat_request(
            "GET", "/", None, None,
            feature_flags=flags,
            session_store=self.session_store,
            message_history=self.message_history,
            upload_handler=self.upload_handler,
            feedback_handler=self.feedback_handler,
            sse_stream=self.sse_stream,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 503)
        self.assertEqual(headers.get("Deprecation"), "true")
        self.assertIn("Sunset", headers)


if __name__ == "__main__":
    unittest.main()
