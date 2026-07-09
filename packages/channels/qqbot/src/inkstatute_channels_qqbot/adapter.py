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
from .sender import (
    SendError,
    build_feedback_keyboard_envelope,
    build_markdown_envelope,
    build_media_envelope,
    build_text_envelope,
    check_passive_reply_window,
    send_message,
    send_rich_media,
)
from .token_manager import TokenError
from .signature import (
    derive_keypair,
    handle_validation_challenge,
    verify_callback_signature,
)

JsonObject = dict[str, Any]


class QQBotChannelAdapter:
    """Sanitized QQBot channel adapter with no server or network side effects."""

    def __init__(
        self,
        config: QQBotChannelConfig | None = None,
        *,
        token_manager: Any = None,
        transport: Any = None,
    ) -> None:
        self._config = config or QQBotChannelConfig()
        self._token_manager = token_manager
        self._transport = transport
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return self._config.channel_id

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=True,
            supports_cards=True,
            supports_images=True,
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

        # Real QQ Bot gateway envelope {op, t, d} → delegate to normalization.py
        if _is_gateway_envelope(payload):
            return _normalize_gateway_envelope(raw, payload, self._config.channel_id)

        # Legacy fixture format (pre-normalized fields) → existing path
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
        delivery_type = _delivery_type(delivery)
        content = _delivery_text(delivery) or ""
        policy = apply_output_policy(content)

        metadata = delivery.metadata
        msg_id = _optional_string(metadata.get("msg_id")) or _optional_string(
            metadata.get("message_id")
        )
        msg_seq = _int_or_default(metadata.get("msg_seq"), 1)
        reply_count = _int_or_default(metadata.get("reply_count"), 0)
        # Do not default missing scene to c2c — fail closed for window gate.
        scene = _optional_string(metadata.get("scene"))
        received_at = metadata.get("received_at")
        if received_at is not None and not isinstance(received_at, str):
            received_at = str(received_at)

        idempotency_key = (
            _optional_string(metadata.get("idempotency_key"))
            or _stable_id("qqbot-delivery", delivery.delivery_id)
        )
        base_meta: JsonObject = {
            "channel_id": self._config.channel_id,
            "delivery_type": delivery_type,
            "message_type": delivery_type,
            "policy_action": policy.action,
            "policy_reason": policy.reason,
            "fixture_only": True,
            "network_io": False,
        }

        # Whenever msg_id is present, always gate — missing/unknown scene fails closed.
        if msg_id is not None:
            scene_for_window = scene if scene is not None else ""
            window = check_passive_reply_window(
                scene=scene_for_window,
                received_at=received_at if isinstance(received_at, str) else None,
                reply_count=reply_count,
                msg_id=msg_id,
            )
            if not window.ok:
                return DeliveryResult(
                    delivery_id=delivery.delivery_id,
                    accepted=False,
                    delivered_at=None,
                    idempotency_key=idempotency_key,
                    metadata={
                        **base_meta,
                        "issue_code": window.issue_code,
                        "interim_notice": window.interim_notice,
                    },
                )

        envelope_msg_id = msg_id or delivery.delivery_id
        if delivery_type in {"file", "image"}:
            return await self._deliver_rich_media(
                delivery=delivery,
                delivery_type=delivery_type,
                metadata=metadata,
                scene=scene,
                envelope_msg_id=envelope_msg_id,
                msg_seq=msg_seq,
                idempotency_key=idempotency_key,
                base_meta=base_meta,
                policy=policy,
            )

        if delivery_type == "card":
            envelope = build_feedback_keyboard_envelope(
                title=content or "请评价本次回复",
                feedback_target=_feedback_target(delivery),
                msg_id=envelope_msg_id,
                msg_seq=msg_seq,
            )
        elif delivery_type == "markdown":
            envelope = build_markdown_envelope(
                content=content,
                msg_id=envelope_msg_id,
                msg_seq=msg_seq,
            )
        else:
            envelope = build_text_envelope(
                content=content,
                msg_id=envelope_msg_id,
                msg_seq=msg_seq,
            )

        envelope_policy = envelope.get("policy") if isinstance(envelope.get("policy"), Mapping) else {}
        policy_action = str(envelope_policy.get("action") or policy.action)
        policy_reason = envelope_policy.get("reason", policy.reason)
        # Empty visible payload (no msg_type) is not a successful delivery.
        has_payload = "msg_type" in envelope
        accepted = (
            policy_action != "block"
            and has_payload
            and self._config.enabled
        )

        result_meta: JsonObject = {
            **base_meta,
            "policy_action": policy_action,
            "policy_reason": policy_reason,
            "envelope": envelope,
        }

        if (
            accepted
            and self._transport is not None
            and self._token_manager is not None
            and self._config.enabled
        ):
            if scene not in {"c2c", "group"}:
                accepted = False
                result_meta["issue_code"] = "qqbot_send_failed"
                result_meta["send_error"] = "unsupported or missing QQ Bot scene"
            else:
                try:
                    await send_message(
                        envelope=envelope,
                        scene=scene,
                        token_manager=self._token_manager,
                        transport=self._transport,
                        user_openid=_optional_string(metadata.get("user_openid")),
                        group_openid=_optional_string(metadata.get("group_openid")),
                    )
                    result_meta["network_io"] = True
                    result_meta["fixture_only"] = False
                except (SendError, TokenError) as exc:
                    accepted = False
                    result_meta["issue_code"] = "qqbot_send_failed"
                    if isinstance(exc, TokenError):
                        result_meta["send_error"] = "QQ Bot token unavailable"
                    else:
                        result_meta["send_error"] = str(exc)
                    status_code = getattr(exc, "status_code", None)
                    qq_code = getattr(exc, "qq_code", None)
                    if status_code is not None:
                        result_meta["send_status_code"] = status_code
                    if qq_code is not None:
                        result_meta["send_qq_code"] = qq_code

        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=accepted,
            delivered_at=_now() if accepted else None,
            idempotency_key=idempotency_key,
            metadata=result_meta,
        )

    async def _deliver_rich_media(
        self,
        *,
        delivery: ChannelDelivery,
        delivery_type: str,
        metadata: Mapping[str, Any],
        scene: str | None,
        envelope_msg_id: str,
        msg_seq: int,
        idempotency_key: str,
        base_meta: JsonObject,
        policy: Any,
    ) -> DeliveryResult:
        """EGRESS-06: file/image deliver via upload → msg_type=7 (metadata-only)."""

        default_file_type = 4 if delivery_type == "file" else 1
        file_type = _int_or_default(metadata.get("file_type"), default_file_type)
        file_url = _optional_string(metadata.get("file_url")) or _optional_string(
            metadata.get("media_url")
        )
        precomputed_file_info = _optional_string(metadata.get("file_info"))

        result_meta: JsonObject = {
            **base_meta,
            "policy_action": policy.action,
            "policy_reason": policy.reason,
        }

        # Fail closed when neither https URL nor fixture precomputed file_info.
        if file_url is None and precomputed_file_info is None:
            result_meta["issue_code"] = "qqbot_rich_media_upload_failed"
            result_meta["send_error"] = "QQ Bot rich media requires https file_url"
            return DeliveryResult(
                delivery_id=delivery.delivery_id,
                accepted=False,
                delivered_at=None,
                idempotency_key=idempotency_key,
                metadata=result_meta,
            )

        if file_url is not None and not file_url.lower().startswith("https://"):
            result_meta["issue_code"] = "qqbot_rich_media_upload_failed"
            result_meta["send_error"] = "QQ Bot rich media file_url must be https"
            return DeliveryResult(
                delivery_id=delivery.delivery_id,
                accepted=False,
                delivered_at=None,
                idempotency_key=idempotency_key,
                metadata=result_meta,
            )

        if not self._config.enabled:
            return DeliveryResult(
                delivery_id=delivery.delivery_id,
                accepted=False,
                delivered_at=None,
                idempotency_key=idempotency_key,
                metadata=result_meta,
            )

        live = (
            self._transport is not None
            and self._token_manager is not None
            and file_url is not None
        )

        if live:
            if scene not in {"c2c", "group"}:
                result_meta["issue_code"] = "qqbot_send_failed"
                result_meta["send_error"] = "unsupported or missing QQ Bot scene"
                return DeliveryResult(
                    delivery_id=delivery.delivery_id,
                    accepted=False,
                    delivered_at=None,
                    idempotency_key=idempotency_key,
                    metadata=result_meta,
                )
            try:
                send_result = await send_rich_media(
                    scene=scene,
                    token_manager=self._token_manager,
                    transport=self._transport,
                    file_url=file_url,
                    file_type=file_type,
                    user_openid=_optional_string(metadata.get("user_openid")),
                    group_openid=_optional_string(metadata.get("group_openid")),
                    msg_id=envelope_msg_id,
                    msg_seq=msg_seq,
                )
            except (SendError, TokenError) as exc:
                evidence = getattr(exc, "evidence", None)
                if isinstance(evidence, Mapping):
                    result_meta.update(
                        {
                            key: value
                            for key, value in evidence.items()
                            if key
                            in {
                                "rich_media_stage",
                                "attempts",
                                "upload_attempts",
                                "send_attempts",
                                "send_status_code",
                                "send_qq_code",
                                "file_uuid_hash",
                                "ttl",
                                "issue_code",
                            }
                        }
                    )
                if isinstance(exc, TokenError):
                    result_meta["issue_code"] = result_meta.get(
                        "issue_code", "qqbot_send_failed"
                    )
                    result_meta["send_error"] = "QQ Bot token unavailable"
                else:
                    stage = (
                        evidence.get("rich_media_stage")
                        if isinstance(evidence, Mapping)
                        else None
                    )
                    result_meta.setdefault(
                        "issue_code",
                        "qqbot_rich_media_upload_failed"
                        if stage == "upload"
                        else "qqbot_send_failed",
                    )
                    result_meta["send_error"] = str(exc)
                status_code = getattr(exc, "status_code", None)
                qq_code = getattr(exc, "qq_code", None)
                if status_code is not None:
                    result_meta["send_status_code"] = status_code
                if qq_code is not None:
                    result_meta["send_qq_code"] = qq_code
                return DeliveryResult(
                    delivery_id=delivery.delivery_id,
                    accepted=False,
                    delivered_at=None,
                    idempotency_key=idempotency_key,
                    metadata=result_meta,
                )

            evidence = send_result.get("evidence")
            if isinstance(evidence, Mapping):
                result_meta.update(
                    {
                        key: value
                        for key, value in evidence.items()
                        if key
                        in {
                            "rich_media_stage",
                            "attempts",
                            "upload_attempts",
                            "send_attempts",
                            "send_status_code",
                            "send_qq_code",
                            "file_uuid_hash",
                            "ttl",
                            "issue_code",
                        }
                    }
                )
            # msg_type=7 marker only — omit live file_info from DeliveryResult.metadata.
            result_meta["envelope"] = {
                "msg_id": envelope_msg_id,
                "msg_seq": msg_seq,
                "msg_type": 7,
                "content": "",
            }
            result_meta["network_io"] = True
            result_meta["fixture_only"] = False
            return DeliveryResult(
                delivery_id=delivery.delivery_id,
                accepted=True,
                delivered_at=_now(),
                idempotency_key=idempotency_key,
                metadata=result_meta,
            )

        # Fixture-only path: require precomputed file_info; never invent it.
        if precomputed_file_info is None:
            result_meta["issue_code"] = "qqbot_rich_media_upload_failed"
            result_meta["send_error"] = (
                "QQ Bot rich media requires transport or precomputed file_info"
            )
            return DeliveryResult(
                delivery_id=delivery.delivery_id,
                accepted=False,
                delivered_at=None,
                idempotency_key=idempotency_key,
                metadata=result_meta,
            )

        envelope = build_media_envelope(
            file_info=precomputed_file_info,
            msg_id=envelope_msg_id,
            msg_seq=msg_seq,
        )
        result_meta["envelope"] = envelope
        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            accepted=True,
            delivered_at=_now(),
            idempotency_key=idempotency_key,
            metadata=result_meta,
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


