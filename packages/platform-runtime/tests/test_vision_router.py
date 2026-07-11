"""Tests for the platform-runtime vision router (VIS-02/03/04)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from platform_contract.enums import Channel, MessageType
from platform_contract.events import AgentTurn, AttachmentRef
from platform_runtime import (
    BoundaryAction,
    DefaultAssistantOutputBoundary,
    VisionRoute,
    VisionRouter,
    VisionRoutingDecision,
)
from platform_runtime.vision_router import FAIL_CLOSED_NOTICE, has_image_attachments

FIXED_NOW = "2026-07-11T00:00:00Z"


def _text_turn() -> AgentTurn:
    return AgentTurn(
        turn_id="turn-text-001",
        conversation_id="conv-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at=FIXED_NOW,
        content="summarize the contract",
        attachments=[],
    )


def _image_turn(*, count: int = 1) -> AgentTurn:
    return AgentTurn(
        turn_id="turn-image-001",
        conversation_id="conv-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at=FIXED_NOW,
        content="describe the attached image",
        attachments=[
            AttachmentRef(
                attachment_id=f"att-{i:02d}",
                kind="image",
                uri=f"fixture://images/test-{i:02d}.png",
                name=f"test-{i:02d}.png",
                mime_type="image/png",
            )
            for i in range(count)
        ],
    )


def _policy(routing_mode: str | None, *, vision_pair: bool = False):
    """Lightweight duck-typed vision policy (no operator-config import)."""
    return SimpleNamespace(
        routing_mode=routing_mode,
        main_model_id="main-model",
        vision_model_id="vision-model" if vision_pair else None,
        vision_provider_id="vision-provider" if vision_pair else None,
    )


class ImageDetectionTests(unittest.TestCase):
    def test_detects_image_by_kind(self) -> None:
        turn = AgentTurn(
            turn_id="t",
            conversation_id="c",
            channel=Channel.WEB,
            user_id="u",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            attachments=[AttachmentRef(attachment_id="a1", kind="image", uri="fixture://x.png")],
        )
        self.assertTrue(has_image_attachments(turn))

    def test_detects_image_by_mime_type_with_file_kind(self) -> None:
        turn = AgentTurn(
            turn_id="t",
            conversation_id="c",
            channel=Channel.WEB,
            user_id="u",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            attachments=[
                AttachmentRef(attachment_id="a1", kind="file", uri="fixture://x.png", mime_type="image/png")
            ],
        )
        self.assertTrue(has_image_attachments(turn))

    def test_returns_false_for_non_image_mime_type(self) -> None:
        turn = AgentTurn(
            turn_id="t",
            conversation_id="c",
            channel=Channel.WEB,
            user_id="u",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            attachments=[
                AttachmentRef(attachment_id="a1", kind="file", uri="fixture://x.pdf", mime_type="application/pdf")
            ],
        )
        self.assertFalse(has_image_attachments(turn))

    def test_returns_false_for_empty_attachments(self) -> None:
        self.assertFalse(has_image_attachments(_text_turn()))

    def test_returns_false_for_none_mime_type_non_image_kind(self) -> None:
        turn = AgentTurn(
            turn_id="t",
            conversation_id="c",
            channel=Channel.WEB,
            user_id="u",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            attachments=[AttachmentRef(attachment_id="a1", kind="file", uri="fixture://x.bin")],
        )
        self.assertFalse(has_image_attachments(turn))

    def test_mime_type_prefix_is_case_insensitive(self) -> None:
        turn = AgentTurn(
            turn_id="t",
            conversation_id="c",
            channel=Channel.WEB,
            user_id="u",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            attachments=[
                AttachmentRef(attachment_id="a1", kind="file", uri="fixture://x.jpg", mime_type="IMAGE/JPEG")
            ],
        )
        self.assertTrue(has_image_attachments(turn))


class FailClosedNoticeTests(unittest.TestCase):
    def test_notice_has_no_provider_or_trace_language(self) -> None:
        lowered = FAIL_CLOSED_NOTICE.lower()
        for forbidden in ("stack trace", "traceback", "api key", "provider", "model:", "quota", "token"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_notice_passes_through_output_boundary_unmodified(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=FAIL_CLOSED_NOTICE,
        )
        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, FAIL_CLOSED_NOTICE)


class VisionRoutingDecisionShapeTests(unittest.TestCase):
    def test_route_enum_has_four_values(self) -> None:
        self.assertEqual(
            {r.value for r in VisionRoute},
            {"multimodal_main", "vision_then_main", "fail_closed", "text_only"},
        )

    def test_decision_is_frozen(self) -> None:
        decision = VisionRoutingDecision(route=VisionRoute.TEXT_ONLY)
        with self.assertRaises(Exception):
            decision.route = VisionRoute.FAIL_CLOSED  # type: ignore[misc]


class VisionRouterDecideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = VisionRouter()

    def _boundary_allows(self, decision: VisionRoutingDecision) -> None:
        if decision.notice is None:
            return
        boundary_decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=decision.notice,
        )
        self.assertEqual(boundary_decision.action, BoundaryAction.ALLOW)

    def _assert_no_raw_bytes(self, decision: VisionRoutingDecision) -> None:
        blob = repr(decision.metadata) + repr(decision.notice) + decision.reason
        self.assertNotIn("base64", blob.lower())
        for key in ("image_bytes", "bytes", "endpoint", "api_base_url"):
            self.assertNotIn(key, decision.metadata)

    def test_text_only_turn_auto_returns_text_only(self) -> None:
        decision = self.router.decide(_text_turn(), _policy("auto"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.TEXT_ONLY)
        self.assertEqual(decision.reason, "no_image_attachments")
        self.assertIsNone(decision.notice)

    def test_text_only_turn_main_only_returns_text_only(self) -> None:
        decision = self.router.decide(_text_turn(), _policy("main_only"), main_supports_vision=False, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.TEXT_ONLY)

    def test_image_auto_main_supports_vision_returns_multimodal_main(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("auto"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)
        self.assertEqual(decision.reason, "main_supports_vision")
        self.assertIsNone(decision.notice)

    def test_image_auto_no_main_vision_pair_returns_vision_then_main(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("auto"), main_supports_vision=False, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.VISION_THEN_MAIN)
        self.assertEqual(decision.reason, "vision_then_main_mix")
        self.assertIsNone(decision.notice)

    def test_image_auto_no_path_returns_fail_closed(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("auto"), main_supports_vision=False, vision_pair_configured=False)
        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertEqual(decision.notice, FAIL_CLOSED_NOTICE)
        self.assertEqual(decision.reason, "no_vision_capable_path")
        self._boundary_allows(decision)

    def test_image_always_preprocess_vision_pair_returns_vision_then_main(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("always_preprocess"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.VISION_THEN_MAIN)
        self.assertEqual(decision.reason, "always_preprocess_vision_mix")

    def test_image_always_preprocess_no_pair_returns_fail_closed(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("always_preprocess"), main_supports_vision=True, vision_pair_configured=False)
        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertEqual(decision.reason, "no_vision_pair_configured")
        self._boundary_allows(decision)

    def test_image_main_only_supports_vision_returns_multimodal_main(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("main_only"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)
        self.assertEqual(decision.reason, "main_only_supports_vision")

    def test_image_main_only_no_vision_support_returns_fail_closed(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("main_only"), main_supports_vision=False, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertEqual(decision.reason, "main_only_no_vision_support")
        self._boundary_allows(decision)

    def test_image_routing_mode_none_defaults_to_auto(self) -> None:
        decision = self.router.decide(_image_turn(), _policy(None), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.MULTIMODAL_MAIN)
        self.assertEqual(decision.reason, "main_supports_vision")

    def test_image_routing_mode_none_no_path_fail_closed(self) -> None:
        decision = self.router.decide(_image_turn(), _policy(None), main_supports_vision=False, vision_pair_configured=False)
        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self._boundary_allows(decision)

    def test_image_unsupported_routing_mode_returns_fail_closed(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("invalid"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.route, VisionRoute.FAIL_CLOSED)
        self.assertEqual(decision.reason, "unsupported_routing_mode")
        self._boundary_allows(decision)
        # never leaks the invalid value
        self.assertNotIn("invalid", repr(decision.metadata))

    def test_metadata_contains_image_count_integer(self) -> None:
        decision = self.router.decide(_image_turn(count=3), _policy("auto"), main_supports_vision=True, vision_pair_configured=True)
        self.assertEqual(decision.metadata["image_count"], 3)
        self.assertIsInstance(decision.metadata["image_count"], int)
        self._assert_no_raw_bytes(decision)

    def test_metadata_never_contains_raw_bytes_or_uris(self) -> None:
        decision = self.router.decide(_image_turn(), _policy("auto"), main_supports_vision=False, vision_pair_configured=False)
        self._assert_no_raw_bytes(decision)
        for key in ("uri", "uris", "attachments", "image_uri"):
            self.assertNotIn(key, decision.metadata)


if __name__ == "__main__":
    unittest.main()
