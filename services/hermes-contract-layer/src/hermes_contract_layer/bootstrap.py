"""Non-mutating Hermes bootstrap probes and sanitized bundle checks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .adapter_manifest import build_hermes_adapter_manifest


@dataclass(frozen=True, slots=True)
class HermesBootstrapIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class HermesBootstrapReport:
    passed: bool
    issues: list[HermesBootstrapIssue]
    capabilities: dict[str, Any]


def probe_hermes_capabilities(
    root_path: str | Path,
    profile_path: str | Path,
    contract_log_path: str | Path,
) -> HermesBootstrapReport:
    """Probe supplied Hermes paths without mutating them."""

    root = Path(root_path)
    profile = Path(profile_path)
    contract_log = Path(contract_log_path)
    issues: list[HermesBootstrapIssue] = []
    manifest = build_hermes_adapter_manifest(
        backend_version=_version_marker(root),
        profile_name=profile.name or "lawfirm",
    )
    hooks_dir = profile / "hooks"
    response_filter_dir = hooks_dir / "response_filter"
    recorder_dir = hooks_dir / "response_filter_contract_result_recorder"

    if not root.exists():
        issues.append(_issue("missing_hermes_root", "Hermes root path does not exist", root))
    elif not ((root / "VERSION").exists() or (root / "gateway").exists() or (root / "hermes_agent").exists()):
        issues.append(_issue("missing_version_or_source", "Hermes root lacks VERSION or source directory marker", root))

    if not profile.exists():
        issues.append(_issue("missing_profile_path", "Hermes lawfirm profile path does not exist", profile))
    if not response_filter_dir.exists():
        issues.append(_issue("missing_response_filter_hook", "response_filter hook directory is required", response_filter_dir))
    if not recorder_dir.exists():
        issues.append(_issue("missing_recorder_hook", "after-filter recorder hook directory is required", recorder_dir))
    if _is_inside_repo(contract_log):
        issues.append(_issue("contract_log_inside_repo", "contract log path must point outside this repository", contract_log))
    if manifest["capabilities"].get("no_channel_io") is not True:
        issues.append(_issue("no_channel_io_not_verified", "Hermes adapter manifest must declare no_channel_io true"))

    capabilities = {
        "hermes_root_exists": root.exists(),
        "profile_exists": profile.exists(),
        "response_filter_present": response_filter_dir.exists(),
        "after_filter_recorder_present": recorder_dir.exists(),
        "contract_log_outside_repo": not _is_inside_repo(contract_log),
        "no_channel_io": manifest["capabilities"].get("no_channel_io") is True,
        "hook_event_support": manifest["capabilities"].get("hook_event_support", []),
    }
    return HermesBootstrapReport(passed=not issues, issues=issues, capabilities=capabilities)


def check_sanitized_bundle_manifest(path: str | Path) -> HermesBootstrapReport:
    """Check a sanitized lawfirm bundle manifest for forbidden indicators."""

    manifest_path = Path(path)
    issues: list[HermesBootstrapIssue] = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(_issue("missing_bundle_manifest", "bundle manifest does not exist", manifest_path))
        return HermesBootstrapReport(False, issues, {"manifest_path": str(manifest_path)})

    for found_path, text in _walk_strings(data):
        lowered = text.lower()
        if any(indicator in lowered for indicator in FORBIDDEN_BUNDLE_INDICATORS):
            issues.append(
                HermesBootstrapIssue(
                    code="forbidden_bundle_indicator",
                    message="bundle manifest contains a forbidden sensitive/runtime indicator",
                    path=found_path,
                )
            )

    capabilities = {
        "manifest_path": str(manifest_path),
        "env_names_only": bool(isinstance(data, dict) and data.get("external_env_names")),
        "entry_count": len(data) if isinstance(data, dict) else 0,
    }
    return HermesBootstrapReport(passed=not issues, issues=issues, capabilities=capabilities)


FORBIDDEN_BUNDLE_INDICATORS = (
    "secret",
    "token",
    "aes",
    "key",
    "database",
    "feedback.jsonl",
    "logs",
    "customer",
    "media",
    "raw_payload",
)


def _version_marker(root: Path) -> str:
    version_path = root / "VERSION"
    if version_path.exists():
        text = version_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return "hermes-version-unverified"


def _issue(code: str, message: str, path: Path | None = None) -> HermesBootstrapIssue:
    return HermesBootstrapIssue(code=code, message=message, path=str(path) if path is not None else None)


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return current.parents[4]


def _is_inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(_repo_root().resolve())
    except ValueError:
        return False
    return True


def _walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            found.append((f"{path}.{key_text}", key_text))
            found.extend(_walk_strings(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_strings(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


__all__ = [
    "HermesBootstrapIssue",
    "HermesBootstrapReport",
    "check_sanitized_bundle_manifest",
    "probe_hermes_capabilities",
]
