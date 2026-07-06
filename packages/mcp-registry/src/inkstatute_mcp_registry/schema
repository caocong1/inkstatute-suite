"""JSON Schema tool schema validator for MCP connector registration.

Provides basic structural validation of tool schemas at registration
time.  No external JSON Schema library is imported — validation checks
required fields and types only.
"""

from __future__ import annotations

from typing import Any


def validate_tool_schema(schema: Any) -> list[str]:
    """Validate a single tool schema dict.

    Returns a list of validation error messages (empty = valid).
    A valid tool schema must have:
    - ``name`` (str) — required
    - ``input_schema`` (dict with ``type`` key) — required
    - ``description`` (str) — optional
    """
    errors: list[str] = []
    if not isinstance(schema, dict):
        errors.append("tool schema must be a dict")
        return errors
    if "name" not in schema:
        errors.append("tool schema missing required field: name")
    elif not isinstance(schema["name"], str):
        errors.append("tool schema field 'name' must be a str")
    if "input_schema" not in schema:
        errors.append("tool schema missing required field: input_schema")
    elif not isinstance(schema["input_schema"], dict):
        errors.append("tool schema field 'input_schema' must be a dict")
    elif "type" not in schema["input_schema"]:
        errors.append("input_schema missing required field: type")
    return errors


def validate_tool_schemas(schemas: list[Any]) -> list[str]:
    """Validate a list of tool schemas.

    Returns an aggregated list of validation error messages (empty = all valid).
    """
    errors: list[str] = []
    for i, schema in enumerate(schemas):
        schema_errors = validate_tool_schema(schema)
        for err in schema_errors:
            errors.append(f"tool[{i}]: {err}")
    return errors


__all__ = [
    "validate_tool_schema",
    "validate_tool_schemas",
]
