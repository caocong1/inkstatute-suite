"""Dual-repo merge and 4-state conflict classification (read-only).

Inherits the 4-state conflict classification semantic from
``lawfirm-profile/scripts/sync_legal_skills.py`` but adapts it to the index
level (read-only, no filesystem sync).

The 4 states are:
    - ``in-sync``         — content hash matches the previous index snapshot
    - ``upstream-changed`` — content hash differs, no local modification marker
    - ``both-changed``     — content hash differs, local modification detected
    - ``local-missing``   — skill not present in the previous index (new skill)

The ``local-meta-only`` extra state from sync_legal_skills.py is collapsed
into ``in-sync`` (content matches, local metadata-only changes are not a
conflict at the index level).  The ``missing-upstream`` extra state is
omitted (skills that exist in the previous index but not in the current scan
are not classified here — they are handled at the index builder level).

CRITICAL: This module is READ-ONLY. It produces a report, it does NOT sync
files. No filesystem copy operations, no version-control checkout, no file
writes. The ``_detect_local_modification`` function only checks for marker
file existence — it never creates markers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .scanner import ScannedSkill

# Marker file names inherited from sync_legal_skills.py.
LOCAL_CHANGELOG_SUFFIX = "LOCAL_CHANGELOG.md"
LOCAL_MODIFICATION_MARKER = ".local_modification"

# The 4 valid conflict statuses.
STATUSES: tuple[str, ...] = (
    "in-sync",
    "upstream-changed",
    "both-changed",
    "local-missing",
)


@dataclass(frozen=True, slots=True)
class ConflictEntry:
    """A single skill's conflict classification entry.

    Attributes:
        skill_id: The skill's namespace-prefixed ID.
        status: One of ``"in-sync"``, ``"upstream-changed"``,
            ``"both-changed"``, ``"local-missing"``.
        content_hash: SHA-256 hash of the SKILL.md content (current scan).
        previous_hash: SHA-256 hash from the previous index (None if new).
        has_local_modification: Whether a local modification marker was detected.
        version: Version from frontmatter (if available).
    """

    skill_id: str
    status: str
    content_hash: str
    previous_hash: str | None
    has_local_modification: bool
    version: str | None


@dataclass(frozen=True, slots=True)
class MergeReport:
    """Merge report assembled from namespace mappings and conflict classification.

    Attributes:
        namespace_mappings: Mapping from original skill name to namespace-prefixed ID.
        conflict_classification: Dict with 4 keys (``"in-sync"``, ``"upstream-changed"``,
            ``"both-changed"``, ``"local-missing"``), each mapping to a list of skill_ids.
        total_skills: Total number of skills in the merge.
        summary: Count per status.
    """

    namespace_mappings: dict[str, str]
    conflict_classification: dict[str, list[str]]
    total_skills: int
    summary: dict[str, int]


def compute_content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of *text* encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_namespace_mappings(skills: list[ScannedSkill]) -> dict[str, str]:
    """Map each skill's raw ``name`` to its namespace-prefixed ``skill_id``.

    For legal-skills: ``{"court-sms": "legal-court-sms", ...}``
    For ai-for-china-legal: ``{"contract-review": "commercial-legal:contract-review", ...}``
    For shared: ``{"cn-law-research-gate": "shared:cn-law-research-gate"}``

    The ``legal-`` prefix quirk from ``sync_legal_skills.py`` is preserved:
    if a legal-skills skill name already starts with ``legal-``, the
    namespace ID doubles the prefix (e.g. ``legal-qa-extractor`` ->
    ``legal-legal-qa-extractor``). This matches the sync script's
    ``local_dir_name()`` behavior and is documented as a known quirk.
    """
    mappings: dict[str, str] = {}
    for skill in skills:
        mappings[skill.name] = skill.skill_id
    return mappings


def _detect_local_modification(skill: ScannedSkill) -> bool:
    """Check for local modification markers in the skill directory.

    Checks for:
        - A ``.local_modification`` marker file
        - A ``LOCAL_CHANGELOG.md`` file (inherited from sync_legal_skills.py)

    This is a READ-ONLY filesystem check — uses ``Path.exists()``, never
    creates files.
    """
    skill_dir = Path(skill.absolute_path).parent
    changelog = skill_dir / LOCAL_CHANGELOG_SUFFIX
    marker = skill_dir / LOCAL_MODIFICATION_MARKER
    return changelog.exists() or marker.exists()


def _build_previous_index_lookup(
    previous_index: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Build a skill_id -> record lookup from a previous index dict."""
    if previous_index is None:
        return {}
    skills_arr = previous_index.get("skills", [])
    if not isinstance(skills_arr, list):
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for record in skills_arr:
        if not isinstance(record, dict):
            continue
        sid = record.get("skill_id")
        if sid is not None:
            lookup[sid] = record
    return lookup


