"""YAML frontmatter extraction and validation with graceful degradation.

Parses YAML frontmatter from SKILL.md files. Handles both the minimal
ai-for-china-legal schema (name, description, argument-hint) and the rich
legal-skills schema (name, version, license, author, homepage, description).

The parser never raises an exception on malformed input — it always returns
a ``FrontmatterResult`` with warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class FrontmatterResult:
    """Result of parsing frontmatter from a SKILL.md file.

    Attributes:
        frontmatter: Parsed YAML dict (empty dict if no frontmatter).
        body: The markdown body after frontmatter (full file content if no frontmatter).
        raw_text: The full file content.
        warnings: List of warning strings (e.g. "missing_frontmatter", "malformed_frontmatter").
    """

    frontmatter: dict[str, Any]
    body: str
    raw_text: str
    warnings: list[str] = field(default_factory=list)


def parse_frontmatter(text: str) -> FrontmatterResult:
    """Extract and parse YAML frontmatter from *text*.

    Handles BOM, missing frontmatter, and malformed YAML gracefully.
    Never raises an exception.
    """
    # Strip BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]

    raw_text = text

    # Check for frontmatter start
    if not text.startswith("---\n"):
        return FrontmatterResult(
            frontmatter={},
            body=text,
            raw_text=text,
            warnings=["missing_frontmatter"],
        )

    # Find the closing --- delimiter (second occurrence of a line that is exactly ---)
    lines = text.split("\n")
    # First line is "---", find the next line that is exactly "---"
    closing_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_index = i
            break

    if closing_index is None:
        # No closing delimiter found
        return FrontmatterResult(
            frontmatter={},
            body=text,
            raw_text=text,
            warnings=["malformed_frontmatter"],
        )

    yaml_block = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return FrontmatterResult(
            frontmatter={},
            body=body,
            raw_text=text,
            warnings=["malformed_frontmatter"],
        )

    if parsed is None:
        parsed = {}

    if not isinstance(parsed, dict):
        return FrontmatterResult(
            frontmatter={},
            body=body,
            raw_text=text,
            warnings=["malformed_frontmatter"],
        )

    warnings: list[str] = []
    if "name" not in parsed:
        warnings.append("missing_name_field")

    return FrontmatterResult(
        frontmatter=parsed,
        body=body,
        raw_text=text,
        warnings=warnings,
    )


def extract_name(frontmatter: dict[str, Any], fallback: str | None = None) -> str | None:
    """Return the skill name from *frontmatter*, falling back to *fallback*."""
    name = frontmatter.get("name")
    if name is not None:
        return str(name)
    return fallback


def extract_description(frontmatter: dict[str, Any]) -> str | None:
    """Return the description from *frontmatter* (handles folded scalar and inline)."""
    desc = frontmatter.get("description")
    if desc is not None:
        return str(desc)
    return None


def extract_version(frontmatter: dict[str, Any]) -> str | None:
    """Return the version as a string from *frontmatter*.

    Handles quoted strings that pyyaml may parse as float.
    """
    version = frontmatter.get("version")
    if version is not None:
        return str(version)
    return None


def extract_license(frontmatter: dict[str, Any]) -> str | None:
    """Return the license from *frontmatter* (None for ai-for-china-legal skills)."""
    lic = frontmatter.get("license")
    if lic is not None:
        return str(lic)
    return None
