"""Manifest-to-descriptor mapper for the Skill Registry.

Converts solution-pack manifest skill dicts into ``NeutralSkillDescriptor``
records.  The ``skill_id`` is derived as ``{solution_id}/{name}`` to ensure
uniqueness across solution packs.

Phase 97 adds :func:`index_to_descriptors` which consumes a real
``skill-index.json`` (produced by ``packages/skill-index``) and converts
each ``IndexRecord`` to a ``NeutralSkillDescriptor``.  This is the new
primary skill source for the lawfirm solution, replacing the manifest-based
fake data.  The existing :func:`load_skills_from_manifests` remains for
backward compatibility (``demo_non_legal`` still uses it).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from platform_contract import NeutralSkillDescriptor

_logger = logging.getLogger(__name__)


def manifest_skill_to_descriptor(
    solution_id: str,
    skill: Mapping[str, Any],
) -> NeutralSkillDescriptor:
    """Convert a manifest skill dict to a :class:`NeutralSkillDescriptor`.

    Field mapping:

    - ``name`` → ``skill_id`` (prefixed as ``{solution_id}/{name}``) and ``name``
    - ``description`` → ``description``
    - ``required_tools`` → ``required_tool_refs``
    - ``intent`` → ``metadata.intent``
    - ``risk_level`` → ``metadata.risk_level``
    - ``solution_id`` → ``metadata.solution_id``
    - ``input_schema_ref`` / ``output_schema_ref`` default to ``None``
    """
    name = str(skill.get("name", ""))
    skill_id = f"{solution_id}/{name}"
    return NeutralSkillDescriptor(
        skill_id=skill_id,
        name=name,
        description=skill.get("description"),
        required_tool_refs=list(skill.get("required_tools", [])),
        metadata={
            "intent": skill.get("intent"),
            "risk_level": skill.get("risk_level"),
            "solution_id": solution_id,
        },
    )


def load_skills_from_manifests(
    manifest_paths: list[Path],
) -> list[NeutralSkillDescriptor]:
    """Load skills from multiple solution-pack manifest JSON files.

    Each manifest is read as JSON.  The ``solution_id`` is taken from
    ``data["solution_id"]`` or falls back to the parent directory name.
    Skills are iterated from ``data["skills"]`` and converted via
    :func:`manifest_skill_to_descriptor`.
    """
    skills: list[NeutralSkillDescriptor] = []
    for path in manifest_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        solution_id = data.get("solution_id", path.parent.name)
        for skill in data.get("skills", []):
            skills.append(manifest_skill_to_descriptor(solution_id, skill))
    return skills


def index_to_descriptors(
    skill_index_path: str | Path,
) -> list[NeutralSkillDescriptor]:
    """Convert a ``skill-index.json`` file into ``NeutralSkillDescriptor`` records.

    This is the Phase 97 primary skill source.  It reads a JSON file produced
    by ``packages/skill-index`` (``serialize_index`` / ``write_index``) and
    converts each serialized ``IndexRecord`` dict into a
    :class:`NeutralSkillDescriptor`.

    Field mapping (three-separation: metadata only, no body text):

    - ``IndexRecord.skill_id`` → ``NeutralSkillDescriptor.skill_id``
    - ``IndexRecord.name`` → ``NeutralSkillDescriptor.name``
    - ``IndexRecord.description`` → ``NeutralSkillDescriptor.description``
    - ``IndexRecord.required_scripts`` → ``NeutralSkillDescriptor.required_tool_refs``
    - Metadata dict includes: ``token_estimate``, ``declared_gates``,
      ``host_assumptions``, ``skill_type``, ``parent_skill``, ``source_repo``,
      ``plugin``

    No ``frontmatter`` raw content or body text is included in the descriptor
    (three-separation: metadata only).

    Args:
        skill_index_path: Path to a ``skill-index.json`` file.

    Returns:
        A list of :class:`NeutralSkillDescriptor` records.  Returns an empty
        list if the index is empty or the ``skills`` key is missing (with a
        warning logged).
    """
    path = Path(skill_index_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    raw_skills = data.get("skills")
    if raw_skills is None:
        _logger.warning(
            "skill-index.json at %s has no 'skills' key; returning empty list",
            path,
        )
        return []
    if not isinstance(raw_skills, list):
        _logger.warning(
            "skill-index.json at %s has non-list 'skills' key; returning empty list",
            path,
        )
        return []

    descriptors: list[NeutralSkillDescriptor] = []
    for record in raw_skills:
        descriptors.append(_index_record_to_descriptor(record))
    return descriptors


def _index_record_to_descriptor(record: Mapping[str, Any]) -> NeutralSkillDescriptor:
    """Convert a single serialized ``IndexRecord`` dict to a descriptor.

    Only metadata-level fields are mapped.  No body text, ``frontmatter`` raw
    content, ``raw_text``, or ``content`` fields are included — this enforces
    the three-separation principle (metadata / body / tools).
    """
    return NeutralSkillDescriptor(
        skill_id=str(record.get("skill_id", "")),
        name=str(record.get("name", "")),
        description=record.get("description"),
        required_tool_refs=list(record.get("required_scripts", [])),
        metadata={
            "token_estimate": record.get("token_estimate"),
            "declared_gates": list(record.get("declared_gates", [])),
            "host_assumptions": list(record.get("host_assumptions", [])),
            "skill_type": record.get("skill_type"),
            "parent_skill": record.get("parent_skill"),
            "source_repo": record.get("source_repo"),
            "plugin": record.get("plugin"),
        },
    )
