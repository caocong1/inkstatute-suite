"""Stdlib self-checks for platform contract schemas, bindings, and fixtures."""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import fields, is_dataclass


PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_ROOT = PACKAGE_ROOT / "src" / "platform_contract" / "schemas"
FIXTURE_ROOT = PACKAGE_ROOT / "fixtures"

EVENT_SCHEMA_BY_KEY = {
    "agent_turn": "agent_turn",
    "route_decision": "route_decision",
    "execution_trace": "execution_trace",
    "agent_result": "agent_result",
    "feedback_event": "feedback_event",
}
CORE_SCHEMA_NAMES = set(EVENT_SCHEMA_BY_KEY.values()) | {"common"}
NEW_STANDALONE_SCHEMA_NAMES = {
    "approval",
    "artifact_record",
    "bot_instance",
    "channel_binding",
    "channel_delivery",
    "channel_message",
    "run",
    "run_event",
    "run_step",
    "session",
    "solution_package_manifest",
    "tenant",
    "tool_call",
    "workspace",
}

FORBIDDEN_REQUIRED_FIELDS = {
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


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def load_schemas():
    schemas = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        name = path.name.removesuffix(".schema.json")
        schemas[name] = load_json(path)
    return schemas


def load_fixtures():
    return [load_json(path) for path in sorted(FIXTURE_ROOT.glob("*.json"))]


def assert_schema_shape(schemas):
    missing = CORE_SCHEMA_NAMES - set(schemas)
    if missing:
        raise AssertionError(f"Missing core schemas {sorted(missing)} from {sorted(schemas)}")

    for name, schema in schemas.items():
        _assert_equal(schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema", f"{name} $schema")
        if "$id" not in schema:
            raise AssertionError(f"{name} missing $id")
        _assert_equal(schema.get("type"), "object", f"{name} type")

        if name == "common":
            if "$defs" not in schema:
                raise AssertionError("common missing $defs")
            continue

        if not isinstance(schema.get("properties"), dict):
            raise AssertionError(f"{name} missing properties")
        if not isinstance(schema.get("required"), list):
            raise AssertionError(f"{name} missing required")


def assert_fixture_required_fields(schemas, fixtures):
    if not fixtures:
        raise AssertionError("No fixtures found")

    for fixture in fixtures:
        events = fixture.get("events")
        if not isinstance(events, dict):
            raise AssertionError(f"{fixture.get('fixture_id')} missing events object")
        missing_events = set(EVENT_SCHEMA_BY_KEY) - set(events)
        if missing_events:
            raise AssertionError(f"{fixture.get('fixture_id')} missing events: {sorted(missing_events)}")

        for event_key, schema_name in EVENT_SCHEMA_BY_KEY.items():
            _assert_required_and_enums(
                schemas[schema_name],
                events[event_key],
                schemas,
                f"{fixture['fixture_id']}.{event_key}",
                is_event_top_level=True,
            )


def assert_fixture_relationships(fixtures):
    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        events = fixture["events"]
        agent_turn = events["agent_turn"]
        route_decision = events["route_decision"]
        execution_trace = events["execution_trace"]
        agent_result = events["agent_result"]
        feedback_event = events["feedback_event"]

        turn_id = agent_turn["turn_id"]
        for name, event in events.items():
            _assert_equal(event.get("turn_id"), turn_id, f"{fixture_id}.{name}.turn_id")

        _assert_equal(
            feedback_event.get("conversation_id"),
            agent_turn.get("conversation_id"),
            f"{fixture_id}.feedback_event.conversation_id",
        )
        _assert_equal(
            feedback_event.get("result_id"),
            agent_result.get("result_id"),
            f"{fixture_id}.feedback_event.result_id",
        )
        _assert_equal(
            feedback_event.get("feedback_target"),
            agent_result.get("feedback_target"),
            f"{fixture_id}.feedback_event.feedback_target",
        )
        _assert_equal(
            feedback_event.get("related_route_decision"),
            route_decision.get("route_decision_id"),
            f"{fixture_id}.feedback_event.related_route_decision",
        )

        artifact_ids = {artifact["artifact_id"] for artifact in agent_result.get("artifacts", [])}
        written_ids = set(execution_trace.get("artifacts_written", []))
        if not artifact_ids:
            raise AssertionError(f"{fixture_id} has no AgentResult artifacts")
        if not artifact_ids <= written_ids:
            raise AssertionError(
                f"{fixture_id} artifacts not written by trace: {sorted(artifact_ids - written_ids)}"
            )

        trace_route = execution_trace.get("route_decision")
        if trace_route is not None:
            _assert_equal(
                trace_route.get("route_decision_id"),
                route_decision.get("route_decision_id"),
                f"{fixture_id}.execution_trace.route_decision_id",
            )


def assert_no_legal_top_level_required(schemas):
    for name, schema in schemas.items():
        required = set(schema.get("required", []))
        forbidden = required & FORBIDDEN_REQUIRED_FIELDS
        if forbidden:
            raise AssertionError(f"{name} has forbidden top-level required fields: {sorted(forbidden)}")


def main():
    schemas = load_schemas()
    fixtures = load_fixtures()

    assert_schema_shape(schemas)
    assert_no_legal_top_level_required(schemas)
    assert_fixture_required_fields(schemas, fixtures)
    assert_fixture_relationships(fixtures)
    _assert_python_bindings_compile()
    assert_python_binding_schema_parity(schemas)

    print("platform-contract self-check passed")
    return 0


def _assert_python_bindings_compile():
    import platform_contract

    expected_dataclasses = [
        platform_contract.AgentTurn,
        platform_contract.RouteDecision,
        platform_contract.ExecutionTrace,
        platform_contract.AgentResult,
        platform_contract.FeedbackEvent,
        platform_contract.ChannelMessage,
        platform_contract.ChannelDelivery,
        platform_contract.Run,
        platform_contract.RunEvent,
        platform_contract.RunStep,
        platform_contract.ToolCall,
        platform_contract.Approval,
        platform_contract.ArtifactRecord,
        platform_contract.Session,
        platform_contract.Tenant,
        platform_contract.Workspace,
        platform_contract.SolutionPackageManifest,
        platform_contract.SolutionBinding,
        platform_contract.NeutralSkillDescriptor,
        platform_contract.McpServerDescriptor,
        platform_contract.BotInstance,
        platform_contract.ChannelBinding,
    ]
    for cls in expected_dataclasses:
        if not is_dataclass(cls):
            raise AssertionError(f"{cls.__name__} is not a dataclass")
        if not fields(cls):
            raise AssertionError(f"{cls.__name__} has no dataclass fields")


def assert_python_binding_schema_parity(schemas):
    import platform_contract

    event_pairs = {
        "agent_turn": platform_contract.AgentTurn,
        "agent_result": platform_contract.AgentResult,
        "feedback_event": platform_contract.FeedbackEvent,
        "execution_trace": platform_contract.ExecutionTrace,
        "route_decision": platform_contract.RouteDecision,
        "channel_message": platform_contract.ChannelMessage,
        "channel_delivery": platform_contract.ChannelDelivery,
        "run": platform_contract.Run,
        "run_event": platform_contract.RunEvent,
        "run_step": platform_contract.RunStep,
        "tool_call": platform_contract.ToolCall,
        "approval": platform_contract.Approval,
        "artifact_record": platform_contract.ArtifactRecord,
        "session": platform_contract.Session,
        "tenant": platform_contract.Tenant,
        "workspace": platform_contract.Workspace,
        "solution_package_manifest": platform_contract.SolutionPackageManifest,
        "bot_instance": platform_contract.BotInstance,
        "channel_binding": platform_contract.ChannelBinding,
    }
    common_pairs = {
        "attachment_ref": platform_contract.AttachmentRef,
        "output_constraints": platform_contract.OutputConstraints,
        "artifact": platform_contract.Artifact,
        "skill_candidate": platform_contract.SkillCandidate,
        "error_info": platform_contract.ErrorInfo,
        "solution_binding": platform_contract.SolutionBinding,
        "neutral_skill_descriptor": platform_contract.NeutralSkillDescriptor,
        "mcp_server_descriptor": platform_contract.McpServerDescriptor,
    }

    for schema_name, cls in event_pairs.items():
        _assert_field_parity(schema_name, schemas[schema_name], cls)

    common_defs = schemas["common"]["$defs"]
    for schema_name, cls in common_pairs.items():
        _assert_field_parity(schema_name, common_defs[schema_name], cls)


def _assert_field_parity(schema_name, schema, cls):
    schema_fields = set(schema.get("properties", {}))
    binding_fields = {field.name for field in fields(cls)}
    if schema_fields != binding_fields:
        raise AssertionError(
            f"{schema_name} schema/binding mismatch: "
            f"schema_only={sorted(schema_fields - binding_fields)}, "
            f"binding_only={sorted(binding_fields - schema_fields)}"
        )


def _assert_required_and_enums(schema, value, schemas, context, *, is_event_top_level=False):
    if not isinstance(value, dict):
        raise AssertionError(f"{context} must be an object")

    properties = schema.get("properties", {})
    forbidden = set(value) & FORBIDDEN_REQUIRED_FIELDS
    if is_event_top_level and forbidden:
        raise AssertionError(f"{context} has forbidden top-level fields: {sorted(forbidden)}")

    extra_fields = set(value) - set(properties)
    if schema.get("additionalProperties") is False and extra_fields:
        raise AssertionError(f"{context} has unsupported fields: {sorted(extra_fields)}")

    for field_name in schema.get("required", []):
        if field_name not in value:
            raise AssertionError(f"{context} missing required field {field_name}")

    for field_name, field_value in value.items():
        field_schema = properties.get(field_name)
        if field_schema is None:
            continue
        _assert_value_enums(field_schema, field_value, schemas, f"{context}.{field_name}")


def _assert_value_enums(schema, value, schemas, context):
    resolved = _resolve_schema(schema, schemas)
    if "enum" in resolved:
        if value not in resolved["enum"]:
            raise AssertionError(f"{context}={value!r} not in enum {resolved['enum']}")
        return

    if isinstance(value, dict):
        if "oneOf" in resolved:
            _assert_matches_one_schema(resolved["oneOf"], value, schemas, context)
            return
        _assert_required_and_enums(resolved, value, schemas, context)
        return

    if isinstance(value, list):
        item_schema = resolved.get("items")
        if item_schema is None:
            return
        for index, item in enumerate(value):
            _assert_value_enums(item_schema, item, schemas, f"{context}[{index}]")


def _assert_matches_one_schema(options, value, schemas, context):
    errors = []
    for option in options:
        resolved = _resolve_schema(option, schemas)
        if resolved.get("type") == "null":
            continue
        try:
            _assert_value_enums(resolved, value, schemas, context)
        except AssertionError as exc:
            errors.append(str(exc))
        else:
            return
    raise AssertionError(f"{context} did not match any oneOf schema: {errors}")


def _resolve_schema(schema, schemas):
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if not ref:
        return schema

    if ref.startswith("common.schema.json#/$defs/"):
        def_name = ref.rsplit("/", 1)[1]
        return schemas["common"]["$defs"][def_name]
    if ref.startswith("#/$defs/"):
        def_name = ref.rsplit("/", 1)[1]
        return schemas["common"]["$defs"][def_name]
    if ref.endswith(".schema.json"):
        schema_name = ref.removesuffix(".schema.json")
        return schemas[schema_name]
    raise AssertionError(f"Unsupported schema reference: {ref}")


def _assert_equal(actual, expected, context):
    if actual != expected:
        raise AssertionError(f"{context}: expected {expected!r}, got {actual!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"platform-contract self-check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
