"""Metadata extractor — enriches ``ScannedSkill`` with 8 SKILL-03 fields.

Extracts:
1. ``token_estimate`` — carried over from the scanner.
2. ``declared_gates`` — legal guardrails referenced in body text.
3. ``referenced_resources`` — shared reference file paths in body text.
4. ``practice_profile_dependency`` — whether the skill references CLAUDE.md.
5. ``host_assumptions`` — trigger patterns and argument-hint assumptions.
6. ``required_scripts`` — script paths referenced in body or present on disk.
7. ``source_repo`` — repo name from the scanner.
8. ``license`` — from frontmatter or project-level.

CRITICAL: The extractor is read-only.  It reads body text and optionally lists
files in a directory (``Path.glob``) but never writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .scanner import ScannedSkill


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Eight SKILL-03 metadata fields for a single skill.

    Attributes:
        token_estimate: Estimated token count (from scanner).
        declared_gates: Legal guardrails declared by this skill.
        referenced_resources: Resource file paths referenced in body.
        practice_profile_dependency: Whether the skill references CLAUDE.md.
        host_assumptions: Trigger patterns and argument-hint assumptions.
        required_scripts: Script paths referenced or present in skill dir.
        source_repo: Repo name (``"ai-for-china-legal"`` or ``"legal-skills"``).
        license: License string from frontmatter or ``None``.
    """

    token_estimate: int
    declared_gates: list[str] = field(default_factory=list)
    referenced_resources: list[str] = field(default_factory=list)
    practice_profile_dependency: bool = False
    host_assumptions: list[str] = field(default_factory=list)
    required_scripts: list[str] = field(default_factory=list)
    source_repo: str = ""
    license: str | None = None


# ---------------------------------------------------------------------------
# Gate extraction
# ---------------------------------------------------------------------------

_GATE_PATTERNS: list[tuple[str, list[str]]] = [
    ("research-gate", ["research-gate", "研究闸门"]),
    ("ask-user-enforcement", ["ask-user", "ask_user", "澄清"]),
    ("citation-audit", ["citation", "引用", "来源标注"]),
    ("de-ai-polish", ["de-ai-polish", "去AI化", "de-AI"]),
]


def _extract_declared_gates(body: str) -> list[str]:
    """Return sorted unique list of declared legal guardrails found in *body*."""
    found: set[str] = set()
    for gate_id, patterns in _GATE_PATTERNS:
        for pat in patterns:
            if pat in body:
                found.add(gate_id)
                break
    return sorted(found)


# ---------------------------------------------------------------------------
# Referenced resources extraction
# ---------------------------------------------------------------------------

_RESOURCE_PATTERNS: list[re.Pattern[str]] = [
    # shared/references/...  or  shared/research-gate/...
    re.compile(r"shared/references/[^\s`|)>\]'\"]+"),
    re.compile(r"shared/research-gate/[^\s`|)>\]'\"]+"),
    # _shared/...
    re.compile(r"_shared/[^\s`|)>\]'\"]+"),
    # references/... (relative to skill directory) — avoid matching
    # ``shared/references/`` again by requiring the path to not be preceded by
    # ``shared/``.
    re.compile(r"(?<!shared/)references/[^\s`|)>\]'\"]+"),
]


def _extract_referenced_resources(body: str) -> list[str]:
    """Return sorted unique list of resource file paths found in *body*."""
    found: set[str] = set()
    for pattern in _RESOURCE_PATTERNS:
        for match in pattern.finditer(body):
            found.add(match.group(0).rstrip(".,;:"))
    return sorted(found)


# ---------------------------------------------------------------------------
# Practice profile dependency
# ---------------------------------------------------------------------------

_PRACTICE_PROFILE_MARKERS: list[str] = [
    "CLAUDE.md",
    "实践配置",
    "审查立场",
    "执业配置",
]


def _check_practice_profile_dependency(body: str) -> bool:
    """Return True if *body* references CLAUDE.md or practice-profile concepts."""
    return any(marker in body for marker in _PRACTICE_PROFILE_MARKERS)


# ---------------------------------------------------------------------------
# Host assumptions extraction
# ---------------------------------------------------------------------------

_TRIGGER_PATTERN: re.Pattern[str] = re.compile(
    r"/[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+"
)


def _extract_host_assumptions(
    body: str, frontmatter: dict[str, Any]
) -> list[str]:
    """Return trigger patterns and argument-hint assumptions.

    Extracts ``/<plugin>:<skill>`` trigger patterns from body text and the
    ``argument-hint`` field from frontmatter (if present).
    """
    assumptions: list[str] = []
    seen: set[str] = set()
    for match in _TRIGGER_PATTERN.finditer(body):
        trig = match.group(0)
        if trig not in seen:
            seen.add(trig)
            assumptions.append(trig)
    arg_hint = frontmatter.get("argument-hint")
    if isinstance(arg_hint, str) and arg_hint.strip():
        hint = arg_hint.strip()
        if hint not in seen:
            assumptions.append(hint)
    return assumptions


# ---------------------------------------------------------------------------
# Required scripts extraction
# ---------------------------------------------------------------------------

_SCRIPT_REF_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|[\s`|(>'\"])(scripts/[^\s`|)>\]'\"]+\.py)"
)


def _extract_required_scripts(
    body: str,
    skill_file_path: str,
    skill_dir: Path | None = None,
) -> list[str]:
    """Return sorted unique list of script paths referenced in body or on disk.

    Scans *body* for ``scripts/<name>.py`` references.  If *skill_dir* is
    provided (the directory containing the SKILL.md), also lists ``.py`` files
    in a ``scripts/`` sub-directory via ``glob`` (read-only).
    """
    found: set[str] = set()
    for match in _SCRIPT_REF_PATTERN.finditer(body):
        path = match.group(1).rstrip(".,;:")
        found.add(path)
    if skill_dir is not None:
        scripts_dir = Path(skill_dir) / "scripts"
        if scripts_dir.is_dir():
            for py_file in scripts_dir.glob("*.py"):
                found.add(f"scripts/{py_file.name}")
    return sorted(found)


# ---------------------------------------------------------------------------
# License extraction
# ---------------------------------------------------------------------------


def _extract_license(
    frontmatter: dict[str, Any], source_repo: str
) -> str | None:
    """Return the license string from *frontmatter* or ``None``.

    - legal-skills: frontmatter ``license`` field (always present per research).
    - ai-for-china-legal: ``None`` (license is project-level, not per-skill).
    """
    lic = frontmatter.get("license")
    if isinstance(lic, str) and lic.strip():
        return lic.strip()
    # ai-for-china-legal has no per-skill license.
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_metadata(
    skill: ScannedSkill, skill_dir: Path | None = None
) -> SkillMetadata:
    """Extract all 8 SKILL-03 metadata fields for *skill*.

    Args:
        skill: The scanned skill record.
        skill_dir: Optional directory containing the SKILL.md (used to list
            ``scripts/*.py`` files on disk).  Read-only — never writes.

    Returns:
        A ``SkillMetadata`` with all fields populated.
    """
    return SkillMetadata(
        token_estimate=skill.token_estimate,
        declared_gates=_extract_declared_gates(skill.body),
        referenced_resources=_extract_referenced_resources(skill.body),
        practice_profile_dependency=_check_practice_profile_dependency(
            skill.body
        ),
        host_assumptions=_extract_host_assumptions(
            skill.body, skill.frontmatter
        ),
        required_scripts=_extract_required_scripts(
            skill.body, skill.absolute_path, skill_dir
        ),
        source_repo=skill.source_repo,
        license=_extract_license(skill.frontmatter, skill.source_repo),
    )
