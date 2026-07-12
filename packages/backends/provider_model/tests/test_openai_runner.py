"""Tests for the OpenAI-compatible runner image attachment support."""

from __future__ import annotations

import unittest

from platform_contract.enums import Channel, MessageType
from platform_contract.events import AgentTurn, AttachmentRef
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeOpenAITransport,
    OpenAIClientRunner,
)


FIXED_NOW = "2026-07-12T00:00:00Z"


class _CapturingTransport(FakeOpenAITransport):
    """Fake transport that records the payload for assertions."""

    def __init__(self) -> None:
        super().__init__(response={"choices": [{"message": {"content": "ok"}}]})
        self.request_payload: dict[str, object] | None = None

    async def create_chat_completion(self, request_payload: dict[str, object]) -> dict[str, object]:
        self.request_payload = request_payload
        return {"choices": [{"message": {"content": "ok"}}]}


def _make_request(*, image: bool = False, content: str = "What is in this image?") -> RunRequest:
    attachments = (
        [
            AttachmentRef(
                attachment_id="att-001",
                kind="image",
                uri="https://example.com/image.png",
                name="image.png",
                mime_type="image/png",
            )
        ]
        if image
        else []
    )
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content=content,
            attachments=attachments,
        ),
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
        metadata={},
    )


class OpenAIClientRunnerImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_only_request_uses_string_content(self) -> None:
        transport = _CapturingTransport()
        runner = OpenAIClientRunner(transport=transport)

        await runner.invoke(_make_request(image=False, content="Hello"))

        self.assertIsNotNone(transport.request_payload)
        messages = transport.request_payload["messages"]
        self.assertEqual(messages, [{"role": "user", "content": "Hello"}])

    async def test_image_request_uses_list_content_with_image_url(self) -> None:
        transport = _CapturingTransport()
        runner = OpenAIClientRunner(transport=transport)

        await runner.invoke(_make_request(image=True, content="What is in this image?"))

        self.assertIsNotNone(transport.request_payload)
        messages = transport.request_payload["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0], {"type": "text", "text": "What is in this image?"})
        self.assertEqual(
            content[1],
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image.png", "detail": "auto"},
            },
        )

    async def test_image_without_content_omits_text_part(self) -> None:
        transport = _CapturingTransport()
        runner = OpenAIClientRunner(transport=transport)

        await runner.invoke(_make_request(image=True, content=""))

        messages = transport.request_payload["messages"]
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "image_url")

    async def test_image_detected_by_mime_type_with_file_kind(self) -> None:
        from dataclasses import replace

        req = _make_request(image=False)
        turn = replace(
            req.turn,
            attachments=[
                AttachmentRef(
                    attachment_id="att-001",
                    kind="file",
                    uri="https://example.com/image.jpg",
                    name="image.jpg",
                    mime_type="image/jpeg",
                )
            ],
        )
        req = replace(req, turn=turn)
        transport = _CapturingTransport()
        runner = OpenAIClientRunner(transport=transport)

        await runner.invoke(req)

        messages = transport.request_payload["messages"]
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        image_parts = [part for part in content if part.get("type") == "image_url"]
        self.assertEqual(len(image_parts), 1)
        self.assertEqual(
            image_parts[0]["image_url"]["url"],
            "https://example.com/image.jpg",
        )


if __name__ == "__main__":
    unittest.main()
