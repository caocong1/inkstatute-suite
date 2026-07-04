"""Manifest-to-descriptor mapper for the Skill Registry.

Converts solution-pack manifest skill dicts into ``NeutralSkillDescriptor``
records.  The ``skill_id`` is derived as ``{solution_id}/{name}`` to ensure
uniqueness across solution packs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from platform_contract import NeutralSkillDescriptor


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
