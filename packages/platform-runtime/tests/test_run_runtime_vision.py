"""Integration tests for DefaultRunRuntime vision routing (VIS-02/03/04)."""

from __future__ import annotations

import unittest
from dataclasses import replace

from platform_contract.enums import AgentResultStatus, AsyncTaskState, Channel, ErrorCategory, MessageType, ReplyType
from platform_contract.events import AgentResult, AgentTurn, AttachmentRef
from platform_runtime import (
    DefaultRunRuntime,
    Run,
    RunHandle,
    RuntimeFeatureFlags,
    RunRequest,
    SolutionBinding,
    VisionRoute,
    VisionRoutingDecision,
)
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory
from platform_runtime.vision_router import FAIL_CLOSED_NOTICE

FIXED_NOW = "2026-07-12T00:00:00Z"


def _make_image_turn(content: str = "describe the image") -> AgentTurn:
    return AgentTurn(
        turn_id="turn-image-001",
        conversation_id="conversation-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at=FIXED_NOW,
        content=content,
        attachments=[
            AttachmentRef(
                attachment_id="att-001",
                kind="image",
                uri="fixture://images/test-001.png",
                name="test-001.png",
                mime_type="image/png",
            )
        ],
    )


def _make_text_turn(content: str = "summarize the contract") -> AgentTurn:
    return AgentTurn(
        turn_id="turn-text-001",
        conversation_id="conversation-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at=FIXED_NOW,
        content=content,
        attachments=[],
    )


def _make_request(*, turn: AgentTurn, metadata: dict[str, object] | None = None) -> RunRequest:
    return RunRequest(
        turn=turn,
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
        metadata=dict(metadata or {}),
    )


def _vision_decision(route: VisionRoute) -> VisionRoutingDecision:
    if route == VisionRoute.FAIL_CLOSED:
        return VisionRoutingDecision(
            route=VisionRoute.FAIL_CLOSED,
            notice=FAIL_CLOSED_NOTICE,
            reason="no_vision_capable_path",
            metadata={"image_count": 1, "reason": "no_vision_capable_path"},
        )
    if route == VisionRoute.VISION_THEN_MAIN:
        return VisionRoutingDecision(
            route=VisionRoute.VISION_THEN_MAIN,
            reason="vision_then_main_mix",
            metadata={
                "image_count": 1,
                "reason": "vision_then_main_mix",
                "vision_provider_id": "vision-provider-001",
                "vision_model_id": "vision-model-001",
            },
        )
    if route == VisionRoute.MULTIMODAL_MAIN:
        return VisionRoutingDecision(
            route=VisionRoute.MULTIMODAL_MAIN,
            reason="main_supports_vision",
            metadata={"image_count": 1, "reason": "main_supports_vision"},
        )
    return VisionRoutingDecision(
        route=VisionRoute.TEXT_ONLY,
        reason="no_image_attachments",
        metadata={"image_count": 0, "reason": "no_image_attachments"},
    )


