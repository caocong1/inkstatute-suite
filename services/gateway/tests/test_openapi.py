"""Tests for the full OpenAPI 3.1 document of the InkStatute Gateway.

Verifies that the OpenAPI document covers all 12 endpoints, has complete
schemas with tenant_id in all response schemas, security schemes, the
Last-Event-ID header parameter, deterministic rendering, and basic
validation passes.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from gateway.openapi import (
    API_TITLE,
    OPENAPI_VERSION,
    build_openapi_document,
    render_openapi_json,
    validate_openapi_document,
)


EXPECTED_PATHS = [
    "/v1/sessions",
    "/v1/sessions/{session_id}",
    "/v1/sessions/{session_id}/runs",
    "/v1/runs",
    "/v1/runs/{run_id}",
    "/v1/runs/{run_id}/events",
    "/v1/runs/{run_id}/elicitation",
    "/v1/runs/{run_id}/approvals",
    "/v1/artifacts/{artifact_id}",
    "/v1/uploads",
    "/v1/feedback",
    "/v1/skills",
]

EXPECTED_TAGS = {
    "Sessions",
    "Runs",
    "Stream",
    "Elicitation",
    "Approvals",
    "Artifacts",
    "Uploads",
    "Feedback",
    "Skills",
}

_HTTP_METHODS = ("get", "post", "put", "delete", "patch")


class TestOpenApiDocument(unittest.TestCase):
    """Validate the Gateway OpenAPI 3.1 document."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = build_openapi_document()
        cls.json_str = render_openapi_json(cls.document)

    # ------------------------------------------------------------------
    # 1. OpenAPI version
    # ------------------------------------------------------------------

    def test_openapi_version(self) -> None:
        self.assertEqual(self.document["openapi"], OPENAPI_VERSION)
        self.assertEqual(self.document["openapi"], "3.1.0")

    # ------------------------------------------------------------------
    # 2. API title
    # ------------------------------------------------------------------

    def test_api_title(self) -> None:
        self.assertEqual(self.document["info"]["title"], API_TITLE)
        self.assertEqual(self.document["info"]["title"], "InkStatute Gateway API")

    # ------------------------------------------------------------------
    # 3. All 12 paths present
    # ------------------------------------------------------------------

    def test_all_12_paths_present(self) -> None:
        paths = self.document["paths"]
        for expected in EXPECTED_PATHS:
            self.assertIn(expected, paths, f"Missing path: {expected}")
        self.assertEqual(len(paths), 12, f"Expected 12 paths, got {len(paths)}")

    # ------------------------------------------------------------------
    # 4. All operations have operationId
    # ------------------------------------------------------------------

    def test_all_operations_have_operationId(self) -> None:
        for path, path_item in self.document["paths"].items():
            for method, op in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                self.assertIn(
                    "operationId",
                    op,
                    f"{method.upper()} {path} missing operationId",
                )
                self.assertTrue(
                    op["operationId"],
                    f"{method.upper()} {path} has empty operationId",
                )

    # ------------------------------------------------------------------
    # 5. All operations have responses
    # ------------------------------------------------------------------

    def test_all_operations_have_responses(self) -> None:
        for path, path_item in self.document["paths"].items():
            for method, op in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                self.assertIn(
                    "responses",
                    op,
                    f"{method.upper()} {path} missing responses",
                )
                self.assertTrue(
                    op["responses"],
                    f"{method.upper()} {path} has empty responses",
                )

    # ------------------------------------------------------------------
    # 6. All response schemas have tenant_id
    # ------------------------------------------------------------------

    def test_all_response_schemas_have_tenant_id(self) -> None:
        """Every schema referenced in a 200/201 JSON response must include tenant_id."""
        schemas = self.document["components"]["schemas"]
        response_schema_names: set[str] = set()
        for path_item in self.document["paths"].values():
            for method, op in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                for status_code, response in op.get("responses", {}).items():
                    if status_code not in ("200", "201"):
                        continue
                    content = response.get("content", {})
                    for media_type_key, media_type in content.items():
                        # SSE frames (text/event-stream) are not JSON response schemas.
                        if media_type_key == "text/event-stream":
                            continue
                        schema = media_type.get("schema", {})
                        ref = schema.get("$ref")
                        if ref and ref.startswith("#/components/schemas/"):
                            response_schema_names.add(ref[len("#/components/schemas/"):])
        for name in response_schema_names:
            schema = schemas.get(name, {})
            properties = schema.get("properties", {})
            self.assertIn(
                "tenant_id",
                properties,
                f"Response schema '{name}' is missing tenant_id property",
            )

    # ------------------------------------------------------------------
    # 7. Security schemes present
    # ------------------------------------------------------------------

    def test_security_schemes_present(self) -> None:
        security_schemes = self.document["components"]["securitySchemes"]
        self.assertIn("BearerAuth", security_schemes)
        self.assertIn("SessionCookie", security_schemes)
        self.assertEqual(security_schemes["BearerAuth"]["type"], "http")
        self.assertEqual(security_schemes["BearerAuth"]["scheme"], "bearer")
        self.assertEqual(security_schemes["SessionCookie"]["type"], "apiKey")
        self.assertEqual(security_schemes["SessionCookie"]["in"], "cookie")

    # ------------------------------------------------------------------
    # 8. All operations have security
    # ------------------------------------------------------------------

    def test_all_operations_have_security(self) -> None:
        for path, path_item in self.document["paths"].items():
            for method, op in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                self.assertIn(
                    "security",
                    op,
                    f"{method.upper()} {path} missing security requirement",
                )
                self.assertTrue(
                    op["security"],
                    f"{method.upper()} {path} has empty security",
                )

    # ------------------------------------------------------------------
    # 9. streamRun has Last-Event-ID header parameter
    # ------------------------------------------------------------------

    def test_stream_run_has_last_event_id_param(self) -> None:
        stream_op = self.document["paths"]["/v1/runs/{run_id}/events"]["get"]
        params = stream_op.get("parameters", [])
        last_event_id_params = [p for p in params if p.get("name") == "Last-Event-ID"]
        self.assertEqual(len(last_event_id_params), 1, "Last-Event-ID parameter not found")
        param = last_event_id_params[0]
        self.assertEqual(param["in"], "header")
        self.assertFalse(param["required"])
        self.assertEqual(param["schema"]["type"], "integer")

    # ------------------------------------------------------------------
    # 10. All tags defined
    # ------------------------------------------------------------------

    def test_all_tags_defined(self) -> None:
        tags = self.document.get("tags", [])
        tag_names = {t["name"] for t in tags}
        for expected_tag in EXPECTED_TAGS:
            self.assertIn(expected_tag, tag_names, f"Missing tag: {expected_tag}")
        for tag in tags:
            self.assertIn("description", tag, f"Tag '{tag['name']}' missing description")
        self.assertEqual(len(tags), 9, f"Expected 9 tags, got {len(tags)}")

    # ------------------------------------------------------------------
    # 11. Render is deterministic (byte-stable)
    # ------------------------------------------------------------------

    def test_render_is_deterministic(self) -> None:
        doc1 = build_openapi_document()
        doc2 = build_openapi_document()
        json1 = render_openapi_json(doc1)
        json2 = render_openapi_json(doc2)
        self.assertEqual(json1, json2, "render_openapi_json is not byte-stable")

    # ------------------------------------------------------------------
    # 12. Render is valid JSON
    # ------------------------------------------------------------------

    def test_render_is_valid_json(self) -> None:
        parsed = json.loads(self.json_str)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["openapi"], "3.1.0")

    # ------------------------------------------------------------------
    # 13. validate_openapi_document returns empty list
    # ------------------------------------------------------------------

    def test_validate_openapi_document(self) -> None:
        errors = validate_openapi_document(self.document)
        self.assertEqual(errors, [], f"Validation errors: {errors}")

    # ------------------------------------------------------------------
    # 14. Examples are sanitized
    # ------------------------------------------------------------------

    def test_examples_are_sanitized(self) -> None:
        """No example contains real tenant IDs or real legal content."""
        json_text = self.json_str
        # Real tenant IDs would not use "tenant-example" — check for sanitized marker.
        self.assertIn("tenant-example", json_text)
        # No real legal content patterns (case numbers, real names, etc.)
        forbidden_patterns = [
            "原告",
            "被告",
            "案号",
            "判决书",
            "(2024)",
            "(2023)",
        ]
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern, json_text, f"Forbidden pattern in examples: {pattern}")

    # ------------------------------------------------------------------
    # 15. Upload example has reference_only: true
    # ------------------------------------------------------------------

    def test_upload_example_reference_only(self) -> None:
        upload_op = self.document["paths"]["/v1/uploads"]["post"]
        # Check request example
        req_examples = upload_op["requestBody"]["content"]["application/json"]["examples"]
        for example in req_examples.values():
            value = example.get("value", {})
            self.assertTrue(
                value.get("reference_only"),
                "Upload request example missing reference_only: true",
            )
        # Check response example
        resp_example = upload_op["responses"]["200"]["content"]["application/json"]["examples"]
        for example in resp_example.values():
            value = example.get("value", {})
            self.assertTrue(
                value.get("reference_only"),
                "Upload response example missing reference_only: true",
            )

    # ------------------------------------------------------------------
    # 16. Artifact example has reference_only: true
    # ------------------------------------------------------------------

    def test_artifact_example_reference_only(self) -> None:
        artifact_op = self.document["paths"]["/v1/artifacts/{artifact_id}"]["get"]
        resp_example = artifact_op["responses"]["200"]["content"]["application/json"]["examples"]
        for example in resp_example.values():
            value = example.get("value", {})
            self.assertTrue(
                value.get("reference_only"),
                "Artifact response example missing reference_only: true",
            )

    # ------------------------------------------------------------------
    # 17. All $ref pointers resolve
    # ------------------------------------------------------------------

    def test_all_refs_resolve(self) -> None:
        schemas = self.document["components"]["schemas"]
        unresolved: list[str] = []

        def _check_ref(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                    schema_name = ref[len("#/components/schemas/"):]
                    if schema_name not in schemas:
                        unresolved.append(f"{ref} at {path}")
                for key, value in node.items():
                    _check_ref(value, f"{path}/{key}" if path else key)
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    _check_ref(item, f"{path}[{i}]")

        _check_ref(self.document)
        self.assertEqual(unresolved, [], f"Unresolved $ref pointers: {unresolved}")

    # ------------------------------------------------------------------
    # 18. No duplicate operationIds
    # ------------------------------------------------------------------

    def test_no_duplicate_operationIds(self) -> None:
        operation_ids: list[str] = []
        for path_item in self.document["paths"].values():
            for method, op in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                operation_ids.append(op["operationId"])
        self.assertEqual(
            len(operation_ids),
            len(set(operation_ids)),
            f"Duplicate operationIds: {operation_ids}",
        )


if __name__ == "__main__":
    unittest.main()
