"""InkStatute-owned QQBot webhook host package (skeleton)."""

from __future__ import annotations

from qqbot_service.config import QQBotHostConfig
from qqbot_service.secrets import resolve_secret_ref
from qqbot_service.wiring import (
    QQBotWiredRuntime,
    build_qqbot_channel_config,
    build_qqbot_wired_runtime,
)

__all__ = [
    "QQBotHostConfig",
    "QQBotWiredRuntime",
    "build_qqbot_channel_config",
    "build_qqbot_wired_runtime",
    "resolve_secret_ref",
]
