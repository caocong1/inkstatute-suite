from __future__ import annotations

from pathlib import Path
import unittest

from platform_contract.enums import Channel, MessageType, RunEventType
from platform_contract.events import AgentTurn
from platform_runtime import BoundaryAction, DefaultAssistantOutputBoundary
from platform_runtime import DefaultRunRuntime, RunRequest, RuntimeFeatureDisabledError, RuntimeFeatureFlags, SolutionBinding
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.protocols import RunEvent


FIXED_NOW = "2026-06-29T03:00:00Z"


def make_run_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-boundary-001",
            conversation_id="conversation-boundary-001",
            channel=Channel.WEB,
            user_id="user-boundary-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content="synthetic request",
            metadata={"raw_payload_ref": "fixture://payloads/turn-boundary-001"},
        ),
        solution=SolutionBinding(solution_id="solution-boundary-001", version="1.0.0"),
        tenant_id="tenant-boundary-001",
        workspace_id="workspace-boundary-001",
        session_id="session-boundary-001",
    )


def make_message_event(run_id: str, text: str, *, seq: int = 100) -> RunEvent:
    return RunEvent(
        event_id=f"run-event-boundary-{seq}",
        run_id=run_id,
        event_type=RunEventType.MESSAGE_DELTA.value,
        occurred_at=FIXED_NOW,
        seq=seq,
        payload={"message_delta": text, "raw_payload_ref": f"fixture://runs/{run_id}/events/{seq}"},
        metadata={"scripted": True},
    )


class DefaultAssistantOutputBoundaryTests(unittest.TestCase):
    def test_allows_business_answer_without_rewriting(self) -> None:
        text = "business answer"
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_allows_legal_conclusion_byte_for_byte(self) -> None:
        text = "Under the contract, the supplier must cure the breach before termination."

        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_blocks_or_rewrites_backend_and_operator_notices_without_original_audit_text(self) -> None:
        samples = {
            "Hermes gateway restarted for profile /home/example/.hermes/profiles/lawfirm": BoundaryAction.BLOCK,
            "Self-update available: run /update now": BoundaryAction.REWRITE,
            "/help /status /credits /insights": BoundaryAction.BLOCK,
            "ADMIN_NOTICE delivery debug stack trace token=secret": BoundaryAction.BLOCK,
            "Tool progress: calling internal retrieval step": BoundaryAction.REWRITE,
            "Dangerous command approval required before shell execution": BoundaryAction.REWRITE,
        }

        boundary = DefaultAssistantOutputBoundary()
        for sample, expected_action in samples.items():
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)

                self.assertEqual(decision.action, expected_action)
                self.assertNotIn(sample, repr(decision.audit_metadata))
                self.assertEqual(decision.audit_metadata["privacy"], "no_original_text_stored")
                self.assertRegex(decision.audit_metadata["input_hash_prefix"], r"^[0-9a-f]{16}$")
                self.assertEqual(decision.audit_metadata["input_length"], len(sample))
                if decision.visible_text is not None:
                    self.assertNotIn("Hermes", decision.visible_text)
                    self.assertNotIn("gateway", decision.visible_text.lower())
                    self.assertNotIn("token=secret", decision.visible_text)

    def test_trade_secret_business_answer_is_not_treated_as_credential(self) -> None:
        text = "A trade secret claim depends on secrecy measures and improper acquisition."

        decision = DefaultAssistantOutputBoundary().apply("ordinary_user", text=text)

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_runtime_source_does_not_embed_concrete_leak_examples(self) -> None:
        src_root = Path("packages/platform-runtime/src")
        source_text = "\n".join(path.read_text(encoding="utf-8") for path in src_root.rglob("*.py"))

        for forbidden in ("Hermes", "WeCom", "lawfirm", "gateway", ".hermes"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), source_text.lower())


class RuntimeStreamBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_rejects_when_streaming_lane_is_default_off(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )
        run = await runtime.create_run(make_run_request())

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: streaming_lane_enabled",
        ):
            [event async for event in runtime.stream(run.run_id)]

    async def test_stream_allows_business_delta_unchanged_and_does_not_mutate_backend_event(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        text = "Under the agreement, the buyer may request cure before termination."
        backend_event = make_message_event(run.run_id, text)
        backend.events[run.run_id].append(backend_event)

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.payload["message_delta"], text)
        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.ALLOW.value)
        self.assertEqual(backend_event.payload["message_delta"], text)
        self.assertNotIn("output_boundary", backend_event.metadata)
        self.assertIsNot(streamed, backend_event)

    async def test_stream_rewrites_lifecycle_delta_with_owned_service_wording(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "Hermes gateway restarted and is back online"
        backend.events[run.run_id].append(make_message_event(run.run_id, original))

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.REWRITE.value)
        self.assertIn("InkStatute", streamed.payload["message_delta"])
        self.assertNotIn(original, repr(streamed))
        self.assertNotIn("gateway", streamed.payload["message_delta"].lower())
        self.assertNotIn(original, repr(streamed.metadata["output_boundary"]))

    async def test_stream_blocks_secret_or_path_delta_without_visible_original_text(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "ADMIN_NOTICE stack trace at /home/example/.hermes/profiles/lawfirm token=secret"
        backend.events[run.run_id].append(make_message_event(run.run_id, original))

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.BLOCK.value)
        self.assertNotIn("message_delta", streamed.payload)
        self.assertNotIn(original, repr(streamed))
        self.assertNotIn("token=secret", repr(streamed))
        self.assertNotIn(original, repr(streamed.metadata["output_boundary"]))


if __name__ == "__main__":
    unittest.main()
