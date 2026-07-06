"""Tests for Codex adapter collect_artifacts and AgentResult.artifacts population."""

from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentResult, AgentTurn, Artifact, ReplyType
from platform_runtime import RunRequest, SolutionBinding
from platform_runtime.protocols import ArtifactRecord

from inkstatute_backends_codex import CodexBackendAdapter, CodexExecResult


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-art-001",
            conversation_id="conversation-art-001",
            channel=Channel.WEB,
            user_id="user-art-001",
            message_type=MessageType.TEXT,
            received_at="2026-07-06T00:00:00Z",
            content="synthetic request for artifact test",
            metadata={"raw_payload_ref": "fixture://raw/turn-art-001"},
        ),
        solution=SolutionBinding(solution_id="codex-solution", backend_id="codex-prototype"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeCodexExecRunnerWithArtifacts:
    def __init__(self, artifact_refs: list[str] | None = None) -> None:
        self.calls: list[RunRequest] = []
        if artifact_refs is None:
            artifact_refs = [
                "fixture://artifacts/codex-run-001/doc-001.pdf",
                "fixture://artifacts/codex-run-001/doc-002.docx",
            ]
        self._artifact_refs = artifact_refs

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        self.calls.append(req)
        return CodexExecResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-art-001",
                turn_id="turn-art-001",
                status="success",
                reply_type=ReplyType.TEXT,
                content="Legal analysis with artifact outputs.",
            ),
            thread_id="thread-art-001",
            artifact_refs=list(self._artifact_refs),
            raw_payload_ref="fixture://raw/result-art-001",
            metadata={
                "codex_thread_id": "thread-art-001",
                "artifact_kind": "backend_ref",
            },
        )


class CollectArtifactsTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_artifacts_returns_artifact_records_from_refs(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(len(artifacts), 2)
        self.assertIsInstance(artifacts[0], ArtifactRecord)
        self.assertEqual(
            artifacts[0].uri_ref,
            "fixture://artifacts/codex-run-001/doc-001.pdf",
        )
        self.assertEqual(
            artifacts[1].uri_ref,
            "fixture://artifacts/codex-run-001/doc-002.docx",
        )

    async def test_collect_artifacts_raises_key_error_for_unknown_run(self) -> None:
        adapter = CodexBackendAdapter(runner=FakeCodexExecRunnerWithArtifacts())

        with self.assertRaises(KeyError):
            await adapter.collect_artifacts("unknown-run-id")

    async def test_submit_run_populates_agent_result_artifacts(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertIsNotNone(run.result)
        self.assertEqual(len(run.result.artifacts), 2)
        self.assertIsInstance(run.result.artifacts[0], Artifact)
        self.assertEqual(
            run.result.artifacts[0].uri,
            "fixture://artifacts/codex-run-001/doc-001.pdf",
        )
        self.assertEqual(
            run.result.artifacts[1].uri,
            "fixture://artifacts/codex-run-001/doc-002.docx",
        )

    async def test_no_artifact_refs_returns_empty_list(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts(artifact_refs=[])
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(artifacts, [])
        run = await adapter.get_run(handle.run_id)
        self.assertEqual(run.result.artifacts, [])

    async def test_artifact_records_use_ref_based_schema(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        for record in artifacts:
            self.assertTrue(record.uri_ref)
            self.assertFalse(
                any(
                    key in record.metadata
                    for key in ("content", "data", "binary", "base64")
                ),
                "Artifact metadata must not contain inline binary content keys",
            )

    async def test_artifact_metadata_contains_source(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        for record in artifacts:
            self.assertEqual(record.metadata["source"], "codex_exec")

    async def test_artifact_ids_are_deterministic(self) -> None:
        runner = FakeCodexExecRunnerWithArtifacts()
        adapter = CodexBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(artifacts[0].artifact_id, f"{handle.run_id}-artifact-001")
        self.assertEqual(artifacts[1].artifact_id, f"{handle.run_id}-artifact-002")


if __name__ == "__main__":
    unittest.main()
