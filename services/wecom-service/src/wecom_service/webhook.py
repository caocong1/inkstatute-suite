"""Pure ACK-first WeCom webhook request handler (HOST-01 / HOST-02).

Captures sanitized WeCom callbacks into a ``RawInbound``, awaits only the
package ``verify_and_ack``, maps ``AckResponse`` to HTTP, and schedules (does
not await) post-ACK composition via an injectable scheduler.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, MutableSequence
from datetime import datetime, timezone
from typing import Any

from platform_contract.events import AgentTurn
from platform_runtime.output_boundary import BoundaryAction
from platform_runtime.protocols import AckResponse, ChannelDelivery, RawInbound, SolutionBinding

from .event_consumer import WeComEventConsumer
from .gateway_client import GatewayClient
from .idempotency import wecom_idempotency_key
from .ingress_runtime import WeComRuntimeIngress
from .protocol import parse_callback_envelope
from .wiring import WeComWiredRuntime

__all__ = [
    "CALLBACK_PATH",
    "build_raw_inbound_from_http",
    "handle_wecom_webhook_request",
    "map_ack_to_http_response",
    "run_post_ack_composition",
]

CALLBACK_PATH = "/wecom/callback"

_JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
}

_TEXT_HEADERS = {
    "Content-Type": "text/plain; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_raw_inbound_from_http(
    headers: Mapping[str, str],
    body_bytes: bytes,
    *,
    payload_ref: str,
    received_at: str,
    idempotency_key: str | None = None,
) -> RawInbound:
    """Build a ``RawInbound`` with the parsed callback body in metadata["callback"]."""
    metadata: dict[str, Any] = {}
    payload: dict[str, Any] = {}
    if body_bytes:
        try:
            parsed = json.loads(body_bytes.decode("utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
    metadata["callback"] = payload

    return RawInbound(
        channel_id="wecom",
        payload_ref=payload_ref,
        received_at=received_at,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def map_ack_to_http_response(ack: AckResponse) -> tuple[int, bytes, dict[str, str]]:
    """Map package ``AckResponse`` to HTTP status + body (no secrets)."""
    if ack.accepted:
        ack_body = ack.metadata.get("ack_body")
        if isinstance(ack_body, str):
            return 200, ack_body.encode("utf-8"), dict(_TEXT_HEADERS)
        return 200, b"{}", dict(_JSON_HEADERS)

    status = int(ack.status_code or 503)
    return status, b'{"accepted":false}', dict(_JSON_HEADERS)


def _is_validation_challenge(ack: AckResponse) -> bool:
    return isinstance(ack.metadata.get("validation_challenge_response"), Mapping)


def _payload_from_raw(raw: RawInbound) -> dict[str, Any]:
    callback = raw.metadata.get("callback")
    if isinstance(callback, dict):
        return callback
    return {}


def _to_user_from_callback(callback: Mapping[str, Any]) -> str | None:
    parsed = parse_callback_envelope(callback)
    return parsed.get("user_id") or callback.get("user_id") or callback.get("FromUserName")


def _conversation_id_from_callback(callback: Mapping[str, Any]) -> str | None:
    """Extract the conversation_id from a WeCom callback payload."""
    parsed = parse_callback_envelope(callback)
    return parsed.get("conversation_id") or callback.get("conversation_id")


def _agent_turn_to_dict(turn: AgentTurn) -> dict[str, Any]:
    """Serialize an :class:`AgentTurn` to a dict for the Gateway create_run body.

    Includes ``user_id``, ``content``, ``message_type``, ``attachments``,
    and ``metadata`` fields — the minimum needed by the Gateway to create a run.
    """
    return {
        "turn_id": turn.turn_id,
        "conversation_id": turn.conversation_id,
        "channel": turn.channel if isinstance(turn.channel, str) else str(turn.channel),
        "user_id": turn.user_id,
        "message_type": turn.message_type if isinstance(turn.message_type, str) else str(turn.message_type),
        "received_at": turn.received_at,
        "content": turn.content,
        "attachments": [
            {k: v for k, v in att.__dict__.items()} if hasattr(att, "__dict__") else dict(att)
            for att in turn.attachments
        ],
        "metadata": dict(turn.metadata) if turn.metadata else {},
    }


async def run_post_ack_composition(
    wired: WeComWiredRuntime,
    raw: RawInbound,
    ack: AckResponse,
    *,
    solution: SolutionBinding | None = None,
    tenant_id: str = "default-tenant",
    workspace_id: str = "default-workspace",
    bot_instance_id: str = "default-bot",
    received_at: str | None = None,
    feedback_sink: MutableSequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Post-ACK composition: normalize → ingress/feedback → boundary → deliver.

    Composes package Protocol helpers only — no host crypto/normalize/send.
    """
    evidence: dict[str, Any] = {"status": "started"}
    when = received_at or raw.received_at or _utc_now()
    payload = _payload_from_raw(raw)

    normalized = await wired.adapter.normalize_inbound(raw)
    if normalized.feedback is not None:
        feedback = normalized.feedback
        if feedback_sink is not None:
            feedback_meta = getattr(feedback, "metadata", None) or {}
            feedback_sink.append(
                {
                    "status": getattr(feedback, "status", None),
                    "feedback_id": getattr(feedback, "feedback_id", None),
                    "idempotency_key": feedback_meta.get("idempotency_key")
                    if isinstance(feedback_meta, Mapping) else None,
                    "action": getattr(feedback, "action", None),
                }
            )
        evidence["branch"] = "feedback"
        evidence["feedback_status"] = getattr(feedback, "status", None)
        evidence["status"] = "completed"
        return evidence

    # Gateway consumer path (BOT-02): when gateway_client is available,
    # use the event consumer instead of direct agent calls.
    if wired.gateway_client is not None and normalized.message is not None:
        return await _compose_via_gateway(
            wired=wired,
            normalized=normalized,
            raw=raw,
            ack=ack,
            payload=payload,
            when=when,
            solution=solution,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            bot_instance_id=bot_instance_id,
            feedback_sink=feedback_sink,
        )

    binding = solution or SolutionBinding(
        solution_id="wecom-host-fixture",
        backend_id=getattr(getattr(wired.runtime, "backend", None), "backend_id", lambda: "fake-backend")()
        if callable(getattr(getattr(wired.runtime, "backend", None), "backend_id", None))
        else "fake-backend",
    )
    ingress = WeComRuntimeIngress(
        runtime=wired.runtime,
        solution=binding,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        bot_instance_id=bot_instance_id,
    )
    outcome = await ingress.handle_callback(payload, received_at=when)
    evidence["branch"] = "message"
    evidence["ingress_action"] = getattr(outcome.action, "value", str(outcome.action))
    evidence["run_id"] = outcome.run_id

    reply_text: str | None = None
    if outcome.run_id is not None:
        backend = getattr(wired.runtime, "backend", None)
        get_run = getattr(backend, "get_run", None)
        if get_run is not None:
            run = await get_run(outcome.run_id)
            result = getattr(run, "result", None)
            if result is not None:
                content = getattr(result, "content", None)
                if isinstance(content, str) and content:
                    reply_text = content

    if not reply_text:
        evidence["status"] = "completed_no_reply"
        return evidence

    decision = wired.runtime.output_boundary.apply("ordinary_user", reply_text)
    evidence["boundary_action"] = getattr(decision.action, "value", str(decision.action))
    evidence["boundary_reason"] = decision.reason

    if decision.action is BoundaryAction.BLOCK or not decision.visible_text:
        evidence["status"] = "completed_boundary_blocked"
        return evidence

    to_user = _to_user_from_callback(payload)
    if not to_user:
        evidence["status"] = "completed_no_to_user"
        return evidence

    delivery = ChannelDelivery(
        delivery_id=f"wecom-deliv-{outcome.run_id}",
        channel_id="wecom",
        run_id=outcome.run_id,
        content=decision.visible_text,
        metadata={
            "delivery_type": "text",
            "to_user": to_user,
            "received_at": when,
            "reply_count": 0,
            "output_boundary": {
                "action": getattr(decision.action, "value", str(decision.action)),
                "reason": decision.reason,
                "privacy": "no_original_text_stored",
            },
        },
    )
    result = await wired.adapter.deliver(delivery)
    evidence["deliver_accepted"] = result.accepted
    evidence["status"] = "completed"
    return evidence


