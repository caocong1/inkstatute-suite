"""Platform-runtime vision router (VIS-02/03/04).

Pure decision function for image-bearing turns. The router decides between
``multimodal_main``, ``vision_then_main``, ``fail_closed``, and ``text_only``
routes according to operator vision policy, without invoking any model,
resolving secrets, making network calls, or reading raw image bytes.

Contract/audit evidence stays reference-first: only ``AttachmentRef.uri``
references are passed through and only attachment counts appear in decision
metadata — never raw image bytes, base64 data, or provider endpoint details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from platform_contract.events import AgentTurn, JsonObject

if TYPE_CHECKING:  # pragma: no cover - typing only
    from inkstatute_operator_config.schemas import VisionPolicyDoc

__all__ = [
    "FAIL_CLOSED_NOTICE",
    "VisionRoute",
    "VisionRouter",
    "VisionRoutingDecision",
    "has_image_attachments",
]


class VisionRoute(StrEnum):
    """Routing decision for an image-bearing turn."""

    MULTIMODAL_MAIN = "multimodal_main"
    VISION_THEN_MAIN = "vision_then_main"
    FAIL_CLOSED = "fail_closed"
    TEXT_ONLY = "text_only"


@dataclass(frozen=True, slots=True)
class VisionRoutingDecision:
    """Outcome of a vision routing decision.

    ``notice`` is an InkStatute-owned service notice string for fail-closed
    paths — never a provider stack trace, backend meta, or raw image bytes.
    ``metadata`` carries only reference-first routing evidence (reason codes
    and image attachment counts).
    """

    route: VisionRoute
    notice: str | None = None
    reason: str = ""
    metadata: JsonObject = field(default_factory=dict)


@runtime_checkable
class _VisionPolicyLike(Protocol):
    """Duck-typed vision policy (avoids a direct operator-config dependency)."""

    routing_mode: str | None
    vision_provider_id: str | None
    vision_model_id: str | None


# InkStatute-owned fail-closed notice. Intentionally free of provider names,
# model names, stack traces, backend meta, tokens, or quota language so it
# passes through DefaultAssistantOutputBoundary unmodified (VIS-04).
FAIL_CLOSED_NOTICE = (
    "InkStatute cannot process this image with the current model configuration. "
    "Please try again without the image or contact your administrator."
)


def has_image_attachments(turn: AgentTurn) -> bool:
    """Return True when ``turn.attachments`` contains an image reference.

    Detection checks ``kind == "image"`` or a ``mime_type`` starting with
    ``"image/"`` (case-insensitive). The function never reads ``uri`` content,
    never fetches the image, and never stores raw bytes (VIS-03 reference-first).
    """

    for attachment in turn.attachments:
        if getattr(attachment, "kind", None) == "image":
            return True
        mime_type = getattr(attachment, "mime_type", None)
        if mime_type and str(mime_type).lower().startswith("image/"):
            return True
    return False


def _image_attachment_count(turn: AgentTurn) -> int:
    """Count image attachments without reading raw bytes."""

    count = 0
    for attachment in turn.attachments:
        if getattr(attachment, "kind", None) == "image":
            count += 1
            continue
        mime_type = getattr(attachment, "mime_type", None)
        if mime_type and str(mime_type).lower().startswith("image/"):
            count += 1
    return count


class VisionRouter:
    """Pure vision routing decision function (no I/O, no model invocation)."""

    def decide(
        self,
        turn: AgentTurn,
        vision_policy: _VisionPolicyLike | "VisionPolicyDoc",
        *,
        main_supports_vision: bool,
        vision_pair_configured: bool,
    ) -> VisionRoutingDecision:
        """Return a routing decision for ``turn``.

        ``main_supports_vision`` is resolved by the caller from the catalog
        ``supports_vision`` metadata for the main model. ``vision_pair_configured``
        is True when both ``vision_provider_id`` and ``vision_model_id`` are set.
        The router makes zero network calls, zero secret resolutions, and zero
        model invocations.
        """

        image_count = _image_attachment_count(turn)

        if not has_image_attachments(turn):
            return VisionRoutingDecision(
                route=VisionRoute.TEXT_ONLY,
                reason="no_image_attachments",
                metadata={"image_count": image_count, "reason": "no_image_attachments"},
            )

        routing_mode = getattr(vision_policy, "routing_mode", None)

        if routing_mode in (None, "auto"):
            return self._decide_auto(
                main_supports_vision, vision_pair_configured, image_count
            )
        if routing_mode == "always_preprocess":
            return self._decide_always_preprocess(vision_pair_configured, image_count)
        if routing_mode == "main_only":
            return self._decide_main_only(main_supports_vision, image_count)
        return self._fail_closed("unsupported_routing_mode", image_count)

    def _decide_auto(
        self, main_supports_vision: bool, vision_pair_configured: bool, image_count: int
    ) -> VisionRoutingDecision:
        if main_supports_vision:
            return VisionRoutingDecision(
                route=VisionRoute.MULTIMODAL_MAIN,
                reason="main_supports_vision",
                metadata={"image_count": image_count, "reason": "main_supports_vision"},
            )
        if vision_pair_configured:
            return VisionRoutingDecision(
                route=VisionRoute.VISION_THEN_MAIN,
                reason="vision_then_main_mix",
                metadata={"image_count": image_count, "reason": "vision_then_main_mix"},
            )
        return self._fail_closed("no_vision_capable_path", image_count)

    def _decide_always_preprocess(
        self, vision_pair_configured: bool, image_count: int
    ) -> VisionRoutingDecision:
        if vision_pair_configured:
            return VisionRoutingDecision(
                route=VisionRoute.VISION_THEN_MAIN,
                reason="always_preprocess_vision_mix",
                metadata={
                    "image_count": image_count,
                    "reason": "always_preprocess_vision_mix",
                },
            )
        return self._fail_closed("no_vision_pair_configured", image_count)

    def _decide_main_only(
        self, main_supports_vision: bool, image_count: int
    ) -> VisionRoutingDecision:
        if main_supports_vision:
            return VisionRoutingDecision(
                route=VisionRoute.MULTIMODAL_MAIN,
                reason="main_only_supports_vision",
                metadata={
                    "image_count": image_count,
                    "reason": "main_only_supports_vision",
                },
            )
        return self._fail_closed("main_only_no_vision_support", image_count)

    def _fail_closed(self, reason: str, image_count: int) -> VisionRoutingDecision:
        return VisionRoutingDecision(
            route=VisionRoute.FAIL_CLOSED,
            notice=FAIL_CLOSED_NOTICE,
            reason=reason,
            metadata={"image_count": image_count, "reason": reason},
        )
