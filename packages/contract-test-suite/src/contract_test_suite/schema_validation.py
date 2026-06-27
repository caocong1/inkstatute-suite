"""Stdlib JSON Schema subset validation for Phase 1 platform contracts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import LOCAL_FIXTURE_ROOT, PLATFORM_FIXTURE_ROOT, PLATFORM_SCHEMA_ROOT


class ContractValidationError(AssertionError):
    """Raised when a fixture event does not satisfy its platform contract."""


EVENT_SCHEMA_BY_KEY = {
    "agent_turn": "agent_turn",
    "route_decision": "route_decision",
    "execution_trace": "execution_trace",
    "agent_result": "agent_result",
    "feedback_event": "feedback_event",
}

FORBIDDEN_TOP_LEVEL_FIELDS = {
    "case_type",
    "jurisdiction",
    "statute",
    "cause_of_action",
    "liability",
    "client_name",
    "id_number",
    "phone",
    "bank_account",
    "address",
    "raw_payload",
}

_RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schemas(schema_root: Path = PLATFORM_SCHEMA_ROOT) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_root.glob("*.schema.json")):
        schemas[path.name.removesuffix(".schema.json")] = load_json(path)
    return schemas


def load_contract_fixtures(
    platform_fixture_root: Path = PLATFORM_FIXTURE_ROOT,
    local_fixture_root: Path = LOCAL_FIXTURE_ROOT,
) -> list[dict[str, Any]]:
    roots = [platform_fixture_root]
    if local_fixture_root.exists():
        roots.append(local_fixture_root)

    fixtures: list[dict[str, Any]] = []
    for root in roots:
        fixtures.extend(load_json(path) for path in sorted(root.glob("*.json")))
    return fixtures


def validate_event(
    event_key: str,
    event: Any,
    schemas: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    fixture_id: str = "<unknown-fixture>",
) -> None:
    loaded_schemas = schemas if schemas is not None else load_schemas()
    schema_name = EVENT_SCHEMA_BY_KEY.get(event_key)
    if schema_name is None:
        raise ContractValidationError(f"{fixture_id}.{event_key}: unknown event key")
    if schema_name not in loaded_schemas:
        raise ContractValidationError(f"{fixture_id}.{event_key}: missing schema {schema_name}")

    _validate_schema(
        loaded_schemas[schema_name],
        event,
        loaded_schemas,
        path=(fixture_id, event_key),
        is_event_top_level=True,
    )


def validate_event_bundle(
    fixture: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    loaded_schemas = schemas if schemas is not None else load_schemas()
    fixture_id = _fixture_id(fixture)
    events = fixture.get("events")
    if not isinstance(events, dict):
        raise ContractValidationError(f"{fixture_id}: events must be object")

    extra_events = sorted(set(events) - set(EVENT_SCHEMA_BY_KEY))
    if extra_events:
        raise ContractValidationError(f"{fixture_id}.{extra_events[0]}: unknown event key")

    for event_key in EVENT_SCHEMA_BY_KEY:
        if event_key not in events:
            raise ContractValidationError(f"{fixture_id}.{event_key}: missing event")
        validate_event(event_key, events[event_key], loaded_schemas, fixture_id=fixture_id)


def _validate_schema(
    schema: Mapping[str, Any],
    value: Any,
    schemas: Mapping[str, Mapping[str, Any]],
    *,
    path: tuple[str, ...],
    is_event_top_level: bool = False,
) -> None:
    resolved = _resolve_schema(schema, schemas)

    if "oneOf" in resolved:
        _validate_one_of(resolved["oneOf"], value, schemas, path=path)
        return

    if "type" in resolved:
        _validate_type(resolved["type"], value, path)

    if resolved.get("format") == "date-time":
        _validate_date_time(value, path)

    if "enum" in resolved and value not in resolved["enum"]:
        allowed = ", ".join(repr(item) for item in resolved["enum"])
        raise ContractValidationError(f"{_path(path)}: value {value!r} not in enum [{allowed}]")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in resolved and value < resolved["minimum"]:
            raise ContractValidationError(f"{_path(path)}: value {value!r} below minimum {resolved['minimum']}")
        if "maximum" in resolved and value > resolved["maximum"]:
            raise ContractValidationError(f"{_path(path)}: value {value!r} above maximum {resolved['maximum']}")

    if isinstance(value, dict):
        _validate_object(resolved, value, schemas, path=path, is_event_top_level=is_event_top_level)
    elif isinstance(value, list):
        _validate_array(resolved, value, schemas, path=path)


def _validate_object(
    schema: Mapping[str, Any],
    value: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]],
    *,
    path: tuple[str, ...],
    is_event_top_level: bool,
) -> None:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    if is_event_top_level:
        forbidden = sorted(set(value) & FORBIDDEN_TOP_LEVEL_FIELDS)
        if forbidden:
            raise ContractValidationError(
                f"{_path(path)}.{forbidden[0]}: forbidden top-level field"
            )

    for field_name in schema.get("required", []):
        if field_name not in value:
            raise ContractValidationError(f"{_path(path)}: missing required field {field_name}")

    extra_fields = sorted(set(value) - set(properties))
    if schema.get("additionalProperties") is False and extra_fields:
        raise ContractValidationError(
            f"{_path(path)}.{extra_fields[0]}: additionalProperties false rejected field"
        )

    for field_name, field_value in value.items():
        field_schema = properties.get(field_name)
        if isinstance(field_schema, dict):
            _validate_schema(field_schema, field_value, schemas, path=path + (field_name,))


def _validate_array(
    schema: Mapping[str, Any],
    value: list[Any],
    schemas: Mapping[str, Mapping[str, Any]],
    *,
    path: tuple[str, ...],
) -> None:
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        return

    for index, item in enumerate(value):
        _validate_schema(items_schema, item, schemas, path=path[:-1] + (f"{path[-1]}[{index}]",))


def _validate_one_of(
    options: list[Mapping[str, Any]],
    value: Any,
    schemas: Mapping[str, Mapping[str, Any]],
    *,
    path: tuple[str, ...],
) -> None:
    failures: list[str] = []
    matches = 0
    for option in options:
        try:
            _validate_schema(option, value, schemas, path=path)
        except ContractValidationError as exc:
            failures.append(str(exc))
        else:
            matches += 1

    if matches != 1:
        if matches == 0:
            detail = "; ".join(failures)
            raise ContractValidationError(f"{_path(path)}: oneOf matched no schemas ({detail})")
        raise ContractValidationError(f"{_path(path)}: oneOf matched {matches} schemas")


def _validate_type(expected: str | list[str], value: Any, path: tuple[str, ...]) -> None:
    expected_types = [expected] if isinstance(expected, str) else list(expected)
    if any(_matches_type(type_name, value) for type_name in expected_types):
        return

    expected_text = " or ".join(expected_types)
    raise ContractValidationError(f"{_path(path)}: expected type {expected_text}, got {_type_name(value)}")


def _validate_date_time(value: Any, path: tuple[str, ...]) -> None:
    if not isinstance(value, str):
        return

    if not _RFC3339_DATE_TIME.fullmatch(value):
        raise ContractValidationError(f"{_path(path)}: invalid date-time format")

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(f"{_path(path)}: invalid date-time format") from exc


def _matches_type(type_name: str, value: Any) -> bool:
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    raise ContractValidationError(f"unsupported JSON Schema type {type_name!r}")


def _resolve_schema(
    schema: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema

    if ref.startswith("#/$defs/"):
        return _resolve_schema(_resolve_pointer(schemas["common"], ref.removeprefix("#")), schemas)

    if "#" in ref:
        file_name, pointer = ref.split("#", 1)
    else:
        file_name, pointer = ref, ""

    schema_name = file_name.removesuffix(".schema.json")
    if schema_name not in schemas:
        raise ContractValidationError(f"missing referenced schema {ref}")

    target: Mapping[str, Any] = schemas[schema_name]
    if pointer:
        target = _resolve_pointer(target, pointer)
    return _resolve_schema(target, schemas)


def _resolve_pointer(schema: Mapping[str, Any], pointer: str) -> Mapping[str, Any]:
    if not pointer.startswith("/"):
        raise ContractValidationError(f"unsupported JSON pointer {pointer!r}")

    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        current = current[part]
    if not isinstance(current, Mapping):
        raise ContractValidationError(f"JSON pointer {pointer!r} did not resolve to schema object")
    return current


def _fixture_id(fixture: Mapping[str, Any]) -> str:
    value = fixture.get("fixture_id", "<unknown-fixture>")
    return value if isinstance(value, str) else "<unknown-fixture>"


def _path(parts: tuple[str, ...]) -> str:
    return ".".join(parts)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
