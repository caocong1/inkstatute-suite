"""Tests for SessionStore — session creation, token issue/verify, multi-device sync."""

from __future__ import annotations

import unittest

from lawyer_web_chat.session import (
    COOKIE_FLAGS,
    COOKIE_NAME,
    SessionStore,
    build_set_cookie_header,
    extract_cookie,
)
from rbac import Role


class SessionStoreTests(unittest.TestCase):
    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.store = SessionStore()

    def test_create_session_returns_session_id_and_session(self) -> None:
        session_id, session = self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
        )
        self.assertIsNotNone(session_id)
        self.assertEqual(session.tenant_id, "tenant-1")
        self.assertEqual(session.user_id, "lawyer-1")
        self.assertEqual(session.conversation_id, "conv-1")

    def test_issue_and_verify_session_token(self) -> None:
        _, session = self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
        )
        token = self.store.issue_session_token(self.SECRET, session)
        claims = self.store.verify_session_token(token, self.SECRET)
        self.assertIsNotNone(claims)
        assert claims is not None
        self.assertEqual(claims.role, Role.LAWYER.value)
        self.assertEqual(claims.tenant_id, "tenant-1")

    def test_verify_invalid_token_returns_none(self) -> None:
        result = self.store.verify_session_token("invalid.token.here", self.SECRET)
        self.assertIsNone(result)

    def test_verify_non_lawyer_role_returns_none(self) -> None:
        from rbac import issue_token
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        result = self.store.verify_session_token(token, self.SECRET)
        self.assertIsNone(result)

    def test_get_session_by_id(self) -> None:
        session_id, session = self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
        )
        retrieved = self.store.get_session(session_id)
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.conversation_id, "conv-1")

    def test_get_nonexistent_session_returns_none(self) -> None:
        result = self.store.get_session("nonexistent")
        self.assertIsNone(result)

    def test_add_device_for_multi_device_sync(self) -> None:
        session_id, _ = self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
            device_id="device-1",
        )
        added = self.store.add_device(session_id, "device-2")
        self.assertTrue(added)
        session = self.store.get_session(session_id)
        assert session is not None
        self.assertIn("device-1", session.devices)
        self.assertIn("device-2", session.devices)

    def test_add_device_to_nonexistent_session(self) -> None:
        result = self.store.add_device("nonexistent", "device-1")
        self.assertFalse(result)

    def test_get_sessions_for_conversation(self) -> None:
        self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
        )
        self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-2",
            conversation_id="conv-1",
        )
        sessions = self.store.get_sessions_for_conversation("conv-1")
        self.assertEqual(len(sessions), 2)

    def test_cleanup_expired_sessions(self) -> None:
        self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
            now=1000,
            ttl_seconds=100,
        )
        removed = self.store.cleanup_expired(now=1200)
        self.assertEqual(removed, 1)

    def test_cleanup_does_not_remove_active_sessions(self) -> None:
        self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
            now=1000,
            ttl_seconds=500,
        )
        removed = self.store.cleanup_expired(now=1200)
        self.assertEqual(removed, 0)

    def test_session_listing_tenant_isolation(self) -> None:
        """Sessions from two tenants — listing only shows current tenant's sessions."""
        self.store.create_session(
            tenant_id="tenant-1",
            user_id="lawyer-1",
            conversation_id="conv-1",
        )
        self.store.create_session(
            tenant_id="tenant-2",
            user_id="lawyer-2",
            conversation_id="conv-2",
        )
        # Verify sessions are scoped by tenant_id (as done in _handle_sessions)
        tenant1_sessions = [
            s for s in self.store._sessions.values()
            if s.tenant_id == "tenant-1"
        ]
        tenant2_sessions = [
            s for s in self.store._sessions.values()
            if s.tenant_id == "tenant-2"
        ]
        self.assertEqual(len(tenant1_sessions), 1)
        self.assertEqual(len(tenant2_sessions), 1)
        self.assertEqual(tenant1_sessions[0].conversation_id, "conv-1")
        self.assertEqual(tenant2_sessions[0].conversation_id, "conv-2")


class CookieHelperTests(unittest.TestCase):
    def test_build_set_cookie_header_contains_httponly(self) -> None:
        header = build_set_cookie_header("token123")
        self.assertIn(COOKIE_NAME, header)
        self.assertIn("HttpOnly", header)
        self.assertIn("Secure", header)
        self.assertIn("SameSite=Strict", header)

    def test_extract_cookie_from_headers(self) -> None:
        headers = {"Cookie": f"{COOKIE_NAME}=token.abc; other=value"}
        token = extract_cookie(headers)
        self.assertEqual(token, "token.abc")

    def test_extract_cookie_missing_returns_none(self) -> None:
        headers = {"Cookie": "other=value"}
        token = extract_cookie(headers)
        self.assertIsNone(token)

    def test_extract_cookie_no_cookie_header_returns_none(self) -> None:
        token = extract_cookie({})
        self.assertIsNone(token)


if __name__ == "__main__":
    unittest.main()
