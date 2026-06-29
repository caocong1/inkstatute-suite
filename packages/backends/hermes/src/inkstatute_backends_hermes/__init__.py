"""Hermes backend adapter package for the InkStatute platform runtime."""

from .adapter import HermesBackendAdapter, HermesOneShotResult, HermesOneShotRunner, is_high_risk_legal_approval
from .config import HermesBackendConfig
from .manifest import build_hermes_oneshot_manifest, build_probe_manifest
from .parity import ParityCase, ParityDimensionResult, ParityReport, evaluate_parity_cases, load_parity_cases
from .probe import HermesCapabilityProbe, HermesProbeIssue, HermesProbeReport, HermesProbeTransport
from .runs_api import HermesRunsClient, HermesRunsDisabledError, HermesRunsTransport, map_hermes_run_status

__all__ = [
    "HermesBackendAdapter",
    "HermesBackendConfig",
    "HermesCapabilityProbe",
    "HermesOneShotResult",
    "HermesOneShotRunner",
    "HermesProbeIssue",
    "HermesProbeReport",
    "HermesProbeTransport",
    "HermesRunsClient",
    "HermesRunsDisabledError",
    "HermesRunsTransport",
    "ParityCase",
    "ParityDimensionResult",
    "ParityReport",
    "build_hermes_oneshot_manifest",
    "build_probe_manifest",
    "evaluate_parity_cases",
    "is_high_risk_legal_approval",
    "load_parity_cases",
    "map_hermes_run_status",
]
