"""Byte-offset tail-follow log reader with privacy scrubbing (Phase 82).

``LogReader`` resolves a fixed allowlist of source names to env-var-derived
file paths, reads forward from a caller-supplied byte offset using
``seek`` + ``readline`` in a bounded loop, and returns scrubbed lines with a
``next_offset`` cursor for HTTP polling.  Every JSONL line is passed through
``scrub_contract_payload``; plain-text lines have known secret env values
replaced with ``[REDACTED]``.  The cursor is rotation-aware: it resets to 0
when the file shrinks or the inode changes.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .privacy import scrub_contract_payload

__all__ = ["LogReader"]

_ALLOWED_SOURCES = frozenset({
    "contract_events",
    "runtime_audit",
    "feedback",
    "wecom_stdout",
    "qqbot_stdout",
})

_LEVEL_ORDER: dict[str, int] = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
_LEVEL_ALIASES: dict[str, str] = {"WARNING": "WARN", "CRITICAL": "ERROR"}

_LEVEL_RE = re.compile(r"^(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b", re.IGNORECASE)

_SECRET_KEY_HINTS = ("secret", "token", "key", "password", "authorization", "cookie")


class LogReader:
    """Tail-follow log reader with privacy scrubbing and path-traversal guard."""

    _ALLOWED_SOURCES = _ALLOWED_SOURCES
    _LEVEL_ORDER = _LEVEL_ORDER
    _LEVEL_ALIASES = _LEVEL_ALIASES

    def __init__(self, env: Mapping[str, str] | None = None, *, process_supervisor: Any = None) -> None:
        self._env = dict(env) if env is not None else dict(os.environ)
        self._process_supervisor = process_supervisor
        self._max_lines = int(self._env.get("LOG_VIEWER_MAX_LINES", "500"))

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def resolve_path(self, source: str) -> str | None:
        """Map a source name to a file path.

        Returns ``None`` when the source is known but not configured.
        Raises ``ValueError`` for unknown source names.
        """
        if source not in _ALLOWED_SOURCES:
            raise ValueError(f"unknown log source: {source!r}")

        if source == "contract_events":
            path = self._env.get("INKSTATUTE_CONTRACT_LOG_PATH")
            return self._validate_path(path) if path else None

        if source == "runtime_audit":
            path = self._env.get("INKSTATUTE_RUNTIME_AUDIT_PATH")
            return self._validate_path(path) if path else None

        if source == "feedback":
            path = self._env.get("INKSTATUTE_FEEDBACK_QUEUE_PATH")
            return self._validate_path(path) if path else None

        # Child-process stdout/stderr logs.
        name = source.removesuffix("_stdout")  # "wecom" or "qqbot"
        log_dir = self._resolve_process_log_dir()

        # Prefer the process supervisor's record when available.
        if self._process_supervisor is not None:
            try:
                record = self._process_supervisor.status(name)
            except Exception:
                record = None
            if record is not None and getattr(record, "log_path", ""):
                candidate = str(record.log_path)
                validated = self._validate_process_path(candidate, log_dir)
                if validated is not None:
                    return validated

        fallback = log_dir / f"{name}-host.log"
        return self._validate_process_path(str(fallback), log_dir)

    def _resolve_process_log_dir(self) -> Path:
        raw = self._env.get("INKSTATUTE_PROCESS_LOG_DIR")
        if raw:
            return Path(raw)
        return Path.home() / ".inkstatute" / "process-logs"

    @staticmethod
    def _validate_path(path: str | None) -> str | None:
        """Defense-in-depth check for env-derived paths."""
        if path is None:
            return None
        if ".." in Path(path).parts:
            return None
        return path

    @staticmethod
    def _validate_process_path(candidate: str, log_dir: Path) -> str | None:
        """Ensure a child-process log path stays within the log directory."""
        if not candidate:
            return None
        resolved = Path(candidate).resolve()
        log_dir_resolved = log_dir.resolve()
        try:
            resolved.relative_to(log_dir_resolved)
        except ValueError:
            return None
        return str(resolved)

    # ------------------------------------------------------------------
    # Source listing
    # ------------------------------------------------------------------

    def list_sources(self) -> list[dict[str, Any]]:
        """Return availability info for every source in the allowlist."""
        result: list[dict[str, Any]] = []
        for name in sorted(_ALLOWED_SOURCES):
            try:
                path = self.resolve_path(name)
            except ValueError:
                path = None
            available = bool(path) and Path(path).is_file()
            result.append({
                "source": name,
                "available": available,
                "path": path or "",
            })
        return result

    # ------------------------------------------------------------------
    # Core read
    # ------------------------------------------------------------------

    def read(
        self,
        source: str,
        offset: int = 0,
        inode: int | None = None,
        level: str | None = None,
        q: str | None = None,
        max_lines: int | None = None,
    ) -> dict[str, Any]:
        """Read lines from *source* starting at byte *offset*.

        Returns a dict with ``lines``, ``next_offset``, ``eof``, ``inode``,
        ``file_size``, and ``metadata``.  When the source is not configured or
        the file is missing, an ``error`` dict is returned instead.
        """
        if source not in _ALLOWED_SOURCES:
            raise ValueError(f"unknown log source: {source!r}")

        path = self.resolve_path(source)
        if path is None:
            return {
                "error": {
                    "code": "source_not_configured",
                    "message": f"Log source {source} has no path configured",
                }
            }

        if not Path(path).is_file():
            return {
                "error": {
                    "code": "source_not_found",
                    "message": f"Log file not found: {source}",
                }
            }

        stat = os.stat(path)
        file_size = stat.st_size
        current_inode = stat.st_ino

        # Rotation detection.
        rotated = False
        if inode is not None and current_inode != inode:
            offset = 0
            rotated = True
        if offset > 0 and file_size < offset:
            offset = 0
            rotated = True
        if offset > file_size:
            offset = 0

        cap = int(max_lines if max_lines is not None else self._max_lines)
        if cap < 1:
            cap = self._max_lines

        level_filter = level.upper() if level else None
        keyword = q.lower() if q else None

        lines: list[dict[str, Any]] = []
        lines_scanned = 0
        lines_filtered = 0
        line_number = 0
        next_offset = offset

        with open(path, "rb") as fh:
            fh.seek(offset)
            while True:
                pos_before = fh.tell()
                raw = fh.readline()
                if not raw:
                    break
                lines_scanned += 1
                line_number += 1
                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")

                # Determine level.
                line_level, parsed = self._detect_level(text)

                # Apply level filter.
                if level_filter is not None:
                    if _LEVEL_ORDER.get(line_level, 1) < _LEVEL_ORDER.get(level_filter, 0):
                        lines_filtered += 1
                        next_offset = fh.tell()
                        continue

                # Scrub the line text.
                scrubbed = self._scrub_line(text, parsed)

                # Apply keyword filter on scrubbed text.
                if keyword:
                    if keyword not in scrubbed.lower():
                        lines_filtered += 1
                        next_offset = fh.tell()
                        continue

                lines.append({
                    "line_number": line_number,
                    "text": scrubbed,
                    "level": line_level,
                    "offset": pos_before,
                })
                next_offset = fh.tell()

                if len(lines) >= cap:
                    break

        eof = next_offset >= file_size

        return {
            "source": source,
            "lines": lines,
            "next_offset": next_offset,
            "eof": eof,
            "inode": current_inode,
            "file_size": file_size,
            "metadata": {
                "lines_returned": len(lines),
                "lines_filtered": lines_filtered,
                "max_lines": cap,
                "level_filter": level_filter,
                "keyword": q if q else None,
                "rotated": rotated,
            },
        }

    # ------------------------------------------------------------------
    # Level detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_level(text: str) -> tuple[str, Any]:
        """Return ``(level, parsed_json_or_none)`` for a line."""
        parsed: Any = None
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None

        if isinstance(parsed, dict):
            raw_level = parsed.get("level")
            if raw_level:
                upper = str(raw_level).upper()
                normalized = _LEVEL_ALIASES.get(upper, upper)
                if normalized in _LEVEL_ORDER:
                    return normalized, parsed

        match = _LEVEL_RE.match(text)
        if match:
            raw_level = match.group("level").upper()
            normalized = _LEVEL_ALIASES.get(raw_level, raw_level)
            if normalized in _LEVEL_ORDER:
                return normalized, parsed

        return "INFO", parsed

    # ------------------------------------------------------------------
    # Privacy scrubbing
    # ------------------------------------------------------------------

    def _scrub_line(self, text: str, parsed: Any) -> str:
        """Scrub a single line for display."""
        if parsed is not None:
            try:
                scrubbed = scrub_contract_payload(parsed)
                return json.dumps(scrubbed, ensure_ascii=False)
            except ValueError as exc:
                forbidden_path = str(exc)
                return f"[REDACTED: forbidden key at {forbidden_path}]"
        # Plain-text line — redact known secret env values.
        return self._redact_text_secrets(text)

    def _redact_text_secrets(self, text: str) -> str:
        """Replace known secret env values in plain text."""
        return self._redact_text_secrets_static(text, self._env)

    @staticmethod
    def _redact_text_secrets_static(text: str, env: Mapping[str, str]) -> str:
        redacted = text
        for name, secret in env.items():
            if not secret or len(secret) < 8:
                continue
            if any(hint in name.lower() for hint in _SECRET_KEY_HINTS):
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
