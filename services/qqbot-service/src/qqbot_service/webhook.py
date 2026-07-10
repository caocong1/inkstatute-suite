"""Pure ACK-first QQBot webhook request handler (HOST-01 / HOST-02).

Captures raw HTTP bytes into RawInbound, awaits only package
``verify_and_ack``, maps AckResponse to HTTP, and schedules (does not await)
post-ACK composition via an injectable scheduler.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from platform_runtime.protocols import AckResponse, RawInbound

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


def _post_ack_placeholder() -> None:
    """Plan 01 placeholder — Plan 02 replaces with real composition."""
    return None


async def run_post_ack_composition(
    wired: QQBotWiredRuntime,
    raw: RawInbound,
    ack: AckResponse,
    **_kwargs: Any,
) -> None:
    """Post-ACK composition entrypoint (stub in Plan 01; filled in Plan 02)."""
    del wired, raw, ack, _kwargs
    _post_ack_placeholder()


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

    raw = build_raw_inbound_from_http(
        hdrs,
        body_bytes,
        bot_secret=resolved_secret,
        payload_ref=payload_ref or "http://qqbot/callback",
        received_at=received_at or _utc_now(),
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
        # Capture closed-over values for the scheduled thunk.
        wired_ref = wired
        raw_ref = raw
        ack_ref = ack

        def _thunk() -> Any:
            return run_post_ack_composition(wired_ref, raw_ref, ack_ref)

        post_ack_scheduler(_thunk)

    return status, resp_body, resp_headers
