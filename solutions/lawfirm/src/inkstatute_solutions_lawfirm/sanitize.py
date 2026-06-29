"""Sanitization patterns and helpers for solution bundles.

Shared by ``lawfirm`` and ``demo_non_legal`` so refusal patterns live in one
place. The patterns are deliberately strict: any false positive at the bundle
level is preferable to a false negative that lets a secret or customer payload
through.
"""

from __future__ import annotations

import re


SANITIZE_REFUSE_PATTERNS: dict[str, re.Pattern[str]] = {
    "secret_marker": re.compile(r"(sk-|bearer\s+[A-Za-z0-9_-]{16,})", re.IGNORECASE),
    "hex_blob": re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    "raw_payload_key": re.compile(r"\b(raw_payload|raw_body|callback_body)\b", re.IGNORECASE),
    "log_file_ref": re.compile(r"\b[a-z_/.-]*\.(log|log\.jsonl)\b", re.IGNORECASE),
    "db_file_ref": re.compile(r"\b[a-z_/.-]*\.(db|sqlite|sqlite3)\b", re.IGNORECASE),
    "customer_doc": re.compile(
        r"\b(case_|contract_|complaint_|appeal_)[a-z0-9_-]*\.(docx|doc|pdf)\b",
        re.IGNORECASE,
    ),
    "confidential_artifact": re.compile(r"\bconfidential[_-]artifact\b", re.IGNORECASE),
}

_SECRET_HINT_KEYS = re.compile(
    r"\b(secret|password|api[_-]?key|token|private[_-]?key)\s*[=:]\s*"
    r"[A-Za-z0-9+/=._\-]{8,}",
    re.IGNORECASE,
)


def scan_text(text: str) -> list[str]:
    """Return a sorted list of refusal-reason codes triggered by this text."""
    if not text:
        return []
    hits: set[str] = set()
    for code, pattern in SANITIZE_REFUSE_PATTERNS.items():
        if pattern.search(text):
            hits.add(code)
    if _SECRET_HINT_KEYS.search(text):
        hits.add("secret_hint_assignment")
    return sorted(hits)


def scan_path(path: str) -> list[str]:
    """Convenience wrapper for path-like strings."""
    return scan_text(path)