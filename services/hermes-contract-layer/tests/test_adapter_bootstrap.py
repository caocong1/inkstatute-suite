from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hermes_contract_layer.adapter_manifest import build_hermes_adapter_manifest
from hermes_contract_layer.bootstrap import (
    check_sanitized_bundle_manifest,
    probe_hermes_capabilities,
)
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


class HermesBootstrapProbeTests(unittest.TestCase):
    def test_probe_reports_missing_recorder_hook_without_live_hermes_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            profile = Path(tmp) / "profiles" / "lawfirm"
            (root / "gateway").mkdir(parents=True)
            (profile / "hooks" / "response_filter").mkdir(parents=True)
            contract_log = Path(tmp).parent / "inkstatute-contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("missing_recorder_hook", {issue.code for issue in report.issues})

    def test_probe_reports_contract_log_path_inside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            profile = Path(tmp) / "profiles" / "lawfirm"
            (root / "gateway").mkdir(parents=True)
            (profile / "hooks" / "response_filter").mkdir(parents=True)
            (profile / "hooks" / "response_filter_contract_result_recorder").mkdir(parents=True)
            contract_log = Path.cwd() / "runtime-contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("contract_log_inside_repo", {issue.code for issue in report.issues})

    def test_bundle_manifest_checker_passes_sanitized_manifest(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "bundles"
            / "lawfirm-profile-bundle.manifest.json"
        )

        report = check_sanitized_bundle_manifest(manifest_path)

        self.assertTrue(report.passed)
        self.assertEqual(report.issues, [])

    def test_bundle_manifest_checker_rejects_sensitive_indicators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unsafe-bundle.json"
            path.write_text(
                json.dumps(
                    {
                        "env": {"WECOM_TOKEN": "secret-value"},
                        "files": ["runtime/logs/feedback.jsonl", "customer/raw_payload.txt"],
                    }
                ),
                encoding="utf-8",
            )

            report = check_sanitized_bundle_manifest(path)

        self.assertFalse(report.passed)
        self.assertTrue({issue.code for issue in report.issues} >= {"forbidden_bundle_indicator"})


if __name__ == "__main__":
    unittest.main()
