"""Unified forbidden full-text keys for contract log privacy.

This module is the single source of truth for keys that must never be stored in
contract logs (store-time rejection) nor exposed via read views (read-time
scrub).  Both ``platform_runtime`` store/interrupt/session modules and the
``conversation_read_view`` privacy helpers import from here so the forbidden set
stays in sync.
"""

from __future__ import annotations

FORBIDDEN_RAW_PAYLOAD_KEY = "raw_payload"

FORBIDDEN_FULL_TEXT_KEYS = frozenset({
    "case_facts",
    "customer_document_text",
    "document_text",
    "full_text",
    "payload_text",
    "raw_text",
    "prompt_content",
    "completion_text",
    "function_call_result",
    "tool_output",
})

ALL_FORBIDDEN_KEYS = frozenset({FORBIDDEN_RAW_PAYLOAD_KEY}) | FORBIDDEN_FULL_TEXT_KEYS


__all__ = [
    "ALL_FORBIDDEN_KEYS",
    "FORBIDDEN_FULL_TEXT_KEYS",
    "FORBIDDEN_RAW_PAYLOAD_KEY",
]
