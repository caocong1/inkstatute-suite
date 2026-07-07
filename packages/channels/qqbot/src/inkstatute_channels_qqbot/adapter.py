"""QQBot ChannelAdapter implementation — fixture-grade, no network IO."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
import hashlib
from typing import Any, Mapping

from channel_core.idempotency import channel_idempotency_key
from channel_core.output_policy import apply_output_policy
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

from .config import QQBotChannelConfig
from .signature import (
    derive_keypair,
    handle_validation_challenge,
    verify_callback_signature,
)

JsonObject = dict[str, Any]


class QQBotChannelAdapter:
    """Sanitized QQBot channel adapter with no server or network side effects."""

    def __init__(self, config: QQBotChannelConfig | None = None) -> None:
        self._config = config or QQBotChannelConfig()
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return self._config.channel_id

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=False,
            supports_cards=True,
            supports_images=False,
            supports_voice=False,
            supports_streaming=False,
            ack_deadline_ms=3000,
            idempotency_strategy="qqbot_callback_metadata",
            metadata={
                "enabled": self._config.enabled,
                "fixture_only": True,
                "network_io": False,
                "secret_refs_configured": {
                    "app_id_ref": self._config.app_id_ref is not None,
                    "app_secret_ref": self._config.app_secret_ref is not None,
                    "token_secret_ref": self._config.token_secret_ref is not None,
                    "bot_secret_ref": self._config.bot_secret_ref is not None,
                },
            },
        )

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        payload = self._payload_from_raw(raw)
        idem_key = raw.idempotency_key or _stable_id("qqbot-ack", raw.payload_ref)
        base_meta: JsonObject = {
            "channel_id": self._config.channel_id,
            "payload_ref": raw.payload_ref,
            "fixture_only": True,
            "network_io": False,
            "payload_kind": payload.get("type") or payload.get("kind") or "message",
        }

        # Channel disabled → preserve existing 503 behavior.
        if not self._config.enabled:
            return AckResponse(
                accepted=False,
                status_code=503,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "channel_disabled"},
            )

        # BotSecret not configured → preserve existing stub behavior.
        if self._config.bot_secret_ref is None:
            return AckResponse(
                accepted=True,
                status_code=200,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "secret_ref_required"},
            )

        # Signature verification path (bot_secret_ref configured).
        sig_hex = raw.metadata.get("x_signature_ed25519")
        timestamp = raw.metadata.get("x_signature_timestamp")
        request_body = raw.metadata.get("request_body")
        bot_secret = raw.metadata.get("bot_secret")

        # Missing signature headers or bot_secret → reject with 401.
        if sig_hex is None or timestamp is None or request_body is None or bot_secret is None:
            return AckResponse(
                accepted=False,
                status_code=401,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "missing"},
            )

        # Derive keypair and verify the signature over timestamp + request_body.
        try:
            public_key, _seed = derive_keypair(bot_secret)
        except ValueError:
            # Empty or invalid bot_secret — reject without crash.
            return AckResponse(
                accepted=False,
                status_code=401,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "invalid"},
            )
        verified = verify_callback_signature(
            public_key, sig_hex, timestamp, request_body
        )
        if not verified:
            return AckResponse(
                accepted=False,
                status_code=401,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "invalid"},
            )

        # Signature verified — check for op=13 validation challenge.
        if payload.get("op") == 13:
            challenge_data = payload.get("d")
            if isinstance(challenge_data, Mapping):
                plain_token = _optional_string(challenge_data.get("plain_token"))
                event_ts = _optional_string(challenge_data.get("event_ts"))
                # Both fields required for a valid challenge — reject if missing.
                if plain_token and event_ts:
                    challenge_response = handle_validation_challenge(
                        bot_secret, plain_token, event_ts
                    )
                    return AckResponse(
                        accepted=True,
                        status_code=200,
                        idempotency_key=idem_key,
                        metadata={
                            **base_meta,
                            "signature_status": "verified",
                            "validation_challenge_response": challenge_response,
                        },
                    )
                # op=13 with missing plain_token/event_ts → reject as invalid.
                return AckResponse(
                    accepted=False,
                    status_code=401,
                    idempotency_key=idem_key,
                    metadata={**base_meta, "signature_status": "invalid_challenge"},
                )
            # op=13 with non-Mapping d → reject as invalid.
            return AckResponse(
                accepted=False,
                status_code=401,
                idempotency_key=idem_key,
                metadata={**base_meta, "signature_status": "invalid_challenge"},
            )

        return AckResponse(
            accepted=True,
            status_code=200,
            idempotency_key=idem_key,
            metadata={**base_meta, "signature_status": "verified"},
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
                    "idempotency_key": raw.idempotency_key
                    or channel_idempotency_key(payload, channel_prefix="qqbot"),
                    "fixture_only": True,
                },
            )
        return InboundNormalized(
            message=_turn_from_payload(raw, payload),
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "agent_turn",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        self.deliveries.append(delivery)
        delivery_type = str(delivery.metadata.get("delivery_type") or "text")
        content = delivery.content or ""
        policy = apply_output_policy(content)
        accepted = policy.action != "block"

        envelope: JsonObject
        if delivery_type == "card":
            envelope = _build_card_envelope(delivery, policy)
        else:
            envelope = _build_text_envelope(delivery, policy)

        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=accepted and self._config.enabled,
            delivered_at=_now() if accepted else None,
            idempotency_key=_optional_string(delivery.metadata.get("idempotency_key"))
            or _stable_id("qqbot-delivery", delivery.delivery_id),
            metadata={
                "channel_id": self._config.channel_id,
                "delivery_type": delivery_type,
                "message_type": delivery_type,
                "policy_action": policy.action,
                "policy_reason": policy.reason,
                "envelope": envelope,
                "fixture_only": True,
                "network_io": False,
            },
        )

    async def health(self) -> ComponentHealth:
        return ComponentHealth(
            ok=self._config.enabled,
            component_id="qqbot-channel",
            checked_at=_now(),
            detail="qqbot channel enabled" if self._config.enabled else "qqbot channel disabled",
            metadata={
                "fixture_only": True,
                "network_io": False,
                "secret_refs_configured": {
                    "app_id_ref": self._config.app_id_ref is not None,
                    "app_secret_ref": self._config.app_secret_ref is not None,
                    "token_secret_ref": self._config.token_secret_ref is not None,
                    "bot_secret_ref": self._config.bot_secret_ref is not None,
                },
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
        turn_id=_optional_string(payload.get("turn_id")) or _stable_id("qqbot-turn", raw.payload_ref),
        conversation_id=_required_string(payload, "conversation_id"),
        channel="qqbot",
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
        "feedback_id": _optional_string(payload.get("feedback_id"))
        or _stable_id("qqbot-feedback", raw.payload_ref),
        "turn_id": _optional_string(payload.get("turn_id")) or _stable_id("qqbot-turn", raw.payload_ref),
        "conversation_id": _required_string(payload, "conversation_id"),
        "user_id": _required_string(payload, "user_id"),
        "source": "card_button",
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
            proposed_name=_optional_string(payload.get("proposed_skill"))
            or "qqbot.route_review_candidate",
            risk_level="high",
            requires_human_review=True,
            evidence=[raw.payload_ref, _required_string(payload, "feedback_target")],
            metadata={"fixture_only": True, "no_auto_modify": True},
        )
    return _dataclass_from_mapping(FeedbackEvent, fields_map)


def _build_text_envelope(delivery: ChannelDelivery, policy: Any) -> JsonObject:
    envelope: JsonObject = {
        "msg_type": "text",
        "policy": {
            "action": policy.action,
            "reason": policy.reason,
        },
    }
    if policy.visible_text:
        envelope["content"] = policy.visible_text
    return envelope


def _build_card_envelope(delivery: ChannelDelivery, policy: Any) -> JsonObject:
    envelope: JsonObject = {
        "msg_type": "card",
        "policy": {
            "action": policy.action,
            "reason": policy.reason,
        },
    }
    if policy.visible_text:
        envelope["content"] = policy.visible_text
    return envelope


def _metadata(payload: Mapping[str, Any], raw: RawInbound) -> JsonObject:
    metadata = {
        "payload_ref": raw.payload_ref,
        "idempotency_key": raw.idempotency_key
        or channel_idempotency_key(payload, channel_prefix="qqbot"),
        "content_ref": payload.get("content_ref"),
        "content_hash": payload.get("content_hash"),
        "source_event": "qqbot_fixture",
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
        raise ValueError(f"unsupported QQBot feedback action {action!r}")
    return action


def _assert_no_forbidden_payload_keys(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in {"rawpayload", "rawbody", "callbackbody"}:
                raise ValueError(f"QQBot payload contains forbidden raw payload key at {child_path}")
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
        raise ValueError(f"QQBot payload requires {key}")
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


__all__ = ["QQBotChannelAdapter"]
