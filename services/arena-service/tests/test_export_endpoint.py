"""Integration tests for the POST /v1/arena/{arena_id}/export endpoint.

Covers:
- Route parsing + dispatch for the export endpoint.
- Auth-before-routing enforcement (401 without token, 403 non-localhost).
- Input validation (empty arena_id → 400, missing output_path → 400).
- Engine delegation via getattr (501 when engine lacks export_arena).
- Real ArenaServiceEngine.export_arena with mocked TrackChangesBuilder
  (the sibling repo lawfirm-profile may not be cloned in CI).

The track-changes module is mocked via patching
``_load_trackchanges_module`` so the test does NOT depend on
``lawfirm-profile/scripts/contract_review_trackchanges.py`` being
present on the filesystem.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from arena_service.app import (
    ArenaServiceApp,
    OPERATION_EXPORT_ARENA,
    _parse_route,
)
from arena_service.auth import ArenaServiceAuth
from arena_service.config import ArenaServiceConfig
from arena_service.engine_integration import ArenaServiceEngine

from arena_engine.mode3 import Mode3Result
from arena_engine.review import ConfidenceLevel, ReviewFinding, SeverityLevel
from platform_contract.arena_contract import ArenaWorkflowConfig


# ---------------------------------------------------------------------------
# Mock engine for app-level routing / auth / validation tests
# ---------------------------------------------------------------------------


class MockEngine:
    """Mock engine with an export_arena method for app-level tests."""

    def __init__(self) -> None:
        self.exported: list[tuple[str, dict]] = []

    async def export_arena(self, arena_id: str, body: dict) -> dict:
        self.exported.append((arena_id, dict(body)))
        return {"ok": True, "output_path": body.get("output_path", "")}


def _make_app(token: str = "secret", engine: object | None = None) -> ArenaServiceApp:
    cfg = ArenaServiceConfig(token=token)
    auth = ArenaServiceAuth(config=cfg)
    return ArenaServiceApp(config=cfg, auth=auth, engine=engine)


# ---------------------------------------------------------------------------
# Route parsing tests
# ---------------------------------------------------------------------------


class ExportParseRouteTests(unittest.TestCase):
    """Tests for _parse_route matching the export endpoint."""

    def test_parse_route_export_arena(self):
        result = _parse_route("POST", "/v1/arena/abc-123/export", "/v1")
        self.assertEqual(result, (OPERATION_EXPORT_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_export_trailing_slash(self):
        result = _parse_route("POST", "/v1/arena/abc-123/export/", "/v1")
        self.assertEqual(result, (OPERATION_EXPORT_ARENA, {"arena_id": "abc-123"}))

    def test_parse_route_export_wrong_method(self):
        result = _parse_route("GET", "/v1/arena/abc-123/export", "/v1")
        self.assertIsNone(result)

    def test_operation_export_arena_constant(self):
        self.assertEqual(OPERATION_EXPORT_ARENA, "export_arena")


# ---------------------------------------------------------------------------
# App-level dispatch tests (routing, auth, validation, delegation)
# ---------------------------------------------------------------------------


class ExportDispatchTests(unittest.IsolatedAsyncioTestCase):
    """Tests for dispatch routing + auth + validation + engine delegation."""

    async def test_export_valid(self):
        """POST /v1/arena/{id}/export with valid body returns 200 + ok:True."""
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {"Authorization": "Bearer secret"},
            {"output_path": "/tmp/test_export.docx"},
        )
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["body"]["ok"])
        self.assertEqual(result["body"]["output_path"], "/tmp/test_export.docx")
        self.assertEqual(len(engine.exported), 1)
        self.assertEqual(engine.exported[0][0], "arena-001")

    async def test_export_empty_arena_id(self):
        """POST /v1/arena//export → 400 (empty arena_id)."""
        # _parse_route with empty arena_id won't match the 3-part pattern,
        # so the route returns None → 404.  But the handler also validates
        # arena_id.  Test the handler-level validation by using a path that
        # matches but has an empty arena_id via path_params manipulation.
        # In practice, /v1/arena//export has parts ["arena", "export"] (len 2)
        # after filtering empties, so it won't match.  Test the handler
        # directly instead.
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        # Simulate empty arena_id by calling the handler directly.
        from arena_service.auth import AuthContext
        ctx = AuthContext(authenticated=True, token_valid=True, error=None)
        result = await app._handle_export_arena(ctx, {"arena_id": ""}, {"output_path": "/tmp/x.docx"})
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    async def test_export_missing_output_path(self):
        """POST /v1/arena/{id}/export with empty body → 400."""
        engine = MockEngine()
        app = _make_app(token="secret", engine=engine)
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {"Authorization": "Bearer secret"},
            {},
        )
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    async def test_export_no_auth(self):
        """POST without Authorization header → 401."""
        app = _make_app(token="secret", engine=MockEngine())
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {},
            {"output_path": "/tmp/test_export.docx"},
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    async def test_export_remote_rejected(self):
        """POST from non-localhost address → 403 (before auth)."""
        app = _make_app(token="secret", engine=MockEngine())
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {"Authorization": "Bearer secret"},
            {"output_path": "/tmp/test_export.docx"},
            client_address="192.168.1.1",
        )
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["error"]["code"], "forbidden_remote")

    async def test_export_no_engine_returns_501(self):
        """POST with no engine → 501 not_implemented."""
        app = _make_app(token="secret", engine=None)
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {"Authorization": "Bearer secret"},
            {"output_path": "/tmp/test_export.docx"},
        )
        self.assertEqual(result["status"], 501)
        self.assertEqual(result["error"]["code"], "not_implemented")

    async def test_export_engine_lacks_method_returns_501(self):
        """POST with engine that lacks export_arena → 501."""
        class EngineWithoutExport:
            async def create_arena(self, body):
                return {}
        app = _make_app(token="secret", engine=EngineWithoutExport())
        result = await app.dispatch(
            "POST",
            "/v1/arena/arena-001/export",
            {"Authorization": "Bearer secret"},
            {"output_path": "/tmp/test_export.docx"},
        )
        self.assertEqual(result["status"], 501)
        self.assertEqual(result["error"]["code"], "not_implemented")


