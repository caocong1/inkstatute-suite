"""InkStatute-owned QQBot webhook host package."""

from __future__ import annotations

from qqbot_service.config import QQBotHostConfig
from qqbot_service.event_consumer import QQBotEventConsumer, is_terminal_event, solution_to_dict
from qqbot_service.gateway_client import GatewayClient, GatewayClientConfig, GatewayClientError
from qqbot_service.http_server import QQBotWebhookServer
from qqbot_service.secrets import resolve_secret_ref
from qqbot_service.webhook import (
    build_raw_inbound_from_http,
    handle_qqbot_webhook_request,
    map_ack_to_http_response,
    run_post_ack_composition,
)
from qqbot_service.wiring import (
    QQBotWiredRuntime,
    build_qqbot_channel_config,
    build_qqbot_wired_runtime,
)

__all__ = [
    "GatewayClient",
    "GatewayClientConfig",
    "GatewayClientError",
    "QQBotEventConsumer",
    "QQBotHostConfig",
    "QQBotWebhookServer",
    "QQBotWiredRuntime",
    "build_qqbot_channel_config",
    "build_qqbot_wired_runtime",
    "build_raw_inbound_from_http",
    "handle_qqbot_webhook_request",
    "is_terminal_event",
    "map_ack_to_http_response",
    "resolve_secret_ref",
    "run_post_ack_composition",
    "solution_to_dict",
]
