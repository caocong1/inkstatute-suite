"""Configuration for the concrete Codex backend adapter prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class CodexBackendConfig:
    """Adapter-local Codex prototype configuration.

    Runtime secrets, API keys, and message payloads intentionally stay
    outside this config object and outside the repository.
    """

    backend_id: str = "codex-prototype"
    backend_version: str = "unknown"
    adapter_version: str = "0.1.0"
    exec_command: tuple[str, ...] = (
        "codex",
        "exec",
        "--json",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
    )
    output_last_message_path: str | None = None
    codex_binary: str = "codex"
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["CodexBackendConfig"]
