from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, Mapping

from contract_test_suite.schema_validation import _validate_schema, load_schemas
from platform_contract.agent_adapter import validate_agent_backend_manifest


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "phase55_non_hermes_adapter_manifest.json"
)


class AgentAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.schema = cls.schemas["agent_adapter_manifest"]

    def test_hermes_style_manifest_validates_against_schema_and_bindings(self) -> None:
        manifest = {
            "adapter_name": "hermes-lawfirm",
            "adapter_version": "0.1.0",
            "mode": "hermes",
            "backend_version": "hermes-fixture-1",
            "profile_name": "lawfirm",
            "bundle_id": "lawfirm-profile-bundle",
            "capabilities": {
                "hook_event_support": ["agent:end"],
                "invocation_mode": "sync",
                "feedback_target_support": "message_id",
                "session_read_support": True,
                "artifact_return_support": True,
                "trace_support": True,
                "no_channel_io": True,
            },
            "metadata": {"production_ready": True},
        }

        self.assert_schema_valid(manifest)
        self.assertEqual(validate_agent_backend_manifest(manifest), [])

    def test_non_hermes_provider_model_fixture_validates(self) -> None:
        manifest = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assert_schema_valid(manifest)
        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertEqual(manifest["mode"], "provider_model")
        self.assertIs(manifest["capabilities"]["no_channel_io"], True)

    def test_schema_does_not_require_hermes_or_lawfirm_fields_for_provider_model(self) -> None:
        top_level_required = set(self.schema.get("required", []))
        properties = set(self.schema.get("properties", {}))
        forbidden = {
            "hermes_hook_names",
            "hook_names",
            "profile_path",
            "hermes_profile_path",
            "lawfirm",
            "lawfirm_profile",
        }

        self.assertFalse(top_level_required & forbidden)
        self.assertFalse(properties & {"case_type", "jurisdiction", "raw_payload"})

        manifest = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for forbidden_field in forbidden:
            self.assertNotIn(forbidden_field, manifest)

    def assert_schema_valid(self, manifest: Mapping[str, Any]) -> None:
        _validate_schema(
            self.schema,
            manifest,
            self.schemas,
            path=("agent_adapter_manifest",),
        )


if __name__ == "__main__":
    unittest.main()
