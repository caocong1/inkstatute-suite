"""Tests for provider_model adapter collect_artifacts and AgentResult.artifacts population."""

from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentResult, AgentTurn, Artifact, ReplyType
from platform_runtime import RunRequest, SolutionBinding
from platform_runtime.protocols import ArtifactRecord

from inkstatute_backends_provider_model import (
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
    parse_openai_response,
)


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
        solution=SolutionBinding(
            solution_id="provider-model-solution",
            backend_id="provider-model-prototype",
        ),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeProviderModelRunnerWithArtifacts:
    def __init__(self, artifact_refs: list[str] | None = None) -> None:
        self.calls: list[RunRequest] = []
        if artifact_refs is None:
            artifact_refs = [
                "fixture://artifacts/provider-model-run-001/doc-001.pdf",
                "fixture://artifacts/provider-model-run-001/doc-002.docx",
            ]
        self._artifact_refs = artifact_refs

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        self.calls.append(req)
        return ProviderModelExecResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-art-001",
                turn_id="turn-art-001",
                status="success",
                reply_type=ReplyType.TEXT,
                content="Legal analysis with artifact outputs.",
            ),
            completion_id="completion-art-001",
            artifact_refs=list(self._artifact_refs),
            raw_payload_ref="fixture://raw/result-art-001",
            metadata={
                "provider_completion_id": "completion-art-001",
                "artifact_kind": "backend_ref",
            },
        )


class CollectArtifactsTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_artifacts_returns_artifact_records_from_refs(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts()
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(len(artifacts), 2)
        self.assertIsInstance(artifacts[0], ArtifactRecord)
        self.assertEqual(
            artifacts[0].uri_ref,
            "fixture://artifacts/provider-model-run-001/doc-001.pdf",
        )
        self.assertEqual(
            artifacts[1].uri_ref,
            "fixture://artifacts/provider-model-run-001/doc-002.docx",
        )

    async def test_collect_artifacts_raises_key_error_for_unknown_run(self) -> None:
        adapter = ProviderModelBackendAdapter(
            runner=FakeProviderModelRunnerWithArtifacts(),
        )

        with self.assertRaises(KeyError):
            await adapter.collect_artifacts("unknown-run-id")

    async def test_submit_run_populates_agent_result_artifacts(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts()
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertIsNotNone(run.result)
        self.assertEqual(len(run.result.artifacts), 2)
        self.assertIsInstance(run.result.artifacts[0], Artifact)
        self.assertEqual(
            run.result.artifacts[0].uri,
            "fixture://artifacts/provider-model-run-001/doc-001.pdf",
        )
        self.assertEqual(
            run.result.artifacts[1].uri,
            "fixture://artifacts/provider-model-run-001/doc-002.docx",
        )

    async def test_no_artifact_refs_returns_empty_list(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts(artifact_refs=[])
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(artifacts, [])
        run = await adapter.get_run(handle.run_id)
        self.assertEqual(run.result.artifacts, [])

    async def test_artifact_records_use_ref_based_schema(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts()
        adapter = ProviderModelBackendAdapter(runner=runner)

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
        runner = FakeProviderModelRunnerWithArtifacts()
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        for record in artifacts:
            self.assertEqual(record.metadata["source"], "provider_model")

    async def test_artifact_ids_are_deterministic(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts()
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        self.assertEqual(artifacts[0].artifact_id, f"{handle.run_id}-artifact-001")
        self.assertEqual(artifacts[1].artifact_id, f"{handle.run_id}-artifact-002")

    async def test_artifact_metadata_filters_model_names(self) -> None:
        runner = FakeProviderModelRunnerWithArtifacts()
        original_invoke = runner.invoke

        async def invoke_with_noise(req: RunRequest) -> ProviderModelExecResult:
            result = await original_invoke(req)
            return ProviderModelExecResult(
                status=result.status,
                result=result.result,
                completion_id=result.completion_id,
                artifact_refs=result.artifact_refs,
                raw_payload_ref=result.raw_payload_ref,
                metadata={
                    **result.metadata,
                    "model": "gpt-4",
                    "api_error": "trace details",
                    "function_call": "tool_result",
                },
            )

        runner.invoke = invoke_with_noise  # type: ignore[assignment]
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        artifacts = await adapter.collect_artifacts(handle.run_id)

        for record in artifacts:
            self.assertNotIn("model", record.metadata)
            self.assertNotIn("api_error", record.metadata)
            self.assertNotIn("function_call", record.metadata)
            self.assertIn("source", record.metadata)


class ParseOpenAIResponseArtifactTests(unittest.TestCase):
    def test_parse_openai_response_extracts_file_refs(self) -> None:
        response = {
            "id": "chatcmpl-001",
            "model": "gpt-4",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "Here is your document."},
                }
            ],
            "files": [
                {"uri": "provider://files/file-001.pdf", "name": "contract.pdf"},
                {"uri": "provider://files/file-002.docx", "name": "memo.docx"},
            ],
        }

        result = parse_openai_response(response, "run-001", "turn-001")

        self.assertEqual(len(result.artifact_refs), 2)
        self.assertEqual(result.artifact_refs[0], "provider://files/file-001.pdf")
        self.assertEqual(result.artifact_refs[1], "provider://files/file-002.docx")

    def test_parse_openai_response_no_files_returns_empty_refs(self) -> None:
        response = {
            "id": "chatcmpl-001",
            "model": "gpt-4",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "No files here."},
                }
            ],
        }

        result = parse_openai_response(response, "run-001", "turn-001")

        self.assertEqual(result.artifact_refs, [])

    def test_parse_openai_response_file_id_only_produces_provider_ref(self) -> None:
        response = {
            "id": "chatcmpl-001",
            "model": "gpt-4",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "Generated file."},
                }
            ],
            "files": [
                {"id": "file-abc-123"},
            ],
        }

        result = parse_openai_response(response, "run-001", "turn-001")

        self.assertEqual(len(result.artifact_refs), 1)
        self.assertEqual(result.artifact_refs[0], "provider://files/file-abc-123")

    def test_parse_openai_response_skips_non_dict_file_entries(self) -> None:
        response = {
            "id": "chatcmpl-001",
            "model": "gpt-4",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "Mixed files."},
                }
            ],
            "files": [
                {"uri": "provider://files/valid.pdf"},
                "not-a-dict",
                {"id": "valid-id"},
            ],
        }

        result = parse_openai_response(response, "run-001", "turn-001")

        self.assertEqual(len(result.artifact_refs), 2)
        self.assertIn("provider://files/valid.pdf", result.artifact_refs)
        self.assertIn("provider://files/valid-id", result.artifact_refs)


if __name__ == "__main__":
    unittest.main()
