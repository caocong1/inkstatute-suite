"""Non-mutating Codex capability probe.

The probe calls ``codex --version`` via an injectable transport (NOT a real
subprocess in tests) and returns a :class:`CodexProbeReport` with a 14-field
:class:`AdapterCapabilitySet`.  The probe must never invoke ``codex exec`` with
a prompt — it is non-mutating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from platform_contract.agent_adapter import AdapterCapabilitySet

from .config import CodexBackendConfig
from .manifest import codex_prototype_capabilities


class CodexProbeTransport(Protocol):
    """Host-provided transport for the non-mutating Codex version probe."""

    def run_version(self) -> str: ...


@dataclass(frozen=True, slots=True)
class CodexProbeIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CodexProbeReport:
    ok: bool
    capabilities: AdapterCapabilitySet
    codex_version: str | None = None
    issues: list[CodexProbeIssue] = field(default_factory=list)


class CodexCapabilityProbe:
    """Probe Codex capabilities without invoking ``codex exec``."""

    def __init__(self, transport: CodexProbeTransport, config: CodexBackendConfig | None = None) -> None:
        self.transport = transport
        self.config = config or CodexBackendConfig()

    def probe(self) -> CodexProbeReport:
        try:
            version = self.transport.run_version()
        except Exception:
            return CodexProbeReport(
                ok=False,
                capabilities=codex_prototype_capabilities(),
                issues=[
                    CodexProbeIssue(
                        code="codex_binary_unavailable",
                        message="codex --version failed",
                    )
                ],
            )
        return CodexProbeReport(
            ok=True,
            capabilities=codex_prototype_capabilities(),
            codex_version=version,
            issues=[],
        )


__all__ = ["CodexCapabilityProbe", "CodexProbeIssue", "CodexProbeReport", "CodexProbeTransport"]
