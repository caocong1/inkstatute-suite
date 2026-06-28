"""Thin-layer and composability boundary checks for InkStatute V2."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
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


__all__ = [
    "BoundaryIssue",
    "assert_feedback_human_review_safety",
    "assert_industry_neutral_schemas",
    "assert_platform_contract_import_boundary",
    "assert_thin_layer_scope",
]