async def _compose_via_gateway(
    *,
    wired: WeComWiredRuntime,
    normalized: Any,
    raw: RawInbound,
    ack: AckResponse,
    payload: dict[str, Any],
    when: str,
    solution: SolutionBinding | None,
    tenant_id: str,
    workspace_id: str,
    bot_instance_id: str,
    feedback_sink: MutableSequence[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Gateway consumer path (BOT-02): create run via Gateway, consume SSE, deliver.

    This function replaces the old ingress path (direct agent calls) with a
    Gateway HTTP client + SSE consumer. No direct agent or backend calls
    are made — the Gateway is the sole agent contact point.
    """
    turn = normalized.message
    turn_dict = _agent_turn_to_dict(turn)

    to_user = _to_user_from_callback(payload)
    if not to_user:
        return {
            "status": "completed_no_to_user",
            "branch": "message",
            "gateway_path": True,
        }

    conversation_id = _conversation_id_from_callback(payload)

    consumer = WeComEventConsumer(
        gateway_client=wired.gateway_client,
        adapter=wired.adapter,
        solution=solution,
        tenant_id=tenant_id,
    )
    evidence = await consumer.consume_and_deliver(
        turn=turn_dict,
        to_user=to_user,
        conversation_id=conversation_id,
        received_at=when,
    )
    evidence["branch"] = "message"
    evidence["gateway_path"] = True
    return evidence


async def handle_wecom_webhook_request(
    method: str,
    path: str,
    headers: Mapping[str, str] | None,
    body_bytes: bytes,
    *,
    wired: WeComWiredRuntime,
    env: Mapping[str, str] | None = None,
    post_ack_scheduler: Callable[[Callable[[], Any]], None] | None = None,
    received_at: str | None = None,
    payload_ref: str | None = None,
    idempotency_key: str | None = None,
    solution: SolutionBinding | None = None,
    tenant_id: str = "default-tenant",
    workspace_id: str = "default-workspace",
    bot_instance_id: str = "default-bot",
    feedback_sink: MutableSequence[dict[str, Any]] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Pure ACK-first webhook handler — no port bind, no QQBot imports.

    Awaits only ``wired.adapter.verify_and_ack``. Accepted callbacks schedule
    post-ACK work via ``post_ack_scheduler`` without awaiting ingress/deliver
    before the HTTP return.
    """
    route = (path or "").split("?", 1)[0]

    if method.upper() != "POST":
        return 405, b'{"error":"method_not_allowed"}', dict(_JSON_HEADERS)
    if route != CALLBACK_PATH:
        return 404, b'{"error":"not_found"}', dict(_JSON_HEADERS)

    when = received_at or _utc_now()
    payload: dict[str, Any] = {}
    if body_bytes:
        try:
            parsed = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(parsed, dict):
                parsed = {}
            payload = parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, b'{"error":"invalid_json"}', dict(_JSON_HEADERS)
    key = idempotency_key or wecom_idempotency_key(payload)
    raw = build_raw_inbound_from_http(
        headers or {},
        body_bytes,
        payload_ref=payload_ref or f"wecom://callback/{key}",
        received_at=when,
        idempotency_key=key,
    )

    ack = await wired.adapter.verify_and_ack(raw)
    status, resp_body, resp_headers = map_ack_to_http_response(ack)

    if (
        ack.accepted
        and not _is_validation_challenge(ack)
        and post_ack_scheduler is not None
    ):
        wired_ref = wired
        raw_ref = raw
        ack_ref = ack
        composition_kwargs: dict[str, Any] = {
            "solution": solution,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "bot_instance_id": bot_instance_id,
            "received_at": when,
            "feedback_sink": feedback_sink,
        }

        def _thunk() -> Any:
            return asyncio.run(
                run_post_ack_composition(
                    wired_ref,
                    raw_ref,
                    ack_ref,
                    **composition_kwargs,
                )
            )

        post_ack_scheduler(_thunk)

    return status, resp_body, resp_headers
