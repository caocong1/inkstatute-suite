"""Cloudflare agent-skills-discovery index builder (RFC v0.2.0).

Builds the ``/.well-known/agent-skills/index.json`` payload from a list of
:class:`NeutralSkillDescriptor` records.  Each entry follows the RFC v0.2.0
format with ``name``, ``type``, ``description``, ``url``, and ``digest``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from platform_contract import NeutralSkillDescriptor

SCHEMA_URI = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"

_MAX_DESCRIPTION_LEN = 1024


def build_discovery_index(
    skills: list[NeutralSkillDescriptor],
) -> dict[str, Any]:
    """Build the discovery index dict from a list of skill descriptors.

    Returns a dict with two top-level keys:

    - ``$schema`` — the RFC v0.2.0 schema URI.
    - ``skills`` — a list of entry dicts, each with ``name``, ``type``,
      ``description``, ``url``, and ``digest``.
    """
    entries: list[dict[str, Any]] = []
    for skill in skills:
        canonical = json.dumps(
            _descriptor_to_dict(skill), sort_keys=True
        ).encode("utf-8")
        digest_hex = hashlib.sha256(canonical).hexdigest()
        normalized_name = _normalize_skill_name(skill.name)
        entries.append(
            {
                "name": normalized_name,
                "type": "skill-md",
                "description": (skill.description or "")[:_MAX_DESCRIPTION_LEN],
                "url": f"/.well-known/agent-skills/{normalized_name}/SKILL.md",
                "digest": f"sha256:{digest_hex}",
            }
        )
    return {"$schema": SCHEMA_URI, "skills": entries}


def _normalize_skill_name(name: str) -> str:
    """Convert a skill name to the agent-skills naming convention.

    Underscores are replaced with hyphens and the result is lowercased
    (e.g., ``case_qa`` -> ``case-qa``).
    """
    return name.replace("_", "-").lower()


def _descriptor_to_dict(skill: NeutralSkillDescriptor) -> dict[str, Any]:
    """Serialize a :class:`NeutralSkillDescriptor` to a plain dict.

    The keys are ``skill_id``, ``name``, ``description``,
    ``input_schema_ref``, ``output_schema_ref``, ``required_tool_refs``,
    and ``metadata``.
    """
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "description": skill.description,
        "input_schema_ref": skill.input_schema_ref,
        "output_schema_ref": skill.output_schema_ref,
        "required_tool_refs": list(skill.required_tool_refs),
        "metadata": dict(skill.metadata),
    }


__all__ = [
    "SCHEMA_URI",
    "build_discovery_index",
]
