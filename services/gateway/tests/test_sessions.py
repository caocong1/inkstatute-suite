"""Unit tests for the Gateway session management.

Tests GatewaySessionManager with RBAC InMemorySessionStore, multi-device
sync, and cookie header building.
"""

from __future__ import annotations

import unittest

from gateway.sessions import GatewaySession, GatewaySessionManager, build_set_cookie_header
from rbac.session import InMemorySessionStore


class TestGatewaySessions(unittest.TestCase):

    def setUp(self) -> None:
        self.store = InMemorySessionStore()
        self.mgr = GatewaySessionManager(
            session_store=self.store, rbac_secret="test-secret",
        )

    def test_create_session(self) -> None:
        sid, cookie, session = self.mgr.create_session(
            tenant_id="t1", user_id="u1", conversation_id="c1",
        )
        self.assertTrue(sid)
        self.assertTrue(cookie)
        self.assertEqual(session.tenant_id, "t1")

    def test_get_session(self) -> None:
        sid, _, original = self.mgr.create_session(
            tenant_id="t1", user_id="u1", conversation_id="c1",
        )
        fetched = self.mgr.get_session(sid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.tenant_id, original.tenant_id)
        self.assertEqual(fetched.conversation_id, original.conversation_id)

    def test_get_session_not_found(self) -> None:
        self.assertIsNone(self.mgr.get_session("nonexistent"))

    def test_list_sessions(self) -> None:
        self.mgr.create_session(tenant_id="t1", user_id="u1", conversation_id="c1")
        self.mgr.create_session(tenant_id="t1", user_id="u2", conversation_id="c2")
        self.mgr.create_session(tenant_id="t2", user_id="u3", conversation_id="c3")
        sessions = self.mgr.list_sessions("t1")
        self.assertEqual(len(sessions), 2)

    def test_add_device(self) -> None:
        sid, _, _ = self.mgr.create_session(
            tenant_id="t1", user_id="u1", conversation_id="c1",
        )
        result = self.mgr.add_device(sid, "device-1")
        self.assertTrue(result)
        session = self.mgr.get_session(sid)
        self.assertIn("device-1", session.devices)

    def test_delete_session(self) -> None:
        sid, _, _ = self.mgr.create_session(
            tenant_id="t1", user_id="u1", conversation_id="c1",
        )
        self.mgr.delete_session(sid)
        self.assertIsNone(self.mgr.get_session(sid))

    def test_build_set_cookie_header(self) -> None:
        header = build_set_cookie_header("cookie-val")
        self.assertIn("HttpOnly", header)
        self.assertIn("Secure", header)
        self.assertIn("SameSite=Strict", header)

    def test_multi_device_sync(self) -> None:
        sid, _, _ = self.mgr.create_session(
            tenant_id="t1", user_id="u1", conversation_id="c1",
            device_id="dev-1",
        )
        self.mgr.add_device(sid, "dev-2")
        session = self.mgr.get_session(sid)
        self.assertIn("dev-1", session.devices)
        self.assertIn("dev-2", session.devices)


if __name__ == "__main__":
    unittest.main()
