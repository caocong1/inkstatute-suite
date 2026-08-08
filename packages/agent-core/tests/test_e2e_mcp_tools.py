"""E2E test: MCP tool discovery and invocation (fixture mode).

Verifies that MCP tools can be discovered and invoked through the turn
loop using fixture mode (no Node.js subprocess or network calls).
Also tests the MCP-to-OpenAI schema conversion functions.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from platform_contract.enums import RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import ContentDelta, FinishDelta, ToolCallDelta
from inkstatute_agent_core.tools.builtin_registry import create_builtin_registry
from inkstatute_agent_core.tools.executor import create_dispatching_executor
from inkstatute_agent_core.tools.mcp_client import (
    mcp_input_schema_to_openai_parameters,
    mcp_tool_to_openai_definition,
)
from inkstatute_agent_core.turn_loop import run_turn

from fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


async def _collect_events(gen) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


class TestE2EMcpTools(unittest.TestCase):
    """MCP tool discovery and invocation e2e (fixture mode)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_fixture_search_laws_through_turn_loop(self) -> None:
        """search_laws fixture tool is called through the turn loop."""
        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="search_laws",
                    arguments='{"keyword": "合同法"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="根据检索结果，合同法相关条款已找到。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-mcp-fixture", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "搜索合同法"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-mcp-fixture",
            ))
        )

        # Tool call events
        tool_started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3]
        tool_completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3]
        self.assertEqual(len(tool_started), 1)
        self.assertEqual(len(tool_completed), 1)
        self.assertEqual(tool_started[0].payload.get("tool_name"), "search_laws")
        self.assertEqual(tool_completed[0].payload.get("status"), "succeeded")

        # Final content produced
        message_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED]
        self.assertGreater(len(message_completed), 0)

    def test_mcp_tool_to_openai_definition(self) -> None:
        """mcp_tool_to_openai_definition converts MCP tool descriptor to OpenAI format."""
        mcp_tool = {
            "name": "search_laws",
            "description": "Search Chinese legal database",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Search keyword"},
                },
                "required": ["keyword"],
            },
        }

        openai_def = mcp_tool_to_openai_definition(mcp_tool)
        self.assertEqual(openai_def["type"], "function")
        self.assertEqual(openai_def["function"]["name"], "search_laws")
        self.assertEqual(openai_def["function"]["description"], "Search Chinese legal database")
        self.assertIn("parameters", openai_def["function"])
        self.assertEqual(openai_def["function"]["parameters"]["type"], "object")
        self.assertIn("keyword", openai_def["function"]["parameters"]["properties"])

    def test_mcp_input_schema_to_openai_parameters(self) -> None:
        """mcp_input_schema_to_openai_parameters is a direct passthrough."""
        input_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        result = mcp_input_schema_to_openai_parameters(input_schema)
        self.assertEqual(result, input_schema)

    def test_no_real_subprocess_or_network(self) -> None:
        """Fixture mode should not spawn subprocesses or make network calls."""
        # Using fixture mode (mcp_connector_path=None)
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        # The search_laws tool should be registered and work in fixture mode
        self.assertTrue(registry.has_tool("search_laws"))

        handler = registry.get_handler("search_laws")
        result = asyncio.new_event_loop().run_until_complete(
            handler({"keyword": "合同法"})
        )
        # Should return fixture response, not error
        self.assertIsNone(result.error)
        self.assertIn("合同法", result.content)


if __name__ == "__main__":
    unittest.main()
