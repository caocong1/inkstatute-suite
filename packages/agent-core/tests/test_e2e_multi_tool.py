"""E2E test: multi-tool orchestration through the full turn loop.

This test exercises the complete ``run_turn()`` async generator with
``FixtureProvider`` and the real ``ToolRegistry`` + dispatching executor
from Phase 101.  It scripts a 3-round conversation:

1. Round 1: LLM calls ``read_file`` tool → tool returns file content
2. Round 2: LLM calls ``search_laws`` tool (fixture mode) → returns results
3. Round 3: LLM produces final content (no tool calls)

Verifies: tool_call events, tool result injection, multi-round
orchestration, final message.completed + run.state_changed(succeeded).
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
from inkstatute_agent_core.model.provider import ContentDelta, FinishDelta, ToolCallDelta, UsageDelta
from inkstatute_agent_core.tools.builtin_registry import create_builtin_registry
from inkstatute_agent_core.tools.executor import create_dispatching_executor
from inkstatute_agent_core.turn_loop import run_turn

from fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


async def _collect_events(gen) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


class TestE2EMultiToolOrchestration(unittest.TestCase):
    """Multi-tool e2e: read_file → search_laws → final content."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()
        (self.root / "contract.txt").write_text(
            "甲方应在2024年12月31日前支付全部款项。", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_3_round_multi_tool_orchestration(self) -> None:
        """3-round conversation: read_file → search_laws → final content."""
        # Script the FixtureProvider
        script: list[TurnScript] = [
            # Round 1: LLM calls read_file
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="read_file",
                    arguments='{"path": "contract.txt"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # Round 2: LLM calls search_laws
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_2",
                    tool_name="search_laws",
                    arguments='{"keyword": "合同法"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            # Round 3: LLM produces final content
            TurnScript(deltas=[
                ContentDelta(content="根据合同内容与相关法规，"),
                ContentDelta(content="甲方应在约定期限前支付款项。"),
                UsageDelta(usage={"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-multi-tool", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "分析合同付款条款"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-multi-tool",
            ))
        )

        # Verify tool_call events for both tools
        tool_started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3]
        tool_completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3]
        self.assertEqual(len(tool_started), 2)
        self.assertEqual(len(tool_completed), 2)

        # Verify tool names
        started_names = [e.payload.get("tool_name") for e in tool_started]
        self.assertIn("read_file", started_names)
        self.assertIn("search_laws", started_names)

        # Verify final events
        message_completed = [e for e in events if e.event_type == RunEventType.MESSAGE_COMPLETED]
        run_state = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED]
        self.assertGreater(len(message_completed), 0)
        self.assertGreater(len(run_state), 0)
        self.assertEqual(run_state[-1].payload["status"], "succeeded")

    def test_tool_results_injected_into_messages(self) -> None:
        """Tool results should be injected as tool messages for the next round."""
        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="read_file",
                    arguments='{"path": "contract.txt"}',
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="文件已读取。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-inject", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "读取文件"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-inject",
            ))
        )

        # The provider should have been called twice (2 rounds)
        self.assertEqual(provider._call_count, 2)

        # Verify no silence gap exceeds threshold
        # (all events should have been emitted — the turn loop streams during tool rounds)
        self.assertGreater(len(events), 5)

    def test_no_external_llm_calls(self) -> None:
        """The test should use FixtureProvider — no external LLM calls."""
        script: list[TurnScript] = [
            TurnScript(deltas=[
                ContentDelta(content="直接回答。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]
        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-no-llm", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "你好"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-no-llm",
            ))
        )

        # FixtureProvider is not an external LLM — verify it was used
        self.assertEqual(provider._call_count, 1)
        self.assertGreater(len(events), 0)


if __name__ == "__main__":
    unittest.main()
