from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn

from platform_runtime import RunRequest, SolutionBinding
from platform_runtime.fakes import (
    FakeBackendAdapter,
    FakeChannelAdapter,
    FakeIdFactory,
    FakeRuntimeClock,
)
from platform_runtime.protocols import ChannelDelivery


FIXED_NOW = "2026-06-29T02:00:00Z"


def make_run_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content="synthetic request",
            metadata={"raw_payload_ref": "fixture://payloads/turn-001"},
        ),
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_backend_uses_deterministic_ids_timestamps_and_states(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        backend = FakeBackendAdapter(clock=clock, id_factory=FakeIdFactory())

        handle = await backend.submit_run(make_run_request())
        run = await backend.get_run(handle.run_id)
        events = [event async for event in backend.stream_events(handle.run_id)]

        self.assertEqual(handle.run_id, "run-001")
        self.assertEqual(handle.backend_run_id, "backend-run-001")
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual([event.seq for event in events], [0, 1, 2])
        self.assertEqual({event.occurred_at for event in events}, {FIXED_NOW})
        self.assertEqual(
            [event.payload["status"] for event in events],
            [AsyncTaskState.QUEUED, AsyncTaskState.RUNNING, AsyncTaskState.SUCCEEDED],
        )
        self.assertNotIn("completed", {str(event.payload["status"]) for event in events})

    async def test_fake_channel_records_delivery_without_network_io(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        channel = FakeChannelAdapter(clock=clock, id_factory=FakeIdFactory())
        delivery = ChannelDelivery(
            delivery_id="delivery-001",
            channel_id="channel-001",
            run_id="run-001",
            content="synthetic reply",
        )

        result = await channel.deliver(delivery)

        self.assertTrue(result.accepted)
        self.assertEqual(result.delivered_at, FIXED_NOW)
        self.assertEqual(channel.deliveries, [delivery])


if __name__ == "__main__":
    unittest.main()
