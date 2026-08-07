"""Comprehensive tests for upload, artifact, and feedback endpoints.

Tests the three endpoints implemented in Plan 91-03:
- POST /v1/uploads — reference-first file upload
- GET /v1/artifacts/{artifact_id} — artifact download with auth + tenant check
- POST /v1/feedback — feedback normalization

All tests use in-memory handlers and fixture data — no network or external
services required.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import unittest

from platform_contract.events import FeedbackEvent, SkillCandidate

from gateway.app import GatewayApp
from gateway.artifacts import (
    ArtifactMetadata,
    GatewayArtifactStore,
    handle_get_artifact_request,
)
from gateway.auth import AuthContext, GatewayAuth
from gateway.config import GatewayConfig
from gateway.feedback import (
    FeedbackResult,
    GatewayFeedbackHandler,
    handle_submit_feedback_request,
)
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from gateway.upload import (
    GatewayUploadHandler,
    UploadResult,
    handle_upload_request,
)
from rbac.session import InMemorySessionStore


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _load_fixture(name: str) -> list:
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _make_auth(tenant_id: str = "default") -> GatewayAuth:
    """Create a GatewayAuth with static token for testing."""
    return GatewayAuth(rbac_enabled=False, static_token="test-token")


def _make_auth_ctx(tenant_id: str = "default") -> AuthContext:
    """Create an AuthContext for a specific tenant (for unit tests)."""
    return AuthContext(identity=None, authenticated=True, tenant_id=tenant_id, error=None)


def _make_app(
    *,
    artifact_store: GatewayArtifactStore | None = None,
    upload_handler: GatewayUploadHandler | None = None,
    feedback_handler: GatewayFeedbackHandler | None = None,
) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = _make_auth()
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        upload_handler=upload_handler,
        artifact_store=artifact_store,
        feedback_handler=feedback_handler,
    )


# ===========================================================================
# TestUpload
# ===========================================================================


class TestUpload(unittest.TestCase):
    """Tests for POST /v1/uploads — reference-first file upload."""

    def setUp(self) -> None:
        self.handler = GatewayUploadHandler()
        self.ctx = _make_auth_ctx("t1")

    def test_upload_returns_references(self) -> None:
        """Upload a file, assert response has upload_id, payload_ref, content_ref, content_hash, reference_only."""
        result = self.handler.handle_upload(
            filename="contract.docx",
            content_bytes=b"hello world",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            tenant_id="t1",
            conversation_id="c1",
        )
        self.assertIsInstance(result, UploadResult)
        self.assertTrue(result.upload_id)
        self.assertTrue(result.payload_ref)
        self.assertTrue(result.content_ref)
        self.assertTrue(result.content_hash)
        # Verify via request handler
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"hello").decode(),
            "mime_type": "text/plain",
            "conversation_id": "c1",
        }
        resp = handle_upload_request(self.handler, self.ctx, body)
        self.assertTrue(resp["upload_id"])
        self.assertTrue(resp["payload_ref"])
        self.assertTrue(resp["content_ref"])
        self.assertTrue(resp["content_hash"])
        self.assertTrue(resp["reference_only"])

    def test_upload_no_raw_content(self) -> None:
        """Assert the handler does not store raw content (only hash and references)."""
        result = self.handler.handle_upload(
            filename="secret.txt",
            content_bytes=b"top secret legal content",
            mime_type="text/plain",
            tenant_id="t1",
            conversation_id="c1",
        )
        # The UploadResult should not have any field containing raw content
        self.assertNotIn("content", result.__dict__)
        self.assertNotIn("raw_content", result.__dict__)
        # The content_hash is a SHA-256 hash, not the raw content
        self.assertNotEqual(result.content_hash, "top secret legal content")
        # Verify the hash is correct (SHA-256 of the content)
        import hashlib
        expected_hash = hashlib.sha256(b"top secret legal content").hexdigest()
        self.assertEqual(result.content_hash, expected_hash)
        # The internal store should not contain raw content
        stored = self.handler._uploads[result.upload_id]
        self.assertNotIn("content", stored.__dict__)
        self.assertNotIn("raw_content", stored.__dict__)

    def test_upload_filename_sanitization(self) -> None:
        """Upload with path traversal filename, assert stored filename is sanitized."""
        result = self.handler.handle_upload(
            filename="../../../etc/passwd",
            content_bytes=b"test",
            mime_type="text/plain",
            tenant_id="t1",
            conversation_id="c1",
        )
        self.assertEqual(result.filename, "passwd")

    def test_upload_tenant_isolation(self) -> None:
        """Upload as tenant-1, try to get_upload as tenant-2, assert None."""
        result = self.handler.handle_upload(
            filename="doc.txt",
            content_bytes=b"test",
            mime_type="text/plain",
            tenant_id="t1",
            conversation_id="c1",
        )
        # Same tenant can access
        got = self.handler.get_upload(result.upload_id, tenant_id="t1")
        self.assertIsNotNone(got)
        # Different tenant cannot access
        got2 = self.handler.get_upload(result.upload_id, tenant_id="t2")
        self.assertIsNone(got2)

    def test_upload_payload_ref_format(self) -> None:
        """Assert payload_ref is ref://{tenant_id}/{conversation_id}/{upload_id}/payload."""
        result = self.handler.handle_upload(
            filename="doc.txt",
            content_bytes=b"test",
            mime_type="text/plain",
            tenant_id="t1",
            conversation_id="c1",
        )
        expected = f"ref://t1/c1/{result.upload_id}/payload"
        self.assertEqual(result.payload_ref, expected)

    def test_upload_via_dispatch(self) -> None:
        """Call dispatch("POST", "/v1/uploads", auth_headers, body), assert 200 response."""
        app = _make_app(upload_handler=self.handler)
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"hello").decode(),
            "mime_type": "text/plain",
            "conversation_id": "c1",
        }
        result = asyncio.run(app.dispatch("POST", "/v1/uploads", AUTH_HEADERS, body))
        self.assertEqual(result["status"], 200)
        self.assertIn("upload_id", result)
        self.assertIn("payload_ref", result)
        self.assertTrue(result["reference_only"])

    def test_upload_no_auth(self) -> None:
        """Call dispatch without auth, assert 401."""
        app = _make_app(upload_handler=self.handler)
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"hello").decode(),
            "mime_type": "text/plain",
            "conversation_id": "c1",
        }
        result = asyncio.run(app.dispatch("POST", "/v1/uploads", {}, body))
        self.assertEqual(result["status"], 401)

    def test_upload_tenant_id_in_response(self) -> None:
        """Assert the response includes tenant_id from the auth context."""
        app = _make_app(upload_handler=self.handler)
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"hello").decode(),
            "mime_type": "text/plain",
            "conversation_id": "c1",
        }
        result = asyncio.run(app.dispatch("POST", "/v1/uploads", AUTH_HEADERS, body))
        self.assertIn("tenant_id", result)


