from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path

from platform_contract.agent_adapter import validate_agent_backend_manifest

from inkstatute_backends_provider_model import (
    ProviderModelCapabilityProbe,
    build_provider_model_manifest,
)
from inkstatute_backends_provider_model.manifest import provider_model_prototype_capabilities


REPO_ROOT = Path(__file__).resolve().parents[4]


class FakeTransport:
    def __init__(self, available: bool = True) -> None:
        self.available = available

    def check_sdk_available(self) -> bool:
        return self.available


class ProviderModelCapabilityProbeTests(unittest.TestCase):
    def test_probe_returns_15_field_capability_set(self) -> None:
        report = ProviderModelCapabilityProbe(FakeTransport()).probe()

        self.assertTrue(report.ok)
        self.assertEqual(len(fields(report.capabilities)), 15)
        self.assertIs(report.capabilities.no_channel_io, True)
        self.assertIs(report.sdk_available, True)

    def test_probe_does_not_make_api_calls(self) -> None:
        probe_text = (
            REPO_ROOT
            / "packages"
            / "backends"
            / "provider_model"
            / "src"
            / "inkstatute_backends_provider_model"
            / "probe.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("chat.completions", probe_text)
        self.assertNotIn("create(", probe_text)

    def test_probe_does_not_import_openai_at_module_level(self) -> None:
        probe_text = (
            REPO_ROOT
            / "packages"
            / "backends"
            / "provider_model"
            / "src"
            / "inkstatute_backends_provider_model"
            / "probe.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("import openai", probe_text)
        self.assertNotIn("from openai", probe_text)

    def test_probe_failure_returns_ok_false_with_issue(self) -> None:
        report = ProviderModelCapabilityProbe(FakeTransport(available=False)).probe()

        self.assertFalse(report.ok)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].code, "openai_sdk_unavailable")
        self.assertIs(report.capabilities.no_channel_io, True)

    def test_probe_report_capabilities_validate_in_manifest(self) -> None:
        report = ProviderModelCapabilityProbe(FakeTransport()).probe()
        manifest = build_provider_model_manifest()

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertEqual(manifest.capabilities, report.capabilities)
        self.assertEqual(report.capabilities, provider_model_prototype_capabilities())


if __name__ == "__main__":
    unittest.main()
