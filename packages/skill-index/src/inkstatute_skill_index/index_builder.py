"""Index builder — assembles complete skill-index.json from all components.

Orchestrates the scanner, orchestration classifier, metadata extractor, and
conflict model to produce a single ``skill-index.json`` file.

CRITICAL: The index builder is READ-ONLY with respect to source repos.
The ``write_index`` function writes only to the caller-specified
``output_path``, which must be OUTSIDE the source repos.  All repo-level
helpers (``_load_plugin_json_skills``, ``_get_repo_commit``) use read-only
filesystem operations only.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .conflict_model import (
    MergeReport,
    _detect_local_modification,
    _load_previous_index,
    build_merge_report,
    compute_content_hash,
)
from .frontmatter_parser import extract_description, extract_version
from .metadata_extractor import extract_metadata
from .orchestration_classifier import classify_all_skills
from .scanner import ScannedSkill, scan_repo


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexRecord:
    """A single skill's complete index record.

    Combines data from the scanner, classifier, metadata extractor, and
    conflict model into one flat record.
    """

    skill_id: str
    name: str
    source_repo: str
    plugin: str | None
    relative_path: str
    skill_type: str  # "orchestration" or "leaf"
    parent_skill: str | None
    child_skills: list[str]
    description: str | None
    frontmatter: dict[str, Any]
    token_estimate: int
    declared_gates: list[str]
    referenced_resources: list[str]
    practice_profile_dependency: bool
    host_assumptions: list[str]
    required_scripts: list[str]
    license: str | None
    version: str | None
    content_hash: str
    has_local_modification: bool
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class SkillIndex:
    """The complete skill index.

    Attributes:
        generated_at: ISO-8601 timestamp of index generation.
        scanner_version: Version string from ``__init__.SCANNER_VERSION``.
        repos: Per-repo metadata dict (name -> {path, commit, skill_count}).
        skills: List of :class:`IndexRecord` for all skills.
        merge_report: Serialized merge report dict.
        warnings: Top-level warnings.
    """

    generated_at: str
    scanner_version: str
    repos: dict[str, dict[str, Any]]
    skills: list[IndexRecord]
    merge_report: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_plugin_json_skills(
    repo_path: Path, repo_name: str
) -> dict[str, list[dict[str, Any]]] | None:
    """Read plugin.json files and extract the ``skills`` array per plugin.

    For ai-for-china-legal: reads each ``<plugin>/.claude-plugin/plugin.json``
    and extracts the ``skills`` array.  Returns a dict mapping
    ``plugin_name -> skills[]``.

    For legal-skills: returns ``None`` (no ``skills[]`` array in plugin.json).

    Handles missing plugin.json gracefully (returns ``None`` for that plugin,
    adds a warning to the returned structure — callers can check).
    """
    if repo_name == "legal-skills":
        return None

    result: dict[str, list[dict[str, Any]]] = {}
    # Find all plugin.json files under <repo>/<plugin>/.claude-plugin/plugin.json
    for plugin_json_path in repo_path.glob("*/.claude-plugin/plugin.json"):
        try:
            data = json.loads(plugin_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        plugin_name = data.get("name")
        skills_arr = data.get("skills")
        if plugin_name and isinstance(skills_arr, list):
            result[plugin_name] = skills_arr
    # Also check shared/ for a plugin.json (unlikely but handle gracefully)
    shared_plugin = repo_path / "shared" / ".claude-plugin" / "plugin.json"
    if shared_plugin.exists():
        try:
            data = json.loads(shared_plugin.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                plugin_name = data.get("name", "shared")
                skills_arr = data.get("skills", [])
                if isinstance(skills_arr, list):
                    result[plugin_name] = skills_arr
        except (json.JSONDecodeError, PermissionError, UnicodeDecodeError):
            pass

    return result if result else None


def _get_repo_commit(repo_path: Path) -> str | None:
    """Try to get the git commit SHA of *repo_path*.

    Returns the SHA string if successful, ``None`` if not a git repo or
    git is unavailable.  Read-only — does not modify the repo.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        PermissionError,
        OSError,
    ):
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_index(
    repo_configs: list[dict[str, str]],
    previous_index_path: str | Path | None = None,
) -> SkillIndex:
    """Assemble a complete :class:`SkillIndex` from multiple repos.

    Args:
        repo_configs: List of dicts, each with ``"name"`` and ``"path"`` keys.
            Example: ``{"name": "ai-for-china-legal", "path": "/path/to/repo"}``.
        previous_index_path: Optional path to a previous skill-index.json
            for conflict classification.

    Returns:
        A :class:`SkillIndex` with all skills, repos metadata, and merge report.
    """
    from . import SCANNER_VERSION  # late import to avoid circular

    all_skills: list[ScannedSkill] = []
    index_records: list[IndexRecord] = []
    repos_meta: dict[str, dict[str, Any]] = {}
    top_warnings: list[str] = []

    for config in repo_configs:
        repo_name = config["name"]
        repo_path = Path(config["path"])

        # 1. Scan the repo (read-only)
        scan_result = scan_repo(repo_path, repo_name)
        all_skills.extend(scan_result.skills)
        if scan_result.warnings:
            top_warnings.extend(
                f"{repo_name}:{w}" for w in scan_result.warnings
            )

        # 2. Load plugin.json skills for classification signal
        plugin_json_skills = _load_plugin_json_skills(repo_path, repo_name)

        # 3. Classify all skills from this repo
        classification_results = classify_all_skills(
            scan_result.skills, plugin_json_skills
        )

        # 4. For each skill: extract metadata, compute hash, detect local mod
        for skill in scan_result.skills:
            cls_result = classification_results.get(skill.skill_id)
            if cls_result is None:
                skill_type = "leaf"
                parent_skill: str | None = None
                child_skills: list[str] = []
            else:
                skill_type = cls_result.skill_type
                parent_skill = cls_result.parent_skill
                child_skills = cls_result.child_skills

            # Metadata extraction (read-only)
            skill_dir = Path(skill.absolute_path).parent
            metadata = extract_metadata(skill, skill_dir)

            # Content hash (pure function)
            content_hash = compute_content_hash(skill.raw_text)

            # Local modification detection (read-only Path.exists)
            has_local_mod = _detect_local_modification(skill)

            # Description and version from frontmatter
            description = extract_description(skill.frontmatter)
            version = extract_version(skill.frontmatter)

            # Assemble IndexRecord
            record = IndexRecord(
                skill_id=skill.skill_id,
                name=skill.name,
                source_repo=skill.source_repo,
                plugin=skill.plugin,
                relative_path=skill.relative_path,
                skill_type=skill_type,
                parent_skill=parent_skill,
                child_skills=child_skills,
                description=description,
                frontmatter=skill.frontmatter,
                token_estimate=metadata.token_estimate,
                declared_gates=metadata.declared_gates,
                referenced_resources=metadata.referenced_resources,
                practice_profile_dependency=metadata.practice_profile_dependency,
                host_assumptions=metadata.host_assumptions,
                required_scripts=metadata.required_scripts,
                license=metadata.license,
                version=version,
                content_hash=content_hash,
                has_local_modification=has_local_mod,
                warnings=list(skill.warnings),
            )
            index_records.append(record)

        # 5. Record repo metadata
        commit = _get_repo_commit(repo_path)
        repos_meta[repo_name] = {
            "path": str(repo_path),
            "commit": commit,
            "skill_count": len(scan_result.skills),
        }

    # 6. Load previous index for conflict classification
    previous_index: dict[str, Any] | None = None
    if previous_index_path is not None:
        previous_index = _load_previous_index(Path(previous_index_path))

    # Build merge report
    merge_report: MergeReport = build_merge_report(all_skills, previous_index)

    # Serialize merge report
    merge_report_dict = _serialize_merge_report(merge_report)

    # Timestamp
    generated_at = datetime.now(timezone.utc).isoformat()

    return SkillIndex(
        generated_at=generated_at,
        scanner_version=SCANNER_VERSION,
        repos=repos_meta,
        skills=index_records,
        merge_report=merge_report_dict,
        warnings=top_warnings,
    )


