"""Codex backend adapter prototype package for the InkStatute platform runtime."""

from .adapter import (
    CodexBackendAdapter,
    CodexExecResult,
    CodexExecRunner,
    CodexStreamEvent,
    StreamingCodexExecRunner,
)
from .config import CodexBackendConfig
from .exec_runner import (
    FakeStreamingCodexRunner,
    SubprocessCodexExecRunner,
    SubprocessTransport,
    parse_codex_jsonl,
    parse_codex_jsonl_stream,
)
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
    "CodexStreamEvent",
    "FakeStreamingCodexRunner",
    "StreamingCodexExecRunner",
    "SubprocessCodexExecRunner",
    "SubprocessTransport",
    "build_codex_manifest",
    "codex_prototype_capabilities",
    "parse_codex_jsonl",
    "parse_codex_jsonl_stream",
]
