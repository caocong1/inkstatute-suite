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
so refusal patterns live in one place. Falls back to name-only scan if the
sanitize module is not importable.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from platform_runtime import Issue


TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".json", ".template", ".jsonl"}
)
BINARY_REFUSE_EXTENSIONS: frozenset[str] = frozenset(
    {".log", ".db", ".sqlite", ".sqlite3", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".wav", ".pdf", ".docx", ".doc"}
)


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

        if sanitize is not None:
            for rule in sanitize.scan_text(text):
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
