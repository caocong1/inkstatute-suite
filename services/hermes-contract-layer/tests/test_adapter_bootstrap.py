from __future__ import annotations

import unittest

from hermes_contract_layer.adapter_manifest import build_hermes_adapter_manifest
from platform_contract.agent_adapter import validate_agent_backend_manifest


class HermesAdapterManifestTests(unittest.TestCase):
    def test_default_hermes_manifest_validates_and_has_no_channel_io(self) -> None:
        manifest = build_hermes_adapter_manifest(
            backend_version="hermes-fixture-1",
            profile_name="lawfirm",
        )

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertEqual(manifest["mode"], "hermes")
        self.assertIs(manifest["capabilities"]["no_channel_io"], True)
        self.assertIn("agent:end", manifest["capabilities"]["hook_event_support"])

    def test_manifest_records_after_filter_recorder_and_channel_owner(self) -> None:
        manifest = build_hermes_adapter_manifest(
            backend_version="hermes-fixture-1",
            profile_name="lawfirm",
        )

        self.assertEqual(
            manifest["metadata"]["after_filter_recorder_dir"],
            "response_filter_contract_result_recorder",
        )
        self.assertIn(
            "response_filter_contract_result_recorder",
            manifest["metadata"]["repo_hook_artifacts"],
        )
        self.assertEqual(
            manifest["metadata"]["ordinary_wecom_channel_owner"],
            "inkstatute_wecom_service",
        )


if __name__ == "__main__":
    unittest.main()
