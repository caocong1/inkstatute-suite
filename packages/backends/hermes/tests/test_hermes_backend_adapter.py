from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract.agent_adapter import validate_agent_backend_manifest
from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentResult, AgentTurn
from platform_contract.events import ReplyType
from platform_runtime import Approval, RunRequest, SolutionBinding

from inkstatute_backends_hermes import (
    HermesBackendAdapter,
    HermesBackendConfig,
    HermesOneShotResult,
    build_hermes_oneshot_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_REQUEST = "synthetic privileged legal request that must not leak"


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at="2026-06-29T00:00:00Z",
            content=RAW_REQUEST,
            metadata={"raw_payload_ref": "fixture://raw/turn-001"},
        ),
        solution=SolutionBinding(solution_id="lawyer-solution", backend_id="hermes-lawfirm"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


def make_result() -> HermesOneShotResult:
    return HermesOneShotResult(
        status=AsyncTaskState.SUCCEEDED,
        result=AgentResult(
            result_id="result-001",
            turn_id="turn-001",
            status="success",
            reply_type=ReplyType.TEXT,
            content="Sanitized legal analysis result.",
        ),
        artifact_refs=["artifact://hermes/run-001/document"],
        trace_refs=["trace://hermes/run-001"],
        raw_payload_ref="fixture://raw/result-001",
        metadata={
            "route": "lawfirm",
            "raw_payload": "blocked",
            "profile_path": "/private/hermes/lawfirm",
            "nested": {"token": "blocked", "kept": "ok"},
        },
    )


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> HermesOneShotResult:
        self.calls.append(req)
        return make_result()


class HermesBackendManifestTests(unittest.TestCase):
    def test_oneshot_manifest_validates_and_declares_no_channel_io(self) -> None:
        manifest = build_hermes_oneshot_manifest(HermesBackendConfig())

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertIs(manifest.capabilities.no_channel_io, True)
        self.assertEqual(manifest.capabilities.run_invocation_modes, ["oneshot"])
        self.assertEqual(manifest.metadata["default_lane"], "oneshot")
        self.assertNotIn("profile_path", repr(manifest.metadata))

    def test_oneshot_manifest_does_not_overclaim_unsupported_capabilities(self) -> None:
        capabilities = build_hermes_oneshot_manifest().capabilities

        self.assertFalse(capabilities.stream_event_support)
        self.assertFalse(capabilities.cancel_support)
        self.assertFalse(capabilities.approval_support)
        self.assertFalse(capabilities.live_update_support)
        self.assertFalse(capabilities.parallel_task_support)


class HermesBackendAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_exposes_backend_adapter_methods(self) -> None:
        adapter = HermesBackendAdapter(runner=FakeRunner())

        for method in (
            "backend_id",
            "capabilities",
            "bootstrap_check",
            "submit_run",
            "get_run",
            "stream_events",
            "cancel_run",
            "submit_approval",
            "collect_artifacts",
        ):
            self.assertTrue(callable(getattr(adapter, method)))

    async def test_submit_and_get_run_use_injected_runner_and_reference_first_metadata(self) -> None:
        runner = FakeRunner()
        adapter = HermesBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(adapter.runner_calls, 1)
        self.assertIsInstance(handle.status, AsyncTaskState)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run.metadata["raw_payload_ref"], "fixture://raw/result-001")
        self.assertEqual(run.metadata["request_content_sha256"], _sha256(RAW_REQUEST))
        self.assertNotIn(RAW_REQUEST, repr(run))
        self.assertNotIn("'raw_payload':", repr(run.metadata))
        self.assertNotIn("profile_path", repr(run.metadata))
        self.assertNotIn("blocked", repr(run.metadata))

    async def test_collect_artifacts_returns_platform_artifact_records(self) -> None:
        adapter = HermesBackendAdapter(runner=FakeRunner())
        handle = await adapter.submit_run(make_request())

        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].uri_ref, "artifact://hermes/run-001/document")
        self.assertEqual(artifacts[0].kind, "backend_ref")

    async def test_stream_cancel_and_approval_are_deterministic_non_runner_paths(self) -> None:
        runner = FakeRunner()
        adapter = HermesBackendAdapter(runner=runner)
        handle = await adapter.submit_run(make_request())

        events = [event async for event in adapter.stream_events(handle.run_id)]
        cancelled = await adapter.cancel_run(handle.run_id)
        approved = await adapter.submit_approval(
            handle.run_id,
            Approval(approval_id="approval-001", decision="approved"),
        )

        self.assertEqual(events, [])
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(cancelled.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(cancelled.metadata["reason"], "unsupported_by_oneshot")
        self.assertEqual(approved.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(approved.metadata["reason"], "approval_unsupported_by_oneshot")
        self.assertFalse(approved.metadata["approval_decision_recorded"])

    async def test_high_risk_legal_approval_is_not_auto_approved(self) -> None:
        adapter = HermesBackendAdapter(runner=FakeRunner())
        handle = await adapter.submit_run(make_request())

        run = await adapter.submit_approval(
            handle.run_id,
            Approval(
                approval_id="approval-legal-001",
                decision="approved",
                metadata={"risk_level": "high", "approval_scope": "legal_conclusion"},
            ),
        )

        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run.metadata["reason"], "high_risk_legal_approval_requires_human_review")
        self.assertFalse(run.metadata["approval_decision_recorded"])

    async def test_bootstrap_reports_runner_and_channel_boundary(self) -> None:
        adapter = HermesBackendAdapter(runner=FakeRunner())

        status = await adapter.bootstrap_check()

        self.assertTrue(status.ok)
        self.assertTrue(status.metadata["runner_injected"])
        self.assertTrue(status.metadata["no_channel_io"])
        self.assertTrue(adapter.capabilities().no_channel_io)

    def test_platform_runtime_does_not_import_concrete_hermes_backend(self) -> None:
        runtime_root = REPO_ROOT / "packages" / "platform-runtime" / "src"
        haystack = "\n".join(path.read_text(encoding="utf-8") for path in runtime_root.rglob("*.py"))

        self.assertNotIn("inkstatute_backends_hermes", haystack)
        self.assertNotIn("HermesBackendAdapter", haystack)


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
