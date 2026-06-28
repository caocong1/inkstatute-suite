"""Hermes lawfirm shadow contract layer for InkStatute V2."""

from .adapter_manifest import build_hermes_adapter_manifest
from .bootstrap import (
    HermesBootstrapIssue,
    HermesBootstrapReport,
    check_sanitized_bundle_manifest,
    probe_hermes_capabilities,
)
from .hook import HookRecordingResult, handle, record_contract_result

__all__ = [
    "HermesBootstrapIssue",
    "HermesBootstrapReport",
    "HookRecordingResult",
    "build_hermes_adapter_manifest",
    "check_sanitized_bundle_manifest",
    "handle",
    "probe_hermes_capabilities",
    "record_contract_result",
]
