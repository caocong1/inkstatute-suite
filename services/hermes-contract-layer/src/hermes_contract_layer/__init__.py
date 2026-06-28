"""Hermes lawfirm shadow contract layer for InkStatute V2."""

from .adapter_manifest import build_hermes_adapter_manifest
from .hook import HookRecordingResult, handle, record_contract_result

__all__ = [
    "HookRecordingResult",
    "build_hermes_adapter_manifest",
    "handle",
    "record_contract_result",
]
