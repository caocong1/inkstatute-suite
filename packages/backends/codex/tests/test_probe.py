from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path

from platform_contract.agent_adapter import validate_agent_backend_manifest

from inkstatute_backends_codex import (
    CodexCapabilityProbe,
    build_codex_manifest,
)
from inkstatute_backends_codex.manifest import codex_prototype_capabilities


REPO_ROOT = Path(__file__).resolve().parents[4]


class FakeTransport:
    def __init__(self, version: str = "codex 1.0.0", error: Exception | None = None) -> None:
        self.version = version
        self.error = error

    def run_version(self) -> str:
        if self.error is not None:
            raise self.error
        return self.version


class CodexCapabilityProbeTests(unittest.TestCase):
    def test_probe_returns_14_field_capability_set(self) -> None:
        report = CodexCapabilityProbe(FakeTransport()).probe()

        self.assertTrue(report.ok)
        self.assertEqual(len(fields(report.capabilities)), 14)
        self.assertIs(report.capabilities.no_channel_io, True)
        self.assertEqual(report.codex_version, "codex 1.0.0")

    def test_probe_does_not_invoke_codex_exec(self) -> None:
        probe_text = (
            REPO_ROOT / "packages" / "backends" / "codex" / "src" / "inkstatute_backends_codex" / "probe.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("codex exec", probe_text)

    def test_probe_failure_returns_ok_false_with_issue(self) -> None:
        report = CodexCapabilityProbe(FakeTransport(error=RuntimeError("not found"))).probe()

        self.assertFalse(report.ok)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].code, "codex_binary_unavailable")
        self.assertIs(report.capabilities.no_channel_io, True)

    def test_probe_report_capabilities_validate_in_manifest(self) -> None:
        report = CodexCapabilityProbe(FakeTransport()).probe()
        manifest = build_codex_manifest()

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertEqual(manifest.capabilities, report.capabilities)
        self.assertEqual(report.capabilities, codex_prototype_capabilities())


if __name__ == "__main__":
    unittest.main()
