"""Unit tests for the Gateway HTTP client — SSE parsing, auth headers, error handling.

All tests are network-free, using ``unittest.mock.patch`` and
``unittest.mock.MagicMock`` to mock ``urllib.request.urlopen`` and
``http.client.HTTPConnection``.
"""

from __future__ import annotations

import inspect
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from wecom_service.gateway_client import (
    GatewayClient,
    GatewayClientConfig,
    GatewayClientError,
    _build_headers,
    _parse_sse_frame,
)


class TestGatewayClient(unittest.TestCase):
    """Unit tests for ``gateway_client.py``."""

    # ------------------------------------------------------------------
    # Config and headers
    # ------------------------------------------------------------------

    def test_config_creation(self) -> None:
        """GatewayClientConfig creates a config with correct fields."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        self.assertEqual(config.base_url, "http://localhost:8081")
        self.assertEqual(config.bearer_token, "test-token")
        self.assertEqual(config.tenant_id, "default-tenant")
        self.assertEqual(config.timeout_seconds, 30.0)

    def test_build_headers_includes_bearer_token(self) -> None:
        """_build_headers returns a dict with Bearer token."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        headers = _build_headers(config)
        self.assertEqual(headers["Authorization"], "Bearer test-token")

    def test_build_headers_includes_content_type(self) -> None:
        """_build_headers returns a dict with Content-Type."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        headers = _build_headers(config)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_build_headers_with_extra(self) -> None:
        """_build_headers includes extra headers when provided."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        headers = _build_headers(config, extra={"Last-Event-ID": "42"})
        self.assertEqual(headers["Last-Event-ID"], "42")
        self.assertEqual(headers["Authorization"], "Bearer test-token")

    # ------------------------------------------------------------------
    # SSE frame parsing
    # ------------------------------------------------------------------

    def test_parse_sse_frame_complete(self) -> None:
        """_parse_sse_frame parses a complete SSE frame."""
        result = _parse_sse_frame([
            'id: evt-1',
            'event: message.delta',
            'data: {"delta":"hello"}',
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["event_id"], "evt-1")
        self.assertEqual(result["event_type"], "message.delta")
        self.assertEqual(result["payload"], {"delta": "hello"})

    def test_parse_sse_frame_multiline_data(self) -> None:
        """_parse_sse_frame concatenates multi-line data fields."""
        result = _parse_sse_frame([
            'id: evt-2',
            'event: message.completed',
            'data: {"content":',
            'data: "hello world"}',
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["event_id"], "evt-2")
        self.assertEqual(result["event_type"], "message.completed")
        self.assertEqual(result["payload"], {"content": "hello world"})

    def test_parse_sse_frame_empty(self) -> None:
        """_parse_sse_frame returns None for empty (incomplete) frames."""
        result = _parse_sse_frame([])
        self.assertIsNone(result)

    def test_parse_sse_frame_no_data(self) -> None:
        """_parse_sse_frame returns a dict with empty payload when no data line."""
        result = _parse_sse_frame([
            'id: evt-3',
            'event: session.started',
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["event_id"], "evt-3")
        self.assertEqual(result["event_type"], "session.started")
        self.assertEqual(result["payload"], {})

    # ------------------------------------------------------------------
    # Error class
    # ------------------------------------------------------------------

    def test_gateway_client_error_fields(self) -> None:
        """GatewayClientError has status, code, message fields."""
        error = GatewayClientError(
            status=401,
            code="unauthorized",
            message="Invalid token",
        )
        self.assertEqual(error.status, 401)
        self.assertEqual(error.code, "unauthorized")
        self.assertEqual(error.message, "Invalid token")

    # ------------------------------------------------------------------
    # HTTP request body tests (mocked)
    # ------------------------------------------------------------------

    def test_create_session_request_body(self) -> None:
        """create_session sends POST /v1/sessions with correct body."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
            tenant_id="test-tenant",
        )
        client = GatewayClient(config)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "session_id": "sess-1",
            "tenant_id": "test-tenant",
        }).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = client.create_session(conversation_id="conv-1")

        self.assertEqual(result["session_id"], "sess-1")
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        self.assertEqual(req.method, "POST")
        self.assertIn("/v1/sessions", req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["conversation_id"], "conv-1")
        self.assertEqual(body["tenant_id"], "test-tenant")

    def test_create_run_request_body(self) -> None:
        """create_run sends POST /v1/runs with turn, solution, session_id."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        client = GatewayClient(config)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "run_id": "run-1",
            "status": "running",
        }).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = client.create_run(
                turn={"content": "hello"},
                solution={"solution_id": "test"},
                session_id="sess-1",
            )

        self.assertEqual(result["run_id"], "run-1")
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        self.assertEqual(req.method, "POST")
        self.assertIn("/v1/runs", req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["turn"], {"content": "hello"})
        self.assertEqual(body["solution"], {"solution_id": "test"})
        self.assertEqual(body["session_id"], "sess-1")

    # ------------------------------------------------------------------
    # SSE streaming tests (mocked)
    # ------------------------------------------------------------------

    def test_stream_events_last_event_id_header(self) -> None:
        """stream_events includes Last-Event-ID header for reconnection."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        client = GatewayClient(config)

        sse_frame = (
            'id: evt-1\nevent: message.delta\ndata: {"delta":"hi"}\n\n'
        )
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__iter__ = MagicMock(
            return_value=iter([sse_frame.encode("utf-8")]),
        )

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("http.client.HTTPConnection", return_value=mock_conn):
            events = list(client.stream_events("run-1", last_event_id=42))

        # Verify Last-Event-ID header was sent
        call_args = mock_conn.request.call_args
        headers = call_args.kwargs.get("headers", {})
        self.assertIn("Last-Event-ID", headers)
        self.assertEqual(headers["Last-Event-ID"], "42")
        self.assertEqual(headers["Accept"], "text/event-stream")

    def test_stream_events_yields_parsed_events(self) -> None:
        """stream_events yields parsed event dicts from SSE frames."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        client = GatewayClient(config)

        frames = [
            'id: evt-1\nevent: message.delta\ndata: {"delta":"hello"}\n\n',
            'id: evt-2\nevent: message.completed\ndata: {"content":"world"}\n\n',
        ]
        raw_lines = []
        for frame in frames:
            for line in frame.split("\n"):
                raw_lines.append(line.encode("utf-8"))

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__iter__ = MagicMock(return_value=iter(raw_lines))

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("http.client.HTTPConnection", return_value=mock_conn):
            events = list(client.stream_events("run-1"))

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_id"], "evt-1")
        self.assertEqual(events[0]["event_type"], "message.delta")
        self.assertEqual(events[0]["payload"], {"delta": "hello"})
        self.assertEqual(events[1]["event_id"], "evt-2")
        self.assertEqual(events[1]["event_type"], "message.completed")
        self.assertEqual(events[1]["payload"], {"content": "world"})

    # ------------------------------------------------------------------
    # Artifact download test (mocked)
    # ------------------------------------------------------------------

    def test_download_artifact_returns_bytes(self) -> None:
        """download_artifact returns the raw artifact bytes."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="test-token",
        )
        client = GatewayClient(config)

        artifact_data = b"fake-document-content"
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = artifact_data

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with patch("http.client.HTTPConnection", return_value=mock_conn):
            result = client.download_artifact("art-1")

        self.assertEqual(result, artifact_data)
        mock_conn.request.assert_called_once()
        call_args = mock_conn.request.call_args
        self.assertIn("/v1/artifacts/art-1", call_args.args[1])

    # ------------------------------------------------------------------
    # Error handling test (mocked)
    # ------------------------------------------------------------------

    def test_error_on_non_2xx_response(self) -> None:
        """Non-2xx responses raise GatewayClientError."""
        config = GatewayClientConfig(
            base_url="http://localhost:8081",
            bearer_token="bad-token",
        )
        client = GatewayClient(config)

        mock_resp = MagicMock()
        mock_resp.status = 401
        mock_resp.read.return_value = json.dumps({
            "code": "unauthorized",
            "message": "Invalid token",
        }).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        import urllib.error

        error = urllib.error.HTTPError(
            url="http://localhost:8081/v1/sessions",
            code=401,
            msg="Unauthorized",
            hdrs=MagicMock(),
            fp=io.BytesIO(json.dumps({
                "code": "unauthorized",
                "message": "Invalid token",
            }).encode("utf-8")),
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(GatewayClientError) as ctx:
                client.create_session(conversation_id="conv-1")

        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.code, "unauthorized")

    # ------------------------------------------------------------------
    # No gateway package import test
    # ------------------------------------------------------------------

    def test_no_gateway_package_import(self) -> None:
        """gateway_client.py does not import from the gateway package."""
        from wecom_service import gateway_client as gc_mod
        source = inspect.getsource(gc_mod)
        # Check for absence of 'from gateway' or 'import gateway'
        self.assertNotIn("from gateway", source)
        self.assertNotIn("import gateway", source)


if __name__ == "__main__":
    unittest.main()
