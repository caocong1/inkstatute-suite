"""E2E test: tool error recovery through the full turn loop.

Verifies that tool failures (both error ToolResult and raised exceptions)
do not crash the turn loop but produce error events and allow recovery.
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
from inkstatute_agent_core.tools.registry import ToolRegistry
from inkstatute_agent_core.turn_loop import ToolResult, run_turn

from fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


async def _collect_events(gen) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


class TestE2EToolErrorRecovery(unittest.TestCase):
    """Tool error recovery e2e: tool fails → error event → loop continues."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_tool_returns_error_result(self) -> None:
        """Tool returns error ToolResult → tool_call.completed with status=error → loop continues."""
        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="read_file",
                    arguments='{"path": "nonexistent.txt"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="文件不存在，我将基于已有知识回答。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-err-recovery", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "读取不存在的文件"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-err-recovery",
            ))
        )

        # Tool call completed with error
        tool_completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3]
        self.assertEqual(len(tool_completed), 1)
        self.assertEqual(tool_completed[0].payload.get("status"), "error")

        # Loop continued — final content produced
        message_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED]
        self.assertGreater(len(message_completed), 0)

        # Run succeeded (not failed)
        run_state = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED]
        self.assertEqual(run_state[-1].payload["status"], "succeeded")

    def test_tool_handler_raises_exception(self) -> None:
        """Tool handler raises RuntimeError → caught → error event → loop continues."""
        # Register a tool that always raises
        registry = ToolRegistry()

        async def raising_handler(args):
            raise RuntimeError("intentional test failure")

        registry.register_definition(
            name="bad_tool",
            handler=raising_handler,
            definition={
                "type": "function",
                "function": {
                    "name": "bad_tool",
                    "description": "A tool that always raises",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        )

        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="bad_tool",
                    arguments="{}",
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="工具出错，但我可以继续回答。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-exc-recovery", config)
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "调用会出错的工具"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-exc-recovery",
            ))
        )

        # Tool call completed with error (exception caught)
        tool_completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3]
        self.assertEqual(len(tool_completed), 1)
        self.assertEqual(tool_completed[0].payload.get("status"), "error")

        # Loop continued — final content produced
        message_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED]
        self.assertGreater(len(message_completed), 0)

        # Run succeeded (not failed — tool errors don't fail the run)
        run_state = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED]
        self.assertEqual(run_state[-1].payload["status"], "succeeded")

    def test_tool_error_does_not_emit_run_failed(self) -> None:
        """Tool errors should NOT cause run.state_changed(failed)."""
        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="read_file",
                    arguments='{"path": "nonexistent.txt"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="恢复回答。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-no-fail", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "测试"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-no-fail",
            ))
        )

        run_state = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED]
        failed_states = [e for e in run_state if e.payload["status"] == "failed"]
        self.assertEqual(len(failed_states), 0)


if __name__ == "__main__":
    unittest.main()
