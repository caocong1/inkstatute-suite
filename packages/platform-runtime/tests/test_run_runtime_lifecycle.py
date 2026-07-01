from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn

from platform_runtime import (
    Approval,
    ContextAssembler,
    ContextAssemblyPolicy,
    DefaultRunRuntime,
    InMemoryContractLogStore,
    RunRequest,
    RunRuntimeStateError,
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
    SolutionBinding,
)
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


class DefaultRunRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_constructs_with_zero_channels_and_no_server(self) -> None:
        runtime = DefaultRunRuntime(backend=FakeBackendAdapter(), channels=())

        self.assertEqual(runtime.channels, ())
        self.assertFalse(hasattr(runtime, "server"))

    async def test_create_run_rejects_default_off_without_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(backend=backend)

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: run_runtime_enabled",
        ):
            await runtime.create_run(make_run_request())

        self.assertEqual(backend.submitted_requests, [])

    def test_context_assembly_flag_is_default_off(self) -> None:
        flags = RuntimeFeatureFlags()

        self.assertFalse(flags.context_assembly_enabled)
        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: context_assembly_enabled",
        ):
            flags.require_enabled("context_assembly_enabled")

    async def test_create_run_does_not_attach_context_when_context_assembly_default_off(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
            context_assembler=ContextAssembler(),
        )

        original = make_run_request()
        await runtime.create_run(original)
        submitted = backend.submitted_requests[0]

        self.assertIs(submitted, original)
        self.assertNotIn("context_bundle", submitted.metadata)
        self.assertNotIn("context_bundle_id", submitted.metadata)
        self.assertEqual(original.metadata, {})

    async def test_create_run_with_context_enabled_requires_assembler_before_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                context_assembly_enabled=True,
            ),
        )

        with self.assertRaisesRegex(
            RunRuntimeStateError,
            "context_assembly_enabled requires context_assembler",
        ):
            await runtime.create_run(make_run_request())

        self.assertEqual(backend.submitted_requests, [])

    async def test_create_run_with_context_enabled_submits_replaced_request_and_logs_bundle(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        store = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                contract_log_enabled=True,
                context_assembly_enabled=True,
            ),
            contract_log_store=store,
            context_assembler=ContextAssembler(
                policy=ContextAssemblyPolicy(budget_tokens=512),
                clock=clock,
                id_factory=id_factory,
            ),
            clock=clock,
            id_factory=id_factory,
        )
        original = make_run_request()

        await runtime.create_run(original)
        submitted = backend.submitted_requests[0]
        entries = store.entries()

        self.assertIsNot(submitted, original)
        self.assertEqual(original.metadata, {})
        self.assertIn("context_bundle_id", submitted.metadata)
        self.assertEqual(submitted.metadata["context_bundle_id"], submitted.metadata["context_bundle"]["context_bundle_id"])
        self.assertEqual(
            submitted.metadata["context_bundle"]["metadata"]["current_turn_ref"],
            "fixture://payloads/turn-001",
        )
        self.assertEqual(
            submitted.metadata["context_bundle"]["metadata"]["current_turn_text_length"],
            len("synthetic request"),
        )
        self.assertEqual([entry.event_key for entry in entries], ["context_bundle", "run", "run_event"])
        self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in entries]))
        self.assertNotIn("synthetic request", repr(submitted.metadata))

    async def test_create_run_with_flags_calls_backend_and_appends_contract_records(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        store = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            channels=(),
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                contract_log_enabled=True,
            ),
            contract_log_store=store,
            clock=clock,
            id_factory=id_factory,
        )

        run = await runtime.create_run(make_run_request())
        entries = store.entries()

        self.assertEqual(run.run_id, "run-001")
        self.assertEqual(len(backend.submitted_requests), 1)
        self.assertEqual([entry.event_key for entry in entries], ["run", "run_event"])
        self.assertEqual(entries[0].event["run_id"], "run-001")
        self.assertEqual(entries[0].event["turn_id"], "turn-001")
        self.assertEqual(entries[0].event["status"], AsyncTaskState.QUEUED.value)
        self.assertEqual(entries[1].event["status"], AsyncTaskState.QUEUED.value)
        self.assertEqual(
            entries[0].event["raw_payload_ref"],
            "fixture://payloads/turn-001",
        )
        self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in entries]))
        self.assertIn("content_sha256", entries[0].event)

    async def test_create_run_with_contract_log_enabled_requires_store_before_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                contract_log_enabled=True,
            ),
        )

        with self.assertRaisesRegex(
            RunRuntimeStateError,
            "contract_log_enabled requires contract_log_store",
        ):
            await runtime.create_run(make_run_request())

        self.assertEqual(backend.submitted_requests, [])
        self.assertEqual(backend.runs, {})

    async def test_zero_channel_runtime_creates_polls_and_streams_fake_run(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            channels=(),
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )

        created = await runtime.create_run(make_run_request())
        polled = await runtime.poll(created.run_id)
        events = [event async for event in runtime.stream(created.run_id)]

        self.assertEqual(created.run_id, "run-001")
        self.assertEqual(polled.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual([event.seq for event in events], [0, 1, 2])

    async def test_cancel_returns_cancelled_state_and_records_append_only_event(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        store = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            channels=(),
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                contract_log_enabled=True,
            ),
            contract_log_store=store,
            clock=clock,
            id_factory=id_factory,
        )
        run = await runtime.create_run(make_run_request())

        cancelled = await runtime.cancel(run.run_id)
        entries = store.entries()

        self.assertEqual(cancelled.status, AsyncTaskState.CANCELLED)
        self.assertEqual([entry.seq for entry in entries], [0, 1, 2])
        self.assertEqual(entries[-1].event["run_id"], run.run_id)
        self.assertEqual(entries[-1].event["turn_id"], "turn-001")
        self.assertEqual(entries[-1].event["status"], AsyncTaskState.CANCELLED.value)
        self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in entries]))

    async def test_cancel_with_contract_log_enabled_requires_store_before_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        setup_runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )
        run = await setup_runtime.create_run(make_run_request())
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                contract_log_enabled=True,
            ),
        )

        with self.assertRaisesRegex(
            RunRuntimeStateError,
            "contract_log_enabled requires contract_log_store",
        ):
            await runtime.cancel(run.run_id)

        self.assertEqual(backend.cancelled_run_ids, [])
        self.assertEqual(backend.runs[run.run_id].status, AsyncTaskState.SUCCEEDED)

    async def test_approve_updates_fake_backend_and_records_reference_first_state(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        store = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            channels=(),
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                approval_lane_enabled=True,
                contract_log_enabled=True,
            ),
            contract_log_store=store,
            clock=clock,
            id_factory=id_factory,
        )
        run = await runtime.create_run(make_run_request())

        approved = await runtime.approve(
            run.run_id,
            Approval(
                approval_id="approval-001",
                decision="approved",
                decided_by="tester",
                decided_at=FIXED_NOW,
            ),
        )
        entries = store.entries()

        self.assertEqual(approved.status, AsyncTaskState.RUNNING)
        self.assertEqual(backend.submitted_approvals[0][1].approval_id, "approval-001")
        self.assertEqual([entry.seq for entry in entries], [0, 1, 2])
        self.assertEqual(entries[-1].event["run_id"], run.run_id)
        self.assertEqual(entries[-1].event["turn_id"], "turn-001")
        self.assertEqual(entries[-1].event["status"], AsyncTaskState.RUNNING.value)
        self.assertEqual(entries[-1].event["metadata"]["approval_id"], "approval-001")
        self.assertEqual(
            entries[0].event["raw_payload_ref"],
            "fixture://payloads/turn-001",
        )
        self.assertRegex(entries[0].event["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in entries]))

    async def test_approve_with_contract_log_enabled_requires_store_before_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        setup_runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )
        run = await setup_runtime.create_run(make_run_request())
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                approval_lane_enabled=True,
                contract_log_enabled=True,
            ),
        )

        with self.assertRaisesRegex(
            RunRuntimeStateError,
            "contract_log_enabled requires contract_log_store",
        ):
            await runtime.approve(
                run.run_id,
                Approval(approval_id="approval-001", decision="approved"),
            )

        self.assertEqual(backend.submitted_approvals, [])

    async def test_approve_rejects_when_approval_lane_is_default_off(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )
        run = await runtime.create_run(make_run_request())

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: approval_lane_enabled",
        ):
            await runtime.approve(
                run.run_id,
                Approval(approval_id="approval-001", decision="approved"),
            )

        self.assertEqual(backend.submitted_approvals, [])


if __name__ == "__main__":
    unittest.main()
