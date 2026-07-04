"""Non-mutating provider_model capability probe.

The probe checks whether the ``openai`` SDK is importable via an injectable
transport (using ``importlib.util.find_spec`` by default — NOT importing the
SDK) and returns a :class:`ProviderModelProbeReport` with a 14-field
:class:`AdapterCapabilitySet`.  The probe must never make a real API call or
import ``openai`` at module top level.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Protocol

from platform_contract.agent_adapter import AdapterCapabilitySet

from .config import ProviderModelBackendConfig
from .manifest import provider_model_prototype_capabilities


class ProviderModelProbeTransport(Protocol):
    """Host-provided transport for the non-mutating SDK availability probe."""

    def check_sdk_available(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class ProviderModelProbeIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ProviderModelProbeReport:
    ok: bool
    capabilities: AdapterCapabilitySet
    sdk_available: bool = False
    issues: list[ProviderModelProbeIssue] = field(default_factory=list)


class _ImportlibProbeTransport:
    """Default transport: check SDK availability without importing it."""

    def check_sdk_available(self) -> bool:
        return importlib.util.find_spec("openai") is not None


class ProviderModelCapabilityProbe:
    """Probe provider_model capabilities without making a real API call."""

    def __init__(
        self,
        transport: ProviderModelProbeTransport,
        config: ProviderModelBackendConfig | None = None,
    ) -> None:
        self.transport = transport
        self.config = config or ProviderModelBackendConfig()

    def probe(self) -> ProviderModelProbeReport:
        try:
            sdk_available = self.transport.check_sdk_available()
        except Exception:
            return ProviderModelProbeReport(
                ok=False,
                capabilities=provider_model_prototype_capabilities(),
                sdk_available=False,
                issues=[
                    ProviderModelProbeIssue(
                        code="openai_sdk_unavailable",
                        message="openai SDK not importable",
                    )
                ],
            )
        if sdk_available:
            return ProviderModelProbeReport(
                ok=True,
                capabilities=provider_model_prototype_capabilities(),
                sdk_available=True,
                issues=[],
            )
        return ProviderModelProbeReport(
            ok=False,
            capabilities=provider_model_prototype_capabilities(),
            sdk_available=False,
            issues=[
                ProviderModelProbeIssue(
                    code="openai_sdk_unavailable",
                    message="openai SDK not importable",
                )
            ],
        )


__all__ = [
    "ProviderModelCapabilityProbe",
    "ProviderModelProbeIssue",
    "ProviderModelProbeReport",
    "ProviderModelProbeTransport",
]
