"""Three-separation routing manifest producer.

Given a ``skill-index.json``, produces a metadata-only routing manifest (JSON)
containing only index-level fields needed for routing. No skill body text is
included. This enforces the metadata/body/tools separation principle.

The routing manifest contains per-skill records with:
- ``skill_id`` — unique skill identifier
- ``name`` — skill name
- ``description`` — short description (from frontmatter)
- ``token_estimate`` — estimated token count for budget enforcement
- ``declared_gates`` — legal guardrails referenced by this skill
- ``host_assumptions`` — trigger patterns and argument-hint assumptions
- ``required_scripts`` — script paths referenced or present on disk
- ``source_path`` — absolute path to the SKILL.md in the source repo
- ``skill_type`` — "orchestration" or "leaf"
- ``parent_skill`` — parent skill ID (for sub-skills)

No ``body``, ``raw_text``, ``frontmatter`` raw content, or any ``content``
field is included. The router consumes this manifest for routing decisions
without ever loading skill bodies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hermes_materializer import _load_index, _resolve_source_dir


# ---------------------------------------------------------------------------
# Fields included in the routing manifest (metadata only)
# ---------------------------------------------------------------------------

_ROUTING_FIELDS: tuple[str, ...] = (
    "skill_id",
    "name",
    "description",
    "token_estimate",
    "declared_gates",
    "host_assumptions",
    "required_scripts",
    "skill_type",
    "parent_skill",
)

# Fields explicitly EXCLUDED (body / content)
_EXCLUDED_FIELDS: frozenset[str] = frozenset({
    "frontmatter",
    "raw_text",
    "body",
    "content",
    "content_hash",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def produce_routing_manifest(
    index_path: str | Path,
    output_path: str | Path,
) -> None:
    """Produce a metadata-only routing manifest from a skill-index.json.

    Reads ``skill-index.json``, extracts only routing-relevant metadata fields,
    and writes a JSON manifest to *output_path*. No skill body text is included.

    Args:
        index_path: Path to ``skill-index.json``.
        output_path: Path to write the routing manifest JSON.
    """
    index_data = _load_index(index_path)
    repos = index_data.get("repos", {})
    skills = index_data.get("skills", [])

    routing_records: list[dict[str, Any]] = []

    for record in skills:
        # Resolve source path (absolute path to SKILL.md in source repo)
        try:
            source_dir = _resolve_source_dir(record, repos)
            source_path = str(source_dir / "SKILL.md")
        except (KeyError, FileNotFoundError):
            source_path = ""

        routing_record: dict[str, Any] = {}

        # Include only routing-relevant fields
        for field_name in _ROUTING_FIELDS:
            if field_name in record:
                value = record[field_name]
                # Copy lists to avoid mutation
                if isinstance(value, list):
                    routing_record[field_name] = list(value)
                else:
                    routing_record[field_name] = value

        # Add source_path (absolute path for on-demand body reading)
        routing_record["source_path"] = source_path

        # Verify no excluded fields are present
        for excluded in _EXCLUDED_FIELDS:
            if excluded in routing_record:
                # This should never happen given _ROUTING_FIELDS, but assert
                raise AssertionError(
                    f"Excluded field '{excluded}' found in routing record "
                    f"for skill '{record.get('skill_id', '?')}'"
                )

        routing_records.append(routing_record)

    manifest: dict[str, Any] = {
        "manifest_type": "routing",
        "version": "1.0.0",
        "generated_at": index_data.get("generated_at", ""),
        "scanner_version": index_data.get("scanner_version", ""),
        "skill_count": len(routing_records),
        "skills": routing_records,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
