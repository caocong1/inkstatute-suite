"""Tests for the Gateway skills endpoint (GET /v1/skills*).

Tests cover:
- List skills (GET /v1/skills)
- Search skills (GET /v1/skills/search)
- Get single skill (GET /v1/skills/{skill_id})
- Not found (GET /v1/skills/unknown)
- Auth required (401 without auth headers)
- Tenant ID in response metadata
- Feature flag disabled (503)
- Feature flag enabled (200)
- Read-only (no POST/PUT/DELETE on /v1/skills)
- Dispatch-level integration tests
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.auth import AuthContext, GatewayAuth
from gateway.config import GatewayConfig
from gateway.sessions import GatewaySessionManager
from gateway.skills import GatewaySkillsHandler, handle_skills_request
from gateway.sse import GatewaySseStream
from inkstatute_skill_registry.registry import SkillRegistry
from platform_contract.events import NeutralSkillDescriptor
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac.identity import Identity
from rbac.roles import Role
from rbac.session import InMemorySessionStore


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_TEST_SKILLS = [
    NeutralSkillDescriptor(
        skill_id="skill-1",
        name="Contract Review",
        description="Review contracts for risks",
        metadata={"tags": ["review"], "intent": "drafting", "risk_level": "medium"},
    ),
    NeutralSkillDescriptor(
        skill_id="skill-2",
        name="Legal Research",
        description="Research legal topics",
        metadata={"tags": ["research"], "intent": "research", "risk_level": "low"},
    ),
    NeutralSkillDescriptor(
        skill_id="skill-3",
        name="Citation Audit",
        description="Audit citations in legal documents",
        metadata={"tags": ["review", "citation"], "intent": "review", "risk_level": "high"},
    ),
]


def _make_registry() -> SkillRegistry:
    return SkillRegistry(list(_TEST_SKILLS))


def _make_flags(enabled: bool = True) -> RuntimeFeatureFlags:
    return RuntimeFeatureFlags(skill_registry_enabled=enabled)


def _make_handler(enabled: bool = True) -> GatewaySkillsHandler:
    return GatewaySkillsHandler(
        registry=_make_registry(),
        feature_flags=_make_flags(enabled),
    )


def _make_auth_ctx(tenant_id: str = "tenant-test") -> AuthContext:
    identity = Identity(role=Role.LAWYER, tenant_id=tenant_id)
    return AuthContext(
        identity=identity,
        authenticated=True,
        tenant_id=tenant_id,
        error=None,
    )


_NO_HANDLER = object()  # sentinel for "explicitly no handler"


def _make_app_with_skills(handler: object = _NO_HANDLER) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()

    class FakeRuntime:
        async def create_run(self, req): pass
        async def stream(self, run_id): pass
        async def cancel(self, run_id): pass

    if handler is _NO_HANDLER:
        skills_handler: GatewaySkillsHandler | None = _make_handler()
    else:
        skills_handler = handler if isinstance(handler, GatewaySkillsHandler) else None

    return GatewayApp(
        config,
        runtime=FakeRuntime(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        skills_handler=skills_handler,
    )


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGatewaySkills(unittest.TestCase):
    """Tests for the Gateway skills endpoint."""

    def setUp(self) -> None:
        self.handler = _make_handler()
        self.auth_ctx = _make_auth_ctx()
        self.app = _make_app_with_skills(self.handler)

    # --- Handler-level tests ---

    def test_list_skills(self) -> None:
        """GET /v1/skills returns 200 with items list and count."""
        result = handle_skills_request(self.handler, self.auth_ctx, "/v1/skills", None)
        self.assertEqual(result["status"], 200)
        self.assertIn("items", result)
        self.assertIn("count", result)
        self.assertEqual(result["count"], 3)
        self.assertIsInstance(result["items"], list)

    def test_search_skills(self) -> None:
        """GET /v1/skills/search?tag=review returns 200 with search results."""
        result = handle_skills_request(self.handler, self.auth_ctx, "/v1/skills/search", "tag=review")
        self.assertEqual(result["status"], 200)
        self.assertIn("items", result)
        self.assertIn("count", result)
        # tag=review matches skill-1 (tags includes "review") and skill-3 (tags includes "review")
        self.assertEqual(result["count"], 2)

    def test_get_single_skill(self) -> None:
        """GET /v1/skills/skill-1 returns 200 with skill details."""
        result = handle_skills_request(self.handler, self.auth_ctx, "/v1/skills/skill-1", None)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["skill_id"], "skill-1")
        self.assertEqual(result["name"], "Contract Review")

    def test_get_skill_not_found(self) -> None:
        """GET /v1/skills/nonexistent returns 404."""
        result = handle_skills_request(self.handler, self.auth_ctx, "/v1/skills/nonexistent", None)
        self.assertEqual(result["status"], 404)
        self.assertIn("error", result)

    # --- Dispatch-level tests ---

    def test_skills_require_auth(self) -> None:
        """GET /v1/skills without auth headers returns 401."""
        result = asyncio.run(self.app.dispatch("GET", "/v1/skills", {}, None))
        self.assertEqual(result["status"], 401)

    def test_skills_via_dispatch(self) -> None:
        """GET /v1/skills via dispatch returns 200 with skill items."""
        result = asyncio.run(self.app.dispatch("GET", "/v1/skills", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 200)
        self.assertIn("items", result)
        self.assertEqual(result["count"], 3)

    def test_skills_tenant_id_in_response(self) -> None:
        """Response metadata includes tenant_id from the auth context."""
        result = handle_skills_request(self.handler, self.auth_ctx, "/v1/skills", None)
        self.assertEqual(result["status"], 200)
        metadata = result.get("metadata", {})
        self.assertIn("tenant_id", metadata)
        self.assertEqual(metadata["tenant_id"], "tenant-test")

    def test_skills_feature_flag_disabled(self) -> None:
        """When skill_registry_enabled is False, handler returns 503."""
        handler = _make_handler(enabled=False)
        result = handle_skills_request(handler, self.auth_ctx, "/v1/skills", None)
        self.assertEqual(result["status"], 503)
        self.assertIn("error", result)

    def test_skills_feature_flag_enabled(self) -> None:
        """When skill_registry_enabled is True, handler returns skill data."""
        handler = _make_handler(enabled=True)
        result = handle_skills_request(handler, self.auth_ctx, "/v1/skills", None)
        self.assertEqual(result["status"], 200)
        self.assertIn("items", result)

    def test_skills_read_only(self) -> None:
        """No write operations (POST/PUT/DELETE) on /v1/skills."""
        # POST /v1/skills should not match any route → 404
        result = asyncio.run(self.app.dispatch("POST", "/v1/skills", AUTH_HEADERS, {}))
        self.assertEqual(result["status"], 404)

        # DELETE /v1/skills should not match any route → 404
        result = asyncio.run(self.app.dispatch("DELETE", "/v1/skills", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 404)

        # PUT /v1/skills should not match any route → 404
        result = asyncio.run(self.app.dispatch("PUT", "/v1/skills", AUTH_HEADERS, {}))
        self.assertEqual(result["status"], 404)

    def test_skills_search_via_dispatch(self) -> None:
        """GET /v1/skills/search?tag=review via dispatch returns 200 with search results."""
        result = asyncio.run(self.app.dispatch("GET", "/v1/skills/search?tag=review", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 200)
        self.assertIn("items", result)
        self.assertEqual(result["count"], 2)

    def test_skills_get_single_via_dispatch(self) -> None:
        """GET /v1/skills/skill-1 via dispatch returns 200 with skill details."""
        result = asyncio.run(self.app.dispatch("GET", "/v1/skills/skill-1", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["skill_id"], "skill-1")

    def test_skills_get_not_found_via_dispatch(self) -> None:
        """GET /v1/skills/unknown via dispatch returns 404."""
        result = asyncio.run(self.app.dispatch("GET", "/v1/skills/unknown", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 404)

    def test_skills_no_handler_returns_501(self) -> None:
        """When no skills_handler is injected, /v1/skills returns 501."""
        app = _make_app_with_skills(handler=None)
        result = asyncio.run(app.dispatch("GET", "/v1/skills", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 501)


if __name__ == "__main__":
    unittest.main()