def classify_conflicts(
    current_skills: list[ScannedSkill],
    previous_index: dict[str, Any] | None = None,
) -> list[ConflictEntry]:
    """Classify each skill into one of 4 conflict states.

    Args:
        current_skills: Skills from the current scan.
        previous_index: Optional previous index snapshot dict with a ``skills``
            array. Each record should have ``skill_id``, ``content_hash``, and
            optionally ``has_local_modification``.

    Returns:
        A list of :class:`ConflictEntry` for all skills, in the same order as
        *current_skills*.
    """
    lookup = _build_previous_index_lookup(previous_index)
    entries: list[ConflictEntry] = []

    for skill in current_skills:
        content_hash = compute_content_hash(skill.raw_text)

        # Extract version from frontmatter if available.
        version: str | None = None
        if skill.frontmatter and "version" in skill.frontmatter:
            raw_version = skill.frontmatter.get("version")
            if raw_version is not None:
                version = str(raw_version)

        prev_record = lookup.get(skill.skill_id)

        if prev_record is None:
            # Skill not in previous index → new skill, auto-add.
            entries.append(
                ConflictEntry(
                    skill_id=skill.skill_id,
                    status="local-missing",
                    content_hash=content_hash,
                    previous_hash=None,
                    has_local_modification=_detect_local_modification(skill),
                    version=version,
                )
            )
            continue

        previous_hash = prev_record.get("content_hash")

        # Determine local modification status.
        # Prefer the previous index record's has_local_modification field;
        # fall back to filesystem detection if the field is absent.
        if "has_local_modification" in prev_record:
            has_local_mod = bool(prev_record.get("has_local_modification", False))
        else:
            has_local_mod = _detect_local_modification(skill)

        if content_hash == previous_hash:
            # Content matches → in-sync (local-meta-only is collapsed into in-sync).
            status = "in-sync"
        elif has_local_mod:
            # Content differs AND local modification detected → conflict.
            status = "both-changed"
        else:
            # Content differs, no local modification → upstream evolved.
            status = "upstream-changed"

        entries.append(
            ConflictEntry(
                skill_id=skill.skill_id,
                status=status,
                content_hash=content_hash,
                previous_hash=previous_hash,
                has_local_modification=has_local_mod,
                version=version,
            )
        )

    return entries


def build_merge_report(
    skills: list[ScannedSkill],
    previous_index: dict[str, Any] | None = None,
) -> MergeReport:
    """Assemble a :class:`MergeReport` from skills and an optional previous index.

    Args:
        skills: Skills from the current scan.
        previous_index: Optional previous index snapshot for conflict classification.

    Returns:
        A :class:`MergeReport` with namespace mappings, conflict classification
        (4 keys), total skill count, and per-status summary counts.
    """
    namespace_mappings = build_namespace_mappings(skills)
    entries = classify_conflicts(skills, previous_index)

    # Group skill_ids by status.
    conflict_classification: dict[str, list[str]] = {
        "in-sync": [],
        "upstream-changed": [],
        "both-changed": [],
        "local-missing": [],
    }
    for entry in entries:
        conflict_classification.setdefault(entry.status, []).append(entry.skill_id)

    # Compute summary counts.
    summary: dict[str, int] = {
        "in-sync": len(conflict_classification["in-sync"]),
        "upstream-changed": len(conflict_classification["upstream-changed"]),
        "both-changed": len(conflict_classification["both-changed"]),
        "local-missing": len(conflict_classification["local-missing"]),
    }

    return MergeReport(
        namespace_mappings=namespace_mappings,
        conflict_classification=conflict_classification,
        total_skills=len(skills),
        summary=summary,
    )


def _load_previous_index(path: Path) -> dict[str, Any] | None:
    """Load a previous index JSON file from *path*.

    Returns ``None`` if the file doesn't exist or is invalid JSON.
    The previous index is expected to have a ``skills`` array with records
    containing ``skill_id``, ``content_hash``, and optionally
    ``has_local_modification``.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (json.JSONDecodeError, PermissionError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data
