"""ACP materializer — Claude Code plugin format + host assumption rewriting.

Produces a Claude Code plugin format directory layout from a
``skill-index.json``, applying host assumption rewriting to SKILL.md content.

Layout produced::

    output_dir/
    ├── .claude-plugin/
    │   └── plugin.json
    ├── skills/
    │   ├── <skill-name>/
    │   │   └── SKILL.md
    │   └── ...
    └── rewrite-report.json

Strategy per skill:
- **No host assumptions + no scripts/** → symlink to source dir (zero-copy)
- **Has host assumptions to rewrite** → rewritten SKILL.md written as a file
  (not symlink, since content differs from source)
- **Has scripts/** → ``shutil.copytree`` with ``.sync_source`` marker
  (then SKILL.md is overwritten with rewritten content if needed)

The rewrite report is written to ``output_dir/rewrite-report.json`` for
auditability.

CRITICAL: The materializer is READ-ONLY with respect to source repos.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .hermes_materializer import (
    _has_scripts_dir,
    _load_index,
    _resolve_source_dir,
    _symlink_name,
    _write_sync_source_marker,
)
from .host_assumption_rewriter import HostAssumptionRewriter, RewriteReport


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ACPMaterializationResult:
    """Result of an ACP materialization run.

    Attributes:
        materialized_count: Total number of skills materialized.
        symlinked_count: Number of skills symlinked (no rewriting needed).
        copied_count: Number of skills copied via ``shutil.copytree``
            (because they have ``scripts/``).
        rewritten_count: Number of skills whose SKILL.md was rewritten
            (host assumptions changed).
        fallback_count: Number of skills copied because symlink failed.
        errors: List of error messages.
        rewrite_report: Aggregated :class:`RewriteReport` from all skills.
        output_dir: The output directory path.
    """

    materialized_count: int
    symlinked_count: int
    copied_count: int
    rewritten_count: int
    fallback_count: int
    errors: list[str] = field(default_factory=list)
    rewrite_report: RewriteReport = field(default_factory=RewriteReport)
    output_dir: str = ""


# ---------------------------------------------------------------------------
# Plugin.json template
# ---------------------------------------------------------------------------


def _build_plugin_json(skills: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal ``plugin.json`` for the materialized output."""
    return {
        "name": "inkstatute-materialized-skills",
        "version": "1.0.0",
        "description": "Materialized legal skills from skill-index.json",
        "skills": [
            {
                "name": s.get("name", ""),
                "description": s.get("description") or "",
            }
            for s in skills
        ],
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_rewrite_report(report: RewriteReport) -> dict[str, Any]:
    """Serialize a :class:`RewriteReport` to a JSON-compatible dict."""
    return {
        "total_rewrites": report.total_rewrites,
        "text_changed": report.text_changed,
        "entries": [
            {
                "original_text": e.original_text,
                "rewritten_text": e.rewritten_text,
                "rule_applied": e.rule_applied,
                "location": e.location,
                "line_number": e.line_number,
            }
            for e in report.entries
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def materialize_acp(
    index_path: str | Path,
    output_dir: str | Path,
) -> ACPMaterializationResult:
    """Materialize skills to an ACP agent skills layout.

    Reads ``skill-index.json``, resolves source paths, and produces a Claude
    Code plugin format directory layout with host assumption rewriting.

    Args:
        index_path: Path to ``skill-index.json``.
        output_dir: Target output directory.

    Returns:
        An :class:`ACPMaterializationResult` with counts and rewrite report.
    """
    materializer = ACPMaterializer()
    return materializer.materialize(index_path, output_dir)


class ACPMaterializer:
    """ACP agent skills materializer (Claude Code plugin format + rewriting)."""

    def __init__(self) -> None:
        self._rewriter = HostAssumptionRewriter()

    def materialize(
        self,
        index_path: str | Path,
        output_dir: str | Path,
    ) -> ACPMaterializationResult:
        """Materialize skills to an ACP agent skills layout."""
        index_data = _load_index(index_path)
        repos = index_data.get("repos", {})
        skills = index_data.get("skills", [])

        out = Path(output_dir)
        skills_dir = out / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Write plugin.json
        plugin_dir = out / ".claude-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_json = _build_plugin_json(skills)
        (plugin_dir / "plugin.json").write_text(
            json.dumps(plugin_json, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        symlinked = 0
        copied = 0
        rewritten = 0
        fallback = 0
        errors: list[str] = []
        all_entries: list = []

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

            # Read source SKILL.md for rewriting check
            source_skill_md = source_dir / "SKILL.md"
            source_text = ""
            if source_skill_md.exists():
                source_text = source_skill_md.read_text(encoding="utf-8")

            # Apply host assumption rewriting
            rewritten_text, rewrite_report = self._rewriter.rewrite(
                source_text, file_path=str(source_skill_md)
            )
            needs_rewrite = rewrite_report.text_changed

            # Remove existing target if present
            if target_path.is_symlink() or target_path.exists():
                if target_path.is_symlink() or target_path.is_file():
                    target_path.unlink()
                else:
                    shutil.rmtree(target_path)

            if needs_rewrite:
                # Rewritten content: must be a file, not a symlink
                if has_scripts:
                    # Copy first (for scripts/), then overwrite SKILL.md
                    shutil.copytree(source_dir, target_path)
                    _write_sync_source_marker(target_path, source_repo)
                    copied += 1
                else:
                    # Create directory and write rewritten SKILL.md
                    target_path.mkdir(parents=True, exist_ok=True)
                    # Copy any non-SKILL.md files from source
                    for item in source_dir.iterdir():
                        if item.name == "SKILL.md":
                            continue
                        if item.is_file():
                            shutil.copy2(item, target_path / item.name)
                        elif item.is_dir():
                            shutil.copytree(item, target_path / item.name)

                # Write rewritten SKILL.md
                (target_path / "SKILL.md").write_text(
                    rewritten_text, encoding="utf-8"
                )
                rewritten += 1
            elif has_scripts:
                # Copy skills with scripts/ (no rewriting needed)
                shutil.copytree(source_dir, target_path)
                _write_sync_source_marker(target_path, source_repo)
                copied += 1
            else:
                # No rewriting, no scripts: symlink
                try:
                    os.symlink(source_dir, target_path)
                    symlinked += 1
                except OSError:
                    shutil.copytree(source_dir, target_path)
                    _write_sync_source_marker(target_path, source_repo)
                    fallback += 1

            # Collect rewrite entries
            all_entries.extend(rewrite_report.entries)

        # Build aggregated rewrite report
        aggregated_report = RewriteReport(
            entries=all_entries,
            total_rewrites=len(all_entries),
            text_changed=len(all_entries) > 0,
        )

        # Write rewrite report to output
        report_path = out / "rewrite-report.json"
        report_path.write_text(
            json.dumps(
                _serialize_rewrite_report(aggregated_report),
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        return ACPMaterializationResult(
            materialized_count=len(skills) - len(errors),
            symlinked_count=symlinked,
            copied_count=copied,
            rewritten_count=rewritten,
            fallback_count=fallback,
            errors=errors,
            rewrite_report=aggregated_report,
            output_dir=str(out),
        )