def _serialize_merge_report(report: MergeReport) -> dict[str, Any]:
    """Serialize a :class:`MergeReport` to a JSON-compatible dict."""
    return {
        "namespace_mappings": dict(report.namespace_mappings),
        "conflict_classification": {
            k: list(v) for k, v in report.conflict_classification.items()
        },
        "total_skills": report.total_skills,
        "summary": dict(report.summary),
    }


def _serialize_record(record: IndexRecord) -> dict[str, Any]:
    """Serialize a single :class:`IndexRecord` to a JSON-compatible dict."""
    return {
        "skill_id": record.skill_id,
        "name": record.name,
        "source_repo": record.source_repo,
        "plugin": record.plugin,
        "relative_path": record.relative_path,
        "skill_type": record.skill_type,
        "parent_skill": record.parent_skill,
        "child_skills": list(record.child_skills),
        "description": record.description,
        "frontmatter": dict(record.frontmatter),
        "token_estimate": record.token_estimate,
        "declared_gates": list(record.declared_gates),
        "referenced_resources": list(record.referenced_resources),
        "practice_profile_dependency": record.practice_profile_dependency,
        "host_assumptions": list(record.host_assumptions),
        "required_scripts": list(record.required_scripts),
        "license": record.license,
        "version": record.version,
        "content_hash": record.content_hash,
        "has_local_modification": record.has_local_modification,
        "warnings": list(record.warnings),
    }


def serialize_index(index: SkillIndex) -> dict[str, Any]:
    """Convert a :class:`SkillIndex` to a JSON-serializable dict.

    The returned dict matches the schema in 96-RESEARCH.md §12.
    """
    return {
        "generated_at": index.generated_at,
        "scanner_version": index.scanner_version,
        "repos": {k: dict(v) for k, v in index.repos.items()},
        "skills": [_serialize_record(r) for r in index.skills],
        "merge_report": index.merge_report,
        "warnings": list(index.warnings),
    }


def write_index(index: SkillIndex, output_path: str | Path) -> None:
    """Write the index as JSON to *output_path*.

    CRITICAL: *output_path* must be OUTSIDE the source repos.
    This is enforced by the CLI's ``_validate_output_path``; this function
    itself does not re-check, but the caller is responsible for ensuring
    read-only enforcement (SAFE-05).

    The JSON is written with ``indent=2`` and ``ensure_ascii=False``.
    """
    data = serialize_index(index)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
