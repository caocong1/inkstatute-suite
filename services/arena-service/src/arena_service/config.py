"""Configuration for the local-only InkStatute Arena Service.

The Arena Service binds to ``127.0.0.1:8001`` by default and NEVER binds
to ``0.0.0.0``. It is a thin, framework-free surface that delegates to
an injected engine (wired in Plan 05) for arena execution.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ArenaServiceConfig:
    """Arena Service settings.

    The service is local-only: ``bind_host`` defaults to ``127.0.0.1``
    and must never be set to ``0.0.0.0``. The ``token`` field holds the
    single Bearer token used for auth; when empty, the caller must set
    it or generate one via :meth:`generate_token`.
    """

    bind_host: str = "127.0.0.1"
    bind_port: int = 8001
    base_path: str = "/v1"
    token: str = ""
    max_concurrent_initializations: int = 2
    per_run_timeout_seconds: float = 300.0
    enabled: bool = True

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "ArenaServiceConfig":
        """Build a config from an environment-like mapping.

        Reads ``ARENA_SERVICE_TOKEN``, ``ARENA_SERVICE_BIND_HOST``
        (default ``127.0.0.1``), ``ARENA_SERVICE_BIND_PORT`` (default
        ``8001``), ``ARENA_SERVICE_MAX_CONCURRENT_INIT`` (default ``2``),
        and ``ARENA_SERVICE_PER_RUN_TIMEOUT`` (default ``300.0``).
        """
        token = mapping.get("ARENA_SERVICE_TOKEN", "")
        bind_host = mapping.get("ARENA_SERVICE_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
        bind_port_raw = mapping.get("ARENA_SERVICE_BIND_PORT", "8001").strip()
        try:
            bind_port = int(bind_port_raw) if bind_port_raw else 8001
        except ValueError:
            bind_port = 8001
        max_init_raw = mapping.get("ARENA_SERVICE_MAX_CONCURRENT_INIT", "2").strip()
        try:
            max_concurrent_initializations = int(max_init_raw) if max_init_raw else 2
        except ValueError:
            max_concurrent_initializations = 2
        timeout_raw = mapping.get("ARENA_SERVICE_PER_RUN_TIMEOUT", "300.0").strip()
        try:
            per_run_timeout_seconds = float(timeout_raw) if timeout_raw else 300.0
        except ValueError:
            per_run_timeout_seconds = 300.0
        enabled_raw = mapping.get("ARENA_SERVICE_ENABLED", "true").strip().lower()
        enabled = enabled_raw in {"1", "true", "yes"}
        return cls(
            bind_host=bind_host,
            bind_port=bind_port,
            token=token,
            max_concurrent_initializations=max_concurrent_initializations,
            per_run_timeout_seconds=per_run_timeout_seconds,
            enabled=enabled,
        )

    @staticmethod
    def generate_token() -> str:
        """Return a URL-safe random token (43 characters from 32 bytes)."""
        return secrets.token_urlsafe(32)


__all__ = ["ArenaServiceConfig"]
