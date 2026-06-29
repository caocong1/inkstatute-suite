"""WeCom ChannelAdapter wrapper over sanitized WeCom service primitives."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from platform_contract.events import (
    AgentTurn,
    AttachmentRef,
    FeedbackEvent,
    OutputConstraints,
    SkillCandidate,
)
from platform_runtime.protocols import (
    AckResponse,
    ChannelCapabilitySet,
    ChannelDelivery,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
)
from wecom_service.normalization import normalize_wecom_feedback_callback, normalize_wecom_turn
from wecom_service.protocol import ack_response, parse_callback_envelope
from wecom_service.sender import (
    build_file_send_envelope,
    build_template_card_envelope,
    build_text_send_envelope,
)

from .config import WeComChannelConfig

JsonObject = dict[str, Any]


class WeComChannelAdapter:
    """ChannelAdapter implementation for sanitized WeCom callbacks and sends."""

    def __init__(self, config: WeComChannelConfig | None = None) -> None:
        self._config = config or WeComChannelConfig()

    def channel_id(self) -> str:
        return self._config.channel_id

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=True,
            supports_cards=True,
            supports_streaming=False,
            ack_deadline_ms=5000,
            idempotency_strategy="wecom_callback_metadata",
            metadata={
                "enabled": self._config.enabled,
                "network_io": False,
                "secret_refs_configured": {
                    "token": self._config.token_secret_ref is not None,
                    "encoding_aes_key": self._config.encoding_aes_key_secret_ref is not None,
                    "corp_id": self._config.corp_id_ref is not None,
                },
            },
        )

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        callback = self._callback_from_raw(raw)
        parsed = parse_callback_envelope(callback)
        return AckResponse(
            accepted=self._config.enabled,
            status_code=200 if self._config.enabled else 503,
            idempotency_key=raw.idempotency_key,
            metadata={
                "ack_body": ack_response(),
                "channel_id": self._config.channel_id,
                "raw_payload_ref": parsed.get("raw_payload_ref") or raw.payload_ref,
                "signature_status": "secret_ref_required",
                "network_io": False,
            },
        )

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
        callback = self._callback_from_raw(raw)
        parsed = parse_callback_envelope(callback)
        if _is_feedback_callback(callback, parsed):
            feedback = normalize_wecom_feedback_callback(callback, created_at=raw.received_at)
            return InboundNormalized(
                feedback=_feedback_event_from_mapping(feedback),
                metadata={
                    "channel_id": self._config.channel_id,
                    "payload_ref": raw.payload_ref,
                    "normalized_type": "feedback_event",
                },
            )

        turn = normalize_wecom_turn(callback, received_at=raw.received_at)
        return InboundNormalized(
            message=_agent_turn_from_mapping(turn),
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "agent_turn",
            },
        )

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        to_user = _required_string(delivery.metadata, "to_user")
        delivery_type = _delivery_type(delivery)
        content = _delivery_text(delivery)

        if delivery_type == "file":
            media_id = _media_id(delivery)
            envelope = build_file_send_envelope(to_user=to_user, media_id=media_id, description=content)
        elif delivery_type == "card":
            envelope = build_template_card_envelope(
                to_user=to_user,
                card_id=_required_string(delivery.metadata, "card_id"),
                title=content or "请评价本次回复",
                feedback_target=_feedback_target(delivery),
            )
        else:
            envelope = build_text_send_envelope(to_user=to_user, text=content or "")

        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=envelope.get("policy", {}).get("action") != "block",
            delivered_at=_now(),
            idempotency_key=_optional_string(delivery.metadata.get("idempotency_key")),
            metadata={
                "channel_id": self._config.channel_id,
                "message_type": envelope.get("msgtype", delivery_type),
                "envelope": envelope,
                "network_io": False,
            },
        )

    async def health(self) -> ComponentHealth:
        return ComponentHealth(
            ok=self._config.enabled,
            component_id=f"{self._config.channel_id}-channel",
            checked_at=_now(),
            detail="enabled" if self._config.enabled else "disabled",
            metadata={
                "channel_id": self._config.channel_id,
                "network_io": False,
                "secret_refs_configured": {
                    "token": self._config.token_secret_ref is not None,
                    "encoding_aes_key": self._config.encoding_aes_key_secret_ref is not None,
                    "corp_id": self._config.corp_id_ref is not None,
                },
            },
        )

    def _callback_from_raw(self, raw: RawInbound) -> JsonObject:
        callback = raw.metadata.get("callback")
        if isinstance(callback, Mapping):
            fields_map: JsonObject = dict(callback)
        else:
            fields_map = dict(raw.metadata)
            fields_map.pop("callback", None)
        fields_map.setdefault("raw_payload_ref", raw.payload_ref)
        return fields_map


def _is_feedback_callback(callback: Mapping[str, Any], parsed: Mapping[str, Any]) -> bool:
    if any(key in callback for key in ("feedback_target", "FeedbackTarget", "feedback_action", "button_action")):
        return True
    event_key = str(parsed.get("event_key") or "").lower()
    return event_key.startswith("feedback:") or parsed.get("message_type") == "button_callback"


def _agent_turn_from_mapping(values: Mapping[str, Any]) -> AgentTurn:
    payload = dict(values)
    payload["attachments"] = [
        _dataclass_from_mapping(AttachmentRef, attachment) for attachment in payload.get("attachments", [])
    ]
    if isinstance(payload.get("output_constraints"), Mapping):
        payload["output_constraints"] = _dataclass_from_mapping(
            OutputConstraints, payload["output_constraints"]
        )
    return _dataclass_from_mapping(AgentTurn, payload)


def _feedback_event_from_mapping(values: Mapping[str, Any]) -> FeedbackEvent:
    payload = dict(values)
    if isinstance(payload.get("skill_candidate"), Mapping):
        payload["skill_candidate"] = _dataclass_from_mapping(SkillCandidate, payload["skill_candidate"])
    return _dataclass_from_mapping(FeedbackEvent, payload)


def _dataclass_from_mapping(cls: type[Any], values: Mapping[str, Any]) -> Any:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in values.items() if key in allowed})


def _delivery_type(delivery: ChannelDelivery) -> str:
    value = (
        delivery.metadata.get("delivery_type")
        or delivery.metadata.get("message_type")
        or delivery.metadata.get("kind")
        or "text"
    )
    text = str(value).strip().lower()
    aliases = {"template_card": "card", "file_ref": "file"}
    return aliases.get(text, text)


def _delivery_text(delivery: ChannelDelivery) -> str | None:
    if delivery.content is not None:
        return delivery.content
    if delivery.result is not None:
        return delivery.result.content
    return _optional_string(delivery.metadata.get("text"))


def _media_id(delivery: ChannelDelivery) -> str:
    value = delivery.metadata.get("media_id")
    if value is not None:
        return _required_string(delivery.metadata, "media_id")
    if delivery.artifact_refs:
        return delivery.artifact_refs[0]
    raise ValueError("file delivery requires media_id metadata or artifact_refs")


def _feedback_target(delivery: ChannelDelivery) -> str:
    value = delivery.metadata.get("feedback_target")
    if value is not None:
        return _required_string(delivery.metadata, "feedback_target")
    if delivery.result is not None and delivery.result.feedback_target:
        return delivery.result.feedback_target
    raise ValueError("card delivery requires feedback_target metadata or result.feedback_target")


def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = _optional_string(values.get(key))
    if value is None:
        raise ValueError(f"WeCom delivery requires {key}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["WeComChannelAdapter"]
