"""Non-mutating Hermes bootstrap probes and sanitized bundle checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class HermesBootstrapIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class HermesBootstrapReport:
    passed: bool
    issues: list[HermesBootstrapIssue]
    capabilities: dict[str, Any]


def probe_hermes_capabilities(
    root_path: str | Path,
    profile_path: str | Path,
    contract_log_path: str | Path,
) -> HermesBootstrapReport:
    """Probe supplied Hermes paths without mutating them."""

    raise NotImplementedError


def check_sanitized_bundle_manifest(path: str | Path) -> HermesBootstrapReport:
    """Check a sanitized lawfirm bundle manifest for forbidden indicators."""

    raise NotImplementedError


__all__ = [
    "HermesBootstrapIssue",
    "HermesBootstrapReport",
    "check_sanitized_bundle_manifest",
    "probe_hermes_capabilities",
]
