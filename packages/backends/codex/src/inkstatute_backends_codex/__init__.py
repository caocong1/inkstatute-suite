"""Codex backend adapter prototype package for the InkStatute platform runtime."""

from .adapter import CodexBackendAdapter, CodexExecResult, CodexExecRunner
from .config import CodexBackendConfig
from .manifest import build_codex_manifest, codex_prototype_capabilities
from .probe import CodexCapabilityProbe, CodexProbeIssue, CodexProbeReport, CodexProbeTransport

__all__ = [
    "CodexBackendAdapter",
    "CodexBackendConfig",
    "CodexCapabilityProbe",
    "CodexExecResult",
    "CodexExecRunner",
    "CodexProbeIssue",
    "CodexProbeReport",
    "CodexProbeTransport",
    "build_codex_manifest",
    "codex_prototype_capabilities",
]
