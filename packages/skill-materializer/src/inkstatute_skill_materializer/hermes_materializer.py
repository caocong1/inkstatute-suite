"""Hermes materializer — symlink-first, copy for scripts/.

Produces a Hermes profile layout under
``output_dir/profiles/<profile>/skills/<skill-name>/`` from a
``skill-index.json``.

Strategy per skill:
- **No ``scripts/`` directory** → symlink to the source SKILL.md directory
  (zero-copy, always current with upstream).  Falls back to
  ``shutil.copytree`` if ``os.symlink`` raises ``OSError`` (cross-filesystem
  or permissions).
- **Has ``scripts/`` directory** → ``shutil.copytree`` with a
  ``.sync_source`` marker file (copies are needed when local modification
  is possible).

Symlink naming convention:
- ai-for-china-legal: ``<plugin>-<skill-name>``
- legal-skills: ``legal-<skill-name>``

CRITICAL: The materializer is READ-ONLY with respect to source repos.
It reads ``skill-index.json`` and source repo files (to check for
``scripts/`` directories) but never writes to source repos.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StrategyEntry:
    """Per-skill strategy log entry."""

    skill_id: str
    skill_name: str
    strategy: str  # "symlink" | "copy" | "fallback_copy"
    target_path: str
    source_path: str
    has_scripts: bool


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    """Result of a Hermes materialization run.

    Attributes:
        materialized_count: Total number of skills materialized.
        symlinked_count: Number of skills symlinked (zero-copy).
        copied_count: Number of skills copied via ``shutil.copytree``
            (because they have ``scripts/``).
        fallback_count: Number of skills copied because symlink failed.
        errors: List of error messages.
        strategy_log: Per-skill strategy entries.
        output_dir: The output directory path.
        profile_name: The profile name used.
    """

    materialized_count: int
    symlinked_count: int
    copied_count: int
    fallback_count: int
    errors: list[str] = field(default_factory=list)
    strategy_log: list[StrategyEntry] = field(default_factory=list)
    output_dir: str = ""
    profile_name: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_index(index_path: str | Path) -> dict[str, Any]:
    """Load a skill-index.json file and return the parsed dict."""
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"skill-index.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_source_dir(
    record: dict[str, Any],
    repos: dict[str, dict[str, Any]],
) -> Path:
    """Resolve the absolute path to the skill's source directory.

    Uses ``repos[record["source_repo"]]["path"]`` + ``record["relative_path"]``
    to construct the absolute path.  The ``relative_path`` points to the
    SKILL.md file, so the source directory is its parent.
    """
    repo_name = record["source_repo"]
    repo_info = repos.get(repo_name)
    if repo_info is None:
        raise KeyError(f"Repo '{repo_name}' not found in index repos metadata")
    repo_path = Path(repo_info["path"])
    relative_path = Path(record["relative_path"])
    # relative_path points to SKILL.md; parent is the skill directory
    skill_file = repo_path / relative_path
    return skill_file.parent


def _has_scripts_dir(source_dir: Path) -> bool:
    """Check if the source skill directory has a ``scripts/`` subdirectory."""
    return (source_dir / "scripts").is_dir()


def _symlink_name(record: dict[str, Any]) -> str:
    """Compute the symlink/directory name for a skill.

    - ai-for-china-legal: ``<plugin>-<skill-name>``
    - legal-skills: ``legal-<skill-name>``
    """
    source_repo = record["source_repo"]
    name = record["name"]
    plugin = record.get("plugin")
    if source_repo == "legal-skills":
        return f"legal-{name}"
    if plugin:
        return f"{plugin}-{name}"
    return name


def _write_sync_source_marker(
    target_dir: Path,
    source_repo: str,
) -> None:
    """Write a ``.sync_source`` marker file in the copied directory."""
    marker = target_dir / ".sync_source"
    marker.write_text(f"{source_repo}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def materialize_hermes(
    index_path: str | Path,
    output_dir: str | Path,
    profile_name: str = "lawfirm",
) -> MaterializationResult:
    """Materialize skills to a Hermes profile layout.

    Reads ``skill-index.json``, resolves source paths, and produces a Hermes
    profile layout under ``output_dir/profiles/<profile>/skills/<skill-name>/``.

    Args:
        index_path: Path to ``skill-index.json``.
        output_dir: Root output directory.  Skills are written under
            ``output_dir/profiles/<profile>/skills/``.
        profile_name: Hermes profile name (default: ``"lawfirm"``).

    Returns:
        A :class:`MaterializationResult` with counts, errors, and strategy log.
    """
    materializer = HermesMaterializer()
    return materializer.materialize(index_path, output_dir, profile_name)


class HermesMaterializer:
    """Hermes profile materializer (symlink-first, copy for scripts/)."""

    def materialize(
        self,
        index_path: str | Path,
        output_dir: str | Path,
        profile_name: str = "lawfirm",
    ) -> MaterializationResult:
        """Materialize skills to a Hermes profile layout."""
        index_data = _load_index(index_path)
        repos = index_data.get("repos", {})
        skills = index_data.get("skills", [])

        skills_dir = (
            Path(output_dir) / "profiles" / profile_name / "skills"
        )
        skills_dir.mkdir(parents=True, exist_ok=True)

        symlinked = 0
        copied = 0
        fallback = 0
        errors: list[str] = []
        strategy_log: list[StrategyEntry] = []

        for record in skills:
            skill_id = record.get("skill_id", "")
            skill_name = record.get("name", "")
            source_repo = record.get("source_repo", "")

            try:
                source_dir = _resolve_source_dir(record, repos)
            except (KeyError, FileNotFoundError) as exc:
                errors.append(f"{skill_id}: cannot resolve source dir: {exc}")
                continue

            if not source_dir.exists():
                errors.append(
                    f"{skill_id}: source directory does not exist: {source_dir}"
                )
                continue

            link_name = _symlink_name(record)
            target_path = skills_dir / link_name
            has_scripts = _has_scripts_dir(source_dir)

            # Remove existing target if present
            if target_path.is_symlink() or target_path.exists():
                if target_path.is_symlink() or target_path.is_file():
                    target_path.unlink()
                else:
                    shutil.rmtree(target_path)

            strategy = ""
            if not has_scripts:
                # Try symlink first
                try:
                    os.symlink(source_dir, target_path)
                    strategy = "symlink"
                    symlinked += 1
                except OSError:
                    # Fallback to copy
                    shutil.copytree(source_dir, target_path)
                    _write_sync_source_marker(target_path, source_repo)
                    strategy = "fallback_copy"
                    fallback += 1
            else:
                # Copy skills with scripts/
                shutil.copytree(source_dir, target_path)
                _write_sync_source_marker(target_path, source_repo)
                strategy = "copy"
                copied += 1

            strategy_log.append(
                StrategyEntry(
                    skill_id=skill_id,
                    skill_name=skill_name,
                    strategy=strategy,
                    target_path=str(target_path),
                    source_path=str(source_dir),
                    has_scripts=has_scripts,
                )
            )

        return MaterializationResult(
            materialized_count=len(strategy_log),
            symlinked_count=symlinked,
            copied_count=copied,
            fallback_count=fallback,
            errors=errors,
            strategy_log=strategy_log,
            output_dir=str(Path(output_dir)),
            profile_name=profile_name,
        )
