"""Hermes lawfirm shadow contract layer for InkStatute V2."""

from .hook import HookRecordingResult, handle, record_contract_result

__all__ = ["HookRecordingResult", "handle", "record_contract_result"]
