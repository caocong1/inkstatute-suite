"""Tests for HMAC-signed session cookies and the in-memory session store."""

from __future__ import annotations

import unittest

from rbac.roles import Role
from rbac.session import (
    DEFAULT_SESSION_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    InMemorySessionStore,
    SessionRecord,
    issue_session_cookie,
    parse_cookie_header,
    verify_session_cookie,
)


class SessionCookieIssueVerifyTests(unittest.TestCase):
    def test_issue_and_verify_session_cookie(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        cookie = issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)
        record = verify_session_cookie(cookie, "s", store, now=1500)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.role, "admin")
        self.assertEqual(record.tenant_id, "t1")
        self.assertEqual(record.sid, sid)

    def test_verify_rejects_bad_signature(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        cookie = issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)
        payload_b64, sig_b64 = cookie.split(".")
        # Flip the last character of the signature.
        tampered = payload_b64 + "." + ("A" if sig_b64[-1] != "A" else "B") + sig_b64[:-1]
        self.assertIsNone(verify_session_cookie(tampered, "s", store, now=1500))

    def test_verify_rejects_unknown_sid(self) -> None:
        store = InMemorySessionStore()
        cookie = issue_session_cookie("s", "unknown-sid", role=Role.ADMIN, tenant_id="t1", now=1000)
        self.assertIsNone(verify_session_cookie(cookie, "s", store, now=1500))

    def test_verify_rejects_expired(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=100, now=1000)
        cookie = issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", ttl_seconds=100, now=1000)
        self.assertIsNone(verify_session_cookie(cookie, "s", store, now=1200))

    def test_verify_rejects_deleted_session(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        cookie = issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)
        record = verify_session_cookie(cookie, "s", store, now=1500)
        self.assertIsNotNone(record)
        store.delete(sid)
        self.assertIsNone(verify_session_cookie(cookie, "s", store, now=1500))

    def test_verify_rejects_no_store(self) -> None:
        sid = "some-sid"
        cookie = issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)
        self.assertIsNone(verify_session_cookie(cookie, "s", None, now=1500))

    def test_verify_rejects_malformed(self) -> None:
        store = InMemorySessionStore()
        for bad in ("not-a-cookie", "a.b.c", "", None):  # type: ignore[arg-type]
            self.assertIsNone(verify_session_cookie(bad, "s", store, now=1500))

    def test_issue_session_cookie_format(self) -> None:
        cookie = issue_session_cookie("s", "sid-1", role=Role.ADMIN, tenant_id="t1", now=1000)
        self.assertEqual(cookie.count("."), 1)
        payload_b64, sig_b64 = cookie.split(".")
        # Both parts should be valid base64url (no padding).
        import base64

        def _decode(text: str) -> bytes:
            padding = "=" * (-len(text) % 4)
            return base64.urlsafe_b64decode(text + padding)

        # Should not raise.
        _decode(payload_b64)
        _decode(sig_b64)


class InMemorySessionStoreTests(unittest.TestCase):
    def test_create_generates_unique_sids(self) -> None:
        store = InMemorySessionStore()
        sid1 = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        sid2 = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        self.assertNotEqual(sid1, sid2)

    def test_get_expired_cleans_up(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=100, now=1000)
        record = store.get(sid, now=1200)
        self.assertIsNone(record)
        # Session should have been removed from the dict.
        self.assertNotIn(sid, store._sessions)

    def test_get_returns_record_when_valid(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        record = store.get(sid, now=1500)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.sid, sid)
        self.assertEqual(record.role, "admin")
        self.assertEqual(record.tenant_id, "t1")

    def test_delete_removes_session(self) -> None:
        store = InMemorySessionStore()
        sid = store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)
        store.delete(sid)
        self.assertIsNone(store.get(sid, now=1500))

    def test_delete_nonexistent_is_noop(self) -> None:
        store = InMemorySessionStore()
        store.delete("nonexistent")  # should not raise


class ParseCookieHeaderTests(unittest.TestCase):
    def test_parse_cookie_header(self) -> None:
        header = f"{SESSION_COOKIE_NAME}=abc.def; other=x"
        self.assertEqual(parse_cookie_header(header, SESSION_COOKIE_NAME), "abc.def")

    def test_parse_cookie_header_missing_name(self) -> None:
        header = "other=x"
        self.assertIsNone(parse_cookie_header(header, SESSION_COOKIE_NAME))

    def test_parse_cookie_header_none(self) -> None:
        self.assertIsNone(parse_cookie_header(None, SESSION_COOKIE_NAME))

    def test_parse_cookie_header_multiple(self) -> None:
        header = f"a=1; {SESSION_COOKIE_NAME}=xyz; b=2"
        self.assertEqual(parse_cookie_header(header, SESSION_COOKIE_NAME), "xyz")


class SessionConstantsTests(unittest.TestCase):
    def test_default_session_ttl(self) -> None:
        self.assertEqual(DEFAULT_SESSION_TTL_SECONDS, 28800)

    def test_session_cookie_name(self) -> None:
        self.assertEqual(SESSION_COOKIE_NAME, "inkstatute_session")


if __name__ == "__main__":
    unittest.main()
