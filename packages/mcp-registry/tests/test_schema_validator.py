"""Tests for JSON Schema tool schema validator."""

from __future__ import annotations

import unittest

from inkstatute_mcp_registry.schema_validator import (
    validate_tool_schema,
    validate_tool_schemas,
)


class ValidateToolSchemaTests(unittest.TestCase):
    def test_valid_tool_schema(self) -> None:
        """Schema with name, description, input_schema → no errors."""
        schema = {
            "name": "law_search",
            "description": "Search legal databases",
            "input_schema": {"type": "object", "properties": {}},
        }
        errors = validate_tool_schema(schema)
        self.assertEqual(errors, [])

    def test_valid_tool_schema_no_description(self) -> None:
        """Schema without description → no errors."""
        schema = {
            "name": "law_search",
            "input_schema": {"type": "object"},
        }
        errors = validate_tool_schema(schema)
        self.assertEqual(errors, [])

    def test_missing_name(self) -> None:
        """Schema without name → error."""
        schema = {
            "input_schema": {"type": "object"},
        }
        errors = validate_tool_schema(schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("name", errors[0])

    def test_missing_input_schema(self) -> None:
        """Schema without input_schema → error."""
        schema = {
            "name": "law_search",
        }
        errors = validate_tool_schema(schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("input_schema", errors[0])

    def test_input_schema_missing_type(self) -> None:
        """input_schema without type → error."""
        schema = {
            "name": "law_search",
            "input_schema": {"properties": {}},
        }
        errors = validate_tool_schema(schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("type", errors[0])

    def test_schema_not_dict(self) -> None:
        """Non-dict schema → error."""
        errors = validate_tool_schema("not a dict")
        self.assertEqual(len(errors), 1)
        self.assertIn("dict", errors[0])


class ValidateToolSchemasTests(unittest.TestCase):
    def test_empty_schema_list(self) -> None:
        """Empty list → no errors."""
        errors = validate_tool_schemas([])
        self.assertEqual(errors, [])

    def test_multiple_schemas_aggregate_errors(self) -> None:
        """Multiple invalid schemas → all errors returned."""
        schemas = [
            {"input_schema": {"type": "object"}},  # missing name
            {"name": "tool2"},  # missing input_schema
        ]
        errors = validate_tool_schemas(schemas)
        self.assertEqual(len(errors), 2)
        self.assertIn("tool[0]", errors[0])
        self.assertIn("tool[1]", errors[1])

    def test_all_valid_schemas(self) -> None:
        """All valid schemas → no errors."""
        schemas = [
            {"name": "tool1", "input_schema": {"type": "object"}},
            {"name": "tool2", "input_schema": {"type": "string"}},
        ]
        errors = validate_tool_schemas(schemas)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
