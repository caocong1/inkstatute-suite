from __future__ import annotations

import json
import unittest
from pathlib import Path

from platform_contract import (
    AgentBackendManifest,
    AgentBackendMode,
    AdapterCapabilitySet,
    validate_agent_backend_manifest,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "platform_contract"
    / "schemas"
    / "agent_adapter_manifest.schema.json"
)


class AgentAdapterManifestTests(unittest.TestCase):
    def test_backend_modes_are_backend_neutral(self) -> None:
        self.assertEqual(AgentBackendMode.HERMES.value, "hermes")
        self.assertEqual(AgentBackendMode.CODEX.value, "codex")
        self.assertEqual(AgentBackendMode.PROVIDER_MODEL.value, "provider_model")

    def test_valid_hermes_manifest_has_no_validation_issues(self) -> None:
        manifest = AgentBackendManifest(
            adapter_name="hermes-lawfirm",
            adapter_version="0.1.0",
            mode=AgentBackendMode.HERMES,
            backend_version="hermes-fixture-1",
            profile_name="lawfirm",
            bundle_id="lawfirm-profile-bundle",
            capabilities=AdapterCapabilitySet(
                hook_event_support=["agent:end", "gateway:startup"],
                invocation_mode="sync",
                feedback_target_support="message_id",
                session_read_support=True,
                artifact_return_support=True,
                trace_support=True,
                no_channel_io=True,
            ),
        )

        self.assertEqual(validate_agent_backend_manifest(manifest), [])

    def test_unsupported_mode_returns_structured_issue(self) -> None:
        manifest = {
            "adapter_name": "future",
            "adapter_version": "0.1.0",
            "mode": "unsupported",
            "backend_version": "future-1",
            "capabilities": {
                "hook_event_support": [],
                "invocation_mode": "async",
                "feedback_target_support": "generated",
                "session_read_support": False,
                "artifact_return_support": True,
                "trace_support": True,
                "no_channel_io": True,
            },
        }

        issues = validate_agent_backend_manifest(manifest)

        self.assertIn("unsupported_mode", {issue["code"] for issue in issues})

    def test_missing_adapter_identity_returns_structured_issues(self) -> None:
        manifest = self.valid_manifest_dict()
        del manifest["adapter_name"]
        manifest["adapter_version"] = " "

        issues = validate_agent_backend_manifest(manifest)

        self.assertIn("missing_adapter_name", {issue["code"] for issue in issues})
        self.assertIn("missing_adapter_version", {issue["code"] for issue in issues})

    def test_missing_or_non_boolean_no_channel_io_returns_issue(self) -> None:
        missing = self.valid_manifest_dict()
        del missing["capabilities"]["no_channel_io"]
        non_boolean = self.valid_manifest_dict()
        non_boolean["capabilities"]["no_channel_io"] = "true"

        self.assertIn(
            "missing_no_channel_io",
            {issue["code"] for issue in validate_agent_backend_manifest(missing)},
        )
        self.assertIn(
            "invalid_no_channel_io",
            {issue["code"] for issue in validate_agent_backend_manifest(non_boolean)},
        )

    def test_manifest_schema_has_industry_neutral_top_level_requirements(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        required = set(schema["required"])
        forbidden = {"case_type", "jurisdiction", "statute", "lawfirm", "hermes_profile_path"}

        self.assertFalse(required & forbidden)
        self.assertFalse(set(schema["properties"]) & {"case_type", "jurisdiction", "raw_payload"})
        self.assertFalse(
            {"hook_names", "profile_path", "lawfirm"} <= set(schema["required"]),
            "schema must not require Hermes hook names, profile paths, or lawfirm fields",
        )

    def valid_manifest_dict(self) -> dict[str, object]:
        return {
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
            "metadata": {},
        }


if __name__ == "__main__":
    unittest.main()