class _FakeVisionBackendAdapter(FakeBackendAdapter):
    """FakeBackendAdapter that returns a SUCCEEDED run with vision description content."""

    def __init__(self, vision_content: str = "A person in a red hat.", **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.vision_content = vision_content

    async def submit_run(self, req: RunRequest) -> RunHandle:
        handle = await super().submit_run(req)
        original = self.runs[handle.run_id]
        result = AgentResult(
            result_id=f"vision-result-{handle.run_id}",
            turn_id=req.turn.turn_id,
            status=AgentResultStatus.SUCCESS,
            reply_type=ReplyType.TEXT,
            content=self.vision_content,
            metadata={"source": "fake_vision_runner"},
        )
        self.runs[handle.run_id] = replace(original, result=result)
        return handle


class VisionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _make_runtime(
        self,
        backend: FakeBackendAdapter,
        vision_resolver=None,
        vision_runner=None,
    ) -> DefaultRunRuntime:
        return DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
            vision_resolver=vision_resolver,
            vision_runner=vision_runner,
            id_factory=FakeIdFactory(),
        )

    async def test_no_vision_resolver_uses_legacy_backend_path(self) -> None:
        backend = FakeBackendAdapter()
        runtime = self._make_runtime(backend)
        req = _make_request(turn=_make_text_turn())

        run = await runtime.create_run(req)

        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(len(backend.submitted_requests), 1)
        self.assertNotIn("vision_decision", backend.submitted_requests[0].metadata)

    async def test_text_only_uses_backend_with_vision_decision(self) -> None:
        backend = FakeBackendAdapter()
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.TEXT_ONLY),
        )
        req = _make_request(turn=_make_text_turn())

        run = await runtime.create_run(req)

        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(len(backend.submitted_requests), 1)
        submitted = backend.submitted_requests[0]
        self.assertEqual(submitted.metadata["vision_decision"]["route"], "text_only")

    async def test_multimodal_main_passes_attachments_and_vision_decision(self) -> None:
        backend = FakeBackendAdapter()
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.MULTIMODAL_MAIN),
        )
        req = _make_request(turn=_make_image_turn())

        run = await runtime.create_run(req)

        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(len(backend.submitted_requests), 1)
        submitted = backend.submitted_requests[0]
        self.assertEqual(submitted.metadata["vision_decision"]["route"], "multimodal_main")
        self.assertEqual(len(submitted.turn.attachments), 1)
        self.assertEqual(submitted.turn.attachments[0].kind, "image")

    async def test_fail_closed_returns_synthetic_run_without_backend_call(self) -> None:
        backend = FakeBackendAdapter()
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.FAIL_CLOSED),
        )
        req = _make_request(turn=_make_image_turn())

        run = await runtime.create_run(req)

        self.assertEqual(len(backend.submitted_requests), 0)
        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertIsNotNone(run.result)
        self.assertEqual(run.result.content, FAIL_CLOSED_NOTICE)
        self.assertEqual(run.result.status, AgentResultStatus.FAILED)
        self.assertEqual(run.result.reply_type, ReplyType.TEXT)
        self.assertIsNotNone(run.result.error)
        self.assertEqual(run.result.error.category, ErrorCategory.CONTRACT_ERROR)
        self.assertEqual(run.metadata["vision_decision"]["route"], "fail_closed")

    async def test_vision_then_main_calls_vision_runner_then_backend(self) -> None:
        backend = FakeBackendAdapter()
        vision_runner = _FakeVisionBackendAdapter()
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.VISION_THEN_MAIN),
            vision_runner=vision_runner,
        )
        req = _make_request(turn=_make_image_turn(content="What is in this image?"))

        run = await runtime.create_run(req)

        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(len(vision_runner.submitted_requests), 1)
        self.assertEqual(len(backend.submitted_requests), 1)

        # Vision runner received the original request with attachments and vision_decision.
        vision_req = vision_runner.submitted_requests[0]
        self.assertEqual(len(vision_req.turn.attachments), 1)
        self.assertEqual(vision_req.metadata["vision_decision"]["route"], "vision_then_main")

        # Main backend received combined content and no attachments.
        main_req = backend.submitted_requests[0]
        self.assertEqual(len(main_req.turn.attachments), 0)
        self.assertIn("A person in a red hat.", main_req.turn.content)
        self.assertIn("vision_run_id", main_req.metadata)
        self.assertEqual(
            main_req.metadata["vision_decision"]["vision_provider_id"],
            "vision-provider-001",
        )
        self.assertEqual(
            main_req.metadata["vision_decision"]["vision_model_id"],
            "vision-model-001",
        )

    async def test_vision_then_main_without_runner_fails_closed(self) -> None:
        backend = FakeBackendAdapter()
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.VISION_THEN_MAIN),
        )
        req = _make_request(turn=_make_image_turn())

        run = await runtime.create_run(req)

        self.assertEqual(len(backend.submitted_requests), 0)
        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertEqual(run.result.content, FAIL_CLOSED_NOTICE)

    async def test_vision_runner_failure_fails_closed(self) -> None:
        backend = FakeBackendAdapter()
        vision_runner = FakeBackendAdapter(submit_statuses=(AsyncTaskState.FAILED,))
        runtime = self._make_runtime(
            backend,
            vision_resolver=lambda req: _vision_decision(VisionRoute.VISION_THEN_MAIN),
            vision_runner=vision_runner,
        )
        req = _make_request(turn=_make_image_turn())

        run = await runtime.create_run(req)

        self.assertEqual(len(backend.submitted_requests), 0)
        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertEqual(run.result.content, FAIL_CLOSED_NOTICE)