def _delivery_type(delivery: ChannelDelivery) -> str:
    value = (
        delivery.metadata.get("delivery_type")
        or delivery.metadata.get("message_type")
        or delivery.metadata.get("kind")
        or "text"
    )
    text = str(value).strip().lower()
    aliases = {"template_card": "card"}
    return aliases.get(text, text)


def _delivery_text(delivery: ChannelDelivery) -> str | None:
    if delivery.content is not None:
        return delivery.content
    if delivery.result is not None:
        return delivery.result.content
    return _optional_string(delivery.metadata.get("text"))


def _feedback_target(delivery: ChannelDelivery) -> str:
    value = delivery.metadata.get("feedback_target")
    if value is not None:
        text = _optional_string(value)
        if text is not None:
            return text
    if delivery.result is not None and delivery.result.feedback_target:
        return delivery.result.feedback_target
    return "unknown"


def _int_or_default(value: Any, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _is_gateway_envelope(payload: Mapping[str, Any]) -> bool:
    """Detect real QQ Bot gateway envelope {op, t, d}.

    Requires ``op`` and ``d`` keys. The ``t`` key is absent on op=13
    validation challenge envelopes, so it is not required. Legacy fixture
    payloads contain neither ``op`` nor ``d``, so this cleanly separates
    gateway envelopes from the pre-normalized fixture format.
    """
    return "op" in payload and "d" in payload


def _normalize_gateway_envelope(
    raw: RawInbound, payload: Mapping[str, Any], channel_id: str
) -> InboundNormalized:
    """Delegate a real QQ Bot gateway envelope to normalization.py pure functions."""
    from .normalization import (
        QQBotEventCategory,
        normalize_interaction_event,
        normalize_message_event,
        parse_envelope,
    )

    event = parse_envelope(payload)

    if event.category == QQBotEventCategory.INTERACTION:
        feedback = normalize_interaction_event(
            event, created_at=raw.received_at, payload_ref=raw.payload_ref
        )
        return InboundNormalized(
            feedback=feedback,
            metadata={
                "channel_id": channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "feedback_event",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )

    if event.category in (
        QQBotEventCategory.C2C_MESSAGE,
        QQBotEventCategory.GROUP_AT_MESSAGE,
    ):
        turn = normalize_message_event(
            event, received_at=raw.received_at, payload_ref=raw.payload_ref
        )
        return InboundNormalized(
            message=turn,
            metadata={
                "channel_id": channel_id,
                "payload_ref": raw.payload_ref,
                "normalized_type": "agent_turn",
                "idempotency_key": raw.idempotency_key
                or channel_idempotency_key(payload, channel_prefix="qqbot"),
                "fixture_only": True,
            },
        )

    # VALIDATION_CHALLENGE or UNKNOWN → return empty InboundNormalized
    return InboundNormalized(
        metadata={
            "channel_id": channel_id,
            "payload_ref": raw.payload_ref,
            "normalized_type": event.category.value,
            "idempotency_key": raw.idempotency_key
            or channel_idempotency_key(payload, channel_prefix="qqbot"),
            "fixture_only": True,
        },
    )


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
