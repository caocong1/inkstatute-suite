"""Tests for WeCom session runtime memory integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime import (
    FakeIdFactory,
    FakeMemory,
    FakeRuntimeClock,
    Memory,
    MemoryRetainInput,
    Run,
    RunRequest,
    SessionScope,
    SolutionBinding,
)

from wecom_service.memory_integration import MemoryIntegrationPolicy, MemoryRetentionScope
from wecom_service.session_runtime import WeComSessionRuntime


FIXED_NOW = "2026-07-03T12:00:00Z"


@dataclass(slots=True)
class RecordingRuntime:
    created: list[RunRequest] = field(default_factory=list)

    async def create_run(self, req: RunRequest) -> Run:
        self.created.append(req)
        return Run(
            run_id=f"created-{len(self.created):03d}",
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={"session_id": req.session_id},
        )


class WeComSessionMemoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.scope = SessionScope(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            channel_id="wecom",
            user_id="alice",
            bot_instance_id="bot-1",
            conversation_id="conv-1",
            thread_id="thread-1",
        )
        self.solution = SolutionBinding(
            solution_id="solution-1",
            version="1.0.0",
        )

    def turn(self, turn_id: str, content: str) -> AgentTurn:
        return AgentTurn(
            turn_id=turn_id,
            content=content,
            user_id="alice",
            conversation_id="conv-1",
            channel=Channel.WECOM,
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            metadata={"raw_payload_ref": f"turn://{turn_id}", "thread_id": "thread-1"},
        )

    def run_request(self, turn_id: str, content: str) -> RunRequest:
        return RunRequest(
            turn=self.turn(turn_id, content),
            solution=self.solution,
            tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
            bot_instance_id=self.scope.bot_instance_id,
            session_id="session-1",
            metadata={},
        )

    async def test_pre_turn_recall_injects_memory_summary(self) -> None:
        memory: Memory = FakeMemory()
        await memory.aretain(
            MemoryRetainInput(
                tenant_id=self.scope.tenant_id,
                workspace_id=self.scope.workspace_id,
                user_id=self.scope.user_id,
                bank_id="default",
                content="User prefers concise contract summaries.",
            )
        )
        runtime = RecordingRuntime()
        helper = WeComSessionRuntime(
            runtime=runtime,
            memory=memory,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-001", "What is the status of my contract?"),
            scope=self.scope,
            run_request=self.run_request("turn-001", "What is the status of my contract?"),
        )

        self.assertEqual(outcome.run_id, "created-001")
        self.assertEqual(len(runtime.created), 1)
        req = runtime.created[0]
        self.assertIn("memory_recall_summary", req.metadata)
        self.assertEqual(req.metadata["memory_recall_summary"]["recalled_count"], 1)

    async def test_post_turn_retention(self) -> None:
        memory: Memory = FakeMemory()
        runtime = RecordingRuntime()
        helper = WeComSessionRuntime(
            runtime=runtime,
            memory=memory,
            memory_policy=MemoryIntegrationPolicy(retention_scope=MemoryRetentionScope.AGENT_REPLY),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-002", "Summarize the Acme contract dispute."),
            scope=self.scope,
            run_request=self.run_request("turn-002", "Summarize the Acme contract dispute."),
        )

        retained = await helper.finalize_memory(
            outcome=outcome,
            scope=self.scope,
            user_turn_text="Summarize the Acme contract dispute.",
            agent_reply_text="The Acme contract dispute involves a breach of payment terms.",
        )
        self.assertEqual(retained, 1)

    async def test_memory_failure_does_not_block_response(self) -> None:
        class FailingMemory:
            async def aretain(self, input: Any) -> Any:
                raise RuntimeError("retain failed")

            async def arecall(self, input: Any) -> Any:
                raise RuntimeError("recall failed")

            def capability_manifest(self) -> dict[str, Any]:
                return {}

        runtime = RecordingRuntime()
        helper = WeComSessionRuntime(
            runtime=runtime,
            memory=FailingMemory(),
            memory_policy=MemoryIntegrationPolicy(failure_mode="fail_open"),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-003", "Hello"),
            scope=self.scope,
            run_request=self.run_request("turn-003", "Hello"),
        )

        self.assertEqual(outcome.run_id, "created-001")
        req = runtime.created[0]
        self.assertIn("memory_recall_summary", req.metadata)
        self.assertEqual(req.metadata["memory_recall_summary"]["recalled_count"], 0)


if __name__ == "__main__":
    unittest.main()
