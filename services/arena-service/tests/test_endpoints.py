"""Tests for ArenaServiceApp routing + OpenAPI docs (SVC-02).

Covers operation constants, _parse_route for all 5 arena endpoints +
OpenAPI, auth-before-routing enforcement, engine delegation, and
OpenAPI 3.1 document generation with BearerAuth security.
"""

from __future__ import annotations

import json
import unittest

from arena_service.app import (
    ArenaServiceApp,
    OPERATION_CANCEL_ARENA,
    OPERATION_CREATE_ARENA,
    OPERATION_GET_OPENAPI,
    OPERATION_STATUS_ARENA,
    OPERATION_STREAM_ARENA,
    OPERATION_USER_ACTION,
    _parse_route,
)
from arena_service.auth import ArenaServiceAuth
from arena_service.config import ArenaServiceConfig
from arena_service.openapi import build_openapi_document, render_openapi_json


class MockEngine:
    """Mock engine callback for create/cancel/action/status handlers."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self.cancelled: list[str] = []
        self.actions: list[dict] = []
        self.queried: list[str] = []

    async def create_arena(self, body: dict) -> dict:
        result = {
            "arena_id": "arena-test-001",
            "status": "created",
            "mode": body.get("mode", ""),
            "agent_slots": body.get("agent_slots", []),
        }
        self.created.append(dict(body))
        return result

    async def cancel_arena(self, arena_id: str) -> dict:
        self.cancelled.append(arena_id)
        return {"arena_id": arena_id, "status": "cancelled"}

    async def user_action(self, arena_id: str, body: dict) -> dict:
        self.actions.append({"arena_id": arena_id, **body})
        return {"arena_id": arena_id, "status": "running"}

    async def status_arena(self, arena_id: str) -> dict:
        self.queried.append(arena_id)
        return {"arena_id": arena_id, "status": "running", "slots": []}


def _make_app(token: str = "secret", engine: object | None = None) -> ArenaServiceApp:
    cfg = ArenaServiceConfig(token=token)
    auth = ArenaServiceAuth(config=cfg)
    return ArenaServiceApp(config=cfg, auth=auth, engine=engine)


class ArenaParseRouteTests(unittest.TestCase):
    """Tests 1-8: operation constants + _parse_route."""

    def test_operation_constants_exist(self):
        # Test 1: all 6 operation constants are defined.
        self.assertEqual(OPERATION_CREATE_ARENA, "create_arena")
        self.assertEqual(OPERATION_STREAM_ARENA, "stream_arena")
        self.assertEqual(OPERATION_CANCEL_ARENA, "cancel_arena")
        self.assertEqual(OPERATION_USER_ACTION, "user_action")
        self.assertEqual(OPERATION_STATUS_ARENA, "status_arena")
        self.assertEqual(OPERATION_GET_OPENAPI, "get_openapi")

    def test_parse_route_create_arena(self):
        # Test 2: POST /v1/arena → (create_arena, {})
        result = _parse_route("POST", "/v1/arena", "/v1")
        self.assertEqual(result, (OPERATION_CREATE_ARENA, {}))

    def test_parse_route_stream_arena(self):
        # Test 3: GET /v1/arena/abc-123/stream → (stream_arena, {arena_id: abc-123})
        result = _parse_route("GET", "/v1/arena/abc-123/stream", "/v1")
        self.assertEqual(result, (OPERATION_STREAM_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_cancel_arena(self):
        # Test 4: POST /v1/arena/abc-123/cancel → (cancel_arena, {arena_id: abc-123})
        result = _parse_route("POST", "/v1/arena/abc-123/cancel", "/v1")
        self.assertEqual(result, (OPERATION_CANCEL_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_user_action(self):
        # Test 5: POST /v1/arena/abc-123/action → (user_action, {arena_id: abc-123})
        result = _parse_route("POST", "/v1/arena/abc-123/action", "/v1")
        self.assertEqual(result, (OPERATION_USER_ACTION, {"arena_id": "abc-123"}))

    def test_parse_route_status_arena(self):
        # Test 6: GET /v1/arena/abc-123/status → (status_arena, {arena_id: abc-123})
        result = _parse_route("GET", "/v1/arena/abc-123/status", "/v1")
        self.assertEqual(result, (OPERATION_STATUS_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_trailing_slash_tolerant(self):
        # Test 7: trailing slash also matches.
        result = _parse_route("GET", "/v1/arena/abc-123/status/", "/v1")
        self.assertEqual(result, (OPERATION_STATUS_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_unknown_method_returns_none(self):
        # Test 8: DELETE /v1/arena → None (unknown method).
        result = _parse_route("DELETE", "/v1/arena", "/v1")
        self.assertIsNone(result)


class ArenaDispatchTests(unittest.IsolatedAsyncioTestCase):
    """Tests 9-10: dispatch auth-before-routing + engine delegation."""

    async def test_dispatch_no_token_returns_401(self):
        # Test 9: dispatch with no token returns 401 unauthorized (auth before routing).
        app = _make_app(token="secret", engine=MockEngine())
        result = await app.dispatch(
            "POST", "/v1/arena", {}, {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    async def test_dispatch_create_arena_delegates_to_engine(self):
        # Test 10: valid token + POST /v1/arena returns arena_id + status created.
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "POST",
            "/v1/arena",
            {"Authorization": "Bearer secret"},
            {"mode": "mode1_parallel", "agent_slots": ["slot-0", "slot-1"], "task": "test"},
        )
        self.assertEqual(result["status"], 201)
        body = result["body"]
        self.assertEqual(body["arena_id"], "arena-test-001")
        self.assertEqual(body["status"], "created")
        self.assertEqual(len(engine.created), 1)
        self.assertEqual(engine.created[0]["mode"], "mode1_parallel")

    async def test_dispatch_non_localhost_rejected_before_auth(self):
        # Extra: non-localhost rejected with 403 before auth check.
        app = _make_app(token="secret", engine=MockEngine())
        result = await app.dispatch(
            "POST", "/v1/arena", {"Authorization": "Bearer secret"},
            {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
            client_address="192.168.1.1",
        )
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["error"]["code"], "forbidden_remote")

    async def test_dispatch_cancel_arena(self):
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "POST", "/v1/arena/abc/cancel", {"Authorization": "Bearer secret"}, {},
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["status"], "cancelled")
        self.assertEqual(engine.cancelled, ["abc"])

    async def test_dispatch_user_action(self):
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "POST", "/v1/arena/abc/action", {"Authorization": "Bearer secret"},
            {"action": "select", "selection": "slot-0"},
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(len(engine.actions), 1)

    async def test_dispatch_status_arena(self):
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "GET", "/v1/arena/abc/status", {"Authorization": "Bearer secret"}, None,
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["status"], "running")

    async def test_dispatch_openapi_requires_auth(self):
        app = _make_app(token="secret", engine=MockEngine())
        # no token → 401
        result = await app.dispatch("GET", "/v1/openapi", {}, None)
        self.assertEqual(result["status"], 401)
        # valid token → 200 with doc
        result = await app.dispatch("GET", "/v1/openapi", {"Authorization": "Bearer secret"}, None)
        self.assertEqual(result["status"], 200)
        self.assertIn("openapi", result["body"])

    async def test_dispatch_no_engine_returns_501(self):
        app = _make_app(token="secret", engine=None)
        result = await app.dispatch(
            "POST", "/v1/arena", {"Authorization": "Bearer secret"},
            {"mode": "mode1_parallel", "agent_slots": ["s0"], "task": "t"},
        )
        self.assertEqual(result["status"], 501)
        self.assertEqual(result["error"]["code"], "not_implemented")


class ArenaOpenApiTests(unittest.TestCase):
    """Tests 11-13: OpenAPI document generation."""

    def test_build_openapi_document_has_correct_structure(self):
        # Test 11: build_openapi_document returns dict with openapi 3.1.0, Arena title, all paths.
        doc = build_openapi_document("/v1")
        self.assertEqual(doc["openapi"], "3.1.0")
        self.assertIn("Arena", doc["info"]["title"])
        paths = doc["paths"]
        # all 5 arena endpoints + openapi
        self.assertIn("/v1/arena", paths)
        self.assertIn("/v1/arena/{arena_id}/stream", paths)
        self.assertIn("/v1/arena/{arena_id}/cancel", paths)
        self.assertIn("/v1/arena/{arena_id}/action", paths)
        self.assertIn("/v1/arena/{arena_id}/status", paths)
        self.assertIn("/v1/openapi", paths)

    def test_render_openapi_json_is_valid_json(self):
        # Test 12: render_openapi_json returns valid JSON string.
        doc = build_openapi_document("/v1")
        rendered = render_openapi_json(doc)
        self.assertIsInstance(rendered, str)
        parsed = json.loads(rendered)
        self.assertEqual(parsed["openapi"], "3.1.0")

    def test_openapi_has_bearer_auth_security_on_all_operations(self):
        # Test 13: securitySchemes with BearerAuth, all operations have security.
        doc = build_openapi_document("/v1")
        schemes = doc["components"]["securitySchemes"]
        self.assertIn("BearerAuth", schemes)
        self.assertEqual(schemes["BearerAuth"]["type"], "http")
        self.assertEqual(schemes["BearerAuth"]["scheme"], "bearer")
        for path_str, path_item in doc["paths"].items():
            for method, operation in path_item.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    self.assertIn(
                        "security",
                        operation,
                        f"{method.upper()} {path_str} missing security requirement",
                    )
                    security = operation["security"]
                    self.assertTrue(
                        any("BearerAuth" in req for req in security),
                        f"{method.upper()} {path_str} security missing BearerAuth",
                    )


if __name__ == "__main__":
    unittest.main()
