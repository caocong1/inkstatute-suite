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


class HermesBootstrapEdgeCaseTests(unittest.TestCase):
    def test_probe_reports_missing_hermes_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nonexistent-hermes"
            profile = Path(tmp) / "profiles" / "lawfirm"
            profile.mkdir(parents=True)
            contract_log = Path(tmp).parent / "contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("missing_hermes_root", {issue.code for issue in report.issues})
        self.assertFalse(report.capabilities["hermes_root_exists"])

    def test_probe_reports_missing_version_or_source_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            root.mkdir(parents=True)
            profile = Path(tmp) / "profiles" / "lawfirm"
            (profile / "hooks" / "response_filter").mkdir(parents=True)
            (profile / "hooks" / "response_filter_contract_result_recorder").mkdir(parents=True)
            contract_log = Path(tmp).parent / "contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("missing_version_or_source", {issue.code for issue in report.issues})

    def test_probe_reports_missing_profile_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            (root / "gateway").mkdir(parents=True)
            profile = Path(tmp) / "profiles" / "nonexistent-profile"
            contract_log = Path(tmp).parent / "contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("missing_profile_path", {issue.code for issue in report.issues})
        self.assertFalse(report.capabilities["profile_exists"])

    def test_probe_reports_missing_response_filter_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            (root / "gateway").mkdir(parents=True)
            profile = Path(tmp) / "profiles" / "lawfirm"
            profile.mkdir(parents=True)
            contract_log = Path(tmp).parent / "contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertFalse(report.passed)
        self.assertIn("missing_response_filter_hook", {issue.code for issue in report.issues})
        self.assertFalse(report.capabilities["response_filter_present"])

    def test_version_marker_reads_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes-agent"
            root.mkdir(parents=True)
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            profile = Path(tmp) / "profiles" / "lawfirm"
            (profile / "hooks" / "response_filter").mkdir(parents=True)
            (profile / "hooks" / "response_filter_contract_result_recorder").mkdir(parents=True)
            contract_log = Path(tmp).parent / "contract-log.jsonl"

            report = probe_hermes_capabilities(root, profile, contract_log)

        self.assertTrue(report.capabilities["hermes_root_exists"])
        issue_codes = {issue.code for issue in report.issues}
        self.assertNotIn("missing_hermes_root", issue_codes)
        self.assertNotIn("missing_version_or_source", issue_codes)

    def test_bundle_manifest_missing_file_returns_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "does-not-exist.json"

            report = check_sanitized_bundle_manifest(path)

        self.assertFalse(report.passed)
        self.assertEqual(report.issues[0].code, "missing_bundle_manifest")


if __name__ == "__main__":
    unittest.main()
