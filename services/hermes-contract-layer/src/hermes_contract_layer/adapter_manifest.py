"""Hermes adapter manifest helpers."""

from __future__ import annotations

from typing import Any


def build_hermes_adapter_manifest(
    *,
    backend_version: str,
    profile_name: str,
    adapter_version: str = "0.1.0",
    no_channel_io: bool = True,
) -> dict[str, Any]:
    """Build a backend-neutral manifest for the Hermes lawfirm adapter."""

    raise NotImplementedError


__all__ = ["build_hermes_adapter_manifest"]
