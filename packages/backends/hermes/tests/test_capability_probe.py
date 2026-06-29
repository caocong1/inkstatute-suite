from __future__ import annotations

import unittest
from pathlib import Path
from typing import Mapping

from platform_contract.agent_adapter import validate_agent_backend_manifest

from inkstatute_backends_hermes import HermesBackendConfig, HermesCapabilityProbe, build_probe_manifest
from inkstatute_backends_hermes.probe import SAFE_PROBE_PATHS


REPO_ROOT = Path(__file__).resolve().parents[4]


class FakeTransport:
    def __init__(self, responses: dict[str, Mapping[str, object]] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or {}
        self.error = error
        self.paths: list[str] = []

    def get_json(self, path: str) -> Mapping[str, object]:
        self.paths.append(path)
        if self.error is not None:
            raise self.error
        return self.responses.get(path, {})


class HermesCapabilityProbeTests(unittest.TestCase):
    def test_probe_calls_only_safe_non_mutating_paths(self) -> None:
        transport = FakeTransport(
            {
                "/health": {"ok": True},
                "/v1/capabilities": {},
                "/v1/models": {"models": ["lawfirm-model"]},
            }
        )

        report = HermesCapabilityProbe(transport).probe()

        self.assertEqual(transport.paths, list(SAFE_PROBE_PATHS))
        self.assertEqual(transport.paths, ["/health", "/v1/capabilities", "/v1/models"])
        self.assertTrue(all(not path.startswith("/v1/runs") for path in transport.paths))
        self.assertTrue(report.ok)
        self.assertEqual(report.models, ["lawfirm-model"])

    def test_probe_module_has_no_network_or_run_state_probe_dependency(self) -> None:
        probe_text = (REPO_ROOT / "packages/backends/hermes/src/inkstatute_backends_hermes/probe.py").read_text(
            encoding="utf-8"
        )

        for forbidden in ("requests", "httpx", "aiohttp", "urllib.request.urlopen", "subprocess", "socket("):
            self.assertNotIn(forbidden, probe_text)
        self.assertNotIn('"/v1/runs/"', probe_text)

    def test_missing_capability_fields_fall_back_to_valid_oneshot_manifest(self) -> None:
        transport = FakeTransport(
            {
                "/health": {"ok": True},
                "/v1/capabilities": {},
                "/v1/models": {},
            }
        )

        report = HermesCapabilityProbe(transport).probe()
        manifest = build_probe_manifest(HermesBackendConfig(), report)

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertEqual(manifest.capabilities.run_invocation_modes, ["oneshot"])
        self.assertIs(manifest.capabilities.no_channel_io, True)
        self.assertEqual(manifest.metadata["fallback_reason"], "runs_api_not_advertised")

    def test_explicit_run_support_maps_to_api_capable_manifest(self) -> None:
        transport = FakeTransport(
            {
                "/health": {"ok": True},
                "/v1/capabilities": {
                    "run_invocation_modes": ["oneshot", "runs_api"],
                    "stream_event_support": True,
                    "cancel_support": True,
                    "approval_support": False,
                    "artifact_return_support": True,
                    "trace_support": True,
                },
                "/v1/models": {"models": ["lawfirm-model", "general-model"]},
            }
        )

        report = HermesCapabilityProbe(transport).probe()
        manifest = build_probe_manifest(HermesBackendConfig(), report)

        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertIn("runs_api", manifest.capabilities.run_invocation_modes)
        self.assertTrue(manifest.capabilities.stream_event_support)
        self.assertTrue(manifest.capabilities.cancel_support)
        self.assertIs(manifest.capabilities.no_channel_io, True)
        self.assertEqual(manifest.metadata["opt_in_lane"], "runs_api")
        self.assertFalse(manifest.metadata["runs_api_default_enabled"])

    def test_probe_failure_falls_back_with_sanitized_audit_reason(self) -> None:
        error = RuntimeError("https://hermes.example.test?token=secret /.hermes/lawfirm")
        transport = FakeTransport(error=error)

        report = HermesCapabilityProbe(transport).probe()
        manifest = build_probe_manifest(HermesBackendConfig(), report)
        combined = f"{report!r} {manifest!r}"

        self.assertFalse(report.ok)
        self.assertEqual(transport.paths, ["/health"])
        self.assertEqual(report.fallback_reason, "probe_endpoint_unavailable")
        self.assertEqual(manifest.metadata["fallback_reason"], "probe_endpoint_unavailable")
        self.assertEqual(validate_agent_backend_manifest(manifest), [])
        self.assertIs(manifest.capabilities.no_channel_io, True)
        for forbidden in ("token=", "http://", "https://", "/.hermes/"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()

