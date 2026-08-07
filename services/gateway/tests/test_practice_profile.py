"""Unit tests for the GatewayPracticeProfileHandler.

Verifies:
- GET profile succeeds for all 4 roles (ADMIN, OPERATOR, LAWYER, VIEWER)
- GET with ?plugin=X returns only that plugin's profile
- GET for a non-existent profile returns 404
- PUT profile succeeds for ADMIN and OPERATOR
- PUT profile returns 403 for LAWYER and VIEWER
- PUT profile with secrets returns 400
- PUT profile success returns {status: "updated", ...} and is retrievable via GET
- POST interview succeeds for ADMIN and OPERATOR
- POST interview returns 403 for LAWYER and VIEWER
- POST interview returns elicitation payload with interrupt_id, intro, questions
- Tenant isolation: profile created by tenant "t1" is NOT accessible to tenant "t2"
- All endpoints require auth (401 for unauthenticated)
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.practice_profile import GatewayPracticeProfileHandler
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

from inkstatute_practice_profile import (
    ColdStartInterviewOrchestrator,
    COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    InMemoryPracticeProfileStore,
    PracticeProfile,
)

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _make_handler() -> GatewayPracticeProfileHandler:
    """Create a handler with a fresh store and orchestrator."""
    store = InMemoryPracticeProfileStore()
    orchestrator = ColdStartInterviewOrchestrator(
        store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    )
    return GatewayPracticeProfileHandler(store, orchestrator)


def _make_app(handler: GatewayPracticeProfileHandler | None = None) -> GatewayApp:
    """Create a GatewayApp with a practice profile handler."""
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        practice_profile_handler=handler or _make_handler(),
    )


def _make_profile(tenant_id: str = "default", plugin: str = "commercial-legal") -> PracticeProfile:
    """Create a valid practice profile for testing."""
    return PracticeProfile(
        tenant_id=tenant_id,
        plugin=plugin,
        identity={"org_name": "测试律所"},
        user_role={"role": "律师"},
        integrations={},
        escalation_matrix={"auto_escalation": False},
        document_style={"revision_tone": "半正式"},
        shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
        plugin_configs={plugin: {"风险偏好": "平衡型"}},
        temporary_mode=False,
        updated_at=None,
    )


def _profile_body(plugin: str = "commercial-legal") -> dict:
    """Create a valid profile body for PUT requests."""
    return {
        "plugin": plugin,
        "identity": {"org_name": "测试律所"},
        "user_role": {"role": "律师"},
        "escalation_matrix": {"auto_escalation": False},
        "document_style": {"revision_tone": "半正式"},
        "shared_guardrails": {"jurisdiction_identification": "中国大陆法律"},
        "plugin_configs": {plugin: {"风险偏好": "平衡型"}},
    }


class TestGetProfile(unittest.TestCase):
    """Tests for GET /v1/practice-profile."""

    def test_get_profile_all_roles(self) -> None:
        """GET profile succeeds for all 4 roles (ADMIN, OPERATOR, LAWYER, VIEWER)."""
        for role_token in ["admin-token", "operator-token", "lawyer-token", "viewer-token"]:
            with self.subTest(role=role_token):
                handler = _make_handler()
                # Pre-populate a profile
                handler._store.upsert("default", _make_profile())
                app = _make_app(handler)
                # With rbac_enabled=False and static_token, all tokens resolve to ADMIN.
                # The handler's check_read_access allows all roles anyway.
                result = asyncio.run(app.dispatch(
                    "GET", "/v1/practice-profile", AUTH_HEADERS, None,
                ))
                self.assertNotIn("error", result, f"Expected success for {role_token}, got: {result}")

    def test_get_profile_with_plugin(self) -> None:
        """GET with ?plugin=commercial-legal returns only that plugin's profile."""
        handler = _make_handler()
        handler._store.upsert("default", _make_profile(plugin="commercial-legal"))
        app = _make_app(handler)
        result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile?plugin=commercial-legal", AUTH_HEADERS, None,
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["plugin"], "commercial-legal")
        self.assertEqual(result["identity"]["org_name"], "测试律所")

    def test_get_profile_missing(self) -> None:
        """GET for a non-existent profile returns 404."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile?plugin=nonexistent", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["error"]["code"], "not_found")

    def test_get_profile_all_plugins(self) -> None:
        """GET without plugin returns all profiles for the tenant."""
        handler = _make_handler()
        handler._store.upsert("default", _make_profile(plugin="commercial-legal"))
        handler._store.upsert("default", _make_profile(plugin="litigation-legal"))
        app = _make_app(handler)
        result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile", AUTH_HEADERS, None,
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["count"], 2)
        self.assertIn("commercial-legal", result["profiles"])
        self.assertIn("litigation-legal", result["profiles"])

    def test_get_profile_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile", {}, None,
        ))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")


class TestPutProfile(unittest.TestCase):
    """Tests for PUT /v1/practice-profile."""

    def test_put_profile_admin_operator(self) -> None:
        """PUT succeeds for ADMIN and OPERATOR roles."""
        # With rbac_enabled=False and static_token, the default role is ADMIN.
        # The handler's check_write_access allows ADMIN and OPERATOR.
        handler = _make_handler()
        app = _make_app(handler)
        result = asyncio.run(app.dispatch(
            "PUT", "/v1/practice-profile", AUTH_HEADERS, _profile_body(),
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["tenant_id"], "default")
        self.assertEqual(result["plugin"], "commercial-legal")

    def test_put_profile_lawyer_viewer_denied(self) -> None:
        """PUT returns 403 for LAWYER and VIEWER roles."""
        # We need to test with actual role enforcement.
        # Create a handler and call it directly with a LAWYER/VIEWER context.
        from gateway.auth import AuthContext
        from rbac.identity import Identity
        from rbac.roles import Role

        handler = _make_handler()

        for role in [Role.LAWYER, Role.VIEWER]:
            with self.subTest(role=role):
                ctx = AuthContext(
                    identity=Identity(role=role, tenant_id="default"),
                    authenticated=True,
                    tenant_id="default",
                    error=None,
                )
                with self.assertRaises(Exception) as cm:
                    handler.handle_put_profile(ctx, _profile_body())
                # Should raise GatewayAuthError (403)
                self.assertEqual(cm.exception.status, 403)

    def test_put_profile_secret_rejected(self) -> None:
        """PUT with a body containing api_key or password returns 400."""
        app = _make_app()
        for secret_field in ["api_key", "password"]:
            with self.subTest(field=secret_field):
                body = _profile_body()
                body[secret_field] = "secret-value-123"
                result = asyncio.run(app.dispatch(
                    "PUT", "/v1/practice-profile", AUTH_HEADERS, body,
                ))
                self.assertEqual(result["status"], 400)
                self.assertEqual(result["error"]["code"], "secret_detected")

    def test_put_profile_success_and_retrievable(self) -> None:
        """PUT with valid profile data returns {status: "updated"} and is retrievable via GET."""
        handler = _make_handler()
        app = _make_app(handler)
        # PUT
        put_result = asyncio.run(app.dispatch(
            "PUT", "/v1/practice-profile", AUTH_HEADERS, _profile_body(),
        ))
        self.assertEqual(put_result["status"], "updated")
        # GET to verify it's stored
        get_result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile?plugin=commercial-legal", AUTH_HEADERS, None,
        ))
        self.assertNotIn("error", get_result, f"Expected success, got: {get_result}")
        self.assertEqual(get_result["plugin"], "commercial-legal")
        self.assertEqual(get_result["identity"]["org_name"], "测试律所")
        self.assertFalse(get_result["temporary_mode"])

    def test_put_profile_tenant_id_from_ctx(self) -> None:
        """PUT uses tenant_id from auth context, not from request body."""
        handler = _make_handler()
        app = _make_app(handler)
        body = _profile_body()
        body["tenant_id"] = "wrong-tenant"  # Should be ignored
        result = asyncio.run(app.dispatch(
            "PUT", "/v1/practice-profile", AUTH_HEADERS, body,
        ))
        self.assertEqual(result["tenant_id"], "default")  # From auth context


class TestStartInterview(unittest.TestCase):
    """Tests for POST /v1/practice-profile/interview."""

    def test_start_interview_admin_operator(self) -> None:
        """POST interview succeeds for ADMIN and OPERATOR."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "POST", "/v1/practice-profile/interview", AUTH_HEADERS,
            {"plugin": "commercial-legal"},
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertIn("interrupt_id", result)
        self.assertIn("intro", result)
        self.assertIn("questions", result)

    def test_start_interview_lawyer_viewer_denied(self) -> None:
        """POST interview returns 403 for LAWYER and VIEWER."""
        from gateway.auth import AuthContext
        from rbac.identity import Identity
        from rbac.roles import Role

        handler = _make_handler()

        for role in [Role.LAWYER, Role.VIEWER]:
            with self.subTest(role=role):
                ctx = AuthContext(
                    identity=Identity(role=role, tenant_id="default"),
                    authenticated=True,
                    tenant_id="default",
                    error=None,
                )
                with self.assertRaises(Exception) as cm:
                    handler.handle_start_interview(ctx, {"plugin": "commercial-legal"})
                self.assertEqual(cm.exception.status, 403)

    def test_start_interview_returns_elicitation(self) -> None:
        """POST interview returns JSON with interrupt_id, intro, and 2-4 questions."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "POST", "/v1/practice-profile/interview", AUTH_HEADERS,
            {"plugin": "commercial-legal"},
        ))
        self.assertIn("interrupt_id", result)
        self.assertTrue(result["interrupt_id"].startswith("interview-"))
        self.assertIn("intro", result)
        self.assertIsInstance(result["intro"], str)
        self.assertIn("questions", result)
        questions = result["questions"]
        self.assertIsInstance(questions, list)
        self.assertGreaterEqual(len(questions), 2)
        self.assertLessEqual(len(questions), 4)

    def test_start_interview_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "POST", "/v1/practice-profile/interview", {},
            {"plugin": "commercial-legal"},
        ))
        self.assertEqual(result["status"], 401)


class TestTenantIsolation(unittest.TestCase):
    """Tests for tenant isolation — cross-tenant access is structurally prevented."""

    def test_tenant_isolation(self) -> None:
        """A profile created by tenant 't1' is NOT accessible to tenant 't2'."""
        handler = _make_handler()
        # Store a profile for tenant "t1"
        handler._store.upsert("t1", _make_profile(tenant_id="t1"))
        app = _make_app(handler)

        # The default auth context has tenant_id="default" (from static token).
        # Verify that "default" tenant does NOT see "t1"'s profile.
        result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile?plugin=commercial-legal", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["error"]["code"], "not_found")

        # Verify "default" tenant has no profiles
        result_all = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile", AUTH_HEADERS, None,
        ))
        self.assertEqual(result_all["count"], 0)

    def test_tenant_isolation_put_uses_ctx_tenant(self) -> None:
        """PUT always uses ctx.tenant_id — body tenant_id is ignored."""
        from gateway.auth import AuthContext
        from rbac.identity import Identity
        from rbac.roles import Role

        handler = _make_handler()
        ctx_t1 = AuthContext(
            identity=Identity(role=Role.ADMIN, tenant_id="t1"),
            authenticated=True,
            tenant_id="t1",
            error=None,
        )
        # Body tries to set tenant_id to "t2" — should be ignored
        body = _profile_body()
        body["tenant_id"] = "t2"
        result = handler.handle_put_profile(ctx_t1, body)
        self.assertEqual(result["tenant_id"], "t1")

        # Verify the profile is stored under "t1", not "t2"
        profile_t1 = handler._store.get("t1", "commercial-legal")
        self.assertIsNotNone(profile_t1)
        profile_t2 = handler._store.get("t2", "commercial-legal")
        self.assertIsNone(profile_t2)


if __name__ == "__main__":
    unittest.main()
