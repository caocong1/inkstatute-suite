"""Solution bundle privacy scanner.

Walks a materialized solution bundle directory and emits Issues for any of:

- secrets / secret markers in text content
- raw_payload / raw_body / callback_body keys
- log files (.log, .log.jsonl)
- DB files (.db, .sqlite, .sqlite3)
- media files (.png, .jpg, .jpeg, .gif, .mp3, .mp4, .wav, .pdf)
- customer doc filenames (case_*.docx, contract_*.pdf, ...)
- confidential_artifact references in any text file

Reuses ``inkstatute_solutions_lawfirm.sanitize.scan_text`` for content scanning
so refusal patterns live in one place. Falls back to an inline minimal pattern
set if the sanitize module is not importable, so that secret markers and
raw_payload keys in text files are never silently skipped (WR-06).
"""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

from platform_runtime import Issue


TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".json", ".template", ".jsonl"}
)
BINARY_REFUSE_EXTENSIONS: frozenset[str] = frozenset(
    {".log", ".db", ".sqlite", ".sqlite3", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".wav", ".pdf", ".docx", ".doc"}
)

# WR-06: minimal inline refusal patterns used when the lawfirm sanitize
# module is not importable. This is a deliberately small subset of
# sanitize.SANITIZE_REFUSE_PATTERNS covering the highest-risk classes
# (secret markers, raw payload keys, confidential artifacts) so that text
# content scanning is never silently skipped.
_FALLBACK_REFUSE_PATTERNS: dict[str, re.Pattern[str]] = {
    "secret_marker": re.compile(r"(sk-|bearer\s+[A-Za-z0-9_-]{16,})", re.IGNORECASE),
    "raw_payload_key": re.compile(
        r"\b(raw_payload|raw_body|callback_body)\b", re.IGNORECASE
    ),
    "confidential_artifact": re.compile(r"\bconfidential[_-]artifact\b", re.IGNORECASE),
}


_lawfirm_sanitize = None


def _get_lawfirm_sanitize():
    """Lazy import the lawfirm sanitize module; returns None on ImportError."""

    global _lawfirm_sanitize
    if _lawfirm_sanitize is False:
        return None
    if _lawfirm_sanitize is None:
        try:
            _lawfirm_sanitize = import_module("inkstatute_solutions_lawfirm.sanitize")
        except ImportError:
            _lawfirm_sanitize = False
    return _lawfirm_sanitize or None


def _fallback_scan_text(text: str) -> list[str]:
    """Minimal inline scan used when the lawfirm sanitize module is unavailable."""

    hits: set[str] = set()
    for code, pattern in _FALLBACK_REFUSE_PATTERNS.items():
        if pattern.search(text):
            hits.add(code)
    return sorted(hits)


def scan_bundle_dir(bundle_dir: Path) -> list[Issue]:
    """Walk a bundle directory and return a sorted list of privacy Issues."""

    issues: list[Issue] = []
    if not bundle_dir.exists():
        return [
            Issue(
                code="bundle_dir_missing",
                path=str(bundle_dir),
                message="bundle directory does not exist",
                severity="error",
            )
        ]

    sanitize = _get_lawfirm_sanitize()
    scan_fn = sanitize.scan_text if sanitize is not None else _fallback_scan_text

    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = str(path.relative_to(bundle_dir))
        except ValueError:
            rel = path.name

        suffix = path.suffix.lower()
        if suffix in BINARY_REFUSE_EXTENSIONS:
            issues.append(
                Issue(
                    code="binary_or_sensitive_extension",
                    path=rel,
                    message=f"refused binary/sensitive file type: {suffix}",
                    severity="error",
                )
            )
            continue

        if suffix not in TEXT_EXTENSIONS:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for rule in scan_fn(text):
            issues.append(
                Issue(
                    code=rule,
                    path=rel,
                    message=f"text matches refusal pattern: {rule}",
                    severity="error",
                )
            )

    return issues


__all__ = ["BINARY_REFUSE_EXTENSIONS", "TEXT_EXTENSIONS", "scan_bundle_dir"]
