"""Privacy scans for committed InkStatute V2 evidence artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT


@dataclass(frozen=True)
class PrivacyIssue:
    path: Path
    code: str
    message: str
    line: int | None = None
    sample: str | None = None

    def summary(self) -> str:
        location = f"{self.path}:{self.line}" if self.line is not None else str(self.path)
        return f"{location} {self.code}: {self.message}"


SECRET_PATTERNS = (
    ("secret_value", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "plaintext_secret_assignment",
        re.compile(
            r"\b(password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-]{12,}",
            re.IGNORECASE,
        ),
    ),
)
PII_PATTERNS = (
    ("phone_number", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("id_number", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("bank_account", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
    ("address_value", re.compile(r"(address|住址|地址)\s*[:=]\s*.{8,}", re.IGNORECASE)),
)
CALLBACK_BODY_PATTERNS = (
    ("callback_xml_body", re.compile(r"<xml>.*</xml>", re.IGNORECASE)),
    ("callback_body", re.compile(r"\b(callback_body|raw_callback|raw_body)\b", re.IGNORECASE)),
)
RUNTIME_FILE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".log", ".mp4", ".mov", ".wav", ".mp3", ".docx")
REFERENCE_PREFIXES = ("fixture://", "hermes://", "ref://")


def scan_privacy_targets(paths: Iterable[str | Path], *, mode: str) -> list[PrivacyIssue]:
    if mode not in {"data", "source"}:
        raise ValueError("mode must be data or source")

    issues: list[PrivacyIssue] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or path.is_dir() or _is_ignored(path):
            continue
        if _is_runtime_artifact(path):
            issues.append(_issue(path, "runtime_artifact", "runtime artifact must not be committed"))
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        if mode == "data":
            issues.extend(_scan_structured_data(path, text))
        issues.extend(_scan_text_patterns(path, text, mode=mode))
    return issues


def default_privacy_data_paths(repo_root: str | Path = REPO_ROOT) -> list[Path]:
    root = Path(repo_root)
    candidates: list[Path] = []
    for pattern in (
        "packages/*/fixtures/**/*.json",
        "packages/*/fixtures/**/*.jsonl",
        "services/*/bundles/**/*.json",
        "services/*/docs/**/*.md",
        "docs/**/*.md",
        ".planning/phases/**/*.md",
    ):
        candidates.extend(path for path in root.glob(pattern) if path.is_file() and not _is_ignored(path))
    return sorted(set(candidates))


def assert_privacy_clean(paths: Iterable[str | Path], *, mode: str) -> None:
    issues = scan_privacy_targets(paths, mode=mode)
    if issues:
        details = "; ".join(issue.summary() for issue in issues[:5])
        remaining = "" if len(issues) <= 5 else f"; ... {len(issues) - 5} more"
        raise AssertionError(f"{len(issues)} privacy issue(s): {details}{remaining}")


def _scan_structured_data(path: Path, text: str) -> list[PrivacyIssue]:
    issues: list[PrivacyIssue] = []
    if path.suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            issues.append(_issue(path, "invalid_json", f"could not parse JSON file: {exc}"))
            return issues
        issues.extend(_raw_payload_issues(value, path=path))
    elif path.suffix == ".jsonl":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(_issue(path, "invalid_jsonl_line", "could not parse JSONL line", line=line_number))
                continue
            issues.extend(_raw_payload_issues(value, path=path, line=line_number))
    return issues


def _raw_payload_issues(value: Any, *, path: Path, line: int | None = None, key_path: str = "") -> list[PrivacyIssue]:
    issues: list[PrivacyIssue] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if key == "raw_payload":
                issues.append(
                    _issue(
                        path,
                        "raw_payload_field",
                        f"exact raw_payload field is forbidden at {child_path}",
                        line=line,
                    )
                )
            issues.extend(_raw_payload_issues(child, path=path, line=line, key_path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{key_path}[{index}]"
            issues.extend(_raw_payload_issues(child, path=path, line=line, key_path=child_path))
    return issues


def _scan_text_patterns(path: Path, text: str, *, mode: str) -> list[PrivacyIssue]:
    issues: list[PrivacyIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _reference_only_line(line):
            continue
        for code, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(_issue(path, code, "plaintext secret-like value is forbidden", line=line_number))
        for code, pattern in PII_PATTERNS:
            if pattern.search(line):
                issues.append(_issue(path, code, "complete PII-like value is forbidden", line=line_number))
        if mode == "data":
            for code, pattern in CALLBACK_BODY_PATTERNS:
                if pattern.search(line):
                    issues.append(_issue(path, code, "raw callback body marker is forbidden", line=line_number))
    return issues


def _reference_only_line(line: str) -> bool:
    stripped = line.strip()
    return any(prefix in stripped for prefix in REFERENCE_PREFIXES) and "raw_payload_ref" in stripped


def _is_runtime_artifact(path: Path) -> bool:
    lowered = path.name.lower()
    return lowered.endswith(RUNTIME_FILE_SUFFIXES)


def _is_ignored(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & {".git", "__pycache__", ".pytest_cache"}) or path.suffix in {".pyc", ".pyo"}


def _issue(
    path: Path,
    code: str,
    message: str,
    *,
    line: int | None = None,
) -> PrivacyIssue:
    return PrivacyIssue(path=path, code=code, message=message, line=line, sample="<redacted>")


__all__ = [
    "PrivacyIssue",
    "assert_privacy_clean",
    "default_privacy_data_paths",
    "scan_privacy_targets",
]