# ---------------------------------------------------------------------------
# Engine-level export_arena test with mocked TrackChangesBuilder
# ---------------------------------------------------------------------------


class _MockTrackChangesBuilder:
    """Mock TrackChangesBuilder that does not require lxml or a real docx."""

    def __init__(self, input_path: str) -> None:
        self._input_path = input_path

    def process(self) -> list[tuple]:
        return [(1, "P2", "applied", "mock comment")]

    def save(self, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"mock docx content")


class _MockTrackChangesModule:
    """Mock module mimicking contract_review_trackchanges.py interface."""

    TrackChangesBuilder = _MockTrackChangesBuilder
    REVIEWER = "mock-reviewer"
    REVIEW_ITEMS: list[dict] = []


class ExportEngineIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Tests for ArenaServiceEngine.export_arena with mocked track-changes."""

    def _make_engine(self) -> ArenaServiceEngine:
        cfg = ArenaServiceConfig(token="secret")
        return ArenaServiceEngine(config=cfg)

    def _inject_arena_state(
        self,
        engine: ArenaServiceEngine,
        arena_id: str,
        input_docx_path: str,
    ) -> None:
        """Inject a completed Mode 3 arena result + config into the engine."""
        # Inject the arena config with input_docx_path in metadata.
        config = ArenaWorkflowConfig(
            arena_id=arena_id,
            mode="mode3_arena_review",
            agent_slots=["slot-0", "slot-1"],
            task_instruction="test task",
            metadata={"input_docx_path": input_docx_path},
        )
        engine._engine._configs[arena_id] = config

        # Inject a Mode3Result with synthesis content + review findings.
        findings = [
            ReviewFinding(
                description="Finding about clause 3",
                confidence=ConfidenceLevel.LIKELY,
                severity=SeverityLevel.HIGH,
                confirmed=True,
                source_slot="slot-1",
                reviewed_slot="slot-0",
            ),
            ReviewFinding(
                description="Finding about clause 5",
                confidence=ConfidenceLevel.POSSIBLE,
                severity=SeverityLevel.LOW,
                confirmed=False,
                source_slot="slot-0",
                reviewed_slot="slot-1",
            ),
        ]
        result = Mode3Result(
            arena_id=arena_id,
            review_findings={"slot-0": findings},
            synthesis_content="综合最终版内容",
        )
        engine._engine._results[arena_id] = result

    async def test_export_arena_with_mocked_trackchanges(self):
        """export_arena delegates to create_document_generate_tool and returns ok."""
        engine = self._make_engine()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_docx = Path(tmpdir) / "input.docx"
            input_docx.write_bytes(b"mock input docx")
            output_docx = Path(tmpdir) / "output.docx"

            self._inject_arena_state(engine, "arena-export-001", str(input_docx))

            # Mock _load_trackchanges_module so the test does not depend
            # on lawfirm-profile/scripts/contract_review_trackchanges.py.
            with patch(
                "inkstatute_agent_core.tools.document_generate._load_trackchanges_module",
                return_value=_MockTrackChangesModule,
            ):
                result = await engine.export_arena(
                    "arena-export-001",
                    {"output_path": str(output_docx)},
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["output_path"], str(output_docx))
            self.assertTrue(output_docx.exists())

    async def test_export_arena_no_synthesis_result(self):
        """export_arena returns error when arena has no synthesis result."""
        engine = self._make_engine()
        result = await engine.export_arena(
            "arena-no-result",
            {"output_path": "/tmp/test.docx"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no_synthesis_result")

    async def test_export_arena_no_input_docx(self):
        """export_arena returns error when arena config lacks input_docx_path."""
        engine = self._make_engine()

        # Inject a result but no input_docx_path in config metadata.
        config = ArenaWorkflowConfig(
            arena_id="arena-no-input",
            mode="mode3_arena_review",
            agent_slots=["slot-0"],
            task_instruction="test",
            metadata={},
        )
        engine._engine._configs["arena-no-input"] = config
        result_obj = Mode3Result(
            arena_id="arena-no-input",
            synthesis_content="some synthesis",
        )
        engine._engine._results["arena-no-input"] = result_obj

        result = await engine.export_arena(
            "arena-no-input",
            {"output_path": "/tmp/test.docx"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no_input_docx")

    async def test_export_arena_missing_output_path(self):
        """export_arena returns error when output_path is missing."""
        engine = self._make_engine()
        result = await engine.export_arena("arena-001", {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "output_path is required")


# ---------------------------------------------------------------------------
# OpenAPI document test — export path is present
# ---------------------------------------------------------------------------


class ExportOpenApiTests(unittest.TestCase):
    """Tests that the OpenAPI document includes the export path."""

    def test_openapi_includes_export_path(self):
        from arena_service.openapi import build_openapi_document
        doc = build_openapi_document("/v1")
        paths = doc["paths"]
        self.assertIn("/v1/arena/{arena_id}/export", paths)
        export_op = paths["/v1/arena/{arena_id}/export"]["post"]
        self.assertEqual(export_op["operationId"], "exportArena")
        self.assertIn("security", export_op)

    def test_openapi_has_export_schemas(self):
        from arena_service.openapi import build_openapi_document
        doc = build_openapi_document("/v1")
        schemas = doc["components"]["schemas"]
        self.assertIn("ExportArenaRequest", schemas)
        self.assertIn("ExportArenaResult", schemas)


if __name__ == "__main__":
    unittest.main()
