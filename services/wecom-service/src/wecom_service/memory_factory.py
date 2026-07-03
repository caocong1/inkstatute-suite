"""Deployment-level memory factory for constructing singleton memory instances.

This module closes MEM-07: the memory layer is initialized once per deployment
and shared across all sessions. The host calls ``build_memory_from_env()`` once
at startup and injects the resulting ``Memory`` instance into
``WeComRuntimeIngress``, which passes it through to every ``WeComSessionRuntime``.

The factory reads only non-secret connection parameters from the environment.
The ``hindsight_client.Hindsight`` instance is constructed here so the neutral
``platform-runtime`` package never reads secrets directly.
"""

from __future__ import annotations

import os
from typing import Any

from platform_runtime import HindsightMemory, Memory


def build_memory_from_env(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    hindsight_client_module: Any = None,
) -> Memory | None:
    """Construct a singleton ``HindsightMemory`` from environment configuration.

    Returns ``None`` when ``HINDSIGHT_BASE_URL`` is not set, allowing graceful
    opt-out for deployments that do not use long-term memory.

    Parameters
    ----------
    base_url:
        Override for ``HINDSIGHT_BASE_URL``. Defaults to the env var.
    api_key:
        Override for ``HINDSIGHT_API_KEY``. Defaults to the env var.
    hindsight_client_module:
        Inject the ``hindsight_client`` module for testing. When ``None``,
        the module is imported lazily so the factory does not hard-depend on
        the package being installed.
    """
    resolved_base_url = base_url or os.environ.get("HINDSIGHT_BASE_URL")
    if not resolved_base_url:
        return None

    resolved_api_key = api_key or os.environ.get("HINDSIGHT_API_KEY")

    if hindsight_client_module is None:
        from hindsight_client import Hindsight  # type: ignore[import-not-found]
    else:
        Hindsight = hindsight_client_module.Hindsight

    client = Hindsight(base_url=resolved_base_url, api_key=resolved_api_key)
    return HindsightMemory(client=client)


__all__ = ["build_memory_from_env"]
