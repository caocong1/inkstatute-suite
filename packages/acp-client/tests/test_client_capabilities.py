"""Tests for client_capabilities advertisement, request handler registration, and backward compat.

Covers:
- clientCapabilities sent in initialize when configured
- clientCapabilities NOT sent when None (Gateway backward compat)
- request handler registration and dispatch
- unregistered handler returns JSON-RPC error -32601 (not crash)
- ACPBackendConfig.client_capabilities defaults to None
- ACPBackendAdapter passes client_capabilities to ACPClient
"""

from __future__ import annotations

import unittest
from typing import Any

from inkstatute_acp_client.adapter import ACPBackendConfig
from inkstatute_acp_client.capability_negotiation import RequiredCapabilities
from inkstatute_acp_client.client import ACPClient


# ---------------------------------------------------------------------------
# Mock transport — captures sent messages, returns canned responses
# ---------------------------------------------------------------------------


class MockTransport:
    """Minimal ACPTransport implementation for unit tests.

    Captures all sent messages in ``sent_messages`` and returns a canned
    initialize response from :meth:`receive`.
    """

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self._canned_response: dict = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": 1,
                "agentInfo": {"name": "mock", "version": "0.1.0"},
                "capabilities": {"streaming": True},
            },
        }
        self._closed = False

    async def start(
        self,
        command: tuple[str, ...],
        env: dict[str, str] | None = None,
    ) -> None:
        pass

    async def send(self, message: dict) -> None:
        self.sent_messages.append(message)

    async def receive(self) -> dict:
        return self._canned_response

    async def receive_notification(self) -> dict | None:
        return None

    async def receive_inbound_request(self) -> dict | None:
        return None

    async def close(self) -> None:
        self._closed = True

    @property
    def pid(self) -> int | None:
        return 99999


# ---------------------------------------------------------------------------
# Async tests: capabilities + handler dispatch
# ---------------------------------------------------------------------------


class ClientCapabilitiesTests(unittest.IsolatedAsyncioTestCase):
    """Tests 1, 2, 5, 6, 7, 8 — async behavior tests."""

    async def test_client_capabilities_sent_when_configured(self) -> None:
        """Test 1: clientCapabilities.fs.readTextFile == True in initialize request."""
        transport = MockTransport()
        client = ACPClient(
            transport,
            RequiredCapabilities(streaming=True),
            client_capabilities={"fs": {"readTextFile": True}},
        )
        await client.initialize()
        # The first sent message should be the initialize request
        init_request = transport.sent_messages[0]
        self.assertEqual(init_request["method"], "initialize")
        self.assertIn("clientCapabilities", init_request["params"])
        self.assertEqual(
            init_request["params"]["clientCapabilities"]["fs"]["readTextFile"],
            True,
        )

    async def test_client_capabilities_not_sent_when_none(self) -> None:
        """Test 2: clientCapabilities key absent when client_capabilities is None."""
        transport = MockTransport()
        client = ACPClient(
            transport,
            RequiredCapabilities(streaming=True),
            client_capabilities=None,
        )
        await client.initialize()
        init_request = transport.sent_messages[0]
        self.assertEqual(init_request["method"], "initialize")
        self.assertNotIn("clientCapabilities", init_request["params"])

    async def test_request_handler_dispatch(self) -> None:
        """Test 5: registered handler is called and its return value sent as response."""
        transport = MockTransport()
        client = ACPClient(transport, RequiredCapabilities(streaming=True))

        called_with: dict = {}

        def handler(params: dict) -> dict:
            called_with.update(params)
            return {"content": "file contents"}

        client.register_request_handler("fs/read_text_file", handler)

        await client.handle_inbound_request(
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "fs/read_text_file",
                "params": {"path": "/x.md"},
            }
        )

        self.assertEqual(called_with, {"path": "/x.md"})
        # The last sent message should be the response
        response = transport.sent_messages[-1]
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 99)
        self.assertEqual(response["result"], {"content": "file contents"})

    async def test_unregistered_handler_returns_error_not_crash(self) -> None:
        """Test 6: unregistered method returns -32601 error, no exception."""
        transport = MockTransport()
        client = ACPClient(transport, RequiredCapabilities(streaming=True))

        # No handler registered for "fs/read_text_file"
        await client.handle_inbound_request(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "fs/read_text_file",
                "params": {"path": "/x.md"},
            }
        )

        response = transport.sent_messages[-1]
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 42)
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32601)
        self.assertIn("fs/read_text_file", response["error"]["message"])

    def test_acpbackend_config_accepts_client_capabilities(self) -> None:
        """Test 7: ACPBackendConfig stores client_capabilities dict."""
        config = ACPBackendConfig(
            backend_id="test",
            command=("python", "echo"),
            client_capabilities={"fs": {"readTextFile": True}},
        )
        self.assertEqual(config.client_capabilities, {"fs": {"readTextFile": True}})

    async def test_adapter_passes_client_capabilities_to_client(self) -> None:
        """Test 8: ACPBackendAdapter creates ACPClient with config.client_capabilities.

        We verify by inspecting the ACPClient._client_capabilities attribute
        after the adapter creates it.  We use a custom transport factory that
        returns our MockTransport so we can intercept the client.
        """
        from inkstatute_acp_client.adapter import ACPBackendAdapter

        config = ACPBackendConfig(
            backend_id="test",
            command=("python", "echo"),
            client_capabilities={"fs": {"readTextFile": True}},
        )

        captured_clients: list[ACPClient] = []
        mock_transport = MockTransport()

        def factory(cfg: ACPBackendConfig) -> Any:
            return mock_transport

        adapter = ACPBackendAdapter(config, transport_factory=factory)

        # Monkey-patch ACPClient creation to capture the client
        original_init = ACPClient.__init__

        def capturing_init(self_client: ACPClient, *args: Any, **kwargs: Any) -> None:
            original_init(self_client, *args, **kwargs)
            captured_clients.append(self_client)

        ACPClient.__init__ = capturing_init  # type: ignore[assignment]
        try:
            await adapter.bootstrap_check()
        finally:
            ACPClient.__init__ = original_init  # type: ignore[assignment]

        self.assertEqual(len(captured_clients), 1)
        self.assertEqual(
            captured_clients[0]._client_capabilities,
            {"fs": {"readTextFile": True}},
        )


# ---------------------------------------------------------------------------
# Sync tests: backward compatibility
# ---------------------------------------------------------------------------


class BackwardCompatTests(unittest.TestCase):
    """Tests 3, 4 — backward compatibility defaults."""

    def test_default_acp_client_has_none_client_capabilities(self) -> None:
        """Test 3: ACPClient with no client_capabilities arg has _client_capabilities == None."""
        transport = MockTransport()
        client = ACPClient(transport, RequiredCapabilities(streaming=True))
        self.assertIsNone(client._client_capabilities)

    def test_acpbackend_config_default_client_capabilities_is_none(self) -> None:
        """Test 4: ACPBackendConfig default has client_capabilities == None."""
        config = ACPBackendConfig(backend_id="test", command=("python", "echo"))
        self.assertIsNone(config.client_capabilities)


if __name__ == "__main__":
    unittest.main()
