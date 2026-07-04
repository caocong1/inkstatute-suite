"""Pure GET route handler for the Skill Registry API.

Follows the ``conversation-read-view`` pattern: a pure ``handle_get``
function that returns ``(status_code, body)`` tuples.  No FastAPI/aiohttp
dependency — the handler is tested via ``unittest``.

Routes:

- ``GET /.well-known/agent-skills/index.json`` — Cloudflare discovery index.
- ``GET /skills`` — list all skills.
- ``GET /skills/search`` — search skills by tag/category/name.
- ``GET /skills/{skill_id}`` — get a single skill by ID.

Read-only enforcement is structural: only ``handle_get`` is exported.
No ``handle_post``, ``handle_put``, ``handle_delete``, or ``handle_patch``
functions exist.

Feature flag: when ``flags`` is provided, ``skill_registry_enabled`` is
checked before processing.  The flag defaults to ``False`` (default-off).
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qs

from platform_contract import NeutralSkillDescriptor
from platform_runtime import RuntimeFeatureFlags

from .discovery import build_discovery_index
from .registry import SkillRegistry


def handle_get(
    path: str,
    query: str | Mapping[str, str] | None,
    registry: SkillRegistry,
    flags: RuntimeFeatureFlags | None = None,
) -> tuple[int, dict[str, Any]]:
    """Pure route handler for Skill Registry GET endpoints.

    If *flags* is not ``None``, ``flags.require_enabled("skill_registry_enabled")``
    is called before processing.  This raises
    :class:`RuntimeFeatureDisabledError` when the flag is disabled (default-off).
    """
    if flags is not None:
        flags.require_enabled("skill_registry_enabled")

    route_path, route_query = _split_path_query(path, query)

    # SKILL-02: Cloudflare agent-skills-discovery endpoint
    if route_path == "/.well-known/agent-skills/index.json":
        index = build_discovery_index(registry.list_skills())
        return 200, index

    # SKILL-01: list all skills
    if route_path == "/skills":
        skills = registry.list_skills()
        return 200, {
            "items": [_descriptor_to_dict(s) for s in skills],
            "count": len(skills),
            "metadata": {
                "read_only": True,
                "source": "solution_pack_manifests",
            },
        }

    # SKILL-01: search skills (must be checked before /skills/{skill_id})
    if route_path == "/skills/search":
        tag = route_query.get("tag")
        category = route_query.get("category")
        name = route_query.get("name")
        results = registry.search(
            tag=tag, category=category, name_substring=name
        )
        return 200, {
            "items": [_descriptor_to_dict(s) for s in results],
            "count": len(results),
            "metadata": {
                "read_only": True,
                "filters": {"tag": tag, "category": category, "name": name},
            },
        }

    # SKILL-01: get single skill by ID
    if route_path.startswith("/skills/"):
        skill_id = route_path.removeprefix("/skills/")
        skill = registry.get_skill(skill_id)
        if skill is None:
            return 404, _not_found("skill", skill_id)
        return 200, _descriptor_to_dict(skill)

    return 404, _not_found("route", route_path)


def parse_query_string(query: str | Mapping[str, str] | None) -> dict[str, str]:
    """Parse a query string or mapping into a flat dict."""
    if query is None:
        return {}
    if isinstance(query, Mapping):
        return {str(key): str(value) for key, value in query.items()}
    parsed = parse_qs(query.lstrip("?"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _split_path_query(
    path: str, query: str | Mapping[str, str] | None
) -> tuple[str, dict[str, str]]:
    """Split *path* on ``?`` and merge inline + separate query params."""
    if "?" in path:
        route_path, inline_query = path.split("?", 1)
        merged = parse_query_string(inline_query)
        merged.update(parse_query_string(query))
        return route_path, merged
    return path, parse_query_string(query)


def _not_found(resource: str, identifier: str) -> dict[str, Any]:
    """Build a standard 404 response body."""
    return {
        "error": {
            "code": "not_found",
            "resource": resource,
            "identifier": identifier,
        },
        "metadata": {"read_only": True},
    }


def _descriptor_to_dict(skill: NeutralSkillDescriptor) -> dict[str, Any]:
    """Serialize a :class:`NeutralSkillDescriptor` to a plain dict."""
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
    "handle_get",
    "parse_query_string",
]