# ===========================================================================
# TestArtifacts
# ===========================================================================


class TestArtifacts(unittest.TestCase):
    """Tests for GET /v1/artifacts/{artifact_id} — auth + tenant check."""

    def setUp(self) -> None:
        self.store = GatewayArtifactStore()
        self.store.register_artifact(ArtifactMetadata(
            artifact_id="art-1",
            kind="docx",
            uri_ref="ref://t1/art-1",
            name="contract.docx",
            tenant_id="t1",
            metadata={"run_id": "run-1"},
        ))
        self.ctx_t1 = _make_auth_ctx("t1")
        self.ctx_t2 = _make_auth_ctx("t2")

    def test_register_and_get_artifact(self) -> None:
        """Register an artifact, get it with the correct tenant, assert 200."""
        resp = handle_get_artifact_request(self.store, self.ctx_t1, "art-1")
        self.assertEqual(resp["status"], 200)
        self.assertEqual(resp["artifact_id"], "art-1")
        self.assertEqual(resp["kind"], "docx")
        self.assertEqual(resp["uri_ref"], "ref://t1/art-1")

    def test_artifact_cross_tenant_denied(self) -> None:
        """Register as tenant-1, get as tenant-2, assert 404 (not 403)."""
        resp = handle_get_artifact_request(self.store, self.ctx_t2, "art-1")
        self.assertEqual(resp["status"], 404)
        self.assertNotEqual(resp["status"], 403)

    def test_artifact_not_found(self) -> None:
        """Get a non-existent artifact, assert 404."""
        resp = handle_get_artifact_request(self.store, self.ctx_t1, "nonexistent")
        self.assertEqual(resp["status"], 404)

    def test_artifact_no_raw_content(self) -> None:
        """Assert the response includes uri_ref but NOT raw content."""
        resp = handle_get_artifact_request(self.store, self.ctx_t1, "art-1")
        self.assertIn("uri_ref", resp)
        self.assertNotIn("content", resp)
        self.assertNotIn("raw_content", resp)

    def test_artifact_via_dispatch(self) -> None:
        """Call dispatch("GET", "/v1/artifacts/art-1", auth_headers, None), assert 200."""
        # Need to use an artifact store with tenant_id="default" for static token auth
        store = GatewayArtifactStore()
        store.register_artifact(ArtifactMetadata(
            artifact_id="art-1",
            kind="docx",
            uri_ref="ref://default/art-1",
            name="contract.docx",
            tenant_id="default",
        ))
        app = _make_app(artifact_store=store)
        result = asyncio.run(app.dispatch("GET", "/v1/artifacts/art-1", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["artifact_id"], "art-1")
        self.assertIn("uri_ref", result)

    def test_artifact_no_auth(self) -> None:
        """Call dispatch without auth, assert 401."""
        app = _make_app(artifact_store=self.store)
        result = asyncio.run(app.dispatch("GET", "/v1/artifacts/art-1", {}, None))
        self.assertEqual(result["status"], 401)

    def test_artifact_tenant_id_in_response(self) -> None:
        """Assert the response includes tenant_id."""
        resp = handle_get_artifact_request(self.store, self.ctx_t1, "art-1")
        self.assertIn("tenant_id", resp)
        self.assertEqual(resp["tenant_id"], "t1")


# ===========================================================================
# TestFeedback
# ===========================================================================


class TestFeedback(unittest.TestCase):
    """Tests for POST /v1/feedback — feedback normalization."""

    def setUp(self) -> None:
        self.handler = GatewayFeedbackHandler()
        self.ctx = _make_auth_ctx("t1")

    def test_feedback_up(self) -> None:
        """Submit 'up' feedback, assert action == 'up', event_type == 'rating'."""
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="up",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertEqual(result.action, "up")
        self.assertEqual(result.event_type, "rating")

    def test_feedback_down(self) -> None:
        """Submit 'down' feedback, assert action == 'down', event_type == 'correction'."""
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="down",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertEqual(result.action, "down")
        self.assertEqual(result.event_type, "correction")

    def test_feedback_needs_fix(self) -> None:
        """Submit 'needs_fix' feedback, assert action == 'needs_fix', event_type == 'correction'."""
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="needs_fix",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertEqual(result.action, "needs_fix")
        self.assertEqual(result.event_type, "correction")

    def test_feedback_route_wrong(self) -> None:
        """Submit 'route_wrong' feedback, assert action == 'route_wrong', event_type == 'route_mismatch'."""
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="route_wrong",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertEqual(result.action, "route_wrong")
        self.assertEqual(result.event_type, "route_mismatch")

    def test_feedback_route_wrong_human_review(self) -> None:
        """For route_wrong, assert requires_human_review == True and metadata.no_auto_modify == True."""
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="route_wrong",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        sc = result.feedback_event.skill_candidate
        self.assertIsNotNone(sc)
        self.assertTrue(sc.requires_human_review)
        self.assertEqual(sc.metadata.get("no_auto_modify"), True)

    def test_feedback_invalid_action(self) -> None:
        """Submit 'invalid' action, assert 400 error."""
        body = {
            "conversation_id": "c1",
            "user_id": "u1",
            "action": "invalid",
            "feedback_target": "turn-1",
        }
        resp = handle_submit_feedback_request(self.handler, self.ctx, body)
        self.assertEqual(resp["status"], 400)

    def test_feedback_via_dispatch(self) -> None:
        """Call dispatch("POST", "/v1/feedback", auth_headers, body), assert 200."""
        app = _make_app(feedback_handler=self.handler)
        body = {
            "conversation_id": "c1",
            "user_id": "u1",
            "action": "up",
            "feedback_target": "turn-1",
        }
        result = asyncio.run(app.dispatch("POST", "/v1/feedback", AUTH_HEADERS, body))
        self.assertIn("feedback_id", result)
        self.assertEqual(result["action"], "up")
        self.assertEqual(result["status"], "pending")

    def test_feedback_no_auth(self) -> None:
        """Call dispatch without auth, assert 401."""
        app = _make_app(feedback_handler=self.handler)
        body = {
            "conversation_id": "c1",
            "user_id": "u1",
            "action": "up",
            "feedback_target": "turn-1",
        }
        result = asyncio.run(app.dispatch("POST", "/v1/feedback", {}, body))
        self.assertEqual(result["status"], 401)

    def test_feedback_tenant_id_in_response(self) -> None:
        """Assert the response includes tenant_id."""
        body = {
            "conversation_id": "c1",
            "user_id": "u1",
            "action": "up",
            "feedback_target": "turn-1",
        }
        resp = handle_submit_feedback_request(self.handler, self.ctx, body)
        self.assertIn("tenant_id", resp)
        self.assertEqual(resp["tenant_id"], "t1")

    def test_feedback_no_auto_synthesize(self) -> None:
        """Assert no feedback handler method auto-synthesizes or auto-modifies skills.

        requires_human_review is always True for route_wrong. The handler
        must never auto-synthesize or auto-modify legal conclusion skills.
        """
        # Test route_wrong — requires_human_review must be True
        result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="route_wrong",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        sc = result.feedback_event.skill_candidate
        self.assertIsNotNone(sc)
        self.assertTrue(sc.requires_human_review)
        self.assertEqual(sc.metadata.get("no_auto_modify"), True)
        # The SkillCandidate should be detected but not auto-applied
        self.assertTrue(sc.detected)
        self.assertEqual(sc.source, "route_mismatch")
        self.assertEqual(sc.risk_level, "high")

        # Verify that non-route_wrong feedback does NOT create a skill_candidate
        # (no auto-synthesis for regular feedback)
        up_result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="up",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertIsNone(up_result.feedback_event.skill_candidate)

        down_result = self.handler.submit_feedback(
            conversation_id="c1",
            user_id="u1",
            action="down",
            feedback_target="turn-1",
            tenant_id="t1",
            now=1000,
        )
        self.assertIsNone(down_result.feedback_event.skill_candidate)


# ===========================================================================
# Fixture-based tests
# ===========================================================================


class TestFixtures(unittest.TestCase):
    """Tests using fixture data from upload_requests.json and feedback_requests.json."""

    def test_upload_fixtures_valid(self) -> None:
        """Verify upload fixture file is valid JSON with 3 requests."""
        fixtures = _load_fixture("upload_requests.json")
        self.assertEqual(len(fixtures), 3)
        for item in fixtures:
            self.assertIn("filename", item)
            self.assertIn("content", item)
            self.assertIn("mime_type", item)
            self.assertIn("conversation_id", item)

    def test_feedback_fixtures_valid(self) -> None:
        """Verify feedback fixture file is valid JSON with 5 requests."""
        fixtures = _load_fixture("feedback_requests.json")
        self.assertEqual(len(fixtures), 5)
        for item in fixtures:
            self.assertIn("conversation_id", item)
            self.assertIn("user_id", item)
            self.assertIn("action", item)
            self.assertIn("feedback_target", item)

    def test_upload_all_fixtures(self) -> None:
        """Upload all 3 fixture files and verify they succeed."""
        handler = GatewayUploadHandler()
        ctx = _make_auth_ctx("t1")
        fixtures = _load_fixture("upload_requests.json")
        for item in fixtures:
            resp = handle_upload_request(handler, ctx, item)
            self.assertEqual(resp["status"], 200)
            self.assertTrue(resp["reference_only"])

    def test_feedback_all_fixtures(self) -> None:
        """Submit all 5 fixture feedback requests, verify 4 succeed and 1 fails."""
        handler = GatewayFeedbackHandler()
        ctx = _make_auth_ctx("t1")
        fixtures = _load_fixture("feedback_requests.json")
        results = []
        for item in fixtures:
            resp = handle_submit_feedback_request(handler, ctx, item)
            results.append(resp)
        # First 4 should succeed (up, down, needs_fix, route_wrong)
        for i in range(4):
            self.assertIn("feedback_id", results[i], f"Fixture {i} should succeed: {results[i]}")
        # Last one (invalid_action) should return 400
        self.assertEqual(results[4]["status"], 400)


if __name__ == "__main__":
    unittest.main()
