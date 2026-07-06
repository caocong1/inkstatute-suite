from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendMode,
    validate_agent_backend_manifest,
)
from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentResult, AgentTurn, ReplyType
from platform_runtime import Approval, RunRequest, SolutionBinding

from inkstatute_backends_codex import (
    CodexBackendAdapter,
    CodexBackendConfig,
    CodexExecResult,
    build_codex_manifest,
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
        solution=SolutionBinding(solution_id="codex-solution", backend_id="codex-prototype"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeCodexExecRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        self.calls.append(req)
        return CodexExecResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-001",
                turn_id="turn-001",
                status="success",
                reply_type=ReplyType.TEXT,
                content="Sanitized legal analysis result.",
            ),
            thread_id="thread-001",
            raw_payload_ref="fixture://raw/result-001",
            metadata={
                "codex_thread_id": "thread-001",
                "raw_payload": "blocked",
                "token": "blocked",
                "nested": {"secret": "blocked", "kept": "ok"},
            },
        )


class CodexManifestTests(unittest.TestCase):
    def test_codex_manifest_validates_with_production_ready_false(self) -> None:
        manifest = build_codex_manifest()

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertIs(manifest.metadata["production_ready"], False)
        self.assertIs(manifest.capabilities.no_channel_io, True)
        self.assertEqual(manifest.mode, AgentBackendMode.CODEX)

    def test_codex_manifest_selects_as_contract_compatible_not_live(self) -> None:
        from wecom_service.agent_backend import select_agent_backend

        selection = select_agent_backend(
            {"agent_backend": {"mode": "codex"}},
            [build_codex_manifest()],
        )

        self.assertEqual(selection.mode, "codex")
        self.assertIs(selection.contract_compatible, True)
        self.assertIs(selection.live_acceptance_allowed, False)

    def test_codex_capabilities_has_14_fields(self) -> None:
        from dataclasses import fields

        self.assertEqual(len(fields(AdapterCapabilitySet)), 14)

    def test_codex_manifest_does_not_overclaim_unsupported_capabilities(self) -> None:
        capabilities = build_codex_manifest().capabilities

        self.assertFalse(capabilities.stream_event_support)
        self.assertFalse(capabilities.cancel_support)
        self.assertFalse(capabilities.approval_support)
        self.assertFalse(capabilities.live_update_support)
        self.assertFalse(capabilities.parallel_task_support)
        self.assertTrue(capabilities.artifact_return_support)

    def test_codex_manifest_declares_session_memory_support(self) -> None:
        """Phase 49 SESSMEM-02: codex adapter declares session_memory_support=True."""
        from inkstatute_backends_codex.manifest import codex_prototype_capabilities

        capabilities = codex_prototype_capabilities()
        self.assertTrue(capabilities.session_memory_support)


class CodexBackendAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_exposes_backend_adapter_methods(self) -> None:
        adapter = CodexBackendAdapter(runner=FakeCodexExecRunner())

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
        runner = FakeCodexExecRunner()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(handle.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(run.metadata["raw_payload_ref"], "fixture://raw/result-001")
        self.assertEqual(run.metadata["codex_thread_id"], "thread-001")
        self.assertEqual(run.metadata["request_content_sha256"], _sha256(RAW_REQUEST))
        self.assertNotIn(RAW_REQUEST, repr(run))
        self.assertNotIn("'raw_payload':", repr(run.metadata))
        self.assertNotIn("token", repr(run.metadata))

    async def test_submit_run_without_runner_raises(self) -> None:
        adapter = CodexBackendAdapter()

        with self.assertRaises(RuntimeError):
            await adapter.submit_run(make_request())

    async def test_stream_cancel_and_approval_are_deterministic_non_runner_paths(self) -> None:
        runner = FakeCodexExecRunner()
        adapter = CodexBackendAdapter(runner=runner)
        handle = await adapter.submit_run(make_request())

        events = [event async for event in adapter.stream_events(handle.run_id)]
        cancelled = await adapter.cancel_run(handle.run_id)
        approved = await adapter.submit_approval(
            handle.run_id,
            Approval(approval_id="approval-001", decision="approved"),
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "state_changed")
        self.assertEqual(events[0].payload["status"], AsyncTaskState.SUCCEEDED.value)
        self.assertEqual(cancelled.metadata["reason"], "unsupported_by_codex_prototype")
        self.assertEqual(approved.metadata["reason"], "approval_unsupported_by_codex_prototype")
        self.assertIs(approved.metadata["approval_decision_recorded"], False)

    async def test_bootstrap_reports_codex_binary_and_channel_boundary(self) -> None:
        adapter = CodexBackendAdapter(runner=FakeCodexExecRunner())

        status = await adapter.bootstrap_check()

        self.assertTrue(status.ok)
        self.assertIs(status.metadata["no_channel_io"], True)
        self.assertEqual(status.metadata["codex_binary"], "codex")
        self.assertIs(adapter.capabilities().no_channel_io, True)

    def test_platform_runtime_does_not_import_concrete_codex_backend(self) -> None:
        runtime_root = REPO_ROOT / "packages" / "platform-runtime" / "src"
        haystack = "\n".join(path.read_text(encoding="utf-8") for path in runtime_root.rglob("*.py"))

        self.assertNotIn("inkstatute_backends_codex", haystack)
        self.assertNotIn("CodexBackendAdapter", haystack)


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
