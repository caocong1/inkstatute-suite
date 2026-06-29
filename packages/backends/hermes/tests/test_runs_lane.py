from __future__ import annotations

import unittest
from typing import Iterable, Mapping

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentResult, AgentTurn, ReplyType
from platform_runtime import Approval, RunRequest, SolutionBinding

from inkstatute_backends_hermes import (
    HermesBackendAdapter,
    HermesBackendConfig,
    HermesOneShotResult,
    HermesRunsClient,
    HermesRunsDisabledError,
    is_high_risk_legal_approval,
    map_hermes_run_status,
)


RAW_APPROVAL_PROMPT = "approve this high-risk legal conclusion without review"


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-runs-001",
            conversation_id="conversation-runs-001",
            channel=Channel.WEB,
            user_id="user-runs-001",
            message_type=MessageType.TEXT,
            received_at="2026-06-29T00:00:00Z",
            content="sensitive run request",
            metadata={"raw_payload_ref": "fixture://raw/runs-turn-001"},
        ),
        solution=SolutionBinding(solution_id="lawyer-solution", backend_id="hermes-lawfirm"),
    )


class FakeRunsTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, object] | None]] = []
        self.events = [
            {"event_id": "event-001", "status": "running", "seq": 1, "raw_payload_ref": "fixture://event/1"}
        ]

    def post_json(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]:
        self.calls.append(("post", path, dict(body)))
        return {"run_id": "api-run-001", "status": "queued", "raw_payload_ref": "fixture://api/run-001"}

    def get_json(self, path: str) -> Mapping[str, object]:
        self.calls.append(("get", path, None))
        return {"run_id": "api-run-001", "status": "running", "raw_payload_ref": "fixture://api/run-001"}

    def iter_json(self, path: str) -> Iterable[Mapping[str, object]]:
        self.calls.append(("iter", path, None))
        return list(self.events)


class FakeOneShotRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> HermesOneShotResult:
        self.calls.append(req)
        return HermesOneShotResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-runs-001",
                turn_id=req.turn.turn_id,
                status="success",
                reply_type=ReplyType.TEXT,
                content="safe one-shot result",
            ),
            raw_payload_ref="fixture://oneshot/result-runs-001",
        )


class HermesRunsConfigTests(unittest.TestCase):
    def test_api_runs_config_defaults_off_and_env_requires_true_value(self) -> None:
        self.assertIs(HermesBackendConfig().api_runs_enabled, False)
        self.assertIs(HermesBackendConfig.from_env({}).api_runs_enabled, False)
        self.assertIs(
            HermesBackendConfig.from_env({"INKSTATUTE_HERMES_API_RUNS_ENABLED": "true"}).api_runs_enabled,
            True,
        )
        self.assertIs(
            HermesBackendConfig.from_env({"INKSTATUTE_HERMES_API_RUNS_ENABLED": "false"}).api_runs_enabled,
            False,
        )
        self.assertIs(
            HermesBackendConfig.from_env({"INKSTATUTE_HERMES_API_RUNS_ENABLED": "YES"}).api_runs_enabled,
            True,
        )


class HermesRunsClientTests(unittest.TestCase):
    def test_disabled_runs_client_raises_before_transport_access(self) -> None:
        transport = FakeRunsTransport()
        client = HermesRunsClient(transport, HermesBackendConfig(api_runs_enabled=False))

        with self.assertRaises(HermesRunsDisabledError):
            client.submit_run(make_request())

        self.assertEqual(transport.calls, [])

    def test_enabled_runs_client_uses_expected_run_paths(self) -> None:
        transport = FakeRunsTransport()
        client = HermesRunsClient(transport, HermesBackendConfig(api_runs_enabled=True))

        client.submit_run(make_request())
        list(client.stream_events("api-run-001"))

        self.assertEqual(transport.calls[0][0:2], ("post", "/v1/runs"))
        self.assertEqual(transport.calls[1][0:2], ("iter", "/v1/runs/api-run-001/events"))
        self.assertNotIn("sensitive run request", repr(transport.calls[0][2]))

    def test_unknown_status_maps_to_failed_with_sanitized_metadata(self) -> None:
        mapped = map_hermes_run_status("secret-status-from-backend")

        self.assertEqual(mapped.status, AsyncTaskState.FAILED)
        self.assertTrue(mapped.metadata["unknown_status"])
        self.assertIn("status_sha256", mapped.metadata)
        self.assertNotIn("secret-status-from-backend", repr(mapped.metadata))


class HermesRunsAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_without_api_mode_still_uses_oneshot_runner(self) -> None:
        transport = FakeRunsTransport()
        runner = FakeOneShotRunner()
        adapter = HermesBackendAdapter(
            config=HermesBackendConfig(api_runs_enabled=True),
            runner=runner,
            runs_client=HermesRunsClient(transport, HermesBackendConfig(api_runs_enabled=True)),
        )

        handle = await adapter.submit_run(make_request())

        self.assertEqual(handle.metadata["invocation_mode"], "oneshot")
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(transport.calls, [])

    async def test_adapter_api_mode_uses_runs_client_only_when_enabled(self) -> None:
        transport = FakeRunsTransport()
        config = HermesBackendConfig(api_runs_enabled=True)
        adapter = HermesBackendAdapter(
            config=config,
            runner=FakeOneShotRunner(),
            runs_client=HermesRunsClient(transport, config),
            invocation_mode="runs_api",
        )

        handle = await adapter.submit_run(make_request())
        events = [event async for event in adapter.stream_events(handle.run_id)]

        self.assertEqual(handle.metadata["invocation_mode"], "runs_api")
        self.assertEqual(handle.backend_run_id, "api-run-001")
        self.assertEqual(transport.calls[0][0:2], ("post", "/v1/runs"))
        self.assertEqual(transport.calls[1][0:2], ("iter", "/v1/runs/api-run-001/events"))
        self.assertEqual(events[0].payload["status"], AsyncTaskState.RUNNING)

    async def test_adapter_explicit_api_mode_falls_back_to_oneshot_when_gate_disabled(self) -> None:
        transport = FakeRunsTransport()
        runner = FakeOneShotRunner()
        disabled = HermesBackendConfig(api_runs_enabled=False)
        adapter = HermesBackendAdapter(
            config=disabled,
            runner=runner,
            runs_client=HermesRunsClient(transport, disabled),
            invocation_mode="runs_api",
        )

        handle = await adapter.submit_run(make_request())

        self.assertEqual(handle.metadata["invocation_mode"], "oneshot")
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(transport.calls, [])

    async def test_high_risk_legal_approval_records_human_review_rejection_without_transport_or_runner(self) -> None:
        transport = FakeRunsTransport()
        runner = FakeOneShotRunner()
        config = HermesBackendConfig(api_runs_enabled=True)
        adapter = HermesBackendAdapter(
            config=config,
            runner=runner,
            runs_client=HermesRunsClient(transport, config),
            invocation_mode="runs_api",
        )
        handle = await adapter.submit_run(make_request())
        transport.calls.clear()
        runner.calls.clear()

        run = await adapter.submit_approval(
            handle.run_id,
            Approval(
                approval_id="approval-high-risk",
                decision="approved",
                metadata={
                    "legal_conclusion": True,
                    "approval_prompt": RAW_APPROVAL_PROMPT,
                },
            ),
        )

        self.assertTrue(is_high_risk_legal_approval(Approval("x", "approved", metadata={"skill_candidate": True})))
        self.assertEqual(transport.calls, [])
        self.assertEqual(runner.calls, [])
        self.assertEqual(run.metadata["approval_rejected"], "high_risk_legal_human_review_required")
        self.assertFalse(run.metadata["approval_decision_recorded"])
        self.assertNotIn(RAW_APPROVAL_PROMPT, repr(run.metadata))

    async def test_non_high_risk_approval_with_oneshot_default_remains_unsupported(self) -> None:
        adapter = HermesBackendAdapter(runner=FakeOneShotRunner())
        handle = await adapter.submit_run(make_request())

        run = await adapter.submit_approval(handle.run_id, Approval("approval-low-risk", "approved"))

        self.assertEqual(run.metadata["reason"], "approval_unsupported_by_oneshot")


if __name__ == "__main__":
    unittest.main()

