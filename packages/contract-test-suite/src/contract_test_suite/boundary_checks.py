"""Thin-layer and composability boundary checks for InkStatute V2."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import PLATFORM_SCHEMA_ROOT, REPO_ROOT
from .schema_validation import FORBIDDEN_TOP_LEVEL_FIELDS, load_json


@dataclass(frozen=True)
class BoundaryIssue:
    path: Path
    code: str
    message: str
    line: int | None = None

    def summary(self) -> str:
        location = f"{self.path}:{self.line}" if self.line is not None else str(self.path)
        return f"{location} {self.code}: {self.message}"


FORBIDDEN_IMPORT_ROOTS = {
    "conversation_read_view",
    "feedback_service",
    "hermes",
    "hermes_contract_layer",
    "services",
    "wecom_service",
}
PLATFORM_FORBIDDEN_TEXT = (
    "~/.hermes",
    "hermes_contract_layer",
    "wecom_service",
    "feedback_service",
    "conversation_read_view",
    "sessions.db",
    "feedback queue",
)
AUTO_MODIFY_TRUE_KEYS = {"auto_modify", "auto_apply", "auto_synthesize", "auto_modify_skill"}

BACKEND_MODE_NAMES = {"hermes", "codex", "provider_model"}
CHANNEL_NAMES = {"wecom", "qqbot", "web", "desktop"}
CONCRETE_CONTEXT_NAMES = BACKEND_MODE_NAMES | CHANNEL_NAMES | {"lawfirm"}
PRIVATE_HERMES_PATTERNS = (
    re.compile(r"(?:~|/[^\s\"']*)/\.hermes(?:/profiles)?(?:/[A-Za-z0-9_.-]+)?"),
    re.compile(r"\.hermes/profiles/[A-Za-z0-9_.-]+"),
)
WECOM_PAYLOAD_FIELD_NAMES = {
    "ToUserName",
    "FromUserName",
    "CreateTime",
    "MsgType",
    "MsgId",
    "AgentID",
    "Event",
    "EventKey",
    "Encrypt",
    "MediaId",
    "PicUrl",
    "Format",
    "Recognition",
}
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
RUNTIME_ARTIFACT_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".log", ".mp4", ".mov", ".wav", ".mp3", ".docx")
RUNTIME_PATH_PATTERNS = (
    re.compile(r"\b(?:sessions|feedback|callbacks?)\.(?:db|sqlite|sqlite3|jsonl|log)\b", re.IGNORECASE),
    re.compile(r"(?:^|[\"'\s])(?:runtime[-_/]logs?|logs?|media|uploads?)/", re.IGNORECASE),
)


@dataclass(frozen=True)
class BoundaryAllowlistPolicy:
    """Path-aware allowlist for neutral package boundary scans."""

    neutral_source_roots: tuple[Path, ...] = field(
        default_factory=lambda: (
            Path("packages/platform-contract/src"),
            Path("packages/platform-runtime/src"),
        )
    )
    neutral_schema_roots: tuple[Path, ...] = field(
        default_factory=lambda: (Path("packages/platform-contract/src/platform_contract/schemas"),)
    )
    neutral_data_roots: tuple[Path, ...] = field(
        default_factory=lambda: (
            Path("packages/platform-contract/fixtures"),
            Path("packages/contract-test-suite/fixtures"),
        )
    )
    architecture_doc_roots: tuple[Path, ...] = field(default_factory=lambda: (Path("docs/architecture"),))
    concrete_package_roots: tuple[Path, ...] = field(
        default_factory=lambda: (
            Path("packages/channels"),
            Path("packages/backends"),
            Path("packages/solutions"),
            Path("packages/solution-loader"),
            Path("services/channels"),
            Path("services/backends"),
            Path("services/solutions"),
            Path("solutions"),
        )
    )

    def iter_neutral_text_files(self, repo_root: Path) -> Iterable[Path]:
        for root in self.neutral_source_roots + self.neutral_schema_roots:
            yield from self._iter_text_files(repo_root / root)

    def iter_neutral_data_files(self, repo_root: Path) -> Iterable[Path]:
        for root in self.neutral_data_roots:
            yield from self._iter_data_files(repo_root / root)

    def is_concrete_name_allowed(self, path: Path, name: str, repo_root: Path) -> bool:
        relative = _relative_path(path, repo_root)
        if self._is_under(relative, self.architecture_doc_roots) or self._is_under(relative, self.concrete_package_roots):
            return True
        if name in BACKEND_MODE_NAMES and relative in {
            Path("packages/platform-contract/src/platform_contract/agent_adapter.py"),
            Path("packages/platform-contract/src/platform_contract/schemas/agent_adapter_manifest.schema.json"),
        }:
            return True
        if name in CHANNEL_NAMES and relative in {
            Path("packages/platform-contract/src/platform_contract/enums.py"),
            Path("packages/platform-contract/src/platform_contract/schemas/common.schema.json"),
        }:
            return True
        return False

    def _iter_text_files(self, root: Path) -> Iterable[Path]:
        if not root.exists():
            return
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json", ".md"} and not _is_ignored_path(path):
                yield path

    def _iter_data_files(self, root: Path) -> Iterable[Path]:
        if not root.exists():
            return
        for path in sorted(root.rglob("*")):
            if path.is_file() and not _is_ignored_path(path):
                yield path

    @staticmethod
    def _is_under(path: Path, roots: tuple[Path, ...]) -> bool:
        return any(path == root or root in path.parents for root in roots)


def assert_platform_contract_import_boundary(repo_root: str | Path = REPO_ROOT) -> None:
    root = Path(repo_root)
    platform_src = root / "packages" / "platform-contract" / "src"
    issues: list[BoundaryIssue] = []
    for path in sorted(platform_src.rglob("*.py")):
        issues.extend(_import_issues(path))
    _raise_if_issues(issues)


def assert_industry_neutral_schemas(schema_root: str | Path = PLATFORM_SCHEMA_ROOT) -> None:
    issues: list[BoundaryIssue] = []
    for path in sorted(Path(schema_root).glob("*.schema.json")):
        schema = load_json(path)
        if isinstance(schema, Mapping):
            issues.extend(_schema_issues(schema, path=path))
    _raise_if_issues(issues)


def assert_thin_layer_scope(repo_root: str | Path = REPO_ROOT) -> None:
    root = Path(repo_root)
    issues: list[BoundaryIssue] = []
    for path in sorted((root / "packages" / "platform-contract" / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in PLATFORM_FORBIDDEN_TEXT:
            if marker in text:
                issues.append(
                    BoundaryIssue(
                        path=path,
                        code="platform_runtime_marker",
                        message=f"platform contract source mentions runtime marker {marker!r}",
                    )
                )

    bundle_root = root / "services" / "hermes-contract-layer" / "bundles"
    for path in sorted(bundle_root.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        policy = value.get("runtime_material_policy") if isinstance(value, Mapping) else None
        if not isinstance(policy, Mapping):
            issues.append(BoundaryIssue(path, "bundle_policy_missing", "bundle manifest requires runtime_material_policy"))
            continue
        for field in (
            "repo_contains_runtime_values",
            "repo_contains_raw_values",
            "repo_contains_private_documents",
            "repo_contains_binary_uploads",
        ):
            if policy.get(field) is not False:
                issues.append(BoundaryIssue(path, "bundle_policy_unsafe", f"{field} must be false"))
    _raise_if_issues(issues)


def assert_feedback_human_review_safety(fixtures: Iterable[str | Path | Mapping[str, Any]]) -> None:
    issues: list[BoundaryIssue] = []
    for source in fixtures:
        path, fixture = _load_fixture(source)
        events = fixture.get("events", {}) if isinstance(fixture, Mapping) else {}
        if not isinstance(events, Mapping):
            continue
        for event_key in ("agent_result", "feedback_event"):
            event = events.get(event_key)
            if not isinstance(event, Mapping):
                continue
            issues.extend(_feedback_event_safety_issues(event, path=path, event_key=event_key))
    _raise_if_issues(issues)


def assert_neutral_boundary_allowlist(
    repo_root: str | Path = REPO_ROOT,
    policy: BoundaryAllowlistPolicy | None = None,
) -> None:
    root = Path(repo_root)
    active_policy = policy or BoundaryAllowlistPolicy()
    issues: list[BoundaryIssue] = []

    for path in active_policy.iter_neutral_text_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        issues.extend(_neutral_text_issues(path, text, repo_root=root, policy=active_policy))
        if path.suffix == ".json":
            issues.extend(_neutral_schema_file_issues(path, text))

    for path in active_policy.iter_neutral_data_files(root):
        issues.extend(_runtime_artifact_path_issues(path))
        if path.suffix not in {".json", ".jsonl"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        issues.extend(_secret_and_runtime_text_issues(path, text))
        issues.extend(_raw_payload_data_issues(path, text))

    _raise_if_issues(issues)


def _import_issues(path: Path) -> list[BoundaryIssue]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [BoundaryIssue(path, "syntax_error", str(exc), line=exc.lineno)]

    issues: list[BoundaryIssue] = []
    for node in ast.walk(tree):
        module_names: list[str] = []
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Import):
            module_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_names.append(node.module)
        for module_name in module_names:
            root = module_name.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                issues.append(
                    BoundaryIssue(
                        path=path,
                        code="forbidden_platform_import",
                        message=f"platform-contract must not import {module_name}",
                        line=line,
                    )
                )
    return issues


def _schema_issues(schema: Mapping[str, Any], *, path: Path) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    properties = schema.get("properties", {})
    if isinstance(properties, Mapping):
        forbidden_properties = sorted(set(properties) & FORBIDDEN_TOP_LEVEL_FIELDS)
        for field in forbidden_properties:
            issues.append(BoundaryIssue(path, "forbidden_schema_property", f"top-level property {field} is forbidden"))
    issues.extend(_required_field_issues(schema, path=path))
    return issues


def _required_field_issues(value: Any, *, path: Path, schema_path: str = "") -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    if isinstance(value, Mapping):
        required = value.get("required")
        if isinstance(required, list):
            forbidden = sorted({item for item in required if isinstance(item, str)} & FORBIDDEN_TOP_LEVEL_FIELDS)
            for field in forbidden:
                issues.append(
                    BoundaryIssue(
                        path,
                        "forbidden_required_field",
                        f"required field {schema_path}.{field}".strip(".") + " is forbidden",
                    )
                )
        for key, child in value.items():
            child_path = f"{schema_path}.{key}" if schema_path else str(key)
            issues.extend(_required_field_issues(child, path=path, schema_path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_required_field_issues(child, path=path, schema_path=f"{schema_path}[{index}]"))
    return issues


def _feedback_event_safety_issues(event: Mapping[str, Any], *, path: Path, event_key: str) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    skill_candidate = event.get("skill_candidate")
    has_skill_candidate = isinstance(skill_candidate, Mapping) and bool(skill_candidate.get("detected", True))
    is_route_mismatch = bool(event.get("route_mismatch")) or event.get("event_type") == "route_mismatch"
    if not (is_route_mismatch or has_skill_candidate):
        return issues

    if isinstance(skill_candidate, Mapping) and skill_candidate.get("requires_human_review") is not True:
        issues.append(
            BoundaryIssue(
                path,
                "human_review_required",
                f"{event_key}.skill_candidate.requires_human_review must be true",
            )
        )
    elif not isinstance(skill_candidate, Mapping) and event.get("requires_human_review") is not True:
        issues.append(BoundaryIssue(path, "human_review_required", f"{event_key} requires human review evidence"))

    if _has_auto_modify_true(event):
        issues.append(BoundaryIssue(path, "auto_modify_forbidden", f"{event_key} enables automatic skill modification"))
    if not _has_no_auto_modify_evidence(event):
        issues.append(BoundaryIssue(path, "no_auto_modify_missing", f"{event_key} must include no-auto-modify evidence"))
    return issues


def _neutral_text_issues(
    path: Path,
    text: str,
    *,
    repo_root: Path,
    policy: BoundaryAllowlistPolicy,
) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        issues.extend(_private_hermes_issues(path, line, line=line_number))
        issues.extend(_wecom_payload_field_issues(path, line, line=line_number))
        issues.extend(_secret_and_runtime_line_issues(path, line, line=line_number))
        issues.extend(_concrete_name_issues(path, line, line=line_number, repo_root=repo_root, policy=policy))
    return issues


def _neutral_schema_file_issues(path: Path, text: str) -> list[BoundaryIssue]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, Mapping):
        return []
    return _schema_issues(value, path=path)


def _private_hermes_issues(path: Path, line_text: str, *, line: int) -> list[BoundaryIssue]:
    return [
        BoundaryIssue(path, "private_hermes_path", "private Hermes runtime/profile path is forbidden", line=line)
        for pattern in PRIVATE_HERMES_PATTERNS
        if pattern.search(line_text)
    ]


def _wecom_payload_field_issues(path: Path, line_text: str, *, line: int) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for field_name in WECOM_PAYLOAD_FIELD_NAMES:
        if re.search(rf"\b{re.escape(field_name)}\b", line_text):
            issues.append(
                BoundaryIssue(
                    path,
                    "wecom_payload_internal",
                    f"WeCom callback payload field {field_name!r} is forbidden in neutral packages",
                    line=line,
                )
            )
    return issues


def _secret_and_runtime_text_issues(path: Path, text: str) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for line_number, line_text in enumerate(text.splitlines(), start=1):
        issues.extend(_secret_and_runtime_line_issues(path, line_text, line=line_number))
    return issues


def _secret_and_runtime_line_issues(path: Path, line_text: str, *, line: int) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for code, pattern in SECRET_PATTERNS:
        if pattern.search(line_text):
            issues.append(BoundaryIssue(path, code, "plaintext secret-like value is forbidden", line=line))
    for pattern in RUNTIME_PATH_PATTERNS:
        if pattern.search(line_text):
            issues.append(BoundaryIssue(path, "runtime_artifact_path", "runtime DB/log/media path is forbidden", line=line))
    return issues


def _concrete_name_issues(
    path: Path,
    line_text: str,
    *,
    line: int,
    repo_root: Path,
    policy: BoundaryAllowlistPolicy,
) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for name in CONCRETE_CONTEXT_NAMES:
        if not re.search(rf"\b{re.escape(name)}\b", line_text, flags=re.IGNORECASE):
            continue
        if policy.is_concrete_name_allowed(path, name, repo_root):
            continue
        issues.append(
            BoundaryIssue(
                path,
                "concrete_name_not_allowlisted",
                f"concrete name {name!r} is not allowed in this neutral package context",
                line=line,
            )
        )
    return issues


def _raw_payload_data_issues(path: Path, text: str) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    if path.suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return issues
        issues.extend(_raw_payload_value_issues(value, path=path))
    elif path.suffix == ".jsonl":
        for line_number, line_text in enumerate(text.splitlines(), start=1):
            if not line_text.strip():
                continue
            try:
                value = json.loads(line_text)
            except json.JSONDecodeError:
                continue
            issues.extend(_raw_payload_value_issues(value, path=path, line=line_number))
    return issues


def _raw_payload_value_issues(value: Any, *, path: Path, line: int | None = None, key_path: str = "") -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if key == "raw_payload":
                issues.append(
                    BoundaryIssue(
                        path,
                        "raw_payload_field",
                        f"exact raw_payload field is forbidden at {child_path}",
                        line=line,
                    )
                )
            issues.extend(_raw_payload_value_issues(child, path=path, line=line, key_path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{key_path}[{index}]"
            issues.extend(_raw_payload_value_issues(child, path=path, line=line, key_path=child_path))
    return issues


def _runtime_artifact_path_issues(path: Path) -> list[BoundaryIssue]:
    lowered = path.name.lower()
    if lowered.endswith(RUNTIME_ARTIFACT_SUFFIXES):
        return [BoundaryIssue(path, "runtime_artifact", "runtime DB/log/media artifact must not be committed")]
    return []


def _has_auto_modify_true(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in AUTO_MODIFY_TRUE_KEYS and child is True:
                return True
            if _has_auto_modify_true(child):
                return True
    elif isinstance(value, list):
        return any(_has_auto_modify_true(child) for child in value)
    return False


def _has_no_auto_modify_evidence(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("no_auto_modify") is True or value.get("auto_modify_skill") is False:
            return True
        return any(_has_no_auto_modify_evidence(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_no_auto_modify_evidence(child) for child in value)
    return False


def _load_fixture(source: str | Path | Mapping[str, Any]) -> tuple[Path, Mapping[str, Any]]:
    if isinstance(source, Mapping):
        return Path("<memory>"), source
    path = Path(source)
    return path, json.loads(path.read_text(encoding="utf-8"))


def _raise_if_issues(issues: list[BoundaryIssue]) -> None:
    if issues:
        details = "; ".join(issue.summary() for issue in issues[:5])
        remaining = "" if len(issues) <= 5 else f"; ... {len(issues) - 5} more"
        raise AssertionError(f"{len(issues)} boundary issue(s): {details}{remaining}")


def _relative_path(path: Path, repo_root: Path) -> Path:
    try:
        return path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return path


def _is_ignored_path(path: Path) -> bool:
    return bool(set(path.parts) & {".git", "__pycache__", ".pytest_cache"}) or path.suffix in {".pyc", ".pyo"}


__all__ = [
    "BoundaryAllowlistPolicy",
    "BoundaryIssue",
    "assert_feedback_human_review_safety",
    "assert_industry_neutral_schemas",
    "assert_neutral_boundary_allowlist",
    "assert_platform_contract_import_boundary",
    "assert_thin_layer_scope",
]
