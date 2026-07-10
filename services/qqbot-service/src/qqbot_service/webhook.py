"""Pure ACK-first QQBot webhook request handler (HOST-01 / HOST-02).

Captures raw HTTP bytes into RawInbound, awaits only package
``verify_and_ack``, maps AckResponse to HTTP, and schedules (does not await)
post-ACK composition via an injectable scheduler.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, MutableSequence
from datetime import datetime, timezone
from typing import Any

from inkstatute_channels_qqbot.feedback_ingress import (
    ensure_interaction_ack,
    handle_feedback_callback,
)
from inkstatute_channels_qqbot.ingress_runtime import QQBotRuntimeIngress
from platform_runtime.output_boundary import BoundaryAction
from platform_runtime.protocols import AckResponse, ChannelDelivery, RawInbound, SolutionBinding

from qqbot_service.secrets import resolve_secret_ref
from qqbot_service.wiring import QQBotWiredRuntime

__all__ = [
    "CALLBACK_PATH",
    "build_raw_inbound_from_http",
    "handle_qqbot_webhook_request",
    "map_ack_to_http_response",
    "run_post_ack_composition",
]

CALLBACK_PATH = "/qqbot/callback"

_JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
}


def _header_ci(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_raw_inbound_from_http(
    headers: Mapping[str, str],
    body_bytes: bytes,
    *,
    bot_secret: str | None,
    payload_ref: str,
    received_at: str,
    idempotency_key: str | None = None,
) -> RawInbound:
    """Build RawInbound preserving exact ``body_bytes`` for signature verify."""
    metadata: dict[str, Any] = {
        # Exact injected/socket bytes — never re-serialized JSON.
        "request_body": body_bytes,
    }
    sig = _header_ci(headers, "X-Signature-Ed25519")
    ts = _header_ci(headers, "X-Signature-Timestamp")
    if sig is not None:
        metadata["x_signature_ed25519"] = sig
    if ts is not None:
        metadata["x_signature_timestamp"] = ts
    if bot_secret is not None:
        metadata["bot_secret"] = bot_secret

    payload: dict[str, Any] = {}
    if body_bytes:
        try:
            parsed = json.loads(body_bytes.decode("utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
    metadata["payload"] = payload

    return RawInbound(
        channel_id="qqbot",
        payload_ref=payload_ref,
        received_at=received_at,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def map_ack_to_http_response(ack: AckResponse) -> tuple[int, bytes, dict[str, str]]:
    """Map package AckResponse to HTTP status + JSON body (no secrets)."""
    headers = dict(_JSON_HEADERS)
    challenge = ack.metadata.get("validation_challenge_response")
    if isinstance(challenge, Mapping):
        return 200, json.dumps(dict(challenge), ensure_ascii=False).encode("utf-8"), headers

    http_body = ack.metadata.get("http_callback_ack_body")
    if ack.accepted and isinstance(http_body, Mapping):
        return 200, json.dumps(dict(http_body), ensure_ascii=False).encode("utf-8"), headers

    status = int(ack.status_code or 500)
    if ack.accepted:
        body = b"{}"
    else:
        body = b'{"accepted":false}'
    return status, body, headers


def _is_validation_challenge(ack: AckResponse) -> bool:
    return isinstance(ack.metadata.get("validation_challenge_response"), Mapping)


def _payload_from_raw(raw: RawInbound) -> dict[str, Any]:
    payload = raw.metadata.get("payload")
    if isinstance(payload, dict):
        return payload
    return {}


def _resolve_reply_text(
    *,
    reply_text: str | None,
    wired: QQBotWiredRuntime,
    run_id: str | None,
) -> str | None:
    if reply_text is not None:
        return reply_text
    if run_id is None:
        return None
    backend = getattr(wired.runtime, "backend", None)
    get_run = getattr(backend, "get_run", None)
    if get_run is None:
        return None
    # FakeBackend get_run is async — callers must await; sync peek via runs dict.
    runs = getattr(backend, "runs", None)
    if isinstance(runs, dict) and run_id in runs:
        run = runs[run_id]
        result = getattr(run, "result", None)
        if result is not None:
            content = getattr(result, "content", None)
            if isinstance(content, str) and content:
                return content
    return None


async def run_post_ack_composition(
    wired: QQBotWiredRuntime,
    raw: RawInbound,
    ack: AckResponse,
    *,
    solution: SolutionBinding | None = None,
    tenant_id: str = "default-tenant",
    workspace_id: str = "default-workspace",
    bot_instance_id: str = "default-bot",
    received_at: str | None = None,
    feedback_sink: MutableSequence[dict[str, Any]] | None = None,
    reply_text: str | None = None,
) -> dict[str, Any]:
    """Post-ACK composition: normalize → ingress/feedback → boundary → deliver.

    Composes package Protocol helpers only — no host crypto/normalize/send.
    """
    evidence: dict[str, Any] = {"status": "started"}
    when = received_at or raw.received_at or _utc_now()
    payload = _payload_from_raw(raw)

    # Prefer package normalize_inbound for branch typing.
    normalized = await wired.adapter.normalize_inbound(raw)
    if normalized.feedback is not None or (
        isinstance(normalized.metadata.get("normalized_type"), str)
        and normalized.metadata.get("normalized_type") == "feedback_event"
    ):
        fb = handle_feedback_callback(
            payload,
            received_at=when,
            payload_ref=raw.payload_ref,
        )
        if feedback_sink is not None:
            # Store sanitized evidence only (feedback_dict already package-shaped).
            feedback_sink.append(
                {
                    "status": fb.get("status"),
                    "feedback_dict": fb.get("feedback_dict"),
                    "idempotency_key": fb.get("idempotency_key"),
                    "category": fb.get("category"),
                }
            )
        evidence["branch"] = "feedback"
        evidence["feedback_status"] = fb.get("status")

        if (
            ack.metadata.get("interaction_ack_status") == "pending_host"
            and wired.live_io_ready
        ):
            ensure_interaction_ack(
                prior_ack_metadata=ack.metadata,
                message_transport=wired.message_transport,
                token_manager=wired.token_manager,
            )
        evidence["status"] = "completed"
        return evidence

    # Message path: package ingress → optional deliver behind output boundary.
    binding = solution or SolutionBinding(
        solution_id="qqbot-host-fixture",
        version="0",
        backend_id=getattr(getattr(wired.runtime, "backend", None), "backend_id", lambda: None)()
        if callable(getattr(getattr(wired.runtime, "backend", None), "backend_id", None))
        else "fake-backend",
    )
    ingress = QQBotRuntimeIngress(
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

    candidate = _resolve_reply_text(
        reply_text=reply_text, wired=wired, run_id=outcome.run_id
    )
    if not candidate:
        evidence["status"] = "completed_no_reply"
        evidence["issue_code"] = "qqbot_no_reply_source"
        return evidence

    decision = wired.runtime.output_boundary.apply("ordinary_user", candidate)
    evidence["boundary_action"] = decision.action.value
    evidence["boundary_reason"] = decision.reason

    if decision.action is BoundaryAction.BLOCK or not decision.visible_text:
        evidence["status"] = "completed_boundary_blocked"
        return evidence

    turn_meta: dict[str, Any] = {}
    if normalized.message is not None:
        turn_meta = dict(getattr(normalized.message, "metadata", {}) or {})

    # scene/scene_id come from package normalize; do not invent "c2c".
    # For group turns scene_id is group_openid; member openid is message.user_id.
    scene = turn_meta.get("scene")
    user_openid = turn_meta.get("user_openid") or getattr(
        normalized.message, "user_id", None
    )
    group_openid = turn_meta.get("group_openid")
    if scene == "group" and not group_openid:
        group_openid = turn_meta.get("scene_id")
    elif scene == "c2c" and not user_openid:
        user_openid = turn_meta.get("scene_id")

    delivery = ChannelDelivery(
        delivery_id=f"qqbot-deliv-{outcome.run_id or 'noreply'}",
        channel_id="qqbot",
        run_id=outcome.run_id,
        content=decision.visible_text,
        metadata={
            "delivery_type": "text",
            "scene": scene,
            "user_openid": user_openid,
            "group_openid": group_openid,
            "msg_id": turn_meta.get("message_id") or turn_meta.get("msg_id"),
            "message_id": turn_meta.get("message_id"),
            "received_at": when,
            "reply_count": 0,
            "output_boundary": {
                "action": decision.action.value,
                "reason": decision.reason,
                "privacy": "no_original_text_stored",
            },
        },
    )
    result = await wired.adapter.deliver(delivery)
    evidence["deliver_accepted"] = result.accepted
    evidence["status"] = "completed"
    return evidence


async def handle_qqbot_webhook_request(
    method: str,
    path: str,
    headers: Mapping[str, str] | None,
    body_bytes: bytes,
    *,
    wired: QQBotWiredRuntime,
    env: Mapping[str, str] | None = None,
    bot_secret: str | None = None,
    post_ack_scheduler: Callable[[Callable[[], Any]], None] | None = None,
    received_at: str | None = None,
    payload_ref: str | None = None,
    idempotency_key: str | None = None,
    solution: SolutionBinding | None = None,
    tenant_id: str = "default-tenant",
    workspace_id: str = "default-workspace",
    bot_instance_id: str = "default-bot",
    feedback_sink: MutableSequence[dict[str, Any]] | None = None,
    reply_text: str | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Pure ACK-first webhook handler — no port bind, no WeCom imports.

    Awaits only ``wired.adapter.verify_and_ack``. Accepted non-challenge
    callbacks schedule post-ACK work via ``post_ack_scheduler`` without
    awaiting ingress/deliver before the HTTP return.
    """
    hdrs = headers or {}
    route = (path or "").split("?", 1)[0]
    json_headers = dict(_JSON_HEADERS)

    if method.upper() != "POST":
        return 405, b'{"error":"method_not_allowed"}', json_headers
    if route != CALLBACK_PATH:
        return 404, b'{"error":"not_found"}', json_headers

    env_map = env or {}
    resolved_secret = bot_secret
    if resolved_secret is None:
        resolved_secret = resolve_secret_ref(wired.host_config.bot_secret_ref, env_map)

    when = received_at or _utc_now()
    raw = build_raw_inbound_from_http(
        hdrs,
        body_bytes,
        bot_secret=resolved_secret,
        payload_ref=payload_ref or "http://qqbot/callback",
        received_at=when,
        idempotency_key=idempotency_key,
    )

    # Only package verify — never await ingress/create_run/deliver here.
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
        composition_kwargs = {
            "solution": solution,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "bot_instance_id": bot_instance_id,
            "received_at": when,
            "feedback_sink": feedback_sink,
            "reply_text": reply_text,
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
