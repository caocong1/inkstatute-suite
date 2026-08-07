"""Fixture-grade Web/SSE ChannelAdapter implementation."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
import hashlib
from typing import Any, Mapping

from platform_contract.events import AgentTurn, FeedbackEvent, SkillCandidate
from platform_runtime.protocols import (
    AckResponse,
    ChannelCapabilitySet,
    ChannelDelivery,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
)

from .config import WebSseChannelConfig

JsonObject = dict[str, Any]


class WebSseChannelAdapter:
    """Sanitized Web/SSE channel adapter with no server or network side effects."""

    def __init__(self, config: WebSseChannelConfig | None = None) -> None:
        self._config = config or WebSseChannelConfig()
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return self._config.channel_id

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=True,
            supports_cards=False,
            supports_streaming=True,
            ack_deadline_ms=1000,
            idempotency_strategy="web_payload_ref",
            verify_and_ack_support=False,
            metadata={"enabled": self._config.enabled, "fixture_only": True, "network_io": False},
        )

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        payload = self._payload_from_raw(raw)
        return AckResponse(
            accepted=self._config.enabled,
            status_code=202 if self._config.enabled else 503,
            idempotency_key=raw.idempotency_key or _stable_id("web-ack", raw.payload_ref),
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "fixture_only": True,
                "payload_kind": payload.get("type") or payload.get("kind") or "message",
            },
        )

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
        payload = self._payload_from_raw(raw)
        if _is_feedback_payload(payload):
            return InboundNormalized(
                feedback=_feedback_from_payload(raw, payload),
                metadata={
                    "channel_id": self._config.channel_id,
                    "payload_ref": raw.payload_ref,
                    "normalized_type": "feedback_event",
                    "fixture_only": True,
                },
            )
        return InboundNormalized(
            message=_turn_from_payload(raw, payload),
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "agent_turn",
                "fixture_only": True,
            },
        )

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        self.deliveries.append(delivery)
        metadata = {
            "channel_id": self._config.channel_id,
            "delivery_type": str(delivery.metadata.get("delivery_type") or "text"),
            "artifact_refs": list(delivery.artifact_refs),
            "content_ref": delivery.metadata.get("content_ref"),
            "output_policy_action_ref": delivery.metadata.get("output_policy_action_ref"),
            "fixture_only": True,
            "network_io": False,
        }
        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=self._config.enabled,
            delivered_at=_now(),
            idempotency_key=_optional_string(delivery.metadata.get("idempotency_key"))
            or _stable_id("web-delivery", delivery.delivery_id),
            metadata={key: value for key, value in metadata.items() if value not in (None, [], {})},
        )

    async def health(self) -> ComponentHealth:
        return ComponentHealth(
            ok=self._config.enabled,
            component_id=f"{self._config.channel_id}-sse-channel",
            checked_at=_now(),
            detail="fixture channel enabled" if self._config.enabled else "fixture channel disabled",
            metadata={
                "fixture_only": True,
                "network_io": False,
                "session_secret_ref_configured": self._config.session_secret_ref is not None,
            },
        )

    def _payload_from_raw(self, raw: RawInbound) -> JsonObject:
        payload = raw.metadata.get("payload")
        if isinstance(payload, Mapping):
            values: JsonObject = dict(payload)
        else:
            values = dict(raw.metadata)
            values.pop("payload", None)
        _assert_no_forbidden_payload_keys(values)
        values.setdefault("payload_ref", raw.payload_ref)
        return values


def _turn_from_payload(raw: RawInbound, payload: Mapping[str, Any]) -> AgentTurn:
    metadata = _metadata(payload, raw)
    metadata["content_source_status"] = "reference_only" if payload.get("content_ref") else "not_provided"
    return AgentTurn(
        turn_id=_optional_string(payload.get("turn_id")) or _stable_id("web-turn", raw.payload_ref),
        conversation_id=_required_string(payload, "conversation_id"),
        channel="web",
        user_id=_required_string(payload, "user_id"),
        message_type=_optional_string(payload.get("message_type")) or "text",
        received_at=raw.received_at,
        content=_optional_string(payload.get("content")),
        industry_context=_mapping_or_empty(payload.get("industry_context")),
        metadata=metadata,
    )


def _feedback_from_payload(raw: RawInbound, payload: Mapping[str, Any]) -> FeedbackEvent:
    action = _feedback_action(payload)
    event_type = "rating" if action == "up" else "route_mismatch" if action == "route_wrong" else "correction"
    fields_map: JsonObject = {
        "feedback_id": _optional_string(payload.get("feedback_id")) or _stable_id("web-feedback", raw.payload_ref),
        "turn_id": _optional_string(payload.get("turn_id")) or _stable_id("web-turn", raw.payload_ref),
        "conversation_id": _required_string(payload, "conversation_id"),
        "user_id": _required_string(payload, "user_id"),
        "source": "web_form",
        "event_type": event_type,
        "status": "pending",
        "created_at": raw.received_at,
        "feedback_target": _required_string(payload, "feedback_target"),
        "action": action,
        "message": _optional_string(payload.get("message")),
        "industry_context": _mapping_or_empty(payload.get("industry_context")),
        "metadata": _metadata(payload, raw),
    }
    if action == "up":
        fields_map["rating"] = 1.0
    if action == "route_wrong":
        fields_map["route_mismatch"] = True
        fields_map["skill_candidate"] = SkillCandidate(
            detected=True,
            source="route_mismatch",
            proposed_name=_optional_string(payload.get("proposed_skill")) or "web.route_review_candidate",
            risk_level="high",
            requires_human_review=True,
            evidence=[raw.payload_ref, _required_string(payload, "feedback_target")],
            metadata={"fixture_only": True, "no_auto_modify": True},
        )
    return _dataclass_from_mapping(FeedbackEvent, fields_map)


def _metadata(payload: Mapping[str, Any], raw: RawInbound) -> JsonObject:
    metadata = {
        "payload_ref": raw.payload_ref,
        "idempotency_key": raw.idempotency_key or _stable_id("web-inbound", raw.payload_ref),
        "content_ref": payload.get("content_ref"),
        "content_hash": payload.get("content_hash"),
        "source_event": "web_sse_fixture",
        "source_status": "sanitized_fixture",
        "fixture_only": True,
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _is_feedback_payload(payload: Mapping[str, Any]) -> bool:
    kind = str(payload.get("type") or payload.get("kind") or "").lower()
    return kind == "feedback" or "feedback_target" in payload or "action" in payload


def _feedback_action(payload: Mapping[str, Any]) -> str:
    action = (_optional_string(payload.get("action")) or "needs_fix").split(":")[-1].lower()
    aliases = {
        "thumbs_up": "up",
        "like": "up",
        "thumbs_down": "down",
        "dislike": "down",
        "fix": "needs_fix",
        "route_mismatch": "route_wrong",
    }
    action = aliases.get(action, action)
    if action not in {"up", "down", "needs_fix", "route_wrong"}:
        raise ValueError(f"unsupported Web/SSE feedback action {action!r}")
    return action


def _assert_no_forbidden_payload_keys(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in {"rawpayload", "rawbody", "callbackbody"}:
                raise ValueError(f"Web/SSE payload contains forbidden raw payload key at {child_path}")
            _assert_no_forbidden_payload_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_payload_keys(child, f"{path}[{index}]")


def _dataclass_from_mapping(cls: type[Any], values: Mapping[str, Any]) -> Any:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in values.items() if key in allowed})


def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = _optional_string(values.get(key))
    if value is None:
        raise ValueError(f"Web/SSE payload requires {key}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _mapping_or_empty(value: Any) -> JsonObject:
    return dict(value) if isinstance(value, Mapping) else {}


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["WebSseChannelAdapter"]
