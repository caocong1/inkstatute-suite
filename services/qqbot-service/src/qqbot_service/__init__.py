"""InkStatute-owned QQBot webhook host package (skeleton)."""

from __future__ import annotations

from qqbot_service.config import QQBotHostConfig
from qqbot_service.secrets import resolve_secret_ref

__all__ = ["QQBotHostConfig", "resolve_secret_ref"]
