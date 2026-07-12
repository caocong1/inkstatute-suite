"""Tests for the operator-config vision resolver builder."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from platform_contract.enums import Channel, MessageType
from platform_contract.events import AgentTurn, AttachmentRef
from platform_runtime import RunRequest, SolutionBinding, VisionRoute

from platform_runtime import RuntimeFeatureFlags

from inkstatute_operator_config import (
    CatalogSelectionDoc,
    OperatorConfigDocument,
    OperatorConfigStore,
    ProviderDoc,
    VisionPolicyDoc,
    build_vision_resolver,
)


FIXED_NOW = "2026-07-12T00:00:00Z"


class _FakeBackend:
    def __init__(self, supports_vision: bool = False) -> None:
        self._supports_vision = supports_vision

    def capabilities(self):
        class _Caps:
            supports_vision = self._supports_vision

        return _Caps()


def _make_run_request(content: str = "describe", *, image: bool = False) -> RunRequest:
    attachments = ()
    if image:
        attachments = (
            AttachmentRef(
                attachment_id="att-001",
                kind="image",
                uri="fixture://images/test.png",
                name="test.png",
                mime_type="image/png",
            ),
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
            attachments=list(attachments),
        ),
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
        metadata={},
    )


class BuildVisionResolverTests(unittest.TestCase):
    def test_missing_store_fail_closed_on_image(self) -> None:
        resolver = build_vision_resolver()
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertEqual(decision.metadata.get("image_count"), 1)

    def test_missing_store_text_only(self) -> None:
        resolver = build_vision_resolver()
        req = _make_run_request(image=False)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.TEXT_ONLY)

    def test_multimodal_main_when_catalog_supports_vision(self) -> None:
        document = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    enabled=True,
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
            vision=VisionPolicyDoc(routing_mode="auto"),
        )
        store = _InMemoryStore(document)
        resolver = build_vision_resolver(store=store)
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)
        self.assertIs(decision.metadata.get("main_supports_vision"), True)

    def test_multimodal_main_with_provider_registry_mapping(self) -> None:
        document = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="my-openai",
                    kind="openai",
                    enabled=True,
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
            catalog=CatalogSelectionDoc(provider_id="my-openai", model_id="gpt-5"),
            vision=VisionPolicyDoc(routing_mode="auto"),
        )
        store = _InMemoryStore(document)
        resolver = build_vision_resolver(store=store)
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)

    def test_vision_then_main_when_vision_pair_configured(self) -> None:
        document = OperatorConfigDocument(
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-4"),
            vision=VisionPolicyDoc(
                routing_mode="auto",
                vision_provider_id="openai",
                vision_model_id="gpt-5",
            ),
        )
        store = _InMemoryStore(document)
        resolver = build_vision_resolver(
            store=store,
            vision_runner=_FakeBackend(),
        )
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.VISION_THEN_MAIN)
        self.assertEqual(decision.metadata.get("vision_provider_id"), "openai")
        self.assertEqual(decision.metadata.get("vision_model_id"), "gpt-5")

    def test_vision_pair_without_runner_fails_closed(self) -> None:
        document = OperatorConfigDocument(
            vision=VisionPolicyDoc(
                routing_mode="auto",
                vision_provider_id="openai",
                vision_model_id="gpt-5",
            ),
        )
        store = _InMemoryStore(document)
        resolver = build_vision_resolver(store=store)
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)

    def test_backend_override_disables_main_vision(self) -> None:
        document = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    enabled=True,
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
            vision=VisionPolicyDoc(routing_mode="auto"),
        )
        store = _InMemoryStore(document)
        backend = _FakeBackend(supports_vision=False)
        resolver = build_vision_resolver(store=store, backend=backend)
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertIs(decision.metadata.get("main_supports_vision"), False)
        self.assertIs(decision.metadata.get("backend_supports_vision"), False)

    def test_backend_supports_vision_keeps_multimodal(self) -> None:
        document = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    enabled=True,
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
            vision=VisionPolicyDoc(routing_mode="auto"),
        )
        store = _InMemoryStore(document)
        backend = _FakeBackend(supports_vision=True)
        resolver = build_vision_resolver(store=store, backend=backend)
        req = _make_run_request(image=True)

        decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)

    def test_store_load_wins_with_real_store(self) -> None:
        document = OperatorConfigDocument(
            providers=(
                ProviderDoc(
                    provider_id="openai",
                    kind="openai",
                    enabled=True,
                    api_base_url="https://api.openai.com/v1",
                ),
            ),
            catalog=CatalogSelectionDoc(provider_id="openai", model_id="gpt-5"),
            vision=VisionPolicyDoc(routing_mode="main_only"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "operator-config.json"
            store = OperatorConfigStore(path=path)
            store.save(document, feature_flags=RuntimeFeatureFlags(operator_config_enabled=True))
            resolver = build_vision_resolver(store=store)
            req = _make_run_request(image=True)

            decision = resolver(req)

        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)


class _InMemoryStore:
    """Duck-typed store for tests without touching the filesystem."""

    def __init__(self, document: OperatorConfigDocument) -> None:
        fd, raw_path = tempfile.mkstemp(suffix="-operator-config.json")
        import os

        os.close(fd)
        self.path = Path(raw_path)
        self._document = document

    def load(self) -> OperatorConfigDocument:
        return self._document


if __name__ == "__main__":
    unittest.main()
